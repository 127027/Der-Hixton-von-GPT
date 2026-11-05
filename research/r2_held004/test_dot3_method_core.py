import unittest
from decimal import Decimal as D
from dot3_method_core import eligible, partial_basis, target_qty, AttemptState
class MethodFixtures(unittest.TestCase):
    def setUp(self):
        self.k=dict(closes=[95]*6,ema72=[100]*6,held_qty='1',remaining_basis='100',adverse_price_rate='0',fee_rate='0',candle_complete=True,historical_contiguous=True,source_valid=True,regular_native_position=True)
    def check(self, **kw):
        x=dict(self.k);x.update(kw);return eligible(**x)
    def test_exact_four_percent(self): self.assertTrue(self.check(closes=[96]*6))
    def test_just_above_four_percent(self): self.assertFalse(self.check(closes=['96.0000001']*6))
    def test_four_of_six(self): self.assertFalse(self.check(closes=[95]*4+[101]*2))
    def test_five_of_six(self): self.assertTrue(self.check(closes=[101]+[95]*5))
    def test_profit(self): self.assertFalse(self.check(closes=[105]*6,ema72=[110]*6))
    def test_missing_or_unclosed(self):
        for field in ['candle_complete','historical_contiguous','source_valid','regular_native_position']: self.assertFalse(self.check(**{field:False}))
    def test_bad_history(self): self.assertFalse(self.check(closes=[95]*5))
    def test_zero_volume_flag(self): self.assertFalse(self.check(source_valid=False))
    def test_nan(self): self.assertFalse(self.check(closes=[95]*5+['NaN']))
    def test_prefix_invariance_interface(self): self.assertNotIn('next_open',self.k)
    def test_attempt_once_per_entry(self):
        s=AttemptState();self.assertTrue(s.register('BTC','id1'));self.assertFalse(s.register('BTC','id1'));self.assertTrue(s.register('BTC','id2'))
    def test_basis(self):
        sold,rem=partial_basis(held_qty='4',executed_qty='1',remaining_basis='100');self.assertEqual((sold,rem),(D('25'),D('75')))
    def test_invalid_fill(self):
        with self.assertRaises(ValueError): partial_basis(held_qty='4',executed_qty='5',remaining_basis='100')
    def test_target(self):self.assertEqual(target_qty('3'),D('.75'))
if __name__=='__main__':unittest.main()
