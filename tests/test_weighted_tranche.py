"""Offline weighted allocation, durable capacity and fail-closed tests."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import pytest

from hixton.backtest.models import ExecutionRules
from hixton.domain.tranche import allocate_tranches, size_tranche
from hixton.domain.versions import strategy_definition
from hixton.live.production import LiveIntent
from hixton.paper.engine import initialize_paper_at_latest, process_new_closed_points
from hixton.paper.models import PaperSettings
from hixton.paper.storage import PaperStore
from tests.test_live_production import controller, enable_now, universe


@pytest.mark.parametrize(
    "dd,n,free,half,expected",
    [
        ("9.99", 3, 20, False, [10, 10]),
        ("10", 3, 20, False, [10, 5, 5]),
        ("20", 2, 20, False, [10, 10]),
        ("20", 1, 20, False, [20]),
        ("10", 2, 10, True, [5, 5]),
        ("10", 2, 10, False, [10]),
        ("10", 2, 5, False, [5]),
    ],
)
def test_splits_only_valid_available_capacity(dd, n, free, half, expected):
    allocation, _ = allocate_tranches(
        list("ABCD")[:n],
        free_units=free,
        policy="ranked_repeat",
        drawdown_pct=D(dd),
        trigger_pct=D(10),
        existing_half=half,
    )
    assert list(allocation.values()) == expected
    assert sum(allocation.values()) <= free


def test_fractional_size_keeps_cash_and_existing_rounding_guards():
    assert size_tranche(
        equity=D("1000.01"), free_quote=D(1000), units=10, entry_fraction=D(1)
    ) == D(500)
    assert size_tranche(equity=D("1000.01"), free_quote=D(1000), units=5, entry_fraction=D(1)) == D(
        250
    )
    assert size_tranche(
        equity=D(1000), free_quote=D("12.345"), units=5, entry_fraction=D(".5")
    ) == D("12.34")
    with pytest.raises(ValueError):
        size_tranche(equity=D(1000), free_quote=D(1000), units=21, entry_fraction=D(1))


def history(at, *, entries=(), exit_symbol=None):
    strategy = strategy_definition("v8r")
    old = universe(at, enter=entries, exit_symbol=exit_symbol)
    for symbol, series in old.items():
        first = series[0]
        old[symbol] = (
            tuple(
                replace(
                    first,
                    candle=replace(
                        first.candle,
                        open_time_utc=first.candle.open_time_utc - timedelta(hours=i),
                        close_time_utc=first.candle.close_time_utc - timedelta(hours=i),
                    ),
                    flip_up=False,
                    flip_down=False,
                    vidya=float(70 - i),
                )
                for i in range(75, 0, -1)
            )
            + series
        )
    sample = old["BTCUSDC"]
    return {
        s: tuple(
            replace(
                p,
                symbol=s,
                strategy_version=strategy.version,
                candle=replace(p.candle, symbol=s, close=100.0),
                atr=0.5,
                flip_up=p.flip_up if s in entries else False,
                flip_down=p.flip_down if s == exit_symbol else False,
            )
            for p in old.get(s, sample)
        )
        for s in strategy.symbols
    }


def reference(at):
    return {
        "strategy_version": strategy_definition("v8r").version,
        "bar_close_utc": at.isoformat(),
        "drawdown_pct": "10",
    }


@pytest.mark.parametrize("auto", [False, True])
def test_live_three_positions_owned_exits_and_pending_capacity_restart(tmp_path, auto):
    at = datetime.now(UTC).replace(second=0, microsecond=0)
    strategy = strategy_definition("v8r")
    c, exchange, account, _ = controller(tmp_path)
    c.strategy = strategy
    c.autonomous_spot = lambda: auto
    c.allocation_reference = reference
    c.rules = lambda: {
        s: ExecutionRules(step_size=D(".000001"), min_notional=D(5)) for s in strategy.symbols
    }
    signals = history(at, entries=("BTCUSDC", "ETHUSDC", "BNBUSDC"))
    c.market_points = lambda: signals
    enable_now(c, account, history(at - timedelta(hours=1)))
    c.advance(signals, now=at, healthy=True)
    assert not exchange.submits
    # A new journal instance must preserve immutable capacity before submission.
    intent = c._pending()
    assert intent is not None
    for _ in range(12):
        c.advance(signals, now=at, healthy=True)
    buys = [i for i in exchange.submits if i.side == "BUY"]
    assert [i.allocation_units for i in buys] == [10, 5, 5]
    assert [i.quote_budget for i in buys] == [D(125), D("62.5"), D("62.5")]
    assert c.report()["used_allocation_units"] == 20
    assert len(c.report()["positions"]) == 3
    loaded, _ = type(c.journal)(c.database).load(buys[-1].intent_id)
    assert loaded == buys[-1]
    with pytest.raises(RuntimeError, match="identity"):
        c.journal.create(replace(loaded, allocation_units=10))
    # Exits remain available if the Paper allocation reference becomes unavailable.
    c.allocation_reference = lambda _: None
    for symbol in ("BTCUSDC", "ETHUSDC", "BNBUSDC"):
        at += timedelta(hours=1)
        exit_points = history(at, exit_symbol=symbol)
        c.market_points = lambda points=exit_points: points
        for _ in range(5):
            c.advance(exit_points, now=at, healthy=True)
    assert not c.report()["positions"]
    assert len(exchange.submits) == 6
    assert all(i.side == "SELL" for i in exchange.submits[3:])
    assert c.reconciler.check(account.snapshot(), now=datetime.now(UTC))["passed"] is True


def test_missing_same_bar_reference_waits_without_sending_or_consuming_signal(tmp_path):
    at = datetime.now(UTC).replace(second=0, microsecond=0)
    c, exchange, account, _ = controller(tmp_path)
    c.strategy = strategy_definition("v8r")
    enable_now(c, account, history(at - timedelta(hours=1)))
    signals = history(at, entries=("BTCUSDC",))
    c.advance(signals, now=at, healthy=True)
    assert c._pending() is None
    assert not exchange.submits
    c.allocation_reference = reference
    c.advance(signals, now=at, healthy=True)
    assert c._pending() is not None


def test_paper_three_capacity_weights_survive_restart_and_reference_is_immutable(tmp_path):
    strategy = strategy_definition("v8r")
    at = datetime(2026, 10, 13, 10, tzinfo=UTC)
    path = tmp_path / "paper.sqlite3"
    initialize_paper_at_latest(
        str(path),
        history(at - timedelta(hours=1)),
        strategy_key=strategy.key,
        strategy_version=strategy.version,
        starting_cash_usdc=D(250),
    )
    with PaperStore(path) as store:
        # Prior peak gives >10% drawdown without an intraday loss stop.
        store.save_account(replace(store.load_account(), high_water_equity_usdc=D(300)))
        store.save_settings(PaperSettings(max_capital_usdc=D(250), auto_budget_enabled=True))
    points = history(at, entries=("BTCUSDC", "ETHUSDC", "BNBUSDC"))
    execution = {
        s: [replace(p[-1].candle, open_time_utc=at, close_time_utc=at + timedelta(hours=1))]
        for s, p in points.items()
    }
    rules = {s: ExecutionRules(step_size=D(".000001"), min_notional=D(5)) for s in strategy.symbols}
    kwargs = {
        "strategy_key": strategy.key,
        "strategy_version": strategy.version,
        "trade_policies_by_symbol": strategy.policy_map(),
        "execution_candles_by_symbol": execution,
    }
    process_new_closed_points(str(path), points, rules, **kwargs)
    with PaperStore(path) as store:
        positions = store.load_positions()
        assert sorted(p.allocation_units for p in positions) == [5, 5, 10]
        assert sum(p.allocation_units for p in positions) == 20
        frozen = store.allocation_reference(strategy.version, at)
        assert frozen is not None and D(frozen["drawdown_pct"]) >= 10
    assert process_new_closed_points(str(path), points, rules, **kwargs) == ()
    with PaperStore(path) as store:
        assert store.load_positions() == positions
        assert store.allocation_reference(strategy.version, at) == frozen
        assert store.allocation_reference("old", at) is None


def test_invalid_fractional_intent_cannot_be_submitted():
    with pytest.raises(ValueError):
        LiveIntent(
            "x", "a", "BTCUSDC", "BUY", "v", D(100), 2, quote_budget=D(100), allocation_units=5
        )
