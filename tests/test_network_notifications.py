"""Offline IPv4 observations, incident transitions and bounded provider contract."""

from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest

from hixton.notifications import network
from hixton.notifications.network import NetworkMonitor, NetworkObservation, public_ipv4
from tests.test_notifications import save, setup_service

NOW = datetime(2026, 10, 31, 8, 30, tzinfo=UTC)
IP1, IP2 = "8.8.8.8", "1.1.1.1"
SCOPE = "0123456789ab"


def obs(ip=IP1, *, at=NOW, state="CURRENT", code=None, account_at=None, scope=SCOPE):
    return NetworkObservation(ip, at, state, code, account_at or at, scope)


def network_service(tmp_path):
    service, sender, _, clock = setup_service(tmp_path)
    clock[0] = NOW
    latest = [obs()]
    service.network_provider = lambda: latest[0]
    save(service, operations_enabled=True)
    return service, sender, clock, latest


@pytest.mark.parametrize("value", [
    None, "", "127.0.0.1", "192.168.0.1", "0.0.0.0", "169.254.1.1", "224.0.0.1",
    "255.255.255.255", "2001:4860:4860::8888", "<html>fail</html>", "8.8.8.8\nTOKEN",
])
def test_reject_non_global_ipv4_or_arbitrary_text(value):
    assert public_ipv4(value) is None


def test_fixed_bounded_proxy_free_probe(monkeypatch):
    calls = []

    class Response(BytesIO):
        def read(self, limit=-1):
            assert limit == 64
            return super().read(limit)

    class Opener:
        def open(self, request, *, timeout):
            assert request.full_url == "https://api.ipify.org" and timeout == 3
            assert set(request.headers) == {"User-agent"}
            calls.append(request)
            return Response(b"8.8.8.8\n")

    monkeypatch.setattr(network, "build_opener", lambda *handlers: Opener())
    assert network.read_public_ipv4() == IP1
    assert len(calls) == 1


def test_baseline_no_notice_change_one_notice_escalation_and_positive_recovery(tmp_path):
    service, sender, clock, latest = network_service(tmp_path)
    service.cycle()
    assert not sender.sent
    clock[0] += timedelta(seconds=30)
    latest[0] = obs(IP2, at=clock[0], state="UNAVAILABLE", code=-2015)
    service.cycle()
    assert len(sender.sent) == 1
    assert IP2 in sender.sent[0][2] and "-2015" in sender.sent[0][2]
    assert "Schlüssel oder Berechtigungen" in sender.sent[0][2]
    for _ in range(10):
        service.cycle()
    assert len(sender.sent) == 1
    clock[0] += timedelta(seconds=30)
    latest[0] = obs(IP2, at=clock[0])
    service.cycle()
    assert len(sender.sent) == 2 and "wieder bestätigt" in sender.sent[-1][1]
    assert "keinen Verkauf" in sender.sent[-1][2]
    service.cycle()
    assert len(sender.sent) == 2


def test_restart_dedup_pending_delivery_and_private_public_status(tmp_path):
    service, sender, clock, latest = network_service(tmp_path)
    service.cycle()
    sender.fail = True
    clock[0] += timedelta(seconds=30)
    latest[0] = obs(IP2, at=clock[0], state="UNAVAILABLE", code=-2015)
    service.cycle()
    assert service.status(True)["pending"] == 1
    restarted = type(service)(
        service.path, service.live_database, service.vault, client=sender,
        collector=lambda _: (), clock=lambda: clock[0], network_provider=lambda: latest[0],
    )
    assert IP2 not in str(restarted.status(False))
    clock[0] += timedelta(seconds=65)
    latest[0] = obs(IP2, at=clock[0], state="UNAVAILABLE", code=-2015)
    sender.fail = False
    restarted.cycle()
    restarted.cycle()
    assert len(sender.sent) == 1 and restarted.status(True)["pending"] == 0


def test_stale_future_and_different_account_cannot_clear_incident(tmp_path):
    service, sender, clock, latest = network_service(tmp_path)
    latest[0] = obs(state="UNAVAILABLE", code=-2015)
    service.cycle()
    assert len(sender.sent) == 1
    clock[0] += timedelta(seconds=30)
    for account_at, scope in [
        (NOW - timedelta(seconds=1), SCOPE),
        (clock[0] + timedelta(seconds=1), SCOPE),
        (clock[0], "differentkey"),
    ]:
        latest[0] = obs(at=clock[0], account_at=account_at, scope=scope)
        service.cycle()
    assert len(sender.sent) == 1


def test_ip_failure_does_not_reset_baseline_or_recover_and_later_change_is_detected(tmp_path):
    service, sender, clock, latest = network_service(tmp_path)
    service.cycle()
    clock[0] += timedelta(seconds=30)
    latest[0] = NetworkObservation()
    service.cycle()
    assert not sender.sent
    latest[0] = obs(IP2, at=clock[0], state="UNKNOWN")
    service.cycle()
    assert len(sender.sent) == 1 and IP2 in sender.sent[0][2]


def test_monitor_opt_in_and_independent_read_only_refresh():
    enabled, calls = [False], []
    monitor = NetworkMonitor(
        enabled=lambda: enabled[0], ip_reader=lambda: calls.append("ip") or IP1,
        account_read=lambda: calls.append("signed-account-get"), clock=lambda: NOW,
        account_health=lambda: {"state": "UNAVAILABLE", "code": -2015, "fresh": True,
                                "observed_at_utc": NOW.isoformat(), "account_scope": SCOPE},
    )
    monitor.sample()
    assert not calls
    enabled[0] = True
    monitor.sample()
    assert calls == ["ip", "signed-account-get"]
    assert monitor.snapshot() == obs(state="UNAVAILABLE", code=-2015)


def test_changed_then_rejected_adds_action_once_and_opt_out_resets(tmp_path):
    service, sender, clock, latest = network_service(tmp_path)
    service.cycle()
    clock[0] += timedelta(seconds=30)
    latest[0] = obs(IP2, at=clock[0], state="UNKNOWN")
    service.cycle()
    clock[0] += timedelta(seconds=30)
    latest[0] = obs(IP2, at=clock[0], state="UNAVAILABLE", code=-2015)
    service.cycle()
    service.cycle()
    assert len(sender.sent) == 2
    save(service, secret="", operations_enabled=False)
    with service._connect() as db:
        assert db.execute("SELECT count(*) FROM network_notice_state").fetchone()[0] == 0
    service.cycle()
    assert len(sender.sent) == 2


def test_outbox_failure_rolls_back_network_transition_and_retry(tmp_path: Path):
    service, sender, clock, latest = network_service(tmp_path)
    service.cycle()
    clock[0] += timedelta(seconds=30)
    latest[0] = obs(IP2, at=clock[0], state="UNAVAILABLE", code=-2015)
    with service._connect() as db:
        db.execute("CREATE TRIGGER fail_insert BEFORE INSERT ON notification_outbox "
                   "BEGIN SELECT RAISE(ABORT,'offline fake disk failure'); END")
    with pytest.raises(Exception, match="offline fake disk failure"):
        service.cycle()
    with service._connect() as db:
        assert db.execute("SELECT ipv4 FROM network_notice_state").fetchone()[0] == IP1
        db.execute("DROP TRIGGER fail_insert")
    service.cycle()
    service.cycle()
    assert len(sender.sent) == 1
