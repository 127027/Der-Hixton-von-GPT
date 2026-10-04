"""Bounded per-market evolution from the original Hixton V1/DMS_V1 basis.

Purpose:
- keep the validated 10-Core product untouched;
- evolve SUI/NEAR/UNI/AAVE/BCH independently from V1, never from Core V6 profiles;
- select only on the first two years of proxy history;
- use the final one-year direct-USDC window as rejection-only validation;
- favor profitable, shorter, more frequent filler opportunities with strong profit/hour.

Research-only. No orders, credentials, Paper/Live activation or product mutation.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict, replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from hixton.backtest.engine import run_single_backtest
from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS, BacktestResult, ExecutionRules
from hixton.data.binance import BinancePublicClient
from hixton.data.quality import audit_candles
from hixton.domain.models import Candle, StrategyParameters
from hixton.domain.versions import V1_STRATEGY
from hixton.runtime.supervisor import safe_closed_window

D = Decimal
BAR = timedelta(hours=1)
HOLDOUT = timedelta(days=365)
SATELLITES = ("SUIUSDC", "NEARUSDC", "UNIUSDC", "AAVEUSDC", "BCHUSDC")
CHECKPOINT = Path("agent_memory/autonomy/satellite_step4_checkpoint.json")
OUTPUT = Path("evidence/satellite-v1-evolution.json")
REFERENCE_CAPITAL = D("250")


def _rules(client: BinancePublicClient, symbol: str) -> ExecutionRules:
    saved = client.symbol_rules(symbol)
    if not saved.tradable_for_quote("USDC"):
        raise RuntimeError(f"{symbol}: current Binance USDC rules are not tradable")
    return ExecutionRules(
        tick_size=saved.tick_size,
        step_size=saved.step_size,
        min_qty=saved.min_qty,
        min_notional=saved.min_notional,
    )


def _adapt(candles: list[Candle], target_symbol: str) -> list[Candle]:
    return [
        replace(
            candle,
            symbol=target_symbol,
            source="binance_spot_usdt_proxy_for_satellite_v1_evolution",
        )
        for candle in candles
    ]


def _run(
    *,
    symbol: str,
    candles: list[Candle],
    rules: ExecutionRules,
    start,
    end,
    costs: Any,
    params: StrategyParameters,
    version: str,
) -> BacktestResult:
    return run_single_backtest(
        symbol=symbol,
        candles=candles,
        report_start_utc=start,
        report_end_utc=end,
        starting_cash=REFERENCE_CAPITAL,
        target_notional=REFERENCE_CAPITAL,
        costs=costs,
        execution_rules=rules,
        strategy_parameters=params,
        strategy_semantics=V1_STRATEGY.semantics,
        strategy_version=version,
        trade_policy=None,
    )


def _metrics(result: BacktestResult) -> dict[str, object]:
    trades = list(result.trades)
    holds = [float(t.holding_hours) for t in trades]
    position_hours = sum((t.holding_hours for t in trades), D("0"))
    active_hours = sum(1 for p in result.equity_curve if p.active_position)
    calendar_hours = len(result.equity_curve)
    completed = result.metrics.completed_trades
    return {
        "ending_equity": str(result.metrics.ending_equity),
        "net_pnl": str(result.metrics.net_pnl),
        "return_pct": str(result.metrics.return_pct),
        "completed_trades": completed,
        "winning_trades": result.metrics.winning_trades,
        "losing_trades": result.metrics.losing_trades,
        "win_rate_pct": None if result.metrics.win_rate_pct is None else str(result.metrics.win_rate_pct),
        "max_drawdown_pct": str(result.metrics.max_drawdown_pct),
        "median_holding_hours": None if not holds else str(statistics.median(holds)),
        "average_holding_hours": (
            None if result.metrics.average_holding_hours is None
            else str(result.metrics.average_holding_hours)
        ),
        "max_holding_hours": None if not holds else str(max(holds)),
        "position_hours": str(position_hours),
        "active_calendar_pct": (
            "0" if calendar_hours == 0
            else str(D(active_hours) / D(calendar_hours) * D("100"))
        ),
        "profit_per_position_hour": (
            None if position_hours <= 0 else str(result.metrics.net_pnl / position_hours)
        ),
        "cycles_per_1000_position_hours": (
            None if position_hours <= 0 else str(D(completed) / position_hours * D("1000"))
        ),
        "entry_signal_count": sum(1 for s in result.signals if s.action.value == "ENTER_LONG"),
        "exit_signal_count": sum(1 for s in result.signals if s.action.value == "EXIT_LONG"),
        "blocked_signal_count": len(result.blocked_signals),
        "open_position_at_end": result.open_position_at_end,
    }


def _params(**changes: object) -> StrategyParameters:
    base = asdict(V1_STRATEGY.parameters)
    base.update(changes)
    return StrategyParameters(**base)


def _candidate_grid() -> list[tuple[str, StrategyParameters, str]]:
    # Deliberately bounded: one-factor probes plus a small set of coherent
    # faster/slower V1-derived composites. No V6 profile values are imported.
    out: list[tuple[str, StrategyParameters, str]] = [
        ("V1_BASE", V1_STRATEGY.parameters, "baseline"),
    ]
    axes: dict[str, tuple[object, ...]] = {
        "vidya_length": (6, 8, 12, 14),
        "momentum_length": (12, 16, 24, 30),
        "smoothing_length": (6, 10, 20, 24),
        "atr_length": (48, 72, 120, 300),
        "band_multiplier": (1.2, 1.5, 1.8, 2.4, 2.8),
    }
    for axis, values in axes.items():
        for value in values:
            out.append((f"AXIS_{axis}_{value}", _params(**{axis: value}), axis))

    composites = (
        ("FAST_A", dict(vidya_length=6, momentum_length=12, smoothing_length=6, atr_length=48, band_multiplier=1.5)),
        ("FAST_B", dict(vidya_length=8, momentum_length=16, smoothing_length=8, atr_length=72, band_multiplier=1.8)),
        ("FAST_C", dict(vidya_length=8, momentum_length=12, smoothing_length=10, atr_length=120, band_multiplier=1.5)),
        ("BALANCED_A", dict(vidya_length=10, momentum_length=16, smoothing_length=10, atr_length=120, band_multiplier=1.8)),
        ("BALANCED_B", dict(vidya_length=12, momentum_length=20, smoothing_length=10, atr_length=120, band_multiplier=2.0)),
        ("BALANCED_C", dict(vidya_length=8, momentum_length=24, smoothing_length=12, atr_length=120, band_multiplier=2.0)),
        ("WIDE_FAST", dict(vidya_length=8, momentum_length=16, smoothing_length=8, atr_length=72, band_multiplier=2.4)),
        ("TIGHT_SLOW", dict(vidya_length=12, momentum_length=24, smoothing_length=20, atr_length=200, band_multiplier=1.5)),
    )
    for name, values in composites:
        out.append((name, _params(**values), "composite"))
    return out


def _decimal(metric: dict[str, object], key: str, default: str = "0") -> D:
    value = metric.get(key)
    return D(default if value is None else str(value))


def _rank_training(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    eligible = [
        row for row in rows
        if _decimal(row["baseline"], "net_pnl") > 0
        and _decimal(row["stress"], "net_pnl") > 0
        and int(row["stress"]["completed_trades"]) > 0
        and row["stress"]["profit_per_position_hour"] is not None
    ]
    if not eligible:
        return []

    def ranks(values: list[D], reverse: bool) -> dict[D, int]:
        ordered = sorted(set(values), reverse=reverse)
        return {value: idx + 1 for idx, value in enumerate(ordered)}

    pph_rank = ranks([_decimal(r["stress"], "profit_per_position_hour") for r in eligible], True)
    density_rank = ranks([_decimal(r["stress"], "cycles_per_1000_position_hours") for r in eligible], True)
    pnl_rank = ranks([_decimal(r["stress"], "net_pnl") for r in eligible], True)
    hold_values = [
        _decimal(r["stress"], "median_holding_hours", "999999")
        for r in eligible
    ]
    hold_rank = ranks(hold_values, False)

    ranked: list[dict[str, object]] = []
    for row in eligible:
        pph = _decimal(row["stress"], "profit_per_position_hour")
        density = _decimal(row["stress"], "cycles_per_1000_position_hours")
        pnl = _decimal(row["stress"], "net_pnl")
        hold = _decimal(row["stress"], "median_holding_hours", "999999")
        score = pph_rank[pph] + density_rank[density] + pnl_rank[pnl] + hold_rank[hold]
        copy = dict(row)
        copy["training_rank_score"] = score
        ranked.append(copy)

    ranked.sort(
        key=lambda r: (
            int(r["training_rank_score"]),
            -float(_decimal(r["stress"], "profit_per_position_hour")),
            -int(r["stress"]["completed_trades"]),
            float(_decimal(r["stress"], "median_holding_hours", "999999")),
        )
    )
    return ranked


def main() -> None:
    checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    sources = checkpoint.get("profiles", {})
    if set(SATELLITES) - set(sources):
        raise RuntimeError("history source lookup missing for selected Satellites")

    _, report_start, report_end = safe_closed_window()
    holdout_start = report_end - HOLDOUT
    training_end = holdout_start
    warmup = V1_STRATEGY.parameters.warmup_bars
    training_warmup_start = report_start - warmup * BAR
    holdout_warmup_start = holdout_start - warmup * BAR

    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    grid = _candidate_grid()
    per_symbol: dict[str, object] = {}
    accepted: list[str] = []

    for symbol in SATELLITES:
        proxy_symbol = str(sources[symbol]["history_source_for_training"])
        rules = _rules(client, symbol)

        proxy = _adapt(
            client.fetch_klines(proxy_symbol, start=training_warmup_start, end_exclusive=training_end),
            symbol,
        )
        audit_candles(
            proxy,
            expected_symbol=symbol,
            expected_start=training_warmup_start,
            expected_end_exclusive=training_end,
        ).require_valid()

        direct = client.fetch_klines(
            symbol,
            start=holdout_warmup_start,
            end_exclusive=report_end,
        )
        audit_candles(
            direct,
            expected_symbol=symbol,
            expected_start=holdout_warmup_start,
            expected_end_exclusive=report_end,
        ).require_valid()

        rows: list[dict[str, object]] = []
        for name, params, family in grid:
            version = f"HIXTON-SAT-V1-RESEARCH-{symbol}-{name}"
            base_result = _run(
                symbol=symbol, candles=proxy, rules=rules,
                start=report_start, end=training_end,
                costs=BASELINE_COSTS, params=params, version=version,
            )
            stress_result = _run(
                symbol=symbol, candles=proxy, rules=rules,
                start=report_start, end=training_end,
                costs=STRESS_COSTS, params=params, version=version,
            )
            rows.append({
                "name": name,
                "family": family,
                "parameters": asdict(params),
                "baseline": _metrics(base_result),
                "stress": _metrics(stress_result),
            })

        ranked = _rank_training(rows)
        champion = ranked[0] if ranked else None
        base_row = next(row for row in rows if row["name"] == "V1_BASE")

        if champion is None:
            per_symbol[symbol] = {
                "proxy_symbol": proxy_symbol,
                "training_v1_base": base_row,
                "training_candidate_count": len(rows),
                "training_eligible_positive_robust_count": 0,
                "training_champion": None,
                "holdout": None,
                "advance_to_shared_replay": False,
                "rejection_reason": "NO_POSITIVE_ROBUST_V1_DERIVED_TRAINING_CANDIDATE",
                "top_training_candidates": [],
            }
            continue

        params = StrategyParameters(**champion["parameters"])
        version = f"HIXTON-SAT-V1-CANDIDATE-{symbol}"
        holdout_base_result = _run(
            symbol=symbol, candles=direct, rules=rules,
            start=holdout_start, end=report_end,
            costs=BASELINE_COSTS, params=params, version=version,
        )
        holdout_stress_result = _run(
            symbol=symbol, candles=direct, rules=rules,
            start=holdout_start, end=report_end,
            costs=STRESS_COSTS, params=params, version=version,
        )
        holdout = {
            "baseline": _metrics(holdout_base_result),
            "stress": _metrics(holdout_stress_result),
        }

        holdout_pass = (
            _decimal(holdout["baseline"], "net_pnl") > 0
            and _decimal(holdout["stress"], "net_pnl") > 0
            and int(holdout["stress"]["completed_trades"]) > 0
            and holdout["stress"]["profit_per_position_hour"] is not None
        )
        if holdout_pass:
            accepted.append(symbol)

        # Explain what changed from unchanged V1 using TRAINING evidence only.
        diagnosis = {
            "v1_base_stress_net_pnl": base_row["stress"]["net_pnl"],
            "v1_base_stress_completed_trades": base_row["stress"]["completed_trades"],
            "v1_base_stress_median_hold_hours": base_row["stress"]["median_holding_hours"],
            "v1_base_stress_profit_per_position_hour": base_row["stress"]["profit_per_position_hour"],
            "champion_family": champion["family"],
            "champion_name": champion["name"],
            "champion_stress_net_pnl": champion["stress"]["net_pnl"],
            "champion_stress_completed_trades": champion["stress"]["completed_trades"],
            "champion_stress_median_hold_hours": champion["stress"]["median_holding_hours"],
            "champion_stress_profit_per_position_hour": champion["stress"]["profit_per_position_hour"],
        }

        per_symbol[symbol] = {
            "proxy_symbol": proxy_symbol,
            "training_v1_base": base_row,
            "training_candidate_count": len(rows),
            "training_eligible_positive_robust_count": len(ranked),
            "training_champion": champion,
            "training_diagnosis": diagnosis,
            "holdout": holdout,
            "advance_to_shared_replay": holdout_pass,
            "rejection_reason": None if holdout_pass else "DIRECT_USDC_HOLDOUT_REJECTION",
            "top_training_candidates": ranked[:5],
        }

    evidence = {
        "schema_version": 1,
        "study": "SATELLITE_V1_PER_MARKET_EVOLUTION",
        "research_only": True,
        "product_mutated": False,
        "protected_core_role": "PRIMARY_ENGINE_UNCHANGED",
        "starting_strategy": {
            "key": V1_STRATEGY.key,
            "version": V1_STRATEGY.version,
            "semantics": V1_STRATEGY.semantics.value,
            "parameters": asdict(V1_STRATEGY.parameters),
        },
        "core_v6_profiles_used_as_starting_point": False,
        "selection_contract": {
            "training_window": {
                "start_utc": report_start.isoformat(),
                "end_utc": training_end.isoformat(),
                "source": "full-history USDT proxy mapped to USDC market identity",
            },
            "holdout_window": {
                "start_utc": holdout_start.isoformat(),
                "end_utc": report_end.isoformat(),
                "source": "direct real USDC",
                "selection_allowed": False,
                "rejection_only": True,
            },
            "candidate_count_per_market": len(grid),
            "ranking": "positive baseline+stress first; then rank-sum of stress profit/hour, cycles/1000 occupied hours, stress net PnL and lower median hold",
        },
        "satellites": list(SATELLITES),
        "per_symbol": per_symbol,
        "accepted_for_shared_core_idle_replay": accepted,
        "next_stage": (
            "SATELLITE_V1_SHARED_CORE_IDLE_REPLAY"
            if accepted else
            "SATELLITE_V1_SECOND_BOUNDED_EVOLUTION"
        ),
        "owner_goal": {
            "core_active_fraction_approx": "0.10",
            "core_idle_fraction_approx": "0.90",
            "rule": "The ~90% idle period is an opportunity pool, never a quota that can override positive after-cost value or protected Core performance.",
        },
        "safety": {
            "private_credentials_used": False,
            "orders_sent": False,
            "paper_or_live_activated": False,
            "future_outcomes_used_for_selection": False,
        },
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "study": evidence["study"],
        "accepted_for_shared_core_idle_replay": accepted,
        "next_stage": evidence["next_stage"],
        "per_symbol_training_champion": {
            symbol: (
                None if per_symbol[symbol]["training_champion"] is None
                else per_symbol[symbol]["training_champion"]["name"]
            )
            for symbol in SATELLITES
        },
    }, indent=2))


if __name__ == "__main__":
    main()
