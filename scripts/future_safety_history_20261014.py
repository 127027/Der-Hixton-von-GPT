"""Check finite research-only safety variants on the same examined history.

No real account, credentials, runtime changes or network. Not untouched holdout.
"""
import json,hashlib
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path
import hixton.backtest.portfolio as native
from hixton.backtest.continuity import load_continuity_history
from hixton.backtest.models import CURRENT_COSTS,STRESS_COSTS,ExecutionRules
from hixton.data.storage import CandleStore
from hixton.domain.versions import strategy_definition
from research_dd10_coins_20261013 import SnapshotOnly
from future_scenarios_additions_20261014 import entry_pause20
from future_scenarios_20261014 import OUT

def main():
    spec=json.loads(Path(r'C:\Users\andre\OneDrive\Desktop\Neuer Ordner\Pruefergebnisse\Coin-Nachoptimierung-20261013\Inputs.json').read_text())
    data=Path(spec['market_snapshot']);strategy=strategy_definition('v8r');rules={}
    start,end=(datetime.fromisoformat(spec[k]) for k in ('start','end'));seed=D(spec['portfolio_seed'])
    with CandleStore(data/'hixton-usdc.sqlite3',read_only=True) as db:
        for symbol in strategy.symbols:
            r=db.load_symbol_rules(symbol);rules[symbol]=ExecutionRules(r.tick_size,r.step_size,r.min_qty,r.min_notional)
    history=load_continuity_history(strategy=strategy,report_start_utc=start,report_end_utc=end,execution_rules=rules,native_database_path=data/'hixton-usdc.sqlite3',cache_path=data/'backtest-history.sqlite3',client=SnapshotOnly())
    contract={'variants':['current','exposure75','exposure50','entry_pause20'],'costs':['current','stress'],
        'start':start.isoformat(),'end':end.isoformat(),'seed_usdc':str(seed),
        'history_reused_not_holdout':True,'no_network':True,'no_orders':True}
    path=OUT/'History-Contract.json'
    if not path.exists():path.write_text(json.dumps(contract,indent=2),encoding='utf-8')
    results=[];result_path=OUT/'History-Comparison.json'
    if result_path.exists():results=json.loads(result_path.read_text())
    for variant in contract['variants']:
        for costs in (CURRENT_COSTS,STRESS_COSTS):
            if any(r['variant']==variant and r['cost']['name']==costs.name for r in results):continue
            original=native.evaluate_portfolio_risk
            if variant=='entry_pause20':native.evaluate_portfolio_risk=entry_pause20
            try:r=native.run_shared_portfolio_backtest(candles_by_symbol=history.candles_by_symbol,report_start_utc=start,report_end_utc=end,
                starting_cash=seed,target_notional=seed/2,execution_rules=rules,strategy=strategy,costs=costs,
                reinvest_profits=True,autonomous_spot=True,capital_exposure_fraction={'exposure75':D('.75'),'exposure50':D('.5')}.get(variant,D(1)))
            finally:native.evaluate_portfolio_risk=original
            row={'variant':variant,'cost':asdict(costs),'end_usdc':str(r.metrics.ending_equity),'close_dd_pct':str(r.metrics.max_drawdown_pct),
                'daily_or_extra_pause_hours':r.daily_paused_bars,'realized_lots':len(r.trades),'not_promoted':variant!='current'}
            results.append(row);result_path.write_text(json.dumps(results,indent=2,default=str),encoding='utf-8');print(row,flush=True)

if __name__=='__main__':main()
