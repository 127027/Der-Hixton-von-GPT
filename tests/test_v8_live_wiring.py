"""V8 Live integration uses only fictitious credentials and exchanges."""

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from hixton.domain.markets import split_market
from hixton.domain.versions import V8_SATELLITE_STRATEGY as STRATEGY
from hixton.live.binance import assess_account
from hixton.live.credentials import BinanceCredentials
from hixton.live.orders import OrderJournal, TrialOrderExecutor
from hixton.live.trial import SignalTrial
from hixton.runtime.supervisor import RuntimeSupervisor
from hixton.ui.api import create_app
from tests.test_live_preparation import KEY, SECRET, MemoryVault, account_fixture
from tests.test_live_trial import NOW, Exchange
from tests.test_paper_engine import _point
from tests.test_v8_product_backtest import history_fixture as history_fixture


def test_v8_ui_binds_full_preflight_filter_and_exchange_universe(history_fixture):
    config, _candles, _rules, _start, _end, _requests = history_fixture
    supervisor = RuntimeSupervisor(config)
    app = create_app(config, supervisor, live_vault=MemoryVault())
    service = app.state.live_preparation
    credentials = BinanceCredentials(KEY, SECRET)
    client = service.client_factory(credentials)
    assert client.symbols == STRATEGY.symbols
    assert set(service.trial.rules_provider()) == set(STRATEGY.symbols)
    assert set(service.live.rules()) == set(STRATEGY.symbols)
    service.credentials.save(credentials)
    assert service._bound_exchange().symbols == STRATEGY.symbols
    assert all(split_market(s) == (s.removesuffix("USDC"), "USDC") for s in STRATEGY.symbols)
    assert service.live.report()["state"] == "LIVE_DISABLED"


def test_v8_preflight_rejects_missing_satellite_filters():
    permissions, account, orders, markets = account_fixture()
    prototype = markets["symbols"][0]
    for symbol in STRATEGY.satellite_symbols:
        markets["symbols"].append(
            {
                **deepcopy(prototype),
                "symbol": symbol,
                "baseAsset": symbol.removesuffix("USDC"),
            }
        )
    args = (permissions, account, orders, markets, Decimal("50"))
    result = assess_account(*args, market_symbols=STRATEGY.symbols)
    assert result["account_checks_passed"] is True
    assert result["checked_symbols"] == list(STRATEGY.symbols)
    markets["symbols"] = [m for m in markets["symbols"] if m["symbol"] != "NEARUSDC"]
    assert assess_account(*args, market_symbols=STRATEGY.symbols)["account_checks_passed"] is False


@pytest.mark.parametrize("core_signal", [False, True])
def test_v8_trial_obeys_shared_activation_priority_and_near_horizon(tmp_path, core_signal):
    journal = OrderJournal(tmp_path / "fake-orders.sqlite3")
    exchange = Exchange()
    controller = SignalTrial(
        journal,
        TrialOrderExecutor(journal, exchange, lambda _: True),
        STRATEGY,
        lambda: True,
    )
    points = {}
    for symbol in STRATEGY.symbols:
        point = _point(
            symbol,
            NOW,
            flip_up=symbol in {"SUIUSDC", "NEARUSDC", "AAVEUSDC"}
            or (core_signal and symbol == "BTCUSDC"),
            strength=20.0 if symbol == "SUIUSDC" else 1.0,
        )
        points[symbol] = (replace(point, strategy_version=STRATEGY.version),)
    controller.arm(
        str(uuid4()), "fake-account", now=NOW - timedelta(seconds=5), notional=Decimal("50")
    )
    assert controller.advance(points, now=NOW, healthy=True)["state"] == "ENTRY_PENDING"
    assert controller.report()["symbol"] == ("BTCUSDC" if core_signal else "NEARUSDC")
    assert controller.advance(points, now=NOW, healthy=True)["state"] == "OPEN"
    if not core_signal:
        later = NOW + timedelta(hours=49)
        points["NEARUSDC"] = (
            replace(
                _point("NEARUSDC", later),
                strategy_version=STRATEGY.version,
            ),
        )
        result = controller.advance(points, now=later, healthy=True)
        assert result["state"] == "EXIT_PENDING"
        assert result["exit_signal"]["reason"] == "SATELLITE_MAX_HOLD"


