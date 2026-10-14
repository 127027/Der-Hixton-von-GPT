"""Invented future operational faults; current product, fake exchange, no network.

These scenarios are independent of invented price-return projections. Orders go
only to in-memory exchanges and journals under pytest's temporary directories.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path
from uuid import uuid4

import pytest

from hixton.backtest.models import ExecutionRules
from hixton.backtest.reporting import source_fingerprint
from hixton.domain.versions import strategy_definition
from hixton.live.exchange import ExchangeRequestError
from hixton.live.orders import ExchangeOrder, OrderJournal, TrialOrderExecutor
from hixton.live.production import LivePortfolioController
from hixton.live.trial import SignalTrial
from tests.test_live_diversification import drain, setup
from tests.test_live_trial import Exchange as TrialExchange
from tests.test_weighted_tranche import history

REPORT = (
    Path(__file__).resolve().parents[1] / "research/future-scenarios-20261014/technical-report.json"
)


def record(name, expected, observed, passed, limitation=None):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report = (
        json.loads(REPORT.read_text(encoding="utf-8"))
        if REPORT.exists()
        else {
            "method": "offline current controllers, synthetic indicators, fake exchange",
            "no_real_orders": True,
            "no_credentials": True,
            "strategy_version": strategy_definition("v8r").version,
            "scenarios": {},
            "limitations": [
                "No forecast of the next twenty years; operational fault experiments only.",
                "Fake fills do not model actual liquidity, price impact or exchange availability.",
                "Stops use finalized one-hour bars; no exchange-hosted guaranteed stop exists.",
                "During process outages execution stops and losses can continue.",
                "Synthetic signals exercise execution safety, not indicator profit.",
            ],
        }
    )
    report["scenarios"][name] = {
        "expected": expected,
        "observed": observed,
        "passed": passed,
        "limitation": limitation,
    }
    report["updated_at_utc"] = datetime.now(UTC).isoformat()
    report["execution_source_sha256"] = source_fingerprint()
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def current_trial(tmp_path):
    strategy = strategy_definition("v8r")
    journal = OrderJournal(tmp_path / "trial.sqlite3")
    exchange = TrialExchange()
    rules = {
        s: ExecutionRules(step_size=D(".000001"), min_qty=D(".000001"), min_notional=D(5))
        for s in strategy.symbols
    }
    c = SignalTrial(
        journal,
        TrialOrderExecutor(journal, exchange, lambda _: True),
        strategy,
        lambda: True,
        lambda: rules,
        execution_source_sha256="offline-current",
        allocator_version=strategy.allocator_version,
        autonomous_spot=lambda: True,
    )
    at = datetime.now(UTC).replace(second=0, microsecond=0)
    c.arm(str(uuid4()), "fake-account", now=at - timedelta(seconds=5), notional=D(50))
    return c, exchange, at


def restart(c):
    return LivePortfolioController(
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


@pytest.mark.parametrize("kind", ["unhealthy", "open_bar", "incomplete", "expired"])
@pytest.mark.parametrize("mode", ["trial", "normal_live"])
def test_bad_signal_never_buys(tmp_path, kind, mode):
    if mode == "trial":
        c, exchange, at = current_trial(tmp_path)
    else:
        c, exchange, _, at = setup(tmp_path, "1100")
    points = history(at, entries=("BTCUSDC",))
    if kind == "open_bar":
        points["BTCUSDC"] = tuple(
            replace(p, candle=replace(p.candle, closed=False)) for p in points["BTCUSDC"]
        )
    elif kind == "incomplete":
        del points["ETHUSDC"]
    if mode == "normal_live":
        c.market_points = lambda: points
    now = at + timedelta(seconds=91) if kind == "expired" else at
    for _ in range(4):
        c.advance(points, now=now, healthy=kind != "unhealthy")
    observed = {"submitted": len(exchange.submits), "state": c.report()["state"]}
    record(f"{mode}_{kind}", "Zero fake BUY submissions", observed, not exchange.submits)
    assert not exchange.submits


@pytest.mark.parametrize("mode", ["trial", "normal_live"])
def test_health_turns_bad_after_buy_reservation(tmp_path, mode):
    if mode == "trial":
        c, exchange, at = current_trial(tmp_path)
    else:
        c, exchange, _, at = setup(tmp_path, "1100")
    points = history(at, entries=("BTCUSDC",))
    if mode == "normal_live":
        c.market_points = lambda: points
    c.advance(points, now=at, healthy=True)  # persist intent, no order yet
    assert not exchange.submits
    c.advance(points, now=at + timedelta(seconds=1), healthy=False)
    observed = {"submitted": len(exchange.submits), "state": c.report()["state"]}
    record(
        f"{mode}_health_degrades_after_reservation",
        "Zero BUY until health recovers",
        observed,
        not exchange.submits,
    )
    assert not exchange.submits, "A reserved BUY must not bypass current unhealthy runtime"


@pytest.mark.parametrize("fault", ["revoked_credentials", "manual_account_change"])
def test_last_moment_account_fault_blocks_reserved_buy(tmp_path, fault):
    c, exchange, account, at = setup(tmp_path, "1100")
    points = history(at, entries=("BTCUSDC",))
    c.market_points = lambda: points
    c.advance(points, now=at, healthy=True)
    assert not exchange.submits
    if fault == "revoked_credentials":

        def unavailable():
            raise ExchangeRequestError(-2015, 400, definitely_rejected=True)

        c.snapshot = unavailable
    else:
        account.balances["USDC"] = (D(1099), D(0))
    c.advance(points, now=at, healthy=True)
    record(
        fault,
        "No BUY on failed fresh signed-account gate",
        {"submitted": len(exchange.submits), "state": c.report()["state"]},
        not exchange.submits,
    )
    assert not exchange.submits


def test_accepted_buy_reply_lost_then_process_restart_no_duplicate(tmp_path):
    c, exchange, account, at = setup(tmp_path, "1100")
    points = history(at, entries=("BTCUSDC",))
    c.market_points = lambda: points
    c.advance(points, now=at, healthy=True)
    exchange.timeout = True
    c.advance(points, now=at, healthy=True)
    assert len(exchange.submits) == 1
    restored = restart(c)
    exchange.timeout = False
    drain(restored, points, at)
    observed = {
        "submitted": len(exchange.submits),
        "owned_positions": len(restored._positions()),
        "account_base": str(account.balances["BTC"][0]),
        "unresolved": restored.journal.unresolved_ids(),
    }
    passed = (
        len(exchange.submits) == 1
        and len(restored._positions()) == 1
        and not restored.journal.unresolved_ids()
    )
    record(
        "lost_accepted_buy_reply_restart",
        "Query durable intent; one BUY, no duplicate",
        observed,
        passed,
    )
    assert passed


@pytest.mark.parametrize("fault", ["rejected", "partial"])
def test_exit_failure_never_claims_closed_or_reuses_capital(tmp_path, fault):
    c, exchange, account, at = setup(tmp_path, "1100")
    entry = history(at, entries=("BTCUSDC",))
    c.market_points = lambda: entry
    drain(c, entry, at)
    assert len(exchange.submits) == 1
    ordinary = exchange.submit

    def faulty_sell(intent):
        if intent.side == "BUY":
            return ordinary(intent)
        exchange.submits.append(intent)
        if fault == "rejected":
            raise ExchangeRequestError(-1013, 400, definitely_rejected=True)
        q = intent.base_quantity / 2
        from hixton.live.orders import ExchangeFill

        response = ExchangeOrder(
            intent.client_order_id,
            "faulty-sell",
            intent.symbol,
            "SELL",
            "CANCELED",
            q,
            q * D(105),
            (ExchangeFill("partial", q, D(105), D(0), "USDC", q * D(105)),),
        )
        exchange.orders[intent.client_order_id] = response
        account.apply(response)
        return response

    exchange.submit = faulty_sell
    later = at + timedelta(hours=1)
    exit_points = history(later, exit_symbol="BTCUSDC")
    c.market_points = lambda: exit_points
    drain(c, exit_points, later)
    subsequent = history(later + timedelta(hours=1), entries=("ETHUSDC",))
    c.market_points = lambda: subsequent
    drain(c, subsequent, later + timedelta(hours=1))
    observed = {
        "state": c.report()["state"],
        "owned_positions": len(c._positions()),
        "account_remaining": str(account.balances["BTC"][0]),
        "submits": len(exchange.submits),
    }
    passed = (
        c.report()["state"] == "NEEDS_REVIEW"
        and bool(c._positions())
        and account.balances["BTC"][0] > 0
        and len([i for i in exchange.submits if i.side == "BUY"]) == 1
    )
    record(
        f"sell_{fault}",
        "Remain unsettled; no false full-close, no new entry",
        observed,
        passed,
        "Partial SELL remains under review; journal can retain the pre-review quantity.",
    )
    assert passed


def test_outage_during_due_exit_catches_up_without_backdated_fill(tmp_path):
    c, exchange, at = current_trial(tmp_path)
    entry = history(at, entries=("BTCUSDC",))
    c.advance(entry, now=at, healthy=True)
    c.advance(entry, now=at, healthy=True)
    assert c.report()["state"] == "OPEN"
    missed_at = at + timedelta(hours=1)
    recovered_at = at + timedelta(hours=4)
    missed = history(missed_at, exit_symbol="BTCUSDC")["BTCUSDC"][-1]
    latest = history(recovered_at)["BTCUSDC"][-1]
    latest = replace(latest, candle=replace(latest.candle, close=80, low=79))
    recovered = {"BTCUSDC": (missed, latest)}
    # Four hours with no scheduler calls: no exchange-held stop exists.
    assert len(exchange.submits) == 1
    c.advance(recovered, now=recovered_at, healthy=True)
    c.advance(recovered, now=recovered_at, healthy=True)
    observed = {
        "sides": [i.side for i in exchange.submits],
        "sell_reference": str(exchange.submits[-1].reference_price),
        "missed_signal": c.report()["exit_signal"]["bar_close"],
        "state": c.report()["state"],
    }
    passed = observed["sides"] == ["BUY", "SELL"] and D(observed["sell_reference"]) == 80
    record(
        "process_outage_exit_due",
        "Exit obligation replayed at recovery reference, not earlier price",
        observed,
        passed,
        "Cannot sell while process offline; fake fill price deliberately not a liquidity model.",
    )
    assert passed


def test_new_minimum_quantity_after_delisting_warning_preserves_hold(tmp_path):
    c, exchange, _, at = setup(tmp_path, "1100")
    entry = history(at, entries=("BTCUSDC",))
    c.market_points = lambda: entry
    drain(c, entry, at)
    c.rules = lambda: {
        s: ExecutionRules(step_size=D(".000001"), min_qty=D(100), min_notional=D(5))
        for s in c.strategy.symbols
    }
    later = at + timedelta(hours=1)
    exits = history(later, exit_symbol="BTCUSDC")
    c.market_points = lambda: exits
    c.advance(exits, now=later, healthy=True)
    observed = {
        "state": c.report()["state"],
        "reason": c.report()["reason"],
        "submitted": len(exchange.submits),
        "owned_positions": len(c._positions()),
    }
    passed = (
        len(exchange.submits) == 1
        and bool(c._positions())
        and c.report()["state"] == "NEEDS_REVIEW"
    )
    record(
        "exchange_minimum_quantity_change",
        "Fail closed, keep owned hold, request review",
        observed,
        passed,
    )
    assert passed


@pytest.mark.parametrize("fault", ["unhealthy", "incomplete_universe"])
@pytest.mark.parametrize("recover_before_expiry", [True, False])
def test_reserved_buy_health_gate_recovers_or_expires(tmp_path, fault, recover_before_expiry):
    c, exchange, _, at = setup(tmp_path, "1100")
    points = history(at, entries=("BTCUSDC",))
    c.market_points = lambda: points
    c.advance(points, now=at, healthy=True)
    bad_points = dict(points)
    if fault == "incomplete_universe":
        del bad_points["ETHUSDC"]
    c.advance(bad_points, now=at + timedelta(seconds=1), healthy=fault != "unhealthy")
    assert not exchange.submits
    if recover_before_expiry:
        drain(c, points, at + timedelta(seconds=2))
        passed = len(exchange.submits) == 1 and bool(c._positions())
    else:
        c.advance(bad_points, now=at + timedelta(seconds=91), healthy=fault != "unhealthy")
        drain(c, points, at + timedelta(seconds=92))
        passed = not exchange.submits and not c._positions() and c._pending() is None
    observed = {
        "submitted": len(exchange.submits),
        "owned_positions": len(c._positions()),
        "pending": c._pending() is not None,
    }
    name = f"reserved_buy_{fault}_{'recovers' if recover_before_expiry else 'expires'}"
    record(
        name,
        "Pause CREATED BUY; resume once within 90s, otherwise expire without buying",
        observed,
        passed,
    )
    assert passed


def test_accepted_uncertain_buy_is_queried_while_runtime_unhealthy(tmp_path):
    c, exchange, _, at = setup(tmp_path, "1100")
    points = history(at, entries=("BTCUSDC",))
    c.market_points = lambda: points
    c.advance(points, now=at, healthy=True)
    exchange.timeout = True
    c.advance(points, now=at, healthy=True)
    assert len(exchange.submits) == 1 and c.journal.unresolved_ids()
    restored = restart(c)
    exchange.timeout = False
    for _ in range(3):
        restored.advance({}, now=at + timedelta(seconds=1), healthy=False)
    observed = {
        "submitted": len(exchange.submits),
        "owned_positions": len(restored._positions()),
        "unresolved": restored.journal.unresolved_ids(),
    }
    passed = (
        len(exchange.submits) == 1
        and bool(restored._positions())
        and not restored.journal.unresolved_ids()
    )
    record(
        "accepted_buy_unhealthy_reconciliation",
        "Query accepted BUY without duplicate, even when market health is down",
        observed,
        passed,
    )
    assert passed


def test_reserved_risk_reducing_sell_still_runs_while_runtime_unhealthy(tmp_path):
    c, exchange, account, at = setup(tmp_path, "1100")
    entry = history(at, entries=("BTCUSDC",))
    c.market_points = lambda: entry
    drain(c, entry, at)
    later = at + timedelta(hours=1)
    exits = history(later, exit_symbol="BTCUSDC")
    c.market_points = lambda: exits
    c.advance(exits, now=later, healthy=True)
    assert c._pending() is not None and len(exchange.submits) == 1
    c.advance({}, now=later + timedelta(seconds=1), healthy=False)
    observed = {
        "sides": [i.side for i in exchange.submits],
        "owned_positions": len(c._positions()),
        "remaining_base": str(account.balances["BTC"][0]),
    }
    passed = (
        observed["sides"] == ["BUY", "SELL"]
        and not c._positions()
        and account.balances["BTC"][0] == 0
    )
    record(
        "reserved_sell_unhealthy",
        "Preserve already valid risk-reducing SELL despite market degradation",
        observed,
        passed,
    )
    assert passed


def test_base_fee_and_step_dust_is_reported_without_selling_foreign_holdings(tmp_path):
    c, exchange, at = current_trial(tmp_path)
    rules = {
        s: ExecutionRules(step_size=D(".001"), min_qty=D(".001"), min_notional=D(5))
        for s in c.strategy.symbols
    }
    c.rules_provider = lambda: rules
    ordinary_submit = exchange.submit

    def buy_with_base_fee(intent):
        order = ordinary_submit(intent)
        if intent.side == "BUY":
            fee_fill = replace(order.fills[0], commission=D(".000123"), commission_asset="BTC")
            order = replace(order, fills=(fee_fill,))
            exchange.orders[intent.client_order_id] = order
        return order

    exchange.submit = buy_with_base_fee
    entry = history(at, entries=("BTCUSDC",))
    c.advance(entry, now=at, healthy=True)
    c.advance(entry, now=at, healthy=True)
    assert D(c.report()["owned_quantity"]) == D(".499877")
    later = at + timedelta(hours=1)
    exits = history(later, exit_symbol="BTCUSDC")
    c.advance(exits, now=later, healthy=True)
    c.advance(exits, now=later, healthy=True)
    observed = {
        "sell_quantity": str(exchange.submits[-1].base_quantity),
        "residual_quantity": c.report()["residual_quantity"],
        "state": c.report()["state"],
    }
    passed = (
        exchange.submits[-1].base_quantity == D(".499")
        and D(c.report()["residual_quantity"]) == D(".000877")
        and c.report()["state"] == "AWAITING_RECONCILIATION"
    )
    record(
        "base_fee_step_dust",
        "Sell only net owned rounded quantity; preserve and report sub-step dust",
        observed,
        passed,
        "Final completion still requires fresh account/order reconciliation.",
    )
    assert passed


@pytest.mark.parametrize(
    "fault",
    [
        "provisional",
        "invalid_ohlc",
        "untradable",
        "wrong_strategy",
        "misaligned",
        "stale",
        "future",
    ],
)
def test_reserved_buy_rechecks_current_finalized_universe(tmp_path, fault):
    c, exchange, _, at = setup(tmp_path, "1100")
    points = history(at, entries=("BTCUSDC",))
    c.market_points = lambda: points
    c.advance(points, now=at, healthy=True)
    assert not exchange.submits
    bad_points = dict(points)
    target = points["BTCUSDC"][-1]
    if fault == "provisional":
        target = replace(target, candle=replace(target.candle, closed=False))
    elif fault == "invalid_ohlc":
        target = replace(target, candle=replace(target.candle, low=101))
    elif fault == "untradable":
        target = replace(target, tradable=False)
    elif fault == "wrong_strategy":
        target = replace(target, strategy_version="unrelated-version")
    elif fault == "misaligned":
        target = replace(
            target,
            candle=replace(
                target.candle,
                open_time_utc=target.candle.open_time_utc - timedelta(minutes=1),
                close_time_utc=target.candle.close_time_utc - timedelta(minutes=1),
            ),
        )
    else:
        stamp = at + timedelta(hours=1) if fault == "future" else at - timedelta(hours=1)
        bad_points = history(stamp, entries=("BTCUSDC",))
        target = bad_points["BTCUSDC"][-1]
    bad_points["BTCUSDC"] = (*bad_points["BTCUSDC"][:-1], target)
    c.market_points = lambda: bad_points
    c.advance(bad_points, now=at + timedelta(seconds=1), healthy=True)
    observed = {
        "submitted": len(exchange.submits),
        "state": c.report()["state"],
        "latest_btc_bar": target.candle.close_time_utc.isoformat(),
    }
    record(
        f"reserved_buy_current_{fault}",
        "No CREATED BUY from invalid or noncurrent finalized universe",
        observed,
        not exchange.submits,
    )
    assert not exchange.submits
