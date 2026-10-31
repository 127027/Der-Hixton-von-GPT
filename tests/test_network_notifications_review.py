"""Independent failure probes: fake providers/vault and temporary journals only."""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from hixton.live.credentials import WindowsVault
from hixton.live.exchange import BinanceSpotTransport
from hixton.notifications import network
from hixton.notifications.network import NetworkMonitor, NetworkObservation
from hixton.notifications.operations import OperationsObservation, sample_operations
from hixton.notifications.service import NotificationService
from hixton.notifications.telegram import DeliveryError, TelegramClient

NOW = datetime(2026, 10, 31, 10, 30, tzinfo=UTC)
IP_A, IP_B = "8.8.8.8", "1.1.1.1"
SCOPE = "private-account-scope-canary"
TOKEN = "1234567:" + "OFFLINE_REVIEW_TOKEN_1234567890"


@pytest.fixture(autouse=True)
def reject_real_providers(monkeypatch: pytest.MonkeyPatch):
    unexpected: list[str] = []

    def forbidden(*args: Any, **kwargs: Any):
        unexpected.append("real-provider-or-vault")
        raise AssertionError("Independent review uses fake providers only")

    monkeypatch.setattr(network, "build_opener", forbidden)
    monkeypatch.setattr(TelegramClient, "_call", forbidden)
    monkeypatch.setattr(BinanceSpotTransport, "request", forbidden)
    for name in ("read", "write", "delete"):
        monkeypatch.setattr(WindowsVault, name, forbidden)
    yield
    assert not unexpected


class ReviewVault:
    def __init__(self):
        self.records = {"binance-hmac": "existing-fake-key", "local-password": "fake-password"}

    def read(self, name: str) -> str | None:
        return self.records.get(name)

    def write(self, name: str, value: str) -> None:
        self.records[name] = value

    def delete(self, name: str) -> None:
        self.records.pop(name, None)


class ReviewSender:
    def __init__(self):
        self.fail = False
        self.sent: list[tuple[str, str]] = []

    def send(self, token: str, recipient: str, title: str, body: str) -> str:
        assert token == TOKEN and recipient == "12345"
        if self.fail:
            raise DeliveryError("Fake Telegram connection outage")
        self.sent.append((title, body))
        return str(len(self.sent))


def observation(at: datetime, *, ip: str | None = IP_B, state: str = "UNAVAILABLE",
                code: int | None = -2015, account_at: datetime | None = None,
                scope: str | None = SCOPE) -> NetworkObservation:
    return NetworkObservation(ip, at if ip else None, state, code, account_at or at, scope)


def service_for(tmp_path: Path):
    clock = [NOW]
    latest = [observation(NOW, ip=IP_A, state="CURRENT", code=None)]
    vault, sender = ReviewVault(), ReviewSender()
    service = NotificationService(
        tmp_path / "outbox.sqlite3", tmp_path / "fake-live.sqlite3", vault,
        client=sender,  # type: ignore[arg-type]
        collector=lambda _: (), clock=lambda: clock[0], network_provider=lambda: latest[0],
        operations_provider=lambda: OperationsObservation((), {}, owned_real=True),
    )
    service.save({"enabled": True, "recipient": "12345", "secret": TOKEN,
                  "operations_enabled": True})
    return service, sender, vault, clock, latest


def state(service: NotificationService) -> dict[str, Any]:
    with service._connect() as connection:
        return dict(connection.execute("SELECT * FROM network_notice_state").fetchone())


def test_restart_retains_one_pending_warning_and_unknown_never_recovers(tmp_path: Path):
    service, sender, vault, clock, latest = service_for(tmp_path)
    service.cycle()
    assert not sender.sent
    clock[0] += timedelta(seconds=30)
    latest[0] = observation(clock[0])
    sender.fail = True
    service.cycle()
    original = state(service)
    assert original["episode"] and service.status(True)["pending"] == 1
    restarted = NotificationService(
        service.path, service.live_database, vault, client=sender,  # type: ignore[arg-type]
        collector=lambda _: (), clock=lambda: clock[0], network_provider=lambda: latest[0],
    )
    latest[0] = NetworkObservation()
    clock[0] += timedelta(seconds=65)
    sender.fail = False
    restarted.cycle()
    restarted.cycle()
    assert len(sender.sent) == 1
    assert state(restarted)["episode"] == original["episode"]
    assert restarted.status(True)["pending"] == 0
    assert "wieder bestätigt" not in repr(sender.sent)
    assert SCOPE not in repr(sender.sent) and TOKEN not in repr(sender.sent)


@pytest.mark.parametrize("bad_success", ["pre-change", "stale", "future", "different-scope",
                                         "contradictory-code"])
