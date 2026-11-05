"""Research-only R2-HELD-004 pure method core; NOT native execution binding."""
from decimal import Decimal
from dataclasses import dataclass, field
D = Decimal
@dataclass
class AttemptState:
    attempted: set = field(default_factory=set)
    def register(self, symbol, entry_id):
        key = (symbol, entry_id)
        if key in self.attempted: return False
        self.attempted.add(key)
        return True
def eligible(*, closes, ema72, held_qty, remaining_basis, adverse_price_rate,
             fee_rate, candle_complete, historical_contiguous, source_valid,
             regular_native_position):
    """Only closed candles; caller must independently verify EMA seed and warmup."""
    if not (candle_complete and historical_contiguous and source_valid and regular_native_position): return False
    if len(closes) != 6 or len(ema72) != 6: return False
    try:
        q, basis = D(str(held_qty)), D(str(remaining_basis))
        price = D(str(closes[-1]))
        adverse, fee = D(str(adverse_price_rate)), D(str(fee_rate))
        if q <= 0 or basis <= 0 or price <= 0 or not (D(0) <= adverse < 1) or not (D(0) <= fee < 1): return False
        c = [D(str(x)) for x in closes]
        e = [D(str(x)) for x in ema72]
        if any(not v.is_finite() or v <= 0 for v in c + e): return False
        if sum(x < y for x,y in zip(c,e)) < 5: return False
        return q * price * (1-adverse) * (1-fee) / basis - 1 <= D('-0.04')
    except (ArithmeticError, ValueError, TypeError): return False
def partial_basis(*, held_qty, executed_qty, remaining_basis):
    q, sold, basis = map(lambda x:D(str(x)), (held_qty, executed_qty, remaining_basis))
    if not all(x.is_finite() for x in (q,sold,basis)) or q <= 0 or sold <= 0 or sold > q or basis <= 0: raise ValueError('invalid partial fill')
    removed = basis * sold / q
    return removed, basis - removed
def target_qty(held_qty):
    q=D(str(held_qty))
    if not q.is_finite() or q <= 0: raise ValueError('invalid quantity')
    return q / D(4)
