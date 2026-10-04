"""Training-selected V1 replacement screen in genuine shared free capacity.

The ten protected Core markets remain unchanged. Replacement Satellites start from
unchanged V1/DMS_V1 entry semantics. Per-market short filler horizon is selected only
on the pre-holdout training window. Direct-USDC is rejection-only.

Unlike the earlier strict-full-idle falsification, this study allows one Satellite to
use a genuinely free shared-account slot while Core is under-deployed. The existing
point-in-time router may reclaim that filler slot for a materially superior Core
opportunity after normalized switching costs. No future realized PnL is a decision
input.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from hixton.backtest.models import (
    BASELINE_COSTS,
    STRESS_COSTS,
    CostModel,
    PortfolioBacktestResult,
    SignalAction,
)
from hixton.data.binance import BinanceApiError, BinancePublicClient
from hixton.data.quality import audit_candles
from hixton.domain.capital import capital_plan
from hixton.domain.trade_policy import TradePolicy
from hixton.domain.versions import V1_STRATEGY, V6_COIN_STRATEGY
from hixton.runtime.supervisor import safe_closed_window
from scripts.satellite_filler_router_research import (
    RouterConfig,
    run_filler_router_portfolio,
)
from scripts.satellite_shared_portfolio_research import _load_histories, _rules
from scripts.satellite_v1_shared_core_idle_replay import _window_payload

D = Decimal
CHECKPOINT = Path("agent_memory/autonomy/satellite_v1_replacement_candidates.json")
OUTPUT = Path("evidence/satellite-v1-replacement-baseline.json")
CAPITAL = D("250")
HORIZONS = (4, 8, 12)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path}: expected JSON object")
    return value


def _d(value: object) -> D:
    return D(str(value))


def _resolve_candidate_data(
    client: BinancePublicClient,
    rows: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    dict[str, str],
    dict[str, dict[str, object]],
]:
    """Resolve training source and require a continuous real-USDC holdout.

    Data eligibility is point-in-time only. No PnL, win rate, or holdout outcome is
    inspected here. Direct USDC may fall back to a continuous USDT proxy for TRAINING,
    but the rejection-only holdout must remain real USDC and must cover the complete
    validation window plus warmup without gaps.
    """

    _warmup_start, report_start, report_end = safe_closed_window()
    full_warmup_start = report_start - timedelta(hours=400)
    validation_start = report_end - timedelta(days=365)
    validation_warmup_start = validation_start - timedelta(hours=400)

    eligible_rows: list[dict[str, Any]] = []
    resolved: dict[str, str] = {}
    details: dict[str, dict[str, object]] = {}

    for row in rows:
        symbol = str(row["symbol"])
        configured = str(row["history_source"])
        chosen = configured
        training_fallback_reason: str | None = None
        holdout_error: str | None = None

        if configured == symbol:
            try:
                direct = client.fetch_klines(
                    symbol,
                    start=full_warmup_start,
                    end_exclusive=report_end,
                )
                audit_candles(
                    direct,
                    expected_symbol=symbol,
                    expected_start=full_warmup_start,
                    expected_end_exclusive=report_end,
                ).require_valid()
            except (BinanceApiError, ValueError) as exc:
                proxy = f"{symbol[:-4]}USDT"
                proxy_candles = client.fetch_klines(
                    proxy,
                    start=full_warmup_start,
                    end_exclusive=report_end,
                )
                audit_candles(
                    proxy_candles,
                    expected_symbol=proxy,
                    expected_start=full_warmup_start,
                    expected_end_exclusive=report_end,
                ).require_valid()
                chosen = proxy
                training_fallback_reason = (
                    "DIRECT_USDC_TRAINING_HISTORY_NOT_CONTIGUOUS; "
                    f"fallback_to_proxy_without_performance_selection: {exc}"
                )

        try:
            real_holdout = client.fetch_klines(
                symbol,
                start=validation_warmup_start,
                end_exclusive=report_end,
            )
            audit_candles(
                real_holdout,
                expected_symbol=symbol,
                expected_start=validation_warmup_start,
                expected_end_exclusive=report_end,
            ).require_valid()
        except (BinanceApiError, ValueError) as exc:
            holdout_error = str(exc)

        holdout_eligible = holdout_error is None
        details[symbol] = {
            "configured_source": configured,
            "resolved_training_source": chosen,
            "training_fallback_used": chosen != configured,
            "training_fallback_reason": training_fallback_reason,
            "direct_usdc_holdout_continuous": holdout_eligible,
            "direct_usdc_holdout_error": holdout_error,
        }
        if not holdout_eligible:
            continue

        eligible_rows.append(row)
        resolved[symbol] = chosen

    return eligible_rows, resolved, details


def _occupied_slot_hours(
    result: PortfolioBacktestResult,
    symbols: set[str],
) -> D:
    total = D("0")
    completed_entry_ids: set[str] = set()
    for trade in result.trades:
        if trade.symbol not in symbols:
            continue
        total += _d(trade.holding_hours) * D(trade.slot_count)
        completed_entry_ids.add(trade.entry_signal_id)

    signal_symbol = {signal.signal_id: signal.symbol for signal in result.signals}
    for fill in result.fills:
        if fill.action is not SignalAction.ENTER_LONG:
            continue
        if fill.signal_id in completed_entry_ids:
            continue
        symbol = signal_symbol.get(fill.signal_id)
        if symbol not in symbols:
            continue
        slots = max(
            1,
            int(
                (
                    _d(fill.quote_value) / _d(result.target_notional)
                ).to_integral_value()
            ),
        )
        hours = max(
            D("0"),
            D(str((result.report_end_utc - fill.fill_time_utc).total_seconds() / 3600)),
        )
        total += hours * D(slots)
    return total


def _capacity_payload(
    *,
    core: PortfolioBacktestResult,
    candidate: PortfolioBacktestResult,
    events: list[dict[str, object]],
    core_symbols: tuple[str, ...],
    satellite_symbol: str,
) -> dict[str, object]:
    payload = _window_payload(
        core=core,
        candidate=candidate,
        candidate_events=events,
        core_symbols=core_symbols,
        satellite_symbols=(satellite_symbol,),
    )
    duration_hours = D(
        str((core.report_end_utc - core.report_start_utc).total_seconds() / 3600)
    )
    total_slot_hours = duration_hours * D(core.slot_count)
    core_slot_hours = _occupied_slot_hours(core, set(core_symbols))
    free_slot_hours = max(D("0"), total_slot_hours - core_slot_hours)
    satellite_slot_hours = _occupied_slot_hours(candidate, {satellite_symbol})
    free_capacity_fill_pct = (
        D("0")
        if free_slot_hours <= 0
        else satellite_slot_hours / free_slot_hours * D("100")
    )
    satellite_pnl = _d(payload["candidate"]["satellite_realized_pnl"])
    incremental = _d(payload["candidate_vs_core"]["ending_equity_delta"])
    completed = int(payload["candidate"]["satellite_completed_cycles"])
    productive = satellite_slot_hours > 0 and completed > 0
    free_capacity_pass = (
        incremental > 0
        and satellite_pnl > 0
        and productive
    )
    payload["shared_capacity"] = {
        "total_account_slot_hours": str(total_slot_hours),
        "protected_core_occupied_slot_hours": str(core_slot_hours),
        "genuinely_free_core_slot_hours": str(free_slot_hours),
        "satellite_occupied_slot_hours": str(satellite_slot_hours),
        "free_capacity_fill_pct": str(free_capacity_fill_pct),
        "router_switch_count": payload["candidate"]["router_switch_count"],
        "router_hold_count": payload["candidate"]["router_hold_count"],
        "core_opportunities_displaced": payload["core_opportunities_displaced"],
    }
    payload["free_capacity_pass"] = free_capacity_pass
    return payload


def main() -> None:
    checkpoint = _load(CHECKPOINT)
    rows = checkpoint.get("candidates")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("replacement checkpoint has no candidates")

    typed_rows = [row for row in rows if isinstance(row, dict)]
    if len(typed_rows) != len(rows):
        raise RuntimeError("malformed replacement candidate checkpoint")

    core_symbols = V6_COIN_STRATEGY.symbols
    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    eligible_rows, satellite_sources, source_resolution = _resolve_candidate_data(
        client,
        typed_rows,
    )
    satellites = tuple(str(row["symbol"]) for row in eligible_rows)
    if not satellites:
        raise RuntimeError(
            "no replacement candidate has both continuous training history/proxy "
            "and a continuous real-USDC rejection-only holdout"
        )
    all_symbols = core_symbols + satellites
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

    params = {
        profile.symbol: profile.parameters for profile in V6_COIN_STRATEGY.coin_profiles
    }
    policies = {
        profile.symbol: profile.trade_policy for profile in V6_COIN_STRATEGY.coin_profiles
    }
    semantics = {
        symbol: V6_COIN_STRATEGY.semantics for symbol in core_symbols
    }
    for symbol in satellites:
        params[symbol] = V1_STRATEGY.parameters
        policies[symbol] = TradePolicy()
        semantics[symbol] = V1_STRATEGY.semantics

    plan = capital_plan(CAPITAL)
    fraction = plan.target_notional_usdc / CAPITAL
    core_cache: dict[tuple[str, str], PortfolioBacktestResult] = {}

    def run_core(window: str, costs: CostModel) -> PortfolioBacktestResult:
        key = (window, costs.name)
        cached = core_cache.get(key)
        if cached is not None:
            return cached
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
            strategy_parameters_by_symbol={s: params[s] for s in core_symbols},
            trade_policies_by_symbol={s: policies[s] for s in core_symbols},
            strategy_semantics_by_symbol={s: semantics[s] for s in core_symbols},
            symbols=core_symbols,
            core_symbols=core_symbols,
            satellite_symbols=(),
            router_config=RouterConfig(12, D("0"), fraction),
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
        return run_filler_router_portfolio(
            candles_by_symbol={s: candles[s] for s in symbols},
            report_start_utc=start,
            report_end_utc=end,
            starting_cash=CAPITAL,
            target_notional=plan.target_notional_usdc,
            slot_count=plan.slot_count,
            costs=costs,
            execution_rules={s: rules[s] for s in symbols},
            strategy_parameters_by_symbol={s: params[s] for s in symbols},
            trade_policies_by_symbol={s: policies[s] for s in symbols},
            strategy_semantics_by_symbol={s: semantics[s] for s in symbols},
            symbols=symbols,
            core_symbols=core_symbols,
            satellite_symbols=(symbol,),
            router_config=RouterConfig(horizon, D("0"), fraction),
            strict_core_idle_mask=False,
            soft_filler_exit_enabled=True,
        )

    per_symbol: dict[str, object] = {}
    training_survivors: list[str] = []
    holdout_survivors: list[str] = []

    for symbol in satellites:
        grid: list[dict[str, object]] = []
        for horizon in HORIZONS:
            row: dict[str, object] = {"max_holding_hours": horizon}
            for costs in (BASELINE_COSTS, STRESS_COSTS):
                core = run_core("training", costs)
                candidate, events = run_candidate(symbol, horizon, "training", costs)
                row[costs.name] = _capacity_payload(
                    core=core,
                    candidate=candidate,
                    events=events,
                    core_symbols=core_symbols,
                    satellite_symbol=symbol,
                )
            base = row[BASELINE_COSTS.name]
            stress = row[STRESS_COSTS.name]
            row["training_eligible"] = bool(base["free_capacity_pass"]) and bool(
                stress["free_capacity_pass"]
            )
            row["min_incremental_equity"] = str(
                min(
                    _d(base["candidate_vs_core"]["ending_equity_delta"]),
                    _d(stress["candidate_vs_core"]["ending_equity_delta"]),
                )
            )
            base_pph = base["candidate"]["profit_per_satellite_position_hour"]
            stress_pph = stress["candidate"]["profit_per_satellite_position_hour"]
            row["min_profit_per_position_hour"] = (
                None
                if base_pph is None or stress_pph is None
                else str(min(_d(base_pph), _d(stress_pph)))
            )
            row["min_free_capacity_fill_pct"] = str(
                min(
                    _d(base["shared_capacity"]["free_capacity_fill_pct"]),
                    _d(stress["shared_capacity"]["free_capacity_fill_pct"]),
                )
            )
            grid.append(row)

        eligible = [row for row in grid if row["training_eligible"]]
        eligible.sort(
            key=lambda row: (
                _d(row["min_incremental_equity"]),
                _d(row["min_profit_per_position_hour"] or "0"),
                _d(row["min_free_capacity_fill_pct"]),
                -int(row["max_holding_hours"]),
            ),
            reverse=True,
        )
        winner = eligible[0] if eligible else None
        if winner is None:
            per_symbol[symbol] = {
                "training_horizon_grid": grid,
                "training_champion_horizon_hours": None,
                "holdout": None,
                "advance_to_combined_shared_replay": False,
                "rejection_reason": "NO_TRAINING_ROBUST_FREE_CAPACITY_EDGE",
            }
            continue

        training_survivors.append(symbol)
        horizon = int(winner["max_holding_hours"])
        holdout: dict[str, object] = {}
        for costs in (BASELINE_COSTS, STRESS_COSTS):
            core = run_core("holdout", costs)
            candidate, events = run_candidate(symbol, horizon, "holdout", costs)
            holdout[costs.name] = _capacity_payload(
                core=core,
                candidate=candidate,
                events=events,
                core_symbols=core_symbols,
                satellite_symbol=symbol,
            )
        holdout_pass = bool(holdout[BASELINE_COSTS.name]["free_capacity_pass"]) and bool(
            holdout[STRESS_COSTS.name]["free_capacity_pass"]
        )
        if holdout_pass:
            holdout_survivors.append(symbol)

        per_symbol[symbol] = {
            "training_horizon_grid": grid,
            "training_champion_horizon_hours": horizon,
            "holdout": holdout,
            "advance_to_combined_shared_replay": holdout_pass,
            "rejection_reason": (
                None if holdout_pass else "DIRECT_USDC_FREE_CAPACITY_REJECTION"
            ),
        }

    evidence = {
        "schema_version": 1,
        "study": "SATELLITE_V1_REPLACEMENT_FREE_CAPACITY_BASELINE",
        "research_only": True,
        "product_mutated": False,
        "protected_product_sha": checkpoint.get("protected_product_sha"),
        "source_discovery_run_id": checkpoint.get("source_discovery_run_id"),
        "source_discovery_artifact_digest": checkpoint.get(
            "source_discovery_artifact_digest"
        ),
        "shared_capital_usdc": str(CAPITAL),
        "capital_plan": asdict(plan),
        "configured_replacement_candidates": [
            str(row["symbol"]) for row in typed_rows
        ],
        "tested_replacement_candidates": list(satellites),
        "data_quality_excluded_candidates": [
            str(row["symbol"])
            for row in typed_rows
            if str(row["symbol"]) not in satellites
        ],
        "horizon_family_hours": list(HORIZONS),
        "training_source_resolution": source_resolution,
        "selection_contract": {
            "unchanged_v1_entry_semantics": True,
            "training_may_select_horizon": True,
            "direct_usdc_holdout_rejection_only": True,
            "holdout_may_select_or_retune": False,
            "genuine_free_shared_slot_capacity": True,
            "materially_better_core_may_reclaim_filler": True,
            "weak_core_signal_alone_forces_exit": False,
        },
        "training_survivors": training_survivors,
        "accepted_for_combined_shared_replay": holdout_survivors,
        "per_symbol": per_symbol,
        "next_stage": (
            "SATELLITE_V1_REPLACEMENT_COMBINED_SHARED_REPLAY"
            if holdout_survivors
            else "SATELLITE_V1_REPLACEMENT_NO_SURVIVOR_REVIEW"
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
                "training_survivors": training_survivors,
                "accepted_for_combined_shared_replay": holdout_survivors,
                "training_horizons": {
                    symbol: row["training_champion_horizon_hours"]
                    for symbol, row in per_symbol.items()
                },
                "next_stage": evidence["next_stage"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
