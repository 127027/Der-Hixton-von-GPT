"""Exchange filters are exercised offline, including old read-only stores."""

import json
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import pytest

from hixton.backtest.engine import run_single_backtest
from hixton.backtest.models import ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.constants import SYMBOLS
from hixton.data.binance import BinanceApiError
from hixton.data.storage import CandleStore, StoredSymbolRules
from hixton.domain.market_rules import (
    market_filter_values,
    market_order_block_reason,
    market_order_is_dust,
    market_quantity_step,
    round_market_quantity,
)
from hixton.domain.strategy import evaluate_batch
from hixton.domain.versions import V2_RESEARCH_STRATEGY
from hixton.live.binance import assess_account
from hixton.paper.engine import initialize_paper_at_latest, process_new_closed_points
from hixton.paper.storage import PaperStore
from tests.golden_reference import deterministic_candles
from tests.test_binance_adapter import StubBinance
from tests.test_live_preparation import account_fixture
from tests.test_live_production import NOW as LIVE_NOW
from tests.test_live_production import controller, enable_now
from tests.test_live_production import universe as live_universe
from tests.test_live_trial import NOW, arm, open_position, trial, universe
from tests.test_paper_engine import _mapping, _point, _rules
from tests.test_paper_engine import process_new_closed_points as process_paper_fixture


def filter_fixture():
    return {
        "LOT_SIZE": {"minQty": "0.02", "maxQty": "100", "stepSize": "0.02"},
        "MARKET_LOT_SIZE": {"minQty": "0.03", "maxQty": "10", "stepSize": "0.03"},
        "MIN_NOTIONAL": {"minNotional": "5", "applyToMarket": True, "avgPriceMins": 5},
        "NOTIONAL": {
            "minNotional": "10",
            "maxNotional": "500",
            "applyMinToMarket": True,
            "applyMaxToMarket": True,
            "avgPriceMins": 1,
        },
    }


def test_parser_retains_both_quantity_filters_and_applicable_notional_bounds():
    values = market_filter_values(filter_fixture())
    rules = ExecutionRules(**values)
    assert rules.min_qty == D(".02") and rules.max_qty == D(100)
    assert rules.market_min_qty == D(".03") and rules.market_max_qty == D(10)
    assert rules.market_step_size == D(".03")
    assert rules.min_notional == D(10) and rules.max_notional == D(500)
    assert rules.notional_avg_price_mins == 5
    raw = filter_fixture()
    raw["NOTIONAL"].update(applyMinToMarket=False, applyMaxToMarket=False)
    rules = ExecutionRules(**market_filter_values(raw))
    assert rules.min_notional == D(5) and rules.max_notional == 0
    raw["MIN_NOTIONAL"]["applyToMarket"] = False
    assert market_filter_values(raw)["min_notional"] == 0


def test_quantity_grid_is_common_multiple_and_never_increases_sell_quantity():
    rules = ExecutionRules(**market_filter_values(filter_fixture()))
    assert market_quantity_step(rules) == D(".06")
    assert round_market_quantity(D("1.01"), rules) == D(".96")
    assert market_order_block_reason(rules, D(".96"), D(100)) is None
    assert market_order_block_reason(rules, D("1.02"), D(100)) is None
    assert market_order_block_reason(rules, D("1.00"), D(100)) == "MARKET_QUANTITY_STEP"


@pytest.mark.parametrize(
    "field,limit,quantity,price,expected",
    [
        ("max_qty", ".5", ".6", "100", "LOT_SIZE_MAX_QTY"),
        ("market_max_qty", ".5", ".6", "100", "MARKET_LOT_SIZE_MAX_QTY"),
        ("max_notional", "50", ".6", "100", "NOTIONAL_MAX"),
        ("market_min_qty", ".7", ".6", "100", "MARKET_MIN_QTY"),
    ],
)
def test_market_bounds_are_inclusive_and_upper_violations_are_never_dust(
    field, limit, quantity, price, expected
):
    rules = replace(ExecutionRules(), **{field: D(limit)})
    reason = market_order_block_reason(rules, D(quantity), D(price))
    assert reason == expected
    assert market_order_is_dust(reason) is (field == "market_min_qty")
    if field.endswith("max_qty"):
        assert market_order_block_reason(rules, D(limit), D(price)) is None
    elif field == "max_notional":
        assert market_order_block_reason(rules, D(".5"), D(price)) is None


@pytest.mark.parametrize(
    "field",
    [
        "tick_size",
        "step_size",
        "min_qty",
        "min_notional",
        "max_qty",
        "market_min_qty",
        "market_max_qty",
        "market_step_size",
        "max_notional",
    ],
)
@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1"])
def test_all_execution_rule_amounts_require_finite_nonnegative_decimals(field, value):
    with pytest.raises(ValueError, match="finite"):
        ExecutionRules(**{field: D(value)})


