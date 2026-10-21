"""Offline durable acceptance: actual adapter/fill/reconciliation path, fake exchange only."""

import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from hixton.domain.versions import strategy_definition
from hixton.live.acceptance import acceptance_status
from hixton.live.credentials import BinanceCredentials
from hixton.live.exchange import BinanceSpotExchange
from hixton.live.monitoring import build_execution_report
from hixton.live.orders import OrderJournal, TrialOrderExecutor
from hixton.live.preparation import LivePreparation
from hixton.live.reconciliation import TrialReconciler
from hixton.live.runtime import TrialRuntime
from hixton.live.trial import SignalTrial
from tests.test_live_preparation import KEY, SECRET, MemoryVault
from tests.test_live_reconciliation_runtime import SpotFixture, history
from tests.test_live_trial import NOW

ACCOUNT = BinanceCredentials(KEY, SECRET).fingerprint


def completed_trial(path, monkeypatch):
    clock = [NOW]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0].astimezone(tz or UTC)

    monkeypatch.setattr("hixton.live.orders.datetime", Clock)
    monkeypatch.setattr("hixton.live.trial.datetime", Clock)
    journal = OrderJournal(path)
    fixture = SpotFixture()
    exchange = BinanceSpotExchange(fixture, account_fingerprint=ACCOUNT, quote_asset="USDC")
    reconciler = TrialReconciler(journal)
    controller = SignalTrial(
        journal, TrialOrderExecutor(journal, exchange, lambda _: True),
        strategy_definition("v6"), lambda: True, execution_source_sha256="original-source",
        allocator_version="original-allocator",
    )
    def snapshot():
        return replace(fixture.snapshot(clock[0]), account=ACCOUNT)

    baseline_at = NOW - timedelta(seconds=3)
    reconciler.capture(replace(snapshot(), observed_at=baseline_at), now=baseline_at)
    controller.arm(str(uuid4()), ACCOUNT, now=NOW - timedelta(seconds=2), notional=Decimal(50))
    runtime = TrialRuntime(controller, reconciler, snapshot, clock=lambda: clock[0])
    points = history(NOW, "SOLUSDC", True)
    assert runtime.tick(
        points, now=NOW, healthy=True, entries_allowed=True
    )["state"] == "ENTRY_PENDING"
    assert runtime.tick(points, now=NOW, healthy=True, entries_allowed=True)["state"] == "OPEN"
    clock[0] += timedelta(hours=1)
    points = history(clock[0], "SOLUSDC", False)
    assert runtime.tick(
        points, now=clock[0], healthy=True, entries_allowed=True
    )["state"] == "EXIT_PENDING"
    assert runtime.tick(
        points, now=clock[0], healthy=True, entries_allowed=True
    )["state"] == "COMPLETED"
    return controller, fixture


def read_status(controller, account=ACCOUNT):
    with controller.journal._connect() as connection:
        connection.execute("BEGIN")
        return acceptance_status(connection, account)


def test_completed_proof_survives_restart_and_other_source_release_without_enabling(
    tmp_path, monkeypatch,
):
    controller, fixture = completed_trial(tmp_path / "live.sqlite3", monkeypatch)
    before = read_status(controller)
    assert before["eligible"] is True
    vault = MemoryVault()
    service = LivePreparation(
        controller.journal.path, vault, execution_source_sha256="new-ui-source"
    )
    service.credentials.save(BinanceCredentials(KEY, SECRET))
    service.connect_runtime(
        strategy_definition("v8r"), settings_provider=lambda: (Decimal(250), False),
        rules_provider=lambda: {},
    )
    assert service.trial_acceptance() == before
    assert service._trial_covers_current_runtime(service.trial.report())
    assert service.live.report()["state"] == "LIVE_DISABLED"
    assert service.trial.report()["execution_identity"]["source_matches_current"] is False
    assert service.trial.report()["strategy"] == controller.report()["strategy"]
    assert len([c for c in fixture.calls if c[0] == "POST"]) == 2
    service.source_is_current = lambda: False
    assert service.trial_acceptance()["eligible"] is True  # Historical fact remains.
    assert not service._trial_covers_current_runtime(service.trial.report())


def test_explicit_retest_revokes_old_certificate_in_archive_transaction(tmp_path, monkeypatch):
    controller, _ = completed_trial(tmp_path / "live.sqlite3", monkeypatch)
    old_id = controller.archive_completed()
    assert read_status(controller)["eligible"] is False
    controller.arm(str(uuid4()), ACCOUNT, now=NOW + timedelta(hours=2), notional=Decimal(50))
    assert read_status(controller)["state"] == "RETEST_REQUIRED"
    controller.disable_entries()
    assert read_status(controller)["eligible"] is False
    with controller.journal._connect() as connection:
        assert connection.execute("SELECT trial_id FROM trial_archives").fetchone()[0] == old_id
        assert connection.execute("SELECT COUNT(*) FROM trial_acceptance").fetchone()[0] == 0
    assert controller.prepare_retry()
    assert read_status(controller)["eligible"] is False


def test_replacement_key_does_not_inherit_the_test(tmp_path, monkeypatch):
    controller, _ = completed_trial(tmp_path / "live.sqlite3", monkeypatch)
    assert read_status(controller, "another-key")["state"] == "ACCOUNT_MISMATCH"
    assert read_status(controller, None)["eligible"] is False
    assert read_status(controller)["eligible"] is True


