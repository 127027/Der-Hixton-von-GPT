"""Transparent adversarial additions after observing a missing-ownership case.

The first BTC crash did NOT hit a held coin, so it cannot certify diversification.
This separate catalogue explicitly forces only BTC to trend before its collapse.
No original scenario or result is silently changed. Protection is research-only.
"""
import argparse,csv,gzip,hashlib,json,math,random
from dataclasses import asdict,replace
from decimal import Decimal as D
from datetime import timedelta
from pathlib import Path
import hixton.backtest.portfolio as native
from hixton.backtest.models import CURRENT_COSTS,STRESS_COSTS,ExecutionRules
from hixton.domain.models import Candle
from hixton.domain.risk import evaluate_portfolio_risk
from hixton.domain.versions import strategy_definition
from hixton.domain.strategy import evaluate_batch
from hixton.paper.engine import initialize_paper_at_latest,process_new_closed_points,load_paper_portfolio
from hixton.paper.storage import PaperStore
from hixton.paper.models import PaperSettings
from future_scenarios_20261014 import OUT,START,WARM,PRICES,measure,candles,VARIANTS

def owned_crash():
    strategy=strategy_definition('v8r');result={s:[] for s in strategy.symbols}
    for s in strategy.symbols:
        price=PRICES[s]
        for t in range(-WARM,2400):
            at=START+timedelta(hours=t);op=price
            if t<150:change=-.0002
            elif t<800:change=.002 if s=='BTCUSDC' else -.00002
            else:change=-.00003
            if t==800 and s=='BTCUSDC':op*=.01
            cl=op*math.exp(change);lo=min(op,cl)*.9993;hi=max(op,cl)*1.0007
            result[s].append(Candle(s,at,at+timedelta(hours=1)-timedelta(milliseconds=1),op,hi,lo,cl,1000000/cl,1000000,1000,True,'SYNTHETIC_OFFLINE_NOT_BINANCE'));price=cl
    return result,[{'hour':800,'kind':'OWNED_BTC_99_PERCENT_GAP_OTHER_COINS_NOT_CRASHED'}]

def chronic():
    rng=random.Random(2718);strategy=strategy_definition('v8r');result={s:[] for s in strategy.symbols}
    for j,s in enumerate(strategy.symbols):
        price=PRICES[s]
        for t in range(-WARM,43824):
            at=START+timedelta(hours=t);op=price
            if t<0:change=-.0002
            else:
                phase=t%31
                change=(.006 if phase<20 else math.log(.85) if phase==20 else 0)+rng.gauss(0,.00015)
            # Accumulating costs and small losers; no initial windfall rally.
            cl=max(1e-8,op*math.exp(change));lo=min(op,cl)*.9993;hi=max(op,cl)*1.0007
            result[s].append(Candle(s,at,at+timedelta(hours=1)-timedelta(milliseconds=1),op,hi,lo,cl,1000000/cl,1000000,1000,True,'SYNTHETIC_OFFLINE_NOT_BINANCE'));price=cl
    return result,[]

def entry_pause20(state,*,equity,at):
    decision=evaluate_portfolio_risk(state,equity=equity,at=at)
    # Diagnostics unchanged; own existing exits remain regular strategy exits.
    return replace(decision,daily_paused=decision.daily_paused or decision.drawdown_pct>=D(20))

