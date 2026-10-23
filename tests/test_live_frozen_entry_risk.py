"""Persistent pre-exit risk evidence fails closed without obstructing lookups."""

import json
from datetime import timedelta

from hixton.live.production import LivePortfolioController
from tests.test_live_diversification import setup
from tests.test_weighted_tranche import history


def risk_row(c, at):
    with c.journal._connect() as connection:
        row = connection.execute(
            "SELECT payload_json FROM live_entry_risk_decisions "
            "WHERE bar_close_utc=? AND strategy_version=?",
            (at.isoformat(), c.strategy.version),
        ).fetchone()
    return json.loads(row[0]) if row else None


def group(at):
    return {symbol: values[-1] for symbol, values in history(at).items()}


def test_failed_risk_insert_rolls_back_utc_day_origin_and_blocks_dispatch(tmp_path):
    c, exchange, _account, at = setup(tmp_path, "1000")
    before = c._control()["day_start_date"]
    with c.journal._connect() as connection:
        connection.execute(
            "CREATE TRIGGER fail_risk BEFORE INSERT ON live_entry_risk_decisions "
            "BEGIN SELECT RAISE(ABORT,'offline storage failure'); END"
        )
    tomorrow = at + timedelta(days=1)
    assert c._freeze_entry_risk(tomorrow, group(tomorrow)) is None
    assert c._control()["day_start_date"] == before
    assert c.report()["state"] == "NEEDS_REVIEW"
    assert risk_row(c, tomorrow) is None and not exchange.submits


def test_pre_exit_evidence_is_never_invented_after_boundary_execution(tmp_path):
    c, exchange, _account, at = setup(tmp_path, "1000")
    with c.journal._connect() as connection:
        connection.execute(
            "INSERT INTO live_events VALUES(?,?,?,?,?,?,?,?)",
            (
                "offline-executed-exit",
                at.isoformat(),
                "BTCUSDC",
                "EXIT_LONG",
                "FILLED",
                None,
                None,
                "{}",
            ),
        )
    assert c._freeze_entry_risk(at, group(at)) is None
    assert risk_row(c, at) is None and not exchange.submits
    assert c.report()["reason"] == "PRE_EXIT_RISK_FREEZE_REQUIRED"


def test_restart_reads_the_original_pre_exit_pause_without_new_snapshot(tmp_path):
    c, _exchange, _account, at = setup(tmp_path, "1000")
    with c.journal._connect() as connection:
        connection.execute("UPDATE live_control SET day_start_equity='1100'")
    assert c._freeze_entry_risk(at, group(at)) is True
    original = risk_row(c, at)

    def no_new_snapshot():
        raise AssertionError("Frozen decision must never be recalculated after a restart")

    again = LivePortfolioController(
        c.database,
        c.journal,
        c.executor,
        c.reconciler,
        no_new_snapshot,
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
    assert again._freeze_entry_risk(at, group(at)) is True
    assert risk_row(again, at) == original


def test_pending_created_order_requires_its_original_risk_record(tmp_path):
    c, exchange, _account, at = setup(tmp_path, "1000")
    points = history(at, entries=("BTCUSDC",))
    c.market_points = lambda: points
    c.advance(points, now=at, healthy=True)
    assert c._pending() is not None and risk_row(c, at) is not None
    with c.journal._connect() as connection:
        connection.execute("DELETE FROM live_entry_risk_decisions")
    report = c.advance(points, now=at, healthy=True)
    assert not exchange.submits
    assert report["state"] == "NEEDS_REVIEW"
    assert report["reason"] == "PRE_EXIT_RISK_FREEZE_REQUIRED"


def test_corrupted_pending_risk_identity_fails_closed_instead_of_dispatch(tmp_path):
    c, exchange, _account, at = setup(tmp_path, "1000")
    points = history(at, entries=("BTCUSDC",))
    c.market_points = lambda: points
    c.advance(points, now=at, healthy=True)
    proof = risk_row(c, at)
    proof["account"] = "foreign-offline-identity"
    with c.journal._connect() as connection:
        connection.execute(
            "UPDATE live_entry_risk_decisions SET payload_json=?", (json.dumps(proof),)
        )
    result = c.advance(points, now=at, healthy=True)
    assert not exchange.submits and result["state"] == "NEEDS_REVIEW"
