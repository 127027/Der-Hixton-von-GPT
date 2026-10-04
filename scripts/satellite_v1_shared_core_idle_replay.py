"""Exact shared-Core-idle replay for V1-derived Satellite candidates.

Research-only: protected Core remains V6, Satellite semantics remain DMS_V1.
Candidates are already frozen by training + direct-USDC rejection. This stage
may reject but never select replacement parameters from holdout/full outcomes.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from hixton.backtest.models import (
    BASELINE_COSTS,
    STRESS_COSTS,
    CostModel,
    PortfolioBacktestResult,
)
from hixton.data.binance import BinancePublicClient
from hixton.domain.capital import capital_plan
from hixton.domain.models import SignalAction, StrategyParameters
from hixton.domain.trade_policy import TradePolicy
from hixton.domain.versions import V1_STRATEGY, V6_COIN_STRATEGY
from scripts.satellite_filler_router_research import (
    RouterConfig,
    _cmp,
    _summary,
    run_filler_router_portfolio,
)
from scripts.satellite_shared_portfolio_research import _load_histories, _rules

D = Decimal
DEFAULT_CANDIDATES = Path("agent_memory/autonomy/satellite_v1_candidates.json")
DEFAULT_OUTPUT = Path("evidence/satellite-v1-shared-core-idle-replay.json")
STUDY = "SATELLITE_V1_SHARED_CORE_IDLE_REPLAY"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path}: expected JSON object")
    return value


def _candidate_inputs(
    checkpoint: dict[str, Any],
) -> tuple[tuple[str, ...], dict[str, StrategyParameters], dict[str, str]]:
    accepted_raw = checkpoint.get("accepted_for_shared_core_idle_replay")
    rows = checkpoint.get("per_symbol")
    if not isinstance(accepted_raw, list) or not isinstance(rows, dict):
        raise RuntimeError("candidate checkpoint is incomplete")
    accepted = tuple(str(symbol) for symbol in accepted_raw)
    if not accepted or len(accepted) > 5 or len(set(accepted)) != len(accepted):
        raise RuntimeError("accepted V1 Satellite set must contain 1..5 unique symbols")

    parameters: dict[str, StrategyParameters] = {}
    sources: dict[str, str] = {}
    for symbol in accepted:
        row = rows.get(symbol)
        if not isinstance(row, dict) or row.get("advance_to_shared_replay") is not True:
            raise RuntimeError(f"{symbol}: not eligible for shared replay")
        params = row.get("parameters")
        source = row.get("history_source_for_training")
        if not isinstance(params, dict) or not isinstance(source, str):
            raise RuntimeError(f"{symbol}: malformed candidate checkpoint")
        parameters[symbol] = StrategyParameters(**params)
        sources[symbol] = source
    return accepted, parameters, sources


def _profiles(
    satellite_parameters: dict[str, StrategyParameters],
) -> tuple[dict[str, StrategyParameters], dict[str, TradePolicy], dict[str, Any]]:
    parameters = {
        profile.symbol: profile.parameters for profile in V6_COIN_STRATEGY.coin_profiles
    }
    policies = {
        profile.symbol: profile.trade_policy for profile in V6_COIN_STRATEGY.coin_profiles
    }
    semantics = {
        symbol: V6_COIN_STRATEGY.semantics for symbol in V6_COIN_STRATEGY.symbols
    }
    for symbol, params in satellite_parameters.items():
        parameters[symbol] = params
        policies[symbol] = TradePolicy()
        semantics[symbol] = V1_STRATEGY.semantics
    return parameters, policies, semantics


def _filled_core_entry_ids(
    result: PortfolioBacktestResult,
    core_symbols: tuple[str, ...],
) -> set[str]:
    symbol_by_signal = {signal.signal_id: signal.symbol for signal in result.signals}
    return {
        fill.signal_id
        for fill in result.fills
        if fill.action is SignalAction.ENTER_LONG
        and symbol_by_signal.get(fill.signal_id) in core_symbols
    }


def _window_payload(
    *,
    core: PortfolioBacktestResult,
    candidate: PortfolioBacktestResult,
    candidate_events: list[dict[str, object]],
    core_symbols: tuple[str, ...],
    satellite_symbols: tuple[str, ...],
) -> dict[str, object]:
    core_summary = _summary(core, [], core_symbols=core_symbols, satellite_symbols=())
    candidate_summary = _summary(
        candidate,
        candidate_events,
        core_symbols=core_symbols,
        satellite_symbols=satellite_symbols,
    )
    comparison = _cmp(candidate_summary, core_summary)
    core_entries = _filled_core_entry_ids(core, core_symbols)
    candidate_core_entries = _filled_core_entry_ids(candidate, core_symbols)
    displaced_ids = sorted(core_entries - candidate_core_entries)
    unexpected_ids = sorted(candidate_core_entries - core_entries)

    core_idle_hours = int(core_summary["zero_position_hours"])
    monetized = max(0, int(comparison["zero_position_hours_reduced"]))
    idle_fill_pct = (
        D(monetized) / D(core_idle_hours) * D("100")
        if core_idle_hours > 0
        else D("0")
    )
    satellite_pnl = D(str(candidate_summary["satellite_realized_pnl"]))
    profit_per_exact_idle_hour = (
        None if monetized <= 0 else str(satellite_pnl / D(monetized))
    )
    strict_core_parity = (
        not displaced_ids
        and not unexpected_ids
        and int(comparison["core_completed_cycles_delta"]) == 0
        and D(str(comparison["core_realized_pnl_delta"])) == 0
        and int(comparison["blocked_core_delta"]) <= 0
        and int(comparison["daily_paused_bars_delta"]) == 0
    )
    incremental_positive = D(str(comparison["ending_equity_delta"])) > 0
    satellite_positive = (
        int(candidate_summary["satellite_completed_cycles"]) > 0
        and satellite_pnl > 0
        and candidate_summary["profit_per_satellite_position_hour"] is not None
    )
    productive_idle_fill = monetized > 0

    return {
        "core_reference": core_summary,
        "candidate": candidate_summary,
        "candidate_vs_core": comparison,
        "core_idle_hours": core_idle_hours,
        "satellite_core_idle_hours_monetized": monetized,
        "core_idle_fill_pct": str(idle_fill_pct),
        "satellite_profit_per_exact_idle_hour": profit_per_exact_idle_hour,
        "core_entry_fill_count_reference": len(core_entries),
        "core_entry_fill_count_candidate": len(candidate_core_entries),
        "core_opportunities_displaced": len(displaced_ids),
        "core_entry_ids_displaced": displaced_ids,
        "unexpected_core_entry_ids": unexpected_ids,
        "strict_core_parity": strict_core_parity,
        "incremental_shared_equity_positive": incremental_positive,
        "satellite_realized_positive": satellite_positive,
        "productive_idle_fill": productive_idle_fill,
        "pass": (
            strict_core_parity
            and incremental_positive
            and satellite_positive
            and productive_idle_fill
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--capital", default="250")
    args = parser.parse_args()

    capital = D(str(args.capital))
    if capital <= 0:
        raise ValueError("capital must be positive")

    checkpoint = _load(args.candidates)
    satellites, satellite_parameters, satellite_sources = _candidate_inputs(checkpoint)
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
        satellite_sources=satellite_sources,
        execution_rules=rules,
    )
    parameters, policies, semantics = _profiles(satellite_parameters)
    plan = capital_plan(capital)
    config = RouterConfig(
        filler_horizon_hours=24,
        hysteresis_atr=D("0"),
        satellite_budget_fraction_of_c=plan.target_notional_usdc / capital,
    )

    def run_one(
        *,
        candles_by_symbol,
        start,
        end,
        costs: CostModel,
        with_satellites: bool,
    ):
        selected = satellites if with_satellites else ()
        symbols = core_symbols + selected
        return run_filler_router_portfolio(
            candles_by_symbol={symbol: candles_by_symbol[symbol] for symbol in symbols},
            report_start_utc=start,
            report_end_utc=end,
            starting_cash=capital,
            target_notional=plan.target_notional_usdc,
            slot_count=plan.slot_count,
            costs=costs,
            execution_rules={symbol: rules[symbol] for symbol in symbols},
            strategy_parameters_by_symbol={symbol: parameters[symbol] for symbol in symbols},
            trade_policies_by_symbol={symbol: policies[symbol] for symbol in symbols},
            strategy_semantics_by_symbol={symbol: semantics[symbol] for symbol in symbols},
            symbols=symbols,
            core_symbols=core_symbols,
            satellite_symbols=selected,
            router_config=config,
            strict_core_idle_mask=with_satellites,
            soft_filler_exit_enabled=False,
        )

    windows = {
        "training_proxy": (proxy_candles, report_start, holdout_start),
        "direct_usdc_holdout": (validation_candles, holdout_start, report_end),
        "full_three_year_proxy_descriptive": (proxy_candles, report_start, report_end),
    }
    evidence_windows: dict[str, object] = {}
    for name, (candles, start, end) in windows.items():
        row: dict[str, object] = {
            "start_utc": start.isoformat(),
            "end_utc": end.isoformat(),
            "selection_or_retuning_performed": False,
            "rejection_only": name != "training_proxy",
        }
        for costs in (BASELINE_COSTS, STRESS_COSTS):
            core, _ = run_one(
                candles_by_symbol=candles,
                start=start,
                end=end,
                costs=costs,
                with_satellites=False,
            )
            candidate, events = run_one(
                candles_by_symbol=candles,
                start=start,
                end=end,
                costs=costs,
                with_satellites=True,
            )
            row[costs.name] = _window_payload(
                core=core,
                candidate=candidate,
                candidate_events=events,
                core_symbols=core_symbols,
                satellite_symbols=satellites,
            )
        evidence_windows[name] = row

    holdout = evidence_windows["direct_usdc_holdout"]
    full = evidence_windows["full_three_year_proxy_descriptive"]
    holdout_pass = bool(holdout[BASELINE_COSTS.name]["pass"]) and bool(
        holdout[STRESS_COSTS.name]["pass"]
    )
    full_pass = bool(full[BASELINE_COSTS.name]["pass"]) and bool(
        full[STRESS_COSTS.name]["pass"]
    )
    shared_replay_pass = holdout_pass and full_pass

    evidence = {
        "schema_version": 1,
        "study": STUDY,
        "research_only": True,
        "activation_performed": False,
        "product_mutated": False,
        "protected_product_sha": checkpoint.get("protected_product_sha"),
        "source_evolution_run_id": checkpoint.get("source_run_id"),
        "source_evolution_head_sha": checkpoint.get("source_head_sha"),
        "source_evolution_artifact_digest": checkpoint.get("source_artifact_digest"),
        "shared_capital_usdc": str(capital),
        "capital_plan": asdict(plan),
        "protected_core_symbols": list(core_symbols),
        "tested_satellites": list(satellites),
        "satellite_strategy_semantics": V1_STRATEGY.semantics.value,
        "core_strategy_semantics": V6_COIN_STRATEGY.semantics.value,
        "core_v6_profiles_used_as_satellite_seed": False,
        "candidate_parameters": {
            symbol: asdict(satellite_parameters[symbol]) for symbol in satellites
        },
        "routing_contract": {
            "satellite_entry_requires_core_engine_completely_idle": True,
            "satellite_closed_when_core_claims_capacity": True,
            "satellite_soft_time_exit_enabled": False,
            "natural_v1_exit_enabled": True,
            "one_shared_account": True,
            "core_entry_fill_parity_required": True,
            "core_realized_pnl_parity_required": True,
            "future_realized_outcomes_used_for_decision": False,
        },
        "windows": evidence_windows,
        "direct_usdc_holdout_pass": holdout_pass,
        "full_three_year_rejection_pass": full_pass,
        "shared_core_idle_replay_pass": shared_replay_pass,
        "accepted_after_shared_core_idle_replay": (
            list(satellites) if shared_replay_pass else []
        ),
        "next_stage": "SATELLITE_V1_SECOND_BOUNDED_EVOLUTION",
        "provenance_by_symbol": provenance,
        "safety": {
            "private_credentials_used": False,
            "orders_sent": False,
            "paper_or_live_activated": False,
            "holdout_used_to_select_or_rank": False,
            "future_used_to_select_or_rank": False,
            "protected_core_mutated": False,
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "study": STUDY,
                "tested_satellites": list(satellites),
                "direct_usdc_holdout_pass": holdout_pass,
                "full_three_year_rejection_pass": full_pass,
                "shared_core_idle_replay_pass": shared_replay_pass,
                "accepted_after_shared_core_idle_replay": evidence[
                    "accepted_after_shared_core_idle_replay"
                ],
                "next_stage": evidence["next_stage"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
