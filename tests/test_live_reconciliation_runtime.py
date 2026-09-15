"""Offline lifecycle contract. No network, keys, real money or release flag."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from uuid import uuid4

import pytest

from hixton.domain.versions import V6_COIN_STRATEGY as V6
from hixton.live.exchange import BinanceSpotExchange
from hixton.live.orders import OrderJournal, TrialOrderExecutor
from hixton.live.reconciliation import AccountSnapshot, TrialReconciler, read_account_snapshot
from hixton.live.runtime import TrialRuntime
from hixton.live.trial import SignalTrial
from hixton.paper.engine import initialize_paper_at_latest, process_new_closed_points
from tests.test_live_trial import NOW, universe
from tests.test_paper_engine import _point, _rules


class SpotFixture:
    """Exercise the real adapter's request/ACK/query/fill parser without HTTP."""

    def __init__(self):
        self.orders = {}
        self.calls = []
        self.balances = {"USDC": D("1200"), "BTC": D("0.003"), "BNB": D("0.03")}
        self.open_orders = []
        self.timeout = False
        self.fee_asset = "USDC"
        self.fee = D("0.05")

    def request(self, method, path, params):
        self.calls.append((method, path, dict(params)))
        if path.endswith("account"):
            return {
                "balances": [
                    {"asset": a, "free": str(q), "locked": "0"} for a, q in self.balances.items()
                ]
            }
        if path.endswith("openOrders"):
            return self.open_orders
        if method == "POST":
            side, symbol = params["side"], params["symbol"]
            assert params["type"] == "MARKET"
            base = symbol.removesuffix("USDC")
            price = D("100") if side == "BUY" else D("105")
            if side == "BUY":
                assert params["quoteOrderQty"] == "50.00" and "quantity" not in params
                qty = D("50") / price
            else:
                assert "quoteOrderQty" not in params
                qty = D(params["quantity"])
            quote = qty * price
            sign = D(1) if side == "BUY" else D(-1)
            self.balances[base] = self.balances.get(base, D(0)) + sign * qty
            self.balances["USDC"] -= sign * quote
            self.balances[self.fee_asset] -= self.fee
            identity = params["newClientOrderId"]
            assert identity not in self.orders
            number = len(self.orders) + 1
            self.orders[identity] = {
                "symbol": symbol,
                "clientOrderId": identity,
                "orderId": number,
                "side": side,
                "type": "MARKET",
                "status": "FILLED",
                "executedQty": str(qty),
                "cummulativeQuoteQty": str(quote),
                "fill": {
                    "symbol": symbol,
                    "orderId": number,
                    "id": number,
                    "isBuyer": side == "BUY",
                    "qty": str(qty),
                    "price": str(price),
                    "quoteQty": str(quote),
                    "commissionAsset": self.fee_asset,
                    "commission": str(self.fee),
                },
            }
            if self.timeout:
                self.timeout = False
                raise TimeoutError("Response lost after fill")
            return self.orders[identity]
        if path.endswith("myTrades"):
            return [
                order["fill"]
                for order in self.orders.values()
                if str(order["orderId"]) == params["orderId"]
            ]
        return self.orders[params["origClientOrderId"]]

    def snapshot(self, at=NOW):
        return AccountSnapshot(
            "fixture",
            at,
            {a: (q, D(0)) for a, q in self.balances.items()},
            tuple(row["clientOrderId"] for row in self.open_orders),
        )


def make_runtime(path, transport, *, clock=lambda: NOW):
    journal = OrderJournal(path)
    exchange = BinanceSpotExchange(transport, account_fingerprint="fixture", quote_asset="USDC")
    controller = SignalTrial(
        journal, TrialOrderExecutor(journal, exchange, lambda _: True), V6, lambda: True
    )
    reconciler = TrialReconciler(journal)
    runtime = TrialRuntime(controller, reconciler, lambda: transport.snapshot(clock()), clock=clock)
    return runtime


def history(at, symbol, enter):
    return {
        coin: tuple(
            replace(
                _point(
                    coin,
                    at - timedelta(hours=24 - offset),
                    flip_up=enter and offset == 24 and coin == symbol,
                    flip_down=not enter and offset == 24 and coin == symbol,
                    strength=1,
                ),
                strategy_version=V6.version,
                vidya=float(70 + offset),
                abs_cmo=0.9,
            )
            for offset in range(25)
        )
        for coin in V6.symbols
    }


