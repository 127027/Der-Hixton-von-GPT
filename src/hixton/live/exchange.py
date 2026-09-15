"""Binance Spot one-shot transport, runtime-bound but production release-gated.

Only the journal executor may dispatch, after its mandatory safety gate. This
adapter does not establish consent, balance ownership, filter/price readiness or
an account reconciliation proof. It must not be used as a shortcut around them.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Callable
from decimal import Decimal
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

from hixton.domain.markets import symbols_for_quote
from hixton.live.binance import _NoRedirect
from hixton.live.credentials import BinanceCredentials
from hixton.live.orders import ExchangeFill, ExchangeOrder, TrialIntent

_BASES = {"https://api.binance.com", "https://testnet.binance.vision"}
_ALLOWLIST = {
    ("GET", "/api/v3/time"),
    ("GET", "/api/v3/order"),
    ("GET", "/api/v3/myTrades"),
    ("GET", "/api/v3/account"),
    ("GET", "/api/v3/openOrders"),
    ("POST", "/api/v3/order"),
}


class ExchangeRequestError(RuntimeError):
    """Redacted codes only; never includes a signed URL, key or server message."""

    def __init__(self, code: int | None = None, http_status: int | None = None) -> None:
        super().__init__(f"Binance order request unresolved (HTTP {http_status}, code {code})")
        self.code = code
        self.http_status = http_status


class SpotTransport(Protocol):
    def request(self, method: str, path: str, params: dict[str, str]) -> Any: ...


class BinanceSpotTransport:
    """Bounded HTTPS, fixed hosts/endpoints, NO automatic retries or redirects."""

    def __init__(
        self,
        credentials: BinanceCredentials,
        *,
        base_url: str,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if base_url not in _BASES:
            raise ValueError("Explicit Binance production or Spot-testnet host required")
        self._credentials = credentials
        self._base_url = base_url
        self._clock = clock
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())
        self._offset_ms = 0
        self._clock_checked_at: float | None = None

    def _synchronize(self) -> None:
        before = self._clock() * 1000
        result = self.request("GET", "/api/v3/time", {})
        after = self._clock() * 1000
        if (
            not isinstance(result, dict)
            or type(result.get("serverTime")) is not int
            or not 0 <= after - before <= 2000
        ):
            raise ExchangeRequestError()
        offset = result["serverTime"] - (before + after) / 2
        if abs(offset) > 1000:
            raise ExchangeRequestError()
        self._offset_ms = int(offset)
        self._clock_checked_at = self._clock()

    def request(self, method: str, path: str, params: dict[str, str]) -> Any:
        if (method, path) not in _ALLOWLIST:
            raise ValueError("Order transport endpoint/method is not allowlisted")
        public = path == "/api/v3/time"
        if not public and (
            self._clock_checked_at is None or not 0 <= self._clock() - self._clock_checked_at <= 30
        ):
            self._synchronize()
        query = dict(params)
        headers = {"Accept": "application/json", "User-Agent": "DerHixton-Trial"}
        if not public:
            if {"signature", "timestamp", "recvWindow"} & query.keys():
                raise ValueError("Signing fields are transport-owned")
            query.update(
                timestamp=str(int(self._clock() * 1000) + self._offset_ms), recvWindow="5000"
            )
            query["signature"] = hmac.new(
                self._credentials.secret_key.encode(), urlencode(query).encode(), hashlib.sha256
            ).hexdigest()
            headers["X-MBX-APIKEY"] = self._credentials.api_key
        encoded = urlencode(query)
        url = self._base_url + path
        data = None
        if method == "POST":
            # Signing material in the body, not a POST URL or access log.
            data = encoded.encode("ascii")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif encoded:
            url += "?" + encoded
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=10) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ExchangeRequestError()
                return json.loads(raw)
        except HTTPError as error:
            code = None
            try:
                body = json.loads(error.read(16_384))
                if isinstance(body, dict) and type(body.get("code")) is int:
                    code = body["code"]
            except (ValueError, OSError):
                pass
            raise ExchangeRequestError(code, error.code) from None
        except (URLError, OSError, ValueError):
            raise ExchangeRequestError() from None


def _decimal(value: Any) -> Decimal:
    if not isinstance(value, str):
        raise ValueError("Expected an exact-decimal Binance string")
    result = Decimal(value)
    if not result.is_finite() or result < 0:
        raise ValueError("Invalid Binance amount")
    return result


def _id(value: Any) -> str:
    if type(value) is not int or value < 0:
        raise ValueError("Invalid Binance numeric identity")
    return str(value)


class BinanceSpotExchange:
    """Exact 50-quote BUY; explicit owned SELL; restart lookup by durable ID.

    A quantity must already satisfy the current filters. Never silently round a
    persisted SELL intent or increase its amount to sell someone else's assets.
    No implicit market conversion: an USDT signal/order is not an USDC order.
    """

    def __init__(
        self,
        transport: SpotTransport,
        *,
        account_fingerprint: str,
        quote_asset: str,
    ) -> None:
        if not account_fingerprint:
            raise ValueError("Explicit credential identity required")
        self.transport = transport
        self.account_fingerprint = account_fingerprint
        self.symbols = symbols_for_quote(quote_asset)

    def _check(self, intent: TrialIntent) -> None:
        if (
            intent.account_fingerprint != self.account_fingerprint
            or intent.symbol not in self.symbols
        ):
            raise ValueError("Order account/market differs from the bound exchange")

    def _identity(self, intent: TrialIntent, data: Any) -> str:
        if (
            not isinstance(data, dict)
            or data.get("symbol") != intent.symbol
            or data.get("clientOrderId") != intent.client_order_id
        ):
            raise ValueError("Exchange acknowledgement identity mismatch")
        return _id(data.get("orderId"))

    def submit(self, intent: TrialIntent) -> ExchangeOrder:
        self._check(intent)
        params = {
            "symbol": intent.symbol,
            "side": intent.side,
            "type": "MARKET",
            "newClientOrderId": intent.client_order_id,
            "newOrderRespType": "ACK",
        }
        if intent.side == "BUY":
            params["quoteOrderQty"] = "50.00"
        else:
            params["quantity"] = format(intent.base_quantity, "f")
        ack = self.transport.request("POST", "/api/v3/order", params)
        order_id = self._identity(intent, ack)
        # ACK is not a fill. Lookup actual status and trade rows, including BNB
        # fees, rather than inventing a fill from the submitted 50-unit budget.
        order = self.query(intent)
        if order is None or order.order_id != order_id:
            raise ExchangeRequestError()
        return order

    def query(self, intent: TrialIntent) -> ExchangeOrder | None:
        self._check(intent)
        try:
            data = self.transport.request(
                "GET",
                "/api/v3/order",
                {"symbol": intent.symbol, "origClientOrderId": intent.client_order_id},
            )
        except ExchangeRequestError as error:
            if error.http_status == 400 and error.code == -2013:
                return None  # UNKNOWN, not permission to send the BUY again.
            raise
        order_id = self._identity(intent, data)
        if data.get("side") != intent.side or data.get("type") != "MARKET":
            raise ValueError("Queried order differs from intent side/type")
        quantity = _decimal(data.get("executedQty"))
        quote = _decimal(data.get("cummulativeQuoteQty"))
        fills = self._fills(intent, order_id) if quantity else ()
        return ExchangeOrder(
            intent.client_order_id,
            order_id,
            intent.symbol,
            intent.side,
            data.get("status"),
            quantity,
            quote,
            fills,
        )

    def _fills(self, intent: TrialIntent, order_id: str) -> tuple[ExchangeFill, ...]:
        params = {"symbol": intent.symbol, "orderId": order_id, "limit": "1000"}
        result: list[ExchangeFill] = []
        previous = -1
        # Bounded pagination. An incomplete response remains unresolved, never
        # terminal success. This normally needs just one page for a 50-unit trade.
        for _ in range(10):
            rows = self.transport.request("GET", "/api/v3/myTrades", params)
            if not isinstance(rows, list):
                raise ValueError("Invalid Binance fills response")
            for row in rows:
                if (
                    not isinstance(row, dict)
                    or row.get("symbol") != intent.symbol
                    or _id(row.get("orderId")) != order_id
                    or row.get("isBuyer") is not (intent.side == "BUY")
                ):
                    raise ValueError("Foreign or mismatched fill")
                identity = _id(row.get("id"))
                if int(identity) <= previous:
                    raise ValueError("Duplicate or regressing fill cursor")
                previous = int(identity)
                asset = row.get("commissionAsset")
                if not isinstance(asset, str) or not asset.isascii() or not asset.isalnum():
                    raise ValueError("Invalid commission asset")
                result.append(
                    ExchangeFill(
                        identity,
                        _decimal(row.get("qty")),
                        _decimal(row.get("price")),
                        _decimal(row.get("commission")),
                        asset,
                        _decimal(row.get("quoteQty")),
                    )
                )
            if len(rows) < 1000:
                return tuple(result)
            params["fromId"] = str(previous + 1)
        raise ValueError("Binance fill pagination limit; reconciliation remains incomplete")