def test_fresh_exchange_parser_and_stored_rules_roundtrip_all_limits(tmp_path):
    raw = filter_fixture()
    payload = {
        "symbols": [
            {
                "symbol": "ETHUSDC",
                "status": "TRADING",
                "baseAsset": "ETH",
                "quoteAsset": "USDC",
                "isSpotTradingAllowed": True,
                "orderTypes": ["MARKET"],
                "filters": [{"filterType": kind, **values} for kind, values in raw.items()],
            }
        ]
    }
    rules = StubBinance([payload]).symbol_rules("ETHUSDC")
    values = market_filter_values(raw)
    saved = StoredSymbolRules(
        rules.symbol,
        rules.status,
        rules.quote_asset,
        rules.spot_allowed,
        rules.order_types,
        rules.tick_size,
        rules.step_size,
        rules.min_qty,
        rules.min_notional,
        datetime.now(UTC),
        **{
            key: value
            for key, value in values.items()
            if key not in {"tick_size", "step_size", "min_qty", "min_notional"}
        },
    )
    path = tmp_path / "filters.sqlite3"
    with CandleStore(path) as store:
        store.put_symbol_rules(saved)
    with CandleStore(path, read_only=True) as store:
        loaded = store.load_symbol_rules("ETHUSDC")
    assert loaded == saved
    assert loaded.market_limits_known is True
    assert ExecutionRules.from_symbol_rules(loaded) == ExecutionRules(**values)
    bad = json.loads(json.dumps(payload))
    bad["symbols"][0]["filters"][0]["maxQty"] = "NaN"
    with pytest.raises(BinanceApiError):
        StubBinance([bad]).symbol_rules("ETHUSDC")


def test_old_readonly_store_never_migrates_and_rw_migrates_without_losing_rules(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE symbol_rules (symbol TEXT PRIMARY KEY,status TEXT,"
            "quote_asset TEXT,spot_allowed INTEGER,order_types_json TEXT,"
            "tick_size_text TEXT,step_size_text TEXT,min_qty_text TEXT,"
            "min_notional_text TEXT,checked_at_utc TEXT)"
        )
        connection.execute(
            "INSERT INTO symbol_rules VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                "ETHUSDC",
                "TRADING",
                "USDC",
                1,
                '["MARKET"]',
                ".01",
                ".001",
                ".001",
                "5",
                datetime.now(UTC).isoformat(),
            ),
        )
    before = path.read_bytes()
    with CandleStore(path, read_only=True) as store:
        old = store.load_symbol_rules("ETHUSDC")
        assert old.max_qty == 0 and old.market_max_qty == 0
        assert old.market_limits_known is False
    assert path.read_bytes() == before
    with CandleStore(path) as store:
        assert store.load_symbol_rules("ETHUSDC") == old
        store.put_symbol_rules(replace(old, max_qty=D(50), market_max_qty=D(5)))
    with CandleStore(path, read_only=True) as store:
        new = store.load_symbol_rules("ETHUSDC")
    assert new.max_qty == 50 and new.market_max_qty == 5 and new.step_size == D(".001")


def test_preflight_honors_market_application_flags_and_rejects_applicable_maximum():
    permissions, account, orders, markets = account_fixture()
    for item in markets["symbols"]:
        item["filters"] = [
            {"filterType": kind, **values} for kind, values in filter_fixture().items()
        ]
        for row in item["filters"]:
            if row["filterType"] == "NOTIONAL":
                row.update(
                    minNotional="1000",
                    maxNotional="40",
                    applyMinToMarket=False,
                    applyMaxToMarket=False,
                )
    assert assess_account(permissions, account, orders, markets, D(50))["account_checks_passed"]
    for item in markets["symbols"]:
        next(row for row in item["filters"] if row["filterType"] == "NOTIONAL")[
            "applyMaxToMarket"
        ] = True
    result = assess_account(permissions, account, orders, markets, D(50))
    assert not result["account_checks_passed"]
    assert any("Maximum" in reason for reason in result["blockers"])


@pytest.mark.parametrize("field", ["max_qty", "market_max_qty", "max_notional"])
def test_isolated_backtest_blocks_oversized_orders_instead_of_fake_fill(field):
    candles = deterministic_candles("ETHUSDC", 900)
    rules = replace(ExecutionRules(), **{field: D(".01")})
    result = run_single_backtest(
        symbol="ETHUSDC",
        candles=candles,
        report_start_utc=candles[400].open_time_utc,
        report_end_utc=candles[-1].open_time_utc + timedelta(hours=1),
        execution_rules=rules,
    )
    assert not result.fills and result.blocked_signals
    assert result.metrics.ending_equity == D(250)


