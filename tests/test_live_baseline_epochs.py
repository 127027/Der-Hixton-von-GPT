"""Offline regression expectations for explicit, settled Live baseline epochs."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta, tzinfo
from decimal import Decimal
from pathlib import Path
from threading import Event

import pytest

import hixton.live.orders as order_module
import hixton.live.production as production_module
import tests.test_live_production as account_helper
import tests.test_live_stop_ack_recovery as source6_helper
from hixton.domain.models import IndicatorPoint
from hixton.live.orders import ExchangeFill, ExchangeOrder
from hixton.live.production import LiveBalanceReconciler, LiveIntent, LiveOrderJournal

D = Decimal
AT = datetime(2026, 11, 1, 12, tzinfo=UTC)


@dataclass
class Clock:
    now: datetime = AT


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    result = Clock()

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:
            return result.now.astimezone(tz or UTC)

    for module in (order_module, production_module, account_helper, source6_helper):
        monkeypatch.setattr(module, "datetime", FrozenDateTime)
    return result


def entry_points(at: datetime) -> dict[str, tuple[IndicatorPoint, ...]]:
    return source6_helper.history(at, entry=True)


def exit_points(at: datetime) -> dict[str, tuple[IndicatorPoint, ...]]:
    result = source6_helper.history(at)
    result["BTCUSDC"] = (
        *result["BTCUSDC"][:-1],
        replace(result["BTCUSDC"][-1], flip_up=False, flip_down=True),
    )
    return result


def drain(
    bot: production_module.LivePortfolioController,
    points: dict[str, tuple[IndicatorPoint, ...]],
    at: datetime,
) -> None:
    bot.market_points = lambda: points
    for _ in range(10):
        bot.advance(points, now=at, healthy=True)


def baseline_state(path: Path) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    with sqlite3.connect(path) as db:
        baseline = db.execute("SELECT * FROM live_account_baseline").fetchall()
        included = db.execute(
            "SELECT account,symbol,trade_id FROM live_baseline_included_fills "
            "ORDER BY account,symbol,trade_id"
        ).fetchall()
    return baseline, included


def historical_fills(path: Path) -> list[tuple[object, ...]]:
    with sqlite3.connect(path) as db:
        return db.execute(
            "SELECT account,symbol,trade_id,intent_id,quantity,price,commission,"
            "commission_asset,quote_quantity FROM live_fills ORDER BY account,symbol,trade_id"
        ).fetchall()


def completed_case(tmp_path: Path, clock: Clock):
    bot, exchange, construct, points, at, journal, account = source6_helper.live_case(tmp_path)
    drain(bot, points, at)
    clock.now = at + timedelta(hours=1)
    points = exit_points(clock.now)
    drain(bot, points, clock.now)
    assert len(exchange.submits) == 2 and not bot._positions()
    assert bot.reconciler.check(account.snapshot(), now=clock.now)["passed"] is True
    bot.disable_entries()
    assert bot.report()["state"] == "LIVE_DISABLED"
    return bot, exchange, construct, points, journal, account


def test_completed_source6_cycle_can_reenable_without_double_counting(
    tmp_path: Path, clock: Clock
) -> None:
    bot, _exchange, _construct, points, journal, account = completed_case(tmp_path, clock)
    fills = historical_fills(journal.path)
    bot.enable(account.account, points, account.snapshot(), now=clock.now)
    assert bot.report()["state"] == "LIVE_ENABLED"
    assert bot.reconciler.check(account.snapshot(), now=clock.now)["passed"] is True
    assert historical_fills(journal.path) == fills


def test_six_cycles_restarts_withdrawal_and_new_epoch_preserve_history(
    tmp_path: Path, clock: Clock
) -> None:
    bot, exchange, construct, points, _at, journal, account = source6_helper.live_case(tmp_path)
    initial = account.balances["USDC"][0]
    for cycle in range(6):
        if cycle:
            clock.now += timedelta(hours=1)
            points = entry_points(clock.now)
        drain(bot, points, clock.now)
        clock.now += timedelta(hours=1)
        points = exit_points(clock.now)
        drain(bot, points, clock.now)
        assert not bot._positions() and bot._pending() is None
        assert bot.reconciler.check(account.snapshot(), now=clock.now)["passed"] is True
        bot.disable_entries()
        bot = construct()
        bot.market_points = lambda points=points: points
        bot.enable(account.account, points, account.snapshot(), now=clock.now)
        assert bot.reconciler.check(account.snapshot(), now=clock.now)["passed"] is True
        assert len(historical_fills(journal.path)) == (cycle + 1) * 2
    assert len(exchange.submits) == 12
    assert account.balances["USDC"][0] - initial > 100
    bot.disable_entries()
    fills = historical_fills(journal.path)
    # Explicitly permitted flat deposit/withdrawal refresh must not require a
    # negative virtual original balance after more profit than the new wallet.
    account.balances["USDC"] = (D(100), D(0))
    bot.settings = lambda: (D(100), False)
    bot.enable(account.account, points, account.snapshot(), now=clock.now)
    assert bot.reconciler.check(account.snapshot(), now=clock.now)["passed"] is True
    assert historical_fills(journal.path) == fills
    assert bot.report()["state"] == "LIVE_ENABLED"


@pytest.mark.parametrize("guard", ["active", "owned", "pending", "unknown", "partial"])
def test_refresh_refuses_active_or_unsettled_state_without_mutating_epoch(
    tmp_path: Path, clock: Clock, guard: str
) -> None:
    bot, _exchange, _construct, _points, journal, account = completed_case(tmp_path, clock)
    if guard == "active":
        with journal._connect() as db:
            db.execute("UPDATE live_control SET state='LIVE_ENABLED',entries_enabled=1")
    elif guard == "owned":
        with journal._connect() as db:
            db.execute(
                "INSERT INTO live_positions VALUES(?,?,?,?,?,?,?,?,?,?)",
                ("BTCUSDC", "1", "100", "100", clock.now.isoformat(), "owned", ".5", "100", 1, 10),
            )
    elif guard == "pending":
        with journal._connect() as db:
            db.execute(
                "INSERT INTO live_events VALUES(?,?,?,?,?,?,?,?)",
                (
                    "unapplied",
                    clock.now.isoformat(),
                    "BTCUSDC",
                    "ENTER_LONG",
                    "RECONCILING",
                    None,
                    "unapplied-filled",
                    "{}",
                ),
            )
    else:
        intent = LiveIntent(
            "unresolved",
            account.account,
            "BTCUSDC",
            "BUY",
            bot.strategy.version,
            D(100),
            1,
            quote_budget=D(50),
        )
        journal.create(intent)
        journal.claim_submit(intent.intent_id)
        if guard == "partial":
            journal.record(
                intent,
                ExchangeOrder(
                    intent.client_order_id,
                    "partial",
                    "BTCUSDC",
                    "BUY",
                    "PARTIALLY_FILLED",
                    D(".25"),
                    D(25),
                    (ExchangeFill("partial", D(".25"), D(100), D(0), "USDC"),),
                ),
            )
        else:
            journal.unknown(intent.intent_id)
    before = baseline_state(journal.path)
    with pytest.raises(RuntimeError):
        bot.reconciler.capture(account.snapshot(), now=clock.now, allow_refresh=True)
    assert baseline_state(journal.path) == before


@pytest.mark.parametrize("identity", ["snapshot", "history", "fill", "fill_symbol", "orphan"])
def test_refresh_rejects_changed_account_or_foreign_fill_without_hiding_it(
    tmp_path: Path, clock: Clock, identity: str
) -> None:
    bot, _exchange, _construct, _points, journal, account = completed_case(tmp_path, clock)
    snapshot = account.snapshot()
    if identity == "snapshot":
        snapshot = replace(snapshot, account="foreign-account")
    elif identity == "orphan":
        with sqlite3.connect(journal.path) as db:
            db.execute(
                "DELETE FROM live_intents WHERE intent_id="
                "(SELECT intent_id FROM live_fills LIMIT 1)"
            )
    elif identity == "fill_symbol":
        with journal._connect() as db:
            db.execute("UPDATE live_fills SET symbol='ETHUSDC'")
    else:
        table = "live_intents" if identity == "history" else "live_fills"
        with journal._connect() as db:
            db.execute(f"UPDATE {table} SET account='foreign-account'")
    before = baseline_state(journal.path)
    with pytest.raises(RuntimeError):
        bot.reconciler.capture(snapshot, now=clock.now, allow_refresh=True)
    assert baseline_state(journal.path) == before


def test_fresh_but_pre_history_snapshot_cannot_absorb_newer_fills(
    tmp_path: Path, clock: Clock
) -> None:
    bot, _exchange, _construct, _points, journal, account = completed_case(tmp_path, clock)
    snapshot = replace(account.snapshot(), observed_at=clock.now - timedelta(seconds=1))
    snapshot.validate(clock.now)  # Fresh enough for normal API use, but predates the SELL record.
    before = baseline_state(journal.path)
    with pytest.raises(RuntimeError, match="predates"):
        bot.reconciler.capture(snapshot, now=clock.now, allow_refresh=True)
    assert baseline_state(journal.path) == before


def test_legacy_baseline_replays_history_until_explicit_refresh(
    tmp_path: Path, clock: Clock
) -> None:
    _bot, _exchange, _construct, _points, journal, account = completed_case(tmp_path, clock)
    with journal._connect() as db:
        db.execute("DROP TABLE live_baseline_included_fills")
    again = LiveBalanceReconciler(LiveOrderJournal(journal.path))
    assert baseline_state(journal.path)[1] == []
    assert again.check(account.snapshot(), now=clock.now)["passed"] is True
    again.capture(account.snapshot(), now=clock.now, allow_refresh=True)
    assert len(baseline_state(journal.path)[1]) == len(historical_fills(journal.path))
    assert again.check(account.snapshot(), now=clock.now)["passed"] is True


def test_refresh_keeps_managed_dust_and_foreign_fee_history(
    tmp_path: Path, clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    bot, exchange, construct, points, journal, account = completed_case(tmp_path, clock)
    account.balances["BNB"] = (D(1), D(0))
    bot.reconciler.capture(account.snapshot(), now=clock.now, allow_refresh=True)
    bot.enable(account.account, points, account.snapshot(), now=clock.now)
    original_submit = exchange.submit

    def with_fee(intent: LiveIntent) -> ExchangeOrder:
        order = original_submit(intent)
        asset = "BTC" if intent.side == "BUY" else "BNB"
        amount = D(".0000001") if intent.side == "BUY" else D(".000001")
        altered = replace(
            order, fills=(replace(order.fills[0], commission_asset=asset, commission=amount),)
        )
        free, locked = account.balances[asset]
        account.balances[asset] = (free - amount, locked)
        exchange.orders[intent.client_order_id] = altered
        return altered

    monkeypatch.setattr(exchange, "submit", with_fee)
    clock.now += timedelta(hours=1)
    drain(bot, entry_points(clock.now), clock.now)
    clock.now += timedelta(hours=1)
    points = exit_points(clock.now)
    drain(bot, points, clock.now)
    assert not bot._positions() and bot._pending() is None
    assert bot.reconciler.check(account.snapshot(), now=clock.now)["passed"] is True
    with journal._connect() as db:
        dust_before = db.execute("SELECT * FROM live_dust ORDER BY symbol").fetchall()
    assert dust_before and D(dust_before[0]["quantity"]) > 0
    assert account.balances["BNB"][0] < 1
    fills = historical_fills(journal.path)
    bot.disable_entries()
    bot.reconciler.capture(account.snapshot(), now=clock.now, allow_refresh=True)
    bot = construct()
    bot.market_points = lambda: points
    bot.enable(account.account, points, account.snapshot(), now=clock.now)
    with journal._connect() as db:
        dust_after = db.execute("SELECT * FROM live_dust ORDER BY symbol").fetchall()
    assert [tuple(r) for r in dust_after] == [tuple(r) for r in dust_before]
    assert historical_fills(journal.path) == fills
    assert bot.reconciler.check(account.snapshot(), now=clock.now)["passed"] is True


def test_orphan_included_fill_set_does_not_become_fresh_baseline(
    tmp_path: Path, clock: Clock
) -> None:
    journal = LiveOrderJournal(tmp_path / "orphan.sqlite3")
    reconciler = LiveBalanceReconciler(journal)
    with journal._connect() as db:
        db.execute(
            "INSERT INTO live_baseline_included_fills VALUES('fake-account','BTCUSDC','orphan')"
        )
    snapshot = production_module.LiveAccountSnapshot(
        "fake-account", clock.now, {"USDC": (D(1000), D(0))}, ()
    )
    before = baseline_state(journal.path)
    with pytest.raises(RuntimeError, match="no baseline"):
        reconciler.capture(snapshot, now=clock.now)
    assert baseline_state(journal.path) == before


def test_stable_fill_identity_survives_rowid_reorganization_and_vacuum(
    tmp_path: Path, clock: Clock
) -> None:
    bot, _exchange, _construct, _points, journal, account = completed_case(tmp_path, clock)
    bot.reconciler.capture(account.snapshot(), now=clock.now, allow_refresh=True)
    before = baseline_state(journal.path), historical_fills(journal.path)
    with sqlite3.connect(journal.path) as db:
        db.execute("UPDATE live_fills SET rowid=rowid+10000")
        db.commit()
        db.execute("VACUUM")
    again = LiveBalanceReconciler(LiveOrderJournal(journal.path))
    assert (baseline_state(journal.path), historical_fills(journal.path)) == before
    assert again.check(account.snapshot(), now=clock.now)["passed"] is True


def test_included_fill_insert_failure_rolls_back_whole_epoch(tmp_path: Path, clock: Clock) -> None:
    bot, _exchange, _construct, _points, journal, account = completed_case(tmp_path, clock)
    before = baseline_state(journal.path)
    with journal._connect() as db:
        db.execute(
            "CREATE TRIGGER deny_included BEFORE INSERT ON live_baseline_included_fills "
            "BEGIN SELECT RAISE(ABORT,'offline epoch interruption'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="epoch interruption"):
        bot.reconciler.capture(account.snapshot(), now=clock.now, allow_refresh=True)
    assert baseline_state(journal.path) == before
    assert bot.reconciler.check(account.snapshot(), now=clock.now)["passed"] is True


def test_concurrent_refresh_does_not_mix_baseline_and_included_fill_epochs(
    tmp_path: Path, clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    bot, _exchange, _construct, _points, journal, account = completed_case(tmp_path, clock)
    original_snapshot = account.snapshot()
    new_balances = dict(original_snapshot.balances)
    new_balances["USDC"] = (new_balances["USDC"][0] + 100, D(0))
    later_snapshot = replace(original_snapshot, balances=new_balances)
    with sqlite3.connect(journal.path) as db:
        assert db.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    reader_has_baseline, writer_committed = Event(), Event()
    original_connect = journal._connect

    @contextmanager
    def interposed_connect() -> Iterator[sqlite3.Connection]:
        with original_connect() as db:

            def factory(cursor: sqlite3.Cursor, values: tuple[object, ...]) -> sqlite3.Row:
                result = sqlite3.Row(cursor, values)
                names = {str(v[0]) for v in cursor.description}
                if "balances_json" in names:
                    reader_has_baseline.set()
                    assert writer_committed.wait(10), "Concurrent epoch writer did not finish"
                return result

            db.row_factory = factory
            yield db

    def refresh() -> None:
        assert reader_has_baseline.wait(10), "Reader did not establish its baseline snapshot"
        other = LiveBalanceReconciler(LiveOrderJournal(journal.path))
        other.capture(later_snapshot, now=clock.now, allow_refresh=True)
        writer_committed.set()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(refresh)
        with monkeypatch.context() as patch:
            patch.setattr(journal, "_connect", interposed_connect)
            assert bot.reconciler.check(original_snapshot, now=clock.now)["passed"] is True
        future.result(timeout=10)
    again = LiveBalanceReconciler(LiveOrderJournal(journal.path))
    assert again.check(later_snapshot, now=clock.now)["passed"] is True
    assert again.check(original_snapshot, now=clock.now)["passed"] is False
    encoded = baseline_state(journal.path)[0][0][-1]
    assert D(json.loads(str(encoded))["USDC"]) == later_snapshot.balances["USDC"][0]
