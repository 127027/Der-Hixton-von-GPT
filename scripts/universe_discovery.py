"""Discover additional Binance USDC spot markets for autonomous research.

This is a nomination step only. It uses public exchange metadata and 24h
liquidity as a cheap first screen, then checks whether at least the current
three-year research start is available. Nominated markets are NOT added to Live.
"""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from hixton.data.binance import BinanceApiError, BinancePublicClient
from hixton.domain.versions import V6_COIN_STRATEGY
from hixton.runtime.supervisor import safe_closed_window

MAX_HISTORY_CHECKS = 30
MAX_NOMINATIONS = 15
MIN_24H_QUOTE_VOLUME_USDC = Decimal("1000000")


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def evaluate() -> dict[str, object]:
    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    exchange = client._request_json("/api/v3/exchangeInfo")  # public research endpoint
    tickers = client._request_json("/api/v3/ticker/24hr")
    if not isinstance(exchange, dict) or not isinstance(exchange.get("symbols"), list):
        raise RuntimeError("Binance exchangeInfo shape unexpected")
    if not isinstance(tickers, list):
        raise RuntimeError("Binance 24h ticker shape unexpected")

    ticker_by_symbol = {
        str(row.get("symbol")): row for row in tickers if isinstance(row, dict)
    }
    current = set(V6_COIN_STRATEGY.symbols)
    raw: list[dict[str, object]] = []
    for item in exchange["symbols"]:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol", ""))
        quote = str(item.get("quoteAsset", ""))
        base = str(item.get("baseAsset", ""))
        order_types = {str(x) for x in item.get("orderTypes", [])}
        if (
            quote != "USDC"
            or item.get("status") != "TRADING"
            or not bool(item.get("isSpotTradingAllowed", False))
            or "MARKET" not in order_types
            or symbol in current
        ):
            continue
        ticker = ticker_by_symbol.get(symbol, {})
        quote_volume = _decimal(ticker.get("quoteVolume", "0"))
        if quote_volume < MIN_24H_QUOTE_VOLUME_USDC:
            continue
        raw.append(
            {
                "symbol": symbol,
                "base_asset": base,
                "quote_asset": quote,
                "quote_volume_24h_usdc": str(quote_volume),
                "trade_count_24h": int(ticker.get("count", 0) or 0),
                "last_price": str(ticker.get("lastPrice", "")),
            }
        )

    raw.sort(
        key=lambda row: (
            _decimal(row["quote_volume_24h_usdc"]),
            int(row["trade_count_24h"]),
        ),
        reverse=True,
    )

    _, report_start, report_end = safe_closed_window()
    warmup_start = report_start - timedelta(hours=400)
    checked: list[dict[str, object]] = []
    for row in raw[:MAX_HISTORY_CHECKS]:
        symbol = str(row["symbol"])
        history_ok = False
        first_open = None
        error = None
        try:
            first = client.first_available_open(
                symbol,
                start=warmup_start,
                end_exclusive=warmup_start + timedelta(days=7),
            )
            first_open = first.isoformat()
            history_ok = first <= warmup_start + timedelta(hours=1)
        except BinanceApiError as exc:
            error = str(exc)
        checked.append(
            {
                **row,
                "required_history_start_utc": warmup_start.isoformat(),
                "first_available_near_required_start_utc": first_open,
                "three_year_plus_warmup_available": history_ok,
                "history_probe_error": error,
            }
        )

    nominations = [
        row for row in checked if row["three_year_plus_warmup_available"]
    ][:MAX_NOMINATIONS]
    return {
        "schema_version": 1,
        "study": "BINANCE_USDC_UNIVERSE_DISCOVERY",
        "research_only": True,
        "activation_performed": False,
        "current_universe": list(V6_COIN_STRATEGY.symbols),
        "minimum_24h_quote_volume_usdc": str(MIN_24H_QUOTE_VOLUME_USDC),
        "screened_liquid_noncore_markets": len(raw),
        "history_checked": len(checked),
        "nominations": nominations,
        "checked": checked,
        "next_gate": (
            "For each nomination run isolated three-year research, then marginal "
            "shared-portfolio baseline/stress and cross-window contribution. "
            "No symbol joins Live from this discovery step."
        ),
    }


def main() -> None:
    result=evaluate()
    out=Path("evidence/universe-discovery.json")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="checked"},indent=2))


if __name__=="__main__":
    main()
