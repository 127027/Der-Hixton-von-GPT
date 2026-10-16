"""One V8 product backtest path for the dashboard and command line."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

from hixton.backtest.account_capital import read_binance_starting_capital
from hixton.backtest.continuity import continuity_manifest_data, load_continuity_history
from hixton.backtest.diagnostics import (
    DIAGNOSTIC_MODEL,
    ISOLATED_STARTING_USDC,
    combine_coin_diagnostics,
    run_coin_diagnostic,
)
from hixton.backtest.engine import candle_snapshot_sha256
from hixton.backtest.models import CURRENT_COSTS, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.backtest.reporting import RunResult, write_report_bundle
from hixton.config import ProjectConfig
from hixton.data.storage import CandleStore
from hixton.domain.versions import strategy_definition
from hixton.paper.storage import PaperStore


def run_product_backtest(
    config: ProjectConfig,
    *,
    mode: str,
    symbol: str | None,
    report_start_utc: datetime,
    report_end_utc: datetime,
    code_commit: str,
    source_sha256: str,
) -> Path:
    strategy = strategy_definition(config.strategy_key)
    if strategy.key not in {"v8", "v8r"} or mode not in {"all", "single", "portfolio"}:
        raise ValueError("V8 product backtest requires a supported mode")
    if mode == "single" and symbol not in strategy.symbols:
        raise ValueError("single backtest requires an active strategy symbol")
    rules = {}
    with CandleStore(config.database_path, read_only=True) as store:
        for item in strategy.symbols:
            saved = store.load_symbol_rules(item)
            if (
                saved is None
                or saved.status != "TRADING"
                or not saved.spot_allowed
                or "MARKET" not in saved.order_types
            ):
                raise ValueError(f"{item}: synchronized Binance Spot rules required")
            rules[item] = ExecutionRules(
                tick_size=saved.tick_size,
                step_size=saved.step_size,
                min_qty=saved.min_qty,
                min_notional=saved.min_notional,
            )
    with PaperStore(config.database_path, read_only=True) as store:
        settings = store.load_settings()
    capital_source: dict[str, object] | None = None
    starting_cash = settings.max_capital_usdc
    target_notional = settings.target_notional_usdc
    if mode == "portfolio" and settings.auto_budget_enabled:
        capital_source = read_binance_starting_capital(config)
        starting_cash = Decimal(str(capital_source["amount_usdc"]))
        if not starting_cash.is_finite() or starting_cash <= 0:
            raise ValueError("Binance starting capital must be positive and finite")
        target_notional = (starting_cash / settings.slot_count).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        )
    if not settings.gap_fillers_enabled:
        strategy = replace(strategy, active_shared_satellites=())
    history = load_continuity_history(
        strategy=strategy,
        report_start_utc=report_start_utc,
        report_end_utc=report_end_utc,
        execution_rules=rules,
        native_database_path=config.database_path,
        cache_path=config.database_path.parent / "backtest-history.sqlite3",
    )
    result: RunResult
    if mode == "portfolio":
        result = run_shared_portfolio_backtest(
            candles_by_symbol=history.candles_by_symbol,
            execution_rules=rules,
            starting_cash=starting_cash,
            target_notional=target_notional,
            slot_count=settings.slot_count,
            strategy=strategy,
            report_start_utc=report_start_utc,
            report_end_utc=report_end_utc,
            costs=CURRENT_COSTS,
            strategy_version=strategy.version,
            reinvest_profits=settings.auto_budget_enabled,
            autonomous_spot=settings.autonomous_performance_enabled,
        )
    else:
        selected_symbols = strategy.symbols if mode == "all" else (symbol,)
        diagnostics = tuple(
            run_coin_diagnostic(
                symbol=item,
                candles_by_symbol=history.candles_by_symbol,
                execution_rules=rules,
                strategy=strategy,
                settings=settings,
                report_start_utc=report_start_utc,
                report_end_utc=report_end_utc,
                costs=CURRENT_COSTS,
            )
            for item in selected_symbols
            if item is not None
        )
        result = combine_coin_diagnostics(diagnostics) if mode == "all" else diagnostics[0]
    return write_report_bundle(
        scenarios={"current": result},
        output_root=config.run_output_root,
        config_sha256=config.sha256,
        code_commit=code_commit,
        report_start_utc=report_start_utc,
        report_end_utc=report_end_utc,
        strategy=strategy,
        python_source_sha256=source_sha256,
        history_data=continuity_manifest_data(history),
        capital_source=capital_source,
        trading_settings={
            "auto_budget_enabled": settings.auto_budget_enabled,
            "autonomous_performance_enabled": settings.autonomous_performance_enabled,
            "gap_fillers_enabled": settings.gap_fillers_enabled,
            **(
                {
                    "diagnostic_model": DIAGNOSTIC_MODEL,
                    "diagnostic_starting_cash_usdc": str(ISOLATED_STARTING_USDC),
                    "risk_limits_applied": True,
                    "market_context_sha256": {
                        s: candle_snapshot_sha256(history.candles_by_symbol[s])
                        for s in strategy.symbols
                    },
                }
                if mode != "portfolio"
                else {}
            ),
        },
    )