def test_trial_market_cap_blocks_buy_without_any_exchange_submit(tmp_path):
    c, exchange = trial(tmp_path)
    c.rules_provider = lambda: dict.fromkeys(SYMBOLS, ExecutionRules(market_max_qty=D(".1")))
    arm(c)
    c.advance(universe(), now=NOW, healthy=True)
    report = c.advance(universe(), now=NOW, healthy=True)
    assert not exchange.submits
    assert report["state"] == "FAILED" and "MAX_QTY" in report["reason"]


def test_legacy_unknown_limits_block_trial_until_public_refresh(tmp_path):
    c, exchange = trial(tmp_path)
    c.rules_provider = lambda: dict.fromkeys(SYMBOLS, ExecutionRules(market_limits_known=False))
    arm(c)
    c.advance(universe(), now=NOW, healthy=True)
    report = c.advance(universe(), now=NOW, healthy=True)
    assert not exchange.submits
    assert report["reason"] == "MARKET_FILTERS_REFRESH_REQUIRED"
    assert report["state"] == "ENTRY_PENDING"


def test_missing_trial_symbol_limits_block_until_public_refresh(tmp_path):
    c, exchange = trial(tmp_path)
    c.rules_provider = lambda: {}
    arm(c)
    c.advance(universe(), now=NOW, healthy=True)
    report = c.advance(universe(), now=NOW, healthy=True)
    assert not exchange.submits
    assert report["reason"] == "MARKET_FILTERS_REFRESH_REQUIRED"
    assert report["state"] == "ENTRY_PENDING"


def test_legacy_unknown_limits_block_live_before_post(tmp_path):
    c, exchange, account, _settings = controller(tmp_path)
    enable_now(c, account, live_universe(LIVE_NOW - timedelta(hours=1)))
    c.rules = lambda: dict.fromkeys(SYMBOLS, ExecutionRules(market_limits_known=False))
    points = live_universe(LIVE_NOW, enter=("BTCUSDC",))
    for _ in range(4):
        c.advance(points, now=LIVE_NOW, healthy=True)
    assert not exchange.submits


def test_trial_oversized_sell_keeps_owned_quantity_and_never_calls_exchange(tmp_path):
    c, exchange = trial(tmp_path)
    arm(c)
    open_position(c)
    c.rules_provider = lambda: dict.fromkeys(SYMBOLS, ExecutionRules(market_max_qty=D(".1")))
    later = NOW + timedelta(hours=1)
    points = universe(later, buy_symbol=None, sell_symbol="SOLUSDC")
    c.advance(points, now=later, healthy=True)
    report = c.advance(points, now=later, healthy=True)
    assert len(exchange.submits) == 1
    assert report["state"] == "NEEDS_REVIEW" and D(report["owned_quantity"]) == D(".5")


def test_trial_unknown_sell_query_is_not_blocked_by_a_later_filter_change(tmp_path):
    c, exchange = trial(tmp_path)
    arm(c)
    open_position(c)
    later = NOW + timedelta(hours=1)
    points = universe(later, buy_symbol=None, sell_symbol="SOLUSDC")
    c.advance(points, now=later, healthy=True)
    exchange.timeout = True
    assert c.advance(points, now=later, healthy=True)["reason"] == "ORDER_UNKNOWN"
    c.rules_provider = lambda: dict.fromkeys(SYMBOLS, ExecutionRules(market_max_qty=D(".1")))
    exchange.timeout = False
    assert c.advance(points, now=later, healthy=False)["state"] == "AWAITING_RECONCILIATION"
    assert len(exchange.submits) == 2


def test_live_market_maximum_is_checked_before_post(tmp_path):
    c, exchange, account, _settings = controller(tmp_path)
    enable_now(c, account, live_universe(LIVE_NOW - timedelta(hours=1)))
    c.rules = lambda: dict.fromkeys(SYMBOLS, ExecutionRules(market_max_qty=D(".1")))
    points = live_universe(LIVE_NOW, enter=("BTCUSDC",))
    c.advance(points, now=LIVE_NOW, healthy=True)
    c.advance(points, now=LIVE_NOW, healthy=True)
    assert not exchange.submits


def test_live_oversized_exit_keeps_position_and_never_sends_sell(tmp_path):
    c, exchange, account, _settings = controller(tmp_path)
    enable_now(c, account, live_universe(LIVE_NOW - timedelta(hours=1)))
    points = live_universe(LIVE_NOW, enter=("BTCUSDC",))
    for _ in range(4):
        c.advance(points, now=LIVE_NOW, healthy=True)
    assert len(exchange.submits) == 1
    owned_before = D(c._positions()["BTCUSDC"]["quantity"])
    c.rules = lambda: dict.fromkeys(SYMBOLS, ExecutionRules(market_max_qty=D(".1")))
    later = LIVE_NOW + timedelta(hours=1)
    result = c.advance(live_universe(later, exit_symbol="BTCUSDC"), now=later, healthy=True)
    assert len(exchange.submits) == 1
    assert D(c._positions()["BTCUSDC"]["quantity"]) == owned_before
    assert result["state"] != "LIVE_ENABLED"