@pytest.mark.parametrize("symbol", V6.symbols)
def test_all_ten_profiles_complete_exactly_one_round_trip_with_real_adapter(tmp_path, symbol):
    fixture = SpotFixture()
    at = NOW
    runtime = make_runtime(tmp_path / "isolated.sqlite3", fixture, clock=lambda: at)
    runtime.reconciler.capture(fixture.snapshot(), now=NOW)
    runtime.trial.arm(str(uuid4()), "fixture", now=NOW - timedelta(seconds=2), notional=D(50))
    points = history(NOW, symbol, True)
    paper_path = str(tmp_path / "paper.sqlite3")
    initialize_paper_at_latest(
        paper_path,
        history(NOW - timedelta(hours=1), symbol, False),
        strategy_key=V6.key,
        strategy_version=V6.version,
        at=NOW - timedelta(hours=1),
        starting_cash_usdc=D(250),
    )

    def paper_decisions(points):
        execution = {
            coin: [
                replace(
                    p.candle,
                    open_time_utc=p.candle.open_time_utc + timedelta(hours=1),
                    close_time_utc=p.candle.close_time_utc + timedelta(hours=1),
                    closed=False,
                )
                for p in series
            ]
            for coin, series in points.items()
        }
        return process_new_closed_points(
            paper_path,
            points,
            _rules(),
            strategy_key=V6.key,
            strategy_version=V6.version,
            execution_candles_by_symbol=execution,
            trade_policies_by_symbol=V6.policy_map(),
        )

    paper_entries = paper_decisions(points)
    assert [(event.symbol, event.action) for event in paper_entries] == [(symbol, "ENTER_LONG")]
    assert (
        runtime.tick(points, now=NOW, healthy=True, entries_allowed=True)["state"]
        == "ENTRY_PENDING"
    )
    assert runtime.tick(points, now=NOW, healthy=True, entries_allowed=True)["state"] == "OPEN"
    assert runtime.trial.report()["entries_enabled"] is False
    at = NOW + timedelta(hours=1)
    points = history(at, symbol, False)
    paper_exits = paper_decisions(points)
    assert [(event.symbol, event.action) for event in paper_exits] == [(symbol, "EXIT_LONG")]
    # Live-off blocks entries, not the already-owned exit. Actual fills determine cash.
    assert (
        runtime.tick(points, now=at, healthy=True, entries_allowed=False)["state"] == "EXIT_PENDING"
    )
    result = runtime.tick(points, now=at, healthy=True, entries_allowed=False)
    assert result["state"] == "COMPLETED"
    assert D(result["net_pnl_usdc"]) == D("2.40")
    assert fixture.balances["USDC"] == D("1202.40")
    runtime.tick(history(at, "ADAUSDC", True), now=at, healthy=True, entries_allowed=True)
    posts = [p for method, _, p in fixture.calls if method == "POST"]
    assert [p["side"] for p in posts] == ["BUY", "SELL"]
    assert posts[1]["quantity"] == "0.5"  # Existing BTC/BNB were never sold.
    assert fixture.balances["BTC"] == D("0.003") and fixture.balances["BNB"] == D("0.03")


def test_timeout_restart_recovers_by_id_without_another_buy(tmp_path):
    fixture = SpotFixture()
    path = tmp_path / "trial.sqlite3"
    runtime = make_runtime(path, fixture)
    runtime.reconciler.capture(fixture.snapshot(), now=NOW)
    runtime.trial.arm(str(uuid4()), "fixture", now=NOW - timedelta(seconds=2), notional=D(50))
    runtime.tick(universe(), now=NOW, healthy=True, entries_allowed=True)
    fixture.timeout = True
    runtime.tick(universe(), now=NOW, healthy=True, entries_allowed=True)
    restarted = make_runtime(path, fixture)
    assert (
        restarted.tick(universe(), now=NOW, healthy=False, entries_allowed=False)["state"] == "OPEN"
    )
    assert sum(method == "POST" for method, _, _ in fixture.calls) == 1


