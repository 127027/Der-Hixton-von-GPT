"""Research-only pure S01 closed-candle predicate. No trading or native order patch.

The native runner must supply only fully closed chronological candles, a genuine
regular held position, remaining proportional native cost basis and original
CostModel rates. This module never opens or closes positions.
"""
from datetime import timedelta
from decimal import Decimal as D

ALPHA = D(2) / D(73)

def held_s01_warning(closes, *, quantity, remaining_cost_basis,
                     adverse_price_rate, fee_rate, regular_held=True):
    """closes: chronological [(timezone-aware close_time_utc, Decimal close)].

    Strict fail-closed on absent bars, invalid basis, noncontiguous time or
    incomplete EMA seed. Caller must enforce original 400h engine warmup.
    """
    if not regular_held or len(closes) < 77:
        return False
    if quantity <= 0 or remaining_cost_basis <= 0:
        return False
    if not (D(0) <= adverse_price_rate < D(1) and D(0) <= fee_rate < D(1)):
        return False
    if any(t.tzinfo is None or not p.is_finite() or p <= 0 for t, p in closes):
        return False
    if any(b[0] - a[0] != timedelta(hours=1) for a, b in zip(closes, closes[1:])):
        return False
    ema = sum((p for _, p in closes[:72]), D(0)) / D(72)
    below = [closes[71][1] < ema]
    for _, price in closes[72:]:
        ema = ALPHA * price + (D(1) - ALPHA) * ema
        below.append(price < ema)
    net_close_liquidation = (quantity * closes[-1][1] *
                             (D(1) - adverse_price_rate) * (D(1) - fee_rate))
    return sum(below[-6:]) >= 5 and net_close_liquidation / remaining_cost_basis - 1 <= D("-0.04")
