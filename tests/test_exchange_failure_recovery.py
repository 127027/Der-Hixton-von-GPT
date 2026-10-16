"""Offline order-dispatch proof, durable ACK and sanitized error regressions."""

import io
import json
from urllib.error import URLError

import pytest

from hixton.live.exchange import ExchangeRequestError
from hixton.live.orders import OrderJournal, TrialOrderExecutor, request_error_metadata
from hixton.live.production import LiveIntent, LiveOrderExecutor, LiveOrderJournal
from tests.test_live_exchange import (
    FakeOpener,
    ScriptedTransport,
    exchange,
    intent,
    transport,
)


def test_clock_failure_before_dispatch_releases_claim_without_post(tmp_path):
    class FailedClock(FakeOpener):
        def open(self, request, timeout):
            self.requests.append(request)
            raise URLError("secret signed url and key must never be persisted")

    opener = FailedClock()
    client = transport(opener)
    from hixton.live.exchange import BinanceSpotExchange

    adapter = BinanceSpotExchange(
        client, account_fingerprint="account-fixture", quote_asset="USDC"
    )
    order = intent()
    journal = OrderJournal(tmp_path / "clock.sqlite3")
    journal.create(order)
    executor = TrialOrderExecutor(journal, adapter, lambda _: True)
    assert executor.execute(order.intent_id) == "CREATED"
    assert [request.get_method() for request in opener.requests] == ["GET"]
    detail = journal.fill_summary(order.intent_id)["last_request_error"]
    assert detail["stage"] == "CLOCK_SYNC"
    assert detail["definitely_not_submitted"] is True
    executor.pre_submit = lambda _: False
    assert executor.execute(order.intent_id) == "BLOCKED"
    assert len(opener.requests) == 1
    assert b"secret signed" not in journal.path.read_bytes()


def test_bad_server_clock_preserves_tolerance_and_no_post(tmp_path):
    class SkewedClock(FakeOpener):
        def open(self, request, timeout):
            self.requests.append(request)
            return io.BytesIO(b'{"serverTime":1001001}')

    opener = SkewedClock()
    from hixton.live.exchange import BinanceSpotExchange

    adapter = BinanceSpotExchange(
        transport(opener), account_fingerprint="account-fixture", quote_asset="USDC"
    )
    order = intent()
    journal = OrderJournal(tmp_path / "clock.sqlite3")
    journal.create(order)
    executor = TrialOrderExecutor(journal, adapter, lambda _: True)
    assert executor.execute(order.intent_id) == "CREATED"
    assert [request.get_method() for request in opener.requests] == ["GET"]


def test_ack_survives_query_failure_and_restart_never_resubmits(tmp_path):
    class QueryFailure(ScriptedTransport):
        fail_query = True

        def request(self, method, path, params):
            if method == "GET" and path.endswith("/order") and self.fail_query:
                self.calls.append((method, path, params))
                raise ExchangeRequestError(-1007, 504, stage="ORDER_QUERY")
            return super().request(method, path, params)

    order = intent()
    client = QueryFailure(order)
    journal = OrderJournal(tmp_path / "ack.sqlite3")
    journal.create(order)
    executor = TrialOrderExecutor(journal, exchange(client), lambda _: True)
    assert executor.execute(order.intent_id) == "UNKNOWN"
    summary = journal.fill_summary(order.intent_id)
    assert summary["exchange_order_id"] == "123"
    assert summary["exchange_state"] is None
    assert summary["fill_count"] == 0
    assert summary["last_request_error"]["stage"] == "ORDER_QUERY"
    assert summary["last_request_error"]["code"] == -1007
    assert summary["last_request_error"]["http_status"] == 504
    assert not journal.release_not_submitted(order.intent_id)
    client.fail_query = False
    restarted = TrialOrderExecutor(OrderJournal(journal.path), exchange(client), lambda _: False)
    assert restarted.execute(order.intent_id) == "FILLED"
    assert sum(method == "POST" for method, _, _ in client.calls) == 1


