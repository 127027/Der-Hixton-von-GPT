"""Closed-decision capital is shared; next-open gaps never change that valuation."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import pytest

from hixton.backtest.models import CostModel, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.domain.models import Candle, IndicatorPoint, TrendState
from hixton.domain.spot_autonomy import (
    entry_capital_equity,
    marked_portfolio_equity,
    size_spot_entry,
)
from hixton.domain.versions import V8_DIV32_PAPER_STRATEGY, strategy_definition
from hixton.paper.engine import initialize_paper_at_latest, process_new_closed_points
from hixton.paper.models import PaperSettings
from hixton.paper.storage import PaperStore


def test_entry_capital_excludes_unspendable_dust_and_next_execution_gap():
    capital = entry_capital_equity(
        free_quote=D(500), base_quantities={"BTCUSDC": D(5)}, closed_prices={"BTCUSDC": D(50)}
    )
    assert capital == D(750)
    assert size_spot_entry(equity=capital, free_quote=D(500), slots=2, allocated_slots=1) == D(375)
    report_equity = marked_portfolio_equity(
        free_quote=D(500),
        base_quantities={"BTCUSDC": D(5)},
        dust_quantities={"XRPUSDC": D(10)},
        open_prices={"BTCUSDC": D(50), "XRPUSDC": D(10)},
    )
    assert report_equity == D(850)  # Dust remains on the ledger, not in the sizing input.
    with pytest.raises(ValueError, match="missing"):
        entry_capital_equity(free_quote=D(500), base_quantities={"BTCUSDC": D(5)}, closed_prices={})


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-1"])
def test_entry_capital_does_not_accept_invalid_balance(bad):
    with pytest.raises(ValueError):
        entry_capital_equity(free_quote=D(bad), base_quantities={}, closed_prices={})


def test_current_entry_contract_preserves_original_div32_payload():
    current = strategy_definition("v8r")
    old = V8_DIV32_PAPER_STRATEGY
    assert old.version.endswith("DIV32-PAPER-5")
    assert "entry_capital_basis" not in old.config_payload()
    assert current.entry_capital_basis == "FINALIZED_CLOSE_OWNED_POSITIONS_V1"
    assert current.autonomous_live_supported
    # Indicator, exit and ownership obligations are exactly the same.
    assert current.coin_profiles == old.coin_profiles
    assert current.diversification_stages == old.diversification_stages


def test_explicit_paper_upgrade_preserves_ledger_original_entries_and_latch(tmp_path):
    from hixton.paper.models import PaperPosition

    old, new = V8_DIV32_PAPER_STRATEGY, strategy_definition("v8r")
    at = datetime(2026, 10, 22, tzinfo=UTC)
    with PaperStore(tmp_path / "upgrade.sqlite3") as store:
        store.initialize(at=at, strategy_key=old.key, strategy_version=old.version)
        store.upsert_position(
            PaperPosition(
                "NEARUSDC",
                D(10),
                D(5),
                D(50),
                at,
                "original-entry",
                D(".05"),
                at,
                strategy_version=old.version,
                entry_atr=D(".1"),
            )
        )
        store._connection.execute("INSERT INTO paper_diversification VALUES(?,?)", (old.version, 3))
        store._connection.commit()
        before = (
            store.load_account(),
            store.load_positions(),
            store.load_events(),
            store.load_dust(),
            store.all_checkpoints(),
        )
        assert store.activate_compatible_entry_upgrade(old, new, at=at)
        assert before == (
            store.load_account(),
            store.load_positions(),
            store.load_events(),
            store.load_dust(),
            store.all_checkpoints(),
        )
        assert store.load_strategy_session().strategy_version == new.version
        assert store.diversification_count(new.version) == 3
        assert store.load_positions()[0].strategy_version == old.version
        assert not store.activate_compatible_entry_upgrade(old, new, at=at)
        bad = replace(
            new,
            coin_profiles=tuple(
                replace(p, trade_policy=replace(p.trade_policy, stop_atr=3))
                if p.symbol == "NEARUSDC"
                else p
                for p in new.coin_profiles
            ),
        )
        with pytest.raises(ValueError, match="identical"):
            store.activate_compatible_entry_upgrade(old, bad, at=at)


def test_native_and_paper_use_same_budget_with_held_coin_gap(tmp_path, monkeypatch):
    import hixton.backtest.portfolio as native_module
    import hixton.paper.engine as paper_module

    strategy = strategy_definition("v8r")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    bars, points = {}, {}
    for symbol in strategy.symbols:
        bars[symbol], points[symbol] = [], []
        for i in range(405):
            at = start + timedelta(hours=i)
            gap = symbol == "BTCUSDC" and i == 403
            candle = Candle(
                symbol=symbol,
                open_time_utc=at,
                close_time_utc=at + timedelta(hours=1, milliseconds=-1),
                open=50 if gap else 100,
                high=101,
                low=49 if gap else 99,
                close=100,
                volume=1000,
                quote_volume=100000,
                trade_count=100,
                closed=True,
                source="fake",
            )
            enter = (i == 401 and symbol in ("BTCUSDC", "ETHUSDC")) or (
                i == 402 and symbol == "BNBUSDC"
            )
            exit_ = i == 402 and symbol == "ETHUSDC"
            point = IndicatorPoint(
                candle=candle,
                strategy_version=strategy.version,
                symbol=symbol,
                index=i,
                vidya_raw=100 + i * 0.01,
                vidya=100 + i * 0.01,
                true_range=2,
                atr=0.1,
                abs_cmo=0.8,
                upper=101,
                lower=99,
                trend=TrendState.UP if enter else TrendState.DOWN,
                flip_up=enter,
                flip_down=exit_,
                tradable=True,
                breakout_strength=0.8,
                rank_strength=0.8,
            )
            bars[symbol].append(candle)
            points[symbol].append(point)

    class IndicatorReplay:
        def __init__(self, symbol, **kwargs):
            self.symbol = symbol

        def update(self, candle):
            return points[self.symbol][int((candle.open_time_utc - start).total_seconds() / 3600)]

    monkeypatch.setattr(native_module, "HixtonStrategy", IndicatorReplay)
    costs = CostModel("current", D(0), D(0), D(0))
    monkeypatch.setattr(paper_module, "BASELINE_COSTS", costs)
    rules = {
        s: ExecutionRules(step_size=D(".000001"), min_qty=D(".000001"), min_notional=D(5))
        for s in strategy.symbols
    }
    native = run_shared_portfolio_backtest(
        candles_by_symbol=bars,
        strategy=strategy,
        execution_rules=rules,
        starting_cash=D(1000),
        target_notional=D(500),
        slot_count=2,
        report_start_utc=bars["BTCUSDC"][401].open_time_utc,
        report_end_utc=bars["BTCUSDC"][-1].open_time_utc + timedelta(hours=1),
        costs=costs,
        reinvest_profits=True,
        autonomous_spot=True,
    )
    db = str(tmp_path / "paper.sqlite3")
    initialize_paper_at_latest(
        db,
        {s: tuple(p[:401]) for s, p in points.items()},
        at=bars["BTCUSDC"][401].open_time_utc,
        strategy_key=strategy.key,
        strategy_version=strategy.version,
        starting_cash_usdc=D(1000),
    )
    with PaperStore(db) as store:
        store.save_settings(
            PaperSettings(
                max_capital_usdc=D(1000),
                auto_budget_enabled=True,
                autonomous_performance_enabled=True,
            )
        )
    events = process_new_closed_points(
        db,
        {s: tuple(p) for s, p in points.items()},
        rules,
        execution_candles_by_symbol=bars,
        trade_policies_by_symbol=strategy.policy_map(),
        strategy_key=strategy.key,
        strategy_version=strategy.version,
    )
    native_buys = [
        (f.fill_time_utc, f.quote_value) for f in native.fills if f.action.value == "ENTER_LONG"
    ]
    paper_buys = [
        (e.occurred_at_utc, e.quote_amount_usdc)
        for e in events
        if e.action == "ENTER_LONG" and e.status.value == "FILLED"
    ]
    assert native_buys == paper_buys
    assert len(native_buys) == 3
    assert native_buys[-1][1] == D(500)  # Legacy OPEN marks would budget375.


def test_live_uses_same_closed_capital_after_fake_partial_portfolio_exit(tmp_path, monkeypatch):
    import hixton.live.production as production
    from tests.test_live_diversification import drain, setup
    from tests.test_weighted_tranche import history

    controller, exchange, _account, at = setup(tmp_path, "1000")
    clock = {"now": at}

    class FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock["now"].astimezone(tz or UTC)

    monkeypatch.setattr(production, "datetime", FakeDateTime)
    snapshot = controller.snapshot
    controller.snapshot = lambda: replace(snapshot(), observed_at=clock["now"])
    first = history(at, entries=("BTCUSDC", "ETHUSDC"))
    controller.market_points = lambda: first
    drain(controller, first, at)
    clock["now"] = at + timedelta(hours=1)
    second = history(at + timedelta(hours=1), entries=("BNBUSDC",), exit_symbol="ETHUSDC")
    controller.market_points = lambda: second
    drain(controller, second, at + timedelta(hours=1))
    buys = [i for i in exchange.submits if i.side == "BUY"]
    assert len(buys) == 3
    # This fake sells at105:525 free +500 held -> half-tranche512.50.
    assert buys[-1].symbol == "BNBUSDC" and buys[-1].quote_budget == D("512.50")


def test_live_risk_equity_counts_owned_dust_without_spending_it(tmp_path):
    from tests.test_live_production import NOW, controller, universe

    c, _exchange, account, _settings = controller(tmp_path)
    account.balances["USDC"] = (D(500), D(0))
    with c.journal._connect() as connection:
        connection.execute("INSERT INTO live_dust(symbol,quantity) VALUES(?,?)", ("BTCUSDC", ".05"))
    points = {s: series[-1] for s, series in universe(NOW).items()}
    assert c._equity(account.snapshot(), {"BTCUSDC": {"quantity": "1"}}, points) == D("606.05")
    # The fixture close is101:500cash+1BTC+0.05BTCdust=606.05.
    assert entry_capital_equity(
        free_quote=D(500), base_quantities={"BTCUSDC": D(1)}, closed_prices={"BTCUSDC": D(101)}
    ) == D(601)
