"""Never-used disabled binding upgrade; entirely fake exchange/account, no network."""

import json
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import pytest

from hixton.backtest.models import ExecutionRules
from hixton.domain.versions import V8_DIV32_PAPER_STRATEGY, strategy_definition
from hixton.live.idle_upgrade import _UNUSED_TABLES, upgrade_unused_live_binding
from hixton.live.production import (
    LiveBalanceReconciler,
    LiveOrderExecutor,
    LiveOrderJournal,
    LivePortfolioController,
)
from tests.test_live_production import Account, ApplyingExchange
from tests.test_paper_engine import _point


def _case(tmp_path):
    old, current = V8_DIV32_PAPER_STRATEGY, strategy_definition("v8r")
    journal = LiveOrderJournal(tmp_path / "live.sqlite3")
    account = Account()
    exchange = ApplyingExchange(account)
    holder = {}
    executor = LiveOrderExecutor(journal, exchange, lambda intent: holder["bot"].pre_submit(intent))
    now = datetime.now(UTC)

    def points(strategy):
        return {
            s: (replace(_point(s, now - timedelta(hours=1)), strategy_version=strategy.version),)
            for s in strategy.symbols
        }

    def make(strategy, *, source_current=True, credential_account="fake-account"):
        bot = LivePortfolioController(
            journal.path,
            journal,
            executor,
            LiveBalanceReconciler(journal),
            account.snapshot,
            lambda: (D("250"), False),
            lambda: {
                s: ExecutionRules(min_qty=D(".001"), min_notional=D("5")) for s in strategy.symbols
            },
            strategy,
            lambda: True,
            execution_source_sha256="new" if strategy is current else "old",
            source_is_current=lambda: source_current,
            account_fingerprint=lambda: credential_account,
        )
        holder["bot"] = bot
        return bot

    bot = make(old)
    snapshot = account.snapshot()
    bot.enable(snapshot.account, points(old), snapshot, now=snapshot.observed_at)
    bot.disable_entries()
    return make, current, account, exchange, journal, points


def test_unused_disabled_upgrade_does_not_activate_or_touch_acceptance(tmp_path):
    make, current, account, exchange, journal, points = _case(tmp_path)
    with journal._connect() as connection:
        before = dict(connection.execute("SELECT * FROM live_control").fetchone())
        checkpoints = list(connection.execute("SELECT * FROM live_checkpoints"))
        connection.execute("CREATE TABLE trial_acceptance(proof TEXT)")
        connection.execute("INSERT INTO trial_acceptance VALUES('immutable-original-proof')")
    bot = make(current)
    assert bot.report()["state"] == "LIVE_DISABLED"
    with journal._connect() as connection:
        control = dict(connection.execute("SELECT * FROM live_control").fetchone())
        audit = connection.execute("SELECT * FROM live_idle_upgrade_audit").fetchone()
        assert json.loads(audit["old_control_json"]) == before
        assert control["entries_enabled"] == 0
        assert json.loads(control["strategy_json"]) == current.config_payload()
        assert control["execution_source_sha256"] == "new"
        changed = {"strategy_json", "application_version", "execution_source_sha256"}
        for key in before.keys() - changed:
            assert control[key] == before[key]
        assert list(connection.execute("SELECT * FROM live_checkpoints")) == checkpoints
        assert connection.execute("SELECT proof FROM trial_acceptance").fetchone()[0] == (
            "immutable-original-proof"
        )
    make(current)  # Idempotent startup: one migration record, still no trading.
    with journal._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM live_idle_upgrade_audit").fetchone()[0] == 1
    assert not exchange.submits
    # Separate explicit enable with a fresh snapshot now succeeds, still without a BUY.
    snapshot = account.snapshot()
    bot.enable(snapshot.account, points(current), snapshot, now=snapshot.observed_at)
    assert bot.report()["state"] == "LIVE_ENABLED"
    assert not exchange.submits


@pytest.mark.parametrize("table", _UNUSED_TABLES)
def test_every_exposure_or_history_table_blocks_upgrade(tmp_path, table):
    _, current, _, exchange, journal, _ = _case(tmp_path)
    with journal._connect() as connection:
        # The helper must reject any row, including malformed/orphan historical
        # state. A minimal replacement isolates each table's independent guard.
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(f"DROP TABLE {table}")
        connection.execute(f"CREATE TABLE {table}(evidence TEXT)")
        connection.execute(f"INSERT INTO {table} VALUES('must-not-be-erased')")
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        assert not upgrade_unused_live_binding(
            connection,
            current,
            application_version="test",
            execution_source_sha256="new",
            source_is_current=True,
            current_account_fingerprint=lambda: "fake-account",
        )
        assert connection.execute(f"SELECT evidence FROM {table}").fetchone()[0] == (
            "must-not-be-erased"
        )
    assert not exchange.submits


