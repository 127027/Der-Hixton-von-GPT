from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from hixton.backtest.engine import run_isolated_batch, run_single_backtest
from hixton.backtest.models import (
    BASELINE_COSTS,
    STRESS_COSTS,
    BacktestResult,
    CostModel,
    ExecutionRules,
)
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.constants import HIXTON_SPEC_VERSION, HIXTON_V2_RESEARCH_VERSION, SYMBOLS
from hixton.domain.models import (
    Candle,
    SignalAction,
    StrategyParameters,
    StrategySemantics,
)
from tests.golden_reference import deterministic_candles


def _single(costs: CostModel = BASELINE_COSTS) -> tuple[list[Candle], BacktestResult]:
    candles = deterministic_candles("ETHUSDC", 1_200, 1)
    return candles, run_single_backtest(
        symbol="ETHUSDC",
        candles=candles,
        report_start_utc=candles[400].open_time_utc,
        report_end_utc=candles[-1].open_time_utc + timedelta(hours=1),
        costs=costs,
    )


def test_fills_occur_at_next_bar_open_without_lookahead() -> None:
    candles, result = _single()
    by_signal = {fill.signal_id: fill for fill in result.fills}
    assert result.fills
    for signal in result.signals:
        fill = by_signal.get(signal.signal_id)
        if fill is None:
            continue
        expected = candles[signal.point_index + 1]
        assert fill.fill_time_utc == expected.open_time_utc
        assert fill.reference_open == Decimal(str(expected.open))


def test_isolated_target_does_not_compound_and_cash_never_goes_negative() -> None:
    _, result = _single()
    entries = [fill for fill in result.fills if fill.action is SignalAction.ENTER_LONG]
    assert len(entries) >= 2
    assert all(fill.quote_value <= Decimal("250.00") for fill in entries)
    assert all(point.cash >= 0 for point in result.equity_curve)
    assert result.metrics.starting_equity == Decimal("250.00")


def test_stress_costs_are_reported_and_reduce_same_strategy_result() -> None:
    _, baseline = _single(BASELINE_COSTS)
    _, stress = _single(STRESS_COSTS)
    assert [signal.signal_id for signal in baseline.signals] == [
        signal.signal_id for signal in stress.signals
    ]
    assert stress.metrics.modeled_spread_slippage > baseline.metrics.modeled_spread_slippage
    assert stress.metrics.ending_equity < baseline.metrics.ending_equity


def test_final_signal_is_not_filled_outside_report_window() -> None:
    candles, full = _single()
    last_signal = full.signals[-1]
    end_exclusive = candles[last_signal.point_index].open_time_utc + timedelta(hours=1)
    partial = run_single_backtest(
        symbol="ETHUSDC",
        candles=candles,
        report_start_utc=candles[400].open_time_utc,
        report_end_utc=end_exclusive,
    )
    assert partial.pending_signal_at_end is not None
    assert partial.pending_signal_at_end.signal_id == last_signal.signal_id
    assert all(fill.signal_id != last_signal.signal_id for fill in partial.fills)


def test_exchange_minimum_blocks_entry_instead_of_inventing_fill() -> None:
    candles = deterministic_candles("BTCUSDC", 1_000)
    result = run_single_backtest(
        symbol="BTCUSDC",
        candles=candles,
        report_start_utc=candles[400].open_time_utc,
        report_end_utc=candles[-1].open_time_utc + timedelta(hours=1),
        execution_rules=ExecutionRules(min_notional=Decimal("1000")),
    )
    assert not result.fills
    assert result.blocked_signals
    assert result.metrics.ending_equity == Decimal("250.00")


def test_batch_runs_exactly_ten_isolated_250_usdc_ledgers() -> None:
    candles_by_symbol = {
        symbol: deterministic_candles(symbol, 1_000, market_index)
        for market_index, symbol in enumerate(SYMBOLS)
    }
    first = candles_by_symbol[SYMBOLS[0]]
    batch = run_isolated_batch(
        candles_by_symbol=candles_by_symbol,
        report_start_utc=first[400].open_time_utc,
        report_end_utc=first[-1].open_time_utc + timedelta(hours=1),
    )
    assert len(batch.results) == 10
    assert batch.starting_equity == Decimal("2500.00")
    assert [result.symbol for result in batch.results] == list(SYMBOLS)
    assert all(result.starting_cash == Decimal("250.00") for result in batch.results)


