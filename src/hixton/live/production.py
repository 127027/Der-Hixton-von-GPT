"""Persistent fail-closed Binance Spot runtime for the owner-approved 3x80 portfolio.

This module never stores credentials and never enables itself. The local authenticated
UI must explicitly arm the first 1x50 trial and, after that round-trip is reconciled,
explicitly enable continuous 3x80. All order identities are persisted before dispatch;
ambiguous submissions are queried and are never blindly re-sent.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal
from pathlib import Path
from threading import Event, RLock
from typing import Any

from hixton.backtest.models import ExecutionRules
from hixton.constants import SYMBOLS
from hixton.domain.allocation import allocate_entry_slots
from hixton.domain.models import IndicatorPoint, SignalAction
from hixton.domain.strategy import entry_priority
from hixton.domain.trade_policy import TradePolicyGate
from hixton.domain.versions import StrategyDefinition
from hixton.live.orders import ExchangeOrder, OrderExchange

ZERO = Decimal("0")
SLOT_NOTIONAL = Decimal("80")
MAX_SLOTS = 3
CASH_RESERVE = Decimal("10")
FINAL_ORDER = {"FILLED", "CANCELED", "REJECTED", "EXPIRED", "EXPIRED_IN_MATCH"}


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timezone-aware time required")
    return value.astimezone(UTC)


def _round_down(value: Decimal, step: Decimal) -> Decimal:
    if step <= ZERO:
        return value
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


@dataclass(frozen=True, slots=True)
class LiveIntent:
    intent_id: str
    account_fingerprint: str
    symbol: str
    side: str
    strategy_version: str
    reference_price: Decimal
    slot_count: int
    quote_budget: Decimal = ZERO
    base_quantity: Decimal = ZERO

    def __post_init__(self) -> None:
        if (
            not self.intent_id
            or len(self.intent_id) > 128
            or not self.account_fingerprint
            or self.symbol not in SYMBOLS
            or self.side not in {"BUY", "SELL"}
            or not self.strategy_version
            or type(self.slot_count) is not int
            or not 1 <= self.slot_count <= MAX_SLOTS
        ):
            raise ValueError("invalid Live order identity")
        for amount, positive in (
            (self.reference_price, True),
            (self.quote_budget, False),
            (self.base_quantity, False),
        ):
            if not amount.is_finite() or amount < 0 or (positive and amount == 0):
                raise ValueError("Live order amounts must be finite and non-negative")
        if self.side == "BUY":
            if self.quote_budget != SLOT_NOTIONAL * self.slot_count or self.base_quantity != ZERO:
                raise ValueError("Live BUY budget must be exactly 80 USDC per allocated slot")
        elif self.quote_budget != ZERO or self.base_quantity <= ZERO:
            raise ValueError("Live SELL requires explicit owned base quantity")

    @property
    def client_order_id(self) -> str:
        digest = hashlib.sha256(
            f"HIXTON-LIVE|{self.account_fingerprint}|{self.intent_id}".encode()
        ).hexdigest()
        return "hxlive_" + digest[:29]


class LiveOrderJournal:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS live_intents (
                    intent_id TEXT PRIMARY KEY,
                    client_id TEXT UNIQUE NOT NULL,
                    account TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    reference TEXT NOT NULL,
                    slot_count INTEGER NOT NULL CHECK(slot_count BETWEEN 1 AND 3),
                    quote_budget TEXT NOT NULL,
                    base_quantity TEXT NOT NULL,
                    state TEXT NOT NULL,
                    order_id TEXT,
                    exchange_state TEXT,
                    executed_quantity TEXT NOT NULL DEFAULT '0',
                    cumulative_quote TEXT NOT NULL DEFAULT '0',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS live_fills (
                    account TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    trade_id TEXT NOT NULL,
                    intent_id TEXT NOT NULL REFERENCES live_intents(intent_id),
                    quantity TEXT NOT NULL,
                    price TEXT NOT NULL,
                    commission TEXT NOT NULL,
                    commission_asset TEXT NOT NULL,
                    quote_quantity TEXT NOT NULL,
                    PRIMARY KEY(account, symbol, trade_id)
                );
                CREATE TABLE IF NOT EXISTS live_order_audit (
                    id INTEGER PRIMARY KEY,
                    intent_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    at_utc TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    @staticmethod
    def _audit(connection: sqlite3.Connection, intent_id: str, action: str) -> None:
        connection.execute(
            "INSERT INTO live_order_audit(intent_id,action,at_utc) VALUES(?,?,?)",
            (intent_id, action, datetime.now(UTC).isoformat()),
        )

    def create(self, intent: LiveIntent) -> bool:
        values = (
            intent.intent_id,
            intent.client_order_id,
            intent.account_fingerprint,
            intent.symbol,
            intent.side,
            intent.strategy_version,
            str(intent.reference_price),
            intent.slot_count,
            str(intent.quote_budget),
            str(intent.base_quantity),
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM live_intents WHERE intent_id=?", (intent.intent_id,)
            ).fetchone()
            if existing is not None:
                expected = (
                    existing["intent_id"],
                    existing["client_id"],
                    existing["account"],
                    existing["symbol"],
                    existing["side"],
                    existing["strategy"],
                    existing["reference"],
                    int(existing["slot_count"]),
                    existing["quote_budget"],
                    existing["base_quantity"],
                )
                if expected != values:
                    raise RuntimeError("Live intent identity cannot change")
                return False
            connection.execute(
                "INSERT INTO live_intents("
                "intent_id,client_id,account,symbol,side,strategy,reference,slot_count,"
                "quote_budget,base_quantity,state,updated_at"
                ") VALUES(?,?,?,?,?,?,?,?,?,?,'CREATED',?)",
                (*values, datetime.now(UTC).isoformat()),
            )
            self._audit(connection, intent.intent_id, "INTENT_CREATED")
            return True

    def load(self, intent_id: str) -> tuple[LiveIntent, str]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM live_intents WHERE intent_id=?", (intent_id,)
            ).fetchone()
        if row is None:
            raise KeyError("unknown Live intent")
        return (
            LiveIntent(
                row["intent_id"],
                row["account"],
                row["symbol"],
                row["side"],
                row["strategy"],
                Decimal(row["reference"]),
                int(row["slot_count"]),
                Decimal(row["quote_budget"]),
                Decimal(row["base_quantity"]),
            ),
            str(row["state"]),
        )

    def claim_submit(self, intent_id: str) -> bool:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute(
                "UPDATE live_intents SET state='SUBMITTING',updated_at=? "
                "WHERE intent_id=? AND state='CREATED'",
                (datetime.now(UTC).isoformat(), intent_id),
            ).rowcount
            if changed:
                self._audit(connection, intent_id, "SUBMITTING")
            return changed == 1

    def abandon_created(self, intent_id: str, reason: str) -> bool:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute(
                "UPDATE live_intents SET state='CANCELED',updated_at=? "
                "WHERE intent_id=? AND state='CREATED'",
                (datetime.now(UTC).isoformat(), intent_id),
            ).rowcount
            if changed:
                self._audit(connection, intent_id, "LOCAL_CANCEL_" + reason)
            return changed == 1

    def unknown(self, intent_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE live_intents SET state='UNKNOWN',updated_at=? WHERE intent_id=? "
                "AND state NOT IN ('CREATED','FILLED','CANCELED','REJECTED','EXPIRED',"
                "'EXPIRED_IN_MATCH')",
                (datetime.now(UTC).isoformat(), intent_id),
            )
            self._audit(connection, intent_id, "RECONCILIATION_REQUIRED")

    def record(self, intent: LiveIntent, order: ExchangeOrder) -> None:
        if (
            order.client_order_id != intent.client_order_id
            or order.symbol != intent.symbol
            or order.side != intent.side
        ):
            raise RuntimeError("exchange response identity mismatch")
        if intent.side == "BUY" and order.cumulative_quote > intent.quote_budget:
            raise RuntimeError("exchange BUY exceeds persisted Live budget")
        if intent.side == "SELL" and order.executed_quantity > intent.base_quantity:
            raise RuntimeError("exchange SELL exceeds persisted owned quantity")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            old = connection.execute(
                "SELECT * FROM live_intents WHERE intent_id=?", (intent.intent_id,)
            ).fetchone()
            if old is None or old["state"] == "CREATED":
                raise RuntimeError("unsubmitted Live intent cannot receive fills")
            if (
                old["client_id"] != intent.client_order_id
                or old["account"] != intent.account_fingerprint
                or old["symbol"] != intent.symbol
                or old["side"] != intent.side
                or old["strategy"] != intent.strategy_version
                or Decimal(old["reference"]) != intent.reference_price
                or int(old["slot_count"]) != intent.slot_count
                or Decimal(old["quote_budget"]) != intent.quote_budget
                or Decimal(old["base_quantity"]) != intent.base_quantity
            ):
                raise RuntimeError("persisted Live intent changed")
            if old["order_id"] and old["order_id"] != order.order_id:
                raise RuntimeError("exchange order identity changed")
            if Decimal(old["executed_quantity"]) > order.executed_quantity:
                raise RuntimeError("executed quantity regressed")
            if Decimal(old["cumulative_quote"]) > order.cumulative_quote:
                raise RuntimeError("cumulative quote regressed")
            if old["exchange_state"] in FINAL_ORDER and (
                old["exchange_state"] != order.state
                or Decimal(old["executed_quantity"]) != order.executed_quantity
                or Decimal(old["cumulative_quote"]) != order.cumulative_quote
            ):
                raise RuntimeError("terminal exchange state changed")
            for fill in order.fills:
                values = (
                    intent.account_fingerprint,
                    intent.symbol,
                    fill.trade_id,
                    intent.intent_id,
                    str(fill.quantity),
                    str(fill.price),
                    str(fill.commission),
                    fill.commission_asset,
                    str(fill.quote),
                )
                existing = connection.execute(
                    "SELECT * FROM live_fills WHERE account=? AND symbol=? AND trade_id=?",
                    values[:3],
                ).fetchone()
                if existing is not None and tuple(existing) != values:
                    raise RuntimeError("conflicting duplicate Live fill")
                connection.execute(
                    "INSERT OR IGNORE INTO live_fills VALUES(?,?,?,?,?,?,?,?,?)", values
                )
            fills = connection.execute(
                "SELECT * FROM live_fills WHERE intent_id=?", (intent.intent_id,)
            ).fetchall()
            booked_quantity = sum((Decimal(row["quantity"]) for row in fills), ZERO)
            booked_quote = sum((Decimal(row["quote_quantity"]) for row in fills), ZERO)
            if booked_quantity > order.executed_quantity or booked_quote > order.cumulative_quote:
                raise RuntimeError("Live fills exceed exchange totals")
            complete = (
                booked_quantity == order.executed_quantity
                and booked_quote == order.cumulative_quote
            )
            state = order.state if complete else "FILL_DETAILS_PENDING"
            connection.execute(
                "UPDATE live_intents SET state=?,exchange_state=?,order_id=?,"
                "executed_quantity=?,cumulative_quote=?,updated_at=? WHERE intent_id=?",
                (
                    state,
                    order.state,
                    order.order_id,
                    str(order.executed_quantity),
                    str(order.cumulative_quote),
                    datetime.now(UTC).isoformat(),
                    intent.intent_id,
                ),
            )
            self._audit(connection, intent.intent_id, state)

    def fill_summary(self, intent_id: str) -> dict[str, object]:
        intent, state = self.load(intent_id)
        with self._connect() as connection:
            order = connection.execute(
                "SELECT order_id,exchange_state,updated_at FROM live_intents WHERE intent_id=?",
                (intent_id,),
            ).fetchone()
            fills = connection.execute(
                "SELECT * FROM live_fills WHERE intent_id=? ORDER BY CAST(trade_id AS INTEGER)",
                (intent_id,),
            ).fetchall()
        quantity = sum((Decimal(row["quantity"]) for row in fills), ZERO)
        quote = sum((Decimal(row["quote_quantity"]) for row in fills), ZERO)
        fees: dict[str, Decimal] = {}
        for row in fills:
            asset = str(row["commission_asset"])
            fees[asset] = fees.get(asset, ZERO) + Decimal(row["commission"])
        base = intent.symbol.removesuffix("USDC")
        net_received = quantity - fees.get(base, ZERO) if intent.side == "BUY" else ZERO
        return {
            "intent_id": intent_id,
            "state": state,
            "exchange_state": order["exchange_state"],
            "exchange_order_id": order["order_id"],
            "recorded_at_utc": order["updated_at"],
            "slot_count": intent.slot_count,
            "gross_quantity": str(quantity),
            "gross_quote": str(quote),
            "net_received_base": str(net_received),
            "fees_by_asset": {key: str(value) for key, value in fees.items()},
            "fill_count": len(fills),
        }

    def unresolved_ids(self, *, ignore: str | None = None) -> tuple[str, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT intent_id FROM live_intents "
                "WHERE state NOT IN ('FILLED','CANCELED','REJECTED','EXPIRED','EXPIRED_IN_MATCH')"
            ).fetchall()
        return tuple(row["intent_id"] for row in rows if row["intent_id"] != ignore)

    def fill_movements(self) -> tuple[sqlite3.Row, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT f.*,i.side FROM live_fills f JOIN live_intents i USING(intent_id)"
            ).fetchall()
        return tuple(rows)


class LiveOrderExecutor:
    def __init__(
        self,
        journal: LiveOrderJournal,
        exchange: OrderExchange,
        pre_submit: Callable[[LiveIntent], bool],
    ) -> None:
        self.journal = journal
        self.exchange = exchange
        self.pre_submit = pre_submit

    def execute(self, intent_id: str) -> str:
        intent, state = self.journal.load(intent_id)
        if state != "CREATED":
            return self.reconcile(intent_id)
        if not self.pre_submit(intent):
            return "BLOCKED"
        if not self.journal.claim_submit(intent_id):
            return self.reconcile(intent_id)
        try:
            self.journal.record(intent, self.exchange.submit(intent))
        except Exception:
            self.journal.unknown(intent_id)
        return self.journal.load(intent_id)[1]

    def reconcile(self, intent_id: str) -> str:
        intent, state = self.journal.load(intent_id)
        if state == "CREATED" or state in FINAL_ORDER:
            return state
        try:
            order = self.exchange.query(intent)
            if order is None:
                self.journal.unknown(intent_id)
            else:
                self.journal.record(intent, order)
        except Exception:
            self.journal.unknown(intent_id)
        return self.journal.load(intent_id)[1]


@dataclass(frozen=True, slots=True)
class LiveAccountSnapshot:
    account: str
    observed_at: datetime
    balances: dict[str, tuple[Decimal, Decimal]]
    open_orders: tuple[str, ...]

    def validate(self, now: datetime) -> None:
        if self.observed_at.tzinfo is None or not self.account:
            raise ValueError("invalid account snapshot")
        age = (now.astimezone(UTC) - self.observed_at.astimezone(UTC)).total_seconds()
        if not 0 <= age <= 15:
            raise ValueError("account snapshot expired")
        for asset, values in self.balances.items():
            if not asset or any(not amount.is_finite() or amount < ZERO for amount in values):
                raise ValueError("invalid account balance")


class LiveBalanceReconciler:
    def __init__(self, journal: LiveOrderJournal) -> None:
        self.journal = journal
        with journal._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS live_account_baseline("
                "singleton INTEGER PRIMARY KEY CHECK(singleton=1),account TEXT NOT NULL,"
                "observed_at TEXT NOT NULL,balances_json TEXT NOT NULL)"
            )

    def has_baseline(self) -> bool:
        with self.journal._connect() as connection:
            return connection.execute(
                "SELECT 1 FROM live_account_baseline WHERE singleton=1"
            ).fetchone() is not None

    def capture(self, snapshot: LiveAccountSnapshot, *, now: datetime) -> None:
        snapshot.validate(now)
        if snapshot.open_orders or any(locked != ZERO for _, locked in snapshot.balances.values()):
            raise ValueError("Live baseline requires no open orders or locked balances")
        foreign = [
            asset
            for asset, (free, locked) in snapshot.balances.items()
            if asset not in {"USDC", "BNB"} and free + locked > ZERO
        ]
        if foreign:
            raise ValueError("Live baseline requires a dedicated account without foreign holdings")
        encoded = json.dumps(
            {asset: str(free) for asset, (free, _) in snapshot.balances.items()},
            sort_keys=True,
        )
        with self.journal._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT account,balances_json FROM live_account_baseline WHERE singleton=1"
            ).fetchone()
            if existing is not None:
                if existing["account"] != snapshot.account:
                    raise RuntimeError("Live account identity changed")
                return
            if connection.execute("SELECT 1 FROM live_intents LIMIT 1").fetchone():
                raise RuntimeError("cannot capture Live baseline after order history exists")
            connection.execute(
                "INSERT INTO live_account_baseline VALUES(1,?,?,?)",
                (snapshot.account, snapshot.observed_at.isoformat(), encoded),
            )

    def check(
        self,
        snapshot: LiveAccountSnapshot,
        *,
        now: datetime,
        ignore_intent_id: str | None = None,
    ) -> dict[str, object]:
        snapshot.validate(now)
        with self.journal._connect() as connection:
            baseline = connection.execute(
                "SELECT * FROM live_account_baseline WHERE singleton=1"
            ).fetchone()
        if baseline is None:
            raise RuntimeError("Live baseline missing")
        if baseline["account"] != snapshot.account:
            raise RuntimeError("Live account identity mismatch")
        expected = {
            asset: Decimal(value) for asset, value in json.loads(baseline["balances_json"]).items()
        }
        for fill in self.journal.fill_movements():
            symbol = str(fill["symbol"])
            base = symbol.removesuffix("USDC")
            sign = Decimal(1) if fill["side"] == "BUY" else Decimal(-1)
            quantity = Decimal(fill["quantity"])
            quote = Decimal(fill["quote_quantity"])
            fee = Decimal(fill["commission"])
            expected[base] = expected.get(base, ZERO) + sign * quantity
            expected["USDC"] = expected.get("USDC", ZERO) - sign * quote
            fee_asset = str(fill["commission_asset"])
            expected[fee_asset] = expected.get(fee_asset, ZERO) - fee
        mismatches = [
            asset
            for asset in sorted(expected.keys() | snapshot.balances.keys())
            if expected.get(asset, ZERO) != sum(snapshot.balances.get(asset, (ZERO, ZERO)))
        ]
        unresolved = self.journal.unresolved_ids(ignore=ignore_intent_id)
        locked = any(value != ZERO for _, value in snapshot.balances.values())
        return {
            "balances_match": not mismatches,
            "no_open_orders": not snapshot.open_orders,
            "no_locked_balances": not locked,
            "mismatched_assets": mismatches,
            "unresolved_intents": list(unresolved),
            "passed": not mismatches and not snapshot.open_orders and not locked and not unresolved,
        }


class LivePortfolioController:
    def __init__(
        self,
        database: Path,
        journal: LiveOrderJournal,
        executor: LiveOrderExecutor,
        reconciler: LiveBalanceReconciler,
        snapshot: Callable[[], LiveAccountSnapshot],
        settings: Callable[[], tuple[int, Decimal, bool]],
        rules: Callable[[], Mapping[str, ExecutionRules]],
        strategy: StrategyDefinition,
        release_check: Callable[[], bool],
    ) -> None:
        self.database = database
        self.journal = journal
        self.executor = executor
        self.reconciler = reconciler
        self.snapshot = snapshot
        self.settings = settings
        self.rules = rules
        self.strategy = strategy
        self.release_check = release_check
        self.lock = RLock()
        with journal._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS live_control(
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    account TEXT NOT NULL,
                    strategy_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    entries_enabled INTEGER NOT NULL,
                    enabled_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    day_start_date TEXT NOT NULL,
                    day_start_equity TEXT NOT NULL,
                    reason TEXT
                );
                CREATE TABLE IF NOT EXISTS live_checkpoints(
                    symbol TEXT PRIMARY KEY,
                    last_close_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS live_positions(
                    symbol TEXT PRIMARY KEY,
                    quantity TEXT NOT NULL,
                    average_price TEXT NOT NULL,
                    cost_basis_quote TEXT NOT NULL,
                    entry_time_utc TEXT NOT NULL,
                    entry_signal_id TEXT NOT NULL,
                    entry_atr TEXT NOT NULL,
                    highest_close TEXT NOT NULL,
                    slot_count INTEGER NOT NULL CHECK(slot_count BETWEEN 1 AND 3)
                );
                CREATE TABLE IF NOT EXISTS live_events(
                    signal_id TEXT PRIMARY KEY,
                    occurred_at_utc TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT,
                    intent_id TEXT UNIQUE,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS live_dust(
                    symbol TEXT PRIMARY KEY,
                    quantity TEXT NOT NULL
                );
                """
            )

    def _strategy_json(self) -> str:
        return json.dumps(self.strategy.config_payload(), sort_keys=True, allow_nan=False)

    def _control(self) -> sqlite3.Row | None:
        with self.journal._connect() as connection:
            return connection.execute("SELECT * FROM live_control WHERE singleton=1").fetchone()

    def _positions(self) -> dict[str, sqlite3.Row]:
        with self.journal._connect() as connection:
            rows = connection.execute("SELECT * FROM live_positions").fetchall()
        return {str(row["symbol"]): row for row in rows}

    def _checkpoints(self) -> dict[str, datetime]:
        with self.journal._connect() as connection:
            rows = connection.execute("SELECT * FROM live_checkpoints").fetchall()
        return {
            str(row["symbol"]): datetime.fromisoformat(row["last_close_utc"]).astimezone(UTC)
            for row in rows
        }

    def _event(self, signal_id: str) -> sqlite3.Row | None:
        with self.journal._connect() as connection:
            return connection.execute(
                "SELECT * FROM live_events WHERE signal_id=?", (signal_id,)
            ).fetchone()

    def _pending(self) -> sqlite3.Row | None:
        with self.journal._connect() as connection:
            return connection.execute(
                "SELECT * FROM live_events WHERE status IN ('ORDER_PENDING','RECONCILING') "
                "ORDER BY occurred_at_utc LIMIT 1"
            ).fetchone()

    def enable(
        self,
        account: str,
        points: Mapping[str, Sequence[IndicatorPoint]],
        snapshot: LiveAccountSnapshot,
        *,
        now: datetime,
    ) -> None:
        now = _utc(now)
        if not self.release_check():
            raise RuntimeError("Live release gate is closed")
        if set(points) != set(SYMBOLS) or any(not points[symbol] for symbol in SYMBOLS):
            raise RuntimeError("Live enable requires all ten synchronized markets")
        latest = {symbol: _utc(points[symbol][-1].candle.close_time_utc) for symbol in SYMBOLS}
        if len(set(latest.values())) != 1:
            raise RuntimeError("Live enable requires aligned closed bars")
        self.reconciler.capture(snapshot, now=now)
        with self.lock, self.journal._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM live_control WHERE singleton=1").fetchone()
            if row is None:
                free_usdc = sum(snapshot.balances.get("USDC", (ZERO, ZERO)))
                connection.execute(
                    "INSERT INTO live_control VALUES(1,?,?,?,?,?,?,?,?,?)",
                    (
                        account,
                        self._strategy_json(),
                        "LIVE_ENABLED",
                        1,
                        now.isoformat(),
                        now.isoformat(),
                        now.date().isoformat(),
                        str(free_usdc),
                        None,
                    ),
                )
                connection.executemany(
                    "INSERT INTO live_checkpoints(symbol,last_close_utc) VALUES(?,?)",
                    [(symbol, latest[symbol].isoformat()) for symbol in SYMBOLS],
                )
                return
            if row["account"] != account or row["strategy_json"] != self._strategy_json():
                raise RuntimeError("Live account/strategy cannot change in place")
            if row["state"] == "NEEDS_REVIEW":
                raise RuntimeError("Live ledger requires review before re-enable")
            proof = self.reconciler.check(snapshot, now=now)
            if proof["passed"] is not True:
                raise RuntimeError("Live account does not reconcile")
            connection.execute(
                "UPDATE live_control SET state='LIVE_ENABLED',entries_enabled=1,"
                "updated_at=?,reason=NULL WHERE singleton=1",
                (now.isoformat(),),
            )

    def disable_entries(self) -> None:
        with self.lock:
            pending = self._pending()
            if pending is not None and pending["action"] == "ENTER_LONG":
                try:
                    _intent, state = self.journal.load(str(pending["intent_id"]))
                except KeyError:
                    state = "CREATED"
                if state == "CREATED" and self.journal.abandon_created(
                    str(pending["intent_id"]), "ENTRIES_DISABLED"
                ):
                    with self.journal._connect() as connection:
                        connection.execute(
                            "UPDATE live_events SET status='BLOCKED',reason='ENTRIES_DISABLED' "
                            "WHERE signal_id=?",
                            (pending["signal_id"],),
                        )
            with self.journal._connect() as connection:
                positions = int(
                    connection.execute("SELECT COUNT(*) FROM live_positions").fetchone()[0]
                )
                unresolved = bool(self.journal.unresolved_ids())
                state = "EXIT_ONLY" if positions or unresolved else "LIVE_DISABLED"
                connection.execute(
                    "UPDATE live_control SET state=?,entries_enabled=0,updated_at=? "
                    "WHERE singleton=1",
                    (state, datetime.now(UTC).isoformat()),
                )

    def fail_closed(self, reason: str) -> None:
        with self.journal._connect() as connection:
            connection.execute(
                "UPDATE live_control SET state='NEEDS_REVIEW',entries_enabled=0,"
                "reason=?,updated_at=? WHERE singleton=1",
                (reason, datetime.now(UTC).isoformat()),
            )

    def pre_submit(self, intent: LiveIntent) -> bool:
        try:
            control = self._control()
            if (
                control is None
                or control["account"] != intent.account_fingerprint
                or control["strategy_json"] != self._strategy_json()
                or not self.release_check()
            ):
                return False
            slots, target, emergency = self.settings()
            if intent.side == "BUY":
                if (
                    control["state"] != "LIVE_ENABLED"
                    or not bool(control["entries_enabled"])
                    or emergency
                    or slots != MAX_SLOTS
                    or target != SLOT_NOTIONAL
                ):
                    return False
            elif control["state"] not in {"LIVE_ENABLED", "EXIT_ONLY"}:
                return False
            snapshot = self.snapshot()
            proof = self.reconciler.check(
                snapshot, now=datetime.now(UTC), ignore_intent_id=intent.intent_id
            )
            if proof["passed"] is not True:
                return False
            positions = self._positions()
            if intent.side == "BUY":
                used = sum(int(row["slot_count"]) for row in positions.values())
                free_usdc = sum(snapshot.balances.get("USDC", (ZERO, ZERO)))
                return (
                    intent.symbol not in positions
                    and used + intent.slot_count <= MAX_SLOTS
                    and free_usdc >= intent.quote_budget + CASH_RESERVE
                )
            position = positions.get(intent.symbol)
            if position is None or intent.base_quantity > Decimal(position["quantity"]):
                return False
            base = intent.symbol.removesuffix("USDC")
            free_base = snapshot.balances.get(base, (ZERO, ZERO))[0]
            return free_base >= intent.base_quantity
        except Exception:
            return False

    def _decision(
        self,
        series: Sequence[IndicatorPoint],
        point: IndicatorPoint,
        position: sqlite3.Row | None,
    ) -> Any:
        gate = TradePolicyGate(self.strategy.policy_for(point.symbol))
        index = next(
            (i for i, candidate in enumerate(series) if candidate.candle.close_time_utc == point.candle.close_time_utc),
            -1,
        )
        if index < 0:
            raise RuntimeError("Live decision point missing from history")
        for prior in series[max(0, index - 80) : index]:
            gate.decide(prior)
        if position is None:
            return gate.decide(point)
        return gate.decide(
            point,
            entry_price=float(Decimal(position["average_price"])),
            entry_atr=float(Decimal(position["entry_atr"])),
            highest_close=float(Decimal(position["highest_close"])),
        )

    def _next_group(
        self,
        points: Mapping[str, Sequence[IndicatorPoint]],
    ) -> tuple[datetime, dict[str, IndicatorPoint]] | None:
        checkpoints = self._checkpoints()
        if set(checkpoints) != set(SYMBOLS):
            raise RuntimeError("Live checkpoints incomplete")
        candidates: dict[str, IndicatorPoint] = {}
        for symbol in SYMBOLS:
            values = [
                point
                for point in points.get(symbol, ())
                if _utc(point.candle.close_time_utc) > checkpoints[symbol]
            ]
            if not values:
                return None
            candidates[symbol] = values[0]
        boundaries = {_utc(point.candle.close_time_utc) for point in candidates.values()}
        if len(boundaries) != 1:
            raise RuntimeError("Live closed bars are not aligned")
        boundary = boundaries.pop()
        return boundary, candidates

    def _reserve(
        self,
        signal: Any,
        point: IndicatorPoint,
        *,
        action: str,
        slot_count: int,
        quantity: Decimal = ZERO,
        reason: str | None = None,
    ) -> None:
        identity = "live-" + hashlib.sha256(
            f"{signal.signal_id}|{action}".encode()
        ).hexdigest()
        payload = {
            "reference_price": str(point.candle.close),
            "atr": str(signal.atr),
            "bar_close": _utc(point.candle.close_time_utc).isoformat(),
            "slot_count": slot_count,
            "base_quantity": str(quantity),
        }
        with self.journal._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT OR IGNORE INTO live_events("
                "signal_id,occurred_at_utc,symbol,action,status,reason,intent_id,payload_json"
                ") VALUES(?,?,?,?,?,?,?,?)",
                (
                    signal.signal_id,
                    _utc(point.candle.close_time_utc).isoformat(),
                    point.symbol,
                    action,
                    "ORDER_PENDING",
                    reason,
                    identity,
                    json.dumps(payload, sort_keys=True),
                ),
            )

    def _blocked(self, signal: Any, reason: str) -> None:
        with self.journal._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO live_events("
                "signal_id,occurred_at_utc,symbol,action,status,reason,intent_id,payload_json"
                ") VALUES(?,?,?,?,?,?,NULL,'{}')",
                (
                    signal.signal_id,
                    _utc(signal.candle_close_time_utc).isoformat(),
                    signal.symbol,
                    signal.action.value,
                    "BLOCKED",
                    reason,
                ),
            )

    def _drive_pending(self, pending: sqlite3.Row, *, now: datetime) -> None:
        payload = json.loads(str(pending["payload_json"]))
        action = str(pending["action"])
        buy = action == "ENTER_LONG"
        slot_count = int(payload["slot_count"])
        intent = LiveIntent(
            str(pending["intent_id"]),
            str(self._control()["account"]),
            str(pending["symbol"]),
            "BUY" if buy else "SELL",
            self.strategy.version,
            Decimal(payload["reference_price"]),
            slot_count,
            quote_budget=SLOT_NOTIONAL * slot_count if buy else ZERO,
            base_quantity=ZERO if buy else Decimal(payload["base_quantity"]),
        )
        self.journal.create(intent)
        _loaded, state = self.journal.load(intent.intent_id)
        if buy and state == "CREATED":
            age = (now - datetime.fromisoformat(str(payload["bar_close"]))).total_seconds()
            if not 0 <= age <= 90:
                self.journal.abandon_created(intent.intent_id, "ENTRY_EXPIRED")
                with self.journal._connect() as connection:
                    connection.execute(
                        "UPDATE live_events SET status='BLOCKED',reason='ENTRY_EXPIRED' "
                        "WHERE signal_id=?",
                        (pending["signal_id"],),
                    )
                return
        state = self.executor.execute(intent.intent_id)
        if state == "BLOCKED" or state not in FINAL_ORDER:
            return
        summary = self.journal.fill_summary(intent.intent_id)
        if int(summary["fill_count"]) == 0:
            with self.journal._connect() as connection:
                connection.execute(
                    "UPDATE live_events SET status='BLOCKED',reason=? WHERE signal_id=?",
                    ("ORDER_" + state, pending["signal_id"]),
                )
            if not buy:
                self.fail_closed("EXIT_ORDER_" + state)
            return
        proof = self.reconciler.check(self.snapshot(), now=datetime.now(UTC))
        if proof["passed"] is not True:
            with self.journal._connect() as connection:
                connection.execute(
                    "UPDATE live_events SET status='RECONCILING' WHERE signal_id=?",
                    (pending["signal_id"],),
                )
            return
        if buy:
            self._apply_buy(pending, summary)
        else:
            self._apply_sell(pending, summary)

    def _apply_buy(self, pending: sqlite3.Row, summary: Mapping[str, object]) -> None:
        payload = json.loads(str(pending["payload_json"]))
        quantity = Decimal(str(summary["net_received_base"]))
        gross_quantity = Decimal(str(summary["gross_quantity"]))
        gross_quote = Decimal(str(summary["gross_quote"]))
        if quantity <= ZERO or gross_quantity <= ZERO:
            self.fail_closed("ENTRY_FILL_INVALID")
            return
        fees = summary["fees_by_asset"]
        if not isinstance(fees, dict):
            self.fail_closed("ENTRY_FEES_INVALID")
            return
        quote_fee = Decimal(str(fees.get("USDC", "0")))
        average = gross_quote / gross_quantity
        with self.journal._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute(
                "SELECT 1 FROM live_positions WHERE symbol=?", (pending["symbol"],)
            ).fetchone():
                raise RuntimeError("Live BUY would overwrite an existing position")
            connection.execute(
                "INSERT INTO live_positions VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    pending["symbol"],
                    str(quantity),
                    str(average),
                    str(gross_quote + quote_fee),
                    pending["occurred_at_utc"],
                    pending["signal_id"],
                    str(payload["atr"]),
                    str(average),
                    int(payload["slot_count"]),
                ),
            )
            connection.execute(
                "UPDATE live_events SET status='FILLED',reason=NULL WHERE signal_id=?",
                (pending["signal_id"],),
            )

    def _apply_sell(self, pending: sqlite3.Row, summary: Mapping[str, object]) -> None:
        positions = self._positions()
        position = positions.get(str(pending["symbol"]))
        if position is None:
            self.fail_closed("EXIT_POSITION_MISSING")
            return
        fees = summary["fees_by_asset"]
        if not isinstance(fees, dict):
            self.fail_closed("EXIT_FEES_INVALID")
            return
        base = str(pending["symbol"]).removesuffix("USDC")
        consumed = Decimal(str(summary["gross_quantity"])) + Decimal(
            str(fees.get(base, "0"))
        )
        owned = Decimal(position["quantity"])
        remaining = owned - consumed
        rules = self.rules()[str(pending["symbol"])]
        if remaining < ZERO or remaining >= max(rules.step_size, rules.min_qty):
            self.fail_closed("EXIT_RESIDUAL_REQUIRES_REVIEW")
            return
        with self.journal._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM live_positions WHERE symbol=?", (pending["symbol"],)
            )
            if remaining > ZERO:
                connection.execute(
                    "INSERT INTO live_dust(symbol,quantity) VALUES(?,?) "
                    "ON CONFLICT(symbol) DO UPDATE SET quantity=quantity+excluded.quantity",
                    (pending["symbol"], str(remaining)),
                )
            connection.execute(
                "UPDATE live_events SET status='FILLED',reason=NULL WHERE signal_id=?",
                (pending["signal_id"],),
            )

    def _equity(
        self,
        snapshot: LiveAccountSnapshot,
        positions: Mapping[str, sqlite3.Row],
        group: Mapping[str, IndicatorPoint],
    ) -> Decimal:
        quote = sum(snapshot.balances.get("USDC", (ZERO, ZERO)))
        position_value = sum(
            Decimal(row["quantity"]) * Decimal(str(group[symbol].candle.close))
            for symbol, row in positions.items()
        )
        return quote + position_value

    def _risk_paused(self, equity: Decimal, boundary: datetime) -> bool:
        control = self._control()
        if control is None:
            return True
        day = boundary.date().isoformat()
        start = Decimal(control["day_start_equity"])
        if control["day_start_date"] != day:
            with self.journal._connect() as connection:
                connection.execute(
                    "UPDATE live_control SET day_start_date=?,day_start_equity=?,updated_at=? "
                    "WHERE singleton=1",
                    (day, str(equity), boundary.isoformat()),
                )
            start = equity
        return start > ZERO and equity <= start * Decimal("0.95")

    def _finish_boundary(
        self,
        boundary: datetime,
        group: Mapping[str, IndicatorPoint],
        positions: Mapping[str, sqlite3.Row],
    ) -> None:
        with self.journal._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for symbol, row in positions.items():
                latest = max(Decimal(row["highest_close"]), Decimal(str(group[symbol].candle.close)))
                connection.execute(
                    "UPDATE live_positions SET highest_close=? WHERE symbol=?",
                    (str(latest), symbol),
                )
            connection.executemany(
                "UPDATE live_checkpoints SET last_close_utc=? WHERE symbol=?",
                [(boundary.isoformat(), symbol) for symbol in SYMBOLS],
            )
            connection.execute(
                "UPDATE live_control SET updated_at=? WHERE singleton=1",
                (boundary.isoformat(),),
            )

    def advance(
        self,
        points: Mapping[str, Sequence[IndicatorPoint]],
        *,
        now: datetime,
        healthy: bool,
    ) -> dict[str, object]:
        now = _utc(now)
        with self.lock:
            control = self._control()
            if control is None or control["state"] == "LIVE_DISABLED":
                return self.report()
            if control["strategy_json"] != self._strategy_json():
                self.fail_closed("FROZEN_STRATEGY_MISMATCH")
                return self.report()
            pending = self._pending()
            if pending is not None:
                self._drive_pending(pending, now=now)
                return self.report()
            if not healthy or set(points) != set(SYMBOLS):
                return self.report()
            slots, target, emergency = self.settings()
            if control["state"] == "LIVE_ENABLED" and (
                slots != MAX_SLOTS or target != SLOT_NOTIONAL
            ):
                self.disable_entries()
                return self.report()
            next_group = self._next_group(points)
            if next_group is None:
                return self.report()
            boundary, group = next_group
            positions = self._positions()
            decisions = {
                symbol: self._decision(points[symbol], point, positions.get(symbol))
                for symbol, point in group.items()
            }

            for symbol in SYMBOLS:
                position = positions.get(symbol)
                decision = decisions[symbol]
                signal = decision.signal
                if (
                    position is not None
                    and signal is not None
                    and signal.action is SignalAction.EXIT_LONG
                    and self._event(signal.signal_id) is None
                ):
                    rules = self.rules()[symbol]
                    quantity = _round_down(Decimal(position["quantity"]), rules.step_size)
                    if quantity < rules.min_qty:
                        self.fail_closed("EXIT_BELOW_MINIMUM_REQUIRES_REVIEW")
                        return self.report()
                    self._reserve(
                        signal,
                        group[symbol],
                        action="EXIT_LONG",
                        slot_count=int(position["slot_count"]),
                        quantity=quantity,
                        reason=decision.exit_reason,
                    )
                    return self.report()

            if control["state"] == "LIVE_ENABLED" and bool(control["entries_enabled"]):
                candidates: list[tuple[Any, IndicatorPoint]] = []
                for symbol in SYMBOLS:
                    if symbol in positions:
                        continue
                    decision = decisions[symbol]
                    signal = decision.signal
                    if signal is None or signal.action is not SignalAction.ENTER_LONG:
                        continue
                    if decision.block_reason:
                        self._blocked(signal, decision.block_reason)
                    else:
                        candidates.append((signal, group[symbol]))
                candidates.sort(
                    key=lambda item: entry_priority(
                        item[1].rank_strength, item[0].symbol, self.strategy.symbols
                    )
                )
                snapshot = self.snapshot()
                proof = self.reconciler.check(snapshot, now=datetime.now(UTC))
                if proof["passed"] is not True:
                    self.fail_closed("ACCOUNT_RECONCILIATION_MISMATCH")
                    return self.report()
                equity = self._equity(snapshot, positions, group)
                paused = self._risk_paused(equity, boundary)
                used = sum(int(row["slot_count"]) for row in positions.values())
                free_slots = max(0, MAX_SLOTS - used)
                allocations = allocate_entry_slots(
                    [signal.symbol for signal, _ in candidates],
                    free_slots=free_slots,
                    policy=self.strategy.slot_allocation,
                )
                for signal, point in candidates:
                    if self._event(signal.signal_id) is not None:
                        continue
                    if emergency:
                        self._blocked(signal, "EMERGENCY_STOP")
                        continue
                    if paused:
                        self._blocked(signal, "DAILY_LOSS_5_PERCENT")
                        continue
                    allocated = allocations.get(signal.symbol, 0)
                    if allocated <= 0:
                        self._blocked(signal, "NO_FREE_SLOT")
                        continue
                    self._reserve(
                        signal,
                        point,
                        action="ENTER_LONG",
                        slot_count=allocated,
                    )
                    return self.report()

            self._finish_boundary(boundary, group, self._positions())
            return self.report()

    def report(self) -> dict[str, object]:
        control = self._control()
        positions = self._positions()
        used = sum(int(row["slot_count"]) for row in positions.values())
        return {
            "state": "LIVE_DISABLED" if control is None else str(control["state"]),
            "entries_enabled": bool(control["entries_enabled"]) if control is not None else False,
            "reason": control["reason"] if control is not None else None,
            "slot_count": MAX_SLOTS,
            "target_notional_usdc": str(SLOT_NOTIONAL),
            "used_slots": used,
            "free_slots": max(0, MAX_SLOTS - used),
            "positions": [
                {
                    "symbol": symbol,
                    "quantity": row["quantity"],
                    "slot_count": int(row["slot_count"]),
                    "entry_time_utc": row["entry_time_utc"],
                }
                for symbol, row in sorted(positions.items())
            ],
            "unresolved_intents": list(self.journal.unresolved_ids()),
        }


class LivePortfolioRuntime:
    def __init__(self, controller: LivePortfolioController) -> None:
        self.controller = controller
        self.stopped = Event()
        self.lock = RLock()
        self.last_error: str | None = None

    def stop(self) -> None:
        self.stopped.set()
        self.controller.disable_entries()

    def tick(
        self,
        points: Mapping[str, Sequence[IndicatorPoint]],
        *,
        now: datetime,
        healthy: bool,
    ) -> dict[str, object]:
        with self.lock:
            if self.stopped.is_set():
                return self.controller.report()
            self.last_error = None
            try:
                return self.controller.advance(points, now=now, healthy=healthy)
            except Exception:
                self.controller.fail_closed("LIVE_RUNTIME_REQUIRES_REVIEW")
                self.last_error = "LIVE_RUNTIME_REQUIRES_REVIEW"
                return {**self.controller.report(), "runtime_error": self.last_error}
