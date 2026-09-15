"""Offline-tested order safety core; no released UI submit route.

Persist SUBMITTING before calling an injected exchange. Ambiguous outcomes are
only queried, NEVER submitted a second time, including across process restarts.
This is not a complete live ledger, reconciliation engine or release approval.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from hixton.domain.markets import split_market

_ZERO = Decimal("0")
_TERMINAL = {"FILLED", "CANCELED", "REJECTED", "EXPIRED", "EXPIRED_IN_MATCH"}
_EXCHANGE_STATES = _TERMINAL | {"NEW", "PARTIALLY_FILLED", "PENDING_CANCEL"}


def _amount(value: Decimal, *, positive: bool = False) -> None:
    if not value.is_finite() or value < 0 or (positive and value == 0):
        raise ValueError("Order amounts must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class TrialIntent:
    """A future explicitly consented order; no default symbol or implicit side."""

    intent_id: str
    account_fingerprint: str
    symbol: str
    side: str
    strategy_version: str
    reference_price: Decimal
    quote_budget: Decimal = _ZERO
    base_quantity: Decimal = _ZERO

    def __post_init__(self) -> None:
        split_market(self.symbol)
        if (
            not self.intent_id
            or len(self.intent_id) > 128
            or not self.account_fingerprint
            or self.side not in {"BUY", "SELL"}
            or not self.strategy_version
        ):
            raise ValueError("Invalid order identity")
        _amount(self.reference_price, positive=True)
        _amount(self.quote_budget)
        _amount(self.base_quantity)
        if self.side == "BUY" and (self.quote_budget != Decimal("50") or self.base_quantity != 0):
            raise ValueError("First trial BUY must use exactly 50 quote units, no base quantity")
        if self.side == "SELL" and (self.quote_budget != 0 or self.base_quantity <= 0):
            raise ValueError("Trial SELL requires an explicit owned base quantity")

    @property
    def client_order_id(self) -> str:
        digest = hashlib.sha256(
            f"LIVE|{self.account_fingerprint}|{self.intent_id}".encode()
        ).hexdigest()
        return "hxtrial_" + digest[:28]  # Binance maximum: 36 characters.


@dataclass(frozen=True, slots=True)
class ExchangeFill:
    trade_id: str
    quantity: Decimal
    price: Decimal
    commission: Decimal
    commission_asset: str
    quote_quantity: Decimal | None = None

    def __post_init__(self) -> None:
        _amount(self.quantity, positive=True)
        _amount(self.price, positive=True)
        _amount(self.commission)
        if self.quote_quantity is not None:
            _amount(self.quote_quantity, positive=True)
        if not self.trade_id or not self.commission_asset:
            raise ValueError("Fill identity and fee asset are required")

    @property
    def quote(self) -> Decimal:
        # Binance myTrades.quoteQty may be rounded to quote precision. Never
        # invent a different cash movement by multiplying the display price.
        return self.quantity * self.price if self.quote_quantity is None else self.quote_quantity


@dataclass(frozen=True, slots=True)
class ExchangeOrder:
    client_order_id: str
    order_id: str
    symbol: str
    side: str
    state: str
    executed_quantity: Decimal
    cumulative_quote: Decimal
    fills: tuple[ExchangeFill, ...] = ()

    def __post_init__(self) -> None:
        split_market(self.symbol)
        if (
            self.state not in _EXCHANGE_STATES
            or self.side not in {"BUY", "SELL"}
            or not self.order_id
        ):
            raise ValueError("Invalid exchange order state")
        _amount(self.executed_quantity)
        _amount(self.cumulative_quote)
        if self.state == "FILLED" and self.executed_quantity == 0:
            raise ValueError("FILLED requires executed quantity")


class OrderExchange(Protocol):
    """Transport contract; its existence does not grant production release."""

    def submit(self, intent: TrialIntent) -> ExchangeOrder: ...
    def query(self, intent: TrialIntent) -> ExchangeOrder | None: ...


class OrderJournal:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS trial_intents (
                    intent_id TEXT PRIMARY KEY, client_id TEXT UNIQUE NOT NULL,
                    account TEXT NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL,
                    strategy TEXT NOT NULL, reference TEXT NOT NULL, quote_budget TEXT NOT NULL,
                    base_quantity TEXT NOT NULL, state TEXT NOT NULL, order_id TEXT,
                    exchange_state TEXT,
                    executed_quantity TEXT NOT NULL DEFAULT '0',
                    cumulative_quote TEXT NOT NULL DEFAULT '0', updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS trial_fills (
                    account TEXT NOT NULL, symbol TEXT NOT NULL, trade_id TEXT NOT NULL,
                    intent_id TEXT NOT NULL REFERENCES trial_intents(intent_id),
                    quantity TEXT NOT NULL, price TEXT NOT NULL, commission TEXT NOT NULL,
                    commission_asset TEXT NOT NULL, PRIMARY KEY(account, symbol, trade_id)
                );
                CREATE TABLE IF NOT EXISTS trial_order_audit (
                    id INTEGER PRIMARY KEY, intent_id TEXT NOT NULL,
                    action TEXT NOT NULL, at_utc TEXT NOT NULL
                );
            """)
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(trial_fills)")}
            if "quote_quantity" not in columns:
                connection.execute("ALTER TABLE trial_fills ADD COLUMN quote_quantity TEXT")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA synchronous=FULL")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _audit(connection: sqlite3.Connection, intent_id: str, action: str) -> None:
        connection.execute(
            "INSERT INTO trial_order_audit(intent_id, action, at_utc) VALUES(?,?,?)",
            (intent_id, action, datetime.now(UTC).isoformat()),
        )

    def create(self, intent: TrialIntent) -> bool:
        identity = (
            intent.intent_id,
            intent.client_order_id,
            intent.account_fingerprint,
            intent.symbol,
            intent.side,
            intent.strategy_version,
            str(intent.reference_price),
            str(intent.quote_budget),
            str(intent.base_quantity),
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT intent_id,client_id,account,symbol,side,strategy,reference,quote_budget,"
                "base_quantity FROM trial_intents WHERE intent_id=?",
                (intent.intent_id,),
            ).fetchone()
            if existing:
                if tuple(existing)[:6] != identity[:6] or any(
                    Decimal(existing[index]) != Decimal(identity[index]) for index in range(6, 9)
                ):
                    raise RuntimeError("Intent identity cannot be reused with different parameters")
                return False
            connection.execute(
                "INSERT INTO trial_intents(intent_id,client_id,account,symbol,side,strategy,"
                "reference,quote_budget,base_quantity,state,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,'CREATED',?)",
                (*identity, datetime.now(UTC).isoformat()),
            )
            self._audit(connection, intent.intent_id, "INTENT_CREATED")
            return True

    def load(self, intent_id: str) -> tuple[TrialIntent, str]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM trial_intents WHERE intent_id=?", (intent_id,)
            ).fetchone()
        if row is None:
            raise KeyError("Unknown trial intent")
        return TrialIntent(
            row["intent_id"],
            row["account"],
            row["symbol"],
            row["side"],
            row["strategy"],
            Decimal(row["reference"]),
            Decimal(row["quote_budget"]),
            Decimal(row["base_quantity"]),
        ), row["state"]

    def claim_submit(self, intent_id: str) -> bool:
        with self._connect() as connection:
            changed = connection.execute(
                "UPDATE trial_intents SET state='SUBMITTING',updated_at=? "
                "WHERE intent_id=? AND state='CREATED'",
                (datetime.now(UTC).isoformat(), intent_id),
            ).rowcount
            if changed:
                self._audit(connection, intent_id, "SUBMITTING")
            return changed == 1

    def unknown(self, intent_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE trial_intents SET state='UNKNOWN',updated_at=? WHERE intent_id=? "
                "AND state NOT IN ('CREATED','FILLED','CANCELED','REJECTED','EXPIRED',"
                "'EXPIRED_IN_MATCH')",
                (datetime.now(UTC).isoformat(), intent_id),
            )
            self._audit(connection, intent_id, "RECONCILIATION_REQUIRED")

    def record(self, intent: TrialIntent, order: ExchangeOrder) -> None:
        if (
            order.client_order_id != intent.client_order_id
            or order.symbol != intent.symbol
            or order.side != intent.side
        ):
            raise RuntimeError("Exchange response does not match the persisted intent")
        if intent.side == "BUY" and order.cumulative_quote > intent.quote_budget:
            raise RuntimeError("Exchange BUY exceeds the consented quote budget")
        if intent.side == "SELL" and order.executed_quantity > intent.base_quantity:
            raise RuntimeError("Exchange SELL exceeds the intent base quantity")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            old = connection.execute(
                "SELECT * FROM trial_intents WHERE intent_id=?", (intent.intent_id,)
            ).fetchone()
            if old is None or old["state"] == "CREATED":
                raise RuntimeError("Unsubmitted/unknown intent cannot receive fills")
            if (
                old["client_id"] != intent.client_order_id
                or old["account"] != intent.account_fingerprint
                or old["symbol"] != intent.symbol
                or old["side"] != intent.side
                or old["strategy"] != intent.strategy_version
                or Decimal(old["reference"]) != intent.reference_price
                or Decimal(old["quote_budget"]) != intent.quote_budget
                or Decimal(old["base_quantity"]) != intent.base_quantity
            ):
                raise RuntimeError("Supplied intent differs from the persisted intent")
            if old["order_id"] and old["order_id"] != order.order_id:
                raise RuntimeError("Exchange order identity changed")
            if Decimal(old["executed_quantity"]) > order.executed_quantity:
                raise RuntimeError("Executed quantity must never decrease")
            if Decimal(old["cumulative_quote"]) > order.cumulative_quote:
                raise RuntimeError("Cumulative quote must never decrease")
            if old["exchange_state"] in _TERMINAL and (
                order.state != old["exchange_state"]
                or Decimal(old["executed_quantity"]) != order.executed_quantity
                or Decimal(old["cumulative_quote"]) != order.cumulative_quote
            ):
                raise RuntimeError("Terminal exchange order state/totals cannot change")
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
                    "SELECT * FROM trial_fills WHERE account=? AND symbol=? AND trade_id=?",
                    values[:3],
                ).fetchone()
                if existing is not None and (
                    tuple(existing)[:4] != values[:4]
                    or existing["commission_asset"] != fill.commission_asset
                    or Decimal(existing["quantity"]) != fill.quantity
                    or Decimal(existing["price"]) != fill.price
                    or Decimal(existing["commission"]) != fill.commission
                    or (
                        Decimal(existing["quote_quantity"])
                        if existing["quote_quantity"] is not None
                        else Decimal(existing["quantity"]) * Decimal(existing["price"])
                    )
                    != fill.quote
                ):
                    raise RuntimeError("Conflicting duplicate fill; manual reconciliation required")
                connection.execute(
                    "INSERT OR IGNORE INTO trial_fills VALUES(?,?,?,?,?,?,?,?,?)", values
                )
            fills = connection.execute(
                "SELECT quantity,price,quote_quantity FROM trial_fills WHERE intent_id=?",
                (intent.intent_id,),
            ).fetchall()
            booked_quantity = sum((Decimal(f["quantity"]) for f in fills), _ZERO)
            booked_quote = sum((self._fill_quote(f) for f in fills), _ZERO)
            if booked_quantity > order.executed_quantity or booked_quote > order.cumulative_quote:
                raise RuntimeError("Fill amounts exceed exchange order totals")
            complete = (
                booked_quantity == order.executed_quantity
                and booked_quote == order.cumulative_quote
            )
            state = order.state if complete else "FILL_DETAILS_PENDING"
            connection.execute(
                "UPDATE trial_intents SET state=?,exchange_state=?,order_id=?,executed_quantity=?,"
                "cumulative_quote=?,updated_at=? WHERE intent_id=?",
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

    @staticmethod
    def _fill_quote(row: sqlite3.Row) -> Decimal:
        return (
            Decimal(row["quote_quantity"])
            if row["quote_quantity"] is not None
            else Decimal(row["quantity"]) * Decimal(row["price"])
        )

    def fill_summary(self, intent_id: str) -> dict[str, object]:
        intent, state = self.load(intent_id)
        with self._connect() as connection:
            order = connection.execute(
                "SELECT client_id,order_id,exchange_state,updated_at FROM trial_intents "
                "WHERE intent_id=?",
                (intent_id,),
            ).fetchone()
            rows = connection.execute(
                "SELECT * FROM trial_fills WHERE intent_id=?", (intent_id,)
            ).fetchall()
        quantity = sum((Decimal(row["quantity"]) for row in rows), _ZERO)
        quote = sum((self._fill_quote(row) for row in rows), _ZERO)
        fees: dict[str, Decimal] = {}
        for row in rows:
            fees[row["commission_asset"]] = fees.get(row["commission_asset"], _ZERO) + Decimal(
                row["commission"]
            )
        base, quote_asset = split_market(intent.symbol)
        net_received = quantity - fees.get(base, _ZERO) if intent.side == "BUY" else _ZERO
        return {
            "intent_id": intent_id,
            "client_order_id": order["client_id"],
            "exchange_order_id": order["order_id"],
            "exchange_state": order["exchange_state"],
            "recorded_at_utc": order["updated_at"],
            "state": state,
            "fill_count": len(rows),
            "gross_quantity": str(quantity),
            "base_asset": base,
            "quote_asset": quote_asset,
            "gross_quote": str(quote),
            # Compatibility only for genuinely USDT records, never relabel USDC.
            "gross_quote_usdt": str(quote) if quote_asset == "USDT" else None,
            "gross_quote_usdc": str(quote) if quote_asset == "USDC" else None,
            "net_received_base": str(net_received),
            "fees_by_asset": {asset: str(value) for asset, value in fees.items()},
            "fees_fully_valued_in_quote": set(fees) <= {quote_asset},
            "fees_fully_valued_in_usdt": quote_asset == "USDT" and set(fees) <= {"USDT"},
            "fees_fully_valued_in_usdc": quote_asset == "USDC" and set(fees) <= {"USDC"},
            "fills": [
                {
                    key: row[key]
                    for key in (
                        "trade_id",
                        "quantity",
                        "price",
                        "commission",
                        "commission_asset",
                    )
                }
                for row in rows
            ],
        }


class TrialOrderExecutor:
    """Crash-safe submission primitive; release, signal, ownership gates remain outside."""

    def __init__(
        self,
        journal: OrderJournal,
        exchange: OrderExchange,
        pre_submit: Callable[[TrialIntent], bool],
    ) -> None:
        self.journal = journal
        self.exchange = exchange
        self.pre_submit = pre_submit

    def execute(self, intent_id: str) -> str:
        intent, state = self.journal.load(intent_id)
        if state != "CREATED":
            return self.reconcile(intent_id)
        # This injected gate must verify explicit consent, account, fresh book and owned quantity.
        # There is no permissive production default and no UI wiring to this primitive.
        if not self.pre_submit(intent):
            return "BLOCKED"
        if not self.journal.claim_submit(intent_id):
            return self.reconcile(intent_id)
        try:
            response = self.exchange.submit(intent)
            self.journal.record(intent, response)
        except Exception:
            # Never log a raw adapter exception (it could contain signed URLs or secrets).
            self.journal.unknown(intent_id)
        return self.journal.load(intent_id)[1]

    def reconcile(self, intent_id: str) -> str:
        intent, state = self.journal.load(intent_id)
        if state == "CREATED" or state in _TERMINAL:
            return state
        try:
            response = self.exchange.query(intent)
            if response is None:
                self.journal.unknown(intent_id)
            else:
                self.journal.record(intent, response)
        except Exception:
            self.journal.unknown(intent_id)
        return self.journal.load(intent_id)[1]
