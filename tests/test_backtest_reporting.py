from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from hixton.backtest.engine import run_single_backtest
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.backtest.reporting import source_fingerprint, write_report_bundle
from hixton.constants import SYMBOLS
from hixton.domain.versions import V2_RESEARCH_STRATEGY
from tests.golden_reference import deterministic_candles


def test_source_fingerprint_detects_uncommitted_python_patch(tmp_path):
    source = tmp_path / "strategy.py"
    source.write_text("rule = 1\n", encoding="utf-8")
    before = source_fingerprint(tmp_path)
    source.write_text("rule = 2\n", encoding="utf-8")
    assert source_fingerprint(tmp_path) != before
    after = source_fingerprint(tmp_path)
    (tmp_path / "unrelated.log").write_text("not executable", encoding="utf-8")
    assert after == source_fingerprint(tmp_path)


def test_v2_report_is_written_only_to_v2_with_full_strategy_snapshot(
    tmp_path: Path,
) -> None:
    candles = deterministic_candles("BTCUSDC", 500)
    result = run_single_backtest(
        symbol="BTCUSDC",
        candles=candles,
        report_start_utc=candles[400].open_time_utc,
        report_end_utc=candles[-1].open_time_utc + timedelta(hours=1),
        strategy_parameters=V2_RESEARCH_STRATEGY.parameters,
        strategy_semantics=V2_RESEARCH_STRATEGY.semantics,
        strategy_version=V2_RESEARCH_STRATEGY.version,
    )
    output_root = tmp_path / "backtests" / "v2" / "runs"
    run_directory = write_report_bundle(
        scenarios={"baseline": result},
        output_root=output_root,
        config_sha256="test-config",
        code_commit="test-commit",
        report_start_utc=candles[400].open_time_utc,
        report_end_utc=candles[-1].open_time_utc + timedelta(hours=1),
        strategy=V2_RESEARCH_STRATEGY,
    )

    manifest = json.loads((run_directory / "manifest.json").read_text(encoding="utf-8"))
    assert run_directory.parent == output_root
    assert manifest["backtest_version"] == "v2"
    assert manifest["strategy"]["version"] == V2_RESEARCH_STRATEGY.version
    assert manifest["strategy"]["semantics"] == "PINE_V6"
    assert manifest["strategy"]["parameters"]["band_multiplier"] == 3.8
    assert manifest["strategy"]["paper_approved"] is True
    assert manifest["strategy"]["slot_allocation"] == "one_per_symbol"
    assert manifest["run_mode"] == "single"
    proof = manifest["validation_scope"]
    assert proof["kind"] == "HISTORICAL_SIMULATION"
    assert proof["binance_order_execution"] == "NOT_TESTED_BY_BACKTEST"
    assert proof["live_release_granted"] is False
    assert len(proof["python_source_sha256"]) == 64


def test_shared_portfolio_report_has_one_portfolio_curve(tmp_path: Path) -> None:
    candles_by_symbol = {
        symbol: deterministic_candles(symbol, 500, market_index)
        for market_index, symbol in enumerate(SYMBOLS)
    }
    first = candles_by_symbol[SYMBOLS[0]]
    result = run_shared_portfolio_backtest(
        candles_by_symbol=candles_by_symbol,
        report_start_utc=first[400].open_time_utc,
        report_end_utc=first[-1].open_time_utc + timedelta(hours=1),
        strategy_parameters=V2_RESEARCH_STRATEGY.parameters,
        strategy_semantics=V2_RESEARCH_STRATEGY.semantics,
        strategy_version=V2_RESEARCH_STRATEGY.version,
    )
    run_directory = write_report_bundle(
        scenarios={"baseline": result},
        output_root=tmp_path / "backtests" / "v2" / "runs",
        config_sha256="test-config",
        code_commit="test-commit",
        report_start_utc=first[400].open_time_utc,
        report_end_utc=first[-1].open_time_utc + timedelta(hours=1),
        strategy=V2_RESEARCH_STRATEGY,
    )

    metrics = json.loads((run_directory / "metrics.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_directory / "manifest.json").read_text(encoding="utf-8"))
    equity = (run_directory / "equity.csv").read_text(encoding="utf-8")
    assert metrics["baseline"]["portfolio"]["starting_cash"] == "240.00"
    assert metrics["baseline"]["portfolio"]["signal_count"] == len(result.signals)
    assert metrics["baseline"]["portfolio"]["fill_count"] == len(result.fills)
    assert manifest["run_mode"] == "portfolio"
    assert "PORTFOLIO" in equity
