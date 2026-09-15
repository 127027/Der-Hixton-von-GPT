"""Read-only Binance Spot REST adapter for metadata, server time and 1h klines."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from hixton.constants import TIMEFRAME
from hixton.domain.models import Candle

_INTERVAL_MS = 3_600_000


class BinanceApiError(RuntimeError):
    """Public API request or response failure."""


def parse_websocket_kline(value: object) -> Candle:
    """Parse one Binance combined-stream 1h kline event."""

    if not isinstance(value, dict):
        raise BinanceApiError("websocket payload has unexpected shape")
    data = value.get("data", value)
    if not isinstance(data, dict) or data.get("e") != "kline":
        raise BinanceApiError("websocket payload is not a kline event")
    raw_kline = data.get("k")
    if not isinstance(raw_kline, dict) or raw_kline.get("i") != TIMEFRAME:
        raise BinanceApiError("websocket kline has unexpected shape or interval")
    try:
        open_ms = int(raw_kline["t"])
        close_ms = int(raw_kline["T"])
        return Candle(
            symbol=str(raw_kline["s"]),
            open_time_utc=datetime.fromtimestamp(open_ms / 1_000, tz=UTC),
            close_time_utc=datetime.fromtimestamp(close_ms / 1_000, tz=UTC),
            open=float(raw_kline["o"]),
            high=float(raw_kline["h"]),
            low=float(raw_kline["l"]),
            close=float(raw_kline["c"]),
            volume=float(raw_kline["v"]),
            quote_volume=float(raw_kline["q"]),
            trade_count=int(raw_kline["n"]),
            closed=bool(raw_kline["x"]),
            source="binance_spot_stream",
        )
    except (KeyError, TypeError, ValueError) as error:
        raise BinanceApiError("websocket kline fields are invalid") from error


@dataclass(frozen=True, slots=True)
class SymbolRules:
    symbol: str
    status: str
    base_asset: str
    quote_asset: str
    spot_allowed: bool
    order_types: tuple[str, ...]
    tick_size: Decimal
    step_size: Decimal
    min_qty: Decimal
    min_notional: Decimal

    @property
    def tradable_for_v1(self) -> bool:
        return self.tradable_for_quote("USDC")

    def tradable_for_quote(self, quote_asset: str) -> bool:
        return (
            self.status == "TRADING"
            and quote_asset in {"USDC"}
            and self.quote_asset == quote_asset
            and self.symbol == self.base_asset + quote_asset
            and self.spot_allowed
            and "MARKET" in self.order_types
        )


class BinancePublicClient:
    """Small dependency-free client; it contains no private trading methods."""

    def __init__(
        self,
        *,
        base_url: str = "https://api.binance.com",
        timeout_seconds: float = 15.0,
        max_attempts: int = 5,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts

    def server_time(self) -> datetime:
        payload = self._request_json("/api/v3/time")
        if not isinstance(payload, dict) or "serverTime" not in payload:
            raise BinanceApiError("server-time response has unexpected shape")
        return datetime.fromtimestamp(int(payload["serverTime"]) / 1_000, tz=UTC)

    def symbol_rules(self, symbol: str) -> SymbolRules:
        normalized = symbol.replace("/", "").upper()
        payload = self._request_json("/api/v3/exchangeInfo", {"symbol": normalized})
        if not isinstance(payload, dict):
            raise BinanceApiError("exchangeInfo response has unexpected shape")
        symbols = payload.get("symbols")
        if not isinstance(symbols, list) or len(symbols) != 1:
            raise BinanceApiError(f"exchangeInfo did not return exactly one symbol: {normalized}")
        raw_item = symbols[0]
        if not isinstance(raw_item, dict):
            raise BinanceApiError("exchangeInfo symbol entry has unexpected shape")
        item: dict[str, Any] = raw_item
        raw_filters = item.get("filters", [])
        if not isinstance(raw_filters, list):
            raise BinanceApiError("exchangeInfo filters have unexpected shape")
        filters: dict[str, dict[str, Any]] = {}
        for raw_filter in raw_filters:
            if not isinstance(raw_filter, dict) or "filterType" not in raw_filter:
                raise BinanceApiError("exchangeInfo filter has unexpected shape")
            filters[str(raw_filter["filterType"])] = raw_filter
        price_filter = filters.get("PRICE_FILTER", {})
        lot_filter = filters.get("LOT_SIZE", {})
        notional_filter = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL") or {}
        return SymbolRules(
            symbol=normalized,
            status=str(item.get("status", "")),
            base_asset=str(item.get("baseAsset", "")),
            quote_asset=str(item.get("quoteAsset", "")),
            spot_allowed=bool(item.get("isSpotTradingAllowed", False)),
            order_types=tuple(str(value) for value in item.get("orderTypes", [])),
            tick_size=Decimal(str(price_filter.get("tickSize", "0"))),
            step_size=Decimal(str(lot_filter.get("stepSize", "0"))),
            min_qty=Decimal(str(lot_filter.get("minQty", "0"))),
            min_notional=Decimal(str(notional_filter.get("minNotional", "0"))),
        )

    def first_available_open(
        self, symbol: str, *, start: datetime, end_exclusive: datetime
    ) -> datetime:
        """Ask the provider for its first real bar in the requested history.

        This is data availability, not proof of an original listing date. A
        shorter prefix is reported; internal gaps still fail the normal audit.
        """
        payload = self._request_json(
            "/api/v3/klines",
            {
                "symbol": symbol,
                "interval": "1h",
                "timeZone": "0",
                "limit": 1,
                "startTime": int(start.timestamp() * 1000),
                "endTime": int(end_exclusive.timestamp() * 1000) - 1,
            },
        )
        if not isinstance(payload, list) or len(payload) != 1:
            raise BinanceApiError(f"{symbol}: no first available hourly candle")
        candle = self._parse_kline(symbol, payload[0], int(end_exclusive.timestamp() * 1000))
        if not candle.ohlc_is_valid or not start <= candle.open_time_utc < end_exclusive:
            raise BinanceApiError(f"{symbol}: invalid first available candle")
        return candle.open_time_utc

    def fetch_klines(
        self,
        symbol: str,
        *,
        start: datetime,
        end_exclusive: datetime,
        interval: str = TIMEFRAME,
    ) -> list[Candle]:
        if interval != "1h":
            raise ValueError("DMS V1 market-data adapter supports only 1h")
        normalized = symbol.replace("/", "").upper()
        start_ms = int(start.astimezone(UTC).timestamp() * 1_000)
        end_ms = int(end_exclusive.astimezone(UTC).timestamp() * 1_000)
        if start_ms >= end_ms:
            raise ValueError("start must be before end_exclusive")
        server_ms = int(self.server_time().timestamp() * 1_000)
        cursor = start_ms
        candles: list[Candle] = []
        while cursor < end_ms:
            payload = self._request_json(
                "/api/v3/klines",
                {
                    "symbol": normalized,
                    "interval": interval,
                    "startTime": cursor,
                    "endTime": end_ms - 1,
                    "limit": 1_000,
                    "timeZone": "0",
                },
            )
            if not isinstance(payload, list):
                raise BinanceApiError("klines response has unexpected shape")
            if not payload:
                break
            page = [self._parse_kline(normalized, row, server_ms) for row in payload]
            for candle in page:
                if start_ms <= int(candle.open_time_utc.timestamp() * 1_000) < end_ms:
                    candles.append(candle)
            last_open_ms = int(page[-1].open_time_utc.timestamp() * 1_000)
            next_cursor = last_open_ms + _INTERVAL_MS
            if next_cursor <= cursor:
                raise BinanceApiError("kline pagination did not advance")
            cursor = next_cursor
            if len(page) < 1_000:
                break
        return candles

    def _request_json(
        self,
        path: str,
        parameters: dict[str, object] | None = None,
    ) -> object:
        query = f"?{urlencode(parameters)}" if parameters else ""
        url = f"{self.base_url}{path}{query}"
        request = Request(url, headers={"User-Agent": "Der-Hixton/0.1 public-market-data"})
        for attempt in range(1, self.max_attempts + 1):
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as error:
                retryable = error.code in {418, 429} or 500 <= error.code < 600
                if not retryable or attempt == self.max_attempts:
                    body = error.read().decode("utf-8", errors="replace")[:500]
                    raise BinanceApiError(f"Binance HTTP {error.code}: {body}") from error
                retry_after = error.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else min(2 ** (attempt - 1), 16)
            except (TimeoutError, URLError) as error:
                if attempt == self.max_attempts:
                    raise BinanceApiError(f"Binance request failed: {error}") from error
                delay = min(2 ** (attempt - 1), 16)
            time.sleep(delay)
        raise AssertionError("retry loop exhausted without result")

    @staticmethod
    def _parse_kline(symbol: str, value: object, server_ms: int) -> Candle:
        if not isinstance(value, list) or len(value) != 12:
            raise BinanceApiError("kline row has unexpected shape")
        open_ms = int(value[0])
        close_ms = int(value[6])
        return Candle(
            symbol=symbol,
            open_time_utc=datetime.fromtimestamp(open_ms / 1_000, tz=UTC),
            close_time_utc=datetime.fromtimestamp(close_ms / 1_000, tz=UTC),
            open=float(value[1]),
            high=float(value[2]),
            low=float(value[3]),
            close=float(value[4]),
            volume=float(value[5]),
            quote_volume=float(value[7]),
            trade_count=int(value[8]),
            closed=close_ms < server_ms,
            source="binance_spot",
        )
