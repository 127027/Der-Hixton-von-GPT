from datetime import timedelta
from decimal import Decimal as D

import pytest

from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.domain.spot_autonomy import reinvestment_capital
from hixton.domain.versions import strategy_definition
from tests.golden_reference import deterministic_candles


@pytest.mark.parametrize(
    "equity,fraction,expected",
    [(1200, "1", 1200), (1200, ".5", 1100), (1200, "0", 1000), (800, ".5", 800), (0, ".5", 0)],
)
def test_losses_reduce_budget_and_reserves_never_become_borrowed_capital(
    equity, fraction, expected
):
    budget = reinvestment_capital(
        equity=D(equity), starting_cash=D(1000), profit_fraction=D(fraction)
    )
    assert budget == D(expected)
    assert budget <= D(equity)


@pytest.mark.parametrize("value", ["-1", "1.01", "NaN", "Infinity"])
def test_invalid_profit_fraction_is_rejected(value):
    with pytest.raises(ValueError):
        reinvestment_capital(equity=D(1200), starting_cash=D(1000), profit_fraction=D(value))


def test_research_default_preserves_complete_product_replay_and_inputs():
    strategy = strategy_definition("v8")
    candles = {symbol: deterministic_candles(symbol, 700) for symbol in strategy.symbols}
    first = next(iter(candles.values()))
    args = {
        "candles_by_symbol": candles,
        "report_start_utc": first[400].open_time_utc,
        "report_end_utc": first[-1].open_time_utc + timedelta(hours=1),
        "strategy": strategy,
        "reinvest_profits": True,
        "autonomous_spot": True,
    }
    original = run_shared_portfolio_backtest(**args)
    assert original == run_shared_portfolio_backtest(**args, profit_reinvestment_fraction=D(1))
    defensive = run_shared_portfolio_backtest(**args, profit_reinvestment_fraction=D(".5"))
    assert original.data_snapshot_sha256_by_symbol == defensive.data_snapshot_sha256_by_symbol
    assert defensive.metrics.ending_equity == defensive.equity_curve[-1].equity
    assert strategy_definition("v8") == strategy
    with pytest.raises(ValueError, match="requires reinvest_profits"):
        run_shared_portfolio_backtest(
            **{**args, "reinvest_profits": False}, profit_reinvestment_fraction=D(".5")
        )


@pytest.mark.parametrize("fraction", [D(0), D(-1), D("1.1"), D("NaN")])
def test_invalid_exposure_cannot_disable_validation(fraction):
    strategy = strategy_definition("v8")
    candles = {symbol: deterministic_candles(symbol, 405) for symbol in strategy.symbols}
    first = next(iter(candles.values()))
    with pytest.raises(ValueError, match="exposure fraction"):
        run_shared_portfolio_backtest(
            candles_by_symbol=candles,
            report_start_utc=first[400].open_time_utc,
            report_end_utc=first[-1].open_time_utc + timedelta(hours=1),
            strategy=strategy,
            reinvest_profits=True,
            capital_exposure_fraction=fraction,
        )


def test_cash_reserve_is_counted_as_equity_without_altering_price_history():
    strategy = strategy_definition("v8")
    candles = {symbol: deterministic_candles(symbol, 1000) for symbol in strategy.symbols}
    first = next(iter(candles.values()))
    args = {
        "candles_by_symbol": candles,
        "report_start_utc": first[400].open_time_utc,
        "report_end_utc": first[-1].open_time_utc + timedelta(hours=1),
        "strategy": strategy,
        "reinvest_profits": True,
        "autonomous_spot": True,
    }
    full = run_shared_portfolio_backtest(**args)
    reduced = run_shared_portfolio_backtest(**args, capital_exposure_fraction=D(".35"))
    assert full.fills and reduced.fills
    assert reduced.fills[0].quote_value < full.fills[0].quote_value
    assert full.data_snapshot_sha256_by_symbol == reduced.data_snapshot_sha256_by_symbol
    assert all(p.equity == p.cash + p.position_value for p in reduced.equity_curve)
    assert reduced.metrics.ending_equity == reduced.equity_curve[-1].equity
