"""Mock HTTP/exchange only. No real credentials, network or account orders."""

from __future__ import annotations

import hashlib
import hmac
import io
import json
from dataclasses import replace
from decimal import Decimal as D
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode

import pytest

from hixton.live.credentials import BinanceCredentials
from hixton.live.exchange import (
    BinanceSpotExchange,
    BinanceSpotTransport,
    ExchangeRequestError,
)
from hixton.live.orders import OrderJournal, TrialIntent, TrialOrderExecutor

KEY = "TESTONLY" * 8
SECRET = "NOTAREAL" * 8


def intent():
    return TrialIntent(
        "one-shot",
        "account-fixture",
        "SOLUSDC",
        "BUY",
        "test-profile",
        D("100"),
        quote_budget=D("50"),
    )


class ScriptedTransport:
    def __init__(self, order):
        self.calls = []
        self.order = order
        self.timeout_after_accept = False
        self.fill_rows = [
            {
                "symbol": order.symbol,
                "orderId": 123,
                "id": 456,
                "isBuyer": order.side == "BUY",
                "qty": "0.5",
                "price": "100",
                "quoteQty": "50",
                "commission": "0.0001",
                "commissionAsset": "BNB",
            }
        ]

    def request(self, method, path, params):
        self.calls.append((method, path, dict(params)))
        if path.endswith("myTrades"):
            return self.fill_rows
        response = {
            "symbol": self.order.symbol,
            "orderId": 123,
            "clientOrderId": self.order.client_order_id,
        }
        if method == "POST":
            if self.timeout_after_accept:
                raise TimeoutError("secret-containing text must never enter the journal")
            return response
        return {
            **response,
            "type": "MARKET",
            "side": self.order.side,
            "status": "FILLED",
            "executedQty": "0.5",
            "cummulativeQuoteQty": "50",
        }


def exchange(transport):
    return BinanceSpotExchange(transport, account_fingerprint="account-fixture", quote_asset="USDC")


def test_quote_budget_is_exact_not_base_quantity_and_fills_are_not_invented(tmp_path):
    order = intent()
    transport = ScriptedTransport(order)
    journal = OrderJournal(tmp_path / "orders.sqlite3")
    journal.create(order)
    executor = TrialOrderExecutor(journal, exchange(transport), lambda _: True)
    assert executor.execute(order.intent_id) == "FILLED"
    sent = transport.calls[0]
    assert sent == (
        "POST",
        "/api/v3/order",
        {
            "symbol": "SOLUSDC",
            "side": "BUY",
            "type": "MARKET",
            "newClientOrderId": order.client_order_id,
            "newOrderRespType": "ACK",
            "quoteOrderQty": "50.00",
        },
    )
    summary = journal.fill_summary(order.intent_id)
    assert summary["quote_asset"] == "USDC"
    assert summary["gross_quote"] == "50"
    assert summary["gross_quote_usdt"] is None
    assert summary["fees_by_asset"] == {"BNB": "0.0001"}
    assert not summary["fees_fully_valued_in_quote"]
    assert summary["fills"][0]["trade_id"] == "456"
    executor.execute(order.intent_id)
    assert sum(method == "POST" for method, _, _ in transport.calls) == 1


def test_accepted_buy_with_lost_response_recovers_once_after_restart(tmp_path):
    order = intent()
    transport = ScriptedTransport(order)
    transport.timeout_after_accept = True
    path = tmp_path / "orders.sqlite3"
    journal = OrderJournal(path)
    journal.create(order)
    assert (
        TrialOrderExecutor(journal, exchange(transport), lambda _: True).execute(order.intent_id)
        == "UNKNOWN"
    )
    restarted = TrialOrderExecutor(OrderJournal(path), exchange(transport), lambda _: False)
    assert restarted.execute(order.intent_id) == "FILLED"
    assert sum(method == "POST" for method, _, _ in transport.calls) == 1
    assert b"secret-containing" not in path.read_bytes()


def test_missing_order_never_becomes_permission_to_retry(tmp_path):
    order = intent()

    class Missing(ScriptedTransport):
        def request(self, method, path, params):
            self.calls.append((method, path, params))
            raise ExchangeRequestError(-2013, 400)

    transport = Missing(order)
    journal = OrderJournal(tmp_path / "orders.sqlite3")
    journal.create(order)
    journal.claim_submit(order.intent_id)
    executor = TrialOrderExecutor(journal, exchange(transport), lambda _: True)
    for _ in range(3):
        assert executor.execute(order.intent_id) == "UNKNOWN"
    assert all(call[0] == "GET" for call in transport.calls)


