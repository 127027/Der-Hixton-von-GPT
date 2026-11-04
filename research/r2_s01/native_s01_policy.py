"""R2-D3-S01: frozen, research-only native exit hook; no second accounting engine.

The hook invokes f56's *actual* execute_exit closure after regular exits and
before entries. S01-disabled instrumentation must be fully identical to f56.
Requires the exact frozen source fingerprint checked by run_native.py.
"""
from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from hixton.domain.models import SignalAction
from hixton.domain.strategy import HixtonStrategy

D = Decimal
ONE = D("1")
THRESHOLD = D("-0.04")
COOLDOWN = timedelta(hours=24)
NAME = "R2-D3-S01"

class S01Policy:
    def __init__(self, *, features, costs, enabled=True):
        self.features = features
        self.costs = costs
        self.enabled = enabled
        self.pending = {}
        self.attempted_entries = set()
        self.cooldown_until = {}
        self.events = []
        self.last_close = None
        self.expected_cash_delta = D("0")
        self.native_fill_events = []

    def on_close(self, *, close_time, positions):
        """Evaluate only genuine held quantities and completed native OHLC."""
        if not self.enabled:
            return
        if self.last_close is not None and close_time - self.last_close != timedelta(hours=1):
            raise RuntimeError("S01_NONCONTIGUOUS_NATIVE_CLOSES")
        self.last_close = close_time
        if self.pending:
            raise RuntimeError("S01_UNEXECUTED_PREVIOUS_OPEN")
        for symbol, p in sorted(positions.items()):
            if p.quantity <= 0 or p.cost_basis <= 0:
                raise RuntimeError("S01_INVALID_NATIVE_COST_BASIS")
            f = self.features.get(symbol, {}).get(close_time)
            if f is None:
                raise RuntimeError("S01_MISSING_COMPLETE_HOURLY_FEATURE:" + symbol)
            close, ema, below = f
            if not (close.is_finite() and close > 0 and ema.is_finite()):
                raise RuntimeError("S01_INVALID_CLOSED_PRICE")
            net = p.quantity * close * (ONE - self.costs.adverse_price_rate) * (ONE - self.costs.fee_rate)
            net_return = net / p.cost_basis - ONE
            marker = (symbol, p.signal.signal_id)
            if below >= 5 and net_return <= THRESHOLD and marker not in self.attempted_entries:
                self.attempted_entries.add(marker)
                self.pending[symbol] = close_time
                self.events.append(dict(kind="TRIGGER", symbol=symbol, signal_close_utc=close_time.isoformat(),
                    native_quantity=str(p.quantity), remaining_native_basis=str(p.cost_basis),
                    net_return=str(net_return), persistence=below, native_slots=p.slots))

    def at_open(self, *, open_time, positions, previous_points, execute_exit, signals, fills, blocked):
        """Use the existing native f56 execute_exit, never a synthetic Fill or Trade."""
        self.expected_cash_delta = D("0")
        if not self.enabled or not self.pending:
            return
        queued = self.pending
        self.pending = {}
        for symbol, close_time in sorted(queued.items()):
            if open_time != close_time + timedelta(milliseconds=1):
                raise RuntimeError("S01_WRONG_NATIVE_EXECUTION_OPEN")
            if symbol not in positions:
                self.events.append(dict(kind="SKIPPED_REGULAR_EXIT", symbol=symbol,
                                        open_utc=open_time.isoformat()))
                continue
            point = previous_points.get(symbol)
            if point is None or not point.candle.closed or point.candle.close_time_utc != close_time:
                raise RuntimeError("S01_STALE_OR_FUTURE_NATIVE_POINT")
            native_signal = HixtonStrategy.signal_for(
                replace(point, flip_down=True, flip_up=False), is_long=True)
            if native_signal is None or native_signal.action is not SignalAction.EXIT_LONG:
                raise RuntimeError("S01_NATIVE_EXIT_SIGNAL_UNAVAILABLE")
            ident = hashlib.sha256(f"{NAME}|{symbol}|{close_time.isoformat()}".encode()).hexdigest()
            forced = replace(native_signal, signal_id=ident)
            signals.append(forced)
            before = len(fills)
            blocked_before = len(blocked)
            original_slots = positions[symbol].slots
            previous_quantity = positions[symbol].quantity
            previous_basis = positions[symbol].cost_basis
            previous_occupied_slots = sum(x.slots for x in positions.values())
            execute_exit(forced)
            actual_fills = [f for f in fills[before:] if f.signal_id == ident]
            if len(actual_fills) > 1:
                raise RuntimeError("S01_DUPLICATE_NATIVE_FILL")
            if len(actual_fills) == 1:
                if symbol in positions:
                    raise RuntimeError("S01_NATIVE_FILL_LEFT_OPEN_POSITION")
                fill = actual_fills[0]
                if fill.base_quantity <= 0 or fill.quote_value <= 0 or fill.fee_quote_equivalent < 0:
                    raise RuntimeError("S01_INVALID_NATIVE_CONFIRMED_FILL")
                if sum(x.slots for x in positions.values()) != previous_occupied_slots - original_slots:
                    raise RuntimeError("S01_NATIVE_SLOT_RELEASE_NOT_CONSERVED")
                self.expected_cash_delta += fill.quote_value - fill.fee_quote_equivalent
                self.cooldown_until[symbol] = open_time + COOLDOWN
                self.events.append(dict(kind="FILLED_NATIVE_FULL_EXIT", symbol=symbol,
                    fill_utc=open_time.isoformat(), cooldown_until_utc=self.cooldown_until[symbol].isoformat(),
                    native_fill_signal_id=ident, freed_native_slots=original_slots,
                    sold_quantity=str(fill.base_quantity), estimated_prior_held_quantity=str(previous_quantity),
                    native_prior_remaining_basis=str(previous_basis),
                    native_quote_value=str(fill.quote_value),native_fee_quote=str(fill.fee_quote_equivalent),
                    native_net_cash_delta=str(fill.quote_value-fill.fee_quote_equivalent)))
            else:
                native_rejections = [reason for reason in blocked[blocked_before:]
                                     if reason.startswith(ident + ":")]
                if not native_rejections:
                    self.events.append(dict(kind="UNKNOWN_NATIVE_EXECUTION",symbol=symbol,
                        open_utc=open_time.isoformat(),still_regular_held=symbol in positions,
                        cooldown_activated=False))
                    raise RuntimeError("S01_UNRESOLVED_NATIVE_EXECUTION_NO_FILL_OR_REJECTION")
                self.events.append(dict(kind="REJECTED_OR_DUST_NO_FILL",symbol=symbol,
                    open_utc=open_time.isoformat(),still_regular_held=symbol in positions,
                    native_rejections=native_rejections,cooldown_activated=False,
                    native_cash_delta="0"))
                # Explicit rejection or dust only; no confirmed sale, no cooldown.

    def verify_cash_after(self, *, before, after):
        if not self.enabled:
            return
        if after-before != self.expected_cash_delta:
            raise RuntimeError(f"S01_NATIVE_CASH_DELTA_MISMATCH:{after-before}:{self.expected_cash_delta}")

    def entry_allowed(self, symbol, at):
        return not self.enabled or at >= self.cooldown_until.get(symbol, at)

    def filter_entries(self, entries, at, blocked):
        if not self.enabled:
            return entries
        kept = []
        for s in entries:
            if self.entry_allowed(s.symbol, at):
                kept.append(s)
            else:
                blocked.append(f"{s.signal_id}:S01_COIN_COOLDOWN")
                self.events.append(dict(kind="BLOCKED_ENTRY_COIN_COOLDOWN",symbol=s.symbol,
                                        at_utc=at.isoformat()))
        return kept