@pytest.mark.parametrize(
    "problem",
    [
        "active",
        "review",
        "entries",
        "baseline_account",
        "no_baseline",
        "old_config",
        "corrupt_config",
        "future_strategy",
        "changed_disk",
        "unknown_credential",
        "different_credential",
    ],
)
def test_unsafe_or_unknown_binding_stays_frozen(tmp_path, problem):
    make, current, _, exchange, journal, _ = _case(tmp_path)
    with journal._connect() as connection:
        if problem == "active":
            connection.execute("UPDATE live_control SET state='LIVE_ENABLED',entries_enabled=1")
        elif problem == "review":
            connection.execute("UPDATE live_control SET state='NEEDS_REVIEW'")
        elif problem == "entries":
            connection.execute("UPDATE live_control SET entries_enabled=1")
        elif problem == "baseline_account":
            connection.execute("UPDATE live_account_baseline SET account='other-account'")
        elif problem == "no_baseline":
            connection.execute("DELETE FROM live_account_baseline")
        elif problem in {"old_config", "corrupt_config"}:
            value = "{" if problem == "corrupt_config" else json.dumps({"version": "unknown"})
            connection.execute("UPDATE live_control SET strategy_json=?", (value,))
        before = dict(connection.execute("SELECT * FROM live_control").fetchone())
    strategy = (
        replace(current, version="unreviewed-future") if problem == "future_strategy" else current
    )
    credential_account = (
        None
        if problem == "unknown_credential"
        else "other-account"
        if problem == "different_credential"
        else "fake-account"
    )
    make(strategy, source_current=problem != "changed_disk", credential_account=credential_account)
    with journal._connect() as connection:
        assert dict(connection.execute("SELECT * FROM live_control").fetchone()) == before
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='live_idle_upgrade_audit'"
            ).fetchone()
            is None
        )
    assert not exchange.submits


def test_migration_audit_and_binding_rollback_together(tmp_path):
    _, current, _, exchange, journal, _ = _case(tmp_path)
    with journal._connect() as connection:
        before = dict(connection.execute("SELECT * FROM live_control").fetchone())
        connection.execute(
            "CREATE TRIGGER reject_upgrade BEFORE UPDATE OF strategy_json ON live_control "
            "BEGIN SELECT RAISE(ABORT,'simulated-storage-failure'); END"
        )
    with (
        pytest.raises(sqlite3.IntegrityError, match="simulated-storage-failure"),
        journal._connect() as connection,
    ):
        connection.execute("BEGIN IMMEDIATE")
        upgrade_unused_live_binding(
            connection,
            current,
            application_version="test",
            execution_source_sha256="new",
            source_is_current=True,
            current_account_fingerprint=lambda: "fake-account",
        )
    with journal._connect() as connection:
        assert dict(connection.execute("SELECT * FROM live_control").fetchone()) == before
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='live_idle_upgrade_audit'"
            ).fetchone()
            is None
        )
    assert not exchange.submits


@pytest.mark.parametrize("mismatch", ["account", "strategy"])
def test_refused_activation_never_refreshes_the_old_baseline(tmp_path, mismatch):
    make, current, account, exchange, journal, points = _case(tmp_path)
    strategy = V8_DIV32_PAPER_STRATEGY if mismatch == "account" else current
    bot = make(strategy, credential_account=None)
    with journal._connect() as connection:
        baseline = [dict(r) for r in connection.execute("SELECT * FROM live_account_baseline")]
    snapshot = account.snapshot()
    snapshot = replace(
        snapshot,
        account="other-account" if mismatch == "account" else snapshot.account,
        balances={"USDC": (D("500"), D("0"))},
    )
    with pytest.raises(RuntimeError, match="cannot change in place"):
        bot.enable(snapshot.account, points(strategy), snapshot, now=snapshot.observed_at)
    with journal._connect() as connection:
        assert [
            dict(r) for r in connection.execute("SELECT * FROM live_account_baseline")
        ] == baseline
    assert not exchange.submits


def test_explicit_enable_can_retry_when_credentials_become_available(tmp_path):
    make, current, account, exchange, journal, points = _case(tmp_path)
    bot = make(current, credential_account=None)
    with journal._connect() as connection:
        assert (
            json.loads(connection.execute("SELECT strategy_json FROM live_control").fetchone()[0])[
                "version"
            ]
            == V8_DIV32_PAPER_STRATEGY.version
        )
    bot.account_fingerprint = lambda: account.account
    snapshot = account.snapshot()
    bot.enable(snapshot.account, points(current), snapshot, now=snapshot.observed_at)
    assert bot.report()["state"] == "LIVE_ENABLED"
    assert not exchange.submits
    with journal._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM live_idle_upgrade_audit").fetchone()[0] == 1
