"""No credentials or network: durable diversification using a fake exchange."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

from hixton.backtest.models import ExecutionRules
from hixton.domain.versions import strategy_definition
from hixton.live.production import LivePortfolioController
from tests.test_live_production import controller, enable_now
from tests.test_weighted_tranche import history, reference


def setup(tmp_path, cash):
    c, exchange, account, _ = controller(tmp_path)
    c.strategy = strategy_definition("v8r")
    c.reinvest_profits = lambda: True
    c.autonomous_spot = lambda: True
    account.balances["USDC"] = (D(cash), D(0))
    c.rules = lambda: {
        s: ExecutionRules(step_size=D(".000001"), min_qty=D(".000001"), min_notional=D(5))
        for s in c.strategy.symbols
    }
    c.allocation_reference = lambda at: {**reference(at), "drawdown_pct": "0"}
    at = datetime.now(UTC).replace(second=0, microsecond=0)
    c.market_points = lambda: history(at)
    enable_now(c, account, history(at - timedelta(hours=1)))
    return c, exchange, account, at


def drain(c, points, at):
    for _ in range(20):
        c.advance(points, now=at, healthy=True)


def test_three_distinct_coins_no_fourth_buy(tmp_path):
    c, exchange, account, at = setup(tmp_path, "32000")
    points = history(at, entries=("BTCUSDC", "ETHUSDC", "BNBUSDC", "SOLUSDC"))
    c.market_points = lambda: points
    drain(c, points, at)
    buys = [i for i in exchange.submits if i.side == "BUY"]
    assert len(buys) == 3 and len({i.symbol for i in buys}) == 3
    assert all(i.quote_budget <= D(32000) / 3 and i.allocation_units == 6 for i in buys)
    assert c.report()["free_slots"] == 0 and c.report()["slot_count"] == 3
    assert c.report()["allocation_capacity_units"] == 18
    assert account.balances["USDC"][0] >= 0


def test_partial_trim_ambiguous_response_restart_then_regular_exit(tmp_path):
    c, exchange, account, at = setup(tmp_path, "31000")
    first = history(at, entries=("BTCUSDC",))
    c.market_points = lambda: first
    drain(c, first, at)
    assert D(c._positions()["BTCUSDC"]["quantity"]) == 310
    second = {
        s: tuple(
            replace(p, candle=replace(p.candle, high=max(p.candle.high, 110), close=110))
            for p in series
        )
        for s, series in history(at + timedelta(hours=1)).items()
    }
    c.market_points = lambda: second
    exchange.timeout = True
    c.advance(second, now=at + timedelta(hours=1), healthy=True)
    assert c._pending() is not None
    c.advance(second, now=at + timedelta(hours=1), healthy=True)
    restarted = LivePortfolioController(
        c.database,
        c.journal,
        c.executor,
        c.reconciler,
        c.snapshot,
        c.settings,
        c.rules,
        c.strategy,
        c.release_check,
        execution_source_sha256=c.execution_source_sha256,
        reinvest_profits=c.reinvest_profits,
        autonomous_spot=c.autonomous_spot,
        market_points=c.market_points,
        allocation_reference=c.allocation_reference,
    )
    drain(restarted, second, at + timedelta(hours=1))
    sells = [i for i in exchange.submits if i.side == "SELL"]
    assert len(sells) == 1 and sells[0].base_quantity == D("206.666666")
    position = restarted._positions()["BTCUSDC"]
    assert D(position["quantity"]) == D("103.333334")
    assert D(position["cost_basis_quote"]) == D("10333.3334")
    assert (
        restarted.report()["diversification_count"] == 3 and not restarted.journal.unresolved_ids()
    )
    exchange.timeout = False
    third = history(at + timedelta(hours=2), exit_symbol="BTCUSDC")
    drain(restarted, third, at + timedelta(hours=2))
    sells = [i for i in exchange.submits if i.side == "SELL"]
    assert len(sells) == 2 and sells[1].base_quantity == D("103.333334")
    assert not restarted._positions() and account.balances["BTC"][0] == 0


def test_unfilled_partial_remainder_stays_owned_and_blocks_entries(tmp_path):
    c, exchange, _account, at = setup(tmp_path, "31000")
    first = history(at, entries=("BTCUSDC",))
    c.market_points = lambda: first
    drain(c, first, at)
    second = {
        s: tuple(
            replace(p, candle=replace(p.candle, high=max(p.candle.high, 110), close=110))
            for p in series
        )
        for s, series in history(at + timedelta(hours=1)).items()
    }
    c.advance(second, now=at + timedelta(hours=1), healthy=True)
    pending = c._pending()
    assert pending is not None
    c._apply_sell(pending, {"gross_quantity": "100", "fees_by_asset": {}})
    assert D(c._positions()["BTCUSDC"]["quantity"]) == 210
    assert c.report()["state"] == "NEEDS_REVIEW" and c.report()["entries_enabled"] is False
    assert len(exchange.submits) == 1
