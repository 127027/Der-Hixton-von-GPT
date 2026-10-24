from __future__ import annotations

import io
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

import pytest

from hixton.live.credentials import VaultError
from hixton.notifications import telegram as telegram_module
from hixton.notifications.events import Notice
from hixton.notifications.service import NotificationService
from hixton.notifications.telegram import DeliveryError, TelegramClient
from tests.test_live_preparation import HEADERS, MemoryVault, client_for, unlock

TOKEN = "1234567:" + "NOT_A_REAL_TELEGRAM_TOKEN_12345"


class FakeTelegram(TelegramClient):
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []
        self.fail = False

    def send(self, token: str, chat: str, title: str, body: str) -> str:
        if self.fail:
            raise DeliveryError("Telegram ist vorübergehend nicht erreichbar.")
        self.sent.append((chat, title, body))
        return str(len(self.sent))

    def discover(self, token: str) -> list[dict[str, str]]:
        return [{"id": "12345", "label": "Testnutzer"}]


def setup_service(
    tmp_path: Path,
) -> tuple[NotificationService, FakeTelegram, list[Notice], list[datetime]]:
    now = [datetime(2026, 10, 21, 12, tzinfo=UTC)]
    notices: list[Notice] = []
    sender = FakeTelegram()
    service = NotificationService(
        tmp_path / "outbox.sqlite3",
        tmp_path / "live.sqlite3",
        MemoryVault(),
        client=sender,
        collector=lambda _: tuple(notices),
        clock=lambda: now[0],
    )
    return service, sender, notices, now


def save(service: NotificationService, **changes: Any) -> dict[str, object]:
    return service.save({"enabled": True, "recipient": "12345", "secret": TOKEN, **changes})


def notice(key: str, at: datetime, kind: str = "entry") -> Notice:
    return Notice(key, kind, at, "Hixton · echter Kauf bestätigt", "49.98 USDC · 9 NEAR")


def test_disabled_and_save_never_send_or_replay_historical_trades(tmp_path: Path) -> None:
    service, sender, notices, now = setup_service(tmp_path)
    notices.append(notice("historical", now[0] - timedelta(days=1)))
    service.cycle()
    save(service)
    service.cycle()
    assert not sender.sent
    notices.append(notice("new-fill", now[0] + timedelta(seconds=1)))
    now[0] += timedelta(seconds=2)
    service.cycle()
    assert len(sender.sent) == 1
    assert "new-fill" in sender.sent[0][2]
    assert service.status(True)["pending"] == 0
    assert TOKEN not in json.dumps(service.status(True))
    assert "12345" not in json.dumps(service.status(False))


def test_token_can_be_saved_first_discovered_and_kept_without_enabling_delivery(
    tmp_path: Path,
) -> None:
    service, sender, _, _ = setup_service(tmp_path)
    partial = save(service, recipient="", enabled=True)
    assert partial["secret_configured"] is True
    assert partial["configured"] is False and partial["enabled"] is False
    assert TOKEN not in json.dumps(partial)
    service.cycle()
    assert not sender.sent
    assert service.discover("") == [{"id": "12345", "label": "Testnutzer"}]
    with pytest.raises(ValueError):
        service.test()
    completed = save(service, recipient="12345", secret="")
    assert completed["configured"] is True and completed["enabled"] is True
    assert not sender.sent


def test_partial_token_survives_restart_and_can_be_removed(tmp_path: Path) -> None:
    service, sender, _, _ = setup_service(tmp_path)
    save(service, recipient="", enabled=False)
    restarted = NotificationService(
        service.path,
        service.live_database,
        service.vault,
        client=sender,
        collector=service.collector,
        clock=service.clock,
    )
    assert restarted.status(True)["secret_configured"] is True
    assert "secret_configured" not in restarted.status(False)
    assert restarted.discover("")[0]["id"] == "12345"
    restarted.delete()
    assert restarted.status(True)["secret_configured"] is False
    assert not sender.sent


def test_restart_deduplicates_and_retains_failed_pending_message(tmp_path: Path) -> None:
    service, sender, notices, now = setup_service(tmp_path)
    save(service)
    notices.append(notice("entry1", now[0] + timedelta(seconds=1)))
    now[0] += timedelta(seconds=2)
    sender.fail = True
    service.cycle()
    assert service.status(True)["pending"] == 1
    assert service.status(True)["last_error"]
    restarted = NotificationService(
        service.path,
        service.live_database,
        service.vault,
        client=sender,
        collector=service.collector,
        clock=service.clock,
    )
    sender.fail = False
    restarted.cycle()
    assert not sender.sent
    now[0] += timedelta(minutes=10)
    restarted.cycle()
    restarted.cycle()
    assert len(sender.sent) == 1
    assert restarted.status(True)["last_error"] is None
    # No contact/token is persisted in the financial outbox.
    assert TOKEN.encode() not in service.path.read_bytes()