def test_batch_drawdown_aligns_bars_not_provider_close_milliseconds() -> None:
    original = {
        symbol: deterministic_candles(symbol, 1_000, market_index)
        for market_index, symbol in enumerate(SYMBOLS)
    }
    shifted = {
        symbol: [
            replace(
                candle,
                close_time_utc=candle.close_time_utc + timedelta(milliseconds=market_index),
            )
            for candle in candles
        ]
        for market_index, (symbol, candles) in enumerate(original.items())
    }
    first = original[SYMBOLS[0]]
    report_start = first[400].open_time_utc
    report_end = first[-1].open_time_utc + timedelta(hours=1)

    reference = run_isolated_batch(
        candles_by_symbol=original,
        report_start_utc=report_start,
        report_end_utc=report_end,
    )
    varied_closes = run_isolated_batch(
        candles_by_symbol=shifted,
        report_start_utc=report_start,
        report_end_utc=report_end,
    )

    assert varied_closes.ending_equity == reference.ending_equity
    assert varied_closes.max_drawdown == reference.max_drawdown
    assert varied_closes.max_drawdown_pct == reference.max_drawdown_pct


def test_batch_rejects_missing_market() -> None:
    with pytest.raises(ValueError, match="all ten"):
        run_isolated_batch(
            candles_by_symbol={"BTCUSDC": deterministic_candles("BTCUSDC", 500)},
            report_start_utc=deterministic_candles("BTCUSDC", 500)[400].open_time_utc,
            report_end_utc=deterministic_candles("BTCUSDC", 500)[-1].open_time_utc
            + timedelta(hours=1),
        )


def test_shared_portfolio_uses_one_240_cash_ledger_and_three_fixed_slots() -> None:
    candles_by_symbol = {
        symbol: deterministic_candles(symbol, 1_200, market_index)
        for market_index, symbol in enumerate(SYMBOLS)
    }
    first = candles_by_symbol[SYMBOLS[0]]
    result = run_shared_portfolio_backtest(
        candles_by_symbol=candles_by_symbol,
        report_start_utc=first[400].open_time_utc,
        report_end_utc=first[-1].open_time_utc + timedelta(hours=1),
    )

    entries = [fill for fill in result.fills if fill.action is SignalAction.ENTER_LONG]
    assert result.metrics.starting_equity == Decimal("240.00")
    assert result.slot_count == 3
    assert result.risk_limits_applied is True
    assert result.max_concurrent_positions <= 3
    assert entries
    assert all(fill.quote_value <= Decimal("80.00") for fill in entries)
    assert all(point.cash >= 0 for point in result.equity_curve)
    assert set(result.data_snapshot_sha256_by_symbol) == set(SYMBOLS)


def test_shared_portfolio_is_deterministic() -> None:
    candles_by_symbol = {
        symbol: deterministic_candles(symbol, 900, market_index)
        for market_index, symbol in enumerate(SYMBOLS)
    }
    first = candles_by_symbol[SYMBOLS[0]]
    arguments = {
        "candles_by_symbol": candles_by_symbol,
        "report_start_utc": first[400].open_time_utc,
        "report_end_utc": first[-1].open_time_utc + timedelta(hours=1),
    }

    first_result = run_shared_portfolio_backtest(**arguments)
    second_result = run_shared_portfolio_backtest(**arguments)

    assert first_result == second_result


def test_research_parameters_and_pine_semantics_are_explicit_overrides() -> None:
    candles = deterministic_candles("ETHUSDC", 1_200, 1)
    parameters = StrategyParameters(
        vidya_length=6,
        momentum_length=20,
        smoothing_length=8,
        atr_length=60,
        band_multiplier=2.0,
    )
    research = run_single_backtest(
        symbol="ETHUSDC",
        candles=candles,
        report_start_utc=candles[400].open_time_utc,
        report_end_utc=candles[-1].open_time_utc + timedelta(hours=1),
        strategy_parameters=parameters,
        strategy_semantics=StrategySemantics.PINE_V6,
    )
    default = run_single_backtest(
        symbol="ETHUSDC",
        candles=candles,
        report_start_utc=candles[400].open_time_utc,
        report_end_utc=candles[-1].open_time_utc + timedelta(hours=1),
    )

    assert research.data_snapshot_sha256 == default.data_snapshot_sha256
    assert {signal.strategy_version for signal in research.signals} == {
        HIXTON_V2_RESEARCH_VERSION
    }
    assert {signal.strategy_version for signal in default.signals} == {
        HIXTON_SPEC_VERSION
    }
    assert [signal.signal_id for signal in research.signals] != [
        signal.signal_id for signal in default.signals
    ]
