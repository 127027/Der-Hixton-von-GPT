"""Build research copy from the unchanged native source, with asserted hook sites."""
from pathlib import Path
source=Path('src/hixton/backtest/portfolio.py').read_text(encoding='utf-8')
source=source.replace('"""Chronological shared-cash max-budget backtest for the canonical ten USDC markets."""','"""Instrumented native concentration research copy; no product/runtime use."""')
source=source.replace('from hixton.backtest.engine import candle_snapshot_sha256','from concentration_research_support_20261013 import ConcentrationPolicy, trim_positions\n\nfrom hixton.backtest.engine import candle_snapshot_sha256')
source=source.replace('    capital_exposure_fraction: Decimal = Decimal("1"),\n)', '    capital_exposure_fraction: Decimal = Decimal("1"),\n    research_policy: ConcentrationPolicy | None = None,\n    research_audit: list[dict] | None = None,\n)')
source=source.replace('    closed_high_water = starting_cash\n','    closed_high_water = starting_cash\n    research_active = False\n    research_events = []\n    last_eligible_entries = ()\n    if research_policy is not None and (not weighted or not autonomous_spot or not reinvest_profits):\n        raise ValueError("concentration research requires current weighted full-equity strategy")\n')
needle='        if in_report and pending:\n'
insert='''        if in_report and research_policy is not None and not research_active:
            last_close = max((p.candle.close_time_utc for p in previous_points.values()), default=None)
            if research_policy.triggered(equity=closed_equity, high_water=closed_high_water, previous_close=last_close):
                research_active = True
                research_events.append({"kind":"SWITCH", "decision_close":last_close.isoformat(),
                    "execution_open":open_time.isoformat(), "previous_equity":str(closed_equity),
                    "previous_dd_pct":str((closed_high_water-closed_equity)/closed_high_water*100),
                    "slots":research_policy.slots, "oracle":research_policy.oracle_start is not None})
                if research_policy.trim_on_activation:
                    regular_exits = {s.symbol for s in pending if s.action is SignalAction.EXIT_LONG}
                    trim_subset = {s:p for s,p in positions.items() if s not in regular_exits}
                    cash += trim_positions(policy=research_policy, positions=trim_subset,
                        previous_points=previous_points, candles=candles, closed_equity=closed_equity,
                        open_time=open_time, costs=costs, rules=rules, signals=signals,
                        fills=fills, trades=trades, round_down=_round_down, audit=research_events)

        last_eligible_entries = ()
'''
assert source.count(needle)==1
source=source.replace(needle,insert+needle)
needle='            for signal in entries:\n'
insert='''            last_eligible_entries = tuple(s.symbol for s in entries if s.symbol not in positions)
            if research_active:
                assert research_policy is not None
                unit_weight = 20 // research_policy.slots
                free_capacity = max(0, 20 - sum(position_units(p.slots,p.allocation_units) for p in positions.values()))
                available = min(free_capacity // unit_weight, max(0,research_policy.slots-len(positions)))
                unique_entries = tuple(dict.fromkeys(last_eligible_entries))
                allocations = {s:unit_weight for s in unique_entries[:available]}
                split = True
'''
assert source.count(needle)==1
source=source.replace(needle,insert+needle)
needle='                reference = _d(candles[signal.symbol].open)\n'
insert='''                if research_active:
                    assert research_policy is not None
                    budget = size_spot_entry(equity=reinvestment_capital(equity=equity_at_open,
                        starting_cash=starting_cash, profit_fraction=profit_reinvestment_fraction),
                        free_quote=cash, slots=research_policy.slots, allocated_slots=1,
                        reserve_fraction=Decimal(1)-entry_fraction)
'''
assert source.count(needle)==2
before,after=source.rsplit(needle,1)
source=before+insert+needle+after
needle='            equity = cash + position_value\n'
insert='''            if research_audit is not None:
                research_audit.append({"time":max(c.close_time_utc for c in row).isoformat(),
                    "cash":str(cash), "equity":str(cash+position_value),
                    "previous_equity":str(closed_equity),
                    "previous_dd_pct":str((closed_high_water-closed_equity)/closed_high_water*100),
                    "active":research_active, "eligible_entries":last_eligible_entries,
                    "positions":{s:{"quantity":str(p.quantity), "value":str(p.quantity*_d(candles[s].close)),
                        "cost_basis":str(p.cost_basis), "units":p.allocation_units} for s,p in positions.items()},
                    "events":tuple(research_events)})
                research_events.clear()
'''
assert source.count(needle)==1
source=source.replace(needle,insert+needle)
Path('scripts/concentration_portfolio_20261013.py').write_text(source,encoding='utf-8')
