"""Preemption-aware short-gap refinement for AAVE, SUI and UNI.

The slot architecture is frozen at the incumbent 2-slot ranked-repeat layout.
NEAR+BCH are the shared incumbent. For each inactive Satellite, training-only
selection tests shorter filler horizons. The final year is rejection-only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from validate_15coin_satellite_integration import _histories, _maps, _metrics, _rules

from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS
from hixton.backtest.satellite_portfolio import RouterConfig, run_filler_router_portfolio
from hixton.data.binance import BinancePublicClient
from hixton.domain.allocation import RANKED_REPEAT
from hixton.domain.capital import capital_plan
from hixton.domain.satellite_layer import CORE_SYMBOLS

D = Decimal
OUTPUT = Path("evidence/short-gap-satellite-refinement.json")
REFERENCE_CAPITAL = D("250")
INCUMBENT = ("NEARUSDC", "BCHUSDC")
CHALLENGERS = ("AAVEUSDC", "SUIUSDC", "UNIUSDC")
HORIZONS = (6, 12, 18, 24, 36, 48, 72, 96)


@dataclass(frozen=True, slots=True)
class Candidate:
    symbol: str
    horizon_hours: int

    @property
    def name(self) -> str:
        return f"{self.symbol.removesuffix('USDC')}_H{self.horizon_hours}"


def _year_after(value, years: int):
    return value.replace(year=value.year + years)


def _run(
    *,
    satellites: tuple[str, ...],
    horizon_override: dict[str, int],
    candles,
    rules,
    report_start,
    report_end,
    costs,
):
    parameters, policies, semantics, filters, horizons, reentry = _maps()
    effective_horizons = dict(horizons)
    effective_horizons.update(horizon_override)
    plan = capital_plan(REFERENCE_CAPITAL)
    symbols = CORE_SYMBOLS + satellites
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
        satellite_symbols=satellites,
        router_config=RouterConfig(
            filler_horizon_hours=24,
            hysteresis_atr=D("0"),
            satellite_budget_fraction_of_c=D("1") / D(plan.slot_count),
        ),
        strategy_semantics_by_symbol={s: semantics[s] for s in symbols},
        strict_core_idle_mask=True,
        soft_filler_exit_enabled=True,
        soft_filler_exit_symbols=frozenset(
            s for s in satellites if effective_horizons.get(s)
        ),
        entry_filter_by_symbol={s: filters[s] for s in satellites if s in filters},
        atr_reentry_level_by_symbol={s: reentry[s] for s in satellites if s in reentry},
        filler_horizon_hours_by_symbol={
            s: effective_horizons[s]
            for s in satellites
            if effective_horizons.get(s)
        },
        core_allocation_policy=RANKED_REPEAT,
    )
    metrics = _metrics(result)
    metrics["handoffs"] = sum(
        event.get("decision") == "STRICT_IDLE_HANDOFF" for event in events
    )
    metrics["per_satellite"] = {
        symbol: {
            "net_pnl": str(
                sum(
                    (trade.realized_pnl for trade in result.trades if trade.symbol == symbol),
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
        for symbol in satellites
    }
    return metrics


def _delta(left: dict[str, object], right: dict[str, object]) -> dict[str, object]:
    return {
        "net_pnl": str(D(str(right["net_pnl"])) - D(str(left["net_pnl"]))),
        "ending_equity": str(
            D(str(right["ending_equity"])) - D(str(left["ending_equity"]))
        ),
        "max_drawdown_pct": str(
            D(str(right["max_drawdown_pct"])) - D(str(left["max_drawdown_pct"]))
        ),
        "zero_position_hours_reduced": str(
            D(str(left["zero_position_hours"])) - D(str(right["zero_position_hours"]))
        ),
        "completed_trades": int(right["completed_trades"]) - int(left["completed_trades"]),
    }


def _score(folds: list[dict[str, object]]) -> tuple:
    pnl = [D(str(f["delta_vs_incumbent"]["net_pnl"])) for f in folds]
    dd = [D(str(f["delta_vs_incumbent"]["max_drawdown_pct"])) for f in folds]
    idle = [
        D(str(f["delta_vs_incumbent"]["zero_position_hours_reduced"]))
        for f in folds
    ]
    robust = all(value > 0 for value in pnl) and max(dd) <= D("1.0")
    return (
        int(robust),
        min(pnl),
        sum(pnl, D("0")),
        min(idle),
        -max(dd),
    )


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

    incumbent_by_window = {
        label: _run(
            satellites=INCUMBENT,
            horizon_override={},
            candles=candles,
            rules=rules,
            report_start=start,
            report_end=end,
            costs=STRESS_COSTS,
        )
        for label, start, end in windows
    }

    per_symbol: dict[str, object] = {}
    training_winners: dict[str, Candidate] = {}
    for symbol in CHALLENGERS:
        rows = []
        for horizon in HORIZONS:
            candidate = Candidate(symbol, horizon)
            folds = []
            for label, start, end in windows:
                integrated = _run(
                    satellites=(*INCUMBENT, symbol),
                    horizon_override={symbol: horizon},
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
                        "delta_vs_incumbent": _delta(
                            incumbent_by_window[label], integrated
                        ),
                    }
                )
            score = _score(folds)
            rows.append(
                {
                    "candidate": {
                        "name": candidate.name,
                        "symbol": symbol,
                        "horizon_hours": horizon,
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
            )
        winner_row = max(rows, key=lambda row: row["_score"])
        winner = Candidate(
            symbol,
            int(winner_row["candidate"]["horizon_hours"]),
        )
        training_winners[symbol] = winner

        incumbent_validation = _run(
            satellites=INCUMBENT,
            horizon_override={},
            candles=candles,
            rules=rules,
            report_start=validation_start,
            report_end=report_end,
            costs=STRESS_COSTS,
        )
        candidate_validation = _run(
            satellites=(*INCUMBENT, symbol),
            horizon_override={symbol: winner.horizon_hours},
            candles=candles,
            rules=rules,
            report_start=validation_start,
            report_end=report_end,
            costs=STRESS_COSTS,
        )
        validation_delta = _delta(incumbent_validation, candidate_validation)
        validation_pass = (
            winner_row["_score"][0] == 1
            and D(validation_delta["net_pnl"]) > 0
            and D(validation_delta["max_drawdown_pct"]) <= D("1.0")
        )
        for row in rows:
            row.pop("_score", None)
        per_symbol[symbol] = {
            "training_search": rows,
            "training_winner": winner_row["candidate"],
            "validation": {
                "incumbent": incumbent_validation,
                "candidate": candidate_validation,
                "delta_vs_incumbent": validation_delta,
                "rejection_only": True,
                "pass": validation_pass,
            },
        }

    accepted = tuple(
        symbol
        for symbol in CHALLENGERS
        if per_symbol[symbol]["validation"]["pass"]
    )
    combined_satellites = INCUMBENT + accepted
    combined_horizons = {
        symbol: training_winners[symbol].horizon_hours for symbol in accepted
    }

    full: dict[str, object] = {}
    for cost_name, costs in (("baseline", BASELINE_COSTS), ("stress", STRESS_COSTS)):
        incumbent = _run(
            satellites=INCUMBENT,
            horizon_override={},
            candles=candles,
            rules=rules,
            report_start=report_start,
            report_end=report_end,
            costs=costs,
        )
        combined = _run(
            satellites=combined_satellites,
            horizon_override=combined_horizons,
            candles=candles,
            rules=rules,
            report_start=report_start,
            report_end=report_end,
            costs=costs,
        )
        full[cost_name] = {
            "incumbent": incumbent,
            "combined": combined,
            "delta_vs_incumbent": _delta(incumbent, combined),
        }

    evidence = {
        "schema_version": 1,
        "purpose": "PREEMPTION_AWARE_SHORT_GAP_REFINEMENT",
        "slot_layout_frozen": {
            "capital_usdc": "250",
            "slot_count": 2,
            "policy": RANKED_REPEAT,
            "slot_notional_usdc": "125",
        },
        "incumbent_satellites": list(INCUMBENT),
        "challengers": list(CHALLENGERS),
        "training_windows": [
            {"label": label, "start": start.isoformat(), "end": end.isoformat()}
            for label, start, end in windows
        ],
        "validation_window": {
            "start": validation_start.isoformat(),
            "end": report_end.isoformat(),
            "rejection_only": True,
        },
        "per_symbol": per_symbol,
        "accepted_challengers": list(accepted),
        "combined_satellites": list(combined_satellites),
        "combined_horizon_overrides": combined_horizons,
        "full_three_year": full,
        "provenance": provenance,
        "orders_sent": False,
        "paper_state_modified": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
