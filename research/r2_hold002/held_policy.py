"""R2-D1-HOLD-002: isolated, predeclared held-position risk reduction.

All financial effects use original f56 native Fill/Trade, market filters, execution
price, proportional cost basis, and unchanged slot allocations. No live imports.
"""
from __future__ import annotations
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
import hashlib

from hixton.backtest.models import Fill, Trade, ExecutionRules, ONE, ZERO
from hixton.domain.market_rules import (
    round_market_quantity, market_order_block_reason, market_order_is_dust
)
from hixton.domain.models import SignalAction
from hixton.domain.strategy import HixtonStrategy

CANDIDATE = "R2-D1-HOLD-002"
TRIGGER_DD = D("0.15")
TRIGGER_HOURS = 72
TRIM_FRACTION = D("0.25")
REARM_DD_STRICT = D("0.10")
REARM_HOURS = 168

class HeldRiskKernel:
    """One risk episode, at most one trim per regular position, after closed bars."""
    def __init__(self, *, enabled=True):
        self.enabled = enabled
        self.last_close = None
        self.warning_streak = 0
        self.clear_streak = 0
        self.defensive = False
        self.episode = 0
        self.pending_trim = {}
        self.pending_close = None
        self.events = []

    @property
    def entry_allowed(self):
        return True

    def on_close(self, *, equity, hwm, close_time, positions):
        if not self.enabled:
            return
        if self.last_close is not None and close_time-self.last_close != timedelta(hours=1):
            raise RuntimeError("R2_HOLD_NONCONTIGUOUS_CLOSED_BARS")
        self.last_close = close_time
        if equity <= 0 or hwm <= 0 or equity > hwm:
            raise RuntimeError("R2_HOLD_INVALID_HWM_OR_EQUITY")
        dd = (hwm-equity)/hwm
        if self.defensive:
            self.clear_streak = self.clear_streak+1 if dd < REARM_DD_STRICT else 0
            if self.clear_streak >= REARM_HOURS:
                self.defensive = False
                self.warning_streak = 0
                self.clear_streak = 0
                self.events.append({"kind":"REARM", "signal_close_utc":close_time.isoformat(),
                                    "dd":str(dd),"episode":self.episode,
                                    "new_buy_gate":"NATIVE_BUYS_ALWAYS_ALLOWED"})
            return
        self.warning_streak = self.warning_streak+1 if dd >= TRIGGER_DD else 0
        if self.warning_streak < TRIGGER_HOURS:
            return
        # Frozen regular-owned quantities, not cash/equity and not dust.
        self.defensive = True
        self.warning_streak = 0
        self.episode += 1
        if self.pending_trim:
            raise RuntimeError("R2_HOLD_DUPLICATE_EPISODE_PENDING")
        self.pending_trim = {s:p.quantity*TRIM_FRACTION for s,p in positions.items()
                             if p.quantity > ZERO}
        self.pending_close = close_time
        self.events.append({"kind":"TRIGGER","signal_close_utc":close_time.isoformat(),
                            "dd":str(dd),"episode":self.episode,"held_regular_coins":len(self.pending_trim),
                            "planned_quantities":{s:str(q) for s,q in self.pending_trim.items()},
                            "new_entries_gate":"UNCHANGED_NATIVE_BUY_RULES"})

    def execute_pending(self, *, cash, positions, previous_points, candles,
                        pending, rules, costs, signals, fills, trades, blocked, open_time):
        """Execute once at next native open, AFTER native exits/handoff, BEFORE buys.

        Native sales and other normal exits have priority. Failed market filters
        do not cause hourly retries. Remaining regular units keep their slots.
        """
        if not self.enabled or not self.pending_trim:
            return cash
        if self.pending_close is None or open_time != self.pending_close+timedelta(milliseconds=1):
            raise RuntimeError("R2_HOLD_NOT_NEXT_NATIVE_OPEN")
        planned = self.pending_trim
        self.pending_trim = {}
        close_time = self.pending_close
        self.pending_close = None
        # Native orders from earlier signals were already processed before this.
        for symbol, frozen_qty in sorted(planned.items()):
            p = positions.get(symbol)
            if p is None or p.quantity <= 0:
                self.events.append({"kind":"TRIM_SKIPPED_NATIVE_EXIT","symbol":symbol,
                                    "open_utc":open_time.isoformat(),"episode":self.episode})
                continue
            if symbol not in previous_points or symbol not in candles:
                raise RuntimeError("R2_HOLD_MISSING_NATIVE_SYMBOL")
            point = previous_points[symbol]
            if not point.candle.closed or point.candle.close_time_utc != close_time:
                raise RuntimeError("R2_HOLD_FUTURE_OR_STALE_INDICATOR")
            rule = rules.get(symbol, ExecutionRules())
            quantity = round_market_quantity(min(frozen_qty,p.quantity), rule)
            reference = D(str(candles[symbol].open))
            fill_price = reference*(ONE-costs.adverse_price_rate)
            reason = market_order_block_reason(rule,quantity,fill_price)
            if reason is not None or quantity<=ZERO:
                why=reason or "ZERO_ROUNDED_QUANTITY"
                blocked.append(f"{CANDIDATE}:{symbol}:TRIM_FILTER_{why}")
                self.events.append({"kind":"TRIM_SKIPPED_MARKET_FILTER","symbol":symbol,
                                    "reason":why,"open_utc":open_time.isoformat(),
                                    "episode":self.episode})
                continue
            if p.cost_basis <= 0:
                raise RuntimeError("R2_HOLD_NONPOSITIVE_LOT_BASIS")
            native_point = replace(point, flip_down=True,flip_up=False)
            forced = HixtonStrategy.signal_for(native_point,is_long=True)
            if forced is None or forced.action is not SignalAction.EXIT_LONG:
                raise RuntimeError("R2_HOLD_NATIVE_EXIT_SIGNAL_NOT_AVAILABLE")
            ident = hashlib.sha256(
                f"{CANDIDATE}|{self.episode}|{symbol}|{close_time.isoformat()}".encode()
            ).hexdigest()
            forced = replace(forced,signal_id=ident)
            basis = p.cost_basis * quantity / p.quantity
            gross = quantity*fill_price
            fee = gross*costs.fee_rate
            net = gross-fee
            pnl=net-basis
            fill = Fill(signal_id=ident,action=SignalAction.EXIT_LONG,
                        fill_time_utc=open_time,reference_open=reference,
                        fill_price=fill_price,base_quantity=quantity,quote_value=gross,
                        fee_quote_equivalent=fee,
                        modeled_spread_slippage=quantity*(reference-fill_price))
            # Same proportional cost-basis and native Fill/Trade accounting as
            # original f56 diversification stage partial trim.
            trade = Trade(symbol=symbol,entry_signal_id=p.signal.signal_id,
                          exit_signal_id=ident,entry_time_utc=p.fill.fill_time_utc,
                          exit_time_utc=open_time,entry_quote_spend=basis,
                          exit_quote_receive=net,realized_pnl=pnl,
                          realized_return_pct=pnl/basis*D(100),
                          entry_price=p.fill.fill_price,exit_price=fill_price,
                          sold_base_quantity=quantity,residual_dust_quantity=ZERO,
                          holding_hours=D(str((open_time-p.fill.fill_time_utc).total_seconds()/3600)),
                          slot_count=p.slots)
            cash += net
            p.quantity -= quantity
            p.cost_basis -= basis
            if p.quantity <= 0:
                raise RuntimeError("R2_HOLD_PARTIAL_TRIM_UNEXPECTEDLY_FULL")
            signals.append(forced)
            fills.append(fill)
            trades.append(trade)
            self.events.append({"kind":"TRIM_EXECUTED","symbol":symbol,"episode":self.episode,
                                "signal_close_utc":close_time.isoformat(),
                                "fill_open_utc":open_time.isoformat(),
                                "base_quantity":str(quantity),"quote_received_net":str(net),
                                "fee_quote":str(fee),"modeled_adverse_quote":str(fill.modeled_spread_slippage),
                                "realized_pnl":str(pnl),"original_slots_retained":p.slots})
        return cash


