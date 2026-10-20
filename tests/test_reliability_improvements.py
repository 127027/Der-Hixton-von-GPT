"""Offline checks of power lifecycle and explicit version-test archive."""

import json
from decimal import Decimal

import pytest

from hixton.live.preparation import LivePreparation
from hixton.live.reconciliation import TrialReconciler
from hixton.ui.lifecycle import VisibleSession
from hixton.ui.power import SleepGuard
from hixton.ui.session_audit import record_session_event
from tests.test_live_preparation import MemoryVault
from tests.test_live_trial import NOW, arm, open_position, trial, universe


class Power:
    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail

    def create(self):
        self.calls.append(("create",))
        return 10

    def set(self, handle, kind):
        self.calls.append(("set", handle, kind))
        return kind != self.fail

    def clear(self, handle, kind):
        self.calls.append(("clear", handle, kind))

    def close(self, handle):
        self.calls.append(("close", handle))


def test_power_requests_are_scoped_and_release_on_error():
    power = Power()
    guard = SleepGuard(power)
    assert guard.start() and guard.start()
    assert power.calls == [("create",), ("set", 10, 1), ("set", 10, 3)]
    guard.close()
    guard.close()
    assert power.calls[-3:] == [("clear", 10, 3), ("clear", 10, 1), ("close", 10)]
    assert not guard.active
    failing = Power(fail=3)
    guard = SleepGuard(failing)
    assert not guard.start()
    assert failing.calls[-2:] == [("clear", 10, 1), ("close", 10)]


def test_stop_audit_survives_restart_and_does_not_store_token(tmp_path):
    events = []
    database = tmp_path / "hixton-usdc.sqlite3"
    session = VisibleSession(
        installation="test",
        token="DO_NOT_STORE_THIS_TOKEN",
        terminal_alive=lambda: True,
        request_exit=lambda: events.append("exit"),
        on_stop=lambda reason: record_session_event(
            database, "session-a", "STOP_REQUESTED", reason
        ),
    )
    session.stop("Letzte Bot-Seite geschlossen")
    session.stop("duplicate")
    payload = database.with_name("runtime-lifecycle.jsonl").read_text(encoding="utf-8")
    assert "DO_NOT_STORE_THIS_TOKEN" not in payload
    rows = [json.loads(r) for r in payload.splitlines()]
    assert len(rows) == 1 and rows[0]["reason"] == "Letzte Bot-Seite geschlossen"
    assert session.info()["stop_reason"] == rows[0]["reason"]
    assert events == ["exit"]


def test_audit_failure_does_not_prevent_shutdown():
    def broken(reason):
        raise OSError("disk unavailable")

    events = []
    session = VisibleSession(
        installation="test",
        token="private",
        terminal_alive=lambda: True,
        request_exit=lambda: events.append(1),
        on_stop=broken,
    )
    session.stop("test")
    assert events == [1]


def completed(tmp_path):
    from datetime import timedelta

    controller, exchange = trial(tmp_path)
    TrialReconciler(controller.journal)
    with controller.journal._connect() as db:
        db.execute(
            "INSERT INTO trial_account_baseline VALUES(1,?,?,?)",
            ("fake-account", NOW.isoformat(), json.dumps({"USDC": "250"})),
        )
    arm(controller)
    open_position(controller)
    at = NOW + timedelta(hours=1)
    points = universe(at, buy_symbol=None, sell_symbol="SOLUSDC")
    controller.advance(points, now=at, healthy=True)
    controller.advance(points, now=at, healthy=True)
    controller.confirm_reconciled(
        no_open_orders=True, owned_remaining=Decimal(0), account_matches=True, now=at
    )
    return controller, exchange


