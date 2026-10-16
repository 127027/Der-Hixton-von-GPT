"""Explicit stopped-runtime recovery of a missing, never-acknowledged trial BUY.

This administrative path never submits/cancels an order, certifies a test, or
asserts an exchange terminal state. Ordinary unknown-order gates stay intact.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from hixton.live.exchange import ExchangeRequestError, SpotTransport
from hixton.live.orders import OrderJournal, TrialIntent

_PATHS = {
    "/api/v3/time",
    "/api/v3/order",
    "/api/v3/allOrders",
    "/api/v3/myTrades",
    "/api/v3/account",
    "/api/v3/openOrders",
}
_FINAL = {"FILLED", "CANCELED", "REJECTED", "EXPIRED", "EXPIRED_IN_MATCH"}
_RESOLUTION = "MANUAL_NO_ORDER_CONFIRMED"


@dataclass(frozen=True)
class RecoveryIdentity:
    account_fingerprint: str
    application_version: str
    execution_source_sha256: str
    allocator_version: str
    strategy_version: str


class ReadOnlyRecoveryTransport:
    """A defensive GET-only facade; injected transport owns signing and keys."""

    def __init__(self, transport: SpotTransport, stopped: Callable[[], bool]):
        self.transport = transport
        self.stopped = stopped

    def request(self, method: str, path: str, params: dict[str, str]) -> Any:
        if method != "GET" or path not in _PATHS:
            raise ValueError("Recovery permits allowlisted GET requests only")
        if self.stopped() is not True:
            raise RuntimeError("Recovery requires the exclusive stopped runtime")
        return self.transport.request(method, path, params)


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Recovery requires timezone-aware clocks")
    return value.astimezone(UTC)


def _decimal(value: object) -> Decimal:
    if not isinstance(value, str):
        raise ValueError("Recovery requires exact decimal strings")
    amount = Decimal(value)
    if not amount.is_finite() or amount < 0:
        raise ValueError("Invalid recovery amount")
    return amount


def _rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    allowed = {
        "signal_trial",
        "trial_intents",
        "trial_fills",
        "trial_order_audit",
        "trial_account_baseline",
        "trial_request_diagnostics",
        "live_positions",
        "live_intents",
        "live_control",
    }
    if table not in allowed:
        raise ValueError("Unrecognized recovery table")
    if (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is None
    ):
        return []
    return [dict(row) for row in connection.execute(f"SELECT * FROM {table}")]


def _metadata(
    connection: sqlite3.Connection, expected: RecoveryIdentity, now: datetime
) -> dict[str, Any]:
    tables: dict[str, Any] = {
        name: _rows(connection, name)
        for name in (
            "signal_trial",
            "trial_intents",
            "trial_fills",
            "trial_order_audit",
            "trial_account_baseline",
            "trial_request_diagnostics",
        )
    }
    if (
        len(tables["signal_trial"]) != 1
        or len(tables["trial_intents"]) != 1
        or len(tables["trial_account_baseline"]) != 1
        or tables["trial_fills"]
    ):
        raise RuntimeError("Recovery requires one empty-fill trial and one immutable baseline")
    trial = tables["signal_trial"][0]
    intent = tables["trial_intents"][0]
    baseline = tables["trial_account_baseline"][0]
    strategy = json.loads(trial["strategy_json"])
    if not isinstance(strategy, dict) or strategy.get("version") != expected.strategy_version:
        raise RuntimeError("Frozen strategy does not match recovery identity")
    if (
        trial["state"] != "ENTRY_PENDING"
        or trial["reason"] != "ORDER_UNKNOWN"
        or trial["buy_id"] != intent["intent_id"]
        or trial["sell_id"] is not None
        or trial["symbol"] != intent["symbol"]
        or trial["account"] != expected.account_fingerprint
        or intent["account"] != expected.account_fingerprint
        or baseline["account"] != expected.account_fingerprint
        or intent["strategy"] != expected.strategy_version
        or trial["application_version"] != expected.application_version
        or trial["execution_source_sha256"] != expected.execution_source_sha256
        or trial["allocator_version"] != expected.allocator_version
        or intent["state"] != "UNKNOWN"
        or intent["side"] != "BUY"
        or intent["order_id"] is not None
        or intent["exchange_state"] is not None
        or _decimal(intent["executed_quantity"]) != 0
        or _decimal(intent["cumulative_quote"]) != 0
        or _decimal(intent["quote_budget"]) != 50
        or _decimal(intent["base_quantity"]) != 0
        or _decimal(trial["residual_quantity"]) != 0
        or (trial["owned_quantity"] is not None and _decimal(trial["owned_quantity"]) != 0)
    ):
        raise RuntimeError("Trial is not an unacknowledged empty UNKNOWN BUY of this identity")
    submitted = [
        row
        for row in tables["trial_order_audit"]
        if (row["intent_id"] == intent["intent_id"] and row["action"] == "SUBMITTING")
    ]
    if len(submitted) != 1:
        raise RuntimeError("Exactly one original submission claim is required")
    submitted_at = _utc(datetime.fromisoformat(submitted[0]["at_utc"]))
    baseline_at = _utc(datetime.fromisoformat(baseline["observed_at"]))
    armed_at = _utc(datetime.fromisoformat(trial["armed_at"]))
    reconstructed = TrialIntent(
        intent["intent_id"],
        intent["account"],
        intent["symbol"],
        intent["side"],
        intent["strategy"],
        _decimal(intent["reference"]),
        _decimal(intent["quote_budget"]),
        _decimal(intent["base_quantity"]),
    )
    if (
        reconstructed.client_order_id != intent["client_id"]
        or intent["intent_id"] != trial["trial_id"] + "-entry"
        or not baseline_at <= armed_at <= submitted_at <= now
        or trial["completed_at"] is not None
    ):
        raise RuntimeError("Original client identity or trial chronology is inconsistent")
    if not timedelta(hours=1) <= now - submitted_at <= timedelta(days=30):
        raise RuntimeError("Submission must be at least one hour old and within retained history")
    if _rows(connection, "live_positions"):
        raise RuntimeError("Owned Live positions block missing-trial recovery")
    if any(row["state"] not in _FINAL for row in _rows(connection, "live_intents")):
        raise RuntimeError("Another unresolved Live intent blocks recovery")
    if any(row.get("entries_enabled", 0) != 0 for row in _rows(connection, "live_control")):
        raise RuntimeError("Live entries must remain disabled during recovery")
    tables["submitted_at"] = submitted_at.isoformat()
    return tables


def _history(
    transport: ReadOnlyRecoveryTransport,
    path: str,
    symbol: str,
    start_ms: int,
    end_ms: int,
) -> dict[str, Any]:
    """Exhaust bounded time partitions; full pages subdivide without skipping ties.

    Binance myTrades forbids fromId+startTime/endTime, so paginate time ranges
    instead. A saturated single millisecond cannot be proven complete and fails.
    """
    pending = [
        (start, min(start + 86_400_000 - 1, end_ms))
        for start in range(start_ms, end_ms + 1, 86_400_000)
    ]
    windows: list[dict[str, int]] = []
    rows: dict[int, dict[str, Any]] = {}
    requests = 0
    while pending:
        start, end = pending.pop(0)
        requests += 1
        if requests > 512:
            raise RuntimeError("Recovery history pagination exceeded its proof bound")
        page = transport.request(
            "GET",
            path,
            {
                "symbol": symbol,
                "startTime": str(start),
                "endTime": str(end),
                "limit": "1000",
            },
        )
        if not isinstance(page, list) or len(page) > 1000:
            raise ValueError("Incomplete or malformed recovery history")
        key = "id" if path.endswith("myTrades") else "orderId"
        for row in page:
            if (
                not isinstance(row, dict)
                or row.get("symbol") != symbol
                or type(row.get(key)) is not int
                or row[key] < 0
                or type(row.get("time")) is not int
                or not start <= row["time"] <= end
            ):
                raise ValueError("History identity or time range is invalid")
            if row[key] in rows and rows[row[key]] != row:
                raise ValueError("Conflicting recovery history identity")
            rows[row[key]] = row
        if len(page) == 1000:
            if start == end:
                raise RuntimeError("Saturated single-millisecond history is not complete")
            midpoint = (start + end) // 2
            pending[0:0] = [(start, midpoint), (midpoint + 1, end)]
        else:
            windows.append({"start_ms": start, "end_ms": end, "count": len(page)})
    return {
        "start_ms": start_ms,
        "end_ms": end_ms,
        "requests": requests,
        "complete_windows": windows,
        "rows": list(rows.values()),
    }


def _balances(transport: ReadOnlyRecoveryTransport) -> dict[str, str]:
    payload = transport.request("GET", "/api/v3/account", {"omitZeroBalances": "false"})
    if not isinstance(payload, dict) or not isinstance(payload.get("balances"), list):
        raise ValueError("Incomplete full account response")
    balances = {}
    seen = set()
    for row in payload["balances"]:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("asset"), str)
            or not row["asset"].isalnum()
            or row["asset"] in seen
        ):
            raise ValueError("Malformed account balance identity")
        seen.add(row["asset"])
        free, locked = _decimal(row.get("free")), _decimal(row.get("locked"))
        if locked != 0:
            raise RuntimeError("Locked balance blocks recovery")
        if free != 0:
            balances[row["asset"]] = str(free)
    return balances


def recover_missing_trial_order(
    journal: OrderJournal,
    transport: SpotTransport,
    *,
    expected_identity: RecoveryIdentity,
    credential_fingerprint: str,
    current_source_sha256: str,
    source_is_current: Callable[[], bool],
    runtime_stopped: Callable[[], bool],
    operator_authorized: bool,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """One explicit local recovery transaction, only while installer owns runtime.

    runtime_stopped/source_is_current are trusted installer checks, never UI flags.
    This does not arm another test or enable normal Live. All evidence stays local.
    """
    if (
        operator_authorized is not True
        or runtime_stopped() is not True
        or source_is_current() is not True
        or not credential_fingerprint
        or credential_fingerprint != expected_identity.account_fingerprint
        or any(
            len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest)
            for digest in (current_source_sha256, expected_identity.execution_source_sha256)
        )
    ):
        raise RuntimeError(
            "Explicit owner authorization and frozen stopped-source identity required"
        )
    readonly = ReadOnlyRecoveryTransport(transport, runtime_stopped)
    with journal._connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        original = _metadata(connection, expected_identity, _utc(clock()))
        intent = original["trial_intents"][0]
        trial = original["signal_trial"][0]
        baseline_raw = json.loads(original["trial_account_baseline"][0]["balances_json"])
        if not isinstance(baseline_raw, dict):
            raise ValueError("Malformed immutable baseline")
        baseline = {
            asset: str(_decimal(value))
            for asset, value in baseline_raw.items()
            if _decimal(value) != 0
        }
        observations = []
        last_observed: float | None = None
        for _ in range(3):
            if last_observed is not None:
                sleep(max(0, 1 - (monotonic() - last_observed)))
                if monotonic() - last_observed < 1:
                    raise RuntimeError("Recovery observations were not separated")
            before = _utc(clock())
            begin = monotonic()
            server = readonly.request("GET", "/api/v3/time", {})
            after = _utc(clock())
            if (
                not isinstance(server, dict)
                or type(server.get("serverTime")) is not int
                or not 0 <= (after - before).total_seconds() <= 2
                or abs(server["serverTime"] - (before.timestamp() + after.timestamp()) * 500) > 1000
            ):
                raise RuntimeError("Recovery requires a fresh trusted Binance clock")
            try:
                readonly.request(
                    "GET",
                    "/api/v3/order",
                    {
                        "symbol": intent["symbol"],
                        "origClientOrderId": intent["client_id"],
                    },
                )
            except ExchangeRequestError as error:
                if error.code != -2013 or error.http_status != 400:
                    raise RuntimeError(
                        "Original order query was not an exact missing-order result"
                    ) from None
            else:
                raise RuntimeError("An exchange order exists; normal reconciliation is required")
            start = int(
                (
                    datetime.fromisoformat(original["submitted_at"]) - timedelta(minutes=5)
                ).timestamp()
                * 1000
            )
            end = server["serverTime"]
            histories = {
                path: _history(readonly, path, intent["symbol"], start, end)
                for path in ("/api/v3/allOrders", "/api/v3/myTrades")
            }
            if any(history["rows"] for history in histories.values()):
                raise RuntimeError(
                    "Order/trade activity in submission window requires manual investigation"
                )
            first = _balances(readonly)
            orders = readonly.request("GET", "/api/v3/openOrders", {})
            second = _balances(readonly)
            if (
                orders != []
                or first != second
                or {asset: Decimal(value) for asset, value in first.items()}
                != {asset: Decimal(value) for asset, value in baseline.items()}
            ):
                raise RuntimeError(
                    "Stable complete account does not exactly match immutable baseline"
                )
            if not 0 <= monotonic() - begin <= 15:
                raise RuntimeError("Recovery account observation became stale")
            observations.append(
                {
                    "observed_at": before.isoformat(),
                    "serverTime": end,
                    "order_query_code": -2013,
                    "histories": histories,
                    "balances": second,
                    "open_orders": [],
                }
            )
            last_observed = monotonic()
        if runtime_stopped() is not True or source_is_current() is not True:
            raise RuntimeError("Exclusive runtime or source changed during recovery")
        if _metadata(connection, expected_identity, _utc(clock())) != original:
            raise RuntimeError("Original recovery metadata changed")
        evidence = {
            "resolution": _RESOLUTION,
            "exchange_state": None,
            "trial_state": "FAILED",
            "certificate_issued": False,
            "operator_authorized": True,
            "identity": asdict(expected_identity),
            "current_source_sha256": current_source_sha256,
            "original": original,
            "terminal_trial": {
                **trial,
                "state": "FAILED",
                "reason": _RESOLUTION,
                "entries_enabled": 0,
                "completed_at": None,
            },
            "observations": observations,
        }
        digest = hashlib.sha256(_json(evidence).encode()).hexdigest()
        archived_at = _utc(clock()).isoformat()
        connection.execute(
            "CREATE TABLE IF NOT EXISTS trial_archives (trial_id TEXT PRIMARY KEY, "
            "archived_at TEXT NOT NULL,payload_json TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS trial_recovery_tombstones ("
            "intent_id TEXT PRIMARY KEY,client_id TEXT UNIQUE NOT NULL,"
            "trial_id TEXT UNIQUE NOT NULL,evidence_sha256 TEXT NOT NULL,"
            "resolution TEXT NOT NULL,at_utc TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TRIGGER IF NOT EXISTS prevent_recovered_trial_intent "
            "BEFORE INSERT ON trial_intents WHEN EXISTS (SELECT 1 FROM "
            "trial_recovery_tombstones WHERE intent_id=NEW.intent_id "
            "OR client_id=NEW.client_id) BEGIN SELECT "
            "RAISE(ABORT,'Archived recovery identity cannot be reused'); END"
        )
        connection.execute(
            "INSERT INTO trial_archives VALUES(?,?,?)",
            (
                trial["trial_id"],
                archived_at,
                _json({"evidence": evidence, "evidence_sha256": digest}),
            ),
        )
        connection.execute(
            "INSERT INTO trial_recovery_tombstones VALUES(?,?,?,?,?,?)",
            (
                intent["intent_id"],
                intent["client_id"],
                trial["trial_id"],
                digest,
                _RESOLUTION,
                archived_at,
            ),
        )
        connection.execute(
            "DELETE FROM trial_request_diagnostics WHERE intent_id=?", (intent["intent_id"],)
        )
        connection.execute("DELETE FROM trial_intents WHERE intent_id=?", (intent["intent_id"],))
        connection.execute("DELETE FROM signal_trial WHERE singleton=1")
        connection.execute("DELETE FROM trial_account_baseline WHERE singleton=1")
        journal._audit(connection, intent["intent_id"], _RESOLUTION)
        return {
            "trial_id": trial["trial_id"],
            "intent_id": intent["intent_id"],
            "trial_state": "FAILED",
            "resolution": _RESOLUTION,
            "evidence_sha256": digest,
            "certificate_issued": False,
        }
