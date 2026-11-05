"""Method-only closed-prefix fixtures; NOT native C0 parity or Dot4 METHOD_PASS."""
import unittest
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from dot3_closed_bar_adapter import closed_bar_warning

@dataclass
class Bar:
    open_time_utc: object
    close_time_utc: object
    close: float = 95.
    volume: float = 10.
    quote_volume: float = 950.
    trade_count: int = 2
    closed: bool = True

def series(n=400):
    start=datetime(2024,1,1,tzinfo=timezone.utc)
    return [Bar(start+timedelta(hours=i),
                start+timedelta(hours=i+1,milliseconds=-1)) for i in range(n)]

def decision(bars, **changes):
    args=dict(candles=bars,held_qty='1',remaining_basis='100',
              adverse_price_rate='0',fee_rate='0',regular_native_position=True,
              expected_close_utc=bars[-1].close_time_utc)
    args.update(changes)
    return closed_bar_warning(**args)

class ClosedPrefixFixtures(unittest.TestCase):
    def test_seeded_ema_400_hour_warmup(self):
        self.assertTrue(decision(series()))
        self.assertFalse(decision(series(399)))
    def test_genuine_future_append_prefix_invariance(self):
        past=series()
        result=decision(past)
        future=series(430)
        for b in future[400:]:
            b.close=100000.
        self.assertEqual(result,decision(future[:400]))
        self.assertTrue(result)
    def test_stale_close_rejected(self):
        x=series()
        self.assertFalse(decision(x,expected_close_utc=x[-2].close_time_utc))
    def test_gap_rejected(self):
        x=series();x[300].open_time_utc+=timedelta(hours=1)
        self.assertFalse(decision(x))
    def test_unclosed_rejected(self):
        x=series();x[-1].closed=False
        self.assertFalse(decision(x))
    def test_zero_volume_rejected(self):
        x=series();x[300].quote_volume=0
        self.assertFalse(decision(x))
    def test_no_regular_position(self):
        self.assertFalse(decision(series(),regular_native_position=False))
    def test_exact_5_of_6(self):
        x=series()
        for i in (395,):x[i].close=120.
        self.assertTrue(decision(x))
    def test_future_open_not_used(self):
        x=series()
        self.assertTrue(decision(x))
if __name__=='__main__':
    unittest.main()
