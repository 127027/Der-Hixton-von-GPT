"""Exhaustive shared-gap Satellite subset + Core-imminence guard search.

Training: first two one-year folds.
Validation: final year, rejection-only.
Capital search reference: 250 USDC. A validated winner is scale-checked at 1000 USDC.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from validate_15coin_satellite_integration import _histories, _maps, _metrics, _rules

from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS
from hixton.backtest.satellite_portfolio import RouterConfig, run_filler_router_portfolio
from hixton.data.binance import BinancePublicClient
from hixton.domain.capital import capital_plan
from hixton.domain.satellite_layer import CORE_SYMBOLS, SATELLITE_SYMBOLS

D = Decimal
OUTPUT = Path("evidence/shared-gap-guard-optimization.json")


@dataclass(frozen=True, slots=True)
class Candidate:
    name: str
    enabled: tuple[str, ...]
    core_guard_atr: Decimal | None = None


def _year_after(value, years: int):
    return value.replace(year=value.year + years)


def _run(
    *,
    candidate: Candidate,
    candles,
    rules,
    report_start,
    report_end,
    costs,
    max_capital: D = D("250"),
):
    parameters, policies, semantics, filters, horizons, reentry = _maps()
    plan = capital_plan(max_capital)
    symbols = CORE_SYMBOLS + candidate.enabled
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
        satellite_symbols=candidate.enabled,
        router_config=RouterConfig(
            filler_horizon_hours=24,
            hysteresis_atr=D("0"),
            satellite_budget_fraction_of_c=D("1") / D(plan.slot_count),
        ),
        strategy_semantics_by_symbol={s: semantics[s] for s in symbols},
        strict_core_idle_mask=True,
        soft_filler_exit_enabled=True,
        soft_filler_exit_symbols=frozenset(
            s for s in candidate.enabled if horizons.get(s)
        ),
        entry_filter_by_symbol={
            s: filters[s] for s in candidate.enabled if s in filters
        },
        atr_reentry_level_by_symbol={
            s: reentry[s] for s in candidate.enabled if s in reentry
        },
        filler_horizon_hours_by_symbol={
            s: horizons[s] for s in candidate.enabled if s in horizons
        },
        core_imminence_guard_atr=candidate.core_guard_atr,
    )
    metrics = _metrics(result)
    metrics["strict_idle_handoffs"] = sum(
        event.get("decision") == "STRICT_IDLE_HANDOFF" for event in events
    )
    metrics["per_satellite"] = {
        symbol: {
            "net_pnl": str(
                sum(
                    (t.realized_pnl for t in result.trades if t.symbol == symbol),
                    D("0"),
                )
            ),
            "trades": sum(t.symbol == symbol for t in result.trades),
            "preemptions": sum(
                t.symbol == symbol
                and t.exit_signal_id.startswith("STRICT_IDLE_HANDOFF::")
                for t in result.trades
            ),
            "preemption_pnl": str(
                sum(
                    (
                        t.realized_pnl
                        for t in result.trades
                        if t.symbol == symbol
                        and t.exit_signal_id.startswith("STRICT_IDLE_HANDOFF::")
                    ),
                    D("0"),
                )
            ),
        }
        for symbol in candidate.enabled
    }
    return metrics


def _core(*, candles, rules, start, end, costs, max_capital=D("250")):
    return _run(
        candidate=Candidate("CORE_ONLY", ()),
        candles=candles,
        rules=rules,
        report_start=start,
        report_end=end,
        costs=costs,
        max_capital=max_capital,
    )


def _delta(integrated, core):
    return {
        "net_pnl": str(D(integrated["net_pnl"]) - D(core["net_pnl"])),
        "ending_equity": str(
            D(integrated["ending_equity"]) - D(core["ending_equity"])
        ),
        "max_drawdown_pct": str(
            D(integrated["max_drawdown_pct"]) - D(core["max_drawdown_pct"])
        ),
        "zero_position_hours_reduced": str(
            D(core["zero_position_hours"]) - D(integrated["zero_position_hours"])
        ),
        "completed_trades": int(integrated["completed_trades"])
        - int(core["completed_trades"]),
    }


def _score(folds):
    pnl = [D(f["delta"]["net_pnl"]) for f in folds]
    idle = [D(f["delta"]["zero_position_hours_reduced"]) for f in folds]
    dd = [D(f["delta"]["max_drawdown_pct"]) for f in folds]
    robust = all(v > 0 for v in pnl) and all(v > 0 for v in idle) and max(dd) <= D("2")
    return (
        int(robust),
        min(pnl),
        sum(pnl, D("0")),
        min(idle),
        -max(dd),
    )


def _evaluate(candidate, *, candles, rules, windows, core_by_window):
    folds = []
    for label, start, end in windows:
        integrated = _run(
            candidate=candidate,
            candles=candles,
            rules=rules,
            report_start=start,
            report_end=end,
            costs=STRESS_COSTS,
        )
        folds.append(
            {
                "label": label,
                "integrated": integrated,
                "delta": _delta(integrated, core_by_window[label]),
            }
        )
    score = _score(folds)
    return {
        "candidate": {
            "name": candidate.name,
            "enabled": list(candidate.enabled),
            "core_guard_atr": (
                None if candidate.core_guard_atr is None else str(candidate.core_guard_atr)
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


def _candidate_from_row(row):
    payload = row["candidate"]
    guard = payload["core_guard_atr"]
    return Candidate(
        payload["name"],
        tuple(payload["enabled"]),
        None if guard is None else D(guard),
    )


def main():
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
        label: _core(
            candles=candles,
            rules=rules,
            start=start,
            end=end,
            costs=STRESS_COSTS,
        )
        for label, start, end in windows
    }

    # Stage 1: every non-empty Satellite subset, no imminence guard.
    stage1 = []
    for count in range(1, len(SATELLITE_SYMBOLS) + 1):
        for enabled in itertools.combinations(SATELLITE_SYMBOLS, count):
            stage1.append(Candidate("SUBSET_" + "_".join(s[:-4] for s in enabled), enabled))
    stage1_rows = [
        _evaluate(
            candidate,
            candles=candles,
            rules=rules,
            windows=windows,
            core_by_window=core_by_window,
        )
        for candidate in stage1
    ]
    ranked_stage1 = sorted(stage1_rows, key=lambda row: row["_score"], reverse=True)
    top_subsets = [_candidate_from_row(row) for row in ranked_stage1[:6]]

    # Stage 2: only the top training subsets; guard asks whether the Core gap
    # appears likely to survive long enough to justify a Satellite entry.
    guards = (D("0.10"), D("0.25"), D("0.50"), D("0.75"), D("1.00"), D("1.50"))
    stage2 = list(top_subsets)
    for base in top_subsets:
        for guard in guards:
            stage2.append(
                Candidate(f"{base.name}_G{guard}", base.enabled, guard)
            )

    unique = []
    seen = set()
    for candidate in stage2:
        key = (candidate.enabled, candidate.core_guard_atr)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    stage2_rows = [
        _evaluate(
            candidate,
            candles=candles,
            rules=rules,
            windows=windows,
            core_by_window=core_by_window,
        )
        for candidate in unique
    ]
    winner_row = max(stage2_rows, key=lambda row: row["_score"])
    winner = _candidate_from_row(winner_row)

    validation_core = _core(
        candles=candles,
        rules=rules,
        start=validation_start,
        end=report_end,
        costs=STRESS_COSTS,
    )
    validation_integrated = _run(
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
        and D(validation_delta["zero_position_hours_reduced"]) > 0
        and D(validation_delta["max_drawdown_pct"]) <= D("2")
    )

    full = {}
    for capital in (D("250"), D("1000")):
        cap_key = str(capital)
        full[cap_key] = {}
        for label, costs in (("baseline", BASELINE_COSTS), ("stress", STRESS_COSTS)):
            core = _core(
                candles=candles,
                rules=rules,
                start=report_start,
                end=report_end,
                costs=costs,
                max_capital=capital,
            )
            integrated = _run(
                candidate=winner,
                candles=candles,
                rules=rules,
                report_start=report_start,
                report_end=report_end,
                costs=costs,
                max_capital=capital,
            )
            full[cap_key][label] = {
                "capital_plan": {
                    "max_capital": str(capital_plan(capital).max_capital_usdc),
                    "slot_count": capital_plan(capital).slot_count,
                    "slot_notional": str(capital_plan(capital).target_notional_usdc),
                },
                "core_only": core,
                "integrated": integrated,
                "delta": _delta(integrated, core),
            }

    def clean(rows):
        cleaned = []
        for row in rows:
            item = dict(row)
            item.pop("_score", None)
            cleaned.append(item)
        return cleaned

    evidence = {
        "schema_version": 1,
        "purpose": "ROBUST_SHARED_GAP_FILLER_SUBSET_AND_CORE_IMMINENCE_SEARCH",
        "training_windows": [
            {"label": label, "start": start.isoformat(), "end": end.isoformat()}
            for label, start, end in windows
        ],
        "validation_window": {
            "start": validation_start.isoformat(),
            "end": report_end.isoformat(),
            "rejection_only": True,
        },
        "stage1_exhaustive_subsets": clean(stage1_rows),
        "stage2_core_imminence_guard": clean(stage2_rows),
        "training_winner": winner_row["candidate"],
        "validation": {
            "core_only": validation_core,
            "integrated": validation_integrated,
            "delta": validation_delta,
            "pass": validation_pass,
        },
        "full_three_year_scale_check": full,
        "capital_contract": "two slots, each max_capital_usdc / 2",
        "provenance": provenance,
        "orders_sent": False,
        "paper_state_modified": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
