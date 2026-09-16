from __future__ import annotations

import json
import re
from pathlib import Path

from hixton.constants import SYMBOLS
from hixton.domain.versions import V6_COIN_STRATEGY

ROOT = Path(__file__).resolve().parents[1]
LEGACY_MARKETS = tuple(symbol.removesuffix("USDC") + "USDT" for symbol in SYMBOLS)
LEGACY_PATTERN = re.compile(r"\b(?:" + "|".join(map(re.escape, LEGACY_MARKETS)) + r")\b")


def test_active_bot_market_universe_and_strategy_quote_are_usdc() -> None:
    assert len(SYMBOLS) == 10
    assert all(symbol.endswith("USDC") for symbol in SYMBOLS)
    assert not any(symbol.endswith("USDT") for symbol in SYMBOLS)
    assert V6_COIN_STRATEGY.config_payload()["quote_asset"] == "USDC"
    assert tuple(V6_COIN_STRATEGY.symbols) == tuple(SYMBOLS)


def test_active_runtime_ui_and_config_have_no_legacy_usdt_market_symbols() -> None:
    roots = (
        ROOT / "src" / "hixton" / "constants.py",
        ROOT / "src" / "hixton" / "config.py",
        ROOT / "src" / "hixton" / "data",
        ROOT / "src" / "hixton" / "domain",
        ROOT / "src" / "hixton" / "live",
        ROOT / "src" / "hixton" / "paper",
        ROOT / "src" / "hixton" / "runtime",
        ROOT / "src" / "hixton" / "ui",
        ROOT / "config",
        ROOT / "ui" / "src",
    )
    # This file intentionally rejects an old Paper database containing legacy
    # symbols. That guard is historical compatibility/safety, not active config.
    allowed_legacy_guard = ROOT / "src" / "hixton" / "paper" / "storage.py"
    hits: list[str] = []
    for root in roots:
        files = [root] if root.is_file() else list(root.rglob("*"))
        for path in files:
            if not path.is_file() or path == allowed_legacy_guard:
                continue
            if path.suffix.lower() not in {".py", ".ts", ".json", ".html"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for line_number, line in enumerate(text.splitlines(), 1):
                for match in LEGACY_PATTERN.finditer(line):
                    hits.append(f"{path.relative_to(ROOT)}:{line_number}:{match.group(0)}")
    assert hits == [], "legacy USDT market symbol remains in active bot surface: " + "; ".join(hits)


def test_historical_reference_and_same_window_diagnosis_remain_distinct() -> None:
    diagnosis = (ROOT / "agent_memory" / "usdt_usdc_migration_diagnosis_2026-09-15.md").read_text(
        encoding="utf-8"
    )
    required_markers = (
        "733.31",
        "201.11",
        "203.62",
        "681.09",
        "431 durch Risikohalt blockiert",
        "28/28 identische Fills",
        "Kein belegter USDT->USDC-Codefehler",
        "nicht vergleichbare Startzeit / Kontopfadabhaengigkeit",
    )
    for marker in required_markers:
        assert marker in diagnosis

    audit = json.loads(
        (ROOT / "backtests" / "v8" / "reports" / "quote-migration-audit-20260915.json").read_text(
            encoding="utf-8"
        )
    )
    assert audit["original_profile_values_equal"] is True
    assert audit["original_candle_hashes_equal"] is True
    assert audit["rules_differences"] == {}
    original = audit["runs"]["original_USDT/baseline"]["portfolio"]
    assert original["starting_equity"] == "250"
    assert original["ending_equity"] == "733.30648172557635000000"
    assert original["completed_trades"] == 187


def test_paper_and_shared_portfolio_reference_replay_still_match_exactly() -> None:
    parity = json.loads(
        (ROOT / "backtests" / "v8" / "reports" / "paper-portfolio-parity-20260915.json").read_text(
            encoding="utf-8"
        )
    )
    for mode in ("whole", "restart"):
        result = parity[mode]
        assert result["fills"] == result["reference_fills"] == 28
        assert result["exact_fills_match"] is True
        assert result["exact_equity_match"] is True
        assert result["paper_equity"] == result["reference_equity"]
        assert result["paper_equity"] == "203.71861079794500000000"
