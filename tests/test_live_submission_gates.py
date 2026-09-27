"""Offline regression coverage for changes during the final order preflight."""

from datetime import timedelta

import pytest

from hixton.live.monitoring import build_execution_report
from tests.test_live_production import NOW as LIVE_NOW
from tests.test_live_production import controller, enable_now
from tests.test_live_production import universe as live_universe
from tests.test_live_trial import NOW, arm, trial, universe


@pytest.mark.parametrize("intent_exists", [False, True])
def test_patch_after_entry_reservation_never_submits(tmp_path, intent_exists):
    c, exchange = trial(tmp_path, source_sha256="before")
    arm(c)
    c.advance(universe(), now=NOW, healthy=True)
    if intent_exists:
        c.executor.pre_submit = lambda _: False
        c.advance(universe(), now=NOW, healthy=True)
    restarted, _ = trial(tmp_path, exchange, source_sha256="after")
    report = restarted.advance(universe(), now=NOW + timedelta(seconds=2), healthy=True)
    assert report["state"] == "CANCELED"
    assert report["reason"] == "EXECUTION_SOURCE_CHANGED_BEFORE_ORDER"
    assert not exchange.submits


@pytest.mark.parametrize("change", ["deadline", "source", "release"])
def test_trial_rechecks_gate_after_slow_preflight(tmp_path, monkeypatch, change):
    c, exchange = trial(tmp_path)
    arm(c)
    c.advance(universe(), now=NOW, healthy=True)
    elapsed = [100.0]
    monkeypatch.setattr("hixton.live.trial.time.monotonic", lambda: elapsed[0])

    def preflight(_):
        if change == "deadline":
            elapsed[0] += 2
        elif change == "source":
            c.source_is_current = lambda: False
        else:
            c.release_check = lambda: False
        return True

    c.executor.pre_submit = preflight
    report = c.advance(universe(), now=NOW + timedelta(seconds=89), healthy=True)
    assert not exchange.submits
    assert report["state"] != "OPEN"
    with c.journal._connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM trial_order_audit WHERE action='SUBMITTING'"
        ).fetchone()[0] == 0


def test_source_change_reconciles_uncertain_buy_and_preserves_owned_exit(tmp_path):
    c, exchange = trial(tmp_path)
    arm(c)
    c.advance(universe(), now=NOW, healthy=True)
    exchange.timeout = True
    c.advance(universe(), now=NOW, healthy=True)
    assert len(exchange.submits) == 1
    c.source_is_current = lambda: False
    exchange.timeout = False
    assert c.advance(universe(), now=NOW, healthy=False)["state"] == "OPEN"
    later = NOW + timedelta(hours=1)
    points = universe(later, buy_symbol=None, sell_symbol="SOLUSDC")
    c.advance(points, now=later, healthy=True)
    assert c.advance(points, now=later, healthy=True)["state"] == "AWAITING_RECONCILIATION"
    assert [intent.side for intent in exchange.submits] == ["BUY", "SELL"]


@pytest.mark.parametrize("change", ["deadline", "source", "emergency", "budget"])
def test_normal_live_rechecks_gate_after_preflight(tmp_path, monkeypatch, change):
    c, exchange, account, settings = controller(tmp_path)
    enable_now(c, account, live_universe(LIVE_NOW - timedelta(hours=1)))
    points = live_universe(LIVE_NOW, enter=("BTCUSDC",))
    c.advance(points, now=LIVE_NOW, healthy=True)
    elapsed = [100.0]
    monkeypatch.setattr("hixton.live.production.time.monotonic", lambda: elapsed[0])

    def preflight(_):
        if change == "deadline":
            elapsed[0] += 2
        elif change == "source":
            c.source_is_current = lambda: False
        elif change == "emergency":
            settings[1] = True
        else:
            settings[0] *= 2
        return True

    c.executor.pre_submit = preflight
    c.advance(points, now=LIVE_NOW + timedelta(seconds=89), healthy=True)
    assert not exchange.submits
    with c.journal._connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM live_order_audit WHERE action='SUBMITTING'"
        ).fetchone()[0] == 0


def test_execution_report_exposes_disk_source_change_without_keys(tmp_path):
    report = build_execution_report(
        tmp_path / "absent-live.sqlite3",
        tmp_path / "absent-paper.sqlite3",
        application_version="test",
        execution_source_sha256="running-source",
        strategy_version="test-strategy",
        allocator_version="test-allocator",
        source_is_current=False,
    )
    assert report["runtime_identity"]["source_matches_disk"] is False
    assert any(item["code"] == "RUNTIME_SOURCE_CHANGED" for item in report["incidents"])
    assert report["summary"]["error_count"] >= 1
