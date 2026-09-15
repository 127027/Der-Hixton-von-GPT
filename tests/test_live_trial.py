from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path
from uuid import uuid4

import pytest

from hixton.constants import SYMBOLS
from hixton.domain.versions import V6_COIN_STRATEGY as V6
from hixton.live.orders import ExchangeFill, ExchangeOrder, OrderJournal, TrialOrderExecutor
from hixton.live.trial import SignalTrial
from tests.test_paper_engine import _point

NOW = datetime(2026, 9, 7, 10, tzinfo=UTC)


class Exchange:
    def __init__(self):
        self.orders = {}
        self.submits = []
        self.timeout = False

    def submit(self, intent):
        self.submits.append(intent)
        # Exact-decimal fictitious prices, not a real Binance account or historical return.
        price = D("100") if intent.side == "BUY" else D("105")
        quantity = intent.quote_budget / price if intent.side == "BUY" else intent.base_quantity
        order = ExchangeOrder(
            intent.client_order_id,
            str(len(self.submits)),
            intent.symbol,
            intent.side,
            "FILLED",
            quantity,
            quantity * price,
            (ExchangeFill(str(len(self.submits)), quantity, price, D("0"), "USDC"),),
        )
        self.orders[intent.client_order_id] = order
        if self.timeout:
            raise TimeoutError("Ambiguous reply after accepted order")
        return order

    def query(self, intent):
        return self.orders.get(intent.client_order_id)


def trial(tmp_path: Path, exchange=None, *, released=True):
    journal = OrderJournal(tmp_path / "test-only.sqlite3")
    exchange = exchange or Exchange()
    executor = TrialOrderExecutor(journal, exchange, lambda _: released)
    return SignalTrial(journal, executor, V6, lambda: released), exchange


def universe(at=NOW, *, buy_symbol="SOLUSDC", sell_symbol=None):
    result = {}
    for symbol in SYMBOLS:
        point = replace(
            _point(
                symbol,
                at,
                flip_up=symbol == buy_symbol,
                flip_down=symbol == sell_symbol,
                strength=1.0,
            ),
            strategy_version=V6.version,
        )
        result[symbol] = (point,)
    return result


def arm(controller):
    controller.arm(str(uuid4()), "fake-account", now=NOW - timedelta(seconds=5), notional=D("50"))


def open_position(controller, points=None):
    points = points or universe()
    assert controller.advance(points, now=NOW, healthy=True)["state"] == "ENTRY_PENDING"
    assert controller.advance(points, now=NOW, healthy=True)["state"] == "OPEN"


@pytest.mark.parametrize("amount", ["500", "80", "0", "49", "NaN", "Infinity", "-50"])
def test_global_trial_budget_rejects_every_other_amount(tmp_path, amount):
    controller, exchange = trial(tmp_path)
    with pytest.raises(ValueError):
        controller.arm(str(uuid4()), "fake-account", now=NOW, notional=D(amount))
    assert not exchange.submits
    assert controller.report()["state"] == "NOT_STARTED"


def test_missing_release_never_arms(tmp_path):
    controller, exchange = trial(tmp_path, released=False)
    with pytest.raises(RuntimeError, match="Testfreigabe"):
        arm(controller)
    assert not exchange.submits


def test_ten_simultaneous_signals_reserve_one_entry_in_dms_rank_order(tmp_path):
    controller, exchange = trial(tmp_path)
    arm(controller)
    points = universe()
    for symbol in SYMBOLS:
        points[symbol] = (replace(points[symbol][0], flip_up=True, rank_strength=2.0),)
    open_position(controller, points)
    for _ in range(3):
        controller.advance(points, now=NOW, healthy=True)
    assert controller.report()["symbol"] == "BTCUSDC"
    assert len(exchange.submits) == 1 and exchange.submits[0].quote_budget == D("50")


def test_concurrent_arm_is_a_single_global_entitlement(tmp_path):
    first, exchange = trial(tmp_path)
    second, _ = trial(tmp_path, exchange)

    def attempt(controller):
        try:
            arm(controller)
            return True
        except RuntimeError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, (first, second))) == [False, True]
    assert not exchange.submits


