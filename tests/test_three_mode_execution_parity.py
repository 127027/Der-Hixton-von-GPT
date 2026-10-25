"""Independent three-mode fixtures and genuine old-contract fake trial lifecycle."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN
from decimal import Decimal as D
from uuid import uuid4

import pytest

from hixton.backtest.models import CostModel, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.domain.models import Candle, IndicatorPoint, TrendState
from hixton.domain.versions import V8_DIV32_PAPER_STRATEGY, strategy_definition
from hixton.live.exchange import BinanceSpotExchange
from hixton.live.frozen_trial import FrozenTrialPoints, continuation_strategy
from hixton.live.orders import ExchangeFill, ExchangeOrder, OrderJournal, TrialOrderExecutor
from hixton.live.production import (
    LiveAccountSnapshot,
    LiveBalanceReconciler,
    LiveOrderExecutor,
    LiveOrderJournal,
    LivePortfolioController,
)
from hixton.live.reconciliation import TrialReconciler
from hixton.live.runtime import TrialRuntime
from hixton.live.trial import SignalTrial
from hixton.paper.engine import initialize_paper_at_latest, process_new_closed_points
from hixton.paper.models import PaperSettings
from hixton.paper.storage import PaperStore


@pytest.mark.parametrize("gap_price", [50, 150])
@pytest.mark.parametrize("fee", [D(0), D(".001")])
def test_independent_three_modes_same_actual_fills_with_gap_dust_and_restart(
    tmp_path,
    monkeypatch,
    gap_price,
    fee,
    exit_price=105,
    expected_fill_count=4,
    decision_price=100,
    midnight=False,
    restart_during_sell=False,
    reinvest=True,
):
    import hixton.backtest.portfolio as native_module
    import hixton.live.production as live_module
    import hixton.paper.engine as paper_module

    strategy = strategy_definition("v8r")
    start = (
        (datetime(2026, 10, 23, tzinfo=UTC) - timedelta(hours=403))
        if midnight
        else datetime(2026, 1, 1, tzinfo=UTC)
    )
    bars, points = {}, {}
    for symbol in strategy.symbols:
        bars[symbol], points[symbol] = [], []
        for i in range(405):
            price = (
                gap_price
                if symbol == "BTCUSDC" and i == 403
                else exit_price
                if symbol == "ETHUSDC" and i == 403
                else 100
            )
            at = start + timedelta(hours=i)
            close = decision_price if symbol in ("BTCUSDC", "ETHUSDC") and i == 402 else 100
            c = Candle(
                symbol,
                at,
                at + timedelta(hours=1, milliseconds=-1),
                price,
                max(101, price + 1, close + 1),
                min(99, price - 1, close - 1),
                close,
                1000,
                100000,
                100,
                True,
                "A09_OFFLINE",
            )
            enter = (i == 401 and symbol in ("BTCUSDC", "ETHUSDC")) or (
                i == 402 and symbol == "BNBUSDC"
            )
            exit_ = i == 402 and symbol == "ETHUSDC"
            p = IndicatorPoint(
                symbol,
                strategy.version,
                i,
                c,
                0.8,
                100 + i * 0.01,
                100 + i * 0.01,
                2,
                0.1,
                101,
                99,
                TrendState.UP if enter else TrendState.DOWN,
                enter,
                exit_,
                0.8,
                0.8,
                True,
            )
            bars[symbol].append(c)
            points[symbol].append(p)

    class Replay:
        def __init__(self, symbol, **kwargs):
            self.symbol = symbol

        def update(self, c):
            return points[self.symbol][int((c.open_time_utc - start).total_seconds() / 3600)]

    monkeypatch.setattr(native_module, "HixtonStrategy", Replay)
    cost = CostModel("current", fee * 10000, D(0), D(0))
    monkeypatch.setattr(paper_module, "BASELINE_COSTS", cost)
    rules = {
        s: ExecutionRules(step_size=D(".01"), min_qty=D(".01"), min_notional=D(5))
        for s in strategy.symbols
    }
    native = run_shared_portfolio_backtest(
        candles_by_symbol=bars,
        strategy=strategy,
        execution_rules=rules,
        starting_cash=D(1000),
        target_notional=D(500),
        slot_count=2,
        report_start_utc=start + timedelta(hours=401),
        report_end_utc=start + timedelta(hours=405),
        costs=cost,
        reinvest_profits=reinvest,
        autonomous_spot=True,
    )
    paper_path = tmp_path / "paper.sqlite3"
    initialize_paper_at_latest(
        str(paper_path),
        {s: tuple(p[:401]) for s, p in points.items()},
        at=start + timedelta(hours=401),
        strategy_key=strategy.key,
        strategy_version=strategy.version,
        starting_cash_usdc=D(1000),
    )
    with PaperStore(paper_path) as store:
        store.save_settings(
            PaperSettings(
                max_capital_usdc=D(1000),
                auto_budget_enabled=reinvest,
                autonomous_performance_enabled=True,
            )
        )
    # Commit the first two fills, close/reopen the Paper store, then replay the
    # replacement-entry decision. The already processed fills cannot repeat.
    events = process_new_closed_points(
        str(paper_path),
        {s: tuple(p[:402]) for s, p in points.items()},
        rules,
        execution_candles_by_symbol=bars,
        trade_policies_by_symbol=strategy.policy_map(),
        strategy_key=strategy.key,
        strategy_version=strategy.version,
    )
    events += process_new_closed_points(
        str(paper_path),
        {s: tuple(p) for s, p in points.items()},
        rules,
        execution_candles_by_symbol=bars,
        trade_policies_by_symbol=strategy.policy_map(),
        strategy_key=strategy.key,
        strategy_version=strategy.version,
    )
    live_clock = {"now": start + timedelta(hours=401)}

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return live_clock["now"].astimezone(tz or UTC)

    monkeypatch.setattr(live_module, "datetime", Clock)
    account = {"USDC": (D(1000), D(0))}

    def snapshot():
        return LiveAccountSnapshot("A09", live_clock["now"], dict(account), ())

    class Exchange:
        def __init__(self):
            self.submits = []
            self.orders = {}

        def submit(self, intent):
            assert intent.client_order_id not in self.orders
            self.submits.append(intent)
            i = int((live_clock["now"] - start).total_seconds() / 3600)
            price = D(str(bars[intent.symbol][i].open))
            base = intent.symbol.removesuffix("USDC")
            quantity = (
                (intent.quote_budget / price / D(".01")).to_integral_value(rounding=ROUND_DOWN)
                * D(".01")
                if intent.side == "BUY"
                else intent.base_quantity
            )
            quote = quantity * price
            asset = base if intent.side == "BUY" else "USDC"
            commission = quantity * fee if intent.side == "BUY" else quote * fee
            free = account.get(base, (D(0), D(0)))[0]
            account[base] = (
                free + (quantity - commission if intent.side == "BUY" else -quantity),
                D(0),
            )
            account["USDC"] = (
                account["USDC"][0] + (-quote if intent.side == "BUY" else quote - commission),
                D(0),
            )
            n = str(len(self.submits))
            order = ExchangeOrder(
                intent.client_order_id,
                n,
                intent.symbol,
                intent.side,
                "FILLED",
                quantity,
                quote,
                (ExchangeFill(n, quantity, price, commission, asset, quote),),
            )
            self.orders[intent.client_order_id] = order
            return order

        def query(self, intent):
            return self.orders.get(intent.client_order_id)

    exchange = Exchange()
    journal = LiveOrderJournal(tmp_path / "live.sqlite3")
    reconciler = LiveBalanceReconciler(journal)
    holder = {}
    executor = LiveOrderExecutor(journal, exchange, lambda intent: holder["c"].pre_submit(intent))
    histories = {"current": {s: tuple(p[:401]) for s, p in points.items()}}

    def controller():
        return LivePortfolioController(
            journal.path,
            journal,
            executor,
            reconciler,
            snapshot,
            lambda: (D(1000), False),
            lambda: rules,
            strategy,
            lambda: True,
            execution_source_sha256="a09-fake-current",
            reinvest_profits=lambda: reinvest,
            autonomous_spot=lambda: True,
            market_points=lambda: histories["current"],
            allocation_reference=lambda at: {
                "strategy_version": strategy.version,
                "bar_close_utc": at.isoformat(),
                "drawdown_pct": "0",
            },
        )

    c = controller()
    holder["c"] = c
    c.enable("A09", histories["current"], snapshot(), now=live_clock["now"])
    for i in (401, 402, 403):
        histories["current"] = {s: tuple(p[: i + 1]) for s, p in points.items()}
        live_clock["now"] = start + timedelta(hours=i + 1)
        if i == 402 and restart_during_sell:
            c.advance(histories["current"], now=live_clock["now"], healthy=True)
            assert c._pending()["action"] == "EXIT_LONG"
            c = controller()
            holder["c"] = c
            c.advance(histories["current"], now=live_clock["now"], healthy=True)
            assert exchange.submits[-1].side == "SELL"
            c = controller()
            holder["c"] = c
        for _ in range(20):
            c.advance(histories["current"], now=live_clock["now"], healthy=True)
        if i == 401:
            c = controller()
            holder["c"] = c
    # Paper SELL events expose net quote; normalize all modes to cash movement.
    native_fills = [
        (
            f.action.value,
            f.quote_value
            if f.action.value == "ENTER_LONG"
            else f.quote_value - f.fee_quote_equivalent,
            f.base_quantity,
        )
        for f in native.fills
    ]
    paper_fills = [
        (e.action, e.quote_amount_usdc, e.base_quantity)
        for e in events
        if e.status.value == "FILLED"
    ]
    live_fills = []
    for intent in exchange.submits:
        order = exchange.orders[intent.client_order_id]
        net = (
            order.executed_quantity * (1 - fee) if intent.side == "BUY" else order.executed_quantity
        )
        live_fills.append(
            (
                "ENTER_LONG" if intent.side == "BUY" else "EXIT_LONG",
                order.cumulative_quote
                if intent.side == "BUY"
                else order.cumulative_quote - order.fills[0].commission,
                net,
            )
        )
    assert native_fills == paper_fills == live_fills
    assert len(live_fills) == expected_fill_count
    with PaperStore(paper_path, read_only=True) as store:
        assert store.load_account().cash_usdc == account["USDC"][0]
        dust = store.load_dust()
        owned = {p.symbol: p.quantity for p in store.load_positions()}
    assert native.equity_curve[-1].cash == account["USDC"][0]
    assert (
        c._equity(snapshot(), c._positions(), {s: p[-1] for s, p in histories["current"].items()})
        == native.equity_curve[-1].equity
    )
    for symbol in strategy.symbols:
        assert account.get(symbol.removesuffix("USDC"), (D(0), D(0)))[0] == owned.get(
            symbol, D(0)
        ) + dust.get(symbol, D(0))
    assert (sum(dust.values()) > 0) is (fee > 0)
    assert not journal.unresolved_ids()
    assert c.report()["state"] == "LIVE_ENABLED"


def test_risk_pause_uses_identical_post_exit_gap_inputs_in_three_modes(tmp_path, monkeypatch):
    # An actually realized 5% portfolio loss is known before a replacement BUY.
    test_independent_three_modes_same_actual_fills_with_gap_dust_and_restart(
        tmp_path, monkeypatch, 50, D(0), exit_price=90, expected_fill_count=3
    )


def test_manual_budget_after_loss_spends_remaining_cash_identically_in_three_modes(
    tmp_path, monkeypatch
):
    # Two 500-USDC entries; one exits at97 for485. The replacement must buy
    # with485 in all modes, rather than reserve500 and fail at Live submission.
    test_independent_three_modes_same_actual_fills_with_gap_dust_and_restart(
        tmp_path,
        monkeypatch,
        50,
        D(0),
        exit_price=97,
        reinvest=False,
        restart_during_sell=True,
    )


@pytest.mark.parametrize("exit_price,count", [(89.99, 3), (90, 3), (90.01, 4)])
@pytest.mark.parametrize("midnight", [False, True])
def test_post_exit_loss_threshold_and_utc_midnight_survive_two_live_restarts(
    tmp_path, monkeypatch, exit_price, count, midnight
):
    test_independent_three_modes_same_actual_fills_with_gap_dust_and_restart(
        tmp_path,
        monkeypatch,
        50,
        D(0),
        exit_price=exit_price,
        expected_fill_count=count,
        midnight=midnight,
        restart_during_sell=True,
    )


@pytest.mark.parametrize("midnight", [False, True])
def test_pre_exit_paused_signal_does_not_revive_after_sell_recovery_and_restart(
    tmp_path, monkeypatch, midnight
):
    # Finalized holdings900 trigger the entry pause; actual SELL at105 recovers
    # cash+remaining closed marks to975. An already rejected BUY stays rejected.
    test_independent_three_modes_same_actual_fills_with_gap_dust_and_restart(
        tmp_path,
        monkeypatch,
        50,
        D(0),
        exit_price=105,
        expected_fill_count=3,
        decision_price=90,
        midnight=midnight,
        restart_during_sell=True,
    )


def test_real_adapter_fake_near_old_div32_restart_exit_and_final_reconciliation(
    tmp_path, monkeypatch
):
    from tests.test_live_reconciliation_runtime import SpotFixture
    from tests.test_paper_engine import _point

    old, new = V8_DIV32_PAPER_STRATEGY, strategy_definition("v8r")
    clock = {"now": datetime(2026, 10, 22, 12, tzinfo=UTC)}

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock["now"].astimezone(tz or UTC)

    monkeypatch.setattr("hixton.live.orders.datetime", Clock)
    monkeypatch.setattr("hixton.live.trial.datetime", Clock)
    fixture = SpotFixture()
    fixture.fee_asset = "BNB"
    fixture.fee = D(".00001")
    fixture.balances["NEAR"] = D("2")  # immutable manual inventory must remain untouched
    journal = OrderJournal(tmp_path / "trial.sqlite3")
    exchange = BinanceSpotExchange(
        fixture, account_fingerprint="fixture", quote_asset="USDC", market_symbols=old.symbols
    )
    reconciler = TrialReconciler(journal)
    rules = {
        s: ExecutionRules(step_size=D(".001"), min_qty=D(".001"), min_notional=D(5))
        for s in old.symbols
    }
    executor = TrialOrderExecutor(
        journal,
        exchange,
        lambda intent: reconciler.check(
            fixture.snapshot(clock["now"]), now=clock["now"], ignore_intent_id=intent.intent_id
        )["passed"],
    )
    before = clock["now"] - timedelta(seconds=3)
    reconciler.capture(fixture.snapshot(before), now=before)
    trial = SignalTrial(
        journal,
        executor,
        old,
        lambda: True,
        lambda: rules,
        execution_source_sha256="genuine-old-div32",
        allocator_version=old.allocator_version,
    )
    trial.arm(str(uuid4()), "fixture", now=clock["now"] - timedelta(seconds=2), notional=D(50))

    def history(version, enter):
        return {
            s: tuple(
                replace(
                    _point(
                        s,
                        clock["now"] - timedelta(hours=74 - i),
                        flip_up=enter and s == "NEARUSDC" and i == 74,
                        flip_down=not enter and s == "NEARUSDC" and i == 74,
                        strength=1,
                    ),
                    strategy_version=version,
                    vidya=float(70 + i),
                    atr=0.5,
                    abs_cmo=0.9,
                )
                for i in range(75)
            )
            for s in old.symbols
        }

    runtime = TrialRuntime(
        trial, reconciler, lambda: fixture.snapshot(clock["now"]), clock=lambda: clock["now"]
    )
    assert (
        runtime.tick(
            history(old.version, True), now=clock["now"], healthy=True, entries_allowed=True
        )["state"]
        == "ENTRY_PENDING"
    )
    assert (
        runtime.tick(
            history(old.version, True), now=clock["now"], healthy=True, entries_allowed=True
        )["state"]
        == "OPEN"
    )
    frozen = continuation_strategy(journal.path, new)
    assert frozen.config_payload() == old.config_payload()
    restarted = SignalTrial(
        journal,
        executor,
        frozen,
        lambda: True,
        lambda: rules,
        execution_source_sha256="new-closecap-source",
        allocator_version=new.allocator_version,
    )
    runtime = TrialRuntime(
        restarted,
        reconciler,
        lambda: fixture.snapshot(clock["now"]),
        clock=lambda: clock["now"],
        points_transform=FrozenTrialPoints(new, frozen),
    )
    clock["now"] += timedelta(hours=1)
    signals = history(new.version, False)
    assert (
        runtime.tick(signals, now=clock["now"], healthy=True, entries_allowed=False)["state"]
        == "EXIT_PENDING"
    )
    fixture.timeout = True  # genuine fill, lost response: restart must query, not resend
    runtime.tick(signals, now=clock["now"], healthy=True, entries_allowed=False)
    restarted2 = SignalTrial(
        journal,
        executor,
        continuation_strategy(journal.path, new),
        lambda: True,
        lambda: rules,
        execution_source_sha256="new-closecap-source",
        allocator_version=new.allocator_version,
    )
    runtime2 = TrialRuntime(
        restarted2,
        reconciler,
        lambda: fixture.snapshot(clock["now"]),
        clock=lambda: clock["now"],
        points_transform=FrozenTrialPoints(new, frozen),
    )
    for _ in range(6):
        runtime2.tick(signals, now=clock["now"], healthy=True, entries_allowed=False)
    report = restarted2.report()
    assert report["state"] == "COMPLETED"
    assert fixture.balances["NEAR"] == D(2)
    posts = [p for method, path, p in fixture.calls if method == "POST"]
    assert [p["side"] for p in posts] == ["BUY", "SELL"]
    assert D(posts[1]["quantity"]) == D("0.5")
    assert report["strategy"] == old.config_payload()
    with journal._connect() as db:
        assert [r[0] for r in db.execute("SELECT state FROM trial_intents ORDER BY side")] == [
            "FILLED",
            "FILLED",
        ]
        row = db.execute(
            "SELECT execution_source_sha256,residual_quantity FROM signal_trial"
        ).fetchone()
        assert row[0] == "genuine-old-div32" and D(row[1]) == 0
    assert reconciler.check(fixture.snapshot(clock["now"]), now=clock["now"])["passed"] is True


def test_live_shared_risk_utc_rollover_and_restart(tmp_path):
    from datetime import timezone

    from tests.test_live_production import NOW, enable_now, universe
    from tests.test_live_production import controller as make_controller

    c, exchange, account, _ = make_controller(tmp_path)
    enable_now(c, account, universe(NOW - timedelta(hours=1)))
    with c.journal._connect() as db:
        db.execute("UPDATE live_control SET day_start_date='2026-10-22',day_start_equity='1000'")
    assert c._risk_paused(D(950), datetime(2026, 10, 22, 23, 59, tzinfo=UTC))
    # Wall-clock next local day still belongs to the same UTC risk day.
    assert c._risk_paused(D(949), datetime(2026, 10, 23, 1, tzinfo=timezone(timedelta(hours=2))))
    assert not c._risk_paused(D(951), datetime(2026, 10, 22, 23, 59, tzinfo=UTC))
    assert not c._risk_paused(D(900), datetime(2026, 10, 23, 0, tzinfo=UTC))
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
    )
    with c.journal._connect() as db:
        row = db.execute("SELECT day_start_date,day_start_equity FROM live_control").fetchone()
        assert tuple(row) == ("2026-10-23", "900")
    assert restarted._risk_paused(D(855), datetime(2026, 10, 23, 1, tzinfo=UTC))
    assert not restarted._risk_paused(D("855.01"), datetime(2026, 10, 23, 1, tzinfo=UTC))
    assert not exchange.submits


def test_independent_paper_entry_upgrade_atomic_rollback_and_identity(tmp_path):
    import sqlite3

    from hixton.paper.models import PaperPosition

    old, new = V8_DIV32_PAPER_STRATEGY, strategy_definition("v8r")
    path = tmp_path / "paper-upgrade.sqlite3"
    at = datetime(2026, 10, 22, 12, tzinfo=UTC)
    with PaperStore(path) as store:
        store.initialize(at=at, strategy_key=old.key, strategy_version=old.version)
        store.upsert_position(
            PaperPosition(
                "NEARUSDC",
                D(10),
                D(5),
                D(50),
                at,
                "genuine-old-entry",
                D(".05"),
                at,
                strategy_version=old.version,
                entry_atr=D(".1"),
            )
        )
        store._connection.execute("INSERT INTO paper_diversification VALUES(?,?)", (old.version, 3))
        store._connection.execute("INSERT INTO paper_dust VALUES('NEARUSDC','0.00001')")
        store._connection.commit()
    # Opening/reading a newer executable does not auto-upgrade an old session.
    with PaperStore(path) as store:
        assert store.load_strategy_session().strategy_version == old.version
        original = (
            store.load_account(),
            store.load_positions(),
            store.load_dust(),
            store.all_checkpoints(),
            store.load_events(),
        )
        store._connection.execute(
            "CREATE TRIGGER a09_abort_upgrade BEFORE INSERT ON paper_audit "
            "BEGIN SELECT RAISE(ABORT,'A09 injected durable audit failure'); END"
        )
        store._connection.commit()
        with pytest.raises(sqlite3.IntegrityError, match="A09 injected"):
            store.activate_compatible_entry_upgrade(old, new, at=at)
        assert store.load_strategy_session().strategy_version == old.version
        assert store.diversification_count(old.version) == 3
        assert not store._connection.execute(
            "SELECT 1 FROM paper_diversification WHERE strategy_version=?", (new.version,)
        ).fetchall()
        assert original == (
            store.load_account(),
            store.load_positions(),
            store.load_dust(),
            store.all_checkpoints(),
            store.load_events(),
        )
        store._connection.execute("DROP TRIGGER a09_abort_upgrade")
        store._connection.commit()
        assert store.activate_compatible_entry_upgrade(old, new, at=at)
        assert store.load_strategy_session().strategy_version == new.version
        assert store.diversification_count(new.version) == 3
        assert original == (
            store.load_account(),
            store.load_positions(),
            store.load_dust(),
            store.all_checkpoints(),
            store.load_events(),
        )
        assert not store.activate_compatible_entry_upgrade(old, new, at=at)