def test_disable_or_recipient_change_never_reroutes_old_pending_financial_data(
    tmp_path: Path,
) -> None:
    service, sender, notices, now = setup_service(tmp_path)
    save(service)
    notices.append(notice("entry", now[0] + timedelta(seconds=1)))
    now[0] += timedelta(seconds=2)
    sender.fail = True
    service.cycle()
    assert service.status(True)["pending"] == 1
    save(service, recipient="54321", secret="")
    sender.fail = False
    now[0] += timedelta(hours=1)
    service.cycle()
    assert not sender.sent
    save(service, enabled=False, recipient="54321", secret="")
    notices.append(notice("while-disabled", now[0] + timedelta(seconds=1)))
    now[0] += timedelta(seconds=2)
    service.cycle()
    save(service, recipient="54321", secret="")
    service.cycle()
    assert not sender.sent


def test_ordinary_save_preserves_epoch_and_pending_delivery(tmp_path: Path) -> None:
    service, sender, notices, now = setup_service(tmp_path)
    save(service)
    notices.append(notice("fill", now[0] + timedelta(seconds=1)))
    now[0] += timedelta(seconds=2)
    sender.fail = True
    service.cycle()
    save(service, secret="")
    assert service.status(True)["pending"] == 1
    now[0] += timedelta(hours=1)
    sender.fail = False
    service.cycle()
    service.cycle()
    assert len(sender.sent) == 1


def test_operations_are_explicit_opt_in_and_restart_does_not_repeat_alert(tmp_path: Path) -> None:
    service, sender, _, now = setup_service(tmp_path)
    service.operations_provider = lambda: ("UNKNOWN_ORDER",)
    assert save(service)["operations_enabled"] is False
    service.cycle()
    assert not sender.sent
    save(service, secret="", operations_enabled=True)
    original_vault = dict(service.vault.records)
    service.cycle()
    assert len(sender.sent) == 1
    restarted = NotificationService(
        service.path, service.live_database, service.vault, client=sender,
        collector=service.collector, clock=service.clock,
        operations_provider=service.operations_provider,
    )
    now[0] += timedelta(seconds=5)
    restarted.cycle()
    assert len(sender.sent) == 1
    assert service.vault.records == original_vault
    assert "operations_enabled" not in restarted.status(False)


def test_operations_toggle_preserves_pending_real_trade_and_disables_only_alerts(
    tmp_path: Path,
) -> None:
    service, sender, notices, now = setup_service(tmp_path)
    service.operations_provider = lambda: ("UNKNOWN_ORDER",)
    save(service, operations_enabled=True)
    sender.fail = True
    service.cycle()
    notices.append(notice("confirmed-fill", now[0] + timedelta(seconds=1)))
    now[0] += timedelta(seconds=5)
    service.cycle()
    assert service.status(True)["pending"] == 2
    save(service, secret="", operations_enabled=False)
    assert service.status(True)["pending"] == 1
    sender.fail = False
    now[0] += timedelta(minutes=2)
    service.cycle()
    assert len(sender.sent) == 1 and "confirmed-fill" in sender.sent[0][2]


def test_retrying_alert_does_not_block_new_confirmed_fill(tmp_path: Path) -> None:
    service, sender, notices, now = setup_service(tmp_path)
    service.operations_provider = lambda: ("UNKNOWN_ORDER",)
    save(service, operations_enabled=True)
    sender.fail = True
    service.cycle()
    notices.append(notice("actual-fill", now[0] + timedelta(seconds=1)))
    now[0] += timedelta(seconds=5)
    sender.fail = False
    service.cycle()
    assert len(sender.sent) == 1 and "actual-fill" in sender.sent[0][2]


def test_recovery_waits_for_its_retrying_alert(tmp_path: Path) -> None:
    service, sender, _, now = setup_service(tmp_path)
    codes = [("BINANCE_CONNECTION",)]
    service.operations_provider = lambda: codes[0]
    save(service, operations_enabled=True)
    sender.fail = True
    service.cycle()
    sender.fail = False
    codes[0] = ()
    for _ in range(8):
        now[0] += timedelta(seconds=5)
        service.cycle()
    assert not sender.sent  # Recovery exists but must not overtake its failed alert.
    assert service.status(True)["pending"] == 2
    for _ in range(4):
        now[0] += timedelta(seconds=5)
        service.cycle()
    assert len(sender.sent) == 1 and "gestört" in sender.sent[0][1]
    now[0] += timedelta(seconds=5)
    service.cycle()
    assert len(sender.sent) == 2 and "unauffällig" in sender.sent[1][1]


