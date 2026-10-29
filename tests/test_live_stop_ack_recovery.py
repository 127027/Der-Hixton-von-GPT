"""A confirmed purchase remains owned while its local application is pending."""

import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import pytest

from hixton.backtest.models import ExecutionRules
from hixton.domain.versions import FROZEN_STRATEGY_DEFINITIONS, strategy_definition
from hixton.live.production import (
    LiveBalanceReconciler,
    LiveOrderExecutor,
    LiveOrderJournal,
    LivePortfolioController,
)
from tests.test_live_production import Account, ApplyingExchange
from tests.test_paper_engine import _point

CONTRACT = next(
    definition
    for definition in (*FROZEN_STRATEGY_DEFINITIONS, strategy_definition("v8r"))
    if definition.version.endswith("DIV32-CLOSECAP-PAPER-6")
)


def history(at, *, entry=False):
    return {
        symbol: tuple(
            replace(
                _point(
                    symbol,
                    at - timedelta(hours=80 - i),
                    flip_up=entry and i == 80 and symbol == "BTCUSDC",
                    strength=1.0,
                ),
                strategy_version=CONTRACT.version,
                atr=1.0,
                vidya=70 + i * 0.1,
                abs_cmo=0.9,
                candle=replace(
                    _point(symbol, at).candle,
                    open_time_utc=at - timedelta(hours=81 - i),
                    close_time_utc=at - timedelta(hours=80 - i),
                    open=100.0,
                    close=100.0,
                    high=102.0,
                    low=98.0,
                    quote_volume=1000000.0,
                ),
            )
            for i in range(81)
        )
        for symbol in CONTRACT.symbols
    }


def live_case(tmp_path):
    now = datetime.now(UTC)
    account = Account()
    account.balances["USDC"] = (D(1000), D(0))
    exchange = ApplyingExchange(account)
    journal = LiveOrderJournal(tmp_path / "fake.sqlite3")
    holder = {}
    executor = LiveOrderExecutor(journal, exchange, lambda intent: holder["bot"].pre_submit(intent))
    points = history(now, entry=True)

    def construct():
        bot = LivePortfolioController(
            journal.path,
            journal,
            executor,
            LiveBalanceReconciler(journal),
            account.snapshot,
            lambda: (D(1000), False),
            lambda: {
                symbol: ExecutionRules(
                    step_size=D(".000001"), min_qty=D(".000001"), min_notional=D(5)
                )
                for symbol in CONTRACT.symbols
            },
            CONTRACT,
            lambda: True,
            execution_source_sha256="fake-frozen-six",
            market_points=lambda: points,
            allocation_reference=lambda at: {
                "strategy_version": CONTRACT.version,
                "bar_close_utc": at.isoformat(),
                "drawdown_pct": "0",
            },
        )
        holder["bot"] = bot
        return bot

    bot = construct()
    snapshot = account.snapshot()
    bot.enable(
        account.account, history(now - timedelta(hours=1)), snapshot, now=snapshot.observed_at
    )
    return bot, exchange, construct, points, now, journal, account


@pytest.mark.parametrize("transition", ["stop", "normalize", "source_change"])
def test_confirmed_unapplied_buy_stays_managed_after_stop_and_restart(
    tmp_path, monkeypatch, transition
):
    bot, exchange, construct, points, now, journal, account = live_case(tmp_path)
    bot.advance(points, now=now, healthy=True)
    # Interrupt only local application after the fake exchange and journal fill.
    with monkeypatch.context() as patch:
        patch.setattr(bot, "_apply_buy", lambda *_: None)
        bot.advance(points, now=now, healthy=True)
    assert len(exchange.submits) == 1
    assert journal.load(exchange.submits[0].intent_id)[1] == "FILLED"
    assert account.balances["BTC"][0] > 0
    assert not bot._positions() and bot._pending() is not None

    if transition == "stop":
        bot.disable_entries()
    elif transition == "normalize":
        with journal._connect() as connection:
            connection.execute("UPDATE live_control SET state='EXIT_ONLY',entries_enabled=0")
        bot._normalize_disabled_state()
    else:
        bot.source_is_current = lambda: False
        bot.advance(points, now=now, healthy=True)
    assert bot.report()["state"] == "EXIT_ONLY"
    restarted = construct()
    assert restarted.report()["state"] == "EXIT_ONLY"
    restarted.advance(points, now=now, healthy=True)
    assert len(restarted._positions()) == 1
    assert restarted._pending() is None
    restarted.advance(points, now=now, healthy=True)
    assert len(exchange.submits) == 1
    assert restarted.report()["state"] == "EXIT_ONLY"


@pytest.mark.parametrize("create_intent", [False, True])
def test_proven_unsent_buy_cancels_without_false_exposure(tmp_path, monkeypatch, create_intent):
    bot, exchange, construct, points, now, journal, _ = live_case(tmp_path)
    bot.advance(points, now=now, healthy=True)
    pending = bot._pending()
    assert pending is not None
    if create_intent:
        monkeypatch.setattr(bot.executor, "execute", lambda *_args, **_kwargs: "CREATED")
        bot.advance(points, now=now, healthy=True)
        assert journal.load(pending["intent_id"])[1] == "CREATED"
    bot.disable_entries()
    assert bot.report()["state"] == "LIVE_DISABLED"
    assert bot._pending() is None and not exchange.submits
    if create_intent:
        assert journal.load(pending["intent_id"])[1] == "CANCELED"
    assert construct().report()["state"] == "LIVE_DISABLED"


@pytest.mark.parametrize("create_intent", [False, True])
def test_reconciling_evidence_is_not_cancelled_as_unsent(tmp_path, monkeypatch, create_intent):
    bot, exchange, construct, points, now, journal, _ = live_case(tmp_path)
    bot.advance(points, now=now, healthy=True)
    if create_intent:
        monkeypatch.setattr(bot.executor, "execute", lambda *_args, **_kwargs: "CREATED")
        bot.advance(points, now=now, healthy=True)
    with journal._connect() as connection:
        connection.execute("UPDATE live_events SET status='RECONCILING'")
    bot.disable_entries()
    assert bot.report()["state"] == "EXIT_ONLY"
    assert bot._pending()["status"] == "RECONCILING"
    assert construct().report()["state"] == "EXIT_ONLY"
    assert not exchange.submits


def test_cancel_and_control_stop_roll_back_together_on_storage_failure(tmp_path):
    bot, exchange, _, points, now, journal, _ = live_case(tmp_path)
    bot.advance(points, now=now, healthy=True)
    with journal._connect() as connection:
        connection.execute(
            "CREATE TRIGGER reject_stop BEFORE UPDATE ON live_control "
            "WHEN NEW.entries_enabled=0 BEGIN SELECT RAISE(ABORT,'fake stop failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="fake stop failure"):
        bot.disable_entries()
    assert bot._pending()["status"] == "ORDER_PENDING"
    assert bot.report()["state"] == "LIVE_ENABLED"
    assert not exchange.submits
