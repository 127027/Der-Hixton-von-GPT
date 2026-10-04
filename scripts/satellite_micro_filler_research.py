"""Research a dedicated small-signal Satellite filler family for the five primary markets.

The protected ten-Core V6 engine is never changed here. Satellites are secondary
gap-fillers only: they may enter while the Core engine is completely idle, and any
executable Core entry signal reclaims Satellite capital at the next executable open.

Candidate family/horizon selection uses TRAINING proxy data only. Real-USDC holdout
is rejection-only and can never select or retune a candidate.
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
OUTPUT = Path("evidence/satellite-micro-filler-research.json")
CAPITAL = D("250")
HORIZONS = (2, 6, 12)

MICRO_FAMILIES: tuple[tuple[str, StrategyParameters], ...] = (
    (
        "MICRO_FAST_08",
        StrategyParameters(
            vidya_length=4,
            momentum_length=8,
            smoothing_length=4,
            atr_length=24,
            band_multiplier=0.8,
            warmup_bars=400,
        ),
    ),
    (
        "MICRO_FAST_12",
        StrategyParameters(
            vidya_length=6,
            momentum_length=10,
            smoothing_length=6,
            atr_length=36,
            band_multiplier=1.2,
            warmup_bars=400,
        ),
    ),
    (
        "MICRO_FAST_16",
        StrategyParameters(
            vidya_length=6,
            momentum_length=12,
            smoothing_length=8,
            atr_length=48,
            band_multiplier=1.6,
            warmup_bars=400,
        ),
    ),
    (
        "MICRO_BALANCED_20",
        StrategyParameters(
            vidya_length=8,
            momentum_length=14,
            smoothing_length=8,
            atr_length=60,
            band_multiplier=2.0,
            warmup_bars=400,
        ),
    ),
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path}: expected JSON object")
    return value


def _decimal(value: object) -> D:
    return D(str(value))


def main() -> None:
    checkpoint = _load(SOURCES)
    source_rows = checkpoint.get("per_symbol")
    if not isinstance(source_rows, dict) or len(source_rows) != 5:
        raise RuntimeError("micro-filler source checkpoint must contain the five primary markets")

    satellites = tuple(source_rows)
    expected = ("SUIUSDC", "NEARUSDC", "UNIUSDC", "AAVEUSDC", "BCHUSDC")
    if satellites != expected:
        raise RuntimeError(f"primary Satellite order drifted: {satellites!r}")

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

    core_params = {
        profile.symbol: profile.parameters for profile in V6_COIN_STRATEGY.coin_profiles
    }
    core_policies = {
        profile.symbol: profile.trade_policy for profile in V6_COIN_STRATEGY.coin_profiles
    }
    plan = capital_plan(CAPITAL)
    fraction = plan.target_notional_usdc / CAPITAL
    core_cache: dict[tuple[str, str], object] = {}

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
            strategy_parameters_by_symbol={s: core_params[s] for s in core_symbols},
            trade_policies_by_symbol={s: core_policies[s] for s in core_symbols},
            strategy_semantics_by_symbol={
                s: V6_COIN_STRATEGY.semantics for s in core_symbols
            },
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
        parameters: StrategyParameters,
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
        params = {s: core_params[s] for s in core_symbols}
        params[symbol] = parameters
        policies = {s: core_policies[s] for s in core_symbols}
        policies[symbol] = TradePolicy()
        semantics = {s: V6_COIN_STRATEGY.semantics for s in core_symbols}
        semantics[symbol] = V1_STRATEGY.semantics

        return run_filler_router_portfolio(
            candles_by_symbol={s: candles[s] for s in symbols},
            report_start_utc=start,
            report_end_utc=end,
            starting_cash=CAPITAL,
            target_notional=plan.target_notional_usdc,
            slot_count=plan.slot_count,
            costs=costs,
            execution_rules={s: rules[s] for s in symbols},
            strategy_parameters_by_symbol=params,
            trade_policies_by_symbol=policies,
            strategy_semantics_by_symbol=semantics,
            symbols=symbols,
            core_symbols=core_symbols,
            satellite_symbols=(symbol,),
            router_config=RouterConfig(horizon, D("0"), fraction),
            strict_core_idle_mask=True,
            soft_filler_exit_enabled=True,
        )

    per_symbol: dict[str, object] = {}
    accepted: list[str] = []

    for symbol in satellites:
        training_rows: list[dict[str, object]] = []
        ranked: list[tuple[tuple[D, D, int, D, int], str, StrategyParameters, int]] = []

        for family_name, parameters in MICRO_FAMILIES:
            for horizon in HORIZONS:
                row: dict[str, object] = {
                    "family": family_name,
                    "parameters": asdict(parameters),
                    "max_holding_hours": horizon,
                }
                payloads: dict[str, dict[str, object]] = {}
                for costs in (BASELINE_COSTS, STRESS_COSTS):
                    core = run_core("training", costs)
                    candidate, events = run_candidate(
                        symbol, parameters, horizon, "training", costs
                    )
                    payload = _window_payload(
                        core=core,
                        candidate=candidate,
                        candidate_events=events,
                        core_symbols=core_symbols,
                        satellite_symbols=(symbol,),
                    )
                    payloads[costs.name] = payload
                    row[costs.name] = payload

                base = payloads[BASELINE_COSTS.name]
                stress = payloads[STRESS_COSTS.name]
                eligible = bool(base["pass"]) and bool(stress["pass"])
                min_equity = min(
                    _decimal(base["candidate_vs_core"]["ending_equity_delta"]),
                    _decimal(stress["candidate_vs_core"]["ending_equity_delta"]),
                )
                min_sat_pnl = min(
                    _decimal(base["candidate"]["satellite_realized_pnl"]),
                    _decimal(stress["candidate"]["satellite_realized_pnl"]),
                )
                min_cycles = min(
                    int(base["candidate"]["satellite_completed_cycles"]),
                    int(stress["candidate"]["satellite_completed_cycles"]),
                )
                pph_values = [
                    value
                    for value in (
                        base["candidate"]["profit_per_satellite_position_hour"],
                        stress["candidate"]["profit_per_satellite_position_hour"],
                    )
                    if value is not None
                ]
                min_pph = min((_decimal(v) for v in pph_values), default=D("-999"))
                row["training_eligible"] = eligible
                row["min_incremental_equity"] = str(min_equity)
                row["min_satellite_pnl"] = str(min_sat_pnl)
                row["min_completed_cycles"] = min_cycles
                row["min_profit_per_position_hour"] = str(min_pph)
                training_rows.append(row)

                if eligible:
                    ranked.append(
                        (
                            (min_equity, min_sat_pnl, min_cycles, min_pph, -horizon),
                            family_name,
                            parameters,
                            horizon,
                        )
                    )

        ranked.sort(key=lambda item: item[0], reverse=True)
        if not ranked:
            per_symbol[symbol] = {
                "training_candidates": training_rows,
                "training_winner": None,
                "holdout": None,
                "advance_to_combined_replay": False,
                "rejection_reason": "NO_TRAINING_ROBUST_MICRO_FILLER",
            }
            continue

        _score, family_name, parameters, horizon = ranked[0]
        holdout: dict[str, object] = {}
        for costs in (BASELINE_COSTS, STRESS_COSTS):
            core = run_core("holdout", costs)
            candidate, events = run_candidate(
                symbol, parameters, horizon, "holdout", costs
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
            "training_candidates": training_rows,
            "training_winner": {
                "family": family_name,
                "parameters": asdict(parameters),
                "max_holding_hours": horizon,
            },
            "holdout": holdout,
            "advance_to_combined_replay": holdout_pass,
            "rejection_reason": None if holdout_pass else "DIRECT_USDC_MICRO_FILLER_REJECTION",
        }

    evidence = {
        "schema_version": 1,
        "study": "SATELLITE_MICRO_FILLER_SMALL_SIGNAL_RESEARCH",
        "research_only": True,
        "product_mutated": False,
        "protected_product_sha": checkpoint.get("protected_product_sha"),
        "shared_capital_usdc": str(CAPITAL),
        "capital_plan": asdict(plan),
        "primary_satellites": list(satellites),
        "micro_family_count": len(MICRO_FAMILIES),
        "horizon_family_hours": list(HORIZONS),
        "selection_contract": {
            "training_only_selects_family_and_horizon": True,
            "direct_usdc_holdout_rejection_only": True,
            "holdout_may_retune": False,
            "core_profiles_mutated": False,
        },
        "routing_contract": {
            "satellites_are_secondary_gap_fillers_only": True,
            "entry_requires_core_engine_completely_idle": True,
            "any_executable_core_entry_preempts_satellite": True,
            "core_handoff_occurs_at_next_executable_open": True,
            "one_shared_account": True,
            "reference_capital_usdc": "250",
            "initial_real_trial_capital_usdc": "50",
            "future_scale_capital_usdc": "1000",
        },
        "per_symbol": per_symbol,
        "accepted_for_combined_shared_replay": accepted,
        "next_stage": (
            "SATELLITE_MICRO_FILLER_COMBINED_REPLAY"
            if accepted
            else "SATELLITE_MICRO_FILLER_NEXT_FAMILY"
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
                "training_winners": {
                    symbol: row["training_winner"]
                    for symbol, row in per_symbol.items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
