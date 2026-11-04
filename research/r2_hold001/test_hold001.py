"""Pre-economic QA for R2-D1-HOLD-001 using native f56 domain structures."""
import hashlib, unittest
from datetime import UTC,datetime,timedelta
from decimal import Decimal as D
from types import SimpleNamespace

from hixton.backtest.models import ExecutionRules, CURRENT_COSTS, Fill, SignalAction
from hixton.domain.models import Candle,IndicatorPoint,TrendState
from hixton.domain.market_rules import market_order_block_reason
from research.r2_hold001.held_policy import HeldRiskKernel,instrument,CANDIDATE

BASE=datetime(2026,10,22,13,tzinfo=UTC)
SYM="BTCUSDC"
def point(t):
    candle=Candle(SYM,t-timedelta(hours=1),t-timedelta(milliseconds=1),
                  10.,10.5,9.5,10.,100.,1000.,100,True,"research")
    return IndicatorPoint(symbol=SYM,strategy_version="HIXTON-V8-QA",index=420,
        candle=candle,abs_cmo=.2,vidya_raw=10.,vidya=10.,true_range=1.,
        atr=1.,upper=12.,lower=8.,trend=TrendState.UP,
        flip_up=False,flip_down=False,breakout_strength=None,
        rank_strength=None,tradable=True)
def position():
    return SimpleNamespace(quantity=D("10"),cost_basis=D("100"),
      signal=SimpleNamespace(signal_id="NATIVE_ENTRY_SIGNAL"),
      fill=SimpleNamespace(fill_time_utc=BASE-timedelta(days=1),fill_price=D("10")),
      slots=1,allocation_units=10)
def trigger(p, *, policy=None):
    k=policy or HeldRiskKernel()
    for i in range(72):
        close=BASE+timedelta(hours=i+1)-timedelta(milliseconds=1)
        k.on_close(equity=D("850"),hwm=D("1000"),close_time=close,positions={SYM:p})
    return k,close
def doopen(k,p,close,*,reg_exit=False,rules=None):
    nextopen=close+timedelta(milliseconds=1)
    f=[];s=[];t=[];b=[]
    if reg_exit:p=None
    book={} if p is None else {SYM:p}
    result=k.execute_pending(cash=D("100"),positions=book,
        previous_points={SYM:point(nextopen)},candles={SYM:Candle(
            SYM,nextopen,nextopen+timedelta(hours=1)-timedelta(milliseconds=1),
            10.,10.5,9.5,10.,100.,1000.,100,True,"research")},
        pending=[],rules=rules or {SYM:ExecutionRules(step_size=D("0.1"),min_qty=D("0.1"),min_notional=D("1"))},
        costs=CURRENT_COSTS,signals=s,fills=f,trades=t,blocked=b,open_time=nextopen)
    return result,s,f,t,b

