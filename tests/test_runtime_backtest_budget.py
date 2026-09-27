"""The dashboard continuity path must use the same saved capital as Paper/Live."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from hixton.constants import SYMBOLS
from hixton.data.storage import CandleStore, StoredSymbolRules
from hixton.paper.models import PaperSettings
from hixton.paper.storage import PaperStore
from hixton.runtime.continuity_supervisor import RuntimeSupervisor
from tests.test_live_preparation import config_for


@pytest.mark.parametrize("budget", ["250", "500", "1000"])
def test_dashboard_portfolio_uses_saved_starting_budget(tmp_path, monkeypatch, budget):
    config = config_for(tmp_path)
    with CandleStore(config.database_path) as store:
        for symbol in SYMBOLS:
            store.put_symbol_rules(StoredSymbolRules(
                symbol, "TRADING", "USDC", True, ("MARKET",),
                Decimal("0.01"), Decimal("0.001"), Decimal("0.001"),
                Decimal("5"), datetime.now(UTC),
            ))
    supervisor = RuntimeSupervisor(config)
    with PaperStore(config.database_path) as store:
        store.initialize(
            strategy_key=supervisor.strategy.key,
            strategy_version=supervisor.strategy.version,
            starting_cash_usdc=config.paper_starting_cash_usdc,
        )
        store.require_strategy(supervisor.strategy.key, supervisor.strategy.version)
        store.save_settings(PaperSettings(max_capital_usdc=Decimal(budget)))
    calls = []

    class Captured(RuntimeError):
        pass

    def portfolio(**kwargs):
        calls.append(kwargs)
        raise Captured

    monkeypatch.setattr(
        "hixton.runtime.continuity_supervisor.load_continuity_history",
        lambda **kwargs: SimpleNamespace(candles_by_symbol={}),
    )
    monkeypatch.setattr(
        "hixton.runtime.continuity_supervisor.run_shared_portfolio_backtest", portfolio
    )
    with pytest.raises(Captured):
        supervisor._synchronous_backtest("portfolio", None, "v6")
    assert len(calls) == 1
    assert calls[0]["starting_cash"] == Decimal(budget)
    assert calls[0]["target_notional"] == Decimal(budget) / 2
    assert calls[0]["slot_count"] == 2
    assert calls[0]["slot_allocation"] == "ranked_repeat"
    with PaperStore(config.database_path) as store:
        assert store.load_settings().max_capital_usdc == Decimal(budget)
