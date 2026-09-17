"""Runtime supervisor with the canonical V6 three-year backtest data adapter.

The running bot is inherited unchanged from RuntimeSupervisor. Only the
historical V6 backtest data source is overridden so the same active USDC
strategy can be simulated over one continuous three-year market path.
"""

from __future__ import annotations

import json
import subprocess

from hixton.backtest.continuity import continuity_manifest_data, load_continuity_history
from hixton.backtest.engine import run_isolated_batch, run_single_backtest
from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.backtest.reporting import RunResult, source_fingerprint, write_report_bundle
from hixton.data.storage import CandleStore
from hixton.domain.versions import V6_COIN_STRATEGY, strategy_definition
from hixton.paper.storage import PaperStore
from hixton.runtime.supervisor import RuntimeSupervisor as BaseRuntimeSupervisor
from hixton.runtime.supervisor import safe_closed_window


class RuntimeSupervisor(BaseRuntimeSupervisor):
    """Single Hixton runtime; only V6 historical candle sourcing is adapted."""

    def _synchronous_backtest(
        self,
        mode: str,
        symbol: str | None,
        strategy_key: str,
    ) -> None:
        strategy = strategy_definition(strategy_key)
        if strategy.key != V6_COIN_STRATEGY.key:
            super()._synchronous_backtest(mode, symbol, strategy_key)
            return
        if source_fingerprint() != self.execution_source_sha256:
            raise RuntimeError("Python-Code seit Botstart geändert: vor neuem Backtest neu starten")

        _, report_start, report_end = safe_closed_window()
        symbols = tuple(profile.symbol for profile in strategy.coin_profiles)
        rules: dict[str, ExecutionRules] = {}
        with CandleStore(self.config.database_path) as store:
            for item_symbol in symbols:
                stored = store.load_symbol_rules(item_symbol)
                if stored is None:
                    raise RuntimeError(f"Binance filters missing for {item_symbol}")
                rules[item_symbol] = ExecutionRules(
                    tick_size=stored.tick_size,
                    step_size=stored.step_size,
                    min_qty=stored.min_qty,
                    min_notional=stored.min_notional,
                )

        history = load_continuity_history(
            strategy=strategy,
            report_start_utc=report_start,
            report_end_utc=report_end,
            execution_rules=rules,
        )
        candles = history.candles_by_symbol
        scenarios: dict[str, RunResult] = {}
        with PaperStore(self.config.database_path) as store:
            paper_settings = store.load_settings()

        for costs in (BASELINE_COSTS, STRESS_COSTS):
            if mode == "all":
                scenarios[costs.name] = run_isolated_batch(
                    candles_by_symbol=candles,
                    report_start_utc=report_start,
                    report_end_utc=report_end,
                    costs=costs,
                    execution_rules=rules,
                    strategy_parameters=strategy.parameters,
                    strategy_parameters_by_symbol=strategy.parameter_map(),
                    trade_policies_by_symbol=strategy.policy_map(),
                    strategy_semantics=strategy.semantics,
                    strategy_version=strategy.version,
                    symbols=symbols,
                )
            elif mode == "portfolio":
                scenarios[costs.name] = run_shared_portfolio_backtest(
                    candles_by_symbol=candles,
                    report_start_utc=report_start,
                    report_end_utc=report_end,
                    starting_cash=self.config.paper_starting_cash_usdc,
                    target_notional=paper_settings.target_notional_usdc,
                    slot_count=paper_settings.slot_count,
                    costs=costs,
                    execution_rules=rules,
                    strategy_parameters=strategy.parameters,
                    strategy_parameters_by_symbol=strategy.parameter_map(),
                    trade_policies_by_symbol=strategy.policy_map(),
                    strategy_semantics=strategy.semantics,
                    strategy_version=strategy.version,
                    slot_allocation=strategy.slot_allocation,
                    symbols=symbols,
                )
            else:
                if symbol is None:
                    raise RuntimeError("single backtest symbol disappeared")
                scenarios[costs.name] = run_single_backtest(
                    symbol=symbol,
                    candles=candles[symbol],
                    report_start_utc=report_start,
                    report_end_utc=report_end,
                    starting_cash=self.config.starting_usdc_per_symbol,
                    target_notional=self.config.target_notional_usdc,
                    costs=costs,
                    execution_rules=rules[symbol],
                    strategy_parameters=strategy.parameters_for(symbol),
                    trade_policy=strategy.policy_for(symbol),
                    strategy_semantics=strategy.semantics,
                    strategy_version=strategy.version,
                )

        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.config.run_output_root.parents[2],
            capture_output=True,
            check=False,
            text=True,
        )
        code_commit = completed.stdout.strip() if completed.returncode == 0 else "UNKNOWN"
        run_directory = write_report_bundle(
            scenarios=scenarios,
            output_root=(
                self.config.run_output_root.parents[1] / strategy.backtest_version / "runs"
            ),
            config_sha256=self.config.sha256,
            code_commit=code_commit,
            report_start_utc=report_start,
            report_end_utc=report_end,
            strategy=strategy,
            python_source_sha256=self.execution_source_sha256,
        )
        manifest_path = run_directory / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        data = manifest.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("backtest manifest data block missing")
        data.update(continuity_manifest_data(history))
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