def instrument(original):
    """Return research-only compiled native source; refuse source drift."""
    needles=(
      ("        if in_report and pending:\n",
       "        if in_report and (pending or R2_POLICY.pending_trim):\n"),
      ("            entries.sort(\n",
       """            cash = R2_POLICY.execute_pending(
                cash=cash, positions=positions, previous_points=previous_points,
                candles=candles, pending=pending, rules=rules, costs=costs,
                signals=signals, fills=fills, trades=trades, blocked=blocked,
                open_time=open_time)
            entries.sort(
"""),
      ("            new_pending: list[Signal] = []\n",
       """            R2_POLICY.on_close(
                equity=equity, hwm=closed_high_water,
                close_time=max(candle.close_time_utc for candle in row),
                positions=positions)
            new_pending: list[Signal] = []
"""),
      ("                signals.append(new_signal)\n",
       """                signals.append(new_signal)
                if new_signal.action is SignalAction.ENTER_LONG and not R2_POLICY.entry_allowed:
                    blocked.append(f"{new_signal.signal_id}:R2_HOLD_DEFENSIVE_NO_BUY")
                    continue
"""),
    )
    text=original
    for old,new in needles:
        if text.count(old)!=1:
            raise RuntimeError(f"R2_INSTRUMENT_UNEXPECTED_SOURCE_COUNT:{old[:50]!r}:{text.count(old)}")
        text=text.replace(old,new)
    if text==original:
        raise RuntimeError("R2_NOT_INSTRUMENTED")
    return text
