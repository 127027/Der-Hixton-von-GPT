"""Durable execution-test evidence, independent of later UI/source releases.

This attests a historical signal-driven Binance roundtrip, not a strategy's
future performance or permission to submit another order. Reads never migrate.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from hixton.domain.markets import split_market

VERSION = "SIGNAL-ROUNDTRIP-ACCEPTANCE-1"


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Missing timezone")
    return parsed.astimezone(UTC)


def _decimal(value: Any) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Non-finite evidence")
    return result


def _proof(connection: sqlite3.Connection) -> dict[str, Any]:
    row = connection.execute("SELECT * FROM signal_trial WHERE singleton=1").fetchone()
    if row is None or row["state"] != "COMPLETED" or row["reason"]:
        raise ValueError("Roundtrip not completed")
    trial = dict(row)
    strategy = json.loads(trial["strategy_json"])
    if not isinstance(strategy, dict):
        raise ValueError("Invalid strategy evidence")
    base, quote = split_market(trial["symbol"])
    if quote != "USDC" or strategy.get("quote_asset") != quote:
        raise ValueError("Wrong quote asset")
    if _decimal(trial["residual_quantity"]) != 0 or trial["entries_enabled"]:
        raise ValueError("Unsettled trial")
    armed, completed = _time(trial["armed_at"]), _time(trial["completed_at"])
    if completed <= armed:
        raise ValueError("Invalid completion clock")
    intents = connection.execute("SELECT * FROM trial_intents ORDER BY side").fetchall()
    if len(intents) != 2 or {r["intent_id"] for r in intents} != {
        trial["buy_id"], trial["sell_id"]
    }:
        raise ValueError("Incomplete or foreign order history")
    baseline = connection.execute("SELECT * FROM trial_account_baseline").fetchall()
    if len(baseline) != 1 or baseline[0]["account"] != trial["account"]:
        raise ValueError("Wrong baseline account")
    balances = json.loads(baseline[0]["balances_json"])
    if not isinstance(balances, dict) or not balances:
        raise ValueError("Invalid baseline balances")
    if any(not asset or not asset.isalnum() or _decimal(amount) < 0
           for asset, amount in balances.items()):
        raise ValueError("Invalid baseline asset or amount")
    if (_decimal(balances.get("USDC", "0")) < 50
        or not 0 <= (armed - _time(baseline[0]["observed_at"])).total_seconds() <= 15):
        raise ValueError("Invalid baseline amount or clock")
    audit = connection.execute(
        "SELECT * FROM trial_order_audit WHERE "
        "(intent_id=? AND action='TRIAL_COMPLETED') OR "
        "(intent_id='ACCOUNT' AND action='BALANCES_MATCH') ORDER BY id DESC",
        (trial["trial_id"],),
    ).fetchall()
    completion = next((r for r in audit if r["action"] == "TRIAL_COMPLETED"), None)
    match = next((r for r in audit if r["action"] == "BALANCES_MATCH"
                  and completion is not None and r["id"] < completion["id"]), None)
    if completion is None or match is None:
        raise ValueError("Missing completed reconciliation audit")
    fills = connection.execute(
        "SELECT * FROM trial_fills ORDER BY account,symbol,trade_id"
    ).fetchall()
    if {r["intent_id"] for r in fills} != {trial["buy_id"], trial["sell_id"]}:
        raise ValueError("Missing or foreign fills")
    base_movement = Decimal(0)
    submission_proof: list[dict[str, Any]] = []
    latest_fill = armed
    clocks: dict[str, datetime] = {}
    signal_clocks: dict[str, datetime] = {}
    net_bought = Decimal(0)
    if len({r["order_id"] for r in intents}) != 2:
        raise ValueError("Duplicate exchange order")
    for order in intents:
        side = order["side"]
        expected_client = "hxtrial_" + hashlib.sha256(
            f"LIVE|{trial['account']}|{order['intent_id']}".encode()
        ).hexdigest()[:28]
        if (side not in {"BUY", "SELL"} or order["account"] != trial["account"]
            or order["symbol"] != trial["symbol"]
            or order["strategy"] != strategy.get("version")
            or order["intent_id"] != trial["buy_id" if side == "BUY" else "sell_id"]
            or order["state"] != "FILLED" or order["exchange_state"] != "FILLED"
            or not order["order_id"] or order["client_id"] != expected_client):
            raise ValueError("Unconfirmed or mismatched order")
        if side == "BUY" and (
            _decimal(order["quote_budget"]) != Decimal(50)
            or _decimal(order["base_quantity"]) != 0
        ):
            raise ValueError("Not the 50-USDC test")
        if side == "SELL" and (
            _decimal(order["quote_budget"]) != 0
            or _decimal(order["base_quantity"]) != _decimal(order["executed_quantity"])
        ):
            raise ValueError("Invalid exit quantity")
        signal = json.loads(trial["entry_signal_json" if side == "BUY" else "exit_signal_json"])
        if not isinstance(signal, dict) or not isinstance(signal.get("reason"), str):
            raise ValueError("Invalid signal evidence")
        reason = signal.get("reason", "")
        valid_reason = (
            reason == "HIXTON_ENTER_LONG" if side == "BUY" else
            reason in {"HIXTON_EXIT_LONG", "POLICY_STOP_ATR", "POLICY_TRAIL_ATR",
                       "SATELLITE_MAX_HOLD"} or reason.startswith("CORE_CAPACITY_HANDOFF::")
        )
        if (signal.get("symbol") != trial["symbol"]
            or signal.get("strategy_version") != strategy.get("version")
            or not valid_reason):
            raise ValueError("Not a strategy signal")
        signal_at = _time(signal["bar_close"])
        signal_clocks[side] = signal_at
        submit = connection.execute(
            "SELECT * FROM trial_order_audit WHERE intent_id=? AND action='SUBMITTING' "
            "ORDER BY id LIMIT 1", (order["intent_id"],),
        ).fetchone()
        if submit is None:
            raise ValueError("Missing submission clock")
        reserved = connection.execute(
            "SELECT * FROM trial_order_audit WHERE intent_id=? AND action=? ORDER BY id LIMIT 1",
            (trial["trial_id"], "ENTRY_RESERVED" if side == "BUY" else "EXIT_RESERVED"),
        ).fetchone()
        if reserved is None or reserved["id"] >= submit["id"]:
            raise ValueError("Missing automatic signal reservation")
        submitted = _time(submit["at_utc"])
        clocks[side] = submitted
        if not -1 <= (submitted - signal_at).total_seconds() <= 90:
            raise ValueError("Submission outside the signal window")
        if submitted < armed or submitted > completed or (side == "BUY" and signal_at < armed):
            raise ValueError("Invalid signal chronology")
        order_fills = [r for r in fills if r["intent_id"] == order["intent_id"]]
        quantity, gross_quote = Decimal(0), Decimal(0)
        for fill in order_fills:
            qty, price, fee = (_decimal(fill[k]) for k in ("quantity", "price", "commission"))
            if (fill["account"] != trial["account"] or fill["symbol"] != trial["symbol"]
                or not fill["trade_id"] or qty <= 0 or price <= 0 or fee < 0
                or not fill["commission_asset"]):
                raise ValueError("Invalid fill")
            quantity += qty
            quote_qty = (_decimal(fill["quote_quantity"])
                         if fill["quote_quantity"] is not None else qty * price)
            if quote_qty <= 0 or abs(quote_qty - qty * price) > Decimal("0.00000001"):
                raise ValueError("Invalid fill quote")
            gross_quote += quote_qty
            base_movement += qty if side == "BUY" else -qty
            if fill["commission_asset"] == base:
                base_movement -= fee
            if side == "BUY":
                net_bought += qty - (fee if fill["commission_asset"] == base else Decimal(0))
        if (quantity != _decimal(order["executed_quantity"])
            or gross_quote <= 0 or gross_quote != _decimal(order["cumulative_quote"])):
            raise ValueError("Incomplete fill totals")
        latest_fill = max(latest_fill, _time(order["updated_at"]))
        submission_proof.extend((dict(reserved), dict(submit)))
    if (clocks["SELL"] <= clocks["BUY"] or signal_clocks["SELL"] < signal_clocks["BUY"]
        or net_bought <= 0 or _decimal(trial["owned_quantity"]) != net_bought or base_movement != 0
        or _time(match["at_utc"]) < latest_fill
        or _time(completion["at_utc"]) < _time(match["at_utc"])):
        raise ValueError("Unsettled owned quantity or stale reconciliation")
    return {
        "trial": trial, "intents": [dict(r) for r in intents],
        "fills": [dict(r) for r in fills], "baseline": dict(baseline[0]),
        "completion": dict(completion), "balance_match": dict(match),
        "submissions": submission_proof,
    }


def _digest(proof: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(proof, sort_keys=True, allow_nan=False).encode()).hexdigest()


def initialize_acceptance(connection: sqlite3.Connection) -> None:
    """Startup migration: derive only from the current complete original ledger."""
    if not connection.in_transaction:
        connection.execute("BEGIN IMMEDIATE")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS trial_acceptance ("
        "singleton INTEGER PRIMARY KEY CHECK(singleton=1), version TEXT NOT NULL, "
        "trial_id TEXT NOT NULL, account TEXT NOT NULL, accepted_at TEXT NOT NULL, "
        "evidence_sha256 TEXT NOT NULL)"
    )
    if connection.execute("SELECT 1 FROM trial_acceptance").fetchone() is None:
        issue_acceptance(connection)


def issue_acceptance(connection: sqlite3.Connection) -> bool:
    try:
        proof = _proof(connection)
    except (ValueError, TypeError, KeyError, IndexError, ArithmeticError, sqlite3.DatabaseError):
        return False
    trial = proof["trial"]
    connection.execute(
        "INSERT OR REPLACE INTO trial_acceptance VALUES(1,?,?,?,?,?)",
        (VERSION, trial["trial_id"], trial["account"], trial["completed_at"], _digest(proof)),
    )
    return True


def acceptance_status(connection: sqlite3.Connection, account: str | None) -> dict[str, object]:
    """No mutation, no key material or account identifiers in public output."""
    result: dict[str, object] = {
        "eligible": False, "state": "NOT_VERIFIED", "reason": "ROUNDTRIP_PROOF_REQUIRED",
        "trial_id": None, "accepted_at_utc": None,
    }
    try:
        trial = connection.execute("SELECT * FROM signal_trial WHERE singleton=1").fetchone()
        if trial is None:
            return result
        if trial["state"] != "COMPLETED":
            return {**result, "state": "RETEST_REQUIRED", "reason": "TEST_NOT_COMPLETED"}
        certificate = connection.execute(
            "SELECT * FROM trial_acceptance WHERE singleton=1"
        ).fetchone()
        if certificate is None or certificate["version"] != VERSION:
            return result
        if account is None or certificate["account"] != account:
            return {**result, "state": "ACCOUNT_MISMATCH", "reason": "TESTED_KEY_REQUIRED"}
        proof = _proof(connection)
        if (certificate["trial_id"] != proof["trial"]["trial_id"]
            or certificate["account"] != proof["trial"]["account"]
            or certificate["accepted_at"] != proof["trial"]["completed_at"]
            or certificate["evidence_sha256"] != _digest(proof)):
            return result
        return {
            "eligible": True, "state": "ACCEPTED", "reason": None,
            "trial_id": certificate["trial_id"], "accepted_at_utc": certificate["accepted_at"],
        }
    except (ValueError, TypeError, KeyError, IndexError, ArithmeticError, sqlite3.DatabaseError):
        return result