@pytest.mark.parametrize("pause", [False, True])
@pytest.mark.parametrize("fillers_enabled", [False, True])
def test_v8_live_all_fillers_yield_and_restore_both_core_tranches(
    tmp_path, pause, fillers_enabled
):
    from hixton.backtest.models import ExecutionRules
    from hixton.live.production import (
        LiveBalanceReconciler,
        LiveOrderExecutor,
        LiveOrderJournal,
        LivePortfolioController,
    )
    from tests.test_live_production import Account, ApplyingExchange

    account = Account()
    exchange = ApplyingExchange(account)
    journal = LiveOrderJournal(tmp_path / "fake-live.sqlite3")
    holder = {}
    settings = [Decimal("250"), False]
    executor = LiveOrderExecutor(
        journal, exchange, lambda intent: holder["controller"].pre_submit(intent)
    )
    rules = {
        s: ExecutionRules(
            step_size=Decimal("0.000001"), min_qty=Decimal("0.000001"), min_notional=Decimal("5")
        )
        for s in STRATEGY.symbols
    }
    controller = LivePortfolioController(
        journal.path,
        journal,
        executor,
        LiveBalanceReconciler(journal),
        account.snapshot,
        lambda: (settings[0], settings[1]),
        lambda: rules,
        STRATEGY,
        lambda: True,
        execution_source_sha256="offline-v8-test",
        gap_fillers_enabled=lambda: fillers_enabled,
    )
    holder["controller"] = controller

    def universe(at, enter=()):
        return {
            s: tuple(
                replace(
                    _point(
                        s,
                        at - timedelta(hours=24 - i),
                        flip_up=i == 24 and s in enter,
                        strength=1.0,
                    ),
                    strategy_version=STRATEGY.version,
                    vidya=90.0 + i / 4,
                )
                for i in range(25)
            )
            for s in STRATEGY.symbols
        }

    snapshot = account.snapshot()
    at_base = snapshot.observed_at
    controller.enable("fake-account", universe(at_base - timedelta(hours=1)), snapshot, now=at_base)
    for at, enter in [(at_base, ("BCHUSDC", "NEARUSDC"))]:
        points = universe(at, enter)
        for _ in range(8):
            controller.advance(points, now=at, healthy=True)
    assert [(x.symbol, x.side, x.slot_count) for x in exchange.submits] == ([
        ("NEARUSDC", "BUY", 1),
        ("BCHUSDC", "BUY", 1),
    ] if fillers_enabled else [])
    at = at_base + timedelta(hours=2)
    settings[1] = pause
    for _ in range(10):
        controller.advance(universe(at, ("BTCUSDC",)), now=at, healthy=True)
    if pause:
        assert len(exchange.submits) == (2 if fillers_enabled else 0)
        assert controller.report()["used_slots"] == (2 if fillers_enabled else 0)
        return
    assert [(x.symbol, x.side, x.slot_count) for x in exchange.submits][-3:] == ([
        ("BCHUSDC", "SELL", 1),
        ("NEARUSDC", "SELL", 1),
        ("BTCUSDC", "BUY", 2),
    ] if fillers_enabled else [("BTCUSDC", "BUY", 2)])
    assert controller.report()["used_slots"] == 2
    assert exchange.submits[-1].quote_budget == Decimal("250")
    at += timedelta(hours=1)
    for _ in range(8):
        controller.advance(universe(at, ("NEARUSDC",)), now=at, healthy=True)
    assert len(exchange.submits) == (5 if fillers_enabled else 1)
    assert not any(x.symbol == "BTCUSDC" and x.side == "SELL" for x in exchange.submits)
