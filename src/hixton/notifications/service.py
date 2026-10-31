"""Independent, opt-in, durable delivery; no callbacks into trading or account control."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from hixton.domain.markets import split_market
from hixton.live.credentials import Vault, VaultError
from hixton.notifications.compact import balance_line, compact_message
from hixton.notifications.events import Notice, collect_notices
from hixton.notifications.network import (
    NetworkObservation,
    evaluate_network,
    initialize_network,
    reset_network,
)
from hixton.notifications.operations import (
    evaluate_operations,
    initialize_operations,
    reset_operations,
)
from hixton.notifications.telegram import (
    DeliveryError,
    TelegramClient,
    validate_chat,
    validate_token,
)

_VAULT_NAME = "telegram-notifications"


class NotificationService:
    def __init__(
        self,
        path: Path,
        live_database: Path,
        vault: Vault,
        *,
        client: TelegramClient | None = None,
        collector: Callable[[Path], tuple[Notice, ...]] = collect_notices,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        balance_provider: Callable[[str], dict[str, object]] | None = None,
        operations_provider: Callable[[], tuple[str, ...]] | None = None,
        network_provider: Callable[[], NetworkObservation] | None = None,
    ) -> None:
        self.path, self.live_database, self.vault = path, live_database, vault
        self.client = client or TelegramClient()
        self.collector, self.clock = collector, clock
        self.balance_provider = balance_provider
        self.operations_provider = operations_provider
        self.network_provider = network_provider
        self._lock = RLock()
        self._task: asyncio.Task[None] | None = None
        self._stopping = False
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS notification_control(
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    configured INTEGER NOT NULL DEFAULT 0,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    generation TEXT NOT NULL DEFAULT '',
                    enabled_at TEXT,
                    last_error TEXT,
                    last_sent_at TEXT
                );
                INSERT OR IGNORE INTO notification_control(singleton) VALUES(1);
                CREATE TABLE IF NOT EXISTS notification_outbox(
                    generation TEXT NOT NULL, event_key TEXT NOT NULL,
                    occurred_at TEXT NOT NULL, kind TEXT NOT NULL,
                    title TEXT NOT NULL, body TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'PENDING', attempts INTEGER NOT NULL DEFAULT 0,
                    next_attempt_at TEXT NOT NULL, accepted_at TEXT, provider_id TEXT,
                    PRIMARY KEY(generation,event_key)
                );
            """)
            columns = {r[1] for r in connection.execute("PRAGMA table_info(notification_outbox)")}
            for column in ("account_fingerprint", "quote_asset", "detail_body", "last_payload"):
                if column not in columns:
                    connection.execute(f"ALTER TABLE notification_outbox ADD COLUMN {column} TEXT")
            control_columns = {
                r[1] for r in connection.execute("PRAGMA table_info(notification_control)")
            }
            if "operations_enabled" not in control_columns:
                connection.execute(
                    "ALTER TABLE notification_control ADD COLUMN operations_enabled INTEGER "
                    "NOT NULL DEFAULT 0"
                )
            initialize_network(connection)
            initialize_operations(connection)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=1)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA synchronous=FULL")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _config(self, *, require_chat: bool = True) -> dict[str, Any]:
        raw = self.vault.read(_VAULT_NAME)
        try:
            value = json.loads(raw or "{}")
            if not isinstance(value, dict):
                raise ValueError
            token = validate_token(value.get("secret", ""))
            chat = value.get("recipient", "")
            if not isinstance(chat, str):
                raise ValueError
            if chat or require_chat:
                chat = validate_chat(chat)
        except (ValueError, TypeError):
            raise ValueError("Telegram-Kontakt zuerst vollständig speichern.") from None
        return {"secret": token, "recipient": chat}

    def status(self, authenticated: bool) -> dict[str, object]:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT * FROM notification_control").fetchone()
            assert row is not None
            result: dict[str, object] = {
                "authenticated": authenticated,
                "configured": bool(row["configured"]),
                "enabled": bool(row["enabled"]),
            }
            if not authenticated:
                return result
            config: dict[str, Any] = {}
            with suppress(ValueError, VaultError):
                config = self._config(require_chat=False)
            result.update(
                {
                    "channel": "telegram",
                    "recipient": config.get("recipient", ""),
                    "secret_configured": bool(config.get("secret")),
                    "pending": connection.execute(
                        "SELECT COUNT(*) FROM notification_outbox WHERE state='PENDING'"
                    ).fetchone()[0],
                    "last_sent_at": row["last_sent_at"],
                    "last_error": row["last_error"],
                    "operations_enabled": bool(row["operations_enabled"]),
                }
            )
            return result

    def save(self, data: dict[str, Any]) -> dict[str, object]:
        if data.get("channel", "telegram") != "telegram" or type(data.get("enabled")) is not bool:
            raise ValueError("Telegram und den gewünschten Benachrichtigungsstatus wählen.")
        if "operations_enabled" in data and type(data["operations_enabled"]) is not bool:
            raise ValueError("Den gewünschten Status der Störungsmeldungen wählen.")
        recipient, secret = data.get("recipient"), data.get("secret", "")
        if not isinstance(recipient, str) or not isinstance(secret, str):
            raise ValueError("Ungültige Telegram-Kontaktdaten.")
        recipient = recipient.strip()
        if recipient:
            recipient = validate_chat(recipient)
        enabled = bool(data["enabled"] and recipient)
        secret = secret.strip()
        with self._lock:
            previous: dict[str, Any] = {}
            with suppress(ValueError):
                previous = self._config(require_chat=False)
            secret = validate_token(secret or previous.get("secret", ""))
            new_config = {"recipient": recipient, "secret": secret}
            with self._connect() as connection:
                row = connection.execute("SELECT * FROM notification_control").fetchone()
                assert row is not None
                operations_enabled = data.get("operations_enabled", bool(row["operations_enabled"]))
                new_generation = previous != new_config or not row["enabled"] or not enabled
                if new_generation:
                    # Commit the stop BEFORE rotating a vault record. A crash or vault/
                    # SQLite failure must never reroute pending financial data to a new chat.
                    connection.execute("UPDATE notification_control SET enabled=0")
                    connection.execute(
                        "UPDATE notification_outbox SET state='CANCELED' WHERE state='PENDING'"
                    )
            # Credentials never enter the outbox, API response, logs or browser storage.
            if previous != new_config:
                self.vault.write(_VAULT_NAME, json.dumps(new_config))
            with self._connect() as connection:
                connection.execute(
                    "UPDATE notification_control SET configured=?,enabled=?,generation=?,"
                    "enabled_at=?,operations_enabled=?,last_error=NULL WHERE singleton=1",
                    (
                        int(bool(recipient)),
                        int(enabled),
                        uuid4().hex if new_generation else row["generation"],
                        self.clock().isoformat() if new_generation else row["enabled_at"],
                        int(operations_enabled),
                    ),
                )
                if new_generation or operations_enabled != bool(row["operations_enabled"]):
                    reset_operations(connection)
                    reset_network(connection)
                    connection.execute(
                        "UPDATE notification_outbox SET state='CANCELED' "
                        "WHERE state='PENDING' AND kind LIKE 'operation_%'"
                    )
        return self.status(True)

    def delete(self) -> dict[str, object]:
        with self._lock:
            self.vault.delete(_VAULT_NAME)
            with self._connect() as connection:
                connection.execute(
                    "UPDATE notification_control SET configured=0,enabled=0,generation='',"
                    "enabled_at=NULL,last_error=NULL,last_sent_at=NULL,operations_enabled=0 "
                    "WHERE singleton=1"
                )
                # Remove local financial message copies when contact is explicitly removed.
                connection.execute("DELETE FROM notification_outbox")
                reset_operations(connection)
                reset_network(connection)
        return self.status(True)

    def discover(self, secret: str) -> list[dict[str, str]]:
        with self._lock:
            token = secret.strip()
            if not token:
                try:
                    token = self._config(require_chat=False)["secret"]
                except ValueError:
                    raise ValueError(
                        "Zuerst den Bot-Token eintragen oder sicher speichern."
                    ) from None
            token = validate_token(token)
            return self.client.discover(token)

    def test(self) -> dict[str, object]:
        with self._lock:
            config = self._config()
            self.client.send(
                config["secret"],
                config["recipient"],
                "Hixton · Verbindungstest",
                "✅ Telegram verbunden.\nKeine Order ausgelöst.",
            )
            with self._connect() as connection:
                connection.execute(
                    "UPDATE notification_control SET last_sent_at=?,last_error=NULL",
                    (self.clock().isoformat(),),
                )
        return {"accepted": True, "detail": "Telegram hat die Testnachricht angenommen."}

    def _error(self, message: str) -> None:
        with self._connect() as connection:
            connection.execute("UPDATE notification_control SET last_error=?", (message,))

    def monitoring_enabled(self) -> bool:
        """No vault/session access: existing Telegram operations opt-in only."""
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM notification_control").fetchone()
            return bool(row and row["configured"] and row["enabled"] and row["operations_enabled"])

    def cycle(self) -> None:
        # Only this delivery worker uses the lock. No lock/transaction on the trading database
        # is held during provider requests, and delivery never controls entries or exits.
        with self._lock:
            if self._stopping:
                return
            with self._connect() as connection:
                control = connection.execute("SELECT * FROM notification_control").fetchone()
            assert control is not None
            if not control["enabled"]:
                return
            now = self.clock()
            codes: tuple[str, ...] = ()
            if control["operations_enabled"] and self.operations_provider is not None:
                try:
                    codes = self.operations_provider()
                except Exception:
                    # Local observation failed, never interpret that as recovery or echo it.
                    codes = ("OBSERVATION_UNAVAILABLE", "ACCOUNT_UNOBSERVED")
            order_evidence = getattr(codes, "order_evidence", None)
            owned_real = getattr(codes, "owned_real", None)
            network = None
            if control["operations_enabled"] and self.network_provider is not None:
                with suppress(Exception):
                    network = self.network_provider()  # Passive immutable snapshot only.
            if (network is not None and network.account_code == -2015
                and network.account_at is not None
                and 0 <= (now - network.account_at).total_seconds() <= 90):
                # The detailed IP/access notice supersedes the generic rejection.
                # Preserve independent unknown-order and market-data obligations.
                codes = tuple(code for code in codes if code != "BINANCE_ACCESS")
            try:
                notices = self.collector(self.live_database)
            except (ValueError, OSError, sqlite3.DatabaseError):
                notices = ()
                codes = (*codes, "OBSERVATION_UNAVAILABLE", "ACCOUNT_UNOBSERVED")
                self._error(
                    "Echtgeld-Meldungen konnten nicht gelesen werden. Erneuter Versuch folgt."
                )
            enabled_at = datetime.fromisoformat(control["enabled_at"])
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if control["operations_enabled"] and self.operations_provider is not None:
                    notices = (*notices, *evaluate_operations(
                        connection, control["generation"], codes, now,
                        order_evidence=order_evidence,
                    ))
                if network is not None:
                    notices = (*notices, *evaluate_network(
                        connection, control["generation"], network, now, owned_real=owned_real,
                    ))
                for notice in notices:
                    if notice.occurred_at < enabled_at:
                        continue
                    title, body = compact_message(notice)
                    connection.execute(
                        "INSERT OR IGNORE INTO notification_outbox"
                        "(generation,event_key,occurred_at,kind,title,body,next_attempt_at,"
                        "account_fingerprint,quote_asset,detail_body)"
                        " VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (
                            control["generation"],
                            notice.key,
                            notice.occurred_at.isoformat(),
                            notice.kind,
                            title,
                            body,
                            now.isoformat(),
                            notice.trade.account if notice.trade else None,
                            split_market(notice.trade.symbol)[1] if notice.trade else None,
                            notice.body,
                        ),
                    )
                pending = connection.execute(
                    "SELECT q.* FROM notification_outbox q "
                    "WHERE q.generation=? AND q.state='PENDING' AND q.next_attempt_at<=? "
                    "AND (q.kind LIKE 'operation_%' OR NOT EXISTS ("
                    "SELECT 1 FROM notification_outbox earlier "
                    "WHERE earlier.generation=q.generation AND earlier.state='PENDING' "
                    "AND earlier.kind NOT LIKE 'operation_%' AND "
                    "(earlier.occurred_at<q.occurred_at OR "
                    "(earlier.occurred_at=q.occurred_at AND earlier.event_key<q.event_key)))) "
                    "AND (q.kind!='operation_recovery' OR NOT EXISTS ("
                    "SELECT 1 FROM notification_outbox alert "
                    "WHERE alert.generation=q.generation AND alert.state='PENDING' "
                    "AND alert.event_key=substr(q.event_key,1,length(q.event_key)-8)||'alert')) "
                    "ORDER BY q.occurred_at,q.event_key LIMIT 1",
                    (control["generation"], now.isoformat()),
                ).fetchone()
            if pending is None:
                return
            try:
                config = self._config()
            except (ValueError, VaultError):
                self._error("Telegram-Kontakt nicht lesbar; Meldungen bleiben gespeichert.")
                return
            delivery_body = str(pending["body"])
            if pending["account_fingerprint"]:
                balance: dict[str, object] = {}
                if self.balance_provider is not None:
                    # Missing account data never suppresses proven executions.
                    with suppress(Exception):
                        balance = self.balance_provider(pending["account_fingerprint"])
                delivery_body += "\n" + balance_line(
                    balance, quote=pending["quote_asset"],
                    after=datetime.fromisoformat(pending["occurred_at"]), now=self.clock(),
                )
            elif str(pending["kind"]).startswith("operation_"):
                episode_id = str(pending["event_key"]).split(":")[1][:8]
                delivery_body += (
                    "\nStand: " + pending["occurred_at"] + "\nID: " + episode_id
                )
            else:
                delivery_body += "\n\nMeldung: " + pending["event_key"]
            if self._stopping:
                return  # to_thread cancellation cannot interrupt a slow balance lookup.
            with self._connect() as connection:
                connection.execute(
                    "UPDATE notification_outbox SET last_payload=? "
                    "WHERE generation=? AND event_key=?",
                    (delivery_body, control["generation"], pending["event_key"]),
                )
            try:
                if self._stopping:
                    return  # Never start a new provider call after stop was requested.
                provider_id = self.client.send(
                    config["secret"],
                    config["recipient"],
                    pending["title"],
                    delivery_body,
                )
            except DeliveryError as error:
                attempts = pending["attempts"] + 1
                delay = max(error.retry_after, min(3600, 30 * 2 ** min(attempts, 7)))
                with self._connect() as connection:
                    connection.execute(
                        "UPDATE notification_outbox SET attempts=?,next_attempt_at=? "
                        "WHERE generation=? AND event_key=?",
                        (
                            attempts,
                            (now + timedelta(seconds=delay)).isoformat(),
                            control["generation"],
                            pending["event_key"],
                        ),
                    )
                self._error(str(error))
                return
            with self._connect() as connection:
                connection.execute(
                    "UPDATE notification_outbox SET state='ACCEPTED',accepted_at=?,provider_id=? "
                    "WHERE generation=? AND event_key=?",
                    (now.isoformat(), provider_id, control["generation"], pending["event_key"]),
                )
                connection.execute(
                    "UPDATE notification_control SET last_sent_at=?,last_error=NULL",
                    (now.isoformat(),),
                )

    def start(self) -> None:
        if self._task is None:
            self._stopping = False
            self._task = asyncio.create_task(self._run(), name="hixton-telegram")

    async def _run(self) -> None:
        while not self._stopping:
            try:
                await asyncio.to_thread(self.cycle)
            except Exception:
                # No provider exception text: it may contain a token-bearing URL.
                with suppress(OSError, sqlite3.DatabaseError):
                    await asyncio.to_thread(
                        self._error, "Benachrichtigungen pausiert; neuer Versuch folgt."
                    )
            if not self._stopping:
                await asyncio.sleep(5)

    async def stop(self) -> None:
        self._stopping = True
        if self._task is not None:
            # Let an in-flight bounded request finish before process exit; no orphan sender.
            with suppress(TimeoutError):
                await asyncio.wait_for(asyncio.shield(self._task), timeout=14)
            if not self._task.done():
                self._task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._task
            self._task = None
