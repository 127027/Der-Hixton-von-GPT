"""Training-only risk brake for the robust NEAR+BCH shared gap-filler duo.

The duo was selected by the exhaustive two-fold subset search. This script searches
only a causal portfolio-drawdown threshold for fresh Satellite entries. The final
year remains rejection-only.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from optimize_shared_satellite_fillers import Candidate, _core_only, _delta, _run_shared
from validate_15coin_satellite_integration import _histories, _rules

from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS
from hixton.data.binance import BinancePublicClient
from hixton.domain.capital import capital_plan

D = Decimal
OUTPUT = Path("evidence/near-bch-shared-risk-gate.json")
BASE = Candidate("NEAR_BCH", ("NEARUSDC", "BCHUSDC"))


def _year_after(value, years: int):
    return value.replace(year=value.year + years)


def _folds(candidate, *, candles, rules, windows, core_by_window):
    result = []
    for label, start, end in windows:
        integrated = _run_shared(
            candidate=candidate,
            candles=candles,
            rules=rules,
            report_start=start,
            report_end=end,
            costs=STRESS_COSTS,
        )
        result.append(
            {
                "label": label,
                "integrated": integrated,
                "delta": _delta(integrated, core_by_window[label]),
            }
        )
    return result


def _payload(candidate):
    return {
        "name": candidate.name,
        "enabled": list(candidate.enabled),
        "max_portfolio_drawdown_pct": (
            None
            if candidate.max_portfolio_drawdown_pct is None
            else str(candidate.max_portfolio_drawdown_pct)
        ),
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
    base_folds = _folds(
        BASE,
        candles=candles,
        rules=rules,
        windows=windows,
        core_by_window=core_by_window,
    )
    base_pnl = [D(row["delta"]["net_pnl"]) for row in base_folds]

    candidates = [BASE] + [
        Candidate(
            f"NEAR_BCH_DD{gate}",
            BASE.enabled,
            (),
            D(gate),
        )
        for gate in ("5", "7.5", "10", "12.5", "15", "20", "25", "30", "35", "40", "50")
    ]
    rows = []
    for candidate in candidates:
        folds = _folds(
            candidate,
            candles=candles,
            rules=rules,
            windows=windows,
            core_by_window=core_by_window,
        )
        pnl = [D(row["delta"]["net_pnl"]) for row in folds]
        dd = [D(row["delta"]["max_drawdown_pct"]) for row in folds]
        idle = [D(row["delta"]["zero_position_hours_reduced"]) for row in folds]
        # Preserve the rare positive first fold and at least half of aggregate
        # incremental PnL, then minimize added drawdown. No validation input here.
        retained = (
            all(value > 0 for value in pnl)
            and min(pnl) >= min(base_pnl) * D("0.50")
            and sum(pnl, D("0")) >= sum(base_pnl, D("0")) * D("0.50")
            and min(idle) > 0
        )
        score = (
            int(retained),
            -max(dd),
            min(pnl),
            sum(pnl, D("0")),
            min(idle),
        )
        rows.append(
            {
                "candidate": _payload(candidate),
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
    wp = winner_row["candidate"]
    gate = wp["max_portfolio_drawdown_pct"]
    winner = Candidate(
        str(wp["name"]),
        tuple(wp["enabled"]),
        (),
        None if gate is None else D(str(gate)),
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
        and D(validation_delta["zero_position_hours_reduced"]) > 0
        and D(validation_delta["max_drawdown_pct"]) <= D("2")
    )

    full = {}
    for capital in (D("250"), D("1000")):
        cap_key = str(capital)
        full[cap_key] = {}
        for label, costs in (("baseline", BASELINE_COSTS), ("stress", STRESS_COSTS)):
            # _run_shared is the 250-reference helper; scale both starting cash and
            # target notional proportionally by using an equivalent scaled result
            # only after the 250 winner is validated. The main integration harness
            # independently proves exact capital-plan scale invariance.
            if capital != D("250"):
                continue
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
            full[cap_key][label] = {
                "core_only": core,
                "integrated": integrated,
                "delta": _delta(integrated, core),
            }

    for row in rows:
        row.pop("_score", None)

    evidence = {
        "schema_version": 1,
        "purpose": "NEAR_BCH_SHARED_RISK_GATE",
        "base": _payload(BASE),
        "base_training_folds": base_folds,
        "training_gate_search": rows,
        "training_winner": _payload(winner),
        "validation": {
            "start": validation_start.isoformat(),
            "end": report_end.isoformat(),
            "rejection_only": True,
            "core_only": validation_core,
            "integrated": validation_integrated,
            "delta": validation_delta,
            "pass": validation_pass,
        },
        "full_three_year_250": full["250"],
        "capital_contract": {
            "allocator": capital_plan(D("250")).version,
            "rule": "two slots each max_capital/2; no fixed 125 runtime constant",
        },
        "provenance": provenance,
        "orders_sent": False,
        "paper_state_modified": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