def test_failed_entry_message_is_delivered_before_confirmed_exit(tmp_path: Path) -> None:
    service, sender, notices, now = setup_service(tmp_path)
    save(service)
    notices.append(notice("buy", now[0] + timedelta(seconds=1)))
    now[0] += timedelta(seconds=2)
    sender.fail = True
    service.cycle()
    sender.fail = False
    notices.append(notice("sell", now[0] + timedelta(seconds=1), "exit"))
    now[0] += timedelta(seconds=5)
    service.cycle()
    assert not sender.sent
    now[0] += timedelta(minutes=2)
    service.cycle()
    service.cycle()
    assert [item[2].split("Meldung: ")[1] for item in sender.sent] == ["buy", "sell"]


def test_failed_trade_collector_still_delivers_sanitized_observation_warning(
    tmp_path: Path,
) -> None:
    service, sender, _, _ = setup_service(tmp_path)
    service.operations_provider = lambda: ()
    def broken(_: Path) -> tuple[Notice, ...]:
        raise sqlite3.DatabaseError("secret/signed-url")
    service.collector = broken
    save(service, operations_enabled=True)
    service.cycle()
    assert len(sender.sent) == 1
    assert "secret" not in str(sender.sent)


def test_operations_validation_does_not_mutate_credentials(tmp_path: Path) -> None:
    service, _, _, _ = setup_service(tmp_path)
    save(service)
    original = dict(service.vault.records)
    with pytest.raises(ValueError):
        save(service, operations_enabled="yes")
    assert service.vault.records == original


def test_failed_contact_rotation_stops_delivery_before_vault_mutation(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    service, sender, notices, now = setup_service(tmp_path)
    save(service)
    notices.append(notice("financial-data", now[0] + timedelta(seconds=1)))
    now[0] += timedelta(seconds=2)
    sender.fail = True
    service.cycle()

    def failed_write(*_: object) -> None:
        raise VaultError("Windows konnte den Schlüssel nicht sicher speichern.")

    monkeypatch.setattr(service.vault, "write", failed_write)
    with pytest.raises(VaultError):
        save(service, recipient="54321")
    sender.fail = False
    now[0] += timedelta(hours=1)
    service.cycle()
    assert service.status(False)["enabled"] is False
    assert not sender.sent


def test_test_message_is_explicit_even_when_automatic_delivery_disabled(tmp_path: Path) -> None:
    service, sender, _, _ = setup_service(tmp_path)
    save(service, enabled=False)
    assert not sender.sent
    assert service.test()["accepted"] is True
    assert len(sender.sent) == 1
    assert "Keine Order" in sender.sent[0][2]
    assert "49.98" not in sender.sent[0][2]
    service.delete()
    assert service.status(True)["configured"] is False
    assert service.status(True)["recipient"] == ""
    with sqlite3.connect(service.path) as database:
        assert database.execute("SELECT COUNT(*) FROM notification_outbox").fetchone()[0] == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"recipient": "https://attacker.example"},
        {"recipient": "-12345"},
        {"enabled": "true"},
        {"secret": "bad\nTOKEN"},
        {"channel": "whatsapp"},
    ],
)
def test_bad_contact_is_rejected_without_token_echo(
    tmp_path: Path, changes: dict[str, Any]
) -> None:
    service, sender, _, _ = setup_service(tmp_path)
    with pytest.raises(ValueError) as error:
        save(service, **changes)
    assert TOKEN not in str(error.value)
    assert not sender.sent
    assert not service.status(False)["configured"]


def test_contact_api_shares_password_origin_and_secrets_never_roundtrip(tmp_path: Path) -> None:
    client, _, _ = client_for(tmp_path)
    contact = client.app.state.notifications
    fake = FakeTelegram()
    contact.client = fake
    payload = {"enabled": True, "recipient": "12345", "secret": TOKEN}
    assert client.get("/api/live/notifications").json() == {
        "authenticated": False,
        "configured": False,
        "enabled": False,
    }
    assert client.post("/api/live/notifications", headers=HEADERS, json=payload).status_code == 401
    unlock(client)
    assert client.post("/api/live/notifications", json=payload).status_code == 403
    response = client.post("/api/live/notifications", headers=HEADERS, json=payload)
    assert response.status_code == 200
    assert response.json()["secret_configured"] is True
    assert TOKEN not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert not fake.sent
    assert (
        client.post(
            "/api/live/notifications/discover", headers=HEADERS, json={"secret": ""}
        ).json()["chats"][0]["id"]
        == "12345"
    )
    assert not fake.sent
    assert client.post("/api/live/notifications/test", headers=HEADERS, json={}).json()["accepted"]
    assert len(fake.sent) == 1
    fake.fail = True
    failure = client.post("/api/live/notifications/test", headers=HEADERS, json={})
    assert failure.status_code == 502 and TOKEN not in failure.text
    client.post("/api/live/lock", headers=HEADERS, json={})
    assert "recipient" not in client.get("/api/live/notifications").json()
    assert client.post("/api/live/notifications/test", headers=HEADERS, json={}).status_code == 401
    assert len(fake.sent) == 1


