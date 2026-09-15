"""Pure metric functions; no strategy or file-system side effects."""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from decimal import Decimal
from itertools import pairwise
from math import sqrt

from hixton.backtest.models import ZERO, BacktestMetrics, EquityPoint, Fill, Trade

_HUNDRED = Decimal("100")


def _decimal(value: float) -> Decimal:
    return Decimal(str(value))


def _daily_returns(equity_curve: tuple[EquityPoint, ...]) -> list[float]:
    daily_close: OrderedDict[str, Decimal] = OrderedDict()
    for point in equity_curve:
        daily_close[point.time_utc.date().isoformat()] = point.equity
    values = list(daily_close.values())
    returns: list[float] = []
    for previous, current in pairwise(values):
        if previous > ZERO:
            returns.append(float(current / previous - Decimal("1")))
    return returns


def _annualized_ratio(returns: list[float], downside_only: bool) -> Decimal | None:
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    sample = [min(value, 0.0) for value in returns] if downside_only else returns
    variance = sum((value - (0.0 if downside_only else mean)) ** 2 for value in sample)
    variance /= len(sample) - 1
    deviation = sqrt(variance)
    if deviation == 0.0:
        return None
    return _decimal(mean / deviation * sqrt(365.0))


def drawdown(equity_curve: tuple[EquityPoint, ...]) -> tuple[Decimal, Decimal]:
    if not equity_curve:
        return ZERO, ZERO
    high = equity_curve[0].equity
    max_amount = ZERO
    max_percent = ZERO
    for point in equity_curve:
        high = max(high, point.equity)
        amount = high - point.equity
        percent = amount / high * _HUNDRED if high > ZERO else ZERO
        max_amount = max(max_amount, amount)
        max_percent = max(max_percent, percent)
    return max_amount, max_percent


def monthly_returns(equity_curve: tuple[EquityPoint, ...]) -> dict[str, Decimal]:
    if not equity_curve:
        return {}
    month_end: OrderedDict[str, Decimal] = OrderedDict()
    for point in equity_curve:
        month_end[point.time_utc.strftime("%Y-%m")] = point.equity
    result: dict[str, Decimal] = {}
    previous = equity_curve[0].equity
    for month, value in month_end.items():
        result[month] = (value / previous - Decimal("1")) * _HUNDRED if previous else ZERO
        previous = value
    return result


def calculate_metrics(
    *,
    starting_equity: Decimal,
    ending_equity: Decimal,
    report_start_utc: datetime,
    report_end_utc: datetime,
    trades: tuple[Trade, ...],
    fills: tuple[Fill, ...],
    equity_curve: tuple[EquityPoint, ...],
    buy_and_hold_ending_equity: Decimal,
) -> BacktestMetrics:
    net_pnl = ending_equity - starting_equity
    return_pct = net_pnl / starting_equity * _HUNDRED
    duration_days = Decimal(str((report_end_utc - report_start_utc).total_seconds() / 86_400))
    annualized: Decimal | None = None
    if duration_days > ZERO and ending_equity > ZERO:
        years = float(duration_days / Decimal("365.2425"))
        annualized = _decimal((float(ending_equity / starting_equity) ** (1.0 / years) - 1.0) * 100)

    max_drawdown, max_drawdown_pct = drawdown(equity_curve)
    wins = [trade.realized_pnl for trade in trades if trade.realized_pnl > ZERO]
    losses = [trade.realized_pnl for trade in trades if trade.realized_pnl < ZERO]
    gross_profit = sum(wins, ZERO)
    gross_loss = -sum(losses, ZERO)
    profit_factor = gross_profit / gross_loss if gross_loss > ZERO else None
    win_rate = Decimal(len(wins)) / Decimal(len(trades)) * _HUNDRED if trades else None
    exposure_bars = sum(point.active_position for point in equity_curve)
    exposure = (
        Decimal(exposure_bars) / Decimal(len(equity_curve)) * _HUNDRED if equity_curve else ZERO
    )
    holding = [trade.holding_hours for trade in trades]
    daily_returns = _daily_returns(equity_curve)
    sharpe = _annualized_ratio(daily_returns, downside_only=False)
    sortino = _annualized_ratio(daily_returns, downside_only=True)
    calmar = (
        annualized / max_drawdown_pct
        if annualized is not None and max_drawdown_pct > ZERO
        else None
    )
    buy_hold_return = (buy_and_hold_ending_equity / starting_equity - Decimal("1")) * _HUNDRED
    return BacktestMetrics(
        starting_equity=starting_equity,
        ending_equity=ending_equity,
        net_pnl=net_pnl,
        return_pct=return_pct,
        annualized_return_pct=annualized,
        max_drawdown=max_drawdown,
        max_drawdown_pct=max_drawdown_pct,
        completed_trades=len(trades),
        winning_trades=len(wins),
        losing_trades=len(losses),
        win_rate_pct=win_rate,
        profit_factor=profit_factor,
        average_win=sum(wins, ZERO) / Decimal(len(wins)) if wins else None,
        average_loss=sum(losses, ZERO) / Decimal(len(losses)) if losses else None,
        exposure_pct=exposure,
        total_fees=sum((fill.fee_quote_equivalent for fill in fills), ZERO),
        modeled_spread_slippage=sum((fill.modeled_spread_slippage for fill in fills), ZERO),
        average_holding_hours=sum(holding, ZERO) / Decimal(len(holding)) if holding else None,
        max_holding_hours=max(holding) if holding else None,
        sharpe=sharpe,
        sortino=sortino,
        calmar=calmar,
        buy_and_hold_ending_equity=buy_and_hold_ending_equity,
        buy_and_hold_return_pct=buy_hold_return,
        monthly_returns_pct=monthly_returns(equity_curve),
    )