def test_lost_post_response_is_never_released_as_pre_dispatch(tmp_path):
    order = intent()
    client = ScriptedTransport(order)
    client.timeout_after_accept = True
    journal = OrderJournal(tmp_path / "ambiguous.sqlite3")
    journal.create(order)
    executor = TrialOrderExecutor(journal, exchange(client), lambda _: True)
    assert executor.execute(order.intent_id) == "UNKNOWN"
    assert not journal.release_not_submitted(order.intent_id)
    assert journal.fill_summary(order.intent_id)["exchange_order_id"] is None
    detail = journal.fill_summary(order.intent_id)["last_request_error"]
    assert detail["definitely_not_submitted"] is False


def test_diagnostics_never_store_raw_exception_fields(tmp_path):
    order = intent()
    journal = OrderJournal(tmp_path / "redaction.sqlite3")
    journal.create(order)
    error = RuntimeError("SECRET https://signed.invalid?signature=SECRET")
    error.stage = {"SECRET": "SECRET"}
    error.code = "SECRET"
    error.http_status = "SECRET"
    error.definitely_not_submitted = "SECRET"
    journal.record_request_error(order.intent_id, error, "RECONCILE")
    detail = journal.fill_summary(order.intent_id)["last_request_error"]
    assert detail["stage"] == "RECONCILE"
    assert detail["code"] is None and detail["http_status"] is None
    assert "SECRET" not in json.dumps(detail)
    assert b"SECRET" not in journal.path.read_bytes()


def test_old_pre_dispatch_proof_cannot_release_next_claim(tmp_path):
    order = intent()
    journal = OrderJournal(tmp_path / "proof.sqlite3")
    journal.create(order)
    assert journal.claim_submit(order.intent_id)
    failure = ExchangeRequestError(definitely_not_submitted=True, stage="CLOCK_SYNC")
    journal.record_request_error(order.intent_id, failure, "ORDER_SUBMIT")
    assert journal.release_not_submitted(order.intent_id)
    assert journal.claim_submit(order.intent_id)
    assert not journal.release_not_submitted(order.intent_id)
    journal.unknown(order.intent_id)
    assert journal.load(order.intent_id)[1] == "UNKNOWN"


def test_error_classifier_only_permits_clock_proof():
    error = ExchangeRequestError(definitely_not_submitted=True, stage="ORDER_QUERY")
    assert request_error_metadata(error, "ORDER_QUERY")["definitely_not_submitted"] is False


def test_missing_lookup_retains_unknown_with_diagnostic_code(tmp_path):
    order = intent()
    journal = OrderJournal(tmp_path / "missing.sqlite3")
    journal.create(order)
    journal.claim_submit(order.intent_id)

    class Missing:
        def submit(self, supplied):
            raise AssertionError("Unknown order must never be submitted again")

        def query(self, supplied):
            return None

    executor = TrialOrderExecutor(journal, Missing(), lambda _: True)
    assert executor.execute(order.intent_id) == "UNKNOWN"
    detail = journal.fill_summary(order.intent_id)["last_request_error"]
    assert detail["code"] == -2013 and detail["stage"] == "ORDER_QUERY"
    assert detail["definitely_not_submitted"] is False


def _live_fixture(tmp_path):
    original = intent()
    order = LiveIntent(
        original.intent_id,
        original.account_fingerprint,
        original.symbol,
        original.side,
        original.strategy_version,
        original.reference_price,
        1,
        quote_budget=original.quote_budget,
    )
    journal = LiveOrderJournal(tmp_path / "live.sqlite3")
    journal.create(order)
    return order, journal


def _live_diagnostic(journal, order):
    with journal._connect() as connection:
        row = connection.execute(
            "SELECT metadata_json FROM live_request_diagnostics WHERE intent_id=?",
            (order.intent_id,),
        ).fetchone()
    return json.loads(row["metadata_json"])


