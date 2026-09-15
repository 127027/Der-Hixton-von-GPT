"""Same coin rules and account assumptions must not depend on test perspective."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from hixton.backtest.engine import run_single_backtest
from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.domain.versions import V6_COIN_STRATEGY as STRATEGY
from tests.golden_reference import deterministic_candles


@pytest.mark.parametrize("symbol", STRATEGY.symbols)
@pytest.mark.parametrize("costs", [BASELINE_COSTS, STRESS_COSTS], ids=["baseline", "stress"])
def test_same_coin_same_rules_and_budget_produce_same_fills(symbol, costs):
    raw = deterministic_candles(symbol, 1200, 0)
    active = [
        replace(c, high=max(c.open, c.close) + 0.01, low=min(c.open, c.close) - 0.01) for c in raw
    ]
    candles = {
        s: active
        if s == symbol
        else [replace(c, symbol=s, open=100, high=100, low=100, close=100) for c in raw]
        for s in STRATEGY.symbols
    }
    rules = ExecutionRules(Decimal(".01"), Decimal(".001"), Decimal(".001"), Decimal(5))
    shared = {
        "report_start_utc": raw[400].open_time_utc,
        "report_end_utc": raw[-1].open_time_utc + timedelta(hours=1),
        "starting_cash": Decimal(250),
        "target_notional": Decimal(80),
        "costs": costs,
        "strategy_semantics": STRATEGY.semantics,
        "strategy_version": STRATEGY.version,
    }
    single = run_single_backtest(
        symbol=symbol,
        candles=active,
        execution_rules=rules,
        strategy_parameters=STRATEGY.parameters_for(symbol),
        trade_policy=STRATEGY.policy_for(symbol),
        **shared,
    )
    portfolio = run_shared_portfolio_backtest(
        candles_by_symbol=candles,
        execution_rules=dict.fromkeys(STRATEGY.symbols, rules),
        strategy_parameters_by_symbol=STRATEGY.parameter_map(),
        trade_policies_by_symbol=STRATEGY.policy_map(),
        slot_count=1,
        # Isolate execution equivalence, not permission to disable production risk.
        apply_risk_limits=False,
        **shared,
    )
    assert len(single.trades) > 0  # No vacuous equality on a no-signal fixture.
    assert single.signals == portfolio.signals
    assert single.fills == portfolio.fills
    assert single.trades == portfolio.trades
    assert single.metrics.ending_equity == portfolio.metrics.ending_equity
