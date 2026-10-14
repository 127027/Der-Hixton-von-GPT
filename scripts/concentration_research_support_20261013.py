"""Public-data-only concentration research helpers; never imported by the bot."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal as D
from hashlib import sha256

from hixton.backtest.models import Fill, Trade
from hixton.domain.models import SignalAction
from hixton.domain.strategy import HixtonStrategy


@dataclass(frozen=True)
class ConcentrationPolicy:
    min_equity: D
    dd_trigger: D = D(0)
    slots: int = 4
    trim_on_activation: bool = True
    oracle_start: datetime | None = None

    def __post_init__(self):
        if self.slots not in (3, 4, 6) or not self.min_equity.is_finite() or self.min_equity < 0:
            raise ValueError("invalid research concentration rule")
        if not self.dd_trigger.is_finite() or not 0 <= self.dd_trigger < 100:
            raise ValueError("invalid causal DD trigger")
        if self.oracle_start is not None and self.oracle_start.tzinfo is None:
            raise ValueError("oracle diagnostic needs timezone")

    def triggered(self, *, equity, high_water, previous_close):
        if previous_close is None:
            return False
        if self.oracle_start is not None:
            return previous_close >= self.oracle_start
        return (
            equity >= self.min_equity
            and (high_water - equity) / high_water * 100 >= self.dd_trigger
        )


def trim_positions(
    *,
    policy,
    positions,
    previous_points,
    candles,
    closed_equity,
    open_time,
    costs,
    rules,
    signals,
    fills,
    trades,
    round_down,
    audit,
):
    """ONE partial exit at NEXT open, quantity decided from previous closed bar.

    Partial sales are realized lots, not completed whole position cycles.
    Regular exits on this same open are skipped by the caller.
    """
    cash_gain = D(0)
    for sym, p in positions.items():
        point = previous_points[sym]
        assert point.candle.closed and point.candle.close_time_utc < open_time
        target_quantity = closed_equity / D(policy.slots) / D(str(point.candle.close))
        rule = rules[sym]
        p.allocation_units = 20 // policy.slots
        p.slots = 1
        if p.quantity <= target_quantity:
            continue
        sell = round_down(p.quantity - target_quantity, rule.step_size)
        reference = D(str(candles[sym].open))
        price = reference * (1 - costs.adverse_price_rate)
        gross = sell * price
        if sell < rule.min_qty or gross < rule.min_notional:
            continue
        forced = HixtonStrategy.signal_for(
            replace(point, flip_down=True, flip_up=False), is_long=True
        )
        if forced is None:
            raise RuntimeError("closed-bar trim signal unavailable")
        forced = replace(
            forced,
            signal_id=sha256(
                f"RESEARCH_CONCENTRATION_TRIM|{sym}|{point.candle.close_time_utc.isoformat()}|{open_time.isoformat()}".encode()
            ).hexdigest(),
        )
        basis = p.cost_basis * sell / p.quantity
        fee = gross * costs.fee_rate
        net = gross - fee
        fill = Fill(
            forced.signal_id,
            SignalAction.EXIT_LONG,
            open_time,
            reference,
            price,
            sell,
            gross,
            fee,
            sell * (reference - price),
        )
        trades.append(
            Trade(
                sym,
                p.signal.signal_id,
                forced.signal_id,
                p.fill.fill_time_utc,
                open_time,
                basis,
                net,
                net - basis,
                (net - basis) / basis * 100,
                p.fill.fill_price,
                price,
                sell,
                D(0),
                D(str((open_time - p.fill.fill_time_utc).total_seconds() / 3600)),
                1,
            )
        )
        signals.append(forced)
        fills.append(fill)
        cash_gain += net
        p.quantity -= sell
        p.cost_basis -= basis
        p.allocation_units = 20 // policy.slots
        p.slots = 1
        audit.append(
            {
                "kind": "PARTIAL_TRIM",
                "symbol": sym,
                "signal_id": forced.signal_id,
                "decision_close": point.candle.close_time_utc.isoformat(),
                "execution_open": open_time.isoformat(),
                "previous_equity": str(closed_equity),
                "previous_price": str(point.candle.close),
                "target_quantity": str(target_quantity),
                "sold_quantity": str(sell),
                "remaining_quantity": str(p.quantity),
                "released_cash": str(net),
                "realized_pnl": str(net - basis),
                "cost_basis_retained": str(p.cost_basis),
            }
        )
    return cash_gain
