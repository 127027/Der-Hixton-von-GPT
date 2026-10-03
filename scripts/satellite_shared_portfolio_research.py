"""Step-5 research-only shared 10-core + satellite portfolio replay.

This module deliberately does not widen the canonical product universe. The product
portfolio runner remains fail-closed on exactly ten USDC markets. For this bounded
research process only, the validator and same-bar ranking function are temporarily
adapted in-process so the exact canonical execution engine can replay the protected
ten-core universe plus the frozen Step-4 satellite profiles.

Satellite profiles are frozen by Step 4 and may be rejected here, never retuned from
shared-portfolio outcomes.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import hixton.backtest.portfolio as portfolio
from hixton.backtest.continuity import load_continuity_history
from hixton.backtest.models import (
    BASELINE_COSTS,
    STRESS_COSTS,
    ExecutionRules,
    PortfolioBacktestResult,
)
from hixton.data.binance import BinancePublicClient
from hixton.data.quality import audit_candles
from hixton.domain.capital import capital_plan
from hixton.domain.models import Candle, StrategyParameters
from hixton.domain.trade_policy import TradePolicy
from hixton.domain.versions import V6_COIN_STRATEGY
from hixton.runtime.supervisor import safe_closed_window

D = Decimal
BAR = timedelta(hours=1)
VERSION = "HIXTON-V6-SATELLITE-STEP5-SHARED-PORTFOLIO"
DEFAULT_CHECKPOINT = Path("agent_memory/autonomy/satellite_step4_checkpoint.json")


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def _rules(client: BinancePublicClient, symbols: tuple[str, ...]) -> dict[str, ExecutionRules]:
    result: dict[str, ExecutionRules] = {}
    for symbol in symbols:
        saved = client.symbol_rules(symbol)
        if not saved.tradable_for_quote("USDC"):
            raise RuntimeError(f"{symbol}: current Binance USDC rules are not tradable")
        result[symbol] = ExecutionRules(
            tick_size=saved.tick_size,
            step_size=saved.step_size,
            min_qty=saved.min_qty,
            min_notional=saved.min_notional,
        )
    return result


def _adapt(candles: list[Candle], target_symbol: str, source_symbol: str) -> list[Candle]:
    if source_symbol == target_symbol:
        return candles
    return [
        replace(
            candle,
            symbol=target_symbol,
            source="binance_spot_proxy_for_step5_shared_satellite_research",
        )
        for candle in candles
    ]


def _satellite_profiles(
    checkpoint: dict[str, Any],
) -> tuple[
    tuple[str, ...],
    dict[str, StrategyParameters],
    dict[str, TradePolicy],
    dict[str, str],
]:
    if checkpoint.get("frozen") is not True:
        raise RuntimeError("Step-4 checkpoint is not frozen")
    symbols_raw = checkpoint.get("advancing_symbols")
    profiles_raw = checkpoint.get("profiles")
    if not isinstance(symbols_raw, list) or not isinstance(profiles_raw, dict):
        raise RuntimeError("Step-4 checkpoint is incomplete")
    symbols = tuple(str(x) for x in symbols_raw)
    if not symbols or len(symbols) > 5 or len(set(symbols)) != len(symbols):
        raise RuntimeError("Step-4 advancing symbol set must contain 1..5 unique symbols")
    parameters: dict[str, StrategyParameters] = {}
    policies: dict[str, TradePolicy] = {}
    sources: dict[str, str] = {}
    for symbol in symbols:
        row = profiles_raw.get(symbol)
        if not isinstance(row, dict):
            raise RuntimeError(f"{symbol}: frozen checkpoint row missing")
        params = row.get("parameters")
        policy = row.get("trade_policy")
        source = row.get("history_source_for_training")
        if not isinstance(params, dict) or not isinstance(policy, dict) or not isinstance(source, str):
            raise RuntimeError(f"{symbol}: malformed frozen profile")
        parameters[symbol] = StrategyParameters(**params)
        policies[symbol] = TradePolicy(**policy)
        sources[symbol] = source
    return symbols, parameters, policies, sources


def _load_histories(
    *,
    client: BinancePublicClient,
    satellite_symbols: tuple[str, ...],
    satellite_sources: dict[str, str],
    execution_rules: dict[str, ExecutionRules],
):
    _warmup_start, report_start, report_end = safe_closed_window()
    core_symbols = V6_COIN_STRATEGY.symbols
    core_history = load_continuity_history(
        strategy=V6_COIN_STRATEGY,
        report_start_utc=report_start,
        report_end_utc=report_end,
        execution_rules={symbol: execution_rules[symbol] for symbol in core_symbols},
        client=client,
    )
    candles = dict(core_history.candles_by_symbol)

    warmup_bars = max(
        [V6_COIN_STRATEGY.parameters_for(symbol).warmup_bars for symbol in core_symbols]
        + [400]
    )
    warmup_start = report_start - warmup_bars * BAR
    provenance: dict[str, dict[str, object]] = dict(core_history.provenance_by_symbol)

    for symbol in satellite_symbols:
        source = satellite_sources[symbol]
        raw = client.fetch_klines(
            source,
            start=warmup_start,
            end_exclusive=report_end,
        )
        adapted = _adapt(raw, symbol, source)
        audit_candles(
            adapted,
            expected_symbol=symbol,
            expected_start=warmup_start,
            expected_end_exclusive=report_end,
        ).require_valid()
        candles[symbol] = adapted
        provenance[symbol] = {
            "target_market": symbol,
            "market_proxy": source,
            "target_quote": "USDC",
            "proxy_scope": "HISTORICAL_MARKET_CANDLES_ONLY",
            "execution_rules_from": symbol,
            "first_open_utc": adapted[0].open_time_utc.isoformat(),
            "last_open_utc": adapted[-1].open_time_utc.isoformat(),
            "candle_count": len(adapted),
        }
    return report_start, report_end, candles, provenance


def _profiles(
    satellite_parameters: dict[str, StrategyParameters],
    satellite_policies: dict[str, TradePolicy],
) -> tuple[dict[str, StrategyParameters], dict[str, TradePolicy]]:
    parameters = {
        profile.symbol: profile.parameters for profile in V6_COIN_STRATEGY.coin_profiles
    }
    policies = {
        profile.symbol: profile.trade_policy for profile in V6_COIN_STRATEGY.coin_profiles
    }
    parameters.update(satellite_parameters)
    policies.update(satellite_policies)
    return parameters, policies


def _run_portfolio(
    *,
    symbols: tuple[str, ...],
    core_symbols: tuple[str, ...],
    candles_by_symbol: dict[str, list[Candle]],
    execution_rules: dict[str, ExecutionRules],
    parameters_by_symbol: dict[str, StrategyParameters],
    policies_by_symbol: dict[str, TradePolicy],
    capital: Decimal,
    costs: Any,
    report_start,
    report_end,
) -> PortfolioBacktestResult:
    plan = capital_plan(capital)
    original_validator = portfolio.validate_market_symbols
    original_priority = portfolio.entry_priority
    core = frozenset(core_symbols)

    def research_validator(observed: tuple[str, ...]) -> str:
        if observed != symbols:
            raise ValueError("research portfolio universe mismatch")
        if any(not symbol.endswith("USDC") for symbol in observed):
            raise ValueError("Step-5 research accepts USDC target symbols only")
        return "USDC"

    def idle_first_priority(strength: float | None, symbol: str, observed):
        base = original_priority(strength, symbol, observed)
        return (0 if symbol in core else 1, *base)

    portfolio.validate_market_symbols = research_validator
    portfolio.entry_priority = idle_first_priority
    try:
        return portfolio.run_shared_portfolio_backtest(
            candles_by_symbol={symbol: candles_by_symbol[symbol] for symbol in symbols},
            report_start_utc=report_start,
            report_end_utc=report_end,
            starting_cash=capital,
            target_notional=plan.target_notional_usdc,
            slot_count=plan.slot_count,
            costs=costs,
            execution_rules={symbol: execution_rules[symbol] for symbol in symbols},
            strategy_parameters=V6_COIN_STRATEGY.parameters,
            strategy_parameters_by_symbol={
                symbol: parameters_by_symbol[symbol] for symbol in symbols
            },
            trade_policies_by_symbol={
                symbol: policies_by_symbol[symbol] for symbol in symbols
            },
            strategy_semantics=V6_COIN_STRATEGY.semantics,
            strategy_version=VERSION,
            slot_allocation=plan.allocation_policy,
            apply_risk_limits=True,
            symbols=symbols,
        )
    finally:
        portfolio.validate_market_symbols = original_validator
        portfolio.entry_priority = original_priority


def _summary(
    result: PortfolioBacktestResult,
    *,
    core_symbols: tuple[str, ...],
    satellite_symbols: tuple[str, ...],
) -> dict[str, object]:
    metrics = result.metrics
    signal_symbol = {signal.signal_id: signal.symbol for signal in result.signals}
    blocked_core = 0
    blocked_satellite = 0
    blocked_total = 0
    for item in result.blocked_signals:
        signal_id, reason = item.rsplit(":", 1)
        if reason != "NO_FREE_SLOT":
            continue
        blocked_total += 1
        symbol = signal_symbol.get(signal_id)
        if symbol in core_symbols:
            blocked_core += 1
        elif symbol in satellite_symbols:
            blocked_satellite += 1

    points = result.equity_curve
    zero_hours = sum(not point.active_position for point in points)
    zero_pct = D(zero_hours) / D(len(points)) * D("100") if points else D("0")
    average_position_value = (
        sum((point.position_value for point in points), D("0")) / D(len(points))
        if points else D("0")
    )
    per_symbol_realized_pnl = {
        symbol: sum(
            (trade.realized_pnl for trade in result.trades if trade.symbol == symbol),
            D("0"),
        )
        for symbol in core_symbols + satellite_symbols
    }
    per_symbol_completed_cycles = {
        symbol: sum(trade.symbol == symbol for trade in result.trades)
        for symbol in core_symbols + satellite_symbols
    }
    satellite_trade_pnl = sum(
        (per_symbol_realized_pnl[symbol] for symbol in satellite_symbols),
        D("0"),
    )
    core_trade_pnl = sum(
        (trade.realized_pnl for trade in result.trades if trade.symbol in core_symbols),
        D("0"),
    )
    satellite_cycles = sum(trade.symbol in satellite_symbols for trade in result.trades)
    core_cycles = sum(trade.symbol in core_symbols for trade in result.trades)
    satellite_hours = sum(
        (trade.holding_hours for trade in result.trades if trade.symbol in satellite_symbols),
        D("0"),
    )

    return {
        "ending_equity": str(metrics.ending_equity),
        "net_pnl": str(metrics.net_pnl),
        "return_pct": str(metrics.return_pct),
        "max_drawdown_pct": str(metrics.max_drawdown_pct),
        "completed_position_cycles": metrics.completed_trades,
        "completed_slot_trades": metrics.completed_slot_trades,
        "core_completed_cycles": core_cycles,
        "satellite_completed_cycles": satellite_cycles,
        "satellite_realized_trade_pnl": str(satellite_trade_pnl),
        "core_realized_trade_pnl": str(core_trade_pnl),
        "per_symbol_realized_trade_pnl": {
            symbol: str(value) for symbol, value in per_symbol_realized_pnl.items()
        },
        "per_symbol_completed_cycles": per_symbol_completed_cycles,
        "satellite_position_hours": str(satellite_hours),
        "zero_position_hours": zero_hours,
        "zero_position_pct": str(zero_pct),
        "average_position_value_usdc": str(average_position_value),
        "average_deployed_notional_pct_of_starting_capital": str(
            average_position_value / result.starting_cash * D("100")
        ),
        "blocked_no_free_slot": blocked_total,
        "blocked_core_no_free_slot": blocked_core,
        "blocked_satellite_no_free_slot": blocked_satellite,
        "total_fees": str(metrics.total_fees),
        "modeled_spread_slippage": str(metrics.modeled_spread_slippage),
        "max_concurrent_slots": result.max_concurrent_positions,
        "open_symbols_at_end": list(result.open_symbols_at_end),
    }


def _d(value: object) -> Decimal:
    return D(str(value))


def _comparison(
    candidate: dict[str, object], reference: dict[str, object]
) -> dict[str, object]:
    return {
        "ending_equity_delta": str(
            _d(candidate["ending_equity"]) - _d(reference["ending_equity"])
        ),
        "net_pnl_delta": str(_d(candidate["net_pnl"]) - _d(reference["net_pnl"])),
        "zero_position_hours_reduced": int(reference["zero_position_hours"])
        - int(candidate["zero_position_hours"]),
        "average_position_value_delta_usdc": str(
            _d(candidate["average_position_value_usdc"])
            - _d(reference["average_position_value_usdc"])
        ),
        "completed_position_cycles_delta": int(candidate["completed_position_cycles"])
        - int(reference["completed_position_cycles"]),
        "core_no_free_slot_delta": int(candidate["blocked_core_no_free_slot"])
        - int(reference["blocked_core_no_free_slot"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output", type=Path, default=Path("evidence/satellite-shared-portfolio-research.json"))
    parser.add_argument("--capital", default="250")
    args = parser.parse_args()

    capital = D(str(args.capital))
    checkpoint = _load(args.checkpoint)
    satellite_symbols, satellite_parameters, satellite_policies, satellite_sources = (
        _satellite_profiles(checkpoint)
    )
    core_symbols = V6_COIN_STRATEGY.symbols
    all_symbols = core_symbols + satellite_symbols
    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    execution_rules = _rules(client, all_symbols)
    report_start, report_end, candles, provenance = _load_histories(
        client=client,
        satellite_symbols=satellite_symbols,
        satellite_sources=satellite_sources,
        execution_rules=execution_rules,
    )
    parameters, policies = _profiles(satellite_parameters, satellite_policies)

    cache: dict[tuple[tuple[str, ...], str], tuple[PortfolioBacktestResult, dict[str, object]]] = {}

    def evaluate(selected: tuple[str, ...], costs):
        key = (selected, costs.name)
        if key not in cache:
            symbols = core_symbols + selected
            raw = _run_portfolio(
                symbols=symbols,
                core_symbols=core_symbols,
                candles_by_symbol=candles,
                execution_rules=execution_rules,
                parameters_by_symbol=parameters,
                policies_by_symbol=policies,
                capital=capital,
                costs=costs,
                report_start=report_start,
                report_end=report_end,
            )
            cache[key] = (
                raw,
                _summary(
                    raw,
                    core_symbols=core_symbols,
                    satellite_symbols=selected,
                ),
            )
        return cache[key]

    _, core_base = evaluate((), BASELINE_COSTS)
    _, core_stress = evaluate((), STRESS_COSTS)

    selected: list[str] = []
    remaining = list(satellite_symbols)
    rounds: list[dict[str, object]] = []

    while remaining:
        current_tuple = tuple(selected)
        _, current_base = evaluate(current_tuple, BASELINE_COSTS)
        _, current_stress = evaluate(current_tuple, STRESS_COSTS)
        candidates: list[dict[str, object]] = []

        for symbol in remaining:
            trial_tuple = tuple(selected + [symbol])
            _, base = evaluate(trial_tuple, BASELINE_COSTS)
            _, stress = evaluate(trial_tuple, STRESS_COSTS)
            base_cmp = _comparison(base, current_base)
            stress_cmp = _comparison(stress, current_stress)
            min_profit_delta = min(
                _d(base_cmp["ending_equity_delta"]),
                _d(stress_cmp["ending_equity_delta"]),
            )
            idle_reduction = min(
                int(base_cmp["zero_position_hours_reduced"]),
                int(stress_cmp["zero_position_hours_reduced"]),
            )
            deployed_gain = min(
                _d(base_cmp["average_position_value_delta_usdc"]),
                _d(stress_cmp["average_position_value_delta_usdc"]),
            )
            symbol_realized_base = _d(base["per_symbol_realized_trade_pnl"][symbol])
            symbol_realized_stress = _d(stress["per_symbol_realized_trade_pnl"][symbol])
            realized_positive = symbol_realized_base > 0 and symbol_realized_stress > 0
            productive_capacity_gain = idle_reduction > 0 or deployed_gain > 0
            advances = (
                min_profit_delta > 0
                and productive_capacity_gain
                and realized_positive
            )
            candidates.append(
                {
                    "symbol": symbol,
                    "trial_satellites": list(trial_tuple),
                    "baseline": base,
                    "stress": stress,
                    "baseline_vs_current": base_cmp,
                    "stress_vs_current": stress_cmp,
                    "min_ending_equity_delta": str(min_profit_delta),
                    "min_zero_position_hours_reduced": idle_reduction,
                    "min_average_position_value_gain_usdc": str(deployed_gain),
                    "productive_capacity_gain": productive_capacity_gain,
                    "added_symbol_realized_pnl_baseline": str(symbol_realized_base),
                    "added_symbol_realized_pnl_stress": str(symbol_realized_stress),
                    "added_symbol_realized_positive_after_costs": realized_positive,
                    "advance": advances,
                }
            )

        candidates.sort(
            key=lambda row: (
                _d(row["min_ending_equity_delta"]),
                int(row["min_zero_position_hours_reduced"]),
                min(
                    _d(row["added_symbol_realized_pnl_baseline"]),
                    _d(row["added_symbol_realized_pnl_stress"]),
                ),
            ),
            reverse=True,
        )
        winner = candidates[0]
        rounds.append(
            {
                "round": len(rounds) + 1,
                "selected_before": list(selected),
                "candidates": candidates,
                "winner": winner["symbol"] if winner["advance"] else None,
            }
        )
        if winner["advance"] is not True:
            break
        chosen = str(winner["symbol"])
        selected.append(chosen)
        remaining.remove(chosen)

    selected_tuple = tuple(selected)
    _, final_base = evaluate(selected_tuple, BASELINE_COSTS)
    _, final_stress = evaluate(selected_tuple, STRESS_COSTS)
    base_vs_core = _comparison(final_base, core_base)
    stress_vs_core = _comparison(final_stress, core_stress)

    step5_pass = bool(selected) and (
        _d(base_vs_core["ending_equity_delta"]) > 0
        and _d(stress_vs_core["ending_equity_delta"]) > 0
        and (
            (
                int(base_vs_core["zero_position_hours_reduced"]) > 0
                and int(stress_vs_core["zero_position_hours_reduced"]) > 0
            )
            or (
                _d(base_vs_core["average_position_value_delta_usdc"]) > 0
                and _d(stress_vs_core["average_position_value_delta_usdc"]) > 0
            )
        )
    )

    output = {
        "schema_version": 1,
        "study": "SATELLITE_STEP5_SHARED_PORTFOLIO_RESEARCH",
        "research_only": True,
        "activation_performed": False,
        "checkpoint_source_run_id": checkpoint.get("source_run_id"),
        "checkpoint_source_commit": checkpoint.get("source_research_commit"),
        "protected_core_symbols": list(core_symbols),
        "step4_advancing_symbols": list(satellite_symbols),
        "capital_usdc_shared_account": str(capital),
        "capital_plan": asdict(capital_plan(capital)),
        "report_start_utc": report_start.isoformat(),
        "report_end_utc": report_end.isoformat(),
        "selection_method": (
            "Greedy forward shared-portfolio selection. Frozen Step-4 satellite profiles "
            "may advance only when adding the satellite improves ending equity under both "
            "baseline and stress costs, improves productive capacity by either reducing "
            "zero-position hours or increasing average deployed capital, and the added "
            "Satellite has positive realized completed-trade PnL under both cost models. "
            "Same-bar core "
            "entries rank before satellites; an already-open satellite may still block a "
            "later core entry, which is measured for the future HOLD/SWITCH/TRIM router."
        ),
        "core_reference": {
            "baseline": core_base,
            "stress": core_stress,
        },
        "rounds": rounds,
        "selected_for_step6_robustness": selected,
        "not_selected": [symbol for symbol in satellite_symbols if symbol not in selected],
        "final_candidate": {
            "baseline": final_base,
            "stress": final_stress,
            "baseline_vs_core": base_vs_core,
            "stress_vs_core": stress_vs_core,
        },
        "step5_pass": step5_pass,
        "next_stage": (
            "STEP6_CROSS_WINDOW_SHIFTED_FUTURE_REDTEAM_FINAL_SATELLITE_SET"
            if step5_pass
            else "STEP5_RESEARCH_REPAIR_OR_NEW_SATELLITE_HYPOTHESIS"
        ),
        "provenance_by_symbol": provenance,
        "known_router_gap": {
            "hold_switch_trim_not_implemented_here": True,
            "open_satellite_can_block_later_core": True,
            "blocked_core_no_free_slot_is_measured": True,
            "purpose": (
                "Step 5 selects complementary profitable satellites under current execution "
                "semantics. Step 7 must solve opportunity-aware HOLD/SWITCH/TRIM rather than "
                "hiding displacement with hindsight."
            ),
        },
        "safety": {
            "canonical_product_portfolio_validator_modified": False,
            "research_only_in_process_adapter": True,
            "private_credentials_used": False,
            "orders_sent": False,
            "paper_or_live_activated": False,
            "satellite_profiles_retuned_from_shared_outcome": False,
            "endpoint_mark_to_market_alone_cannot_advance_satellite": True,
            "positive_realized_completed_trade_pnl_required": True,
            "future_realized_outcome_used_for_entry_decision": False,
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "study": output["study"],
                "step5_pass": step5_pass,
                "selected_for_step6_robustness": selected,
                "not_selected": output["not_selected"],
                "baseline_vs_core": base_vs_core,
                "stress_vs_core": stress_vs_core,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
