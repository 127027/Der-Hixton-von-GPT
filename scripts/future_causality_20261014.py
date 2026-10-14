"""Future extension must not alter a finalized past decision or fill."""
import json
from dataclasses import replace
from decimal import Decimal as D
from datetime import timedelta
from hixton.backtest.models import CURRENT_COSTS,ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.domain.versions import strategy_definition
from future_scenarios_20261014 import candles,OUT,START

def main():
    strategy=strategy_definition('v8r');data,_=candles('common_crash_70',1701)
    rules={s:ExecutionRules(step_size=D('.00000001'),min_qty=D('.00000001'),min_notional=D(5)) for s in strategy.symbols}
    def run(d,hours):return run_shared_portfolio_backtest(candles_by_symbol=d,report_start_utc=START,report_end_utc=START+timedelta(hours=hours),starting_cash=D(1000),target_notional=D(500),costs=CURRENT_COSTS,execution_rules=rules,strategy=strategy,reinvest_profits=True,autonomous_spot=True)
    end=START+timedelta(hours=750)
    before={s:[b for b in bars if b.open_time_utc<end] for s,bars in data.items()}
    prefix=run(before,750);full=run(data,1800)
    assert tuple(p for p in full.equity_curve if p.time_utc<end)==prefix.equity_curve
    assert tuple(f for f in full.fills if f.fill_time_utc<end)==prefix.fills
    # Mutate only the as-yet unseen suffix, including the planned crash into a rally.
    mutated={s:[b if b.open_time_utc<end else replace(b,open=b.open*10,high=b.high*10,low=b.low*10,close=b.close*10) for b in bars] for s,bars in data.items()}
    changed=run(mutated,1800)
    assert tuple(p for p in changed.equity_curve if p.time_utc<end)==prefix.equity_curve
    assert tuple(f for f in changed.fills if f.fill_time_utc<end)==prefix.fills
    result={'checked_hours':750,'matching_fills_before_future':len(prefix.fills),'append_future_does_not_change_past':True,'replace_future_crash_with_rally_does_not_change_past':True,'no_orders':True}
    (OUT/'Causality.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(result)

if __name__=='__main__':main()
