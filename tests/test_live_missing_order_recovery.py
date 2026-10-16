from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import pairwise
from uuid import uuid4

import pytest

from hixton.live.exchange import ExchangeRequestError
from hixton.live.orders import TrialIntent
from hixton.live.recovery import (
    ReadOnlyRecoveryTransport,
    RecoveryIdentity,
    _history,
    recover_missing_trial_order,
)
from tests.test_live_trial import trial

NOW = datetime(2026, 10, 16, 10, tzinfo=UTC)
SOURCE = "a" * 64


class Clock:
    def __init__(self):
        self.elapsed = 0.0

    def now(self):
        return NOW + timedelta(seconds=self.elapsed)

    def monotonic(self):
        return self.elapsed

    def sleep(self, seconds):
        self.elapsed += seconds


class Transport:
    def __init__(self, clock):
        self.clock = clock
        self.calls = []
        self.overrides = {}

    def request(self, method, path, params):
        assert method == "GET"
        self.calls.append((method, path, dict(params)))
        if path in self.overrides:
            value = self.overrides[path]
            if isinstance(value, Exception):
                raise value
            return value(params) if callable(value) else value
        if path == "/api/v3/time":
            return {"serverTime": int(self.clock.now().timestamp() * 1000)}
        if path == "/api/v3/order":
            raise ExchangeRequestError(-2013, 400)
        if path == "/api/v3/account":
            return {
                "balances": [
                    {"asset": "USDC", "free": "1000.000", "locked": "0"},
                    {"asset": "BNB", "free": "1", "locked": "0"},
                    {"asset": "ETH", "free": "2", "locked": "0"},
                    {"asset": "BTC", "free": "0", "locked": "0"},
                ]
            }
        return []


def setup(tmp_path):
    controller, exchange = trial(tmp_path, source_sha256=SOURCE)
    controller.arm(
        str(uuid4()), "fake-account", now=NOW - timedelta(hours=3), notional=Decimal("50")
    )
    row = controller._row()
    intent = TrialIntent(
        row["trial_id"] + "-entry",
        "fake-account",
        "BTCUSDC",
        "BUY",
        controller.strategy.version,
        Decimal("100"),
        Decimal("50"),
    )
    controller.journal.create(intent)
    with controller.journal._connect() as connection:
        connection.execute("UPDATE trial_intents SET state='UNKNOWN'")
        connection.execute(
            "UPDATE signal_trial SET state='ENTRY_PENDING',reason='ORDER_UNKNOWN',"
            "buy_id=?,symbol=?",
            (intent.intent_id, intent.symbol),
        )
        connection.execute(
            "INSERT INTO trial_order_audit(intent_id,action,at_utc) VALUES(?,?,?)",
            (intent.intent_id, "SUBMITTING", (NOW - timedelta(hours=2)).isoformat()),
        )
        connection.execute(
            "CREATE TABLE trial_account_baseline(singleton INTEGER PRIMARY KEY,"
            "account TEXT,observed_at TEXT,balances_json TEXT)"
        )
        connection.execute(
            "INSERT INTO trial_account_baseline VALUES(1,?,?,?)",
            (
                "fake-account",
                (NOW - timedelta(hours=3)).isoformat(),
                json.dumps({"USDC": "1000", "BNB": "1.00", "ETH": "2"}),
            ),
        )
    clock = Clock()
    transport = Transport(clock)
    identity = RecoveryIdentity(
        "fake-account", "unknown", SOURCE, "CAPITAL-V1-2X50PCT", controller.strategy.version
    )
    kwargs = {
        "expected_identity": identity,
        "credential_fingerprint": "fake-account",
        "current_source_sha256": "b" * 64,
        "source_is_current": lambda: True,
        "runtime_stopped": lambda: True,
        "operator_authorized": True,
        "clock": clock.now,
        "monotonic": clock.monotonic,
        "sleep": clock.sleep,
    }
    return controller, exchange, intent, transport, kwargs


