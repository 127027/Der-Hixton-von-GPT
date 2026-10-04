"""Bounded exact-idle maximum-hold research for five V1-derived Satellites.

Entry parameters are frozen from prior TRAINING winners. Only the causal filler
holding horizon is selected here, on the pre-holdout training window. Direct-USDC
holdout remains rejection-only. Core V6 strategy and shared capital C stay unchanged.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS, CostModel
from hixton.data.binance import BinancePublicClient
from hixton.domain.capital import capital_plan
from hixton.domain.models import StrategyParameters
from hixton.domain.trade_policy import TradePolicy
from hixton.domain.versions import V1_STRATEGY, V6_COIN_STRATEGY
from scripts.satellite_filler_router_research import (
    RouterConfig,
    run_filler_router_portfolio,
)
from scripts.satellite_shared_portfolio_research import _load_histories, _rules
from scripts.satellite_v1_shared_core_idle_replay import _window_payload

D = Decimal
SOURCES = Path("agent_memory/autonomy/satellite_v1_idle_horizon_sources.json")
OUTPUT = Path("evidence/satellite-v1-idle-horizon-research.json")
HORIZONS = (2, 4, 6)
CAPITAL = D("250")


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path}: expected JSON object")
    return value


def _profiles(
    source_rows: dict[str, Any],
) -> tuple[
    dict[str, StrategyParameters],
    dict[str, TradePolicy],
    dict[str, Any],
    dict[str, str],
]:
    params = {
        profile.symbol: profile.parameters for profile in V6_COIN_STRATEGY.coin_profiles
    }
    policies = {
        profile.symbol: profile.trade_policy for profile in V6_COIN_STRATEGY.coin_profiles
    }
    semantics = {
        symbol: V6_COIN_STRATEGY.semantics for symbol in V6_COIN_STRATEGY.symbols
    }
    sources: dict[str, str] = {}
    for symbol, row in source_rows.items():
        raw_params = row.get("parameters")
        proxy = row.get("history_source_for_training")
        if not isinstance(raw_params, dict) or not isinstance(proxy, str):
            raise RuntimeError(f"{symbol}: malformed source row")
        params[symbol] = StrategyParameters(**raw_params)
        policies[symbol] = TradePolicy()
        semantics[symbol] = V1_STRATEGY.semantics
        sources[symbol] = proxy
    return params, policies, semantics, sources


def _decimal(value: object) -> D:
    return D(str(value))


def main() -> None:
    checkpoint = _load(SOURCES)
    source_rows = checkpoint.get("per_symbol")
    if not isinstance(source_rows, dict) or len(source_rows) != 5:
        raise RuntimeError("idle-horizon source checkpoint must contain five markets")

    satellites = tuple(source_rows)
    core_symbols = V6_COIN_STRATEGY.symbols
    all_symbols = core_symbols + satellites
    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    rules = _rules(client, all_symbols)
    (
        report_start,
        holdout_start,
        report_end,
        proxy_candles,
        validation_candles,
        provenance,
    ) = _load_histories(
        client=client,
        satellite_symbols=satellites,
        satellite_sources={
            symbol: str(source_rows[symbol]["history_source_for_training"])
            for symbol in satellites
        },
        execution_rules=rules,
    )
    parameters, policies, semantics, _ = _profiles(source_rows)
    plan = capital_plan(CAPITAL)
    fraction = plan.target_notional_usdc / CAPITAL

    core_cache: dict[tuple[str, str], Any] = {}

    def run_core(window: str, costs: CostModel):
        key = (window, costs.name)
        if key in core_cache:
            return core_cache[key]
        if window == "training":
            candles, start, end = proxy_candles, report_start, holdout_start
        elif window == "holdout":
            candles, start, end = validation_candles, holdout_start, report_end
        else:
            raise ValueError(window)
        result, _ = run_filler_router_portfolio(
            candles_by_symbol={s: candles[s] for s in core_symbols},
            report_start_utc=start,
            report_end_utc=end,
            starting_cash=CAPITAL,
            target_notional=plan.target_notional_usdc,
            slot_count=plan.slot_count,
            costs=costs,
            execution_rules={s: rules[s] for s in core_symbols},
            strategy_parameters_by_symbol={s: parameters[s] for s in core_symbols},
            trade_policies_by_symbol={s: policies[s] for s in core_symbols},
            strategy_semantics_by_symbol={s: semantics[s] for s in core_symbols},
            symbols=core_symbols,
            core_symbols=core_symbols,
            satellite_symbols=(),
            router_config=RouterConfig(24, D("0"), fraction),
            strict_core_idle_mask=False,
            soft_filler_exit_enabled=False,
        )
        core_cache[key] = result
        return result

    def run_candidate(
        symbol: str,
        horizon: int,
        window: str,
        costs: CostModel,
    ):
        if window == "training":
            candles, start, end = proxy_candles, report_start, holdout_start
        elif window == "holdout":
            candles, start, end = validation_candles, holdout_start, report_end
        else:
            raise ValueError(window)
        symbols = core_symbols + (symbol,)
        result, events = run_filler_router_portfolio(
            candles_by_symbol={s: candles[s] for s in symbols},
            report_start_utc=start,
            report_end_utc=end,
            starting_cash=CAPITAL,
            target_notional=plan.target_notional_usdc,
            slot_count=plan.slot_count,
            costs=costs,
            execution_rules={s: rules[s] for s in symbols},
            strategy_parameters_by_symbol={s: parameters[s] for s in symbols},
            trade_policies_by_symbol={s: policies[s] for s in symbols},
            strategy_semantics_by_symbol={s: semantics[s] for s in symbols},
            symbols=symbols,
            core_symbols=core_symbols,
            satellite_symbols=(symbol,),
            router_config=RouterConfig(horizon, D("0"), fraction),
            strict_core_idle_mask=True,
            soft_filler_exit_enabled=True,
        )
        return result, events

    per_symbol: dict[str, object] = {}
    accepted: list[str] = []

    for symbol in satellites:
        training_rows: list[dict[str, object]] = []
        for horizon in HORIZONS:
            row: dict[str, object] = {"max_holding_hours": horizon}
            for costs in (BASELINE_COSTS, STRESS_COSTS):
                core = run_core("training", costs)
                candidate, events = run_candidate(
                    symbol, horizon, "training", costs
                )
                row[costs.name] = _window_payload(
                    core=core,
                    candidate=candidate,
                    candidate_events=events,
                    core_symbols=core_symbols,
                    satellite_symbols=(symbol,),
                )
            baseline = row[BASELINE_COSTS.name]
            stress = row[STRESS_COSTS.name]
            row["training_eligible"] = bool(baseline["pass"]) and bool(stress["pass"])
            row["min_incremental_equity"] = str(
                min(
                    _decimal(baseline["candidate_vs_core"]["ending_equity_delta"]),
                    _decimal(stress["candidate_vs_core"]["ending_equity_delta"]),
                )
            )
            row["min_profit_per_position_hour"] = str(
                min(
                    _decimal(baseline["candidate"]["profit_per_satellite_position_hour"]),
                    _decimal(stress["candidate"]["profit_per_satellite_position_hour"]),
                )
            ) if row["training_eligible"] else None
            training_rows.append(row)

        eligible = [row for row in training_rows if row["training_eligible"]]
        eligible.sort(
            key=lambda row: (
                _decimal(row["min_incremental_equity"]),
                _decimal(row["min_profit_per_position_hour"]),
                -int(row["max_holding_hours"]),
            ),
            reverse=True,
        )
        winner = eligible[0] if eligible else None
        if winner is None:
            per_symbol[symbol] = {
                "source_training_champion": source_rows[symbol]["training_champion"],
                "training_horizon_grid": training_rows,
                "training_champion_horizon_hours": None,
                "holdout": None,
                "advance_to_combined_shared_replay": False,
                "rejection_reason": "NO_TRAINING_ROBUST_EXACT_IDLE_HORIZON",
            }
            continue

        horizon = int(winner["max_holding_hours"])
        holdout: dict[str, object] = {}
        for costs in (BASELINE_COSTS, STRESS_COSTS):
            core = run_core("holdout", costs)
            candidate, events = run_candidate(
                symbol, horizon, "holdout", costs
            )
            holdout[costs.name] = _window_payload(
                core=core,
                candidate=candidate,
                candidate_events=events,
                core_symbols=core_symbols,
                satellite_symbols=(symbol,),
            )
        holdout_pass = bool(holdout[BASELINE_COSTS.name]["pass"]) and bool(
            holdout[STRESS_COSTS.name]["pass"]
        )
        if holdout_pass:
            accepted.append(symbol)

        per_symbol[symbol] = {
            "source_training_champion": source_rows[symbol]["training_champion"],
            "training_horizon_grid": training_rows,
            "training_champion_horizon_hours": horizon,
            "holdout": holdout,
            "advance_to_combined_shared_replay": holdout_pass,
            "rejection_reason": (
                None if holdout_pass else "DIRECT_USDC_EXACT_IDLE_REJECTION"
            ),
        }

    evidence = {
        "schema_version": 1,
        "study": "SATELLITE_V1_IDLE_HORIZON_EVOLUTION",
        "research_only": True,
        "product_mutated": False,
        "protected_product_sha": checkpoint.get("protected_product_sha"),
        "shared_capital_usdc": str(CAPITAL),
        "capital_plan": asdict(plan),
        "horizon_family_hours": list(HORIZONS),
        "family_selection_basis": checkpoint.get("hypothesis_basis"),
        "selection_contract": {
            "training_exact_idle_may_select_horizon": True,
            "direct_usdc_holdout_may_select": False,
            "direct_usdc_holdout_rejection_only": True,
            "entry_parameters_frozen_before_this_stage": True,
        },
        "per_symbol": per_symbol,
        "accepted_for_combined_shared_replay": accepted,
        "next_stage": (
            "SATELLITE_V1_COMBINED_IDLE_REPLAY"
            if accepted
            else "SATELLITE_V1_NO_SURVIVOR_REVIEW"
        ),
        "provenance_by_symbol": provenance,
        "safety": {
            "core_v6_profiles_used_as_satellite_seed": False,
            "core_strategy_mutated": False,
            "private_credentials_used": False,
            "orders_sent": False,
            "paper_or_live_activated": False,
            "holdout_used_to_rank_or_retune": False,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2, default=str) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "study": evidence["study"],
                "accepted_for_combined_shared_replay": accepted,
                "next_stage": evidence["next_stage"],
                "training_horizons": {
                    symbol: row["training_champion_horizon_hours"]
                    for symbol, row in per_symbol.items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
