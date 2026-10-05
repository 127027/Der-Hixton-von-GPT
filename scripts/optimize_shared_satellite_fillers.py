"""Optimize the five Satellites for the real shared-capital gap-filler role.

Search direction uses two training folds only. The final year is rejection-only.
The objective is incremental stressed shared-PnL first, then idle-hour reduction,
while bounding drawdown deterioration versus Core-only.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from validate_15coin_satellite_integration import (
    _histories,
    _maps,
    _metrics,
    _rules,
)

from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS
from hixton.backtest.satellite_portfolio import RouterConfig, run_filler_router_portfolio
from hixton.data.binance import BinancePublicClient
from hixton.domain.capital import capital_plan
from hixton.domain.models import IndicatorPoint, SignalAction
from hixton.domain.satellite_layer import (
    CORE_SYMBOLS,
    SATELLITE_PROFILE_BY_SYMBOL,
    SATELLITE_SYMBOLS,
)
from hixton.domain.strategy import HixtonStrategy
from hixton.domain.trade_policy import TradePolicyGate

D = Decimal
OUTPUT = Path("evidence/shared-satellite-optimization.json")
REFERENCE_CAPITAL = D("250")


@dataclass(frozen=True, slots=True)
class Candidate:
    name: str
    enabled: tuple[str, ...]
    min_breakout: tuple[tuple[str, float], ...] = ()
    max_portfolio_drawdown_pct: Decimal | None = None

    @property
    def thresholds(self) -> dict[str, float]:
        return dict(self.min_breakout)


def _year_after(value, years: int):
    return value.replace(year=value.year + years)


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return float(ordered[index])


def _eligible_breakouts(
    *,
    symbol: str,
    candles,
    report_start,
    report_end,
) -> list[float]:
    profile = SATELLITE_PROFILE_BY_SYMBOL[symbol]
    selected = [
        candle
        for candle in candles[symbol]
        if report_start <= candle.open_time_utc < report_end
        or candle.open_time_utc < report_start
    ]
    strategy = HixtonStrategy(
        symbol,
        parameters=profile.parameters,
        semantics=profile.semantics,
        strategy_version="HIXTON-V6-SATELLITE-SHARED-SEARCH",
    )
    gate = TradePolicyGate(profile.trade_policy)
    values: list[float] = []
    for candle in selected:
        point = strategy.update(candle)
        decision = gate.decide(point)
        if candle.open_time_utc < report_start:
            continue
        if decision.signal is None or decision.signal.action is not SignalAction.ENTER_LONG:
            continue
        if decision.block_reason or profile.entry_block_reason(point):
            continue
        if point.breakout_strength is not None and point.breakout_strength > 0:
            values.append(float(point.breakout_strength))
    return values


def _filter(
    symbol: str,
    threshold: float,
) -> Callable[[IndicatorPoint], str | None]:
    profile = SATELLITE_PROFILE_BY_SYMBOL[symbol]

    def apply(point: IndicatorPoint) -> str | None:
        reason = profile.entry_block_reason(point)
        if reason:
            return reason
        if threshold > 0 and (point.breakout_strength or 0.0) < threshold:
            return "SHARED_BREAKOUT_QUALITY"
        return None

    return apply


def _run_shared(
    *,
    candidate: Candidate,
    candles,
    rules,
    report_start,
    report_end,
    costs,
    max_capital: D = REFERENCE_CAPITAL,
):
    parameters, policies, semantics, _filters, horizons, reentry = _maps()
    sats = candidate.enabled
    symbols = CORE_SYMBOLS + sats
    thresholds = candidate.thresholds
    plan = capital_plan(max_capital)
    result, events = run_filler_router_portfolio(
        candles_by_symbol={s: candles[s] for s in symbols},
        report_start_utc=report_start,
        report_end_utc=report_end,
        starting_cash=plan.max_capital_usdc,
        target_notional=plan.target_notional_usdc,
        slot_count=plan.slot_count,
        costs=costs,
        execution_rules={s: rules[s] for s in symbols},
        strategy_parameters_by_symbol={s: parameters[s] for s in symbols},
        trade_policies_by_symbol={s: policies[s] for s in symbols},
        symbols=symbols,
        core_symbols=CORE_SYMBOLS,
        satellite_symbols=sats,
        router_config=RouterConfig(
            filler_horizon_hours=24,
            hysteresis_atr=D("0"),
            satellite_budget_fraction_of_c=D("1") / D(plan.slot_count),
        ),
        strategy_semantics_by_symbol={s: semantics[s] for s in symbols},
        strict_core_idle_mask=True,
        soft_filler_exit_enabled=True,
        soft_filler_exit_symbols=frozenset(s for s in sats if horizons.get(s)),
        entry_filter_by_symbol={s: _filter(s, thresholds.get(s, 0.0)) for s in sats},
        atr_reentry_level_by_symbol={s: reentry[s] for s in sats if s in reentry},
        filler_horizon_hours_by_symbol={s: horizons[s] for s in sats if s in horizons},
        satellite_max_portfolio_drawdown_pct=candidate.max_portfolio_drawdown_pct,
    )
    metrics = _metrics(result)
    metrics["strict_idle_handoffs"] = sum(
        event.get("decision") == "STRICT_IDLE_HANDOFF" for event in events
    )
    metrics["satellite_realized_pnl"] = str(
        sum(
            (
                trade.realized_pnl
                for trade in result.trades
                if trade.symbol in SATELLITE_SYMBOLS
            ),
            D("0"),
        )
    )
    metrics["per_satellite"] = {
        symbol: {
            "net_pnl": str(
                sum(
                    (
                        trade.realized_pnl
                        for trade in result.trades
                        if trade.symbol == symbol
                    ),
                    D("0"),
                )
            ),
            "trades": sum(trade.symbol == symbol for trade in result.trades),
            "preemptions": sum(
                trade.symbol == symbol
                and trade.exit_signal_id.startswith("STRICT_IDLE_HANDOFF::")
                for trade in result.trades
            ),
            "preemption_pnl": str(
                sum(
                    (
                        trade.realized_pnl
                        for trade in result.trades
                        if trade.symbol == symbol
                        and trade.exit_signal_id.startswith("STRICT_IDLE_HANDOFF::")
                    ),
                    D("0"),
                )
            ),
        }
        for symbol in sats
    }
    return metrics


def _delta(integrated: dict[str, object], core: dict[str, object]) -> dict[str, object]:
    return {
        "net_pnl": str(D(str(integrated["net_pnl"])) - D(str(core["net_pnl"]))),
        "ending_equity": str(
            D(str(integrated["ending_equity"])) - D(str(core["ending_equity"]))
        ),
        "max_drawdown_pct": str(
            D(str(integrated["max_drawdown_pct"])) - D(str(core["max_drawdown_pct"]))
        ),
        "zero_position_hours_reduced": str(
            D(str(core["zero_position_hours"]))
            - D(str(integrated["zero_position_hours"]))
        ),
        "completed_trades": (
            int(integrated["completed_trades"]) - int(core["completed_trades"])
        ),
    }


def _core_only(*, candles, rules, report_start, report_end, costs):
    empty = Candidate("CORE_ONLY", ())
    return _run_shared(
        candidate=empty,
        candles=candles,
        rules=rules,
        report_start=report_start,
        report_end=report_end,
        costs=costs,
    )


def _score(folds: list[dict[str, object]]) -> tuple:
    deltas = [D(str(row["delta"]["net_pnl"])) for row in folds]
    idle = [D(str(row["delta"]["zero_position_hours_reduced"])) for row in folds]
    dd = [D(str(row["delta"]["max_drawdown_pct"])) for row in folds]
    both_profitable = all(value > 0 for value in deltas)
    drawdown_bounded = max(dd) <= D("2.0")
    return (
        int(both_profitable and drawdown_bounded),
        min(deltas),
        sum(deltas, D("0")),
        min(idle),
        -max(dd),
    )


def _evaluate_training(
    *,
    candidate: Candidate,
    candles,
    rules,
    windows,
    core_by_window,
) -> dict[str, object]:
    folds = []
    for label, start, end in windows:
        integrated = _run_shared(
            candidate=candidate,
            candles=candles,
            rules=rules,
            report_start=start,
            report_end=end,
            costs=STRESS_COSTS,
        )
        delta = _delta(integrated, core_by_window[label])
        folds.append(
            {
                "label": label,
                "integrated": integrated,
                "delta": delta,
            }
        )
    score = _score(folds)
    return {
        "candidate": {
            "name": candidate.name,
            "enabled": list(candidate.enabled),
            "min_breakout": dict(candidate.min_breakout),
            "max_portfolio_drawdown_pct": (
                None
                if candidate.max_portfolio_drawdown_pct is None
                else str(candidate.max_portfolio_drawdown_pct)
            ),
        },
        "folds": folds,
        "score": [
            score[0],
            str(score[1]),
            str(score[2]),
            str(score[3]),
            str(score[4]),
        ],
        "_score": score,
    }


def main() -> None:
    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    rules = _rules(client)
    report_start, report_end, candles, provenance = _histories(client)

    train_a_end = _year_after(report_start, 1)
    train_b_end = _year_after(report_start, 2)
    validation_start = train_b_end
    windows = (
        ("TRAIN_A", report_start, train_a_end),
        ("TRAIN_B", train_a_end, train_b_end),
    )

    core_by_window = {
        label: _core_only(
            candles=candles,
            rules=rules,
            report_start=start,
            report_end=end,
            costs=STRESS_COSTS,
        )
        for label, start, end in windows
    }

    breakout_quantiles: dict[str, dict[str, float]] = {}
    for symbol in SATELLITE_SYMBOLS:
        values = _eligible_breakouts(
            symbol=symbol,
            candles=candles,
            report_start=report_start,
            report_end=train_b_end,
        )
        breakout_quantiles[symbol] = {
            "count": len(values),
            "q50": _quantile(values, 0.50),
            "q75": _quantile(values, 0.75),
            "q90": _quantile(values, 0.90),
        }

    stage1: list[Candidate] = [
        Candidate("ALL_FIVE", SATELLITE_SYMBOLS),
        Candidate("DROP_SUI", tuple(s for s in SATELLITE_SYMBOLS if s != "SUIUSDC")),
        Candidate("DROP_UNI", tuple(s for s in SATELLITE_SYMBOLS if s != "UNIUSDC")),
        Candidate(
            "POSITIVE_TRIO",
            tuple(s for s in SATELLITE_SYMBOLS if s not in {"SUIUSDC", "UNIUSDC"}),
        ),
        Candidate("DROP_NEAR", tuple(s for s in SATELLITE_SYMBOLS if s != "NEARUSDC")),
        Candidate("DROP_AAVE", tuple(s for s in SATELLITE_SYMBOLS if s != "AAVEUSDC")),
        Candidate("DROP_BCH", tuple(s for s in SATELLITE_SYMBOLS if s != "BCHUSDC")),
        Candidate("NEAR_AAVE", ("NEARUSDC", "AAVEUSDC")),
    ]
    stage1_rows = [
        _evaluate_training(
            candidate=candidate,
            candles=candles,
            rules=rules,
            windows=windows,
            core_by_window=core_by_window,
        )
        for candidate in stage1
    ]
    best_row = max(stage1_rows, key=lambda row: row["_score"])
    best = Candidate(
        best_row["candidate"]["name"],
        tuple(best_row["candidate"]["enabled"]),
        tuple(sorted(best_row["candidate"]["min_breakout"].items())),
    )

    stage2: list[Candidate] = [best]
    for symbol in SATELLITE_SYMBOLS:
        for key in ("q50", "q75", "q90"):
            threshold = breakout_quantiles[symbol][key]
            enabled = tuple(dict.fromkeys((*best.enabled, symbol)))
            thresholds = dict(best.thresholds)
            thresholds[symbol] = threshold
            stage2.append(
                Candidate(
                    f"{best.name}+{symbol}_{key.upper()}",
                    enabled,
                    tuple(sorted(thresholds.items())),
                )
            )
        if symbol in best.enabled:
            enabled = tuple(s for s in best.enabled if s != symbol)
            thresholds = {
                key: value for key, value in best.thresholds.items() if key != symbol
            }
            stage2.append(
                Candidate(
                    f"{best.name}-NO_{symbol}",
                    enabled,
                    tuple(sorted(thresholds.items())),
                )
            )

    # Deduplicate exact configurations while preserving deterministic order.
    unique_stage2: list[Candidate] = []
    seen: set[tuple] = set()
    for candidate in stage2:
        key = (candidate.enabled, candidate.min_breakout)
        if key not in seen:
            seen.add(key)
            unique_stage2.append(candidate)

    stage2_rows = [
        _evaluate_training(
            candidate=candidate,
            candles=candles,
            rules=rules,
            windows=windows,
            core_by_window=core_by_window,
        )
        for candidate in unique_stage2
    ]
    winner_row = max(stage2_rows, key=lambda row: row["_score"])
    stage2_winner = Candidate(
        winner_row["candidate"]["name"],
        tuple(winner_row["candidate"]["enabled"]),
        tuple(sorted(winner_row["candidate"]["min_breakout"].items())),
    )

    # Third training-only pass: retain the profitable Shared configuration but
    # block fresh Satellite entries during deeper portfolio drawdowns.
    stage3 = [
        Candidate(
            f"{stage2_winner.name}+DD{gate}",
            stage2_winner.enabled,
            stage2_winner.min_breakout,
            D(gate),
        )
        for gate in ("5", "10", "15", "20", "25", "30", "40", "50")
    ]
    stage3_rows = [
        _evaluate_training(
            candidate=candidate,
            candles=candles,
            rules=rules,
            windows=windows,
            core_by_window=core_by_window,
        )
        for candidate in stage3
    ]

    base_fold_deltas = [
        D(str(fold["delta"]["net_pnl"])) for fold in winner_row["folds"]
    ]
    retain_min = min(base_fold_deltas) * D("0.50")
    retain_sum = sum(base_fold_deltas, D("0")) * D("0.50")

    def risk_score(row):
        fold_deltas = [D(str(fold["delta"]["net_pnl"])) for fold in row["folds"]]
        fold_dd = [D(str(fold["delta"]["max_drawdown_pct"])) for fold in row["folds"]]
        fold_idle = [
            D(str(fold["delta"]["zero_position_hours_reduced"]))
            for fold in row["folds"]
        ]
        retained = (
            min(fold_deltas) >= retain_min
            and sum(fold_deltas, D("0")) >= retain_sum
            and all(value > 0 for value in fold_deltas)
        )
        max_dd = max(fold_dd)
        return (
            int(retained and max_dd <= D("0.50")),
            -max_dd,
            min(fold_deltas),
            sum(fold_deltas, D("0")),
            min(fold_idle),
        )

    risk_winner_row = max(stage3_rows, key=risk_score)
    winner = Candidate(
        risk_winner_row["candidate"]["name"],
        tuple(risk_winner_row["candidate"]["enabled"]),
        tuple(sorted(risk_winner_row["candidate"]["min_breakout"].items())),
        D(str(risk_winner_row["candidate"]["max_portfolio_drawdown_pct"])),
    )

    validation_core = _core_only(
        candles=candles,
        rules=rules,
        report_start=validation_start,
        report_end=report_end,
        costs=STRESS_COSTS,
    )
    validation_integrated = _run_shared(
        candidate=winner,
        candles=candles,
        rules=rules,
        report_start=validation_start,
        report_end=report_end,
        costs=STRESS_COSTS,
    )
    validation_delta = _delta(validation_integrated, validation_core)
    validation_pass = (
        D(validation_delta["net_pnl"]) > 0
        and D(validation_delta["max_drawdown_pct"]) <= D("2.0")
        and D(validation_delta["zero_position_hours_reduced"]) > 0
    )

    full_results: dict[str, object] = {}
    for name, costs in (("baseline", BASELINE_COSTS), ("stress", STRESS_COSTS)):
        core = _core_only(
            candles=candles,
            rules=rules,
            report_start=report_start,
            report_end=report_end,
            costs=costs,
        )
        integrated = _run_shared(
            candidate=winner,
            candles=candles,
            rules=rules,
            report_start=report_start,
            report_end=report_end,
            costs=costs,
        )
        full_results[name] = {
            "core_only": core,
            "integrated": integrated,
            "delta": _delta(integrated, core),
        }
    def clean(rows):
        result = []
        for row in rows:
            row = dict(row)
            row.pop("_score", None)
            result.append(row)
        return result

    evidence = {
        "schema_version": 1,
        "purpose": "SHARED_PREEMPTION_AWARE_SATELLITE_OPTIMIZATION",
        "reference_capital_usdc": str(REFERENCE_CAPITAL),
        "capital_rule": "two equal 50-percent slots derived from configured max capital",
        "report_start_utc": report_start.isoformat(),
        "report_end_utc": report_end.isoformat(),
        "training_windows": [
            {"label": label, "start": start.isoformat(), "end": end.isoformat()}
            for label, start, end in windows
        ],
        "validation_window": {
            "start": validation_start.isoformat(),
            "end": report_end.isoformat(),
            "rejection_only": True,
        },
        "breakout_quantiles_training_only": breakout_quantiles,
        "stage1_subset_search": clean(stage1_rows),
        "stage2_quality_search": clean(stage2_rows),
        "stage2_training_winner": winner_row["candidate"],
        "stage3_drawdown_gate_search": clean(stage3_rows),
        "training_winner": risk_winner_row["candidate"],
        "validation": {
            "core_only": validation_core,
            "integrated": validation_integrated,
            "delta": validation_delta,
            "pass": validation_pass,
        },
        "full_three_year_results": full_results,
        "provenance": provenance,
        "orders_sent": False,
        "paper_state_modified": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
