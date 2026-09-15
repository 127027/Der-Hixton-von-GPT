"""Typed immutable records emitted by the backtest engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from hixton.domain.models import Signal, SignalAction

ZERO = Decimal("0")
ONE = Decimal("1")
TEN_THOUSAND = Decimal("10000")


@dataclass(frozen=True, slots=True)
class CostModel:
    name: str
    fee_bps_per_side: Decimal
    spread_bps_per_side: Decimal
    slippage_bps_per_side: Decimal

    def __post_init__(self) -> None:
        if (
            min(
                self.fee_bps_per_side,
                self.spread_bps_per_side,
                self.slippage_bps_per_side,
            )
            < ZERO
        ):
            raise ValueError("cost basis points must be non-negative")

    @property
    def fee_rate(self) -> Decimal:
        return self.fee_bps_per_side / TEN_THOUSAND

    @property
    def adverse_price_rate(self) -> Decimal:
        return (self.spread_bps_per_side + self.slippage_bps_per_side) / TEN_THOUSAND

    @property
    def total_bps_per_side(self) -> Decimal:
        return self.fee_bps_per_side + self.spread_bps_per_side + self.slippage_bps_per_side


BASELINE_COSTS = CostModel(
    name="baseline",
    fee_bps_per_side=Decimal("10"),
    spread_bps_per_side=Decimal("2"),
    slippage_bps_per_side=Decimal("3"),
)

STRESS_COSTS = CostModel(
    name="stress",
    fee_bps_per_side=Decimal("10"),
    spread_bps_per_side=Decimal("10"),
    slippage_bps_per_side=Decimal("20"),
)


@dataclass(frozen=True, slots=True)
class ExecutionRules:
    tick_size: Decimal = ZERO
    step_size: Decimal = ZERO
    min_qty: Decimal = ZERO
    min_notional: Decimal = ZERO

    def __post_init__(self) -> None:
        if min(self.tick_size, self.step_size, self.min_qty, self.min_notional) < ZERO:
            raise ValueError("execution filters must be non-negative")


@dataclass(frozen=True, slots=True)
class Fill:
    signal_id: str
    action: SignalAction
    fill_time_utc: datetime
    reference_open: Decimal
    fill_price: Decimal
    base_quantity: Decimal
    quote_value: Decimal
    fee_quote_equivalent: Decimal
    modeled_spread_slippage: Decimal


@dataclass(frozen=True, slots=True)
class Trade:
    symbol: str
    entry_signal_id: str
    exit_signal_id: str
    entry_time_utc: datetime
    exit_time_utc: datetime
    entry_quote_spend: Decimal
    exit_quote_receive: Decimal
    realized_pnl: Decimal
    realized_return_pct: Decimal
    entry_price: Decimal
    exit_price: Decimal
    sold_base_quantity: Decimal
    residual_dust_quantity: Decimal
    holding_hours: Decimal


@dataclass(frozen=True, slots=True)
class EquityPoint:
    time_utc: datetime
    cash: Decimal
    position_value: Decimal
    equity: Decimal
    active_position: bool


@dataclass(frozen=True, slots=True)
class BacktestMetrics:
    starting_equity: Decimal
    ending_equity: Decimal
    net_pnl: Decimal
    return_pct: Decimal
    annualized_return_pct: Decimal | None
    max_drawdown: Decimal
    max_drawdown_pct: Decimal
    completed_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: Decimal | None
    profit_factor: Decimal | None
    average_win: Decimal | None
    average_loss: Decimal | None
    exposure_pct: Decimal
    total_fees: Decimal
    modeled_spread_slippage: Decimal
    average_holding_hours: Decimal | None
    max_holding_hours: Decimal | None
    sharpe: Decimal | None
    sortino: Decimal | None
    calmar: Decimal | None
    buy_and_hold_ending_equity: Decimal
    buy_and_hold_return_pct: Decimal
    monthly_returns_pct: dict[str, Decimal]


@dataclass(frozen=True, slots=True)
class BacktestResult:
    symbol: str
    report_start_utc: datetime
    report_end_utc: datetime
    warmup_start_utc: datetime
    cost_model: CostModel
    starting_cash: Decimal
    target_notional: Decimal
    signals: tuple[Signal, ...]
    fills: tuple[Fill, ...]
    trades: tuple[Trade, ...]
    equity_curve: tuple[EquityPoint, ...]
    blocked_signals: tuple[str, ...]
    pending_signal_at_end: Signal | None
    open_position_at_end: bool
    open_position_quantity: Decimal
    dust_quantity: Decimal
    metrics: BacktestMetrics
    data_snapshot_sha256: str


@dataclass(frozen=True, slots=True)
class BatchResult:
    results: tuple[BacktestResult, ...]
    starting_equity: Decimal
    ending_equity: Decimal
    net_pnl: Decimal
    return_pct: Decimal
    completed_trades: int
    max_drawdown: Decimal
    max_drawdown_pct: Decimal


@dataclass(frozen=True, slots=True)
class PortfolioBacktestResult:
    """One shared-cash ledger trading all ten DMS markets."""

    symbols: tuple[str, ...]
    report_start_utc: datetime
    report_end_utc: datetime
    warmup_start_utc: datetime
    cost_model: CostModel
    starting_cash: Decimal
    target_notional: Decimal
    slot_count: int
    slot_allocation: str
    signals: tuple[Signal, ...]
    fills: tuple[Fill, ...]
    trades: tuple[Trade, ...]
    equity_curve: tuple[EquityPoint, ...]
    blocked_signals: tuple[str, ...]
    pending_signals_at_end: tuple[Signal, ...]
    open_symbols_at_end: tuple[str, ...]
    dust_quantity_by_symbol: dict[str, Decimal]
    max_concurrent_positions: int
    risk_limits_applied: bool
    risk_halted_at_utc: datetime | None
    daily_paused_bars: int
    metrics: BacktestMetrics
    data_snapshot_sha256_by_symbol: dict[str, str]
