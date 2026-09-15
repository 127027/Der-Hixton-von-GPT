from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from hixton.domain.risk import PortfolioRiskState, evaluate_portfolio_risk


def _state() -> PortfolioRiskState:
    return PortfolioRiskState(
        high_water_equity_usdc=Decimal("240"),
        day_start_equity_usdc=Decimal("240"),
        day_start_date_utc="2026-09-01",
    )


def test_five_percent_daily_loss_pauses_only_until_next_utc_day() -> None:
    paused = evaluate_portfolio_risk(
        _state(),
        equity=Decimal("228"),
        at=datetime(2026, 9, 1, 18, tzinfo=UTC),
    )
    assert paused.daily_paused is True
    assert paused.state.halted is False

    next_day = evaluate_portfolio_risk(
        paused.state,
        equity=Decimal("228"),
        at=datetime(2026, 9, 2, 0, tzinfo=UTC),
    )
    assert next_day.daily_paused is False
    assert next_day.state.day_start_equity_usdc == Decimal("228")


def test_twenty_percent_high_water_drawdown_halt_is_persistent() -> None:
    halted = evaluate_portfolio_risk(
        _state(),
        equity=Decimal("192"),
        at=datetime(2026, 9, 1, 18, tzinfo=UTC),
    )
    assert halted.state.halted is True
    assert halted.state.halt_reason == "MAX_DRAWDOWN_20_PERCENT"

    recovered = evaluate_portfolio_risk(
        halted.state,
        equity=Decimal("250"),
        at=datetime(2026, 9, 1, 18, tzinfo=UTC) + timedelta(hours=1),
    )
    assert recovered.state.halted is True