@pytest.mark.parametrize("corruption", [
    "DELETE FROM trial_fills WHERE trade_id=(SELECT MIN(trade_id) FROM trial_fills)",
    "UPDATE trial_fills SET account='foreign'",
    "UPDATE trial_fills SET quantity='NaN'",
    "UPDATE trial_fills SET quote_quantity='0'",
    "UPDATE trial_intents SET state='UNKNOWN' WHERE side='BUY'",
    "UPDATE trial_intents SET client_id='wrong' WHERE side='SELL'",
    "UPDATE signal_trial SET residual_quantity='0.01'",
    "UPDATE trial_account_baseline SET account='foreign'",
    "UPDATE trial_account_baseline SET balances_json='[]'",
    "UPDATE trial_account_baseline SET balances_json='{\"USDC\":\"NaN\"}'",
    "UPDATE trial_account_baseline SET observed_at='invalid'",
    "DELETE FROM trial_order_audit WHERE action='BALANCES_MATCH'",
    "UPDATE signal_trial SET entry_signal_json='{}'",
    "UPDATE signal_trial SET entry_signal_json='[]'",
    "UPDATE signal_trial SET strategy_json='[]'",
    "DELETE FROM trial_order_audit WHERE action='ENTRY_RESERVED'",
    "UPDATE signal_trial SET completed_at='not-a-clock'",
    "UPDATE trial_acceptance SET evidence_sha256='forged'",
])
def test_incomplete_or_changed_evidence_is_rejected_without_status_writes(
    tmp_path, monkeypatch, corruption,
):
    controller, _ = completed_trial(tmp_path / "live.sqlite3", monkeypatch)
    with controller.journal._connect() as connection:
        connection.execute(corruption)
    before = controller.journal.path.read_bytes()
    assert read_status(controller)["eligible"] is False
    assert controller.journal.path.read_bytes() == before


@pytest.mark.parametrize("late_or_manual", ["late-buy", "late-sell", "manual", "unreconciled"])
def test_startup_migration_never_accepts_bad_legacy_completion(
    tmp_path, monkeypatch, late_or_manual,
):
    controller, _ = completed_trial(tmp_path / "live.sqlite3", monkeypatch)
    with controller.journal._connect() as connection:
        connection.execute("DELETE FROM trial_acceptance")
        if late_or_manual.startswith("late"):
            side = "BUY" if late_or_manual == "late-buy" else "SELL"
            connection.execute(
                "UPDATE trial_order_audit SET at_utc=? WHERE action='SUBMITTING' AND intent_id="
                "(SELECT intent_id FROM trial_intents WHERE side=?)",
                ((NOW + timedelta(hours=1, minutes=10)).isoformat(), side),
            )
        elif late_or_manual == "manual":
            connection.execute(
                "UPDATE signal_trial SET entry_signal_json=replace(entry_signal_json,"
                "'HIXTON_ENTER_LONG','MANUAL_OPERATOR_TEST')"
            )
        else:
            connection.execute("DELETE FROM trial_order_audit WHERE action='TRIAL_COMPLETED'")
    SignalTrial(controller.journal, controller.executor, controller.strategy, lambda: True)
    assert read_status(controller)["eligible"] is False


def test_startup_migrates_genuine_legacy_ledger_once_and_status_does_not(tmp_path, monkeypatch):
    controller, _ = completed_trial(tmp_path / "live.sqlite3", monkeypatch)
    report = controller.report()
    with controller.journal._connect() as connection:
        connection.execute("DELETE FROM trial_acceptance")
    assert read_status(controller)["eligible"] is False
    SignalTrial(controller.journal, controller.executor, controller.strategy, lambda: True)
    assert read_status(controller)["eligible"] is True
    assert controller.report() == report  # Never rewrite the old source or strategy.
    with sqlite3.connect(controller.journal.path) as writer:
        writer.execute("BEGIN IMMEDIATE")
        assert read_status(controller)["eligible"] is True
        writer.rollback()


def test_successful_explicit_second_roundtrip_grants_new_durable_certificate(tmp_path, monkeypatch):
    path = tmp_path / "live.sqlite3"
    first, _ = completed_trial(path, monkeypatch)
    old_id = first.archive_completed()
    assert not read_status(first)["eligible"]
    second, _ = completed_trial(path, monkeypatch)
    assert read_status(second)["eligible"]
    assert read_status(second)["trial_id"] != old_id


def test_diagnostic_report_keeps_original_identity_without_false_source_failure(
    tmp_path, monkeypatch,
):
    controller, _ = completed_trial(tmp_path / "live.sqlite3", monkeypatch)
    report = build_execution_report(
        controller.journal.path, tmp_path / "absent-paper.sqlite3",
        application_version="new-app", execution_source_sha256="new-source",
        strategy_version=controller.strategy.version, allocator_version="new-allocator",
    )
    assert report["trial"]["technical_execution_acceptance"]["eligible"] is True
    assert report["trial"]["identity_matches_current"]["source"] is False
    assert report["trial"]["frozen_identity"]["execution_source_sha256"] == "original-source"
    assert "TRIAL_EXECUTION_SOURCE_STALE" not in {i["code"] for i in report["incidents"]}