def test_no_false_recovery_from_untrusted_success(tmp_path: Path, bad_success: str):
    service, sender, _, clock, latest = service_for(tmp_path)
    latest[0] = observation(NOW)
    service.cycle()
    assert len(sender.sent) == 1
    episode = state(service)["episode"]
    clock[0] += timedelta(seconds=30)
    account_at = clock[0]
    scope, code = SCOPE, None
    if bad_success == "pre-change":
        account_at = NOW - timedelta(seconds=1)
    elif bad_success == "stale":
        account_at = clock[0] - timedelta(seconds=91)
    elif bad_success == "future":
        account_at = clock[0] + timedelta(microseconds=1)
    elif bad_success == "different-scope":
        scope = "different-private-account"
    else:
        code = -2015
    latest[0] = observation(clock[0], state="CURRENT", code=code,
                            account_at=account_at, scope=scope)
    for _ in range(3):
        service.cycle()
    assert len(sender.sent) == 1
    assert state(service)["episode"] == episode


def test_positive_recovery_once_then_next_real_change_is_new_episode(tmp_path: Path):
    service, sender, _, clock, latest = service_for(tmp_path)
    service.cycle()
    clock[0] += timedelta(seconds=30)
    latest[0] = observation(clock[0])
    service.cycle()
    first = state(service)["episode"]
    clock[0] += timedelta(seconds=30)
    latest[0] = observation(clock[0], state="CURRENT", code=None)
    service.cycle()
    service.cycle()
    assert len(sender.sent) == 2 and state(service)["episode"] is None
    assert "keinen Verkauf" in sender.sent[-1][1]
    clock[0] += timedelta(seconds=30)
    latest[0] = observation(clock[0], ip=IP_A, state="UNKNOWN", code=None)
    service.cycle()
    assert len(sender.sent) == 3 and state(service)["episode"] != first


def test_newly_known_ip_adds_context_without_replacing_access_incident(tmp_path: Path):
    service, sender, _, clock, latest = service_for(tmp_path)
    latest[0] = observation(NOW, ip=None)
    service.cycle()
    episode = state(service)["episode"]
    clock[0] += timedelta(seconds=30)
    latest[0] = observation(clock[0])
    service.cycle()
    service.cycle()
    assert state(service)["episode"] == episode
    assert len(sender.sent) == 2 and IP_B in sender.sent[-1][1]
    assert "IPv4" in sender.sent[-1][0]


def test_enqueue_failure_rolls_back_network_baseline_and_episode(tmp_path: Path):
    service, sender, vault, clock, latest = service_for(tmp_path)
    service.cycle()
    before, records = state(service), dict(vault.records)
    clock[0] += timedelta(seconds=30)
    latest[0] = observation(clock[0])
    with service._connect() as connection:
        connection.execute("CREATE TRIGGER fail_notice BEFORE INSERT ON notification_outbox "
                           "BEGIN SELECT RAISE(ABORT,'fake enqueue disk failure'); END")
    with pytest.raises(sqlite3.IntegrityError, match="fake enqueue disk failure"):
        service.cycle()
    assert state(service) == before and not sender.sent
    with service._connect() as connection:
        assert connection.execute("SELECT count(*) FROM notification_outbox").fetchone()[0] == 0
        connection.execute("DROP TRIGGER fail_notice")
    service.cycle()
    service.cycle()
    assert len(sender.sent) == 1 and vault.records == records


def test_unknown_private_health_overwrites_success_without_echo_or_new_calls():
    health = [{"state": "CURRENT", "fresh": True, "observed_at_utc": NOW.isoformat(),
               "account_scope": SCOPE}]
    calls: list[str] = []
    fail = [False]

    def account_read():
        calls.append("existing-account-read")
        if fail[0]:
            raise RuntimeError("signed-url/APIKEY-SECRET-CANARY")

    monitor = NetworkMonitor(enabled=lambda: True, account_read=account_read,
        account_health=lambda: health[0], ip_reader=lambda: IP_A, clock=lambda: NOW)
    monitor.sample()
    assert monitor.snapshot().account_state == "CURRENT"
    fail[0] = True
    monitor.sample()
    snapshot = monitor.snapshot()
    assert snapshot.account_state == "UNKNOWN" and snapshot.account_at is None
    assert snapshot.account_scope is None and "SECRET-CANARY" not in repr(snapshot)
    assert calls == ["existing-account-read", "existing-account-read"]


