"""Offline-only production Live tests. No real Binance credentials or network orders."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path

from hixton.backtest.models import ExecutionRules
from hixton.constants import SYMBOLS
from hixton.domain.versions import V6_COIN_STRATEGY as V6
from hixton.live.orders import ExchangeFill, ExchangeOrder
from hixton.live.production import (
    LiveAccountSnapshot,
    LiveBalanceReconciler,
    LiveIntent,
    LiveOrderExecutor,
    LiveOrderJournal,
    LivePortfolioController,
)
from tests.test_paper_engine import _point

NOW = datetime.now(UTC).replace(second=0, microsecond=0)


class Exchange:
    def __init__(self) -> None:
        self.orders: dict[str, ExchangeOrder] = {}
        self.submits: list[LiveIntent] = []
        self.timeout = False

    def submit(self, intent: LiveIntent) -> ExchangeOrder:
        self.submits.append(intent)
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
            (
                ExchangeFill(
                    str(len(self.submits)),
                    quantity,
                    price,
                    D("0"),
                    "USDC",
                    quantity * price,
                ),
            ),
        )
        self.orders[intent.client_order_id] = order
        if self.timeout:
            raise TimeoutError("ambiguous accepted order")
        return order

    def query(self, intent: LiveIntent) -> ExchangeOrder | None:
        return self.orders.get(intent.client_order_id)


class Account:
    def __init__(self) -> None:
        self.account = "fake-account"
        self.balances = {"USDC": (D("250"), D("0")), "BNB": (D("0"), D("0"))}
        self.open_orders: tuple[str, ...] = ()

    def snapshot(self) -> LiveAccountSnapshot:
        return LiveAccountSnapshot(
            self.account,
            datetime.now(UTC),
            dict(self.balances),
            self.open_orders,
        )

    def apply(self, order: ExchangeOrder) -> None:
        fill = order.fills[0]
        base = order.symbol.removesuffix("USDC")
        base_free = self.balances.get(base, (D("0"), D("0")))[0]
        quote_free = self.balances["USDC"][0]
        if order.side == "BUY":
            self.balances[base] = (base_free + fill.quantity, D("0"))
            self.balances["USDC"] = (quote_free - fill.quote, D("0"))
        else:
            self.balances[base] = (base_free - fill.quantity, D("0"))
            self.balances["USDC"] = (quote_free + fill.quote, D("0"))


class ApplyingExchange(Exchange):
    def __init__(self, account: Account) -> None:
        super().__init__()
        self.account = account

    def submit(self, intent: LiveIntent) -> ExchangeOrder:
        order = super().submit(intent)
        self.account.apply(order)
        return order


def universe(at: datetime, *, enter: tuple[str, ...] = (), exit_symbol: str | None = None):
    result = {}
    for symbol in SYMBOLS:
        history = []
        for offset in range(25):
            point = _point(
                symbol,
                at - timedelta(hours=24 - offset),
                flip_up=offset == 24 and symbol in enter,
                flip_down=offset == 24 and symbol == exit_symbol,
                strength=2.0 if symbol == "BTCUSDC" else 1.0,
            )
            history.append(
                replace(point, strategy_version=V6.version, vidya=float(70 + offset), abs_cmo=0.9)
            )
        result[symbol] = tuple(history)
    return result


def controller(tmp_path: Path):
    database = tmp_path / "live.sqlite3"
    account = Account()
    exchange = ApplyingExchange(account)
    journal = LiveOrderJournal(database)
    reconciler = LiveBalanceReconciler(journal)
    holder = {}
    executor = LiveOrderExecutor(journal, exchange, lambda intent: holder["c"].pre_submit(intent))
    rules = {
        symbol: ExecutionRules(step_size=D("0.000001"), min_qty=D("0.000001"), min_notional=D("5"))
        for symbol in SYMBOLS
    }
    settings = [3, D("80"), False]
    c = LivePortfolioController(
        database,
        journal,
        executor,
        reconciler,
        account.snapshot,
        lambda: (settings[0], settings[1], settings[2]),
        lambda: rules,
        V6,
        lambda: True,
    )
    holder["c"] = c
    return c, exchange, account, settings


def test_live_intent_hard_caps_three_by_eighty() -> None:
    for slots in (1, 2, 3):
        intent = LiveIntent(
            f"buy-{slots}",
            "account",
            "BTCUSDC",
            "BUY",
            V6.version,
            D("100"),
            slots,
            quote_budget=D("80") * slots,
        )
        assert len(intent.client_order_id) == 36
    for slots, budget in ((4, "320"), (3, "800"), (1, "50"), (1, "NaN")):
        try:
            LiveIntent(
                "bad",
                "account",
                "BTCUSDC",
                "BUY",
                V6.version,
                D("100"),
                slots,
                quote_budget=D(budget),
            )
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe Live budget was accepted")


def test_ranked_repeat_three_slots_is_one_bounded_market_order(tmp_path: Path) -> None:
    c, exchange, account, _settings = controller(tmp_path)
    initial = universe(NOW - timedelta(hours=1))
    c.enable("fake-account", initial, account.snapshot(), now=NOW)
    points = universe(NOW, enter=("BTCUSDC",))
    c.advance(points, now=NOW, healthy=True)
    c.advance(points, now=NOW, healthy=True)
    c.advance(points, now=NOW, healthy=True)
    report = c.report()
    assert len(exchange.submits) == 1
    assert exchange.submits[0].side == "BUY"
    assert exchange.submits[0].quote_budget == D("240")
    assert exchange.submits[0].slot_count == 3
    assert report["used_slots"] == 3
    assert report["free_slots"] == 0
    assert account.balances["USDC"][0] == D("10")


def test_ten_simultaneous_signals_never_exceed_three_slots(tmp_path: Path) -> None:
    c, exchange, account, _settings = controller(tmp_path)
    c.enable(
        "fake-account",
        universe(NOW - timedelta(hours=1)),
        account.snapshot(),
        now=NOW,
    )
    points = universe(NOW, enter=SYMBOLS)
    for _ in range(12):
        c.advance(points, now=NOW, healthy=True)
    assert sum(intent.slot_count for intent in exchange.submits if intent.side == "BUY") == 3
    assert (
        sum(intent.quote_budget for intent in exchange.submits if intent.side == "BUY")
        == D("240")
    )
    assert c.report()["used_slots"] == 3


def test_timeout_restart_reconciles_without_duplicate_submit(tmp_path: Path) -> None:
    c, exchange, account, _settings = controller(tmp_path)
    c.enable(
        "fake-account",
        universe(NOW - timedelta(hours=1)),
        account.snapshot(),
        now=NOW,
    )
    points = universe(NOW, enter=("BTCUSDC",))
    c.advance(points, now=NOW, healthy=True)
    exchange.timeout = True
    c.advance(points, now=NOW, healthy=True)
    assert len(exchange.submits) == 1
    exchange.timeout = False
    for _ in range(4):
        c.advance(points, now=NOW, healthy=True)
    assert len(exchange.submits) == 1
    assert c.report()["used_slots"] == 3


def test_settings_change_or_emergency_stop_blocks_new_live_entry(tmp_path: Path) -> None:
    c, exchange, account, settings = controller(tmp_path)
    c.enable(
        "fake-account",
        universe(NOW - timedelta(hours=1)),
        account.snapshot(),
        now=NOW,
    )
    settings[0] = 10
    settings[1] = D("250")
    for _ in range(3):
        c.advance(universe(NOW, enter=("BTCUSDC",)), now=NOW, healthy=True)
    assert not exchange.submits
    assert c.report()["state"] in {"EXIT_ONLY", "LIVE_DISABLED"}


def test_account_mismatch_fails_closed_before_order(tmp_path: Path) -> None:
    c, exchange, account, _settings = controller(tmp_path)
    c.enable(
        "fake-account",
        universe(NOW - timedelta(hours=1)),
        account.snapshot(),
        now=NOW,
    )
    account.balances["USDC"] = (D("251"), D("0"))
    for _ in range(3):
        c.advance(universe(NOW, enter=("BTCUSDC",)), now=NOW, healthy=True)
    assert not exchange.submits
    assert c.report()["state"] == "NEEDS_REVIEW"


def test_exit_is_allowed_after_entries_are_disabled(tmp_path: Path) -> None:
    c, exchange, account, _settings = controller(tmp_path)
    c.enable(
        "fake-account",
        universe(NOW - timedelta(hours=1)),
        account.snapshot(),
        now=NOW,
    )
    entry = universe(NOW, enter=("SOLUSDC",))
    for _ in range(4):
        c.advance(entry, now=NOW, healthy=True)
    assert c.report()["used_slots"] == 3
    c.disable_entries()
    later = NOW + timedelta(hours=1)
    exit_points = universe(later, exit_symbol="SOLUSDC")
    for _ in range(5):
        c.advance(exit_points, now=later, healthy=True)
    assert [item.side for item in exchange.submits] == ["BUY", "SELL"]
    assert c.report()["used_slots"] == 0
    assert c.report()["state"] == "EXIT_ONLY"


def test_repeated_scheduler_ticks_do_not_duplicate_orders(tmp_path: Path) -> None:
    c, exchange, account, _settings = controller(tmp_path)
    c.enable(
        "fake-account",
        universe(NOW - timedelta(hours=1)),
        account.snapshot(),
        now=NOW,
    )
    points = universe(NOW, enter=("ETHUSDC",))
    for _ in range(30):
        c.advance(points, now=NOW, healthy=True)
    buys = [item for item in exchange.submits if item.side == "BUY"]
    assert len(buys) == 1
    assert buys[0].quote_budget <= D("240")
