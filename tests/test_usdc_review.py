from __future__ import annotations

import json
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from hixton.backtest.engine import run_isolated_batch
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.backtest.reporting import write_report_bundle
from hixton.backtest.usdc_review import continuous_window, run_usdc_review
from hixton.constants import SYMBOLS
from hixton.data.binance import BinancePublicClient, SymbolRules
from hixton.data.storage import CandleStore
from hixton.domain.markets import symbols_for_quote, validate_market_symbols
from hixton.domain.models import Candle
from hixton.domain.versions import V6_COIN_STRATEGY, V7_USDC_STRATEGY
from tests.golden_reference import deterministic_candles


def _candles(count: int = 500) -> dict[str, list[Candle]]:
    return {
        symbol: deterministic_candles(symbol, count, index)
        for index, symbol in enumerate(V7_USDC_STRATEGY.symbols)
    }


def test_quote_universes_and_frozen_profiles_do_not_change_v6() -> None:
    assert symbols_for_quote("USDC") == SYMBOLS
    assert validate_market_symbols(V7_USDC_STRATEGY.symbols) == "USDC"
    assert V6_COIN_STRATEGY.version == "HIXTON-V6-COIN-PAPER-1-d57f88ec2e5f"
    assert V6_COIN_STRATEGY.config_payload()["quote_asset"] == "USDC"
    assert V7_USDC_STRATEGY.config_payload()["quote_asset"] == "USDC"
    assert not V7_USDC_STRATEGY.paper_approved
    for old, new in zip(SYMBOLS, V7_USDC_STRATEGY.symbols, strict=True):
        assert V6_COIN_STRATEGY.parameters_for(old) == V7_USDC_STRATEGY.parameters_for(new)
        assert V6_COIN_STRATEGY.policy_for(old) == V7_USDC_STRATEGY.policy_for(new)
    assert V7_USDC_STRATEGY.parameters_for("BTCUSDC") == V6_COIN_STRATEGY.parameters_for("BTCUSDC")