@pytest.mark.parametrize("case", ["before_arm", "stale", "incomplete", "open_bar", "unhealthy"])
def test_old_incomplete_or_unhealthy_signals_do_not_enter(tmp_path, case):
    controller, exchange = trial(tmp_path)
    arm(controller)
    at = NOW - timedelta(seconds=10) if case == "before_arm" else NOW
    points = universe(at)
    if case == "incomplete":
        del points["ETHUSDC"]
    if case == "open_bar":
        point = points["SOLUSDC"][0]
        points["SOLUSDC"] = (replace(point, candle=replace(point.candle, closed=False)),)
    controller.advance(
        points,
        now=NOW + timedelta(seconds=91) if case == "stale" else NOW,
        healthy=case != "unhealthy",
    )
    assert controller.report()["state"] == "WAITING_SIGNAL"
    assert not exchange.submits


def test_uses_existing_coin_filter_not_just_green_flip(tmp_path):
    controller, exchange = trial(tmp_path)
    arm(controller)
    points = universe(buy_symbol="BTCUSDC")
    points["BTCUSDC"] = (replace(points["BTCUSDC"][0], abs_cmo=0.1),)
    controller.advance(points, now=NOW, healthy=True)
    assert controller.report()["state"] == "WAITING_SIGNAL"
    assert not exchange.submits


def test_reserved_entry_restart_and_timeout_cannot_rebuy(tmp_path):
    controller, exchange = trial(tmp_path)
    arm(controller)
    controller.advance(universe(), now=NOW, healthy=True)
    restarted, _ = trial(tmp_path, exchange)
    exchange.timeout = True
    assert restarted.advance(universe(), now=NOW, healthy=True)["state"] == "ENTRY_PENDING"
    restarted_again, _ = trial(tmp_path, exchange)
    assert restarted_again.advance(universe(), now=NOW, healthy=False)["state"] == "OPEN"
    assert len(exchange.submits) == 1


def test_disable_waiting_or_reserved_entry_never_sends(tmp_path):
    controller, exchange = trial(tmp_path)
    arm(controller)
    controller.advance(universe(), now=NOW, healthy=True)
    controller.disable_entries()
    assert controller.advance(universe(), now=NOW, healthy=True)["state"] == "CANCELED"
    assert not exchange.submits
    restarted, _ = trial(tmp_path, exchange)
    with pytest.raises(RuntimeError, match="bereits angelegt"):
        arm(restarted)


def test_disable_open_position_preserves_exit_and_completion_survives_restart(tmp_path):
    controller, exchange = trial(tmp_path)
    arm(controller)
    open_position(controller)
    controller.disable_entries()
    assert controller.report()["state"] == "OPEN"
    at = NOW + timedelta(hours=1)
    points = universe(at, buy_symbol="BTCUSDC", sell_symbol="SOLUSDC")
    assert controller.advance(points, now=at, healthy=True)["state"] == "EXIT_PENDING"
    assert controller.advance(points, now=at, healthy=True)["state"] == "AWAITING_RECONCILIATION"
    with pytest.raises(RuntimeError, match="reconciliation incomplete"):
        controller.confirm_reconciled(
            no_open_orders=False, owned_remaining=D(0), account_matches=True, now=at
        )
    controller.confirm_reconciled(
        no_open_orders=True, owned_remaining=D(0), account_matches=True, now=at
    )
    restarted, _ = trial(tmp_path, exchange)
    assert restarted.advance(universe(at), now=at, healthy=True)["state"] == "COMPLETED"
    assert [order.side for order in exchange.submits] == ["BUY", "SELL"]
    assert exchange.submits[-1].base_quantity == D("0.5")
    assert restarted.report()["net_pnl_usdc"] == "2.5"
    assert restarted.report()["buy"]["exchange_order_id"] == "1"
    assert restarted.report()["sell"]["fills"][0]["trade_id"] == "2"
    with pytest.raises(RuntimeError, match="bereits angelegt"):
        arm(restarted)


