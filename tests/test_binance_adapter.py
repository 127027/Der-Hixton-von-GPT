from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from hixton.data.binance import BinanceApiError, BinancePublicClient, parse_websocket_kline


class StubBinance(BinancePublicClient):
    def __init__(self, responses: list[object]) -> None:
        super().__init__()
        self.responses = responses
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def _request_json(
        self, path: str, parameters: dict[str, object] | None = None
    ) -> object:
        self.calls.append((path, parameters))
        return self.responses.pop(0)


def _kline(open_ms: int, close: str = "101.0") -> list[Any]:
    return [
        open_ms,
        "100.0",
        "102.0",
        "99.0",
        close,
        "12.5",
        open_ms + 3_599_999,
        "1262.5",
        42,
        "6.0",
        "606.0",
        "0",
    ]


def test_symbol_rules_parse_required_binance_filters() -> None:
    response = {
        "symbols": [
            {
                "symbol": "ETHUSDC",
                "status": "TRADING",
                "baseAsset": "ETH",
                "quoteAsset": "USDC",
                "isSpotTradingAllowed": True,
                "orderTypes": ["LIMIT", "MARKET"],
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.01000000"},
                    {
                        "filterType": "LOT_SIZE",
                        "stepSize": "0.00010000",
                        "minQty": "0.00010000",
                    },
                    {"filterType": "NOTIONAL", "minNotional": "5.00000000"},
                ],
            }
        ]
    }
    client = StubBinance([response])
    rules = client.symbol_rules("ETH/USDC")
    assert rules.tradable_for_v1
    assert str(rules.tick_size) == "0.01000000"
    assert str(rules.step_size) == "0.00010000"
    assert str(rules.min_notional) == "5.00000000"


def test_kline_download_uses_utc_and_marks_final_bars() -> None:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    start_ms = int(start.timestamp() * 1_000)
    server_ms = start_ms + 10 * 3_600_000
    client = StubBinance(
        [
            {"serverTime": server_ms},
            [_kline(start_ms), _kline(start_ms + 3_600_000, "102.0")],
        ]
    )
    candles = client.fetch_klines(
        "BTCUSDC", start=start, end_exclusive=start + timedelta(hours=2)
    )
    assert len(candles) == 2
    assert all(candle.closed for candle in candles)
    assert candles[1].close == 102.0
    assert client.calls[1][0] == "/api/v3/klines"
    assert client.calls[1][1] is not None
    assert client.calls[1][1]["timeZone"] == "0"


def test_bad_kline_shape_is_rejected() -> None:
    with pytest.raises(BinanceApiError, match="shape"):
        BinancePublicClient._parse_kline("BTCUSDC", [1, 2], server_ms=3)


def test_websocket_kline_preserves_provisional_status() -> None:
    payload = {
        "stream": "btcusdc@kline_1h",
        "data": {
            "e": "kline",
            "k": {
                "t": 1_700_000_000_000,
                "T": 1_700_003_599_999,
                "s": "BTCUSDC",
                "i": "1h",
                "o": "100.0",
                "h": "102.0",
                "l": "99.0",
                "c": "101.0",
                "v": "12.5",
                "q": "1250.0",
                "n": 42,
                "x": False,
            },
        },
    }
    candle = parse_websocket_kline(payload)
    assert candle.symbol == "BTCUSDC"
    assert candle.closed is False
    assert candle.source == "binance_spot_stream"
