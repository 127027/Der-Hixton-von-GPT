"""Offline diagnostics must distinguish ambiguous trial orders from normal Live."""

import json
from datetime import timedelta
from decimal import Decimal

import pytest

from hixton.live.monitoring import build_execution_report
from tests.test_live_preparation import client_for
from tests.test_live_trial import NOW, arm, trial, universe


@pytest.mark.parametrize("side", ["buy", "sell"])
def test_unknown_trial_order_is_error_even_with_normal_live_disabled(tmp_path, side):
    controller, exchange = trial(tmp_path)
    arm(controller)
    points = universe()
    controller.advance(points, now=NOW, healthy=True)
    at = NOW
    if side == "sell":
        controller.advance(points, now=NOW, healthy=True)
        at = NOW + timedelta(hours=1)
        points = universe(at, buy_symbol=None, sell_symbol="SOLUSDC")
        controller.advance(points, now=at, healthy=True)
    exchange.timeout = True
    controller.advance(points, now=at, healthy=True)
    report = build_execution_report(
        controller.journal.path,
        tmp_path / "absent-paper.sqlite3",
        application_version=controller.application_version,
        execution_source_sha256=controller.execution_source_sha256,
        strategy_version=controller.strategy.version,
        allocator_version=controller.allocator_version,
    )
    assert report["trial"][side]["state"] == "UNKNOWN"
    assert report["summary"]["status"] == "ERROR"
    assert report["summary"]["trial_unresolved_intents"] == 1
    assert len(report["trial"]["unresolved_intents"]) == 1
    assert report["summary"]["live_unresolved_intents"] == 0
    incident = next(i for i in report["incidents"] if i["code"] == "TRIAL_ORDER_UNRESOLVED")
    assert incident["severity"] == "ERROR"
    assert incident["intent_id"] == report["trial"]["unresolved_intents"][0]


def test_armed_waiting_trial_is_not_an_unresolved_binance_order(tmp_path):
    controller, _ = trial(tmp_path)
    arm(controller)
    report = build_execution_report(
        controller.journal.path,
        tmp_path / "absent-paper.sqlite3",
        application_version=controller.application_version,
        execution_source_sha256=controller.execution_source_sha256,
        strategy_version=controller.strategy.version,
        allocator_version=controller.allocator_version,
    )
    assert report["summary"]["status"] == "OK"
    assert report["summary"]["trial_unresolved_intents"] == 0


def test_locked_status_exposes_only_safe_order_codes_and_blocks_false_completed(tmp_path):
    client, _, service = client_for(tmp_path)

    class ContradictoryCompletedTrial:
        def report(self):
            return {
                "state": "COMPLETED",
                "has_unsettled": True,
                "symbol": "SOLUSDC",
                "reason": "ORDER_UNKNOWN",
                "strategy": service.live.strategy.config_payload(),
                "execution_identity": {
                    "source_matches_current": True,
                    "allocator_matches_current": True,
                    "frozen_application_version": service.application_version,
                },
                "buy": {"state": "UNKNOWN", "exchange_state": None,
                        "private_payload": "secret-query-string"},
                "account": "private-account-identity",
            }

    service.trial = ContradictoryCompletedTrial()
    public = client.get("/api/live/status").json()
    assert public["trial"]["reason"] == "ORDER_UNKNOWN"
    assert public["trial"]["symbol"] == "SOLUSDC"
    assert public["trial"]["buy"] == {"state": "UNKNOWN", "exchange_state": None}
    assert public["trial"]["has_unresolved_orders"] is True
    assert "secret-query-string" not in json.dumps(public)
    assert "private-account-identity" not in json.dumps(public)
    status = service.status(
        authenticated=True, soak_ready=True, healthy=True,
        max_capital=Decimal("1000"), emergency_stop=False,
    )
    assert status["ready"] is False
    assert status["order_dispatch_available"] is False
    assert any("Testorder ungeklärt" in blocker for blocker in status["blockers"])


def test_locked_status_does_not_echo_unbounded_transport_error(tmp_path):
    client, _, service = client_for(tmp_path)

    class FailedTrial:
        def report(self):
            return {"state": "NEEDS_REVIEW", "has_unsettled": True,
                    "reason": "https://example/?signature=secret"}

    service.trial = FailedTrial()
    public = client.get("/api/live/status")
    assert public.json()["trial"]["reason"] is None
    assert "signature=secret" not in public.text