def test_xrp_stop_uses_frozen_profile_without_adding_take_profit(tmp_path):
    controller, _ = trial(tmp_path)
    arm(controller)
    open_position(controller, universe(buy_symbol="XRPUSDC"))
    at = NOW + timedelta(hours=1)
    points = universe(at, buy_symbol=None)
    point = points["XRPUSDC"][0]
    points["XRPUSDC"] = (replace(point, candle=replace(point.candle, close=95, low=94)),)
    result = controller.advance(points, now=at, healthy=True)
    assert result["state"] == "EXIT_PENDING"
    assert result["exit_signal"]["reason"] == "POLICY_STOP_ATR"
    assert result["exit_rules"]["fixed_take_profit"] is False
    assert result["exit_rules"]["exchange_hosted_stop"] is False


def test_changed_strategy_cannot_silently_take_over_reserved_trade(tmp_path):
    controller, exchange = trial(tmp_path)
    arm(controller)
    controller.strategy = replace(V6, version="unexpected-version")
    result = controller.advance(universe(), now=NOW, healthy=True)
    assert result["reason"] == "FROZEN_STRATEGY_MISMATCH"
    assert not exchange.submits


def test_base_entry_fee_reduces_sell_and_unknown_bnb_value_is_not_zero(tmp_path):
    controller, exchange = trial(tmp_path)
    arm(controller)
    controller.advance(universe(), now=NOW, healthy=True)
    exchange.timeout = True
    controller.advance(universe(), now=NOW, healthy=True)
    identity = exchange.submits[0].client_order_id
    response = exchange.orders[identity]
    exchange.orders[identity] = replace(
        response, fills=(replace(response.fills[0], commission=D("0.001"), commission_asset="SOL"),)
    )
    assert controller.advance(universe(), now=NOW, healthy=True)["state"] == "OPEN"
    at = NOW + timedelta(hours=1)
    points = universe(at, buy_symbol=None, sell_symbol="SOLUSDC")
    controller.advance(points, now=at, healthy=True)
    controller.advance(points, now=at, healthy=True)
    identity = exchange.submits[-1].client_order_id
    response = exchange.orders[identity]
    exchange.orders[identity] = replace(
        response,
        fills=(replace(response.fills[0], commission=D("0.0001"), commission_asset="BNB"),),
    )
    controller.advance(points, now=at, healthy=True)
    controller.confirm_reconciled(
        no_open_orders=True, owned_remaining=D(0), account_matches=True, now=at
    )
    assert exchange.submits[-1].base_quantity == D("0.499")
    assert controller.report()["net_pnl_usdc"] is None
    assert controller.report()["unvalued_fee_assets"] == ["BNB"]


def test_missed_exit_uses_current_reference_without_backdated_fill(tmp_path):
    controller, exchange = trial(tmp_path)
    arm(controller)
    open_position(controller)
    missed_at = NOW + timedelta(hours=1)
    current_at = NOW + timedelta(hours=4)
    missed = universe(missed_at, buy_symbol=None, sell_symbol="SOLUSDC")["SOLUSDC"][0]
    current = universe(current_at, buy_symbol=None)["SOLUSDC"][0]
    current = replace(current, candle=replace(current.candle, close=99))
    points = {"SOLUSDC": (missed, current)}
    result = controller.advance(points, now=current_at, healthy=True)
    assert result["exit_signal"]["bar_close"] == missed_at.isoformat()
    assert result["exit_signal"]["reference_price"] == "99"
    controller.advance(points, now=current_at, healthy=True)
    assert exchange.submits[-1].reference_price == D("99")


def test_tradable_residue_is_not_a_completed_success(tmp_path):
    controller, exchange = trial(tmp_path)
    arm(controller)
    open_position(controller)
    at = NOW + timedelta(hours=1)
    points = universe(at, buy_symbol=None, sell_symbol="SOLUSDC")
    controller.advance(points, now=at, healthy=True)
    exchange.timeout = True
    controller.advance(points, now=at, healthy=True)
    identity = exchange.submits[-1].client_order_id
    response = exchange.orders[identity]
    exchange.orders[identity] = replace(
        response,
        state="CANCELED",
        executed_quantity=D("0.25"),
        cumulative_quote=D("26.25"),
        fills=(replace(response.fills[0], quantity=D("0.25")),),
    )
    result = controller.advance(points, now=at, healthy=True)
    assert result["state"] == "NEEDS_REVIEW"
    assert result["has_unsettled"] is True
    with pytest.raises(RuntimeError, match="reconciliation gate"):
        controller.confirm_reconciled(
            no_open_orders=True, owned_remaining=D(0), account_matches=True, now=at
        )