@pytest.mark.parametrize(
    "field,value",
    [
        ("symbol", "SOLUSDT"),
        ("account_fingerprint", "other-account"),
    ],
)
def test_no_implicit_quote_or_account_conversion(field, value):
    transport = ScriptedTransport(intent())
    with pytest.raises(ValueError, match="account/market"):
        exchange(transport).submit(replace(intent(), **{field: value}))
    assert not transport.calls


@pytest.mark.parametrize(
    "field,value",
    [
        ("symbol", "BTCUSDC"),
        ("orderId", 999),
        ("id", -1),
        ("isBuyer", False),
        ("qty", "NaN"),
        ("quoteQty", "Infinity"),
        ("commissionAsset", ""),
    ],
)
def test_foreign_or_corrupt_fill_never_booked(tmp_path, field, value):
    order = intent()
    transport = ScriptedTransport(order)
    transport.fill_rows[0][field] = value
    journal = OrderJournal(tmp_path / "orders.sqlite3")
    journal.create(order)
    result = TrialOrderExecutor(journal, exchange(transport), lambda _: True).execute(
        order.intent_id
    )
    assert result == "UNKNOWN"
    assert journal.fill_summary(order.intent_id)["fill_count"] == 0


def test_ack_without_trade_rows_waits_for_fill_details(tmp_path):
    order = intent()
    transport = ScriptedTransport(order)
    fills = transport.fill_rows
    transport.fill_rows = []
    journal = OrderJournal(tmp_path / "orders.sqlite3")
    journal.create(order)
    executor = TrialOrderExecutor(journal, exchange(transport), lambda _: True)
    assert executor.execute(order.intent_id) == "FILL_DETAILS_PENDING"
    transport.fill_rows = fills
    assert executor.execute(order.intent_id) == "FILLED"
    assert sum(method == "POST" for method, _, _ in transport.calls) == 1


def test_sell_only_sends_explicit_owned_quantity():
    order = replace(intent(), side="SELL", quote_budget=D(0), base_quantity=D("0.5"))
    transport = ScriptedTransport(order)
    exchange(transport).submit(order)
    sent = transport.calls[0][2]
    assert sent["quantity"] == "0.5"
    assert "quoteOrderQty" not in sent


class Response(io.BytesIO):
    pass


class FakeOpener:
    def __init__(self, fail=None):
        self.requests = []
        self.fail = fail

    def open(self, request, timeout):
        self.requests.append(request)
        assert timeout == 10
        if request.full_url.endswith("/time"):
            return Response(b'{"serverTime":1000000}')
        if self.fail:
            raise self.fail
        return Response(b"{}")


def transport(opener):
    result = BinanceSpotTransport(
        BinanceCredentials(KEY, SECRET),
        base_url="https://testnet.binance.vision",
        clock=lambda: 1000,
    )
    result._opener = opener
    return result


def test_signed_post_body_exact_and_no_api_header_on_public_clock():
    opener = FakeOpener()
    client = transport(opener)
    client.request("POST", "/api/v3/order", {"symbol": "SOLUSDC", "quoteOrderQty": "50.00"})
    public, private = opener.requests
    assert public.get_header("X-mbx-apikey") is None
    assert "?" not in private.full_url
    assert private.get_header("X-mbx-apikey") == KEY
    values = {k: v[0] for k, v in parse_qs(private.data.decode()).items()}
    signature = values.pop("signature")
    assert values["quoteOrderQty"] == "50.00" and values["recvWindow"] == "5000"
    assert (
        signature
        == hmac.new(SECRET.encode(), urlencode(values).encode(), hashlib.sha256).hexdigest()
    )


@pytest.mark.parametrize(
    "failure",
    [
        URLError("API key and signature must not be echoed"),
        HTTPError(
            "https://secret-url.invalid",
            400,
            "secret-message",
            {},
            io.BytesIO(json.dumps({"code": -2015, "msg": SECRET}).encode()),
        ),
    ],
)
def test_transport_failure_has_no_retry_or_secret_echo(failure):
    opener = FakeOpener(failure)
    with pytest.raises(ExchangeRequestError) as captured:
        transport(opener).request("POST", "/api/v3/order", {})
    assert len(opener.requests) == 2  # one clock request, one POST, no retry
    assert SECRET not in str(captured.value)
    assert "secret-url" not in str(captured.value)
    assert "secret-message" not in str(captured.value)


def test_transport_refuses_alternative_hosts_and_mutating_endpoints():
    with pytest.raises(ValueError):
        BinanceSpotTransport(BinanceCredentials(KEY, SECRET), base_url="http://api.binance.com")
    opener = FakeOpener()
    client = transport(opener)
    for method, path in [
        ("POST", "/sapi/v1/capital/withdraw/apply"),
        ("DELETE", "/api/v3/openOrders"),
        ("GET", "/api/v3/unknown"),
    ]:
        with pytest.raises(ValueError):
            client.request(method, path, {})
    assert not opener.requests