def test_failed_sell_keeps_real_ownership_and_notices_do_not_mutate_journal(tmp_path: Path):
    service, sender, vault, clock, latest = service_for(tmp_path)
    journal = service.live_database
    with sqlite3.connect(journal) as connection:
        connection.executescript("""
            CREATE TABLE signal_trial(state TEXT,reason TEXT,owned_quantity TEXT,
                                      residual_quantity TEXT);
            INSERT INTO signal_trial VALUES('COMPLETED',NULL,'10','0');
            CREATE TABLE live_control(state TEXT);
            INSERT INTO live_control VALUES('LIVE_DISABLED');
            CREATE TABLE live_positions(quantity TEXT);
            INSERT INTO live_positions VALUES('1');
        """)
        for prefix in ("trial", "live"):
            connection.execute(f"CREATE TABLE {prefix}_intents(intent_id TEXT,state TEXT,"
                               "exchange_state TEXT,executed_quantity TEXT,order_id TEXT)")
            connection.execute(f"CREATE TABLE {prefix}_fills(intent_id TEXT,quantity TEXT)")
        connection.execute("INSERT INTO live_intents VALUES"
                           "('failed-sell','REJECTED','REJECTED','0','fake-order')")
    before = hashlib.sha256(journal.read_bytes()).hexdigest()
    records = dict(vault.records)

    def operations():
        return sample_operations(journal, {
            "health": "HEALTHY", "expected_symbols": ("ETHUSDC",),
            "final_bar_times": {"ETHUSDC": clock[0].replace(minute=0, second=0)
                                - timedelta(milliseconds=1)},
            "account_observation": {"state": "CURRENT", "fresh": True},
        }, (), clock[0])

    service.operations_provider = operations
    assert operations().owned_real is True
    latest[0] = observation(NOW)
    service.cycle()
    assert "Echtgeldposition noch offen" in sender.sent[-1][1]
    clock[0] += timedelta(seconds=30)
    latest[0] = observation(clock[0], state="CURRENT", code=None)
    service.cycle()
    assert "keinen Verkauf" in sender.sent[-1][1]
    assert operations().owned_real is True
    assert hashlib.sha256(journal.read_bytes()).hexdigest() == before
    assert vault.records == records


def test_unknown_or_invalid_public_ip_never_replaces_valid_baseline(tmp_path: Path):
    service, sender, _, clock, latest = service_for(tmp_path)
    service.cycle()
    for bad in (None, "10.0.0.1", "100.64.0.1", "203.0.113.1", "224.0.0.1", "<html>bad</html>"):
        clock[0] += timedelta(seconds=5)
        latest[0] = observation(clock[0], ip=bad, state="UNKNOWN", code=None)
        service.cycle()
        assert state(service)["ipv4"] == IP_A
    assert not sender.sent


def test_new_warning_cancels_older_retry_before_positive_recovery(tmp_path: Path):
    service, sender, _, clock, latest = service_for(tmp_path)
    service.cycle()
    clock[0] += timedelta(seconds=30)
    latest[0] = observation(clock[0], state="UNKNOWN", code=None)
    sender.fail = True
    service.cycle()
    assert service.status(True)["pending"] == 1
    clock[0] += timedelta(seconds=5)
    latest[0] = observation(clock[0])
    sender.fail = False
    service.cycle()
    assert len(sender.sent) == 1 and "-2015" in sender.sent[0][1]
    clock[0] += timedelta(seconds=5)
    latest[0] = observation(clock[0], state="CURRENT", code=None)
    service.cycle()
    assert len(sender.sent) == 2 and "wieder bestätigt" in sender.sent[-1][0]
    clock[0] += timedelta(seconds=120)
    latest[0] = observation(clock[0], state="CURRENT", code=None)
    for _ in range(3):
        service.cycle()
    assert len(sender.sent) == 2
    with service._connect() as connection:
        rows = list(connection.execute("SELECT kind,state FROM notification_outbox"))
    assert [(x["kind"], x["state"]) for x in rows].count(
        ("operation_network_alert", "CANCELED")
    ) == 1
    assert service.status(True)["pending"] == 0


def test_recovery_cannot_overtake_its_only_pending_warning(tmp_path: Path):
    service, sender, _, clock, latest = service_for(tmp_path)
    service.cycle()
    clock[0] += timedelta(seconds=30)
    latest[0] = observation(clock[0])
    sender.fail = True
    service.cycle()
    clock[0] += timedelta(seconds=5)
    latest[0] = observation(clock[0], state="CURRENT", code=None)
    sender.fail = False
    service.cycle()
    assert not sender.sent and service.status(True)["pending"] == 2
    clock[0] += timedelta(seconds=65)
    latest[0] = NetworkObservation()
    service.cycle()
    assert len(sender.sent) == 1 and "-2015" in sender.sent[0][1]
    service.cycle()
    assert len(sender.sent) == 2 and "wieder bestätigt" in sender.sent[-1][0]


def test_detailed_rejection_suppresses_generic_but_retains_unknown_order_proof(tmp_path: Path):
    service, sender, _, _, latest = service_for(tmp_path)
    obligation = "a" * 64
    service.operations_provider = lambda: OperationsObservation(
        ("ACCOUNT_UNOBSERVED", "BINANCE_ACCESS", "UNKNOWN_ORDER"),
        {obligation: False}, owned_real=True,
    )
    latest[0] = observation(NOW)
    for _ in range(4):
        service.cycle()
    assert len(sender.sent) == 2
    titles = [title for title, _ in sender.sent]
    assert "Hixton: Binance-Zugriff prüfen" not in titles
    assert "Hixton: Order ungeklärt" in titles
    assert any("Binance-Zugriff abgelehnt" in title for title in titles)
    assert any("Echtgeldposition noch offen" in body for _, body in sender.sent)
    with service._connect() as connection:
        assert [row[0] for row in connection.execute(
            "SELECT identity_hash FROM operational_notice_orders"
        )] == [obligation]
        assert [row[0] for row in connection.execute(
            "SELECT code FROM operational_notice_episodes"
        )] == ["UNKNOWN_ORDER"]

