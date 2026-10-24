"""Offline operational alerts: no exchange, vault, provider or trading mutations."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from hixton.notifications import operations
from hixton.notifications.operations import (
    ACCOUNT_UNOBSERVED,
    OPERATIONS_CATALOG,
    OperationsObservation,
    evaluate_operations,
    initialize_operations,
    reset_operations,
    sample_operations,
)

NOW = datetime(2026, 10, 24, 12, 10, tzinfo=UTC)
SYMBOLS = ("BTCUSDC", "BCHUSDC", "NEARUSDC")


def runtime(**updates: object) -> dict[str, object]:
    return {
        "health": "HEALTHY", "stream_connected": False, "feed_mode": "REST",
        "expected_symbols": SYMBOLS,
        "final_bar_times": dict.fromkeys(SYMBOLS, NOW.replace(minute=0)-timedelta(milliseconds=1)),
        "account_observation": {"state": "CURRENT", "fresh": True, "code": None},
        **updates,
    }


@pytest.fixture
def journal(tmp_path: Path) -> Path:
    path = tmp_path / "journal.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.executescript("""
          CREATE TABLE signal_trial(
            state TEXT,reason TEXT,owned_quantity TEXT,residual_quantity TEXT);
          CREATE TABLE live_control(state TEXT);
          INSERT INTO live_control VALUES('LIVE_DISABLED');
          CREATE TABLE live_positions(quantity TEXT);
        """)
        for prefix in ("trial", "live"):
            conn.execute(f"CREATE TABLE {prefix}_intents(intent_id TEXT,state TEXT,"
                         "exchange_state TEXT,executed_quantity TEXT,order_id TEXT)")
            conn.execute(f"CREATE TABLE {prefix}_fills(intent_id TEXT,quantity TEXT)")
    return path


def intent(path: Path, prefix: str, state: str, exchange: str | None = None,
           quantity: str = "0", filled: str | None = None) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(f"INSERT INTO {prefix}_intents VALUES('intent',?,?,?,'order')",
                     (state, exchange, quantity))
        if filled is not None:
            conn.execute(f"INSERT INTO {prefix}_fills VALUES('intent',?)", (filled,))


@pytest.mark.parametrize("prefix", ["trial", "live"])
@pytest.mark.parametrize("state", [
    "UNKNOWN", "SUBMITTING", "NEW", "PARTIALLY_FILLED", "FILL_DETAILS_PENDING", "PENDING_CANCEL",
])
def test_unknown_order_includes_no_fills(journal: Path, prefix: str, state: str) -> None:
    intent(journal, prefix, state)
    assert sample_operations(journal, runtime(), (), NOW) == ("UNKNOWN_ORDER",)


@pytest.mark.parametrize("filled", [None, "0.5"])
def test_terminal_missing_or_partial_fill_evidence_not_healthy(
    journal: Path, filled: str | None
) -> None:
    intent(journal, "live", "FILLED", "FILLED", "1", filled)
    assert "UNKNOWN_ORDER" in sample_operations(journal, runtime(), (), NOW)


def test_complete_terminal_history_no_alarm_and_read_only(journal: Path) -> None:
    intent(journal, "live", "FILLED", "FILLED", "1", "1")
    before = hashlib.sha256(journal.read_bytes()).digest()
    assert sample_operations(journal, runtime(), (), NOW) == ()
    assert hashlib.sha256(journal.read_bytes()).digest() == before


def test_runtime_errors_only_active_and_fixed_text(journal: Path) -> None:
    secret = "https://api?signature=SUPER_SECRET_TOKEN"
    assert sample_operations(journal, runtime(), (secret,), NOW) == ()
    with sqlite3.connect(journal) as conn:
        conn.execute("UPDATE live_control SET state='EXIT_ONLY'")
    assert sample_operations(journal, runtime(), (secret,), NOW) == ("EXECUTION_REVIEW",)
    assert secret not in str(OPERATIONS_CATALOG)


@pytest.mark.parametrize("state", ["WAITING_SIGNAL", "OPEN", "EXIT_PENDING"])
def test_trial_active_context_needs_market_data(journal: Path, state: str) -> None:
    with sqlite3.connect(journal) as conn:
        conn.execute("INSERT INTO signal_trial VALUES(?,NULL,NULL,'0')", (state,))
    assert "MARKET_DATA" in sample_operations(journal, runtime(health="DEGRADED"), (), NOW)
    assert "MARKET_DATA" not in sample_operations(journal, runtime(), (), NOW)


def test_disabled_with_owned_position_still_protected(journal: Path) -> None:
    with sqlite3.connect(journal) as conn:
        conn.execute("INSERT INTO live_positions VALUES('1')")
    assert "MARKET_DATA" in sample_operations(journal, runtime(health="STARTING"), (), NOW)


@pytest.mark.parametrize("bad_times", [None, {}, {"BTCUSDC": NOW}, dict.fromkeys(
    SYMBOLS, NOW-timedelta(hours=2)
)])
def test_all_market_finalized_times_required(journal: Path, bad_times: object) -> None:
    with sqlite3.connect(journal) as conn:
        conn.execute("UPDATE live_control SET state='LIVE_ENABLED'")
    assert "MARKET_DATA" in sample_operations(
        journal, runtime(final_bar_times=bad_times), (), NOW
    )


def test_final_boundary_grace_not_websocket_requirement(journal: Path) -> None:
    with sqlite3.connect(journal) as conn:
        conn.execute("UPDATE live_control SET state='LIVE_ENABLED'")
    just_closed = NOW.replace(minute=0)+timedelta(seconds=30)
    previous = just_closed.replace(minute=0, second=0)-timedelta(hours=1, milliseconds=1)
    assert "MARKET_DATA" not in sample_operations(
        journal, runtime(final_bar_times=dict.fromkeys(SYMBOLS, previous)), (), just_closed
    )
    assert "MARKET_DATA" in sample_operations(
        journal, runtime(final_bar_times=dict.fromkeys(SYMBOLS, previous)), (),
        just_closed+timedelta(minutes=2)
    )


@pytest.mark.parametrize(("state", "code", "expected"), [
    ("KEY_MISSING", None, "BINANCE_ACCESS"),
    ("UNAVAILABLE", -2015, "BINANCE_ACCESS"),
    ("UNAVAILABLE", -1021, "BINANCE_CLOCK"),
    ("UNAVAILABLE", -1003, "BINANCE_CONNECTION"),
])
def test_passive_account_current_error_only(journal: Path, state: str,
                                          code: int | None, expected: str) -> None:
    with sqlite3.connect(journal) as conn:
        conn.execute("UPDATE live_control SET state='LIVE_ENABLED'")
    assert sample_operations(journal, runtime(account_observation={
        "state": state, "fresh": True, "code": code,
    }), (), NOW) == tuple(sorted((ACCOUNT_UNOBSERVED, expected)))
    assert sample_operations(journal, runtime(account_observation={
        "state": state, "fresh": False, "code": code,
    }), (), NOW) == (ACCOUNT_UNOBSERVED,)


def test_missing_invalid_or_locked_db_not_healthy(tmp_path: Path) -> None:
    with pytest.raises(sqlite3.Error):
        sample_operations(tmp_path/"absent.sqlite3", runtime(), (), NOW)
    empty = tmp_path/"empty.sqlite3"
    sqlite3.connect(empty).close()
    with pytest.raises(sqlite3.DatabaseError):
        sample_operations(empty, runtime(), (), NOW)


def test_sampling_holds_one_sqlite_snapshot(journal: Path, monkeypatch: Any) -> None:
    intent(journal, "live", "UNKNOWN")
    with sqlite3.connect(journal) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
    original = sqlite3.connect
    changed = False

    def connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        conn = original(*args, **kwargs)

        def trace(sql: str) -> None:
            nonlocal changed
            if "SELECT * FROM live_control" in sql and not changed:
                changed = True
                with original(journal) as writer:
                    writer.execute("UPDATE live_intents SET state='FILLED',"
                                   "exchange_state='FILLED',executed_quantity='1'")
                    writer.execute("INSERT INTO live_fills VALUES('intent','1')")
        conn.set_trace_callback(trace)
        return conn

    monkeypatch.setattr(operations.sqlite3, "connect", connect)
    assert sample_operations(journal, runtime(), (), NOW) == ("UNKNOWN_ORDER",)
    assert changed
    assert sample_operations(journal, runtime(), (), NOW) == ()


@pytest.fixture
def tracker() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    initialize_operations(conn)
    conn.commit()
    yield conn
    conn.close()


def evaluate(conn: sqlite3.Connection, seconds: int, *codes: str,
             generation: str = "recipient-1") -> tuple[Any, ...]:
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        # The fixture has one fixed obligation, terminal only when UNKNOWN disappears.
        observation = OperationsObservation(codes, {"a"*64: "UNKNOWN_ORDER" not in codes})
        return evaluate_operations(conn, generation, observation, NOW+timedelta(seconds=seconds))


def test_critical_dedup_recovery_and_recurrence(tracker: sqlite3.Connection) -> None:
    first = evaluate(tracker, 0, "UNKNOWN_ORDER")
    assert len(first) == 1 and first[0].kind == "operation_alert"
    assert evaluate(tracker, 5, "UNKNOWN_ORDER") == ()
    for second in range(10, 40, 5):
        assert evaluate(tracker, second) == ()
    recovered = evaluate(tracker, 40)
    assert len(recovered) == 1 and recovered[0].kind == "operation_recovery"
    second = evaluate(tracker, 45, "UNKNOWN_ORDER")
    assert len(second) == 1 and first[0].key != second[0].key


def test_market_grace_requires_continuous_observations(tracker: sqlite3.Connection) -> None:
    for second in range(0, 120, 5):
        assert evaluate(tracker, second, "MARKET_DATA") == ()
    assert len(evaluate(tracker, 120, "MARKET_DATA")) == 1
    assert evaluate(tracker, 125, "MARKET_DATA") == ()


def test_gaps_do_not_count_recovery_or_grace(tracker: sqlite3.Connection) -> None:
    evaluate(tracker, 0, "UNKNOWN_ORDER")
    evaluate(tracker, 5)
    assert evaluate(tracker, 300) == ()
    for second in range(305, 330, 5):
        assert evaluate(tracker, second) == ()
    assert len(evaluate(tracker, 330)) == 1
    assert evaluate(tracker, 400, "MARKET_DATA") == ()
    assert evaluate(tracker, 600, "MARKET_DATA") == ()


def test_restart_preserves_incident_but_not_healthy_credit(tracker: sqlite3.Connection) -> None:
    evaluate(tracker, 0, "UNKNOWN_ORDER")
    for second in range(5, 30, 5):
        evaluate(tracker, second)
    with tracker:
        initialize_operations(tracker)
    assert evaluate(tracker, 30) == ()
    for second in range(35, 60, 5):
        assert evaluate(tracker, second) == ()
    assert len(evaluate(tracker, 60)) == 1


def test_restart_does_not_repeat_existing_critical(tracker: sqlite3.Connection) -> None:
    evaluate(tracker, 0, "UNKNOWN_ORDER")
    with tracker:
        initialize_operations(tracker)
    assert evaluate(tracker, 5, "UNKNOWN_ORDER") == ()


def test_account_recovery_requires_fresh_current_observation(tracker: sqlite3.Connection) -> None:
    evaluate(tracker, 0, "BINANCE_ACCESS", ACCOUNT_UNOBSERVED)
    for second in range(5, 60, 5):
        assert evaluate(tracker, second, ACCOUNT_UNOBSERVED) == ()
    for second in range(60, 90, 5):
        assert evaluate(tracker, second) == ()
    assert len(evaluate(tracker, 90)) == 1


def test_unknown_observation_never_resolves_safety_incident(tracker: sqlite3.Connection) -> None:
    evaluate(tracker, 0, "UNKNOWN_ORDER")
    evaluate(tracker, 5)
    notice = evaluate(tracker, 10, "OBSERVATION_UNAVAILABLE", ACCOUNT_UNOBSERVED)
    assert len(notice) == 1 and notice[0].title == OPERATIONS_CATALOG[
        "OBSERVATION_UNAVAILABLE"
    ].title
    for second in range(15, 50, 5):
        assert evaluate(tracker, second, "OBSERVATION_UNAVAILABLE", ACCOUNT_UNOBSERVED) == ()
    for second in range(50, 80, 5):
        assert evaluate(tracker, second) == ()
    assert len(evaluate(tracker, 80)) == 2


def test_generation_change_resets_recipient_context(tracker: sqlite3.Connection) -> None:
    first = evaluate(tracker, 0, "UNKNOWN_ORDER")
    assert evaluate(tracker, 5, generation="new-recipient") == ()
    current = evaluate(tracker, 10, "UNKNOWN_ORDER", generation="new-recipient")
    assert len(current) == 1 and current[0].key != first[0].key
    with tracker:
        reset_operations(tracker)
    assert tracker.execute("SELECT COUNT(*) FROM operational_notice_episodes").fetchone()[0] == 0


def test_tracker_and_enqueue_rollback_together(tracker: sqlite3.Connection) -> None:
    tracker.execute("CREATE TABLE outbox(key TEXT PRIMARY KEY)")
    tracker.commit()
    with pytest.raises(RuntimeError), tracker:
        tracker.execute("BEGIN IMMEDIATE")
        notice = evaluate_operations(tracker, "recipient-1", ("UNKNOWN_ORDER",), NOW)[0]
        tracker.execute("INSERT INTO outbox VALUES(?)", (notice.key,))
        raise RuntimeError("crash before commit")
    assert tracker.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0
    assert len(evaluate(tracker, 5, "UNKNOWN_ORDER")) == 1


def test_tracker_requires_atomic_transaction_and_fixed_codes(tracker: sqlite3.Connection) -> None:
    with pytest.raises(RuntimeError):
        evaluate_operations(tracker, "recipient-1", (), NOW)
    with tracker:
        tracker.execute("BEGIN IMMEDIATE")
        with pytest.raises(ValueError):
            evaluate_operations(tracker, "recipient-1", ("TOKEN=must-not-escape",), NOW)


def test_backward_clock_does_not_finish_recovery(tracker: sqlite3.Connection) -> None:
    evaluate(tracker, 30, "UNKNOWN_ORDER")
    evaluate(tracker, 35)
    assert evaluate(tracker, 5) == ()
    for second in range(10, 35, 5):
        assert evaluate(tracker, second) == ()
    assert len(evaluate(tracker, 35)) == 1


def test_completed_trial_bought_quantity_is_history_not_exposure(journal: Path) -> None:
    with sqlite3.connect(journal) as conn:
        conn.execute("INSERT INTO signal_trial VALUES('COMPLETED',NULL,'10','0')")
    intent(journal, "trial", "FILLED", "FILLED", "10", "10")
    intent(journal, "live", "FILLED", "FILLED", "10", "10")
    codes = sample_operations(journal, runtime(health="DEGRADED", account_observation={
        "state": "UNAVAILABLE", "fresh": True, "code": -2015,
    }), ("private historical runtime error",), NOW)
    assert codes == (ACCOUNT_UNOBSERVED,)


@pytest.mark.parametrize("table", ["trial_intents", "live_intents", "trial_fills", "live_fills"])
def test_missing_journal_table_is_not_proof_of_resolution(journal: Path, table: str) -> None:
    with sqlite3.connect(journal) as conn:
        conn.execute(f"DROP TABLE {table}")
    with pytest.raises(sqlite3.DatabaseError):
        sample_operations(journal, runtime(), (), NOW)


def test_order_disappearing_or_replaced_does_not_recover(
    journal: Path, tracker: sqlite3.Connection
) -> None:
    intent(journal, "live", "UNKNOWN")
    first = sample_operations(journal, runtime(), (), NOW)
    with tracker:
        tracker.execute("BEGIN IMMEDIATE")
        assert len(evaluate_operations(tracker, "generation", first, NOW)) == 1
    with sqlite3.connect(journal) as conn:
        conn.execute("DELETE FROM live_intents")
    cleared = sample_operations(journal, runtime(), (), NOW)
    assert cleared == ()  # Absence differs from positive terminal evidence.
    for second in range(5, 60, 5):
        with tracker:
            tracker.execute("BEGIN IMMEDIATE")
            assert evaluate_operations(
                tracker, "generation", cleared, NOW+timedelta(seconds=second)
            ) == ()
    intent(journal, "live", "FILLED", "FILLED", "1", "1")
    settled = sample_operations(journal, runtime(), (), NOW)
    for second in range(60, 90, 5):
        with tracker:
            tracker.execute("BEGIN IMMEDIATE")
            assert evaluate_operations(
                tracker, "generation", settled, NOW+timedelta(seconds=second)
            ) == ()
    with tracker:
        tracker.execute("BEGIN IMMEDIATE")
        notice = evaluate_operations(tracker, "generation", settled, NOW+timedelta(seconds=90))
    assert len(notice) == 1 and notice[0].kind == "operation_recovery"


def test_codes_without_order_evidence_never_clear_unknown(tracker: sqlite3.Connection) -> None:
    with tracker:
        tracker.execute("BEGIN IMMEDIATE")
        assert len(evaluate_operations(tracker, "generation", ("UNKNOWN_ORDER",), NOW)) == 1
    for second in range(5, 60, 5):
        with tracker:
            tracker.execute("BEGIN IMMEDIATE")
            assert evaluate_operations(
                tracker, "generation", (), NOW+timedelta(seconds=second)
            ) == ()
