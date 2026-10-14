"""Key-free mechanics tests for the isolated concentration research model."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN
from decimal import Decimal as D
from types import SimpleNamespace

import pytest
from concentration_portfolio_20261013 import run_shared_portfolio_backtest
from concentration_research_support_20261013 import ConcentrationPolicy, trim_positions

from hixton.backtest.models import CURRENT_COSTS, ExecutionRules, Fill
from hixton.domain.models import Candle, SignalAction, StrategyParameters
from hixton.domain.strategy import HixtonStrategy
from hixton.domain.trade_policy import TradePolicy
from hixton.domain.versions import strategy_definition
from tests.test_paper_engine import _point

NOW = datetime(2026, 10, 13, 10, tzinfo=UTC)


def trim_fixture(*, next_open=100, small=False, minimum=5, closed=True):
    point = _point("BTCUSDC", NOW - timedelta(milliseconds=1), flip_up=True)
    point = replace(
        point,
        strategy_version=strategy_definition("v8r").version,
        candle=replace(point.candle, close=100.0, closed=closed),
    )
    signal = HixtonStrategy.signal_for(point, is_long=False)
    qty = D(1) if small else D(10)
    basis = qty * 100
    entry = Fill(
        signal.signal_id,
        SignalAction.ENTER_LONG,
        NOW - timedelta(hours=1),
        D(100),
        D(100),
        qty,
        basis,
        D(1),
        D(0),
    )
    pos = SimpleNamespace(
        signal=signal, fill=entry, quantity=qty, cost_basis=basis, slots=2, allocation_units=20
    )
    next_candle = replace(
        point.candle,
        open_time_utc=NOW,
        close_time_utc=NOW + timedelta(hours=1) - timedelta(milliseconds=1),
        open=float(next_open),
        high=float(next_open) * 1.02,
        low=float(next_open) * 0.98,
        close=float(next_open),
    )
    signals = []
    fills = []
    trades = []
    audit = []
    cash = trim_positions(
        policy=ConcentrationPolicy(D(0)),
        positions={"BTCUSDC": pos},
        previous_points={"BTCUSDC": point},
        candles={"BTCUSDC": next_candle},
        closed_equity=D(1000),
        open_time=NOW,
        costs=CURRENT_COSTS,
        rules={
            "BTCUSDC": ExecutionRules(step_size=D(".01"), min_qty=D(".01"), min_notional=D(minimum))
        },
        signals=signals,
        fills=fills,
        trades=trades,
        round_down=lambda x, step: (x / step).to_integral_value(rounding=ROUND_DOWN) * step,
        audit=audit,
    )
    return pos, cash, fills, trades, audit


def test_partial_sale_preserves_total_basis_and_accounts_for_fees():
    pos, cash, fills, trades, audit = trim_fixture()
    assert pos.quantity == D("2.5") and pos.cost_basis == D(250)
    assert trades[0].entry_quote_spend + pos.cost_basis == D(1000)
    assert fills[0].base_quantity == D("7.5")
    assert cash == fills[0].quote_value - fills[0].fee_quote_equivalent
    assert audit[0]["remaining_quantity"] == "2.5"
    assert pos.allocation_units == 5 and pos.slots == 1


def test_quantity_is_decided_before_execution_price_is_known():
    low = trim_fixture(next_open=80)
    high = trim_fixture(next_open=200)
    assert low[0].quantity == high[0].quantity == D("2.5")
    assert low[2][0].base_quantity == high[2][0].base_quantity
    assert low[1] != high[1]


def test_small_owned_position_relabels_capacity_without_fictitious_sale():
    pos, cash, fills, trades, audit = trim_fixture(small=True)
    assert pos.quantity == 1 and pos.cost_basis == 100
    assert cash == 0 and not fills and not trades and not audit
    assert pos.allocation_units == 5


def test_exchange_minimum_never_creates_cash():
    pos, cash, fills, trades, _ = trim_fixture(minimum=10000)
    assert pos.quantity == 10 and pos.cost_basis == 1000
    assert cash == 0 and not fills and not trades


def test_provisional_decision_bar_is_refused():
    with pytest.raises(AssertionError):
        trim_fixture(closed=False)


@pytest.mark.parametrize(
    "rule", [ConcentrationPolicy(D(20000)), ConcentrationPolicy(D(20000), D(5))]
)
def test_trigger_uses_supplied_previous_equity_and_dd(rule):
    assert not rule.triggered(equity=D(19999), high_water=D(40000), previous_close=NOW)
    assert not rule.triggered(equity=D(30000), high_water=D(40000), previous_close=None)
    assert rule.triggered(equity=D(30000), high_water=D(40000), previous_close=NOW)


@pytest.mark.parametrize("slots", [0, 3, 7])
def test_invalid_position_counts_refused(slots):
    with pytest.raises(ValueError):
        ConcentrationPolicy(D(20000), slots=slots)


def universe():
    base = strategy_definition("v8r")
    uniform = StrategyParameters(
        vidya_length=2,
        momentum_length=2,
        smoothing_length=2,
        atr_length=2,
        band_multiplier=0.2,
        warmup_bars=400,
    )
    base = replace(
        base,
        paper_approved=False,
        coin_profiles=tuple(
            replace(p, parameters=uniform, trade_policy=TradePolicy()) for p in base.coin_profiles
        ),
    )
    start = datetime(2024, 1, 1, tzinfo=UTC)
    data = {}
    for sym in base.symbols:
        rows = []
        for j in range(500):
            price = 100.0 if j < 400 else 110 + (j - 400) * 0.1
            at = start + timedelta(hours=j)
            rows.append(
                Candle(
                    sym,
                    at,
                    at + timedelta(hours=1) - timedelta(milliseconds=1),
                    price,
                    price + 0.01,
                    price - 0.01,
                    price,
                    10.0,
                )
            )
        data[sym] = rows
    return base, data, start + timedelta(hours=400)


def replay(slots, hours):
    base, data, start = universe()
    audit = []
    r = run_shared_portfolio_backtest(
        candles_by_symbol=data,
        report_start_utc=start,
        report_end_utc=start + timedelta(hours=hours),
        starting_cash=D(30000),
        target_notional=D(15000),
        execution_rules={
            s: ExecutionRules(step_size=D(".001"), min_notional=D(5)) for s in base.symbols
        },
        strategy=base,
        costs=CURRENT_COSTS,
        reinvest_profits=True,
        autonomous_spot=True,
        research_policy=ConcentrationPolicy(D(0), slots=slots),
        research_audit=audit,
    )
    return r, audit, start


@pytest.mark.parametrize("slots", [4, 6])
def test_research_fills_are_distinct_coins_and_no_cash_is_reused(slots):
    r, audit, _ = replay(slots, 24)
    assert r.max_concurrent_positions == slots
    buys = [f for f in r.fills if f.action is SignalAction.ENTER_LONG]
    lookup = {s.signal_id: s.symbol for s in r.signals}
    assert len(buys) == slots and len({lookup[f.signal_id] for f in buys}) == slots
    assert all(D(x["cash"]) >= 0 for x in audit)
    assert all(len(x["positions"]) <= slots for x in audit)


def test_future_bars_do_not_change_prior_decisions_or_fills():
    short, sa, start = replay(6, 24)
    long, la, _ = replay(6, 48)
    cutoff = start + timedelta(hours=24)
    assert short.equity_curve == tuple(e for e in long.equity_curve if e.time_utc < cutoff)
    assert short.fills == tuple(f for f in long.fills if f.fill_time_utc < cutoff)
    assert sa == la[: len(sa)]