def test_archive_preserves_all_fills_and_only_explicitly_allows_next_trial(tmp_path):
    controller, exchange = completed(tmp_path)
    old = controller.report()
    old_id = controller.archive_completed()
    assert old_id == old["trial_id"]
    with controller.journal._connect() as db:
        row = db.execute(
            "SELECT payload_json FROM trial_archives WHERE trial_id=?", (old_id,)
        ).fetchone()
        history = json.loads(row[0])
        assert history["report"]["buy"] == old["buy"]
        assert history["report"]["sell"] == old["sell"]
        assert len(history["fills"]) == 2 and len(history["intents"]) == 2
        assert history["trial"]["execution_source_sha256"] == "test-source-v1"
        assert db.execute("SELECT count(*) FROM trial_account_baseline").fetchone()[0] == 0
    assert controller.report()["state"] == "NOT_STARTED"
    assert [i.side for i in exchange.submits] == ["BUY", "SELL"]
    arm(controller)
    assert controller.report()["state"] == "WAITING_SIGNAL"
    assert [i.side for i in exchange.submits] == ["BUY", "SELL"]
    with pytest.raises(RuntimeError):
        controller.archive_completed()


def test_open_and_unreconciled_trials_cannot_be_archived(tmp_path):
    controller, exchange = trial(tmp_path)
    arm(controller)
    open_position(controller)
    with pytest.raises(RuntimeError, match="completed"):
        controller.archive_completed()
    assert controller.report()["state"] == "OPEN"
    assert len(exchange.submits) == 1


def test_incomplete_fills_abort_archive_atomically(tmp_path):
    controller, _ = completed(tmp_path)
    with controller.journal._connect() as db:
        db.execute(
            "DELETE FROM trial_fills WHERE intent_id=?", (controller.report()["sell"]["intent_id"],)
        )
    with pytest.raises(RuntimeError, match="fills"):
        controller.archive_completed()
    assert controller.report()["state"] == "COMPLETED"
    with controller.journal._connect() as db:
        assert db.execute("SELECT count(*) FROM trial_intents").fetchone()[0] == 2


def test_completed_stale_trial_makes_new_action_available_without_arming(tmp_path):
    controller, exchange = completed(tmp_path)
    from hixton.domain.versions import strategy_definition

    service = LivePreparation(
        controller.journal.path, MemoryVault(), execution_source_sha256="new-source"
    )
    service.connect_runtime(
        strategy_definition("v6"),
        settings_provider=lambda: (Decimal(250), False),
        rules_provider=lambda: {},
    )
    status = service.status(
        authenticated=False,
        soak_ready=False,
        healthy=True,
        max_capital=Decimal(250),
        emergency_stop=False,
    )
    assert status["trial_retest_available"]
    assert service.trial.report()["state"] == "COMPLETED"
    assert not status["order_dispatch_available"]
    assert [i.side for i in exchange.submits] == ["BUY", "SELL"]


def retest_service(tmp_path, *, orders=(), same_source=False):
    from datetime import UTC, datetime

    from hixton.domain.versions import strategy_definition
    from hixton.live.credentials import BinanceCredentials
    from hixton.live.reconciliation import AccountSnapshot
    from tests.test_live_preparation import KEY, SECRET

    controller, exchange = completed(tmp_path)
    service = LivePreparation(
        controller.journal.path, MemoryVault(),
        execution_source_sha256="test-source-v1" if same_source else "new-source",
        application_version=controller.application_version,
        allocator_version=controller.allocator_version,
    )
    credentials = BinanceCredentials(KEY, SECRET)
    service.credentials.save(credentials)
    service.connect_runtime(
        controller.strategy if same_source else strategy_definition("v8r"),
        settings_provider=lambda: (Decimal(250), False),
        rules_provider=lambda: {},
    )
    service._action_check = lambda **kwargs: {"account_checks_passed": True}
    service._account_snapshot = lambda: AccountSnapshot(
        credentials.fingerprint,
        datetime.now(UTC),
        {"USDC": (Decimal("252.5"), Decimal(0))},
        orders,
    )
    return service, exchange


def test_same_source_test_is_repeatable_only_on_explicit_click(tmp_path):
    from hixton.live.binance import BinanceCheckError

    service, exchange = retest_service(tmp_path, same_source=True)
    previous = service.trial.report()
    assert service._trial_covers_current_runtime(previous)
    status = service.status(
        authenticated=True, soak_ready=False, healthy=True,
        max_capital=Decimal(250), emergency_stop=False,
    )
    assert status["trial_retest_available"] and status["trial_dispatch_available"]
    assert service.trial.report() == previous
    report = service.start_trial(healthy=True, emergency_stop=False)
    assert report["state"] == "WAITING_SIGNAL"
    assert report["trial_id"] != previous["trial_id"]
    old_file = service.database.parent / "trial-reports" / f"{previous['trial_id']}.json"
    assert json.loads(old_file.read_text(encoding="utf-8")) == previous
    assert [i.side for i in exchange.submits] == ["BUY", "SELL"]
    with pytest.raises(BinanceCheckError, match="WAITING_SIGNAL"):
        service.start_trial(healthy=True, emergency_stop=False)


