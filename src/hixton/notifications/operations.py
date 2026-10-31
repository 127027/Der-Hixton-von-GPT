"""Passive, coherent journal observations and transactional incident episodes.

This module cannot trade, read a vault, contact an exchange or deliver a message.
Only fixed catalog text enters notices. Delivery must enqueue returned notices in
the SAME transaction as ``evaluate_operations``; otherwise a crash could lose one.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import MappingProxyType
from uuid import uuid4

from hixton.notifications.events import Notice


@dataclass(frozen=True)
class OperationSpec:
    title: str
    body: str
    raise_delay_seconds: int = 0
    recovery_delay_seconds: int = 30


OPERATIONS_CATALOG: Mapping[str, OperationSpec] = MappingProxyType({
    "UNKNOWN_ORDER": OperationSpec(
        "Hixton: Order ungeklärt",
        "Eine echte Order ist noch offen oder ihre Ausführung ist nicht vollständig bestätigt. "
        "Orderstatus und Ausführungsbericht prüfen. "
        "Nicht erneut kaufen oder den Schlüssel ersetzen.",
    ),
    "EXECUTION_REVIEW": OperationSpec(
        "Hixton: Handelsprüfung erforderlich",
        "Ein Echtgeldtest oder Live-Vorgang benötigt Prüfung. Bericht und Kontenabgleich ansehen. "
        "Diese Meldung bestätigt weder einen Verkauf noch eine sichere Freigabe.",
    ),
    "MARKET_DATA": OperationSpec(
        "Hixton: Marktdaten oder Laufzeit gestört",
        "Für einen aktiven Echtgeldkontext fehlen aktuelle, vollständig verarbeitete Marktdaten "
        "oder eine gesunde Laufzeit. Offene Positionen können unbetreut sein. Bot vor Ort prüfen.",
        raise_delay_seconds=120,
    ),
    "BINANCE_ACCESS": OperationSpec(
        "Hixton: Binance-Zugriff prüfen",
        "Der Binance-Zugriff fehlt oder wird nicht akzeptiert. Lokalen Schlüssel, Berechtigungen "
        "und öffentliche IP-Freigabe prüfen. Auch Verkäufe können betroffen sein.",
    ),
    "BINANCE_CLOCK": OperationSpec(
        "Hixton: Binance-Zeitprüfung fehlgeschlagen",
        "Binance lehnt den Zeitstempel ab. Systemzeit und Kontozugriff prüfen. "
        "Es wurde dadurch keine Order bestätigt oder erneut gesendet.",
    ),
    "BINANCE_CONNECTION": OperationSpec(
        "Hixton: Binance-Verbindung gestört",
        "Eine aktuelle passive Kontobeobachtung meldet einen Verbindungsfehler. "
        "Kontozugriff und laufende Positionen vor Ort prüfen.",
    ),
    "OBSERVATION_UNAVAILABLE": OperationSpec(
        "Hixton: Betriebsbeobachtung nicht verfügbar",
        "Der lokale Handelszustand konnte nicht zuverlässig gelesen werden. "
        "Der Zustand ist unbekannt; dies ist keine Entwarnung. Bot und Berichte vor Ort prüfen.",
    ),
})
ACCOUNT_UNOBSERVED = "ACCOUNT_UNOBSERVED"
_ACCOUNT_CODES = frozenset({"BINANCE_ACCESS", "BINANCE_CLOCK", "BINANCE_CONNECTION"})
_OPEN_ORDER_STATES = frozenset({
    "SUBMITTING", "UNKNOWN", "NEW", "PARTIALLY_FILLED", "PENDING_CANCEL",
    "FILL_DETAILS_PENDING",
})
_ACTIVE_TRIAL = frozenset({
    "WAITING_SIGNAL", "ENTRY_PENDING", "OPEN", "EXIT_PENDING", "AWAITING_RECONCILIATION",
    "NEEDS_REVIEW",
})
_MAX_OBSERVATION_GAP_SECONDS = 15
_TERMINAL = frozenset({"FILLED", "CANCELED", "EXPIRED", "EXPIRED_IN_MATCH", "REJECTED"})
_REQUIRED_SCHEMA = {
    "signal_trial": {"state", "reason", "owned_quantity", "residual_quantity"},
    "live_control": {"state"},
    "live_positions": {"quantity"},
    **{prefix + "_intents": {
        "intent_id", "state", "exchange_state", "executed_quantity", "order_id",
    } for prefix in ("trial", "live")},
    **{prefix + "_fills": {"intent_id", "quantity"} for prefix in ("trial", "live")},
}


class OperationsObservation(tuple[str, ...]):
    """Tuple-compatible fixed codes with private, non-deliverable order proof.

    Hashes identify only episode obligations; they never enter notification text.
    A missing order is not positive resolution evidence.
    """

    order_evidence: Mapping[str, bool]
    owned_real: bool

    def __new__(
        cls, codes: tuple[str, ...], order_evidence: Mapping[str, bool], owned_real: bool = False
    ) -> OperationsObservation:
        value = super().__new__(cls, codes)
        value.order_evidence = MappingProxyType(dict(order_evidence))
        value.owned_real = owned_real
        return value


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("An aware operational observation time is required")
    return value.astimezone(UTC)


def _timestamp(value: object) -> datetime | None:
    try:
        if isinstance(value, datetime):
            return _utc(value)
        if isinstance(value, str):
            return _utc(datetime.fromisoformat(value))
    except ValueError:
        pass
    return None


def _quantity(value: object) -> Decimal:
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        raise sqlite3.DatabaseError("Operational journal amounts are invalid") from None
    return number


def _rows(connection: sqlite3.Connection, table: str) -> tuple[sqlite3.Row, ...]:
    # All callers supply fixed internal table names, never external identifiers.
    return tuple(connection.execute(f"SELECT * FROM {table}"))


def _order_evidence(connection: sqlite3.Connection, prefix: str) -> dict[str, bool]:
    table = prefix + "_intents"
    evidence: dict[str, bool] = {}
    for row in _rows(connection, table):
        quantity = _quantity(row["executed_quantity"])
        fills = tuple(connection.execute(
            f"SELECT quantity FROM {prefix}_fills WHERE intent_id=?", (row["intent_id"],)
        ))
        fill_quantity = sum((_quantity(fill[0]) for fill in fills), Decimal(0))
        complete = bool(
            row["state"] in _TERMINAL and row["state"] == row["exchange_state"]
            and row["order_id"] and fill_quantity == quantity
            and (quantity > 0 or row["state"] != "FILLED")
        )
        unresolved = (
            row["state"] in _OPEN_ORDER_STATES or row["exchange_state"] in _OPEN_ORDER_STATES
            or ((row["state"] == "FILLED" or quantity > 0) and not complete)
        )
        if unresolved or complete:
            identity = hashlib.sha256(f"{prefix}|{row['intent_id']}".encode()).hexdigest()
            evidence[identity] = complete and not unresolved
    return evidence


def _market_unhealthy(snapshot: Mapping[str, object], now: datetime) -> bool:
    if snapshot.get("health") != "HEALTHY":
        return True
    final_times = snapshot.get("final_bar_times")
    expected = snapshot.get("expected_symbols")
    if isinstance(final_times, Mapping) and isinstance(expected, (tuple, list)):
        if not expected or set(final_times) != set(expected):
            return True
        required = now.replace(minute=0, second=0, microsecond=0) - timedelta(milliseconds=1)
        if (now - now.replace(minute=0, second=0, microsecond=0)).total_seconds() < 120:
            required -= timedelta(hours=1)
        for value in final_times.values():
            moment = _timestamp(value)
            if moment is None or moment < required or moment > now:
                return True
        return False  # A fresh REST-fed universe does not require a WebSocket.
    # Missing full-universe evidence is not proof of current finalized data.
    return True


def sample_operations(
    path: Path,
    runtime_snapshot: Mapping[str, object],
    runtime_errors: tuple[object, ...],
    now: datetime,
) -> OperationsObservation:
    """Read one coherent SQLite snapshot; failures propagate as unknown observation.

    Account health is a passive observation supplied by the caller, never fetched
    here. Arbitrary error/reason strings affect booleans only and never output text.
    """
    now = _utc(now)
    codes: set[str] = set()
    with closing(sqlite3.connect(
        path.resolve().as_uri() + "?mode=ro", uri=True, timeout=1
    )) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if not set(_REQUIRED_SCHEMA) <= tables:
            raise sqlite3.DatabaseError("Operational execution journal is unavailable")
        for table, required in _REQUIRED_SCHEMA.items():
            available = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            if not required <= available:
                raise sqlite3.DatabaseError("Operational execution journal is incomplete")
        active = False
        owned_real = False
        if "signal_trial" in tables:
            for row in _rows(connection, "signal_trial"):
                state = row["state"]
                owned = _quantity(row["owned_quantity"] or "0")
                residual = _quantity(row["residual_quantity"] or "0")
                owned_real = owned_real or residual > 0 or (
                    state not in {"COMPLETED", "CANCELED"} and owned > 0
                )
                # COMPLETED retains historical bought quantity, not current exposure.
                active = active or state in _ACTIVE_TRIAL or residual > 0 or (
                    state not in {"COMPLETED", "CANCELED"} and owned > 0
                )
                if state in {"FAILED", "NEEDS_REVIEW"} or (
                    bool(row["reason"]) and state in _ACTIVE_TRIAL
                ):
                    codes.add("EXECUTION_REVIEW")
        if "live_control" in tables:
            for row in _rows(connection, "live_control"):
                active = active or row["state"] in {"LIVE_ENABLED", "EXIT_ONLY", "NEEDS_REVIEW"}
                if row["state"] == "NEEDS_REVIEW":
                    codes.add("EXECUTION_REVIEW")
        if "live_positions" in tables:
            owned_real = owned_real or any(
                _quantity(row["quantity"]) > 0 for row in _rows(connection, "live_positions")
            )
            active = active or owned_real
        evidence = {key: value for prefix in ("trial", "live")
                    for key, value in _order_evidence(connection, prefix).items()}
        if any(not complete for complete in evidence.values()):
            codes.add("UNKNOWN_ORDER")
            active = True
        if active:
            if any(bool(error) for error in runtime_errors):
                codes.add("EXECUTION_REVIEW")
            if _market_unhealthy(runtime_snapshot, now):
                codes.add("MARKET_DATA")
        observation = runtime_snapshot.get("account_observation")
        account_observation = observation if isinstance(observation, Mapping) else {}
        state = account_observation.get("state")
        fresh = account_observation.get("fresh") is True
        if not (fresh and state == "CURRENT"):
            codes.add(ACCOUNT_UNOBSERVED)
        if active and fresh:
            code = account_observation.get("code")
            if state == "KEY_MISSING" or (state == "UNAVAILABLE" and code == -2015):
                codes.add("BINANCE_ACCESS")
            elif state == "UNAVAILABLE" and code == -1021:
                codes.add("BINANCE_CLOCK")
            elif state == "UNAVAILABLE":
                codes.add("BINANCE_CONNECTION")
    return OperationsObservation(tuple(sorted(codes)), evidence, owned_real)


def initialize_operations(connection: sqlite3.Connection) -> None:
    """Create tracker tables and break continuity on service construction/restart.

    Does not commit, replace a delivered episode or modify a trading table.
    """
    connection.execute(
        "CREATE TABLE IF NOT EXISTS operational_notice_control("
        "singleton INTEGER PRIMARY KEY CHECK(singleton=1), generation TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS operational_notice_episodes("
        "code TEXT PRIMARY KEY, episode TEXT NOT NULL, active_since TEXT, clear_since TEXT,"
        "last_observed TEXT, alerted INTEGER NOT NULL CHECK(alerted IN (0,1)))"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS operational_notice_orders("
        "episode TEXT NOT NULL,identity_hash TEXT NOT NULL,PRIMARY KEY(episode,identity_hash))"
    )
    connection.execute(
        "UPDATE operational_notice_episodes "
        "SET active_since=NULL,clear_since=NULL,last_observed=NULL"
    )


def reset_operations(connection: sqlite3.Connection) -> None:
    """Recipient/opt-in generation reset; caller also cancels its pending outbox."""
    connection.execute("DELETE FROM operational_notice_episodes")
    connection.execute("DELETE FROM operational_notice_orders")
    connection.execute("DELETE FROM operational_notice_control")


def _notice(code: str, generation: str, episode: str, now: datetime, recovery: bool) -> Notice:
    spec = OPERATIONS_CATALOG[code]
    identity = hashlib.sha256(f"{generation}|{code}|{episode}".encode()).hexdigest()
    return Notice(
        key=f"operation:{identity}:{'recovery' if recovery else 'alert'}",
        kind="operation_recovery" if recovery else "operation_alert",
        occurred_at=now,
        title=f"Hixton: Beobachtung wieder unauffällig ({code})" if recovery else spec.title,
        body=(
            "Die zuvor gemeldete Störung ist bei fortlaufender Beobachtung nicht mehr vorhanden. "
            "Dies bestätigt weder einen erfolgreichen Trade noch eine Echtgeldfreigabe."
            if recovery else spec.body
        ),
    )


def evaluate_operations(
    connection: sqlite3.Connection,
    generation: str,
    codes: tuple[str, ...],
    now: datetime,
    *,
    order_evidence: Mapping[str, bool] | None = None,
) -> tuple[Notice, ...]:
    """Advance durable episodes without committing; enqueue returned notices atomically."""
    if not connection.in_transaction:
        raise RuntimeError("Operational episodes require an explicit outbox transaction")
    if not isinstance(generation, str) or not generation or len(generation) > 128:
        raise ValueError("Invalid notification generation")
    if set(codes) - set(OPERATIONS_CATALOG) - {ACCOUNT_UNOBSERVED}:
        raise ValueError("Unrecognized operational code")
    now = _utc(now)
    if order_evidence is None and isinstance(codes, OperationsObservation):
        order_evidence = codes.order_evidence
    stamp = now.isoformat()
    previous = connection.execute(
        "SELECT generation FROM operational_notice_control WHERE singleton=1"
    ).fetchone()
    if previous is None or previous[0] != generation:
        reset_operations(connection)
        connection.execute(
            "INSERT INTO operational_notice_control(singleton,generation) VALUES(1,?)",
            (generation,),
        )
    notices: list[Notice] = []
    for code, spec in OPERATIONS_CATALOG.items():
        present = code in codes
        if not present and (
            "OBSERVATION_UNAVAILABLE" in codes
            or (code in _ACCOUNT_CODES and ACCOUNT_UNOBSERVED in codes)
        ):
            # Unknown is never a healthy observation, including its recovery timer.
            connection.execute(
                "UPDATE operational_notice_episodes SET clear_since=NULL,last_observed=NULL "
                "WHERE code=?", (code,)
            )
            continue
        row = connection.execute(
            "SELECT episode,active_since,clear_since,last_observed,alerted "
            "FROM operational_notice_episodes WHERE code=?", (code,)
        ).fetchone()
        if row is None:
            if not present:
                continue
            episode = uuid4().hex
            active_since: datetime | None = now
            clear_since: datetime | None = None
            last_observed: datetime | None = None
            alerted = False
        else:
            episode = str(row[0])
            active_since, clear_since, last_observed = (_timestamp(value) for value in row[1:4])
            alerted = bool(row[4])
        if code == "UNKNOWN_ORDER":
            if present and order_evidence is not None:
                for identity, complete in order_evidence.items():
                    if not complete:
                        if (len(identity) != 64
                            or any(char not in "0123456789abcdef" for char in identity)):
                            raise ValueError("Invalid operational order proof identity")
                        connection.execute(
                            "INSERT OR IGNORE INTO operational_notice_orders VALUES(?,?)",
                            (episode, identity),
                        )
            if not present and alerted:
                obligations = tuple(connection.execute(
                    "SELECT identity_hash FROM operational_notice_orders WHERE episode=?",
                    (episode,),
                ))
                if not obligations or order_evidence is None or not all(
                    order_evidence.get(obligation[0]) is True for obligation in obligations
                ):
                    connection.execute(
                        "UPDATE operational_notice_episodes "
                        "SET clear_since=NULL,last_observed=NULL WHERE code=?", (code,),
                    )
                    continue
        gap = None if last_observed is None else (now - last_observed).total_seconds()
        continuous = gap is not None and 0 <= gap <= _MAX_OBSERVATION_GAP_SECONDS
        if present:
            clear_since = None
            if active_since is None or not continuous:
                active_since = now
            if not alerted and (now - active_since).total_seconds() >= spec.raise_delay_seconds:
                notices.append(_notice(code, generation, episode, now, recovery=False))
                alerted = True
        elif not alerted:
            connection.execute("DELETE FROM operational_notice_episodes WHERE code=?", (code,))
            continue
        else:
            if clear_since is None or not continuous:
                clear_since = now
            if (now - clear_since).total_seconds() >= spec.recovery_delay_seconds:
                notices.append(_notice(code, generation, episode, now, recovery=True))
                connection.execute("DELETE FROM operational_notice_episodes WHERE code=?", (code,))
                connection.execute(
                    "DELETE FROM operational_notice_orders WHERE episode=?", (episode,)
                )
                continue
        connection.execute(
            "INSERT INTO operational_notice_episodes"
            "(code,episode,active_since,clear_since,last_observed,alerted) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(code) DO UPDATE SET episode=excluded.episode,"
            "active_since=excluded.active_since,clear_since=excluded.clear_since,"
            "last_observed=excluded.last_observed,alerted=excluded.alerted",
            (code, episode, active_since.isoformat() if active_since else None,
             clear_since.isoformat() if clear_since else None, stamp, int(alerted)),
        )
    return tuple(notices)