def test_paper_oversized_exit_keeps_position_and_never_books_as_dust(tmp_path):
    path = str(tmp_path / "paper-cap.sqlite3")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    initialize_paper_at_latest(path, _mapping(start), at=start)
    entry = start + timedelta(hours=1)
    points = _mapping(entry)
    points[SYMBOLS[0]] = (_point(SYMBOLS[0], entry, flip_up=True),)
    process_paper_fixture(path, points, _rules())
    with PaperStore(path) as store:
        before = store.load_positions()
        dust = store.load_dust()
        cash = store.load_account().cash_usdc
    assert before
    exit_at = entry + timedelta(hours=1)
    points = _mapping(exit_at)
    points[SYMBOLS[0]] = (_point(SYMBOLS[0], exit_at, flip_down=True),)
    rules = {s: replace(r, market_max_qty=D(".1")) for s, r in _rules().items()}
    events = process_paper_fixture(path, points, rules)
    assert any(e.reason == "EXIT_FILTER_MARKET_LOT_SIZE_MAX_QTY" for e in events)
    with PaperStore(path) as store:
        assert store.load_positions()[0].quantity == before[0].quantity
        assert store.load_dust() == dust
        assert store.load_account().cash_usdc == cash


def test_isolated_profitable_exit_above_maximum_is_blocked_without_fake_sale():
    candles = deterministic_candles("ETHUSDC", 1200, 1)
    result = run_single_backtest(
        symbol="ETHUSDC",
        candles=candles,
        report_start_utc=candles[400].open_time_utc,
        report_end_utc=candles[-1].open_time_utc + timedelta(hours=1),
        execution_rules=ExecutionRules(max_notional=D(250)),
    )
    assert any("EXIT_FILTER_NOTIONAL_MAX" in reason for reason in result.blocked_signals)
    assert all(fill.quote_value <= D(250) for fill in result.fills)


@pytest.mark.parametrize("upper_cap", [False, True])
def test_native_and_paper_share_market_grid_and_maximums(tmp_path, upper_cap):
    strategy = replace(
        V2_RESEARCH_STRATEGY,
        parameters=replace(V2_RESEARCH_STRATEGY.parameters, band_multiplier=0.8),
    )
    candles = {s: deterministic_candles(s, 900, index) for index, s in enumerate(SYMBOLS)}
    points = {
        s: tuple(
            evaluate_batch(
                s,
                candles[s],
                parameters=strategy.parameters,
                semantics=strategy.semantics,
                strategy_version=strategy.version,
            )
        )
        for s in SYMBOLS
    }
    rule = ExecutionRules(
        step_size=D(".02"),
        market_step_size=D(".03"),
        max_qty=D(100),
        market_max_qty=D(50),
        max_notional=D(100) if upper_cap else D(10000),
    )
    rules = dict.fromkeys(SYMBOLS, rule)
    start = candles[SYMBOLS[0]][400].open_time_utc
    end = candles[SYMBOLS[0]][-1].open_time_utc + timedelta(hours=1)
    native = run_shared_portfolio_backtest(
        candles_by_symbol=candles,
        report_start_utc=start,
        report_end_utc=end,
        execution_rules=rules,
        strategy_parameters=strategy.parameters,
        strategy_semantics=strategy.semantics,
        strategy_version=strategy.version,
        slot_allocation=strategy.slot_allocation,
    )
    path = str(tmp_path / "paper.sqlite3")
    initialize_paper_at_latest(
        path,
        {s: p[:400] for s, p in points.items()},
        at=start,
        strategy_key=strategy.key,
        strategy_version=strategy.version,
        starting_cash_usdc=D(250),
    )
    events = process_new_closed_points(
        path,
        points,
        rules,
        strategy_key=strategy.key,
        strategy_version=strategy.version,
        execution_candles_by_symbol=candles,
    )
    paper_fills = [e for e in events if e.status == "FILLED"]
    assert [(e.signal_id, e.base_quantity) for e in paper_fills] == [
        (f.signal_id, f.base_quantity) for f in native.fills
    ]
    if upper_cap:
        assert not paper_fills and native.blocked_signals
        with PaperStore(path) as store:
            assert store.load_account().cash_usdc == D(250)
    else:
        assert paper_fills
        assert all(
            f.base_quantity % D(".06") == 0 for f in native.fills if f.action.value == "EXIT_LONG"
        )
