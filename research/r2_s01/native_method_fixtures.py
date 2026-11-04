"""R2-S01 pre-economic native semantics checks. NOT an independent Dot4 approval."""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from decimal import Decimal as D
from types import SimpleNamespace as NS
from pathlib import Path

from research.r2_s01.native_s01_policy import S01Policy,instrument
from research.r2_s01.s01_predicate_prefix_fixtures import test as predicate_test

def run(bundle):
    predicate_test()
    root=Path(bundle)
    src=(root/"engine/src/hixton/backtest/portfolio.py").read_text()
    patched=instrument(src)
    assert "R2_S01.at_open" in patched and "execute_exit=execute_exit" in patched
    assert patched.index("for signal in exits:") < patched.index("R2_S01.at_open") < patched.index("entries.sort(")
    assert "if signal.symbol in positions:" in src
    assert "positions[signal.symbol] = _OpenTrade(" in src
    assert "del positions[signal.symbol]" in src
    assert "basis_fraction = sell_quantity / open_trade.quantity" in src
    assert "realized_basis = open_trade.cost_basis * basis_fraction" in src
    assert "dust[signal.symbol] += residual" in src

    t=datetime(2024,1,1,tzinfo=timezone.utc)
    cost=NS(adverse_price_rate=D("0.001"),fee_rate=D("0.001"))
    prices={"BTCUSDC":{t:(D("90"),D("94"),6)}}
    p=NS(quantity=D("0.5"),cost_basis=D("50"),slots=1)
    policy=S01Policy(features=prices,costs=cost)
    policy.on_close(close_time=t,positions={"BTCUSDC":p})
    assert list(policy.pending)==["BTCUSDC"]
    assert len(policy.events)==1 and policy.events[0]["remaining_native_basis"]=="50"
    # The equivalent 1-unit / 100-USDC lot must have identical signal semantics.
    policy2=S01Policy(features=prices,costs=cost)
    policy2.on_close(close_time=t,positions={"BTCUSDC":NS(quantity=D(1),cost_basis=D(100),slots=2)})
    assert list(policy2.pending)==["BTCUSDC"]
    # No signal for non-held positions, no signal on 4/6.
    policy3=S01Policy(features=prices,costs=cost)
    policy3.on_close(close_time=t,positions={})
    assert not policy3.pending
    policy4=S01Policy(features={"BTCUSDC":{t:(D(90),D(94),4)}},costs=cost)
    policy4.on_close(close_time=t,positions={"BTCUSDC":p})
    assert not policy4.pending
    policy5=S01Policy(features={"BTCUSDC":{t:(D(99),D(100),6)}},costs=cost)
    policy5.on_close(close_time=t,positions={"BTCUSDC":p})
    assert not policy5.pending

    # Fixed 24 elapsed hours after a confirmed native fill, not after warning.
    policy.cooldown_until["BTCUSDC"]=t+timedelta(milliseconds=1,hours=24)
    assert not policy.entry_allowed("BTCUSDC",t+timedelta(hours=23,milliseconds=1))
    assert policy.entry_allowed("BTCUSDC",t+timedelta(hours=24,milliseconds=1))
    assert policy.entry_allowed("ETHUSDC",t+timedelta(hours=1))
    s=NS(symbol="BTCUSDC",signal_id="test")
    blocked=[]
    assert not policy.filter_entries([s],t+timedelta(hours=1),blocked)
    assert blocked==["test:S01_COIN_COOLDOWN"]
    # Disabled mode must be no-op even with a synthetic cooldown value.
    off=S01Policy(features=prices,costs=cost,enabled=False)
    off.on_close(close_time=t,positions={"BTCUSDC":p})
    assert not off.pending and off.filter_entries([s],t,[])==[s]
    assert off.entry_allowed("BTCUSDC",t)
    # No future-bar contamination: further features never change the earlier decision.
    future={"BTCUSDC":dict(prices["BTCUSDC"])}
    future["BTCUSDC"][t+timedelta(hours=1)]=(D("100000"),D("9000"),0)
    pref=S01Policy(features=future,costs=cost)
    pref.on_close(close_time=t,positions={"BTCUSDC":p})
    assert pref.pending==policy2.pending
    print("S01_PRE_ECONOMIC_PREDICATE_AND_NATIVE_STRUCTURE_FIXTURES_PASS")
if __name__=="__main__":
    import sys
    run(sys.argv[1])
