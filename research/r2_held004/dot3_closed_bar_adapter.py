"""R2-HELD-004 research-only causal closed-bar EMA72 adapter.

Method staging only: no native order hook, no finance runner, no METHOD_PASS.
The native snapshot loader remains research/r2_hold003/run_native.py.
"""
from decimal import Decimal as D

def closed_bar_warning(*, candles, held_qty, remaining_basis, adverse_price_rate,
                       fee_rate, regular_native_position, expected_close_utc):
    """Compute the sealed S01 predicate from a contiguous *completed* candle prefix.

    EMA is seeded by SMA of the first 72 completed closes, then recursively
    updated with alpha=2/73. The first 400 candles are required for original
    native warmup; no future candle or next-open is inspected.
    """
    from dot3_method_core import eligible
    if len(candles) < 400 or not regular_native_position:
        return False
    try:
        # Mandatory decision-time cutoff; never infer it from the last supplied bar.
        if expected_close_utc is None:
            return False
        prefix = candles
        # Future appended candles must not enter the decision prefix.
        matches = [i for i, bar in enumerate(candles)
                   if bar.close_time_utc == expected_close_utc]
        if len(matches) != 1:
            return False
        prefix = candles[:matches[0] + 1]
        # Warmup is a property of the decision-time prefix, not the supplied future suffix.
        if len(prefix) < 400:
            return False
        closes = []
        previous = None
        from datetime import timedelta
        for bar in prefix:
            if not bar.closed:
                return False
            if previous is not None and bar.open_time_utc != previous.open_time_utc + timedelta(hours=1):
                return False
            if bar.close_time_utc != bar.open_time_utc + timedelta(hours=1, milliseconds=-1):
                return False
            if bar.volume <= 0 or bar.quote_volume <= 0 or bar.trade_count <= 0:
                return False
            price = D(str(bar.close))
            if not price.is_finite() or price <= 0:
                return False
            closes.append(price)
            previous = bar
        alpha = D(2) / D(73)
        ema = sum(closes[:72], D(0)) / D(72)
        last_ema = []
        for idx, price in enumerate(closes):
            if idx < 71:
                continue
            if idx > 71:
                ema = alpha * price + (D(1) - alpha) * ema
            if idx >= len(closes) - 6:
                last_ema.append(ema)
        if len(last_ema) != 6:
            return False
        return eligible(closes=closes[-6:], ema72=last_ema,
                        held_qty=held_qty, remaining_basis=remaining_basis,
                        adverse_price_rate=adverse_price_rate, fee_rate=fee_rate,
                        candle_complete=True, historical_contiguous=True,
                        source_valid=True, regular_native_position=True)
    except (ValueError, TypeError, ArithmeticError, AttributeError, OverflowError):
        return False
