"""Independent red-team gate for autonomous Hixton research candidates.

This module does not search for winners. It only tries to falsify already-selected
candidates using evidence produced by independent research steps.
"""

from __future__ import annotations

import argparse
import json
from decimal import Decimal as D
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return value


def _window_gate(row: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    base = D(str(row.get("baseline_equity_delta_usdc", "0")))
    stress = D(str(row.get("stress_equity_delta_usdc", "0")))
    dd = D(str(row.get("max_drawdown_worsening_pp", "0")))
    if base < 0:
        reasons.append(f"baseline_regression={base}")
    if stress < 0:
        reasons.append(f"stress_regression={stress}")
    if dd > D("5"):
        reasons.append(f"drawdown_worsening={dd}")
    return (not reasons), reasons


def _shifted_section(section: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(section, dict):
        return {"pass": False, "reasons": ["missing_shifted_section"]}
    rows = section.get("windows")
    if not isinstance(rows, list) or not rows:
        return {"pass": False, "reasons": ["missing_shifted_windows"]}
    failures: list[dict[str, Any]] = []
    passes = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        ok, reasons = _window_gate(row)
        if ok:
            passes += 1
        else:
            failures.append(
                {"offset_hours": row.get("offset_hours"), "reasons": reasons}
            )
    minimum = int(section.get("minimum_non_regressive_windows", 4))
    aggregate_base = D(str(section.get("aggregate_baseline_delta_usdc", "0")))
    aggregate_stress = D(str(section.get("aggregate_stress_delta_usdc", "0")))
    reasons: list[str] = []
    if section.get("shifted_window_pass") is not True:
        reasons.append("producer_shifted_gate_failed")
    if passes < minimum:
        reasons.append(f"only_{passes}_of_{len(rows)}_windows_non_regressive")
    if aggregate_base <= 0:
        reasons.append(f"aggregate_baseline_not_positive={aggregate_base}")
    if aggregate_stress <= 0:
        reasons.append(f"aggregate_stress_not_positive={aggregate_stress}")
    return {
        "pass": not reasons,
        "non_regressive_windows": passes,
        "total_windows": len(rows),
        "minimum_required": minimum,
        "aggregate_baseline_delta_usdc": str(aggregate_base),
        "aggregate_stress_delta_usdc": str(aggregate_stress),
        "failed_windows": failures,
        "reasons": reasons,
    }


def evaluate(
    coin: dict[str, Any],
    layout: dict[str, Any],
    cross: dict[str, Any],
    shifted: dict[str, Any],
) -> dict[str, Any]:
    per_coin = coin.get("per_coin")
    accepted = sorted(
        str(symbol)
        for symbol, row in (per_coin.items() if isinstance(per_coin, dict) else [])
        if isinstance(row, dict) and row.get("accepted") is True
    )
    shifted_coin = shifted.get("coin_profile")
    coin_gate = _shifted_section(
        shifted_coin if isinstance(shifted_coin, dict) else None
    )
    shifted_symbols = sorted(
        str(x)
        for x in (
            shifted_coin.get("accepted_symbols", [])
            if isinstance(shifted_coin, dict)
            else []
        )
    )
    if accepted != shifted_symbols:
        coin_gate["pass"] = False
        coin_gate.setdefault("reasons", []).append(
            f"accepted_symbol_mismatch={accepted}!={shifted_symbols}"
        )

    comparison = layout.get("frequency_comparison")
    strict = (
        [str(x) for x in comparison.get("strict_frequency_improvements", [])]
        if isinstance(comparison, dict)
        else []
    )
    shifted_layout = shifted.get("layout")
    layout_gate = _shifted_section(
        shifted_layout if isinstance(shifted_layout, dict) else None
    )
    candidate_layout = (
        str(shifted_layout.get("candidate"))
        if isinstance(shifted_layout, dict)
        and shifted_layout.get("candidate") is not None
        else None
    )
    if candidate_layout and candidate_layout not in strict:
        layout_gate["pass"] = False
        layout_gate.setdefault("reasons", []).append(
            f"shifted_layout_not_in_strict_set={candidate_layout}"
        )
    if candidate_layout and (
        cross.get("candidate") != candidate_layout
        or cross.get("cross_window_pass") is not True
    ):
        layout_gate["pass"] = False
        layout_gate.setdefault("reasons", []).append(
            "ordinary_cross_window_gate_not_confirmed"
        )

    return {
        "schema_version": 1,
        "study": "AUTONOMOUS_RED_TEAM_FALSIFICATION",
        "coin_profile": {
            **coin_gate,
            "accepted_symbols": accepted,
        },
        "capital_layout": {
            **layout_gate,
            "candidate": candidate_layout,
        },
        "independent_gate": True,
        "research_only": True,
        "activation_performed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coin-evidence", type=Path, required=True)
    parser.add_argument("--layout-evidence", type=Path, required=True)
    parser.add_argument("--cross-window-evidence", type=Path, required=True)
    parser.add_argument("--shifted-window-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = evaluate(
        _load(args.coin_evidence),
        _load(args.layout_evidence),
        _load(args.cross_window_evidence),
        _load(args.shifted_window_evidence),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
