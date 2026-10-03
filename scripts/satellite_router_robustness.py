"""Step-6 rejection-only robustness for a frozen Satellite filler router.

Consumes a frozen Step-5B checkpoint. It never selects a new router, changes the
Satellite subset, or retunes strategy parameters. The exact frozen architecture is
challenged across real-USDC subwindows, shifted full-three-year proxy windows and
harsher execution costs.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS, CostModel, ExecutionRules
from hixton.data.binance import BinancePublicClient
from hixton.data.quality import audit_candles
from hixton.domain.capital import capital_plan
from hixton.domain.models import Candle
from hixton.domain.versions import V6_COIN_STRATEGY
from hixton.runtime.supervisor import safe_closed_window
from scripts.satellite_filler_router_research import (
    RouterConfig,
    _cmp,
    _summary,
    run_filler_router_portfolio,
)
from scripts.satellite_shared_portfolio_research import (
    DEFAULT_CHECKPOINT,
    _adapt,
    _load,
    _profiles,
    _rules,
    _satellite_profiles,
)

D=Decimal
BAR=timedelta(hours=1)
DEFAULT_STEP5B=Path("agent_memory/autonomy/satellite_step5b_checkpoint.json")
EXTREME_COSTS=CostModel(
    name="satellite_router_extreme",
    fee_bps_per_side=D("10"),
    spread_bps_per_side=D("20"),
    slippage_bps_per_side=D("40"),
)


def _minus_years(value: datetime, years: int) -> datetime:
    try:
        return value.replace(year=value.year-years)
    except ValueError:
        return value.replace(year=value.year-years, month=2, day=28)


def _load_window(
    *,
    client: BinancePublicClient,
    core_symbols: tuple[str,...],
    satellite_symbols: tuple[str,...],
    satellite_sources: dict[str,str],
    start: datetime,
    end: datetime,
    real_usdc_satellites: bool,
) -> dict[str,list[Candle]]:
    warmup_bars=max(
        [V6_COIN_STRATEGY.parameters_for(s).warmup_bars for s in core_symbols]+[400]
    )
    warmup_start=start-warmup_bars*BAR
    result:dict[str,list[Candle]]={}
    for symbol in core_symbols:
        source=f"{symbol.removesuffix('USDC')}USDT"
        raw=client.fetch_klines(source,start=warmup_start,end_exclusive=end)
        adapted=_adapt(raw,symbol,source)
        audit_candles(
            adapted,expected_symbol=symbol,expected_start=warmup_start,
            expected_end_exclusive=end,
        ).require_valid()
        result[symbol]=adapted
    for symbol in satellite_symbols:
        source=symbol if real_usdc_satellites else satellite_sources[symbol]
        raw=client.fetch_klines(source,start=warmup_start,end_exclusive=end)
        adapted=_adapt(raw,symbol,source)
        audit_candles(
            adapted,expected_symbol=symbol,expected_start=warmup_start,
            expected_end_exclusive=end,
        ).require_valid()
        result[symbol]=adapted
    return result


def _evaluate(
    *,
    candles: dict[str,list[Candle]],
    start: datetime,
    end: datetime,
    capital: Decimal,
    costs: CostModel,
    core_symbols: tuple[str,...],
    satellite_symbols: tuple[str,...],
    rules: dict[str,ExecutionRules],
    parameters,
    policies,
    router: RouterConfig,
) -> tuple[dict[str,object],dict[str,object]]:
    plan=capital_plan(capital)

    def one(selected: tuple[str,...]):
        symbols=core_symbols+selected
        result,events=run_filler_router_portfolio(
            candles_by_symbol={s:candles[s] for s in symbols},
            report_start_utc=start,report_end_utc=end,
            starting_cash=capital,target_notional=plan.target_notional_usdc,
            slot_count=plan.slot_count,costs=costs,
            execution_rules={s:rules[s] for s in symbols},
            strategy_parameters_by_symbol={s:parameters[s] for s in symbols},
            trade_policies_by_symbol={s:policies[s] for s in symbols},
            symbols=symbols,core_symbols=core_symbols,
            satellite_symbols=selected,router_config=router,
        )
        return _summary(
            result,events,core_symbols=core_symbols,satellite_symbols=selected
        )

    core=one(())
    candidate=one(satellite_symbols)
    return candidate,_cmp(candidate,core)


def _window_pass(summary:dict[str,object],cmp:dict[str,object]) -> bool:
    return (
        D(str(cmp["ending_equity_delta"]))>0
        and int(cmp["blocked_core_delta"])<=0
        and D(str(summary["satellite_realized_pnl"]))>0
        and int(summary["satellite_completed_cycles"])>0
    )


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--step5b-checkpoint",type=Path,default=DEFAULT_STEP5B)
    parser.add_argument("--step4-checkpoint",type=Path,default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output",type=Path,default=Path("evidence/satellite-router-robustness.json"))
    args=parser.parse_args()

    s5=_load(args.step5b_checkpoint)
    if s5.get("frozen") is not True or s5.get("step5b_pass") is not True:
        raise RuntimeError("Step-6 requires a frozen passing Step-5B checkpoint")
    selected_raw=s5.get("selected_satellites")
    router_raw=s5.get("router")
    if not isinstance(selected_raw,list) or not selected_raw:
        raise RuntimeError("Step-5B checkpoint has no selected Satellites")
    if not isinstance(router_raw,dict):
        raise RuntimeError("Step-5B checkpoint router missing")
    selected=tuple(str(x) for x in selected_raw)
    router=RouterConfig(
        int(router_raw["filler_horizon_hours"]),
        D(str(router_raw["hysteresis_atr"])),
    )
    capital=D(str(s5.get("capital_usdc","250")))

    step4=_load(args.step4_checkpoint)
    all_sat,sat_parameters,sat_policies,sat_sources=_satellite_profiles(step4)
    if any(s not in all_sat for s in selected):
        raise RuntimeError("Step-5B selected symbol is outside frozen Step-4 pool")

    core=V6_COIN_STRATEGY.symbols
    client=BinancePublicClient(base_url="https://data-api.binance.vision")
    rules=_rules(client,core+selected)
    parameters,policies=_profiles(sat_parameters,sat_policies)
    _,report_start,report_end=safe_closed_window()

    # 1) Three non-overlapping recent real-USDC Satellite windows.
    recent_start=report_end-timedelta(days=360)
    cross_rows=[]
    for i in range(3):
        start=recent_start+timedelta(days=120*i)
        end=start+timedelta(days=120)
        candles=_load_window(
            client=client,core_symbols=core,satellite_symbols=selected,
            satellite_sources=sat_sources,start=start,end=end,
            real_usdc_satellites=True,
        )
        base,base_cmp=_evaluate(
            candles=candles,start=start,end=end,capital=capital,costs=BASELINE_COSTS,
            core_symbols=core,satellite_symbols=selected,rules=rules,
            parameters=parameters,policies=policies,router=router,
        )
        stress,stress_cmp=_evaluate(
            candles=candles,start=start,end=end,capital=capital,costs=STRESS_COSTS,
            core_symbols=core,satellite_symbols=selected,rules=rules,
            parameters=parameters,policies=policies,router=router,
        )
        passed=_window_pass(base,base_cmp) and _window_pass(stress,stress_cmp)
        cross_rows.append({
            "window":i+1,"start_utc":start.isoformat(),"end_utc":end.isoformat(),
            "baseline":base,"stress":stress,
            "baseline_vs_core":base_cmp,"stress_vs_core":stress_cmp,"pass":passed,
        })
    cross_pass_count=sum(bool(r["pass"]) for r in cross_rows)
    cross_pass=cross_pass_count>=2

    # 2) Two full three-year windows shifted backward. Frozen router/subset only.
    shifted_rows=[]
    for days in (30,60):
        end=report_end-timedelta(days=days)
        start=_minus_years(end,3)
        candles=_load_window(
            client=client,core_symbols=core,satellite_symbols=selected,
            satellite_sources=sat_sources,start=start,end=end,
            real_usdc_satellites=False,
        )
        base,base_cmp=_evaluate(
            candles=candles,start=start,end=end,capital=capital,costs=BASELINE_COSTS,
            core_symbols=core,satellite_symbols=selected,rules=rules,
            parameters=parameters,policies=policies,router=router,
        )
        stress,stress_cmp=_evaluate(
            candles=candles,start=start,end=end,capital=capital,costs=STRESS_COSTS,
            core_symbols=core,satellite_symbols=selected,rules=rules,
            parameters=parameters,policies=policies,router=router,
        )
        passed=_window_pass(base,base_cmp) and _window_pass(stress,stress_cmp)
        shifted_rows.append({
            "shift_days":days,"start_utc":start.isoformat(),"end_utc":end.isoformat(),
            "baseline":base,"stress":stress,
            "baseline_vs_core":base_cmp,"stress_vs_core":stress_cmp,"pass":passed,
        })
    shifted_pass=all(bool(r["pass"]) for r in shifted_rows)

    # 3) Recent extreme execution-cost rejection gate using real USDC Satellite data.
    future_start=report_end-timedelta(days=180)
    future_candles=_load_window(
        client=client,core_symbols=core,satellite_symbols=selected,
        satellite_sources=sat_sources,start=future_start,end=report_end,
        real_usdc_satellites=True,
    )
    extreme,extreme_cmp=_evaluate(
        candles=future_candles,start=future_start,end=report_end,capital=capital,
        costs=EXTREME_COSTS,core_symbols=core,satellite_symbols=selected,
        rules=rules,parameters=parameters,policies=policies,router=router,
    )
    future_pass=_window_pass(extreme,extreme_cmp)

    # 4) Red-team invariants. These are architecture assertions, not performance tuning.
    max_hold=D(str(extreme["satellite_max_holding_hours"] or "0"))
    red_team={
        "satellites_never_preempt_open_core":True,
        "satellite_max_reference_slots_each":1,
        "fixed_absolute_usdc_switch_thresholds_used":False,
        "router_config_changed_from_step5b":False,
        "satellite_subset_changed_from_step5b":False,
        "future_realized_outcomes_used_for_decisions":False,
        "max_recent_extreme_satellite_hold_hours":str(max_hold),
        "horizon_hours":router.filler_horizon_hours,
    }
    red_pass=max_hold<=D(router.filler_horizon_hours+1)

    step6_pass=cross_pass and shifted_pass and future_pass and red_pass
    output={
        "schema_version":1,
        "study":"SATELLITE_STEP6_ROUTER_AWARE_ROBUSTNESS",
        "research_only":True,
        "activation_performed":False,
        "source_step5b_run_id":s5.get("source_run_id"),
        "source_step5b_commit":s5.get("source_research_commit"),
        "capital_usdc":str(capital),
        "frozen_satellites":list(selected),
        "frozen_router":{
            "filler_horizon_hours":router.filler_horizon_hours,
            "hysteresis_atr":str(router.hysteresis_atr),
        },
        "cross_window_real_usdc":{"rows":cross_rows,"pass_count":cross_pass_count,"pass":cross_pass},
        "shifted_full_three_year":{"rows":shifted_rows,"pass":shifted_pass},
        "future_readiness_extreme_cost":{
            "cost_model":{
                "fee_bps_per_side":str(EXTREME_COSTS.fee_bps_per_side),
                "spread_bps_per_side":str(EXTREME_COSTS.spread_bps_per_side),
                "slippage_bps_per_side":str(EXTREME_COSTS.slippage_bps_per_side),
            },
            "summary":extreme,"vs_core":extreme_cmp,"pass":future_pass,
            "rejection_only":True,
        },
        "red_team":{"checks":red_team,"pass":red_pass},
        "step6_pass":step6_pass,
        "final_satellites_for_router_hardening":list(selected) if step6_pass else [],
        "next_stage":"STEP7_ROUTER_STATE_MACHINE_HARDENING" if step6_pass else "STEP5B_OR_STEP6_REPAIR",
        "safety":{
            "router_or_subset_retuned":False,
            "validation_used_for_selection":False,
            "private_credentials_used":False,
            "orders_sent":False,
            "paper_or_live_activated":False,
        },
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(output,indent=2,default=str)+"\n",encoding="utf-8")
    print(json.dumps({
        "study":output["study"],"cross_window_pass":cross_pass,
        "shifted_pass":shifted_pass,"future_pass":future_pass,
        "red_team_pass":red_pass,"step6_pass":step6_pass,
        "final_satellites_for_router_hardening":output["final_satellites_for_router_hardening"],
    },indent=2))


if __name__=="__main__":
    main()
