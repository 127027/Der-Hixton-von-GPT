"""Sanitized 24/7 execution diagnostics for trial, Live and Paper parity."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_FINAL_ORDER = {"FILLED", "CANCELED", "REJECTED", "EXPIRED", "EXPIRED_IN_MATCH"}
_ERROR_REASONS = {
    "ACCOUNT_RECONCILIATION_MISMATCH",
    "EXIT_BELOW_MINIMUM_REQUIRES_REVIEW",
    "EXIT_RESIDUAL_REQUIRES_REVIEW",
    "FROZEN_STRATEGY_MISMATCH",
    "LIVE_RUNTIME_REQUIRES_REVIEW",
    "PATCH_SOURCE_CHANGED_EXIT_ONLY",
}
_WARNING_REASONS = {
    "ENTRY_EXPIRED",
    "PATCH_SOURCE_CHANGED_REENABLE_REQUIRED",
    "EXECUTION_SOURCE_CHANGED_DURING_TEST",
    "EXECUTION_SOURCE_CHANGED_BEFORE_ORDER",
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
        is not None
    )


def _json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _delay_seconds(expected: str | None, actual: str | None) -> float | None:
    before = _time(expected)
    after = _time(actual)
    if before is None or after is None:
        return None
    return round((after - before).total_seconds(), 3)


def _timing_class(action: str, delay: float | None) -> str:
    if delay is None:
        return "NOT_AVAILABLE"
    if delay < -1:
        return "EARLY_CLOCK_ORDERING_ERROR"
    if action == "ENTER_LONG" and delay > 90:
        return "LATE_ENTRY"
    if action == "EXIT_LONG" and delay > 90:
        return "LATE_EXIT"
    return "ON_TIME"


def _submit_time(
    connection: sqlite3.Connection,
    audit_table: str,
    intent_id: str,
) -> str | None:
    if not _table_exists(connection, audit_table):
        return None
    row = connection.execute(
        f"SELECT at_utc FROM {audit_table} "
        "WHERE intent_id=? AND action='SUBMITTING' ORDER BY id LIMIT 1",
        (intent_id,),
    ).fetchone()
    return str(row["at_utc"]) if row is not None else None


def _intent_report(
    connection: sqlite3.Connection,
    *,
    intent_table: str,
    fill_table: str,
    audit_table: str,
    intent_id: str | None,
    signal_at: str | None,
    action: str,
) -> dict[str, object] | None:
    if not intent_id or not _table_exists(connection, intent_table):
        return None
    row = connection.execute(
        f"SELECT * FROM {intent_table} WHERE intent_id=?",
        (intent_id,),
    ).fetchone()
    if row is None:
        return None
    fill_count = 0
    if _table_exists(connection, fill_table):
        fill_count = int(
            connection.execute(
                f"SELECT COUNT(*) FROM {fill_table} WHERE intent_id=?",
                (intent_id,),
            ).fetchone()[0]
        )
    submitted_at = _submit_time(connection, audit_table, intent_id)
    recorded_at = str(row["updated_at"]) if row["updated_at"] else None
    delay = _delay_seconds(signal_at, submitted_at)
    return {
        "intent_id": intent_id,
        "strategy_version": row["strategy"],
        "side": row["side"],
        "state": row["state"],
        "exchange_state": row["exchange_state"],
        "exchange_order_id": row["order_id"],
        "fill_count": fill_count,
        "signal_at_utc": signal_at,
        "submitted_at_utc": submitted_at,
        "recorded_at_utc": recorded_at,
        "submit_delay_seconds": delay,
        "timing": _timing_class(action, delay),
        "binance_terminal": row["exchange_state"] in _FINAL_ORDER,
        "binance_filled": row["exchange_state"] == "FILLED" and fill_count > 0,
    }


def _incident(
    items: list[dict[str, object]],
    *,
    severity: str,
    code: str,
    detail: str,
    symbol: str | None = None,
    signal_id: str | None = None,
    intent_id: str | None = None,
) -> None:
    items.append(
        {
            "severity": severity,
            "code": code,
            "detail": detail,
            "symbol": symbol,
            "signal_id": signal_id,
            "intent_id": intent_id,
        }
    )


def build_execution_report(
    live_database: Path,
    paper_database: Path,
    *,
    application_version: str,
    execution_source_sha256: str,
    strategy_version: str,
    allocator_version: str,
) -> dict[str, object]:
    """Build a read-only report. API keys/secrets are never read or emitted."""
    incidents: list[dict[str, object]] = []
    report: dict[str, object] = {
        "generated_at_utc": _utc_now(),
        "runtime_identity": {
            "application_version": application_version,
            "execution_source_sha256": execution_source_sha256,
            "strategy_version": strategy_version,
            "allocator_version": allocator_version,
        },
    }

    paper_events: dict[str, dict[str, object]] = {}
    paper_strategy_version: str | None = None
    if paper_database.exists():
        with sqlite3.connect(paper_database) as paper:
            paper.row_factory = sqlite3.Row
            if _table_exists(paper, "paper_strategy_state"):
                row = paper.execute(
                    "SELECT strategy_version FROM paper_strategy_state WHERE singleton=1"
                ).fetchone()
                if row is not None:
                    paper_strategy_version = str(row["strategy_version"])
            if _table_exists(paper, "paper_events"):
                rows = paper.execute(
                    "SELECT signal_id,occurred_at_utc,symbol,action,status,reason,"
                    "strategy_version FROM paper_events ORDER BY occurred_at_utc DESC LIMIT 5000"
                ).fetchall()
                paper_events = {
                    str(row["signal_id"]): {
                        "occurred_at_utc": row["occurred_at_utc"],
                        "symbol": row["symbol"],
                        "action": row["action"],
                        "status": row["status"],
                        "reason": row["reason"],
                        "strategy_version": row["strategy_version"],
                    }
                    for row in rows
                }
    report["paper_identity"] = {
        "strategy_version": paper_strategy_version,
        "matches_runtime": paper_strategy_version in {None, strategy_version},
    }
    if paper_strategy_version not in {None, strategy_version}:
        _incident(
            incidents,
            severity="ERROR",
            code="PAPER_RUNTIME_STRATEGY_MISMATCH",
            detail="Paper und Echtgeld-Runtime verwenden unterschiedliche Strategieversionen.",
        )

    trial_payload: dict[str, object] = {"state": "NOT_STARTED"}
    live_payload: dict[str, object] = {
        "state": "LIVE_DISABLED",
        "events": [],
        "positions": [],
        "unresolved_intents": [],
    }
    parity_rows: list[dict[str, object]] = []
    cycles: list[dict[str, object]] = []

    if live_database.exists():
        with sqlite3.connect(live_database) as live:
            live.row_factory = sqlite3.Row
            if _table_exists(live, "signal_trial"):
                trial = live.execute(
                    "SELECT * FROM signal_trial WHERE singleton=1"
                ).fetchone()
                if trial is not None:
                    trial_columns = set(trial.keys())
                    strategy = _json(str(trial["strategy_json"]))
                    trial_source = (
                        str(trial["execution_source_sha256"])
                        if "execution_source_sha256" in trial_columns
                        else "legacy"
                    )
                    trial_allocator = (
                        str(trial["allocator_version"])
                        if "allocator_version" in trial_columns
                        else "legacy"
                    )
                    entry_signal = _json(trial["entry_signal_json"])
                    exit_signal = _json(trial["exit_signal_json"])
                    buy = _intent_report(
                        live,
                        intent_table="trial_intents",
                        fill_table="trial_fills",
                        audit_table="trial_order_audit",
                        intent_id=trial["buy_id"],
                        signal_at=entry_signal.get("bar_close"),
                        action="ENTER_LONG",
                    )
                    sell = _intent_report(
                        live,
                        intent_table="trial_intents",
                        fill_table="trial_fills",
                        audit_table="trial_order_audit",
                        intent_id=trial["sell_id"],
                        signal_at=exit_signal.get("bar_close"),
                        action="EXIT_LONG",
                    )
                    source_matches = trial_source == execution_source_sha256
                    strategy_matches = strategy.get("version") == strategy_version
                    trial_payload = {
                        "state": trial["state"],
                        "symbol": trial["symbol"],
                        "reason": trial["reason"],
                        "armed_at_utc": trial["armed_at"],
                        "completed_at_utc": trial["completed_at"],
                        "account_reconciled": trial["state"] == "COMPLETED",
                        "residual_quantity": trial["residual_quantity"],
                        "frozen_identity": {
                            "application_version": (
                                trial["application_version"]
                                if "application_version" in trial_columns
                                else "legacy"
                            ),
                            "execution_source_sha256": trial_source,
                            "strategy_version": strategy.get("version"),
                            "allocator_version": trial_allocator,
                        },
                        "identity_matches_current": {
                            "source": source_matches,
                            "strategy": strategy_matches,
                            "allocator": trial_allocator == allocator_version,
                        },
                        "buy": buy,
                        "sell": sell,
                        "binance_roundtrip_complete": bool(
                            trial["state"] == "COMPLETED"
                            and buy
                            and buy["binance_filled"]
                            and sell
                            and sell["binance_filled"]
                        ),
                    }
                    if not source_matches:
                        _incident(
                            incidents,
                            severity=(
                                "ERROR"
                                if trial["state"] not in ("COMPLETED", "CANCELED")
                                else "WARNING"
                            ),
                            code="TRIAL_EXECUTION_SOURCE_STALE",
                            detail="50-USDC-Test stammt aus einer anderen Patch-/Quellversion.",
                            symbol=trial["symbol"],
                        )
                    if not strategy_matches:
                        _incident(
                            incidents,
                            severity="ERROR",
                            code="TRIAL_STRATEGY_VERSION_STALE",
                            detail=(
                                "50-USDC-Test und aktuelle Strategieversion stimmen nicht "
                                "überein."
                            ),
                            symbol=trial["symbol"],
                        )
                    for item in (buy, sell):
                        if not item:
                            continue
                        timing = str(item["timing"])
                        if timing == "EARLY_CLOCK_ORDERING_ERROR":
                            _incident(
                                incidents,
                                severity="ERROR",
                                code="ORDER_BEFORE_SIGNAL_CLOSE",
                                detail="Order-Zeit liegt vor dem zugehörigen geschlossenen Signal.",
                                symbol=trial["symbol"],
                                intent_id=str(item["intent_id"]),
                            )
                        elif timing == "LATE_ENTRY":
                            _incident(
                                incidents,
                                severity="ERROR",
                                code="TRIAL_ENTRY_LATE",
                                detail=(
                                    "50-USDC-Einstieg wurde mehr als 90 Sekunden nach Signal "
                                    "gesendet."
                                ),
                                symbol=trial["symbol"],
                                intent_id=str(item["intent_id"]),
                            )
                        elif timing == "LATE_EXIT":
                            _incident(
                                incidents,
                                severity="WARNING",
                                code="TRIAL_EXIT_LATE",
                                detail=(
                                    "50-USDC-Ausstieg wurde mehr als 90 Sekunden nach "
                                    "Exit-Signal gesendet."
                                ),
                                symbol=trial["symbol"],
                                intent_id=str(item["intent_id"]),
                            )
                    if trial["state"] in ("FAILED", "NEEDS_REVIEW"):
                        _incident(
                            incidents,
                            severity="ERROR",
                            code="TRIAL_REQUIRES_REVIEW",
                            detail=(
                                f"50-USDC-Test ist im Zustand {trial['state']}: "
                                f"{trial['reason']}"
                            ),
                            symbol=trial["symbol"],
                        )

            if _table_exists(live, "live_control"):
                control = live.execute(
                    "SELECT * FROM live_control WHERE singleton=1"
                ).fetchone()
                if control is not None:
                    control_columns = set(control.keys())
                    strategy = _json(str(control["strategy_json"]))
                    capital = _json(str(control["capital_json"]))
                    frozen_source = (
                        str(control["execution_source_sha256"])
                        if "execution_source_sha256" in control_columns
                        else "legacy"
                    )
                    frozen_app = (
                        str(control["application_version"])
                        if "application_version" in control_columns
                        else "legacy"
                    )
                    positions = []
                    if _table_exists(live, "live_positions"):
                        positions = [
                            dict(row)
                            for row in live.execute(
                                "SELECT symbol,quantity,entry_time_utc,entry_signal_id,slot_count "
                                "FROM live_positions ORDER BY symbol"
                            ).fetchall()
                        ]
                    unresolved: list[str] = []
                    if _table_exists(live, "live_intents"):
                        unresolved = [
                            str(row["intent_id"])
                            for row in live.execute(
                                "SELECT intent_id FROM live_intents WHERE state NOT IN "
                                "('FILLED','CANCELED','REJECTED','EXPIRED','EXPIRED_IN_MATCH')"
                            ).fetchall()
                        ]
                    event_rows = (
                        live.execute(
                            "SELECT * FROM live_events ORDER BY occurred_at_utc DESC LIMIT 1000"
                        ).fetchall()
                        if _table_exists(live, "live_events")
                        else []
                    )
                    event_reports: list[dict[str, object]] = []
                    chronological: list[dict[str, object]] = []
                    for event in event_rows:
                        action = str(event["action"])
                        intent = _intent_report(
                            live,
                            intent_table="live_intents",
                            fill_table="live_fills",
                            audit_table="live_order_audit",
                            intent_id=event["intent_id"],
                            signal_at=str(event["occurred_at_utc"]),
                            action=action,
                        )
                        paper_match = paper_events.get(str(event["signal_id"]))
                        parity = {
                            "signal_id": event["signal_id"],
                            "symbol": event["symbol"],
                            "action": action,
                            "live_status": event["status"],
                            "live_reason": event["reason"],
                            "paper_seen": paper_match is not None,
                            "paper_action": paper_match.get("action") if paper_match else None,
                            "paper_status": paper_match.get("status") if paper_match else None,
                            "paper_reason": paper_match.get("reason") if paper_match else None,
                            "paper_strategy_version": (
                                paper_match.get("strategy_version") if paper_match else None
                            ),
                        }
                        parity_rows.append(parity)
                        item = {
                            "signal_id": event["signal_id"],
                            "occurred_at_utc": event["occurred_at_utc"],
                            "symbol": event["symbol"],
                            "action": action,
                            "status": event["status"],
                            "reason": event["reason"],
                            "order": intent,
                            "paper_parity": parity,
                        }
                        event_reports.append(item)
                        chronological.append(item)
                        if intent:
                            timing = str(intent["timing"])
                            if timing == "EARLY_CLOCK_ORDERING_ERROR":
                                _incident(
                                    incidents,
                                    severity="ERROR",
                                    code="LIVE_ORDER_BEFORE_SIGNAL_CLOSE",
                                    detail=(
                                        "Live-Order liegt zeitlich vor dem geschlossenen "
                                        "Signal."
                                    ),
                                    symbol=str(event["symbol"]),
                                    signal_id=str(event["signal_id"]),
                                    intent_id=str(intent["intent_id"]),
                                )
                            elif timing == "LATE_ENTRY":
                                _incident(
                                    incidents,
                                    severity="ERROR",
                                    code="LIVE_ENTRY_LATE",
                                    detail=(
                                        "Live-Einstieg wurde mehr als 90 Sekunden nach "
                                        "Signal gesendet."
                                    ),
                                    symbol=str(event["symbol"]),
                                    signal_id=str(event["signal_id"]),
                                    intent_id=str(intent["intent_id"]),
                                )
                            elif timing == "LATE_EXIT":
                                _incident(
                                    incidents,
                                    severity="WARNING",
                                    code="LIVE_EXIT_LATE",
                                    detail=(
                                        "Live-Ausstieg wurde mehr als 90 Sekunden nach "
                                        "Signal gesendet."
                                    ),
                                    symbol=str(event["symbol"]),
                                    signal_id=str(event["signal_id"]),
                                    intent_id=str(intent["intent_id"]),
                                )
                        reason = str(event["reason"] or "")
                        if reason in _ERROR_REASONS or reason.startswith("EXIT_ORDER_"):
                            _incident(
                                incidents,
                                severity="ERROR",
                                code="LIVE_EVENT_ERROR",
                                detail=reason,
                                symbol=str(event["symbol"]),
                                signal_id=str(event["signal_id"]),
                                intent_id=str(event["intent_id"] or "") or None,
                            )
                        elif reason in _WARNING_REASONS:
                            _incident(
                                incidents,
                                severity="WARNING",
                                code="LIVE_EVENT_WARNING",
                                detail=reason,
                                symbol=str(event["symbol"]),
                                signal_id=str(event["signal_id"]),
                                intent_id=str(event["intent_id"] or "") or None,
                            )
                        if paper_match is not None and paper_match.get("action") != action:
                            _incident(
                                incidents,
                                severity="ERROR",
                                code="PAPER_LIVE_ACTION_MISMATCH",
                                detail=(
                                    "Gleiche Signal-ID hat in Paper und Live unterschiedliche "
                                    "Aktion."
                                ),
                                symbol=str(event["symbol"]),
                                signal_id=str(event["signal_id"]),
                            )

                    chronological.sort(key=lambda item: str(item["occurred_at_utc"]))
                    opened: dict[str, dict[str, object]] = {}
                    for item in chronological:
                        if item["status"] != "FILLED":
                            continue
                        symbol = str(item["symbol"])
                        if item["action"] == "ENTER_LONG":
                            opened[symbol] = item
                        elif item["action"] == "EXIT_LONG":
                            entry = opened.pop(symbol, None)
                            cycles.append(
                                {
                                    "symbol": symbol,
                                    "entry_signal_id": (
                                        entry["signal_id"] if entry is not None else None
                                    ),
                                    "exit_signal_id": item["signal_id"],
                                    "binance_entry_filled": bool(
                                        entry
                                        and entry["order"]
                                        and entry["order"]["binance_filled"]
                                    ),
                                    "binance_exit_filled": bool(
                                        item["order"] and item["order"]["binance_filled"]
                                    ),
                                    "complete": bool(
                                        entry
                                        and entry["order"]
                                        and entry["order"]["binance_filled"]
                                        and item["order"]
                                        and item["order"]["binance_filled"]
                                    ),
                                }
                            )

                    source_matches = frozen_source == execution_source_sha256
                    strategy_matches = strategy.get("version") == strategy_version
                    allocator_matches = capital.get("allocator_version") == allocator_version
                    live_payload = {
                        "state": control["state"],
                        "reason": control["reason"],
                        "enabled_at_utc": control["enabled_at"],
                        "updated_at_utc": control["updated_at"],
                        "entries_enabled": bool(control["entries_enabled"]),
                        "frozen_identity": {
                            "application_version": frozen_app,
                            "execution_source_sha256": frozen_source,
                            "strategy_version": strategy.get("version"),
                            "allocator_version": capital.get("allocator_version"),
                        },
                        "identity_matches_current": {
                            "source": source_matches,
                            "strategy": strategy_matches,
                            "allocator": allocator_matches,
                        },
                        "positions": positions,
                        "unresolved_intents": unresolved,
                        "events": event_reports,
                    }
                    if not source_matches:
                        _incident(
                            incidents,
                            severity="ERROR" if positions or unresolved else "WARNING",
                            code="LIVE_EXECUTION_SOURCE_STALE",
                            detail=(
                                "Aktive/gespeicherte Live-Sitzung stammt aus einer anderen "
                                "Patch-Version."
                            ),
                        )
                    if not strategy_matches:
                        _incident(
                            incidents,
                            severity="ERROR",
                            code="LIVE_STRATEGY_VERSION_STALE",
                            detail=(
                                "Live-Ledger und aktuelle Strategieversion stimmen nicht "
                                "überein."
                            ),
                        )
                    if not allocator_matches:
                        _incident(
                            incidents,
                            severity="ERROR",
                            code="LIVE_ALLOCATOR_VERSION_STALE",
                            detail=(
                                "Live-Ledger und aktueller Kapital-Allocator stimmen nicht "
                                "überein."
                            ),
                        )
                    if unresolved:
                        _incident(
                            incidents,
                            severity="ERROR",
                            code="LIVE_UNRESOLVED_BINANCE_ORDERS",
                            detail=(
                                f"{len(unresolved)} Live-Order(s) sind noch nicht terminal "
                                "abgeglichen."
                            ),
                        )
                    if control["state"] == "NEEDS_REVIEW":
                        _incident(
                            incidents,
                            severity="ERROR",
                            code="LIVE_NEEDS_REVIEW",
                            detail=str(control["reason"] or "Live-Ledger benötigt Klärung."),
                        )

    report["trial"] = trial_payload
    report["live"] = live_payload
    report["paper_live_parity"] = {
        "checked_live_events": len(parity_rows),
        "events": parity_rows,
    }
    report["completed_live_roundtrips"] = cycles
    severity_order = {"INFO": 0, "WARNING": 1, "ERROR": 2}
    maximum = max((severity_order.get(str(item["severity"]), 0) for item in incidents), default=0)
    status = "ERROR" if maximum >= 2 else "WARNING" if maximum == 1 else "OK"
    report["incidents"] = incidents
    report["summary"] = {
        "status": status,
        "error_count": sum(item["severity"] == "ERROR" for item in incidents),
        "warning_count": sum(item["severity"] == "WARNING" for item in incidents),
        "trial_binance_roundtrip_complete": bool(
            isinstance(trial_payload, dict)
            and trial_payload.get("binance_roundtrip_complete") is True
        ),
        "live_open_positions": len(
            live_payload.get("positions", []) if isinstance(live_payload, dict) else []
        ),
        "live_unresolved_intents": len(
            live_payload.get("unresolved_intents", [])
            if isinstance(live_payload, dict)
            else []
        ),
    }
    return report


def write_execution_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)
