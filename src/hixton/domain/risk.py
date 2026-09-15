"""Pure shared portfolio-risk state transition for paper and mirror backtests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

ZERO = Decimal("0")
ONE = Decimal("1")
_HUNDRED = Decimal("100")
DAILY_LOSS_LIMIT_PCT = Decimal("5")
MAX_DRAWDOWN_LIMIT_PCT = Decimal("20")


@dataclass(frozen=True, slots=True)
class PortfolioRiskState:
    high_water_equity_usdc: Decimal
    day_start_equity_usdc: Decimal
    day_start_date_utc: str
    halted: bool = False
    halt_reason: str | None = None


@dataclass(frozen=True, slots=True)
class PortfolioRiskDecision:
    state: PortfolioRiskState
    daily_paused: bool
    drawdown_pct: Decimal


def evaluate_portfolio_risk(
    state: PortfolioRiskState,
    *,
    equity: Decimal,
    at: datetime,
) -> PortfolioRiskDecision:
    """Apply the frozen 5% UTC-day pause and persistent 20% drawdown halt."""

    date_text = at.astimezone(UTC).date().isoformat()
    day_start = state.day_start_equity_usdc
    if date_text != state.day_start_date_utc:
        day_start = equity
    high_water = max(state.high_water_equity_usdc, equity)
    daily_paused = equity <= day_start * (ONE - DAILY_LOSS_LIMIT_PCT / _HUNDRED)
    drawdown_pct = ZERO if high_water <= ZERO else (ONE - equity / high_water) * _HUNDRED
    halted = state.halted or drawdown_pct >= MAX_DRAWDOWN_LIMIT_PCT
    halt_reason = state.halt_reason
    if halted and halt_reason is None:
        halt_reason = "MAX_DRAWDOWN_20_PERCENT"
    return PortfolioRiskDecision(
        state=PortfolioRiskState(
            high_water_equity_usdc=high_water,
            day_start_equity_usdc=day_start,
            day_start_date_utc=date_text,
            halted=halted,
            halt_reason=halt_reason,
        ),
        daily_paused=daily_paused,
        drawdown_pct=drawdown_pct,
    )
