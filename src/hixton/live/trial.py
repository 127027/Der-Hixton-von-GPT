"""Persistent signal-driven one-shot controller with release-gated runtime wiring.

No HTTP release is provided by this module. It reuses the canonical Hixton policy,
never imports Paper holdings or Paper fills. Operational acceptance remains open.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from threading import RLock
from typing import Any
from uuid import UUID

from hixton.domain.markets import split_market
from hixton.domain.models import IndicatorPoint, SignalAction
from hixton.domain.strategy import entry_priority
from hixton.domain.trade_policy import TradePolicyGate
from hixton.domain.versions import StrategyDefinition
from hixton.live.orders import OrderJournal, TrialIntent, TrialOrderExecutor

_FINAL = {"COMPLETED", "CANCELED", "FAILED"}
_ORDER_FINAL = {"FILLED", "CANCELED", "EXPIRED", "EXPIRED_IN_MATCH", "REJECTED"}


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Timezone-aware UTC clock required")
    return value.astimezone(UTC)


def _strategy_json(strategy: StrategyDefinition) -> str:
    return json.dumps(strategy.config_payload(), sort_keys=True, allow_nan=False)


class SignalTrial:
    """One irreversible entry entitlement per ledger, independently of Paper settings.

    release_check and executor.pre_submit are mandatory injected safety gates.
    Actual account reconciliation, market filters and 24/7 Live remain outside.
    """

    def __init__(
        self,
        journal: OrderJournal,
        executor: TrialOrderExecutor,
        strategy: StrategyDefinition,
        release_check: Callable[[], bool],
    ) -> None:
        if executor.journal.path.resolve() != journal.path.resolve():
            raise ValueError("Trial and order journal must share the same ledger")
        self.journal = journal
        self.executor = executor
        self.strategy = strategy
        self.release_check = release_check
        self.lock = RLock()
        with journal._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS signal_trial (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    trial_id TEXT UNIQUE NOT NULL, account TEXT NOT NULL,
                    strategy_json TEXT NOT NULL, armed_at TEXT NOT NULL,
                    state TEXT NOT NULL, entries_enabled INTEGER NOT NULL,
                    buy_id TEXT UNIQUE, sell_id TEXT UNIQUE, symbol TEXT,
                    entry_signal_json TEXT, exit_signal_json TEXT,
                    entry_price TEXT, entry_atr TEXT, owned_quantity TEXT,
                    highest_close TEXT, last_exit_bar TEXT,
                    reason TEXT, completed_at TEXT
                )
            """)

    def _row(self) -> dict[str, Any] | None:
        with self.journal._connect() as connection:
            row = connection.execute("SELECT * FROM signal_trial WHERE singleton=1").fetchone()
        return dict(row) if row is not None else None

    def arm(self, trial_id: str, account: str, *, now: datetime, notional: Decimal) -> None:
        # No amount supplied by a caller can silently become 80, 500 or NaN.
        if not notional.is_finite() or notional != Decimal("50"):
            raise ValueError("Einmaltest benötigt genau 50 USDC Kaufbudget")
        if str(UUID(trial_id)) != trial_id or not account:
            raise ValueError("Invalid trial identity")
        now = _utc(now)
        with self.lock, self.journal._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM signal_trial").fetchone() is not None:
                raise RuntimeError("Einmaltest bereits angelegt; keine automatische Wiederholung")
            if connection.execute("SELECT 1 FROM trial_intents LIMIT 1").fetchone() is not None:
                raise RuntimeError("Unzugeordnete Orderhistorie; zuerst abgleichen")
            if not self.release_check():
                raise RuntimeError("Echtgeld-Testfreigabe fehlt")
            connection.execute(
                "INSERT INTO signal_trial(singleton,trial_id,account,strategy_json,armed_at,"
                "state,entries_enabled) VALUES(1,?,?,?,?,'WAITING_SIGNAL',1)",
                (trial_id, account, _strategy_json(self.strategy), now.isoformat()),
            )
            self.journal._audit(connection, trial_id, "TRIAL_ARMED")

    def disable_entries(self) -> None:
        """No liquidation, no cancel of potentially filled orders, no Paper changes."""
        with self.lock, self.journal._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM signal_trial").fetchone()
            if row is None:
                return
            state = "CANCELED" if row["state"] == "WAITING_SIGNAL" else row["state"]
            # An unclaimed entry may be abandoned; an uncertain sent order must be queried.
            if row["state"] == "ENTRY_PENDING":
                order = connection.execute(
                    "SELECT state FROM trial_intents WHERE intent_id=?", (row["buy_id"],)
                ).fetchone()
                if order is None or order["state"] == "CREATED":
                    state = "CANCELED"
            connection.execute(
                "UPDATE signal_trial SET entries_enabled=0,state=? WHERE singleton=1", (state,)
            )
            self.journal._audit(connection, row["trial_id"], "NEW_ENTRIES_DISABLED")

    def _set(self, *, from_state: str | None = None, **values: object) -> None:
        allowed = {
            "state",
            "reason",
            "entry_price",
            "entry_atr",
            "owned_quantity",
            "highest_close",
            "last_exit_bar",
            "completed_at",
            "entries_enabled",
        }
        if not values or not values.keys() <= allowed:
            raise ValueError("Invalid trial update")
        with self.journal._connect() as connection:
            connection.execute(
                "UPDATE signal_trial SET "
                + ",".join(f"{key}=?" for key in values)
                + " WHERE singleton=1 AND state NOT IN ('COMPLETED','CANCELED','FAILED')"
                + (" AND state=?" if from_state else ""),
                (*values.values(), *((from_state,) if from_state else ())),
            )

    @staticmethod
    def _signal(point: IndicatorPoint, reason: str) -> str:
        return json.dumps(
            {
                "symbol": point.symbol,
                "strategy_version": point.strategy_version,
                "bar_close": _utc(point.candle.close_time_utc).isoformat(),
                "close": point.candle.close,
                "atr": point.atr,
                "vidya": point.vidya,
                "cmo": point.abs_cmo,
                "rank": point.rank_strength,
                "reason": reason,
            },
            sort_keys=True,
            allow_nan=False,
        )

    def _reserve(
        self,
        row: dict[str, Any],
        point: IndicatorPoint,
        *,
        side: str,
        reason: str,
        reference: Decimal,
    ) -> None:
        entry = side == "BUY"
        intent_id = row["trial_id"] + ("-entry" if entry else "-exit")
        signal = json.loads(self._signal(point, reason))
        signal["reference_price"] = str(reference)
        with self.journal._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            fresh = connection.execute("SELECT * FROM signal_trial").fetchone()
            expected = "WAITING_SIGNAL" if entry else "OPEN"
            if fresh["state"] != expected or (entry and not fresh["entries_enabled"]):
                return
            # Reserve the sole BUY/SELL identity BEFORE constructing the order record.
            # Recovery uses that same identity if the process stops between transactions.
            connection.execute(
                "UPDATE signal_trial SET state=?,symbol=?,"
                + ("buy_id=?,entry_signal_json=?" if entry else "sell_id=?,exit_signal_json=?")
                + " WHERE singleton=1",
                (
                    "ENTRY_PENDING" if entry else "EXIT_PENDING",
                    point.symbol,
                    intent_id,
                    json.dumps(signal, sort_keys=True),
                ),
            )
            self.journal._audit(
                connection, row["trial_id"], "ENTRY_RESERVED" if entry else "EXIT_RESERVED"
            )

    def _drive_order(self, row: dict[str, Any], now: datetime) -> None:
        entry = row["state"] == "ENTRY_PENDING"
        signal = json.loads(row["entry_signal_json"] if entry else row["exit_signal_json"])
        intent = TrialIntent(
            row["buy_id"] if entry else row["sell_id"],
            row["account"],
            row["symbol"],
            "BUY" if entry else "SELL",
            self.strategy.version,
            Decimal(signal["reference_price"]),
            quote_budget=Decimal("50") if entry else Decimal(0),
            base_quantity=Decimal(0) if entry else Decimal(row["owned_quantity"]),
        )
        self.journal.create(intent)
        _, state = self.journal.load(intent.intent_id)
        if state == "CREATED":
            age = (now - datetime.fromisoformat(signal["bar_close"])).total_seconds()
            if entry and (not row["entries_enabled"] or not 0 <= age <= 90):
                self._set(state="FAILED", reason="ENTRY_EXPIRED_OR_DISABLED", entries_enabled=0)
                return
            if entry and not self.release_check():
                self._set(reason="RELEASE_REQUIRED")
                return
        state = self.executor.execute(intent.intent_id)
        if state not in _ORDER_FINAL:
            self._set(reason="ORDER_" + state)
            return
        summary = self.journal.fill_summary(intent.intent_id)
        if entry:
            quantity = Decimal(str(summary["net_received_base"]))
            if quantity <= 0:
                self._set(state="FAILED", reason="NO_NET_ENTRY_FILL", entries_enabled=0)
                return
            gross = Decimal(str(summary["gross_quantity"]))
            price = Decimal(str(summary["gross_quote"])) / gross
            self._set(
                from_state="ENTRY_PENDING",
                state="OPEN",
                reason=None,
                entry_price=str(price),
                entry_atr=str(signal["atr"]),
                owned_quantity=str(quantity),
                highest_close=str(price),
                last_exit_bar=signal["bar_close"],
                entries_enabled=0,
            )
        else:
            sold = Decimal(str(summary["gross_quantity"]))
            owned = Decimal(row["owned_quantity"])
            fees = summary["fees_by_asset"]
            assert isinstance(fees, dict)
            consumed = sold + Decimal(str(fees.get(split_market(row["symbol"])[0], "0")))
            if consumed != owned:
                self._set(
                    from_state="EXIT_PENDING",
                    state="NEEDS_REVIEW",
                    reason="EXIT_RESIDUAL_OR_BALANCE_MISMATCH",
                )
            else:
                # Confirmed fills are not an account/foreign-order reconciliation proof.
                self._set(
                    from_state="EXIT_PENDING",
                    state="AWAITING_RECONCILIATION",
                    reason="ACCOUNT_CHECK_REQUIRED",
                )

    def confirm_reconciled(
        self,
        *,
        no_open_orders: bool,
        owned_remaining: Decimal,
        account_matches: bool,
        now: datetime,
    ) -> None:
        """For an eventual trusted account reconciler, NEVER expose as a UI assertion."""
        with self.lock:
            row = self._row()
            if row is None or row["state"] != "AWAITING_RECONCILIATION":
                raise RuntimeError("Round trip has not reached the account reconciliation gate")
            if (
                no_open_orders is not True
                or account_matches is not True
                or not owned_remaining.is_finite()
                or owned_remaining != 0
            ):
                raise RuntimeError("Account/order reconciliation incomplete")
            self._set(
                state="COMPLETED",
                reason=None,
                entries_enabled=0,
                completed_at=_utc(now).isoformat(),
            )
            with self.journal._connect() as connection:
                self.journal._audit(connection, row["trial_id"], "TRIAL_COMPLETED")

    def advance(
        self, points: Mapping[str, Sequence[IndicatorPoint]], *, now: datetime, healthy: bool
    ) -> dict[str, object]:
        now = _utc(now)
        with self.lock:
            row = self._row()
            if row is None or row["state"] in _FINAL:
                return self.report()
            if row["strategy_json"] != _strategy_json(self.strategy):
                self._set(reason="FROZEN_STRATEGY_MISMATCH", entries_enabled=0)
                return self.report()
            if row["state"] in {"ENTRY_PENDING", "EXIT_PENDING"}:
                # Query uncertain orders even when market health is degraded.
                if healthy or self.journal_state(row) != "CREATED":
                    self._drive_order(row, now)
                return self.report()
            if not healthy:
                return self.report()
            if row["state"] == "WAITING_SIGNAL":
                self._select_entry(row, points, now)
            elif row["state"] == "OPEN":
                self._select_exit(row, points)
            return self.report()

    def journal_state(self, row: dict[str, Any]) -> str:
        identity = row["buy_id"] if row["state"] == "ENTRY_PENDING" else row["sell_id"]
        try:
            return self.journal.load(identity)[1]
        except KeyError:
            return "CREATED"

    def _select_entry(
        self, row: dict[str, Any], points: Mapping[str, Sequence[IndicatorPoint]], now: datetime
    ) -> None:
        candidates: list[IndicatorPoint] = []
        boundaries = set()
        for symbol in self.strategy.symbols:
            series = points.get(symbol, ())
            if not series:
                return  # Incomplete universe cannot win merely by arriving earlier.
            point = series[-1]
            boundary = _utc(point.candle.close_time_utc)
            boundaries.add(boundary)
            if point.symbol != symbol or point.strategy_version != self.strategy.version:
                return
            if not point.candle.closed or not point.tradable or not point.candle.ohlc_is_valid:
                return
            if not 0 <= (now - boundary).total_seconds() <= 90:
                return
            gate = TradePolicyGate(self.strategy.policy_for(symbol))
            decision = None
            for prior in series[-74:]:
                decision = gate.decide(prior)
            if (
                boundary > datetime.fromisoformat(row["armed_at"])
                and decision
                and decision.signal
                and decision.signal.action is SignalAction.ENTER_LONG
                and not decision.block_reason
                and point.atr
                and point.atr > 0
            ):
                candidates.append(point)
        if len(boundaries) != 1 or not candidates:
            return
        candidates.sort(
            key=lambda point: entry_priority(
                point.rank_strength, point.symbol, self.strategy.symbols
            )
        )
        winner = candidates[0]
        self._reserve(
            row,
            winner,
            side="BUY",
            reason="HIXTON_ENTER_LONG",
            reference=Decimal(str(winner.candle.close)),
        )

    def _select_exit(
        self, row: dict[str, Any], points: Mapping[str, Sequence[IndicatorPoint]]
    ) -> None:
        series = points.get(row["symbol"], ())
        if not series or series[-1].strategy_version != self.strategy.version:
            return
        latest = series[-1]
        if not latest.candle.closed or not latest.candle.ohlc_is_valid:
            return
        gate = TradePolicyGate(self.strategy.policy_for(row["symbol"]))
        highest = float(row["highest_close"])
        after = datetime.fromisoformat(row["last_exit_bar"])
        if _utc(latest.candle.close_time_utc) <= after:
            return
        for point in series:
            if _utc(point.candle.close_time_utc) <= after:
                gate.decide(point)
                continue
            if not point.candle.closed or not point.candle.ohlc_is_valid:
                return
            decision = gate.decide(
                point,
                entry_price=float(row["entry_price"]),
                entry_atr=float(row["entry_atr"]),
                highest_close=highest,
            )
            if decision.signal and decision.signal.action is SignalAction.EXIT_LONG:
                # A missed exit remains a real exit obligation, not a backdated model fill.
                self._reserve(
                    row,
                    point,
                    side="SELL",
                    reason=decision.exit_reason or "HIXTON_EXIT_LONG",
                    reference=Decimal(str(latest.candle.close)),
                )
                return
            highest = max(highest, point.candle.close)
        self._set(
            highest_close=str(highest), last_exit_bar=_utc(latest.candle.close_time_utc).isoformat()
        )

    def report(self) -> dict[str, object]:
        row = self._row()
        if row is None:
            return {"state": "NOT_STARTED", "mode": "ONE_SHOT_50", "has_unsettled": False}
        result: dict[str, object] = {
            "trial_id": row["trial_id"],
            "mode": "ONE_SHOT_50",
            "state": row["state"],
            "symbol": row["symbol"],
            "quote_asset": json.loads(row["strategy_json"]).get("quote_asset", "USDT"),
            "quote_budget": "50.00",
            "quote_budget_usdt": (
                "50.00"
                if json.loads(row["strategy_json"]).get("quote_asset", "USDT") == "USDT"
                else None
            ),
            "entries_enabled": bool(row["entries_enabled"]),
            "reason": row["reason"],
            "armed_at_utc": row["armed_at"],
            "completed_at_utc": row["completed_at"],
            "has_unsettled": row["state"] not in _FINAL,
            "strategy": json.loads(row["strategy_json"]),
            "entry_signal": json.loads(row["entry_signal_json"] or "null"),
            "exit_signal": json.loads(row["exit_signal_json"] or "null"),
            "account_reconciled": row["state"] == "COMPLETED",
        }
        for label in ("buy", "sell"):
            identity = row[label + "_id"]
            try:
                result[label] = self.journal.fill_summary(identity) if identity else None
            except KeyError:
                result[label] = None
        if row["symbol"]:
            policy = self.strategy.policy_for(row["symbol"])
            result["exit_rules"] = {
                **asdict(policy),
                "fixed_take_profit": False,
                "exchange_hosted_stop": False,
            }
        # Fees in BNB/other assets must not be labelled USDT or silently valued at zero.
        result["net_pnl_usdt"] = None
        result["net_pnl_usdc"] = None
        result["net_pnl_quote"] = None
        entry, exit_order = result["buy"], result["sell"]
        if isinstance(entry, dict) and isinstance(exit_order, dict):
            fees: dict[str, Decimal] = {}
            for order in (entry, exit_order):
                for asset, amount in order["fees_by_asset"].items():
                    fees[asset] = fees.get(asset, Decimal(0)) + Decimal(amount)
            base, quote_asset = split_market(row["symbol"])
            unvalued = [
                asset
                for asset, amount in fees.items()
                if amount and asset not in {base, quote_asset}
            ]
            result["unvalued_fee_assets"] = unvalued
            result["fees_by_asset"] = {asset: str(amount) for asset, amount in fees.items()}
            if row["state"] == "COMPLETED" and not unvalued:
                result["net_pnl_quote"] = str(
                    Decimal(exit_order["gross_quote"])
                    - Decimal(entry["gross_quote"])
                    - fees.get(quote_asset, Decimal(0))
                )
                if quote_asset == "USDT":
                    result["net_pnl_usdt"] = result["net_pnl_quote"]
                elif quote_asset == "USDC":
                    result["net_pnl_usdc"] = result["net_pnl_quote"]
        return result
