"""Pre-economic time-causal fixture QA for preregistered HOLD-003.
No financial case may run until this gate and frozen C0 identity pass.
"""
import unittest
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D

from research.r2_hold003.held_policy import HeldRiskKernel, CANDIDATE
from research.r2_hold001.test_hold001 import position, point, doopen, trigger, BASE, SYM
from hixton.backtest.models import CURRENT_COSTS, ExecutionRules
from hixton.domain.models import Candle

class LossOnlyNativeTrimMethodQA(unittest.TestCase):
    def setUp(self):
        self.assertEqual(CANDIDATE,"R2-D1-HOLD-003")

    def test_native_underwater_position_is_trimmed_once_with_proportional_basis(self):
        p=position();p.cost_basis=D("110")
        k,t=trigger(p,policy=HeldRiskKernel())
        cash,signals,fills,trades,blocked=doopen(k,p,t)
        self.assertEqual(len(fills),1)
        self.assertEqual(len(signals),1)
        self.assertEqual(len(trades),1)
        self.assertEqual(fills[0].base_quantity,D("2.5"))
        self.assertEqual(p.quantity,D("7.5"))
        self.assertEqual(p.cost_basis,D("82.5"))
        self.assertEqual(p.slots,1)
        self.assertEqual(trades[0].entry_quote_spend,D("27.5"))
        self.assertEqual(trades[0].realized_pnl,trades[0].exit_quote_receive-D("27.5"))
        self.assertEqual(cash,D("100")+trades[0].exit_quote_receive)
        self.assertEqual(sum(e["kind"]=="TRIM_EXECUTED" for e in k.events),1)

    def test_positive_held_position_not_trimmed_and_no_retry(self):
        p=position();p.cost_basis=D("90")
        k,t=trigger(p,policy=HeldRiskKernel())
        cash,signals,fills,trades,blocked=doopen(k,p,t)
        self.assertEqual(cash,D("100"))
        self.assertFalse(fills)
        self.assertFalse(trades)
        self.assertEqual(p.cost_basis,D("90"))
        self.assertEqual(p.quantity,D("10"))
        self.assertEqual(sum(e["kind"]=="TRIM_SKIPPED_NOT_UNDERWATER" for e in k.events),1)
        self.assertEqual(k.pending_trim,{})
        for j in range(1,75):
            k.on_close(equity=D("840"),hwm=D("1000"),
                close_time=t+timedelta(hours=j),positions={SYM:p})
        self.assertEqual(sum(e["kind"]=="TRIGGER" for e in k.events),1)

    def test_net_liquidation_equality_is_NOT_underwater(self):
        p=position()
        q=p.quantity;close=D("10")
        p.cost_basis=q*close*(D(1)-CURRENT_COSTS.adverse_price_rate)*(D(1)-CURRENT_COSTS.fee_rate)
        k,t=trigger(p,policy=HeldRiskKernel())
        _,_,fills,_,_=doopen(k,p,t)
        self.assertFalse(fills)
        self.assertEqual(sum(e["kind"]=="TRIM_SKIPPED_NOT_UNDERWATER" for e in k.events),1)

    def test_tiny_negative_net_liquidation_below_cost_is_eligible(self):
        p=position()
        p.cost_basis=p.quantity*D("10")*(D(1)-CURRENT_COSTS.adverse_price_rate)*(D(1)-CURRENT_COSTS.fee_rate)+D("0.000000001")
        k,t=trigger(p,policy=HeldRiskKernel())
        _,_,fills,_,_=doopen(k,p,t)
        self.assertEqual(len(fills),1)

    def _attempt_with_different_future_open(self, p, future_open):
        k,t=trigger(p,policy=HeldRiskKernel())
        open_time=t+timedelta(milliseconds=1)
        signals=[];fills=[];trades=[];blocked=[]
        candle=Candle(SYM,open_time,open_time+timedelta(hours=1)-timedelta(milliseconds=1),
            float(future_open),float(future_open)+1,float(future_open)-1,float(future_open),
            100.,1000.,100,True,"research")
        k.execute_pending(cash=D("100"),positions={SYM:p},
            previous_points={SYM:point(open_time)},candles={SYM:candle},
            pending=[],rules={SYM:ExecutionRules(step_size=D(".1"),min_qty=D(".1"),min_notional=D("1"))},
            costs=CURRENT_COSTS,signals=signals,fills=fills,trades=trades,
            blocked=blocked,open_time=open_time)
        return k,fills

    def test_future_open_crash_must_NOT_change_profitable_at_close_classification(self):
        p=position();p.cost_basis=D("90")
        k,fills=self._attempt_with_different_future_open(p,D("2"))
        self.assertFalse(fills)
        self.assertEqual(sum(e["kind"]=="TRIM_SKIPPED_NOT_UNDERWATER" for e in k.events),1)

    def test_future_open_rally_must_NOT_remove_prior_underwater_eligibility(self):
        p=position();p.cost_basis=D("110")
        k,fills=self._attempt_with_different_future_open(p,D("100"))
        self.assertEqual(len(fills),1)
        self.assertEqual(fills[0].reference_open,D("100"))
        self.assertEqual(sum(e["kind"]=="TRIM_EXECUTED" for e in k.events),1)

    def test_native_exit_wins_even_when_underwater(self):
        p=position();p.cost_basis=D("110")
        k,t=trigger(p,policy=HeldRiskKernel())
        cash,signals,fills,trades,blocked=doopen(k,p,t,reg_exit=True)
        self.assertFalse(fills);self.assertFalse(trades)
        self.assertEqual(cash,D("100"))
        self.assertEqual(sum(e["kind"]=="TRIM_SKIPPED_NATIVE_EXIT" for e in k.events),1)

    def test_market_minimum_filter_and_one_attempt(self):
        p=position();p.cost_basis=D("110")
        k,t=trigger(p,policy=HeldRiskKernel())
        _,_,fills,_,blocked=doopen(k,p,t,rules={SYM:ExecutionRules(step_size=D(".1"),min_notional=D("100"))})
        self.assertFalse(fills);self.assertTrue(blocked)
        self.assertEqual(k.pending_trim,{})
        self.assertEqual(p.quantity,D("10"))

    def test_delayed_fill_fails_closed(self):
        p=position();p.cost_basis=D("110")
        k,t=trigger(p,policy=HeldRiskKernel())
        with self.assertRaisesRegex(RuntimeError,"NOT_NEXT_NATIVE_OPEN"):
            k.execute_pending(cash=D("100"),positions={SYM:p},previous_points={},candles={},
                pending=[],rules={},costs=CURRENT_COSTS,signals=[],fills=[],trades=[],
                blocked=[],open_time=t+timedelta(hours=1,milliseconds=1))

    def test_rearm_requires_168_sequential_closed_hours_and_native_entry_never_frozen(self):
        p=position();p.cost_basis=D("110")
        k,t=trigger(p,policy=HeldRiskKernel())
        k.pending_trim={};k.pending_close=None
        for j in range(1,169):
            k.on_close(equity=D("950"),hwm=D("1000"),
                close_time=t+timedelta(hours=j),positions={SYM:p})
            self.assertTrue(k.entry_allowed)
        self.assertFalse(k.defensive)
        self.assertEqual(sum(e["kind"]=="REARM" for e in k.events),1)

    def test_missing_closed_price_fails_closed(self):
        p=position();p.cost_basis=D("110")
        k,t=trigger(p,policy=HeldRiskKernel());open_time=t+timedelta(milliseconds=1)
        badpoint=replace(point(open_time),candle=replace(point(open_time).candle,close=0.0))
        with self.assertRaisesRegex(RuntimeError,"INVALID_LAST_CLOSED_PRICE"):
            k.execute_pending(cash=D("100"),positions={SYM:p},
                previous_points={SYM:badpoint},candles={SYM:Candle(
                    SYM,open_time,open_time+timedelta(hours=1)-timedelta(milliseconds=1),
                    10.,10.5,9.5,10.,100.,1000.,100,True,"research")},
                pending=[],rules={},costs=CURRENT_COSTS,signals=[],fills=[],trades=[],
                blocked=[],open_time=open_time)

if __name__=="__main__":unittest.main(verbosity=2)
