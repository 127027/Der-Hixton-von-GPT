"""Immutable paper-ledger records and runtime settings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from hixton.constants import HIXTON_SPEC_VERSION
from hixton.domain.capital import DEFAULT_MAX_CAPITAL_USDC, CapitalPlan, capital_plan

MAX_TRADING_SLOTS = 10


class PaperEventStatus(StrEnum):
    FILLED = "FILLED"
    BLOCKED = "BLOCKED"
    OBSERVED = "OBSERVED"


@dataclass(frozen=True, slots=True, init=False)
class PaperSettings:
    max_capital_usdc: Decimal
    emergency_stop: bool

    def __init__(
        self,
        max_capital_usdc: Decimal = DEFAULT_MAX_CAPITAL_USDC,
        emergency_stop: bool = False,
    ) -> None:
        plan = capital_plan(Decimal(str(max_capital_usdc)))
        if type(emergency_stop) is not bool:
            raise ValueError("paper emergency_stop must be boolean")
        object.__setattr__(self, "max_capital_usdc", plan.max_capital_usdc)
        object.__setattr__(self, "emergency_stop", emergency_stop)

    @property
    def plan(self) -> CapitalPlan:
        return capital_plan(self.max_capital_usdc)

    @property
    def slot_count(self) -> int:
        return self.plan.slot_count

    @property
    def target_notional_usdc(self) -> Decimal:
        return self.plan.target_notional_usdc

    @property
    def reserve_usdc(self) -> Decimal:
        return self.plan.reserve_usdc

    @property
    def allocation_policy(self) -> str:
        return self.plan.allocation_policy


@dataclass(frozen=True, slots=True)
class PaperAccount:
    cash_usdc: Decimal
    starting_cash_usdc: Decimal
    high_water_equity_usdc: Decimal
    day_start_equity_usdc: Decimal
    day_start_date_utc: str
    halted: bool
    halt_reason: str | None
    created_at_utc: datetime
    updated_at_utc: datetime


@dataclass(frozen=True, slots=True)
class PaperPosition:
    symbol: str
    quantity: Decimal
    average_price: Decimal
    cost_basis_usdc: Decimal
    entry_time_utc: datetime
    entry_signal_id: str
    entry_fee_usdc: Decimal
    updated_at_utc: datetime
    strategy_version: str = HIXTON_SPEC_VERSION
    slot_count: int = 1
    entry_atr: Decimal = Decimal("0")
    highest_close: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class PaperEvent:
    event_id: str
    signal_id: str
    occurred_at_utc: datetime
    symbol: str
    action: str
    status: PaperEventStatus
    reason: str | None
    reference_price: Decimal
    execution_price: Decimal | None
    base_quantity: Decimal | None
    quote_amount_usdc: Decimal | None
    fee_usdc: Decimal | None
    realized_pnl_usdc: Decimal | None
    breakout_strength: Decimal | None
    strategy_version: str = HIXTON_SPEC_VERSION
    processed_at_utc: datetime | None = None
    execution_model: str = "LEGACY_CLOSE_OR_MIGRATION"


@dataclass(frozen=True, slots=True)
class PaperStrategySession:
    strategy_key: str
    strategy_version: str
    activated_at_utc: datetime
    starting_equity_usdc: Decimal


@dataclass(frozen=True, slots=True)
class PaperPortfolio:
    account: PaperAccount
    settings: PaperSettings
    positions: tuple[PaperPosition, ...]
    equity_usdc: Decimal
    unrealized_pnl_usdc: Decimal
    daily_loss_paused: bool
    drawdown_pct: Decimal


@dataclass(frozen=True, slots=True)
class PaperSoakProgress:
    started_at_utc: datetime
    calendar_days: int
    processed_closed_bars_by_symbol: Mapping[str, int]
    minimum_processed_closed_bars: int
    completed_trades: int
    minimum_days: int
    minimum_closed_bars_per_symbol: int
    minimum_completed_trades: int
    maximum_days_when_trade_count_low: int
    status: str
    ready: bool
    blockers: tuple[str, ...]
