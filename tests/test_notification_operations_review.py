"""Independent operational-delivery failure probes; only fake providers and databases."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from hixton.live.credentials import WindowsVault
from hixton.notifications.operations import evaluate_operations, initialize_operations
from hixton.notifications.service import NotificationService

TOKEN = "1234567:" + "FAKE_OPERATION_REVIEW_TOKEN_12345"


class ReviewVault:
    def __init__(self) -> None:
        self.records = {
            "local-password": "fake-existing-password-proof",
            "binance-hmac": "fake-existing-binance-record",
        }

    def read(self, name: str) -> str | None:
        return self.records.get(name)

    def write(self, name: str, value: str) -> None:
        self.records[name] = value

    def delete(self, name: str) -> None:
        self.records.pop(name, None)


class ReviewSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, token: str, recipient: str, title: str, body: str) -> str:
        assert token == TOKEN and recipient == "12345"
        self.sent.append((title, body))
        return str(len(self.sent))


def review_service(tmp_path: Path):
    vault, sender = ReviewVault(), ReviewSender()
    now = [datetime(2026, 10, 24, 12, tzinfo=UTC)]
    live = tmp_path / "fake-trading.sqlite3"
    with sqlite3.connect(live) as db:
        db.execute("CREATE TABLE untouched_trial(proof TEXT)")
        db.execute("INSERT INTO untouched_trial VALUES('original-acceptance')")
    service = NotificationService(
        tmp_path / "outbox.sqlite3",
        live,
        vault,
        client=sender,  # type: ignore[arg-type]
        collector=lambda _: (),
        clock=lambda: now[0],
        operations_provider=lambda: ("EXECUTION_REVIEW",),
    )
    service.save(
        {"enabled": True, "recipient": "12345", "secret": TOKEN, "operations_enabled": True}
    )
    return service, sender, vault, now


def test_outbox_insert_failure_rolls_back_episode_and_retry_enqueues_once(tmp_path: Path) -> None:
    service, sender, _, _ = review_service(tmp_path)
    before = hashlib.sha256(service.live_database.read_bytes()).hexdigest()
    with service._connect() as db:
        db.execute(
            "CREATE TRIGGER reject_enqueue BEFORE INSERT ON notification_outbox "
            "BEGIN SELECT RAISE(ABORT,'fake disk enqueue failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="fake disk enqueue failure"):
        service.cycle()
    with service._connect() as db:
        for table in (
            "notification_outbox",
            "operational_notice_episodes",
            "operational_notice_control",
        ):
            assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
        db.execute("DROP TRIGGER reject_enqueue")
    assert not sender.sent
    service.cycle()
    service.cycle()
    assert len(sender.sent) == 1
    with service._connect() as db:
        assert db.execute("SELECT COUNT(*) FROM operational_notice_episodes").fetchone()[0] == 1
        assert db.execute("SELECT state FROM notification_outbox").fetchone()[0] == "ACCEPTED"
    assert hashlib.sha256(service.live_database.read_bytes()).hexdigest() == before


def test_accepted_send_then_ack_disk_failure_can_duplicate_but_never_trades(tmp_path: Path) -> None:
    service, sender, _, _ = review_service(tmp_path)
    before = hashlib.sha256(service.live_database.read_bytes()).hexdigest()
    with service._connect() as db:
        db.execute(
            "CREATE TRIGGER reject_ack BEFORE UPDATE OF state ON notification_outbox "
            "WHEN NEW.state='ACCEPTED' "
            "BEGIN SELECT RAISE(ABORT,'fake ack disk failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="fake ack disk failure"):
        service.cycle()
    assert len(sender.sent) == 1
    with service._connect() as db:
        first = dict(db.execute("SELECT * FROM notification_outbox").fetchone())
        assert first["state"] == "PENDING" and first["provider_id"] is None
        assert db.execute("SELECT alerted FROM operational_notice_episodes").fetchone()[0] == 1
        db.execute("DROP TRIGGER reject_ack")
    # Telegram lacks an idempotency token: this uncertain-delivery retry may duplicate.
    # Stable incident ID and body expose the ambiguity; no new incident or trade exists.
    service.cycle()
    service.cycle()
    assert len(sender.sent) == 2 and sender.sent[0] == sender.sent[1]
    with service._connect() as db:
        assert db.execute("SELECT COUNT(*) FROM notification_outbox").fetchone()[0] == 1
        assert db.execute("SELECT state FROM notification_outbox").fetchone()[0] == "ACCEPTED"
    assert hashlib.sha256(service.live_database.read_bytes()).hexdigest() == before


def test_legacy_migration_and_restart_leave_existing_vault_records_untouched(
    tmp_path: Path,
) -> None:
    path, vault = tmp_path / "outbox.sqlite3", ReviewVault()
    vault.records["telegram-notifications"] = json.dumps({"secret": TOKEN, "recipient": "12345"})
    original = dict(vault.records)
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE notification_control(singleton INTEGER PRIMARY KEY,"
            "configured INTEGER,enabled INTEGER,generation TEXT,enabled_at TEXT,"
            "last_error TEXT,last_sent_at TEXT)"
        )
        db.execute(
            "INSERT INTO notification_control VALUES"
            "(1,1,1,'existing-generation','2026-10-24T12:00:00+00:00',NULL,NULL)"
        )
    for _ in range(2):
        service = NotificationService(
            path, tmp_path / "never-read.sqlite3", vault, collector=lambda _: ()
        )
        assert service.status(True)["operations_enabled"] is False
        with service._connect() as db:
            row = db.execute("SELECT * FROM notification_control").fetchone()
            assert row["generation"] == "existing-generation" and row["enabled"] == 1
            assert db.execute("SELECT COUNT(*) FROM notification_outbox").fetchone()[0] == 0
        assert vault.records == original


def test_vault_namespace_preserves_same_path_alias_but_isolates_fresh_folder(
    tmp_path: Path,
) -> None:
    original = WindowsVault(tmp_path / "existing" / "data" / "hixton.sqlite3")
    same = WindowsVault(tmp_path / "existing" / "data" / "hixton.sqlite3")
    alias = WindowsVault(tmp_path / "existing" / "data" / "hixton-usdc.sqlite3")
    fresh = WindowsVault(tmp_path / "fresh-download" / "data" / "hixton.sqlite3")
    assert original.prefix == same.prefix == alias.prefix
    assert original.prefix != fresh.prefix


def test_sparse_observations_and_restart_cannot_fabricate_continuous_recovery(
    tmp_path: Path,
) -> None:
    db = sqlite3.connect(tmp_path / "episodes.sqlite3")
    try:
        initialize_operations(db)
        db.commit()
        start = datetime(2026, 10, 24, 12, tzinfo=UTC)

        def observe(seconds: int, codes: tuple[str, ...] = ()):
            db.execute("BEGIN IMMEDIATE")
            notices = evaluate_operations(
                db, "stable-generation", codes, start + timedelta(seconds=seconds)
            )
            db.commit()
            return notices

        alert = observe(0, ("EXECUTION_REVIEW",))
        assert len(alert) == 1 and alert[0].kind == "operation_alert"
        assert not observe(10)
        assert not observe(31)  # The21-second gap resets the clear timer.
        initialize_operations(db)  # Restart breaks continuity, keeps the delivered episode.
        db.commit()
        for seconds in (40, 50, 60):
            assert not observe(seconds)
        recovered = observe(70)
        assert len(recovered) == 1 and recovered[0].kind == "operation_recovery"
        assert alert[0].key.removesuffix("alert") == recovered[0].key.removesuffix("recovery")
        assert not observe(80)
    finally:
        db.close()