def test_stale_snapshot_cannot_archive_completed_trial(tmp_path):
    from dataclasses import replace
    from datetime import timedelta

    from hixton.live.binance import BinanceCheckError

    service, exchange = retest_service(tmp_path, same_source=True)
    previous = service.trial.report()
    snapshot = service._account_snapshot()
    service._account_snapshot = lambda: replace(
        snapshot, observed_at=snapshot.observed_at - timedelta(minutes=1)
    )
    with pytest.raises(BinanceCheckError, match="nicht frisch"):
        service.start_trial(healthy=True, emergency_stop=False)
    assert service.trial.report() == previous
    with service.trial.journal._connect() as db:
        assert db.execute("SELECT count(*) FROM trial_intents").fetchone()[0] == 2
        assert not db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='trial_archives'"
        ).fetchone()
    assert len(exchange.submits) == 2


@pytest.mark.parametrize("obligation", ["positions", "unresolved_intents"])
def test_live_obligation_blocks_retest_before_archive(tmp_path, monkeypatch, obligation):
    from hixton.live.binance import BinanceCheckError

    service, exchange = retest_service(tmp_path, same_source=True)
    previous = service.trial.report()
    original = service.live.report()
    monkeypatch.setattr(service.live, "report", lambda: {**original, obligation: ["owned"]})
    status = service.status(
        authenticated=True, soak_ready=False, healthy=True,
        max_capital=Decimal(250), emergency_stop=False,
    )
    assert not status["trial_retest_available"] and not status["trial_dispatch_available"]
    with pytest.raises(BinanceCheckError, match="Live-Positionen"):
        service.start_trial(healthy=True, emergency_stop=False)
    assert service.trial.report() == previous and len(exchange.submits) == 2


def test_changed_disk_source_cannot_start_a_retest(tmp_path):
    from hixton.live.binance import BinanceCheckError

    service, exchange = retest_service(tmp_path, same_source=True)
    previous = service.trial.report()
    service.source_is_current = lambda: False
    with pytest.raises(BinanceCheckError, match="Code seit Botstart"):
        service.start_trial(healthy=True, emergency_stop=False)
    assert service.trial.report() == previous and len(exchange.submits) == 2


def test_explicit_new_version_action_archives_and_rebinds_without_a_buy(tmp_path):
    service, exchange = retest_service(tmp_path)
    previous_id = service.trial.report()["trial_id"]
    report = service.start_trial(healthy=True, emergency_stop=False)
    assert report["state"] == "WAITING_SIGNAL"
    assert report["trial_id"] != previous_id
    assert report["strategy"]["key"] == "v8r"
    assert report["execution_identity"]["frozen_source_sha256"] == "new-source"
    assert [i.side for i in exchange.submits] == ["BUY", "SELL"]
    old_file = service.database.parent / "trial-reports" / f"{previous_id}.json"
    assert json.loads(old_file.read_text(encoding="utf-8"))["state"] == "COMPLETED"
    with service.trial.journal._connect() as db:
        assert db.execute("SELECT count(*) FROM trial_archives").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM trial_intents").fetchone()[0] == 0


def test_open_account_order_blocks_retest_without_erasing_completion(tmp_path):
    from hixton.live.binance import BinanceCheckError

    service, exchange = retest_service(tmp_path, orders=("foreign-order",))
    old_id = service.trial.report()["trial_id"]
    with pytest.raises(BinanceCheckError, match="offene Orders"):
        service.start_trial(healthy=True, emergency_stop=False)
    assert service.trial.report()["trial_id"] == old_id
    assert service.trial.report()["state"] == "COMPLETED"
    assert [i.side for i in exchange.submits] == ["BUY", "SELL"]
