from __future__ import annotations

import json
from pathlib import Path

from scripts.swarm_core import validate_migration_research_evidence

ROOT = Path(__file__).resolve().parents[1]


def test_fresh_dual_quote_and_three_year_continuity_evidence() -> None:
    evidence = validate_migration_research_evidence(ROOT)

    assert evidence["fresh_common_start_utc"] == "2024-03-24T00:00:00+00:00"
    assert evidence["limiting_usdc_symbol"] == "DOGEUSDC"
    assert evidence["same_window_usdt_ending"] == "201.1088399751235000000"
    assert evidence["same_window_usdc_ending"] == "203.62406023954500000000"
    assert evidence["three_year_portfolio_ending"] == "733.30648172557635000000"
    assert evidence["three_year_isolated_ending"] == "7152.29370844759090000000"
    assert evidence["classification"] == "NON_EQUIVALENT_HISTORY_WINDOW_DOMINATES"
    assert evidence["proxy_labelled"] is True


def test_shared_portfolio_and_isolated_batch_are_not_same_capital_context() -> None:
    report = (
        ROOT / "backtests" / "v8" / "reports" / "fresh-quote-replay-20260916.json"
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    shared = payload["portfolio_3x80"]["usdc_fresh_common"]
    isolated = payload["isolated_10x250"]

    assert shared["starting_equity"] == "250"
    assert shared["completed_trades"] == 14
    assert shared["risk_halted_at_utc"] == "2024-05-01T19:59:59.999000+00:00"
    assert isolated["usdc_fresh_common_ending_equity"] == "4007.26179461508830000000"
    assert payload["portfolio_3x80"]["usdt_full"]["risk_halted_at_utc"] == (
        "2026-02-25T05:59:59.999000+00:00"
    )
