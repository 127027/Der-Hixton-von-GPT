"""Public historical-data research only. No Binance credentials or runtime mutations."""
import argparse,gzip,json,csv,hashlib
from pathlib import Path
from dataclasses import asdict
from datetime import datetime,timedelta
from decimal import Decimal as D
from concurrent.futures import ProcessPoolExecutor,as_completed
from concentration_portfolio_20261013 import run_shared_portfolio_backtest as research_run
from concentration_research_support_20261013 import ConcentrationPolicy
from research_dd10_coins_20261013 import SnapshotOnly
from hixton.backtest.continuity import load_continuity_history,continuity_manifest_data
from hixton.backtest.models import CURRENT_COSTS,STRESS_COSTS,ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest as native_run
from hixton.backtest.reporting import source_fingerprint
from hixton.data.storage import CandleStore
from hixton.domain.versions import strategy_definition
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'research';INPUT=Path(r'C:\Users\andre\OneDrive\Desktop\Neuer Ordner\Pruefergebnisse\Coin-Nachoptimierung-20261013\Inputs.json')
CATALOGUE={'baseline':(), 'six20':((20000,6),),'six25':((25000,6),),'six28':((28000,6),),'six30':((30000,6),),'six35':((35000,6),),'four25':((25000,4),),'three25':((25000,3),),'three15_four25_six30':((15000,3),(25000,4),(30000,6)),'three20_four25_six30':((20000,3),(25000,4),(30000,6)),'three20_four30_six35':((20000,3),(30000,4),(35000,6)),'four25_six30':((25000,4),(30000,6)),'three25_six30':((25000,3),(30000,6)),'three20_six25':((20000,3),(25000,6)),'four20_six25':((20000,4),(25000,6)),'three10_four20_six30':((10000,3),(20000,4),(30000,6)), 'three28':((28000,3),),'three30':((30000,3),),'three32':((32000,3),),'four28':((28000,4),),'four32':((32000,4),),'six32':((32000,6),),'three30_four35_six40':((30000,3),(35000,4),(40000,6)), 'three32_four40_six50':((32000,3),(40000,4),(50000,6)), 'three30_four40_six50':((30000,3),(40000,4),(50000,6))}
def initialize():
 global BASE,H,RULES,I,START,END
 I=json.loads(INPUT.read_text(encoding='utf-8'));BASE=strategy_definition('v8r');data=Path(I['market_snapshot']);RULES={}
 START,END=(datetime.fromisoformat(I[k]) for k in ('start','end'))
 with CandleStore(data/'hixton-usdc.sqlite3',read_only=True) as db:
  for s in BASE.symbols:
   rr=db.load_symbol_rules(s);RULES[s]=ExecutionRules(rr.tick_size,rr.step_size,rr.min_qty,rr.min_notional)
 H=load_continuity_history(strategy=BASE,report_start_utc=START,report_end_utc=END,execution_rules=RULES,native_database_path=data/'hixton-usdc.sqlite3',cache_path=data/'backtest-history.sqlite3',client=SnapshotOnly())
def run(job):
 name,cost_name,period=job;cost=CURRENT_COSTS if cost_name=='current' else STRESS_COSTS
 start=START if period in ('full','high') else END.replace(year=END.year-1)
 seed=D(I['portfolio_seed']) if period=='full' else D(50000) if period=='high' else D(30000)
 kw=dict(candles_by_symbol=H.candles_by_symbol,report_start_utc=start,report_end_utc=END,starting_cash=seed,target_notional=seed/2,costs=cost,execution_rules=RULES,strategy=BASE,reinvest_profits=True,autonomous_spot=True)
 stages=tuple((D(eq),n) for eq,n in CATALOGUE[name]);audit=[]
 policy=ConcentrationPolicy(stages[0][0],slots=stages[0][1]) if stages else None
 r=research_run(**kw,research_policy=policy,research_stages=stages,research_audit=audit)
 if name=='baseline':
  native=native_run(**kw)
  assert native.equity_curve==r.equity_curve and native.fills==r.fills and native.trades==r.trades and native.metrics==r.metrics
 switches=[ev for x in audit for ev in x['events'] if ev['kind']=='SWITCH'];trims=[ev for x in audit for ev in x['events'] if ev['kind']=='PARTIAL_TRIM'];trim_ids={t['signal_id'] for t in trims}
 assert all(D(x['cash'])>=0 and len(x['positions'])<=max(3,max((n for _,n in stages),default=0)) for x in audit)
 assert all(ep.equity==D(x['equity']) and ep.cash==D(x['cash']) for ep,x in zip(r.equity_curve,audit,strict=True))
 for ev in switches+trims:assert datetime.fromisoformat(ev['decision_close'])<datetime.fromisoformat(ev['execution_open'])
 row=dict(name=name,cost=cost_name,period=period,seed=str(seed),end=str(r.metrics.ending_equity),dd=str(r.metrics.max_drawdown_pct),fees=str(r.metrics.total_fees),cycles=sum(t.exit_signal_id not in trim_ids for t in r.trades),trims=len(trims),max_distinct=max(len(x['positions']) for x in audit),switches=switches,stages=[(str(e),n) for e,n in stages],source_sha256=source_fingerprint(),strategy=BASE.version,snapshot=r.data_snapshot_sha256_by_symbol,native_matches=name=='baseline',open_at_end=r.open_symbols_at_end)
 folder=OUT/period/name/cost_name;folder.mkdir(parents=True,exist_ok=True)
 (folder/'Metrics.json').write_text(json.dumps(row,indent=2,default=str),encoding='utf-8')
 with gzip.open(folder/'Ledger.jsonl.gz','wt',encoding='utf-8') as f:
  for x in audit:f.write(json.dumps(x)+'\n')
 with (folder/'Trades.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(asdict(r.trades[0])));w.writeheader();w.writerows(asdict(t) for t in r.trades)
 return row
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--cost',default='current');ap.add_argument('--period',default='full');ap.add_argument('--names',default=','.join(CATALOGUE));a=ap.parse_args()
 OUT.mkdir(exist_ok=True)
 contract=dict(scope='ISOLATED_RESEARCH_NO_ORDERS',catalogue=CATALOGUE,inputs=str(INPUT),method='Thresholds use finalized previous equity; stage latches monotonically. One real-cost modeled trim per upgrade. Only fresh distinct valid signals; cash is never forcibly invested. Exact base ETH8 indicators and gates. No dates chosen from future peaks.',selection='Compare whole-period ending capital and DD; normal end loss within 10% of baseline, DD reduced at least 5 percentage points. Stress end loss within 10%, DD no worse. Report fresh 30k last-year separately; all historical periods already inspected, no untouched holdout claim.',scripts_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),ROOT/'scripts/concentration_portfolio_20261013.py',ROOT/'scripts/concentration_research_support_20261013.py')})
 (OUT/('Contract-'+a.period+'-'+a.cost+'-'+hashlib.sha256(a.names.encode()).hexdigest()[:8]+'.json')).write_text(json.dumps(contract,indent=2),encoding='utf-8')
 jobs=[(n,a.cost,a.period) for n in a.names.split(',')]
 with ProcessPoolExecutor(max_workers=2,initializer=initialize) as pool:
  fs={pool.submit(run,j):j for j in jobs}
  for f in as_completed(fs):
   x=f.result();print(json.dumps({k:x[k] for k in ('name','cost','period','end','dd','cycles','trims','max_distinct')},default=str),flush=True)
 print('ALL_REQUESTED_COMPLETE',flush=True)



