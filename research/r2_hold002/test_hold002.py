"""Before economic runs: pure unchanged-native-buy ablation QA."""
import unittest
from datetime import datetime,timedelta,UTC
from decimal import Decimal as D
from research.r2_hold002.held_policy import HeldRiskKernel,CANDIDATE,instrument
from research.r2_hold001.test_hold001 import point,position,doopen,BASE,SYM

class ExitOnlyAblationQA(unittest.TestCase):
    def setup_trigger(self):
        p=position();k=HeldRiskKernel()
        for i in range(72):
            k.on_close(equity=D("850"),hwm=D("1000"),
                       close_time=BASE+timedelta(hours=i+1)-timedelta(milliseconds=1),
                       positions={SYM:p})
        return k,p,BASE+timedelta(hours=72)-timedelta(milliseconds=1)

    def test_native_entry_gate_unaffected_during_defensive_episode(self):
        k,p,t=self.setup_trigger()
        self.assertTrue(k.defensive)
        self.assertTrue(k.entry_allowed)
        self.assertEqual(CANDIDATE,"R2-D1-HOLD-002")
        self.assertEqual(len(k.pending_trim),1)
        self.assertEqual(k.pending_trim[SYM],D("2.5"))
        self.assertEqual(k.events[-1]["new_entries_gate"],"UNCHANGED_NATIVE_BUY_RULES")

    def test_native_partial_exit_allocation_and_fees(self):
        k,p,t=self.setup_trigger()
        cash,s,f,trades,blocked=doopen(k,p,t)
        self.assertEqual(len(f),1);self.assertFalse(blocked)
        self.assertEqual(f[0].base_quantity,D("2.5"))
        self.assertEqual(p.quantity,D("7.5"))
        self.assertEqual(p.cost_basis,D("75"))
        self.assertEqual(p.slots,1)
        self.assertTrue(k.entry_allowed)
        self.assertEqual(cash,D("100")+trades[0].exit_quote_receive)

    def test_no_repeated_sell_when_dd_persists(self):
        k,p,t=self.setup_trigger()
        doopen(k,p,t)
        for j in range(1,150):
            k.on_close(equity=D("840"),hwm=D("1000"),close_time=t+timedelta(hours=j),positions={SYM:p})
        self.assertEqual(sum(e["kind"]=="TRIGGER" for e in k.events),1)
        self.assertEqual(sum(e["kind"]=="TRIM_EXECUTED" for e in k.events),1)
        self.assertTrue(k.entry_allowed)

    def test_native_full_exit_wins(self):
        k,p,t=self.setup_trigger()
        cash,s,f,trades,blocked=doopen(k,p,t,reg_exit=True)
        self.assertFalse(f);self.assertFalse(trades);self.assertEqual(cash,D("100"))
        self.assertTrue(k.entry_allowed)

    def test_exact_rearm_does_not_affect_native_buy_permissions(self):
        k,p,t=self.setup_trigger()
        k.pending_trim={};k.pending_close=None
        for j in range(1,169):
            k.on_close(equity=D("950"),hwm=D("1000"),close_time=t+timedelta(hours=j),positions={SYM:p})
            self.assertTrue(k.entry_allowed)
        self.assertFalse(k.defensive)
        self.assertEqual(sum(e["kind"]=="REARM" for e in k.events),1)

if __name__=="__main__":unittest.main(verbosity=2)
