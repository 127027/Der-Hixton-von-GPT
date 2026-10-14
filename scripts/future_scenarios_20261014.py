"""Invented offline paths, NOT forecasts or probabilities; exact product engine.

No exchange clients, credentials, runtime databases, network or real orders.
All generator rules and jobs are written before observing performance.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import random
from collections import Counter,defaultdict
from dataclasses import asdict
from datetime import UTC,datetime,timedelta
from decimal import Decimal as D
from pathlib import Path

from hixton.backtest.models import CURRENT_COSTS,STRESS_COSTS,CostModel,ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.backtest.reporting import source_fingerprint
from hixton.domain.models import Candle,SignalAction
from hixton.domain.versions import strategy_definition

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'research/future-scenarios-20261014'
START=datetime(2027,1,1,tzinfo=UTC)
WARM=400
PRICES={'BTCUSDC':50000,'ETHUSDC':3000,'BNBUSDC':500,'SOLUSDC':100,'XRPUSDC':1,'ADAUSDC':.5,'LINKUSDC':15,'AVAXUSDC':20,'DOTUSDC':4,'DOGEUSDC':.15,'NEARUSDC':3,'AAVEUSDC':150,'BCHUSDC':300,'SUIUSDC':2,'UNIUSDC':6}
SCENARIOS={
    'calm_bull':('Geordneter Anstieg',2400),
    'parabolic_bull':('Extremer Anstieg, anschließend unveränderter Kurs',2400),
    'common_crash_35':('Gemeinsamer 35-Prozent-Sprung nach unten',1800),
    'common_crash_70':('Gemeinsamer 70-Prozent-Sprung nach unten',1800),
    'gap_after_exit_90':('Kurssturz nach Ausstiegssignal vor nächstem Open',1800),
    'single_coin_99':('Ein Coin verliert 99 Prozent, andere bewegen sich weiter',2400),
    'flash_wick_recovery':('Gleichzeitiger 80-Prozent-Stundentiefstkurs, Schlusskurs erholt',1800),
    'slow_crypto_winter':('Zwei Jahre überwiegend fallende Kurse',17520),
    'whipsaw':('Sägezahn: wiederholte Fehlausbrüche',4800),
    'rotating_coins':('Wechselnde Gewinner statt gemeinsamer Bewegung',4800),
    'sideways':('Seitwärtsbewegung mit Kosten und Rauschen',4800),
    'all_three_correlated':('Drei verschiedene Coins fallen gleichzeitig um 70 Prozent',2400),
    'illiquid_crash':('70-Prozent-Crash bei 5 Prozent modelliertem Preisnachteil je Order',1800),
    'twenty_year_regimes':('20 erfundene Jahre: Zyklen, Krisen, Fehlausbrüche',175320),
}
VARIANTS={'current':D(1),'exposure75':D('.75'),'exposure50':D('.5')}
ILLQ=CostModel('illiquid',D(10),D(100),D(400))

def drift(name,t,j,rng):
    if t<0:return -.0002 + .0001*math.sin(t/12+j/20)
    if t<150:return -.0003
    if t<650:return .0022*(1+j*.025)
    if name=='calm_bull':return .0007+.0001*math.sin(t/9+j)
    if name=='parabolic_bull':return .006 if t<1200 else 0
    if name in ('common_crash_35','common_crash_70','gap_after_exit_90','illiquid_crash','all_three_correlated','single_coin_99','flash_wick_recovery'):
        return -.0002 if t<1200 else .0005*math.sin(t/80+j)
    if name=='slow_crypto_winter':return -.00045+.0005*math.sin(t/100+j*.02)
    if name=='whipsaw':return (.0024 if (t//72)%2==0 else -.0026)+rng.gauss(0,.0003)
    if name=='rotating_coins':return (.002 if (t//180)%5==j%5 else -.0005)+rng.gauss(0,.0005)
    if name=='sideways':return .0001*math.sin(t/45+j)+rng.gauss(0,.002)
    phase=(t//(24*183))%8
    # Fixed predeclared alternating regimes: 1yr bull, 1yr bear, 1yr chop, 1yr rotation.
    mu=(.00014,.00016,-.00017,-.00013,0,0,.00006,-.00004)[phase]
    if phase in (4,5):mu+=.0015 if (t//96)%2==0 else -.0015
    if phase in (6,7):mu+=.00018 if (t//720)%5==j%5 else -.000045
    common=random.Random(170000+t).gauss(0,.002)
    return mu+common+rng.gauss(0,.0008)

def candles(name,seed):
    hours=SCENARIOS[name][1];rng=random.Random(seed);strategy=strategy_definition('v8r')
    data={s:[] for s in strategy.symbols};events=[]
    for j,symbol in enumerate(strategy.symbols):
        price=float(PRICES[symbol])
        for t in range(-WARM,hours):
            at=START+timedelta(hours=t);op=price
            change=drift(name,t,j,rng)
            if name=='twenty_year_regimes' and t>650 and t%(24*365*3)==24*365*2:
                op*=.55
                if j==0:events.append({'hour':t,'kind':'COMMON_45_PERCENT_GAP'})
            if t==800:
                drop={'common_crash_35':.65,'common_crash_70':.3,'illiquid_crash':.3,'all_three_correlated':.3}.get(name)
                if drop:op*=drop
                if name=='single_coin_99' and symbol=='BTCUSDC':
                    op*=.01;events.append({'hour':t,'kind':'BTC_99_PERCENT_GAP'})
                if j==0 and drop:events.append({'hour':t,'kind':'COMMON_GAP','price_multiplier':drop})
            # Exit decision closes at t799; real modeled next execution opens t800.
            if name=='gap_after_exit_90' and t==799:change=math.log(.7)
            if name=='gap_after_exit_90' and t==800:
                op*=.1
                if j==0:events.append({'hour':t,'kind':'COMMON_90_PERCENT_GAP_AFTER_SELL_SIGNAL'})
            cl=max(1e-9,op*math.exp(change))
            wick=.0007 if name not in ('sideways','twenty_year_regimes') else .0015
            hi=max(op,cl)*(1+wick);lo=min(op,cl)*(1-wick)
            if name=='flash_wick_recovery' and t==800:
                lo=min(op,cl)*.2
                if j==0:events.append({'hour':t,'kind':'SYNCHRONOUS_MID_HOUR_LOW_80_PERCENT_CLOSE_RECOVERS'})
            volume=1_000_000/((op+cl)/2)
            data[symbol].append(Candle(symbol,at,at+timedelta(hours=1)-timedelta(milliseconds=1),op,hi,lo,cl,volume,1_000_000,1000,True,'SYNTHETIC_OFFLINE_NOT_BINANCE'))
            price=cl
    return data,events

def measure(result,data,seed,events):
    lookup={s.signal_id:s for s in result.signals}
    fills=defaultdict(list)
    for f in result.fills:fills[f.fill_time_utc].append(f)
    owned={s:D(0) for s in data};cash=seed;peak=seed;intra_dd=D(0);worst_at=None;max_fraction=D(0);before=[]
    crash_times={START+timedelta(hours=e['hour']) for e in events}
    for k,p in enumerate(result.equity_curve):
        bars={s:data[s][k+WARM] for s in data};at=next(iter(bars.values())).open_time_utc
        for f in fills.get(at,[]):
            sym=lookup[f.signal_id].symbol
            if f.action==SignalAction.ENTER_LONG:cash-=f.quote_value;owned[sym]+=f.base_quantity
            else:cash+=f.quote_value-f.fee_quote_equivalent;owned[sym]-=f.base_quantity
        if at in crash_times:before.append({'at':at.isoformat(),'owned_symbols':[s for s,q in owned.items() if q>D('.000000000001')],'cash':str(cash)})
        low=cash+sum((owned[s]*D(str(b.low)) for s,b in bars.items()),D(0))
        close=cash+sum((owned[s]*D(str(b.close)) for s,b in bars.items()),D(0))
        assert abs(close-p.equity)<D('1e-12'),('ledger reconstruction',k,close,p.equity)
        assert cash>=0 and min(owned.values())>=0
        dd=(1-low/peak)*100 if peak>0 else D(0)
        if dd>intra_dd:intra_dd=dd;worst_at=at.isoformat()
        peak=max(peak,p.equity)
        if close>0:max_fraction=max(max_fraction,sum((owned[s]*D(str(b.close)) for s,b in bars.items()),D(0))/close)
    issues=Counter(x.rsplit(':',1)[-1] for x in result.blocked_signals)
    worst=min(result.trades,key=lambda t:t.realized_return_pct,default=None)
    return {'end_usdc':str(result.metrics.ending_equity),'close_dd_pct':str(result.metrics.max_drawdown_pct),
        'minimum_close_equity':str(min(p.equity for p in result.equity_curve)),
        'synchronous_low_dd_vs_previous_closed_peak_pct':str(intra_dd),'synchronous_low_dd_at':worst_at,
        'trades':len(result.trades),'fills':len(result.fills),'max_distinct_positions':result.max_concurrent_positions,
        'max_invested_fraction_at_close':str(max_fraction),'daily_paused_hours':result.daily_paused_bars,
        'permanent_risk_halt':result.risk_halted_at_utc is not None,'entry_block_reasons':dict(issues),
        'worst_trade':None if worst is None else {'symbol':worst.symbol,'return_pct':str(worst.realized_return_pct),'pnl':str(worst.realized_pnl),'entry':worst.entry_time_utc.isoformat(),'exit':worst.exit_time_utc.isoformat()},
        'injected_events':events,'ownership_at_event':before,'nonnegative_cash_and_inventory':True,
        'data_hashes':result.data_snapshot_sha256_by_symbol}

def jobs():
    rows=[]
    for name in SCENARIOS:
        seeds=(1701,1702,1703) if name=='twenty_year_regimes' else (1701,)
        variants=('current',) if name=='twenty_year_regimes' else ('current','exposure75','exposure50')
        costs=('current','stress') if name not in ('illiquid_crash',) else ('illiquid',)
        budgets=(D(1000),D(35000)) if name in ('single_coin_99','all_three_correlated') else (D(1000),)
        for seed in seeds:
            for budget in budgets:
                for variant in variants:
                    for cost in costs:rows.append((name,seed,str(budget),variant,cost))
    return rows

def run(job):
    name,seed,budget,variant,cost=job
    dest=OUT/'runs'/f'{name}-s{seed}-b{budget}-{variant}-{cost}'
    if (dest/'Result.json').exists():return
    dest.mkdir(parents=True,exist_ok=True)
    data,events=candles(name,seed);amount=D(budget)
    model={'current':CURRENT_COSTS,'stress':STRESS_COSTS,'illiquid':ILLQ}[cost]
    strategy=strategy_definition('v8r')
    rules={s:ExecutionRules(step_size=D('.00000001'),min_qty=D('.00000001'),min_notional=D(5)) for s in strategy.symbols}
    r=run_shared_portfolio_backtest(candles_by_symbol=data,report_start_utc=START,
        report_end_utc=START+timedelta(hours=SCENARIOS[name][1]),starting_cash=amount,target_notional=amount/2,
        costs=model,execution_rules=rules,strategy=strategy,reinvest_profits=True,autonomous_spot=True,
        capital_exposure_fraction=VARIANTS[variant])
    row={'scenario':name,'label':SCENARIOS[name][0],'seed':seed,'budget':budget,'variant':variant,'cost':asdict(model),
        'strategy_version':strategy.version,'native_source_sha256':source_fingerprint(),'hours':SCENARIOS[name][1],
        'report_start':START.isoformat(),'report_end':r.report_end_utc.isoformat(),'synthetic_not_forecast':True,
        **measure(r,data,amount,events)}
    (dest/'Result.json').write_text(json.dumps(row,indent=2,default=str),encoding='utf-8')
    with gzip.open(dest/'Equity.csv.gz','wt',encoding='utf-8',newline='') as f:
        w=csv.writer(f);w.writerow(['time_utc','equity','cash']);w.writerows((p.time_utc.isoformat(),p.equity,p.cash) for p in r.equity_curve)
    with (dest/'Trades.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f);w.writerow(['symbol','entry','exit','return_pct','pnl']);w.writerows((t.symbol,t.entry_time_utc.isoformat(),t.exit_time_utc.isoformat(),t.realized_return_pct,t.realized_pnl) for t in r.trades)
    print(json.dumps({k:row[k] for k in ('scenario','seed','budget','variant','end_usdc','close_dd_pct','synchronous_low_dd_vs_previous_closed_peak_pct','trades')}),flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('short','long','contract'),default='short');parser.add_argument('--index',type=int);args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    catalogue=jobs();contract={'source_sha256':source_fingerprint(),'strategy':strategy_definition('v8r').config_payload(),
        'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scenarios':SCENARIOS,'jobs':catalogue,'prices':PRICES,'warmup':WARM,
        'limitations':['Invented paths, not future predictions or probabilities','Static modeled costs/filters; no depth, orderbook, trading halts or counterparty failure','USDC unit cannot measure a USDC/USD depeg','Synchronous lows explicitly injected; other low-based marks are pessimistic bounds, not observed fills','Variants change only research entry exposure; not promoted or live approved']}
    path=OUT/'Contract.json'
    if path.exists():
        old=json.loads(path.read_text(encoding='utf-8'))
        if old['generator_sha256']!=contract['generator_sha256']:
            assert not list((OUT/'runs').rglob('Result.json')),'Changing generator invalidates all completed results'
            archive=OUT/('Contract-before-generator-fix-'+old['generator_sha256'][:8]+'.json')
            if not archive.exists():path.rename(archive)
    if not path.exists():path.write_text(json.dumps(contract,indent=2,default=str),encoding='utf-8')
    if args.phase=='contract':print(len(catalogue),'predeclared jobs');return
    selected=[j for j in catalogue if (j[0]=='twenty_year_regimes')==(args.phase=='long')]
    if args.index is not None:selected=[selected[args.index]]
    for j in selected:run(j)

if __name__=='__main__':main()