class MethodologyTest(unittest.TestCase):
    def test_exact_closed_hour_trigger_and_nonrepeat(self):
        p=position();k=HeldRiskKernel()
        for i in range(71):
            k.on_close(equity=D("850"),hwm=D("1000"),
                       close_time=BASE+timedelta(hours=i+1)-timedelta(milliseconds=1),positions={SYM:p})
        self.assertTrue(k.entry_allowed);self.assertFalse(k.pending_trim)
        t=BASE+timedelta(hours=72)-timedelta(milliseconds=1)
        k.on_close(equity=D("850"),hwm=D("1000"),close_time=t,positions={SYM:p})
        self.assertFalse(k.entry_allowed);self.assertEqual(k.pending_trim[SYM],D("2.50"))
        for j in range(1,100):
            k.on_close(equity=D("800"),hwm=D("1000"),close_time=t+timedelta(hours=j),positions={SYM:p})
        self.assertEqual(sum(e["kind"]=="TRIGGER" for e in k.events),1)

    def test_native_partial_book_and_fees_exactly_once(self):
        p=position();k,t=trigger(p)
        cash,signals,fills,trades,blocked=doopen(k,p,t)
        self.assertEqual(len(signals),1);self.assertEqual(len(fills),1)
        self.assertEqual(len(trades),1);self.assertFalse(blocked)
        f=fills[0];v=trades[0]
        self.assertEqual(f.action,SignalAction.EXIT_LONG)
        self.assertEqual(f.base_quantity,D("2.5"));self.assertEqual(p.quantity,D("7.5"))
        self.assertEqual(p.cost_basis,D("75"))
        self.assertEqual(p.slots,1);self.assertEqual(p.allocation_units,10)
        self.assertEqual(v.entry_quote_spend,D("25"))
        self.assertEqual(f.fee_quote_equivalent,f.quote_value*CURRENT_COSTS.fee_rate)
        self.assertEqual(v.realized_pnl,v.exit_quote_receive-v.entry_quote_spend)
        self.assertEqual(cash,D("100")+v.exit_quote_receive)
        # A second attempt next hour must never sell again.
        self.assertEqual(k.pending_trim,{})
        self.assertEqual(k.execute_pending(cash=cash,positions={SYM:p},previous_points={},
              candles={},pending=[],rules={},costs=CURRENT_COSTS,signals=[],fills=[],
              trades=[],blocked=[],open_time=t+timedelta(hours=1)),cash)

    def test_native_full_exit_preempts_research_sale(self):
        p=position();k,t=trigger(p)
        cash,signals,fills,trades,blocked=doopen(k,p,t,reg_exit=True)
        self.assertEqual(cash,D("100"));self.assertFalse(fills);self.assertFalse(trades)
        self.assertTrue(any(e["kind"]=="TRIM_SKIPPED_NATIVE_EXIT" for e in k.events))

    def test_native_minimum_filter_does_not_create_retries(self):
        p=position();k,t=trigger(p)
        # Native rule rejects 2.5 units * price ~25 < minimum notional 100.
        cash,signals,fills,trades,blocked=doopen(k,p,t,rules={
            SYM:ExecutionRules(step_size=D(".1"),min_notional=D("100"))})
        self.assertFalse(fills);self.assertTrue(blocked);self.assertEqual(p.quantity,D("10"))
        self.assertFalse(k.pending_trim)

    def test_rearm_after_168_consecutive_clear_hours(self):
        p=position();k,t=trigger(p)
        k.pending_trim={};k.pending_close=None
        for i in range(167):
            k.on_close(equity=D("950"),hwm=D("1000"),close_time=t+timedelta(hours=i+1),positions={SYM:p})
        self.assertFalse(k.entry_allowed)
        k.on_close(equity=D("950"),hwm=D("1000"),close_time=t+timedelta(hours=168),positions={SYM:p})
        self.assertTrue(k.entry_allowed)
        self.assertEqual(sum(e["kind"]=="REARM" for e in k.events),1)
        for i in range(72):
            k.on_close(equity=D("850"),hwm=D("1000"),
                       close_time=t+timedelta(hours=169+i),positions={SYM:p})
        self.assertEqual(sum(e["kind"]=="TRIGGER" for e in k.events),2)

    def test_future_bar_gap_fail_closed(self):
        k=HeldRiskKernel();t=BASE+timedelta(hours=1)-timedelta(milliseconds=1)
        k.on_close(equity=D("900"),hwm=D("1000"),close_time=t,positions={})
        with self.assertRaisesRegex(RuntimeError,"NONCONTIGUOUS"):
            k.on_close(equity=D("900"),hwm=D("1000"),close_time=t+timedelta(hours=2),positions={})

    def test_delayed_fill_fail_closed(self):
        p=position();k,t=trigger(p)
        with self.assertRaisesRegex(RuntimeError,"NOT_NEXT_NATIVE_OPEN"):
            k.execute_pending(cash=D("1"),positions={SYM:p},previous_points={},candles={},
              pending=[],rules={},costs=CURRENT_COSTS,signals=[],fills=[],trades=[],blocked=[],
              open_time=t+timedelta(hours=1, milliseconds=1))

    def test_control_hook_is_identity_and_native_code_unmodified(self):
        original=("        if in_report and pending:\n"+
          "            entries.sort(\n"+"            new_pending: list[Signal] = []\n"+
          "                signals.append(new_signal)\n")
        patched=instrument(original)
        self.assertIn("R2_POLICY.execute_pending",patched)
        self.assertIn("R2_POLICY.on_close",patched)
        self.assertNotEqual(patched,original)
        with self.assertRaisesRegex(RuntimeError,"UNEXPECTED_SOURCE_COUNT"):
            instrument(patched)
        k=HeldRiskKernel(enabled=False)
        k.on_close(equity=D("850"),hwm=D("1000"),close_time=BASE,positions={SYM:position()})
        self.assertTrue(k.entry_allowed);self.assertEqual(k.pending_trim,{})

if __name__=="__main__":
    unittest.main(verbosity=2)
