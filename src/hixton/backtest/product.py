"""One V8 product backtest path for the dashboard and command line."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from hixton.backtest.continuity import continuity_manifest_data, load_continuity_history
from hixton.backtest.engine import run_isolated_batch, run_single_backtest
from hixton.backtest.models import CURRENT_COSTS, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.backtest.reporting import RunResult, write_report_bundle
from hixton.config import ProjectConfig
from hixton.data.storage import CandleStore
from hixton.domain.satellite_layer import SATELLITE_PROFILE_BY_SYMBOL
from hixton.domain.versions import strategy_definition
from hixton.paper.models import PaperSettings
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
    if strategy.key != "v8" or mode not in {"all", "single", "portfolio"}:
        raise ValueError("V8 product backtest requires a supported mode")
    if mode == "single" and symbol not in strategy.symbols:
        raise ValueError("single backtest requires an active strategy symbol")
    rules = {}
    with CandleStore(config.database_path) as store:
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
    with PaperStore(config.database_path) as store:
        try:
            settings = store.load_settings()
        except RuntimeError:
            settings = PaperSettings(max_capital_usdc=config.paper_max_capital_usdc)
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
            starting_cash=settings.max_capital_usdc,
            target_notional=settings.target_notional_usdc,
            slot_count=settings.slot_count,
            strategy=strategy,
            report_start_utc=report_start_utc,
            report_end_utc=report_end_utc,
            costs=CURRENT_COSTS,
            strategy_version=strategy.version,
        )
    elif mode == "all":
        result = run_isolated_batch(
            candles_by_symbol=history.candles_by_symbol,
            execution_rules=rules,
            symbols=strategy.symbols,
            strategy_parameters=strategy.parameters,
            strategy_parameters_by_symbol=strategy.parameter_map(),
            trade_policies_by_symbol=strategy.policy_map(),
            strategy_semantics_by_symbol={s: strategy.semantics_for(s) for s in strategy.symbols},
            starting_cash_per_symbol=settings.max_capital_usdc,
            target_notional_per_symbol=settings.max_capital_usdc,
            apply_risk_limits=True,
            satellite_profiles_by_symbol=SATELLITE_PROFILE_BY_SYMBOL,
            report_start_utc=report_start_utc,
            report_end_utc=report_end_utc,
            costs=CURRENT_COSTS,
            strategy_version=strategy.version,
        )
    else:
        assert symbol is not None
        result = run_single_backtest(
            symbol=symbol,
            candles=history.candles_by_symbol[symbol],
            execution_rules=rules[symbol],
            starting_cash=settings.max_capital_usdc,
            target_notional=settings.max_capital_usdc,
            apply_risk_limits=True,
            strategy_parameters=strategy.parameters_for(symbol),
            trade_policy=strategy.policy_for(symbol),
            strategy_semantics=strategy.semantics_for(symbol),
            report_start_utc=report_start_utc,
            report_end_utc=report_end_utc,
            costs=CURRENT_COSTS,
            strategy_version=strategy.version,
            satellite_profile=SATELLITE_PROFILE_BY_SYMBOL.get(symbol),
        )
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
    )