def instrument(original):
    """Inject hooks into verified f56 text; refuse any unexpected source layout."""
    needles = (
        ("        if in_report and pending:\n",
         "        if in_report and (pending or R2_S01.pending):\n"),
        ("            entries.sort(\n",
         """            _s01_native_cash_before = cash
            R2_S01.at_open(open_time=open_time, positions=positions,
                previous_points=previous_points, execute_exit=execute_exit,
                signals=signals, fills=fills, blocked=blocked)
            R2_S01.verify_cash_after(before=_s01_native_cash_before, after=cash)
            entries = R2_S01.filter_entries(entries, open_time, blocked)
            entries.sort(
"""),
        ("            new_pending: list[Signal] = []\n",
         """            R2_S01.on_close(
                close_time=max(candle.close_time_utc for candle in row),
                positions=positions)
            new_pending: list[Signal] = []
"""),
        ("                new_pending.append(new_signal)\n",
         """                if (new_signal.action is SignalAction.ENTER_LONG
                        and not R2_S01.entry_allowed(new_signal.symbol,
                            max(candle.close_time_utc for candle in row) + timedelta(milliseconds=1))):
                    blocked.append(f"{new_signal.signal_id}:S01_COIN_COOLDOWN")
                    continue
                new_pending.append(new_signal)
"""),
    )
    result=original
    for old,new in needles:
        if result.count(old)!=1:
            raise RuntimeError(f"S01_UNEXPECTED_FROZEN_SOURCE_LAYOUT:{old[:45]}:{result.count(old)}")
        result=result.replace(old,new)
    # timedelta required by injected native source; add import without touching the original file.
    marker="from datetime import datetime\n"
    if result.count(marker)!=1:raise RuntimeError("S01_DATETIME_SOURCE_DRIFT")
    return result.replace(marker,"from datetime import datetime, timedelta\n")
