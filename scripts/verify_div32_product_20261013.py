"""Exact public-snapshot native/Paper parity for owner-selected DIV32 contract."""
import json, gzip,hashlib
from pathlib import Path
from datetime import datetime
from decimal import Decimal as D
from tempfile import mkdtemp
from hixton.backtest.continuity import load_continuity_history
from hixton.backtest.models import CURRENT_COSTS,STRESS_COSTS,ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.backtest.reporting import source_fingerprint
from hixton.data.storage import CandleStore
from hixton.domain.versions import strategy_definition,V8_ETH8_PAPER_STRATEGY
from hixton.domain.strategy import evaluate_batch
from hixton.paper.engine import initialize_paper_at_latest,process_new_closed_points,load_paper_portfolio
from hixton.paper.storage import PaperStore
from hixton.paper.models import PaperSettings
from research_dd10_coins_20261013 import SnapshotOnly
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'verification-final';OUT.mkdir(exist_ok=True)
i=json.loads(Path(r'C:\Users\andre\OneDrive\Desktop\Neuer Ordner\Pruefergebnisse\Coin-Nachoptimierung-20261013\Inputs.json').read_text(encoding='utf-8'))
base=strategy_definition('v8r');assert base.diversification_stages==(('32000',3),)
start,end=(datetime.fromisoformat(i[k]) for k in ('start','end'));seed=D(i['portfolio_seed']);data=Path(i['market_snapshot']);rules={}
with CandleStore(data/'hixton-usdc.sqlite3',read_only=True) as db:
 for s in base.symbols:
  x=db.load_symbol_rules(s);rules[s]=ExecutionRules(x.tick_size,x.step_size,x.min_qty,x.min_notional)
h=load_continuity_history(strategy=base,report_start_utc=start,report_end_utc=end,execution_rules=rules,native_database_path=data/'hixton-usdc.sqlite3',cache_path=data/'backtest-history.sqlite3',client=SnapshotOnly())
kw=dict(candles_by_symbol=h.candles_by_symbol,report_start_utc=start,report_end_utc=end,starting_cash=seed,target_notional=seed/2,execution_rules=rules,reinvest_profits=True,autonomous_spot=True)
proof={'source_sha256':source_fingerprint(),'strategy':base.version,'stages':base.diversification_stages,'costs':[]}
for cost in (CURRENT_COSTS,STRESS_COSTS):
 r=run_shared_portfolio_backtest(**kw,strategy=base,costs=cost)
 name='three32' if cost.name=='current' else 'baseline'
 old=json.loads((ROOT/'research'/'full'/name/cost.name/'Metrics.json').read_text(encoding='utf-8'))
 assert str(r.metrics.ending_equity)==old['end'],(r.metrics.ending_equity,old['end'])
 assert str(r.metrics.max_drawdown_pct)==old['dd']
 ledger=[json.loads(l) for l in gzip.open(ROOT/'research'/'full'/name/cost.name/'Ledger.jsonl.gz','rt',encoding='utf-8')]
 assert all(D(x['equity'])==p.equity and D(x['cash'])==p.cash for x,p in zip(ledger,r.equity_curve,strict=True))
 row=dict(cost=cost.name,end=str(r.metrics.ending_equity),dd=str(r.metrics.max_drawdown_pct),fills=len(r.fills),all_hourly_values_match_research=True)
 proof['costs'].append(row);print(row,flush=True)
 if cost.name=='current':native=r
old=run_shared_portfolio_backtest(**kw,strategy=V8_ETH8_PAPER_STRATEGY,costs=CURRENT_COSTS)
assert old.metrics.ending_equity==D('31825.37351337113595000000')
proof['old_eth8_frozen_regression_matches']=True
print('Frozen old ETH8 regression matches. Full Paper replay starting.',flush=True)
points={s:tuple(evaluate_batch(s,bars,parameters=base.parameters_for(s),semantics=base.semantics_for(s),strategy_version=base.version)) for s,bars in h.candles_by_symbol.items()}
paper=OUT/'paper-parity.sqlite3'
assert not paper.exists(), 'Never overwrite previous parity evidence'
initialize_paper_at_latest(str(paper),{s:p[:400] for s,p in points.items()},strategy_key=base.key,strategy_version=base.version,starting_cash_usdc=seed)
with PaperStore(paper) as store:store.save_settings(PaperSettings(max_capital_usdc=seed,auto_budget_enabled=True,autonomous_performance_enabled=True))
process_new_closed_points(str(paper),points,rules,strategy_key=base.key,strategy_version=base.version,execution_candles_by_symbol=h.candles_by_symbol,trade_policies_by_symbol=base.policy_map())
portfolio=load_paper_portfolio(str(paper),{s:D(str(b[-1].close)) for s,b in h.candles_by_symbol.items()},strategy_key=base.key,strategy_version=base.version)
assert abs(portfolio.equity_usdc-native.metrics.ending_equity)<D('1e-18'),(portfolio.equity_usdc,native.metrics.ending_equity)
with PaperStore(paper) as store:
 events=[store._row_to_event(x) for x in store._connection.execute("SELECT * FROM paper_events WHERE status='FILLED'")]
 count=store.diversification_count(base.version)
 refs=[json.loads(x[0]) for x in store._connection.execute('SELECT payload_json FROM paper_allocation_reference WHERE strategy_version=?',(base.version,))]
 assert count==3
native_curve={p.time_utc.isoformat():p.equity for p in native.equity_curve}
assert all(abs(D(x['equity_usdc'])-native_curve[x['bar_close_utc']])<D('1e-18') for x in refs if x['bar_close_utc'] in native_curve)
lookup={s.signal_id:s for s in native.signals}
expected=sorted((lookup[f.signal_id].symbol,f.action.value,f.fill_time_utc,f.base_quantity,f.fill_price) for f in native.fills)
actual=sorted((e.symbol,e.action,e.occurred_at_utc,e.base_quantity,e.execution_price) for e in events)
assert expected==actual, 'Every regular and partial fill must match'
# Restart/catch-up consumes no bar twice and retains three-position stage.
assert process_new_closed_points(str(paper),points,rules,strategy_key=base.key,strategy_version=base.version,execution_candles_by_symbol=h.candles_by_symbol,trade_policies_by_symbol=base.policy_map())==()
with PaperStore(paper) as store:assert store.diversification_count(base.version)==3
proof['paper']=dict(ending=str(portfolio.equity_usdc),matching_fills=len(events),matching_hourly_references=len(refs),stage_survives_restart=True,partial_exits=sum((e.reason or '').startswith('DIVERSIFICATION_TRIM::') for e in events),no_orders_sent=True)
(OUT/'Full-Parity.json').write_text(json.dumps(proof,indent=2,default=str),encoding='utf-8')
print(json.dumps(proof,indent=2,default=str),flush=True)