def test_archives_failed_local_resolution_and_permanently_blocks_old_identity(tmp_path):
    controller, exchange, intent, transport, kwargs = setup(tmp_path)
    result = recover_missing_trial_order(controller.journal, transport, **kwargs)
    assert result["trial_state"] == "FAILED"
    assert result["certificate_issued"] is False
    assert not exchange.submits
    assert len([call for call in transport.calls if call[1] == "/api/v3/order"]) == 3
    assert kwargs["monotonic"]() >= 2
    assert controller.report()["state"] == "NOT_STARTED"
    with controller.journal._connect() as connection:
        archive = json.loads(
            connection.execute("SELECT payload_json FROM trial_archives").fetchone()[0]
        )
        assert archive["evidence"]["original"]["trial_intents"][0]["state"] == "UNKNOWN"
        assert (
            archive["evidence"]["original"]["signal_trial"][0]["execution_source_sha256"] == SOURCE
        )
        assert archive["evidence"]["exchange_state"] is None
        assert archive["evidence_sha256"] == result["evidence_sha256"]
        assert connection.execute("SELECT COUNT(*) FROM trial_intents").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM trial_order_audit").fetchone()[0] >= 3
    with pytest.raises(sqlite3.IntegrityError, match="cannot be reused"):
        controller.journal.create(intent)
    controller.arm(str(uuid4()), "fake-account", now=NOW, notional=Decimal("50"))
    assert controller.report()["state"] == "WAITING_SIGNAL"


@pytest.mark.parametrize(
    "override",
    [
        {"credential_fingerprint": "other"},
        {"operator_authorized": False},
        {"runtime_stopped": lambda: False},
        {"source_is_current": lambda: False},
        {"current_source_sha256": "unknown"},
        {"sleep": lambda _: None},
    ],
)
def test_rejects_untrusted_authorization_identity_source_runtime_or_observation_spacing(
    tmp_path, override
):
    controller, _, _, transport, kwargs = setup(tmp_path)
    kwargs.update(override)
    with pytest.raises((RuntimeError, ValueError)):
        recover_missing_trial_order(controller.journal, transport, **kwargs)
    assert controller._row()["state"] == "ENTRY_PENDING"


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE trial_intents SET order_id='ack'",
        "UPDATE trial_intents SET exchange_state='NEW'",
        "UPDATE trial_intents SET executed_quantity='0.001'",
        "UPDATE trial_intents SET cumulative_quote='0.001'",
        "UPDATE trial_intents SET state='CREATED'",
        "UPDATE trial_intents SET account='other'",
        "UPDATE trial_intents SET client_id='wrong-persisted-client'",
        "UPDATE signal_trial SET execution_source_sha256='different'",
        "UPDATE signal_trial SET owned_quantity='1'",
        "UPDATE signal_trial SET sell_id='exit'",
        "UPDATE signal_trial SET state='OPEN'",
        "UPDATE trial_account_baseline SET account='other'",
        "UPDATE trial_account_baseline SET observed_at='2026-10-16T09:59:00+00:00'",
        "UPDATE trial_order_audit SET at_utc='2026-10-16T09:59:30+00:00' WHERE action='SUBMITTING'",
        "DELETE FROM trial_order_audit WHERE action='SUBMITTING'",
        "INSERT INTO trial_order_audit(intent_id,action,at_utc) SELECT intent_id,action,at_utc "
        "FROM trial_order_audit WHERE action='SUBMITTING'",
        "CREATE TABLE live_positions(symbol TEXT); INSERT INTO live_positions VALUES('BTCUSDC')",
        "CREATE TABLE live_intents(state TEXT); INSERT INTO live_intents VALUES('UNKNOWN')",
        "CREATE TABLE live_control(entries_enabled INTEGER); INSERT INTO live_control VALUES(1)",
    ],
)
def test_any_existing_ack_quantity_other_exposure_or_invalid_original_proof_blocks(tmp_path, sql):
    controller, _, _, transport, kwargs = setup(tmp_path)
    with controller.journal._connect() as connection:
        connection.executescript(sql)
    with pytest.raises((RuntimeError, ValueError)):
        recover_missing_trial_order(controller.journal, transport, **kwargs)
    assert not transport.calls


@pytest.mark.parametrize(
    "path,response",
    [
        ("/api/v3/order", {}),
        ("/api/v3/order", ExchangeRequestError(-2015, 400)),
        ("/api/v3/order", ExchangeRequestError(-2013, 500)),
        ("/api/v3/allOrders", {"code": -1003}),
        ("/api/v3/myTrades", [{"id": 1, "symbol": "OTHER", "time": 1}]),
        ("/api/v3/openOrders", [{"clientOrderId": "foreign"}]),
        ("/api/v3/account", {"balances": [{"asset": "USDC", "free": "1000", "locked": "1"}]}),
        ("/api/v3/account", {"balances": [{"asset": "USDC", "free": "1000", "locked": "0"}]}),
        ("/api/v3/account", {"balances": [{"asset": "BNB", "free": "NaN", "locked": "0"}]}),
        ("/api/v3/time", {"serverTime": 1}),
    ],
)
def test_any_incomplete_or_contradictory_exchange_observation_preserves_unknown(
    tmp_path, path, response
):
    controller, _, _, transport, kwargs = setup(tmp_path)
    transport.overrides[path] = response
    with pytest.raises((RuntimeError, ValueError)):
        recover_missing_trial_order(controller.journal, transport, **kwargs)
    with controller.journal._connect() as connection:
        assert connection.execute("SELECT state FROM trial_intents").fetchone()[0] == "UNKNOWN"
        assert not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='trial_archives'"
        ).fetchone()