@pytest.mark.parametrize("symbols", [SYMBOLS[::-1], SYMBOLS[:-1], ("BTCBUSD", *SYMBOLS[1:])])
def test_mixed_incomplete_or_reordered_universe_rejected(symbols: tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        validate_market_symbols(symbols)


def test_continuous_window_honors_later_listing_and_preserves_gaps() -> None:
    candles = _candles(1000)
    first = candles["BTCUSDC"]
    start, end = first[400].open_time_utc, first[-1].open_time_utc + timedelta(hours=1)
    assert continuous_window(candles, start, end)[0] == start
    candles["AVAXUSDC"] = candles["AVAXUSDC"][100:]
    actual, _ = continuous_window(candles, start, end)
    assert actual == first[500].open_time_utc
    del candles["DOTUSDC"][500]
    actual, coverage = continuous_window(candles, start, end)
    assert actual == first[901].open_time_utc
    assert coverage["DOTUSDC"]["gaps"][0]["code"] == "GAP"
    assert len(candles["DOTUSDC"]) == 999  # No synthetic fill.


@pytest.mark.parametrize(
    "problem", ["latest", "duplicate", "wrong_symbol", "ohlc", "provisional", "warmup"]
)
def test_invalid_or_insufficient_data_cannot_be_approved(problem: str) -> None:
    candles = _candles()
    first = candles["BTCUSDC"]
    start, end = first[400].open_time_utc, first[-1].open_time_utc + timedelta(hours=1)
    if problem == "latest":
        candles["BTCUSDC"] = first[:-1]
    elif problem == "duplicate":
        first.insert(100, first[100])
    elif problem == "wrong_symbol":
        first[100] = replace(first[100], symbol="BTCBUSD")
    elif problem == "ohlc":
        first[100] = replace(first[100], high=0)
    elif problem == "provisional":
        first[100] = replace(first[100], closed=False)
    else:
        candles["BTCUSDC"] = first[101:]
    with pytest.raises(ValueError):
        continuous_window(candles, start, end)


def test_both_canonical_engines_use_usdc_and_report_the_quote(tmp_path: Path) -> None:
    candles = _candles(1200)
    # Small synthetic wicks create deterministic crossings even with the wide frozen bands.
    candles = {
        symbol: [
            replace(c, high=max(c.open, c.close) + 0.01, low=min(c.open, c.close) - 0.01)
            for c in rows
        ]
        for symbol, rows in candles.items()
    }
    strategy = V7_USDC_STRATEGY
    first = candles["BTCUSDC"]
    start, end = first[400].open_time_utc, first[-1].open_time_utc + timedelta(hours=1)
    batch = run_isolated_batch(
        candles_by_symbol=candles,
        report_start_utc=start,
        report_end_utc=end,
        symbols=strategy.symbols,
        strategy_version=strategy.version,
        strategy_semantics=strategy.semantics,
        strategy_parameters_by_symbol=strategy.parameter_map(),
        trade_policies_by_symbol=strategy.policy_map(),
    )
    portfolio = run_shared_portfolio_backtest(
        candles_by_symbol=candles,
        report_start_utc=start,
        report_end_utc=end,
        symbols=strategy.symbols,
        strategy_version=strategy.version,
        strategy_semantics=strategy.semantics,
        strategy_parameters_by_symbol=strategy.parameter_map(),
        trade_policies_by_symbol=strategy.policy_map(),
        starting_cash=Decimal("250"),
    )
    assert tuple(result.symbol for result in batch.results) == strategy.symbols
    assert all(result.metrics.starting_equity == 250 for result in batch.results)
    assert portfolio.symbols == strategy.symbols
    assert portfolio.starting_cash == 250
    assert portfolio.target_notional == 80
    assert portfolio.fills
    signals = {signal.signal_id: signal for signal in portfolio.signals}
    assert all(signals[fill.signal_id].symbol.endswith("USDC") for fill in portfolio.fills)
    assert all(point.cash >= 0 for point in portfolio.equity_curve)
    assert run_isolated_batch(
        candles_by_symbol=candles, report_start_utc=start, report_end_utc=end
    ).results
    output = write_report_bundle(
        scenarios={"baseline": portfolio},
        output_root=tmp_path / "v7" / "runs",
        config_sha256="test",
        code_commit="test",
        report_start_utc=start,
        report_end_utc=end,
        strategy=strategy,
    )
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["quote_asset"] == "USDC"
    assert manifest["strategy"]["paper_approved"] is False


def test_usdc_study_pipeline_isolated_from_runtime_account(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candles = _candles()
    first = candles["BTCUSDC"]
    end = first[-1].open_time_utc + timedelta(hours=1)
    (tmp_path / "data").mkdir()
    original = tmp_path / "data" / "hixton.sqlite3"
    original.write_bytes(b"Existing account must not be opened, migrated or relabeled")
    before = original.read_bytes()
    calls: list[str] = []
    control_db = tmp_path / "data" / "control.sqlite3"
    with CandleStore(control_db) as store:
        store.put_candles(
            replace(c, symbol=symbol.removesuffix("USDC") + "USDC")
            for symbol, rows in candles.items()
            for c in rows
        )
    control_before = control_db.read_bytes()

    def rules(_self: BinancePublicClient, symbol: str) -> SymbolRules:
        return SymbolRules(
            symbol,
            "TRADING",
            symbol[:-4],
            symbol[-4:],
            True,
            ("MARKET",),
            Decimal("0.01"),
            Decimal("0.001"),
            Decimal("0.001"),
            Decimal("5"),
        )

    def fetch(_self: BinancePublicClient, symbol: str, **_kwargs: object) -> list[Candle]:
        calls.append(symbol)
        return candles[symbol]

    monkeypatch.setattr(BinancePublicClient, "symbol_rules", rules)
    monkeypatch.setattr(BinancePublicClient, "fetch_klines", fetch)
    output = run_usdc_review(
        tmp_path, end, code_commit="offline-fixture", usdc_control_database=control_db
    )
    assert calls == list(V7_USDC_STRATEGY.symbols)
    assert original.read_bytes() == before
    assert control_db.read_bytes() == control_before
    assert (tmp_path / "data" / "usdc-validation.sqlite3").exists()
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["live_ready"] is False
    assert summary["account_tradability_verified"] is False
    assert summary["full_three_years_available"] is False
    assert set(summary["windows"]) == {"available_common_history"}
    window = summary["windows"]["available_common_history"]
    assert set(window["per_coin"]) == {"baseline", "stress"}
    assert set(window["per_coin"]["baseline"]) == set(V7_USDC_STRATEGY.symbols)
    assert len(list(output.rglob("manifest.json"))) == 4
    control = summary["usdc_same_window_control"]["available_common_history"]
    assert control["start_utc"] == window["start_utc"]
    assert control["end_utc"] == window["end_utc"]
    assert control["quote_asset"] == "USDC"
    # Numeric parity for identical synthetic prices is not a claim about real market parity.
    assert (
        control["portfolio_3x80"]["baseline"]["metrics"]
        == (window["portfolio_3x80"]["baseline"]["metrics"])
    )
    assert summary["source_file_sha256"]["hixton/backtest/usdc_review.py"]


def test_usdc_metadata_does_not_pass_legacy_or_wrong_market_checks() -> None:
    rule = SymbolRules(
        "ETHUSDC",
        "TRADING",
        "ETH",
        "USDC",
        True,
        ("MARKET",),
        Decimal("0.01"),
        Decimal("0.001"),
        Decimal("0.001"),
        Decimal("5"),
    )
    assert rule.tradable_for_quote("USDC")
    assert rule.tradable_for_v1
    assert not replace(rule, quote_asset="BUSD").tradable_for_quote("USDC")
    assert not replace(rule, base_asset="BTC").tradable_for_quote("USDC")
    assert not replace(rule, status="BREAK").tradable_for_quote("USDC")
    assert not replace(rule, spot_allowed=False).tradable_for_quote("USDC")