def test_unfilled_expired_reservation_is_not_replaced(tmp_path):
    controller, exchange = trial(tmp_path)
    arm(controller)
    controller.advance(universe(), now=NOW, healthy=True)
    assert (
        controller.advance(universe(), now=NOW + timedelta(seconds=91), healthy=True)["state"]
        == "FAILED"
    )
    assert not exchange.submits


def test_entry_release_expiry_does_not_block_an_owned_exit(tmp_path):
    controller, exchange = trial(tmp_path)
    arm(controller)
    open_position(controller)
    controller.release_check = lambda: False
    at = NOW + timedelta(hours=1)
    points = universe(at, buy_symbol=None, sell_symbol="SOLUSDC")
    controller.advance(points, now=at, healthy=True)
    assert controller.advance(points, now=at, healthy=True)["state"] == "AWAITING_RECONCILIATION"
    assert [order.side for order in exchange.submits] == ["BUY", "SELL"]


@pytest.mark.parametrize(
    "base", ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "LINK", "AVAX", "DOT", "DOGE"]
)
def test_each_usdc_coin_uses_own_profile_once_without_relabeling_usdt(tmp_path, base):
    from hixton.domain.versions import V7_USDC_STRATEGY as V7

    journal = OrderJournal(tmp_path / "usdc-test-only.sqlite3")
    fake = Exchange()
    controller = SignalTrial(
        journal, TrialOrderExecutor(journal, fake, lambda _: True), V7, lambda: True
    )
    arm(controller)

    def points(at, enter):
        # ETH's slope filter needs its real 24-bar history; all ten profiles
        # remain unchanged. This is a synthetic controller test, not approval.
        result = {}
        for symbol in V7.symbols:
            history = []
            for offset in range(25):
                point = _point(
                    symbol,
                    at - timedelta(hours=24 - offset),
                    flip_up=enter and offset == 24 and symbol == base + "USDC",
                    flip_down=not enter and offset == 24 and symbol == base + "USDC",
                    strength=1.0,
                )
                history.append(
                    replace(
                        point, strategy_version=V7.version, vidya=float(70 + offset), abs_cmo=0.9
                    )
                )
            result[symbol] = tuple(history)
        return result

    entry_points = points(NOW, True)
    # A USDT universe must not be implicitly accepted by this USDC controller.
    wrong_quote = {
        symbol.removesuffix("USDC") + "USDT": series for symbol, series in entry_points.items()
    }
    assert controller.advance(wrong_quote, now=NOW, healthy=True)["state"] == "WAITING_SIGNAL"
    assert controller.advance(entry_points, now=NOW, healthy=True)["state"] == "ENTRY_PENDING"
    assert controller.advance(entry_points, now=NOW, healthy=True)["state"] == "OPEN"
    at = NOW + timedelta(hours=1)
    exit_points = points(at, False)
    controller.advance(exit_points, now=at, healthy=True)
    controller.advance(exit_points, now=at, healthy=True)
    controller.confirm_reconciled(
        no_open_orders=True, owned_remaining=D(0), account_matches=True, now=at
    )
    report = controller.report()
    assert report["state"] == "COMPLETED"
    assert report["quote_asset"] == "USDC"
    assert report["quote_budget_usdt"] is None
    assert report["net_pnl_usdt"] is None
    assert report["net_pnl_quote"] == "2.5"
    assert fake.submits[0].symbol == base + "USDC"
    assert fake.submits[0].quote_budget == D("50")
    assert [order.side for order in fake.submits] == ["BUY", "SELL"]
    assert not V7.paper_approved