def test_api_token_first_chat_discovery_then_full_contact_without_token_reentry(
    tmp_path: Path,
) -> None:
    client, _, _ = client_for(tmp_path)
    fake = FakeTelegram()
    client.app.state.notifications.client = fake
    unlock(client)
    partial = client.post(
        "/api/live/notifications",
        headers=HEADERS,
        json={
            "enabled": True,
            "recipient": "",
            "secret": TOKEN,
        },
    )
    assert partial.status_code == 200
    assert partial.json()["secret_configured"] is True
    assert partial.json()["configured"] is False and partial.json()["enabled"] is False
    assert TOKEN not in partial.text
    chats = client.post("/api/live/notifications/discover", headers=HEADERS, json={"secret": ""})
    assert chats.status_code == 200 and chats.json()["chats"][0]["id"] == "12345"
    full = client.post(
        "/api/live/notifications",
        headers=HEADERS,
        json={
            "enabled": True,
            "recipient": "12345",
            "secret": "",
        },
    )
    assert full.status_code == 200 and full.json()["configured"] is True
    assert full.json()["enabled"] is True and TOKEN not in full.text
    assert not fake.sent


def test_telegram_http_uses_private_chat_no_paid_broadcast_and_no_markup(monkeypatch: Any) -> None:
    calls: list[tuple[str, str, dict[str, object]]] = []
    telegram = TelegramClient()

    def api(token: str, method: str, payload: dict[str, object]) -> dict[str, Any]:
        calls.append((token, method, payload))
        return {"ok": True, "result": {"chat": {"id": 12345}, "message_id": 7}}

    monkeypatch.setattr(telegram, "_call", api)
    assert telegram.send(TOKEN, "12345", "Titel", "echte <Zahlen>") == "7"
    assert calls[0][1:] == ("sendMessage", {"chat_id": "12345", "text": "Titel\n\nechte <Zahlen>"})
    monkeypatch.setattr(
        telegram,
        "_call",
        lambda *_: {
            "ok": True,
            "result": [
                {"message": {"chat": {"id": 12345, "type": "private", "first_name": "André"}}},
                {"message": {"chat": {"id": -678, "type": "group", "title": "Not private"}}},
            ],
        },
    )
    assert telegram.discover(TOKEN) == [{"id": "12345", "label": "André"}]


@pytest.mark.parametrize("message_id", [True, False, 0, -1, "7", None])
def test_telegram_requires_positive_integer_message_ack(
    monkeypatch: Any,
    message_id: object,
) -> None:
    telegram = TelegramClient()
    monkeypatch.setattr(
        telegram,
        "_call",
        lambda *_: {
            "ok": True,
            "result": {"chat": {"id": 12345}, "message_id": message_id},
        },
    )
    with pytest.raises(DeliveryError):
        telegram.send(TOKEN, "12345", "Titel", "Handelsmeldung")


@pytest.mark.parametrize("failure", ["timeout", "auth", "rate", "redirect"])
def test_provider_errors_never_echo_token_or_provider_body(
    monkeypatch: Any,
    failure: str,
) -> None:
    class Opener:
        def open(self, *_: object, **__: object) -> None:
            if failure == "timeout":
                raise URLError("https://api.telegram.org/bot" + TOKEN)
            code = {"auth": 401, "rate": 429, "redirect": 302}[failure]
            raise HTTPError(
                "https://api.telegram.org/bot" + TOKEN,
                code,
                TOKEN,
                {},
                io.BytesIO(
                    json.dumps({"secret": TOKEN, "parameters": {"retry_after": 180}}).encode()
                ),
            )

    monkeypatch.setattr(telegram_module, "build_opener", lambda *_: Opener())
    with pytest.raises(DeliveryError) as error:
        TelegramClient().send(TOKEN, "12345", "Test", "Keine Order")
    assert TOKEN not in str(error.value)
    if failure == "rate":
        assert error.value.retry_after == 180