@pytest.mark.parametrize("case", ["balance", "open_order", "account", "stale", "locked"])
def test_reconciliation_never_accepts_unproved_balances(tmp_path, case):
    fixture = SpotFixture()
    runtime = make_runtime(tmp_path / "trial.sqlite3", fixture)
    runtime.reconciler.capture(fixture.snapshot(), now=NOW)
    snapshot = fixture.snapshot()
    if case == "balance":
        snapshot.balances["BTC"] = (D("0.002"), D(0))
    elif case == "open_order":
        snapshot = replace(snapshot, open_orders=("manual-order",))
    elif case == "account":
        snapshot = replace(snapshot, account="another-account")
    elif case == "stale":
        snapshot = replace(snapshot, observed_at=NOW - timedelta(seconds=16))
    else:
        snapshot.balances["BTC"] = (D("0.002"), D("0.001"))
    if case in {"account", "stale"}:
        with pytest.raises((ValueError, RuntimeError)):
            runtime.reconciler.check(snapshot, now=NOW)
    else:
        assert runtime.reconciler.check(snapshot, now=NOW)["balances_match"] is False


def test_no_inactive_or_stopped_runtime_network_and_immutable_baseline(tmp_path):
    fixture = SpotFixture()
    runtime = make_runtime(tmp_path / "trial.sqlite3", fixture)
    runtime.tick({}, now=NOW, healthy=True, entries_allowed=True)
    runtime.reconciler.capture(fixture.snapshot(), now=NOW)
    with pytest.raises(RuntimeError, match="replaced"):
        runtime.reconciler.capture(fixture.snapshot(), now=NOW)
    runtime.trial.arm(str(uuid4()), "fixture", now=NOW - timedelta(seconds=2), notional=D(50))
    runtime.stop()
    assert (
        runtime.tick(universe(), now=NOW, healthy=True, entries_allowed=True)["state"]
        == "WAITING_SIGNAL"
    )
    assert fixture.calls == []


def test_account_reader_reads_around_orders_and_rejects_changes():
    fixture = SpotFixture()
    result = read_account_snapshot(fixture, account="fixture")
    result.validate(datetime.now(UTC))
    assert [path for _, path, _ in fixture.calls] == [
        "/api/v3/account",
        "/api/v3/openOrders",
        "/api/v3/account",
    ]
    original = fixture.request

    def changing(method, path, params):
        result = original(method, path, params)
        if path.endswith("account"):
            fixture.balances["USDC"] += D(1)
        return result

    fixture.request = changing
    with pytest.raises(ValueError, match="changed"):
        read_account_snapshot(fixture, account="fixture")


def test_bnb_fees_reconcile_as_bnb_and_are_not_fabricated_net_profit(tmp_path):
    fixture = SpotFixture()
    fixture.fee_asset, fixture.fee = "BNB", D("0.0001")
    at = NOW
    runtime = make_runtime(tmp_path / "trial.sqlite3", fixture, clock=lambda: at)
    runtime.reconciler.capture(fixture.snapshot(), now=NOW)
    runtime.trial.arm(str(uuid4()), "fixture", now=NOW - timedelta(seconds=2), notional=D(50))
    runtime.tick(universe(), now=NOW, healthy=True, entries_allowed=True)
    runtime.tick(universe(), now=NOW, healthy=True, entries_allowed=True)
    at += timedelta(hours=1)
    points = universe(at, buy_symbol=None, sell_symbol="SOLUSDC")
    runtime.tick(points, now=at, healthy=True, entries_allowed=False)
    result = runtime.tick(points, now=at, healthy=True, entries_allowed=False)
    assert result["state"] == "COMPLETED"
    assert result["net_pnl_usdc"] is None and result["unvalued_fee_assets"] == ["BNB"]
    assert fixture.balances["BNB"] == D("0.0298")


def test_unexpected_account_change_prevents_completion_and_recovers_after_clarification(tmp_path):
    fixture = SpotFixture()
    at = NOW
    runtime = make_runtime(tmp_path / "trial.sqlite3", fixture, clock=lambda: at)
    runtime.reconciler.capture(fixture.snapshot(), now=NOW)
    runtime.trial.arm(str(uuid4()), "fixture", now=NOW - timedelta(seconds=2), notional=D(50))
    runtime.tick(universe(), now=NOW, healthy=True, entries_allowed=True)
    runtime.tick(universe(), now=NOW, healthy=True, entries_allowed=True)
    fixture.balances["BTC"] -= D("0.001")
    at += timedelta(hours=1)
    points = universe(at, buy_symbol=None, sell_symbol="SOLUSDC")
    runtime.tick(points, now=at, healthy=True, entries_allowed=False)
    result = runtime.tick(points, now=at, healthy=True, entries_allowed=False)
    assert result["state"] == "AWAITING_RECONCILIATION" and result["net_pnl_usdc"] is None
    assert sum(method == "POST" for method, _, _ in fixture.calls) == 2