def test_live_ack_timeout_survives_restart_without_second_post(tmp_path):
    class QueryFailure(ScriptedTransport):
        fail_query = True

        def request(self, method, path, params):
            if method == "GET" and path.endswith("/order") and self.fail_query:
                self.calls.append((method, path, params))
                raise ExchangeRequestError(-1007, 504, stage="ORDER_QUERY")
            return super().request(method, path, params)

    order, journal = _live_fixture(tmp_path)
    client = QueryFailure(order)
    executor = LiveOrderExecutor(journal, exchange(client), lambda _: True)
    assert executor.execute(order.intent_id) == "UNKNOWN"
    summary = journal.fill_summary(order.intent_id)
    assert summary["exchange_order_id"] == "123" and summary["fill_count"] == 0
    assert _live_diagnostic(journal, order)["stage"] == "ORDER_QUERY"
    assert not journal.release_not_submitted(order.intent_id)
    client.fail_query = False
    restarted = LiveOrderExecutor(LiveOrderJournal(journal.path), exchange(client), lambda _: False)
    assert restarted.execute(order.intent_id) == "FILLED"
    assert sum(method == "POST" for method, _, _ in client.calls) == 1


def test_live_clock_failure_releases_only_unsent_claim_and_rechecks_gate(tmp_path):
    class FailedClock(FakeOpener):
        def open(self, request, timeout):
            self.requests.append(request)
            raise URLError("SECRET signed url and key must never be persisted")

    from hixton.live.exchange import BinanceSpotExchange

    order, journal = _live_fixture(tmp_path)
    opener = FailedClock()
    adapter = BinanceSpotExchange(
        transport(opener), account_fingerprint="account-fixture", quote_asset="USDC"
    )
    executor = LiveOrderExecutor(journal, adapter, lambda _: True)
    assert executor.execute(order.intent_id) == "CREATED"
    assert [request.get_method() for request in opener.requests] == ["GET"]
    assert _live_diagnostic(journal, order)["definitely_not_submitted"] is True
    executor.pre_submit = lambda _: False
    assert executor.execute(order.intent_id) == "BLOCKED"
    assert len(opener.requests) == 1
    assert b"SECRET" not in journal.path.read_bytes()


def test_live_error_redaction_ignores_untrusted_exception_fields(tmp_path):
    order, journal = _live_fixture(tmp_path)
    error = RuntimeError("SECRET https://signed.invalid?signature=SECRET")
    error.stage = "SECRET"
    error.code = "SECRET"
    error.http_status = "SECRET"
    journal.record_request_error(order.intent_id, error, "RECONCILE")
    detail = _live_diagnostic(journal, order)
    assert detail["stage"] == "RECONCILE"
    assert detail["code"] is None and detail["http_status"] is None
    assert "SECRET" not in json.dumps(detail)
    assert b"SECRET" not in journal.path.read_bytes()


@pytest.mark.parametrize("kind", ["trial", "live"])
@pytest.mark.parametrize("field", ["executed_quantity", "cumulative_quote"])
def test_aggregate_execution_evidence_blocks_clock_claim_release(tmp_path, kind, field):
    if kind == "trial":
        order = intent()
        journal = OrderJournal(tmp_path / "trial.sqlite3")
        journal.create(order)
    else:
        order, journal = _live_fixture(tmp_path)
    journal.claim_submit(order.intent_id)
    with journal._connect() as connection:
        connection.execute(
            f"UPDATE {kind}_intents SET {field}='0.1' WHERE intent_id=?", (order.intent_id,)
        )
    failure = ExchangeRequestError(definitely_not_submitted=True, stage="CLOCK_SYNC")
    journal.record_request_error(order.intent_id, failure, "ORDER_SUBMIT")
    assert not journal.release_not_submitted(order.intent_id)
    assert journal.load(order.intent_id)[1] == "SUBMITTING"
