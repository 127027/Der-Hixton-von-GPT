"""Step-4 research: freeze one strategy per eligible satellite, then test on real USDC holdout.

This module is research-only. It does not select the final five, mutate V6, activate
Paper/Live, or place orders. Candidate strategy selection is based only on the
pre-holdout training window. The real-USDC holdout may accept/reject that frozen
winner but never retune it.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from hixton.backtest.engine import run_single_backtest
from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS, BacktestResult, ExecutionRules
from hixton.data.binance import BinancePublicClient
from hixton.data.quality import audit_candles
from hixton.domain.models import Candle, StrategyParameters
from hixton.domain.trade_policy import TradePolicy
from hixton.domain.versions import V6_COIN_STRATEGY
from hixton.runtime.supervisor import safe_closed_window

D = Decimal
BAR = timedelta(hours=1)
REAL_HOLDOUT = timedelta(days=365)
MIN_HOLDOUT_REPORT_DAYS = 300
VERSION = "HIXTON-V6-SATELLITE-STEP4-RESEARCH"


def _dt(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("expected ISO datetime string")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


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


def _adapt(candles: list[Candle], target_symbol: str, source_symbol: str) -> list[Candle]:
    if source_symbol == target_symbol:
        return candles
    return [
        replace(
            candle,
            symbol=target_symbol,
            source="binance_spot_usdt_market_proxy_for_satellite_training",
        )
        for candle in candles
    ]


def _templates() -> tuple[tuple[str, StrategyParameters, TradePolicy], ...]:
    """Deduplicate the already-proven V6 core profiles into a bounded template set."""

    rows: list[tuple[str, StrategyParameters, TradePolicy]] = [
        ("GENERIC_V6", V6_COIN_STRATEGY.parameters, TradePolicy())
    ]
    rows.extend(
        (f"CORE_TEMPLATE_{profile.symbol}", profile.parameters, profile.trade_policy)
        for profile in V6_COIN_STRATEGY.coin_profiles
    )
    seen: set[str] = set()
    unique: list[tuple[str, StrategyParameters, TradePolicy]] = []
    for name, parameters, policy in rows:
        identity = json.dumps(
            {"parameters": asdict(parameters), "trade_policy": asdict(policy)},
            sort_keys=True,
            separators=(",", ":"),
        )
        if identity in seen:
            continue
        seen.add(identity)
        unique.append((name, parameters, policy))
    return tuple(unique)


def _run(
    *,
    symbol: str,
    candles: list[Candle],
    rules: ExecutionRules,
    start: datetime,
    end: datetime,
    capital: Decimal,
    parameters: StrategyParameters,
    policy: TradePolicy,
    costs: Any,
) -> BacktestResult:
    return run_single_backtest(
        symbol=symbol,
        candles=candles,
        report_start_utc=start,
        report_end_utc=end,
        starting_cash=capital,
        target_notional=capital,
        costs=costs,
        execution_rules=rules,
        strategy_parameters=parameters,
        strategy_semantics=V6_COIN_STRATEGY.semantics,
        strategy_version=VERSION,
        trade_policy=policy,
    )


def _summary(result: BacktestResult) -> dict[str, object]:
    metrics = result.metrics
    position_hours = sum((trade.holding_hours for trade in result.trades), D("0"))
    days = D(str((result.report_end_utc - result.report_start_utc).total_seconds())) / D("86400")
    return {
        "ending_equity": str(metrics.ending_equity),
        "net_pnl": str(metrics.net_pnl),
        "return_pct": str(metrics.return_pct),
        "completed_trades": metrics.completed_trades,
        "winning_trades": metrics.winning_trades,
        "losing_trades": metrics.losing_trades,
        "win_rate_pct": None if metrics.win_rate_pct is None else str(metrics.win_rate_pct),
        "profit_factor": None if metrics.profit_factor is None else str(metrics.profit_factor),
        "max_drawdown_pct": str(metrics.max_drawdown_pct),
        "average_holding_hours": (
            None if metrics.average_holding_hours is None else str(metrics.average_holding_hours)
        ),
        "total_position_hours": str(position_hours),
        "profit_per_calendar_day": None if days <= 0 else str(metrics.net_pnl / days),
        "profit_per_position_hour": (
            None if position_hours <= 0 else str(metrics.net_pnl / position_hours)
        ),
        "blocked_signal_count": len(result.blocked_signals),
        "data_snapshot_sha256": result.data_snapshot_sha256,
    }


def _score(base: BacktestResult, stress: BacktestResult) -> tuple[Decimal, Decimal, int]:
    """Training-only robust ranking; no holdout result enters this ordering."""

    return (
        min(base.metrics.net_pnl, stress.metrics.net_pnl),
        min(base.metrics.return_pct, stress.metrics.return_pct),
        min(base.metrics.completed_trades, stress.metrics.completed_trades),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--discovery",
        default="evidence/satellite-universe-discovery.json",
        help="D19 discovery evidence produced earlier in the same workflow",
    )
    parser.add_argument(
        "--output",
        default="evidence/satellite-strategy-research.json",
    )
    parser.add_argument("--capital", default="250")
    args = parser.parse_args()

    capital = D(str(args.capital))
    if capital <= 0:
        raise ValueError("capital must be positive")

    discovery = json.loads(Path(args.discovery).read_text(encoding="utf-8"))
    eligible = discovery.get("proxy_eligible_candidates")
    if not isinstance(eligible, list) or not eligible:
        raise RuntimeError("satellite discovery contains no eligible candidates")

    _, report_start, report_end = safe_closed_window()
    templates = _templates()
    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    per_symbol: dict[str, dict[str, object]] = {}
    advancing: list[str] = []
    rejected: list[str] = []

    for raw in eligible:
        if not isinstance(raw, dict):
            continue
        symbol = str(raw["symbol"])
        discovered_source = str(raw["history_source_for_research"])
        proxy_symbol = raw.get("proxy_symbol")
        proxy_full = raw.get("proxy_three_year_history") is True
        source_symbol = (
            str(proxy_symbol)
            if proxy_full and isinstance(proxy_symbol, str) and proxy_symbol
            else discovered_source
        )
        training_source_reason = (
            "PREFER_FULL_HISTORY_USDT_PROXY"
            if source_symbol != discovered_source
            else "DISCOVERY_SOURCE"
        )
        usdc_first = _dt(raw["usdc_first_available_utc"])
        rules = _rules(client, symbol)

        # Keep a full warm-up strictly before the real-USDC evaluation window.
        warmup_bars = max(parameters.warmup_bars for _, parameters, _ in templates)
        earliest_holdout_start = usdc_first + warmup_bars * BAR
        desired_holdout_start = report_end - REAL_HOLDOUT
        holdout_start = max(desired_holdout_start, earliest_holdout_start)
        holdout_days = (report_end - holdout_start).total_seconds() / 86400
        if holdout_days < MIN_HOLDOUT_REPORT_DAYS:
            per_symbol[symbol] = {
                "status": "REJECT_INSUFFICIENT_REAL_USDC_HOLDOUT_AFTER_WARMUP",
                "real_usdc_report_days": holdout_days,
            }
            rejected.append(symbol)
            continue
        if report_start >= holdout_start:
            raise RuntimeError(f"{symbol}: no pre-holdout training interval")

        train_candles = _adapt(
            client.fetch_klines(
                source_symbol,
                start=report_start - warmup_bars * BAR,
                end_exclusive=holdout_start,
            ),
            symbol,
            source_symbol,
        )
        holdout_candles = client.fetch_klines(
            symbol,
            start=holdout_start - warmup_bars * BAR,
            end_exclusive=report_end,
        )

        try:
            audit_candles(
                train_candles,
                expected_symbol=symbol,
                expected_start=report_start - warmup_bars * BAR,
                expected_end_exclusive=holdout_start,
            ).require_valid()
            audit_candles(
                holdout_candles,
                expected_symbol=symbol,
                expected_start=holdout_start - warmup_bars * BAR,
                expected_end_exclusive=report_end,
            ).require_valid()
        except ValueError as exc:
            per_symbol[symbol] = {
                "status": "REJECT_DATA_QUALITY",
                "history_source_for_training": source_symbol,
                "discovery_history_source": discovered_source,
                "training_source_reason": training_source_reason,
                "reason": str(exc),
            }
            rejected.append(symbol)
            continue

        training_rows: list[dict[str, object]] = []
        ranked: list[
            tuple[
                tuple[Decimal, Decimal, int],
                str,
                StrategyParameters,
                TradePolicy,
                BacktestResult,
                BacktestResult,
            ]
        ] = []

        for name, parameters, policy in templates:
            base = _run(
                symbol=symbol,
                candles=train_candles,
                rules=rules,
                start=report_start,
                end=holdout_start,
                capital=capital,
                parameters=parameters,
                policy=policy,
                costs=BASELINE_COSTS,
            )
            stress = _run(
                symbol=symbol,
                candles=train_candles,
                rules=rules,
                start=report_start,
                end=holdout_start,
                capital=capital,
                parameters=parameters,
                policy=policy,
                costs=STRESS_COSTS,
            )
            score = _score(base, stress)
            training_rows.append(
                {
                    "template": name,
                    "profile": {
                        "parameters": asdict(parameters),
                        "trade_policy": asdict(policy),
                    },
                    "baseline": _summary(base),
                    "stress": _summary(stress),
                    "training_score": [str(score[0]), str(score[1]), score[2]],
                }
            )
            ranked.append((score, name, parameters, policy, base, stress))

        ranked.sort(key=lambda row: row[0], reverse=True)
        score, winner_name, winner_parameters, winner_policy, train_base, train_stress = ranked[0]

        # The winner is now frozen. Holdout evidence can only accept/reject it.
        holdout_base = _run(
            symbol=symbol,
            candles=holdout_candles,
            rules=rules,
            start=holdout_start,
            end=report_end,
            capital=capital,
            parameters=winner_parameters,
            policy=winner_policy,
            costs=BASELINE_COSTS,
        )
        holdout_stress = _run(
            symbol=symbol,
            candles=holdout_candles,
            rules=rules,
            start=holdout_start,
            end=report_end,
            capital=capital,
            parameters=winner_parameters,
            policy=winner_policy,
            costs=STRESS_COSTS,
        )

        positive_after_costs = (
            holdout_base.metrics.net_pnl > 0
            and holdout_stress.metrics.net_pnl > 0
            and holdout_base.metrics.completed_trades >= 2
            and holdout_stress.metrics.completed_trades >= 2
        )
        status = (
            "ADVANCE_TO_SHARED_PORTFOLIO_RESEARCH"
            if positive_after_costs
            else "REJECT_STEP4_REAL_USDC_HOLDOUT"
        )
        (advancing if positive_after_costs else rejected).append(symbol)

        per_symbol[symbol] = {
            "status": status,
            "history_source_for_training": source_symbol,
            "discovery_history_source": discovered_source,
            "training_source_reason": training_source_reason,
            "real_usdc_holdout_symbol": symbol,
            "training_window": {
                "start_utc": report_start.isoformat(),
                "end_utc": holdout_start.isoformat(),
            },
            "real_usdc_holdout_window": {
                "start_utc": holdout_start.isoformat(),
                "end_utc": report_end.isoformat(),
                "report_days": holdout_days,
            },
            "frozen_training_winner": {
                "template": winner_name,
                "profile": {
                    "parameters": asdict(winner_parameters),
                    "trade_policy": asdict(winner_policy),
                },
                "training_score": [str(score[0]), str(score[1]), score[2]],
                "baseline": _summary(train_base),
                "stress": _summary(train_stress),
            },
            "real_usdc_holdout": {
                "baseline": _summary(holdout_base),
                "stress": _summary(holdout_stress),
                "positive_after_costs": positive_after_costs,
            },
            "training_candidates": training_rows,
        }

    output = {
        "schema_version": 1,
        "study": "SATELLITE_STRATEGY_STEP4_RESEARCH",
        "research_only": True,
        "activation_performed": False,
        "capital_usdc_per_isolated_diagnostic": str(capital),
        "capital_semantics": (
            "Each satellite is tested independently with full C for diagnostic research; "
            "this is not aggregate live account capital."
        ),
        "strategy_template_source": "DEDUPLICATED_CURRENT_V6_CORE_PROFILES_PLUS_GENERIC_V6",
        "template_count": len(templates),
        "candidate_count": len(eligible),
        "advancing_symbols": advancing,
        "rejected_symbols": rejected,
        "per_symbol": per_symbol,
        "selection_contract": {
            "training_only_selects_profile": True,
            "real_usdc_holdout_may_retune": False,
            "final_five_selected_here": False,
            "next_stage": "SHARED_10_PLUS_UP_TO_5_PORTFOLIO_OPPORTUNITY_REPLAY",
            "advance_rule": (
                "Frozen training winner must have positive net PnL under both baseline and "
                "stress costs on the real-USDC holdout with at least two completed trades."
            ),
        },
        "safety": {
            "future_outcomes_used_for_entry_decisions": False,
            "training_prefers_full_history_proxy_when_available": True,
            "data_quality_failure_rejects_symbol_not_whole_run": True,
            "private_credentials_used": False,
            "orders_sent": False,
            "paper_or_live_activated": False,
            "core_priority_absolute": False,
        },
    }

    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "study": output["study"],
                "candidate_count": output["candidate_count"],
                "advancing_symbols": advancing,
                "rejected_symbols": rejected,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
