"""Fast controlled Core10 slot-layout comparison using the 15-candidate router.

Research-only. Frozen Core profiles, identical history/costs/risk, fixed total capital.
"""

from __future__ import annotations

import json
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

from validate_15coin_satellite_integration import _histories, _maps, _rules

from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS
from hixton.backtest.satellite_portfolio import RouterConfig, run_filler_router_portfolio
from hixton.data.binance import BinancePublicClient
from hixton.domain.allocation import ONE_PER_SYMBOL, RANKED_REPEAT
from hixton.domain.satellite_layer import CORE_SYMBOLS

D = Decimal
CENT = D("0.01")
OUTPUT = Path("evidence/core10-slot-layout-quick.json")
LAYOUTS = (
    ("2xRR", 2, RANKED_REPEAT),
    ("3xRR", 3, RANKED_REPEAT),
    ("4xRR", 4, RANKED_REPEAT),
    ("5xRR", 5, RANKED_REPEAT),
    ("5xOPS", 5, ONE_PER_SYMBOL),
)


def tranche(capital: D, slots: int) -> tuple[D, D]:
    value=(capital / D(slots)).quantize(CENT, rounding=ROUND_DOWN)
    return value, capital - value * slots


def occupancy(result):
    events={}
    for trade in result.trades:
        events[trade.entry_time_utc]=events.get(trade.entry_time_utc,0)+trade.slot_count
        events[trade.exit_time_utc]=events.get(trade.exit_time_utc,0)-trade.slot_count
    hours={i:D("0") for i in range(result.slot_count+1)}
    occ=0
    prev=result.report_start_utc
    for at in sorted(events):
        clipped=min(max(at,result.report_start_utc),result.report_end_utc)
        if clipped>prev:
            hours[occ]+=D(str((clipped-prev).total_seconds()/3600))
            prev=clipped
        occ+=events[at]
    if prev<result.report_end_utc:
        hours[occ]+=D(str((result.report_end_utc-prev).total_seconds()/3600))
    total=sum(hours.values(),D("0"))
    util=sum(D(k)*v for k,v in hours.items())/(D(result.slot_count)*total)*D("100")
    return {
        "hours_by_slots":{str(k):str(v) for k,v in hours.items()},
        "zero_hours":str(hours[0]),
        "full_hours":str(hours[result.slot_count]),
        "utilization_pct":str(util),
    }


def main():
    client=BinancePublicClient(base_url="https://data-api.binance.vision")
    rules=_rules(client)
    start,end,candles,provenance=_histories(client)
    parameters,policies,semantics,_filters,_horizons,_reentry=_maps()
    output={
        "schema_version":1,
        "purpose":"CORE10_FIXED_CAPITAL_SLOT_LAYOUT_QUICK",
        "report_start_utc":start.isoformat(),
        "report_end_utc":end.isoformat(),
        "results":{},
        "orders_sent":False,
        "paper_state_modified":False,
        "provenance":{s:provenance[s] for s in CORE_SYMBOLS},
    }
    for capital in (D("250"),D("1000")):
        cap={}
        for cost_name,costs in (("baseline",BASELINE_COSTS),("stress",STRESS_COSTS)):
            rows={}
            for name,slots,policy in LAYOUTS:
                target,reserve=tranche(capital,slots)
                result,_events=run_filler_router_portfolio(
                    candles_by_symbol={s:candles[s] for s in CORE_SYMBOLS},
                    report_start_utc=start,
                    report_end_utc=end,
                    starting_cash=capital,
                    target_notional=target,
                    slot_count=slots,
                    costs=costs,
                    execution_rules={s:rules[s] for s in CORE_SYMBOLS},
                    strategy_parameters_by_symbol={s:parameters[s] for s in CORE_SYMBOLS},
                    trade_policies_by_symbol={s:policies[s] for s in CORE_SYMBOLS},
                    symbols=CORE_SYMBOLS,
                    core_symbols=CORE_SYMBOLS,
                    satellite_symbols=(),
                    router_config=RouterConfig(
                        filler_horizon_hours=24,
                        hysteresis_atr=D("0"),
                        satellite_budget_fraction_of_c=D("0"),
                    ),
                    strategy_semantics_by_symbol={s:semantics[s] for s in CORE_SYMBOLS},
                    strict_core_idle_mask=False,
                    core_allocation_policy=policy,
                )
                m=result.metrics
                rows[name]={
                    "slots":slots,
                    "policy":policy,
                    "slot_notional_usdc":str(target),
                    "reserve_usdc":str(reserve),
                    "ending_equity":str(m.ending_equity),
                    "net_pnl":str(m.net_pnl),
                    "return_pct":str(m.return_pct),
                    "max_drawdown_pct":str(m.max_drawdown_pct),
                    "completed_trades":m.completed_trades,
                    "completed_slot_trades":m.completed_slot_trades,
                    "winning_trades":m.winning_trades,
                    "losing_trades":m.losing_trades,
                    "average_holding_hours":None if m.average_holding_hours is None else str(m.average_holding_hours),
                    "fees":str(m.total_fees),
                    "no_free_slot_blocks":sum(":NO_FREE_SLOT" in x for x in result.blocked_signals),
                    **occupancy(result),
                }
            cap[cost_name]=rows
        output["results"][str(capital)]=cap
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(output,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(output,indent=2))


if __name__=="__main__":
    main()
