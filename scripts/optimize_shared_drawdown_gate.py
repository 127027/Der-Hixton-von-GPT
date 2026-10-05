"""Fast third-stage search for the Shared Satellite portfolio drawdown gate.

The base candidate is the training-only winner from shared optimizer run #5:
SUI + NEAR + BCH + UNI with UNI breakout >= training q75.
Only the drawdown gate is searched here. Validation remains rejection-only.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from optimize_shared_satellite_fillers import Candidate, _core_only, _delta, _run_shared
from validate_15coin_satellite_integration import _histories, _rules

from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS
from hixton.data.binance import BinancePublicClient

D = Decimal
OUTPUT = Path("evidence/shared-satellite-dd-gate.json")
BASE = Candidate(
    "DROP_AAVE_UNI_Q75",
    ("SUIUSDC", "NEARUSDC", "UNIUSDC", "BCHUSDC"),
    (("UNIUSDC", 0.9046589627865385),),
)


def _year_after(value, years: int):
    return value.replace(year=value.year + years)


def _folds(candidate, *, candles, rules, windows, core_by_window):
    rows = []
    for label, start, end in windows:
        integrated = _run_shared(
            candidate=candidate,
            candles=candles,
            rules=rules,
            report_start=start,
            report_end=end,
            costs=STRESS_COSTS,
        )
        rows.append(
            {
                "label": label,
                "integrated": integrated,
                "delta": _delta(integrated, core_by_window[label]),
            }
        )
    return rows


def _candidate_payload(candidate: Candidate) -> dict[str, object]:
    return {
        "name": candidate.name,
        "enabled": list(candidate.enabled),
        "min_breakout": candidate.thresholds,
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
    base_delta = [D(str(row["delta"]["net_pnl"])) for row in base_folds]
    retain_min = min(base_delta) * D("0.50")
    retain_sum = sum(base_delta, D("0")) * D("0.50")

    candidates = [
        Candidate(
            f"{BASE.name}_DD{gate}",
            BASE.enabled,
            BASE.min_breakout,
            D(gate),
        )
        for gate in ("5", "10", "15", "20", "25", "30", "40", "50")
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
        deltas = [D(str(row["delta"]["net_pnl"])) for row in folds]
        dds = [D(str(row["delta"]["max_drawdown_pct"])) for row in folds]
        idle = [D(str(row["delta"]["zero_position_hours_reduced"])) for row in folds]
        retained = (
            min(deltas) >= retain_min
            and sum(deltas, D("0")) >= retain_sum
            and all(value > 0 for value in deltas)
        )
        score = (
            int(retained and max(dds) <= D("0.50")),
            -max(dds),
            min(deltas),
            sum(deltas, D("0")),
            min(idle),
        )
        rows.append(
            {
                "candidate": _candidate_payload(candidate),
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
    payload = winner_row["candidate"]
    winner = Candidate(
        str(payload["name"]),
        tuple(payload["enabled"]),
        tuple(sorted(payload["min_breakout"].items())),
        D(str(payload["max_portfolio_drawdown_pct"])),
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

    full_results = {}
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

    for row in rows:
        row.pop("_score", None)

    evidence = {
        "schema_version": 1,
        "purpose": "SHARED_250_SATELLITE_DRAWDOWN_GATE_SEARCH",
        "base_training_winner": _candidate_payload(BASE),
        "base_training_folds": base_folds,
        "retention_floor": {
            "min_fold_delta": str(retain_min),
            "sum_fold_delta": str(retain_sum),
        },
        "training_gate_search": rows,
        "training_winner": _candidate_payload(winner),
        "validation": {
            "start": validation_start.isoformat(),
            "end": report_end.isoformat(),
            "rejection_only": True,
            "core_only": validation_core,
            "integrated": validation_integrated,
            "delta": validation_delta,
            "pass": validation_pass,
        },
        "full_three_year_diagnostic": full_results,
        "provenance": provenance,
        "orders_sent": False,
        "paper_state_modified": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