def run(name,budget,variant,cost):
    dest=OUT/'additions'/f'{name}-b{budget}-{variant}-{cost}'
    if (dest/'Result.json').exists():return
    dest.mkdir(parents=True,exist_ok=True)
    if name=='owned_coin_99':data,events=owned_crash();hours=2400
    elif name=='chronic_chop_no_initial_rally':data,events=chronic();hours=43824
    else:data,events=candles(name,1701);hours=len(next(iter(data.values())))-WARM
    strategy=strategy_definition('v8r');amount=D(budget);model=CURRENT_COSTS if cost=='current' else STRESS_COSTS
    rules={s:ExecutionRules(step_size=D('.00000001'),min_qty=D('.00000001'),min_notional=D(5)) for s in strategy.symbols}
    original=native.evaluate_portfolio_risk
    if variant=='entry_pause20':native.evaluate_portfolio_risk=entry_pause20
    try:r=native.run_shared_portfolio_backtest(candles_by_symbol=data,report_start_utc=START,report_end_utc=START+timedelta(hours=hours),
        starting_cash=amount,target_notional=amount/2,costs=model,execution_rules=rules,strategy=strategy,
        reinvest_profits=True,autonomous_spot=True,capital_exposure_fraction=VARIANTS.get(variant,D(1)))
    finally:native.evaluate_portfolio_risk=original
    row={'scenario':name,'budget':budget,'variant':variant,'cost':asdict(model),'hours':hours,
        'synthetic_not_forecast':True,'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'research_only_protection':variant=='entry_pause20',**measure(r,data,amount,events)}
    if name=='owned_coin_99':assert row['ownership_at_event'][0]['owned_symbols']==['BTCUSDC'],row['ownership_at_event']
    (dest/'Result.json').write_text(json.dumps(row,indent=2,default=str),encoding='utf-8')
    with gzip.open(dest/'Equity.csv.gz','wt',encoding='utf-8',newline='') as f:
        w=csv.writer(f);w.writerow(['time_utc','equity','cash']);w.writerows((p.time_utc.isoformat(),p.equity,p.cash) for p in r.equity_curve)
    with (dest/'Trades.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f);w.writerow(['symbol','entry','exit','return_pct','pnl']);w.writerows((t.symbol,t.entry_time_utc.isoformat(),t.exit_time_utc.isoformat(),t.realized_return_pct,t.realized_pnl) for t in r.trades)
    print(json.dumps({k:row[k] for k in ('scenario','budget','variant','end_usdc','close_dd_pct','trades')}),flush=True)

def parity():
    strategy=strategy_definition('v8r')
    proof=[]
    for name,budget in [('common_crash_70','1000'),('flash_wick_recovery','1000'),('all_three_correlated','35000')]:
        data,events=candles(name,1701)
        folder=OUT/'runs'/f'{name}-s1701-b{budget}-current-current'
        native_result=json.loads((folder/'Result.json').read_text())
        points={s:tuple(evaluate_batch(s,bars,parameters=strategy.parameters_for(s),semantics=strategy.semantics_for(s),strategy_version=strategy.version)) for s,bars in data.items()}
        path=OUT/f'Paper-Parity-{name}-{budget}.sqlite3'
        assert not path.exists(),'Preserve existing evidence'
        initialize_paper_at_latest(str(path),{s:p[:WARM] for s,p in points.items()},strategy_key=strategy.key,strategy_version=strategy.version,starting_cash_usdc=D(budget))
        with PaperStore(path) as store:store.save_settings(PaperSettings(max_capital_usdc=D(budget),auto_budget_enabled=True,autonomous_performance_enabled=True))
        rules={s:ExecutionRules(step_size=D('.00000001'),min_qty=D('.00000001'),min_notional=D(5)) for s in strategy.symbols}
        process_new_closed_points(str(path),points,rules,strategy_key=strategy.key,strategy_version=strategy.version,execution_candles_by_symbol=data,trade_policies_by_symbol=strategy.policy_map())
        p=load_paper_portfolio(str(path),{s:D(str(b[-1].close)) for s,b in data.items()},strategy_key=strategy.key,strategy_version=strategy.version)
        assert abs(p.equity_usdc-D(native_result['end_usdc']))<D('1e-12')
        with PaperStore(path) as store:
            count=store._connection.execute("SELECT COUNT(*) FROM paper_events WHERE status='FILLED'").fetchone()[0]
            assert count==native_result['fills']
            curve={x['time_utc']:D(x['equity']) for x in csv.DictReader(gzip.open(folder/'Equity.csv.gz','rt',encoding='utf-8'))}
            refs=[json.loads(x[0]) for x in store._connection.execute('SELECT payload_json FROM paper_allocation_reference WHERE strategy_version=?',(strategy.version,))]
            assert all(abs(D(x['equity_usdc'])-curve[x['bar_close_utc']])<D('1e-12') for x in refs)
        assert process_new_closed_points(str(path),points,rules,strategy_key=strategy.key,strategy_version=strategy.version,execution_candles_by_symbol=data,trade_policies_by_symbol=strategy.policy_map())==()
        proof.append({'scenario':name,'budget':budget,'matching_equity':str(p.equity_usdc),'matching_fill_count':count,'matching_hourly_references':len(refs),'restart_duplicate_events':0})
        print(proof[-1],flush=True)
    (OUT/'Synthetic-Paper-Parity.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('owned','chronic','parity'),required=True);args=parser.parse_args()
    jobs=[('owned_coin_99',b,v,c) for b in ('1000','35000') for v in ('current','exposure75','exposure50') for c in ('current','stress')]
    jobs += [('chronic_chop_no_initial_rally','1000',v,c) for v in ('current','exposure50','entry_pause20') for c in ('current','stress')]
    jobs +=[(n,'1000','entry_pause20',c) for n in ('common_crash_70','gap_after_exit_90') for c in ('current','stress')]
    contract=OUT/'Additions-Contract.json'
    if not contract.exists():contract.write_text(json.dumps({'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'reason':'Initial BTC99case had no BTCposition; targeted ownership and chronic loss additions','jobs':jobs,'not_unseen_holdout':True,'entry_pause20':'Only new entries pause at20pct closing DD; no forced exits; no hard loss bound'},indent=2),encoding='utf-8')
    if args.phase=='parity':parity();return
    for j in jobs:
        if (j[0]=='owned_coin_99')==(args.phase=='owned'):run(*j)

if __name__=='__main__':main()