@pytest.mark.parametrize("path,key", [("/api/v3/myTrades", "id"), ("/api/v3/allOrders", "orderId")])
def test_a_single_trade_or_order_in_submit_window_blocks_even_with_unchanged_balance(
    tmp_path, path, key
):
    controller, _, _, transport, kwargs = setup(tmp_path)
    transport.overrides[path] = lambda params: [
        {
            key: 9,
            "symbol": "BTCUSDC",
            "time": int(params["startTime"]) + 1,
        }
    ]
    with pytest.raises(RuntimeError, match="activity"):
        recover_missing_trial_order(controller.journal, transport, **kwargs)


def test_history_splits_full_pages_without_unsupported_parameter_combinations():
    clock = Clock()
    transport = Transport(clock)
    rows = [{"id": index, "time": index, "symbol": "BTCUSDC"} for index in range(1000)]
    transport.overrides["/api/v3/myTrades"] = lambda params: [
        row for row in rows if (int(params["startTime"]) <= row["time"] <= int(params["endTime"]))
    ]
    proof = _history(
        ReadOnlyRecoveryTransport(transport, lambda: True), "/api/v3/myTrades", "BTCUSDC", 0, 999
    )
    assert proof["requests"] == 3
    assert len(proof["rows"]) == 1000
    assert all("fromId" not in call[2] for call in transport.calls)


def test_saturated_single_millisecond_and_readonly_mutation_are_rejected():
    clock = Clock()
    transport = Transport(clock)
    transport.overrides["/api/v3/myTrades"] = [
        {"id": index, "time": 0, "symbol": "BTCUSDC"} for index in range(1000)
    ]
    readonly = ReadOnlyRecoveryTransport(transport, lambda: True)
    with pytest.raises(RuntimeError, match="single-millisecond"):
        _history(readonly, "/api/v3/myTrades", "BTCUSDC", 0, 0)
    with pytest.raises(ValueError, match="GET"):
        readonly.request("POST", "/api/v3/order", {})


def test_source_or_runtime_revoked_after_observations_rolls_back(tmp_path):
    controller, _, _, transport, kwargs = setup(tmp_path)
    kwargs["source_is_current"] = lambda: len(transport.calls) < 21
    with pytest.raises(RuntimeError, match="source changed"):
        recover_missing_trial_order(controller.journal, transport, **kwargs)
    assert controller._row()["state"] == "ENTRY_PENDING"


def test_filled_history_cannot_be_archived_as_missing_even_without_ack(tmp_path):
    controller, _, intent, transport, kwargs = setup(tmp_path)
    with controller.journal._connect() as connection:
        connection.execute(
            "INSERT INTO trial_fills(account,symbol,trade_id,intent_id,quantity,price,"
            "commission,commission_asset) VALUES(?,?,?,?,?,?,?,?)",
            ("fake-account", "BTCUSDC", "trade", intent.intent_id, "0.1", "100", "0", "BNB"),
        )
    with pytest.raises(RuntimeError, match="empty-fill"):
        recover_missing_trial_order(controller.journal, transport, **kwargs)
    assert not transport.calls


def test_account_movement_between_reads_and_stale_observations_block(tmp_path):
    controller, _, _, transport, kwargs = setup(tmp_path)
    account = transport.request("GET", "/api/v3/account", {})
    reads = 0

    def moving(_):
        nonlocal reads
        reads += 1
        if reads == 2:
            return {"balances": []}
        return account

    transport.overrides["/api/v3/account"] = moving
    with pytest.raises(RuntimeError, match="Stable complete"):
        recover_missing_trial_order(controller.journal, transport, **kwargs)
    assert controller._row()["state"] == "ENTRY_PENDING"


def test_24h_windows_cover_history_without_gaps():
    clock = Clock()
    transport = Transport(clock)
    proof = _history(
        ReadOnlyRecoveryTransport(transport, lambda: True),
        "/api/v3/allOrders",
        "BTCUSDC",
        100,
        172_800_101,
    )
    windows = sorted(proof["complete_windows"], key=lambda row: row["start_ms"])
    assert len(windows) == 3
    assert windows[0]["start_ms"] == 100 and windows[-1]["end_ms"] == 172_800_101
    assert all(second["start_ms"] == first["end_ms"] + 1 for first, second in pairwise(windows))
