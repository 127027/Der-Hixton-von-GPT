"""Discover mature Binance USDC markets for the idle-satellite layer.

A satellite must be tradable as USDC Spot now. When the USDC pair itself is too new
for a full three-year study, a long-lived Binance USDT pair may be used only as a
research history proxy. At least one year of the real USDC pair is still required as
an independent holdout before a market can advance. Regional account availability is
always a later fail-closed Live gate.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from hixton.data.binance import BinanceApiError, BinancePublicClient
from hixton.domain.versions import V6_COIN_STRATEGY
from hixton.runtime.supervisor import safe_closed_window

MIN_24H_QUOTE_VOLUME_USDC = Decimal("1000000")
MIN_REAL_USDC_HOLDOUT_DAYS = 365
MAX_CHECKS = 35
MAX_PROXY_ELIGIBLE = 15
HISTORY_EPOCH = datetime(2017, 1, 1, tzinfo=UTC)
EXCLUDED_BASE_ASSETS = {
    "USDC", "USDT", "FDUSD", "USD1", "USDP", "TUSD", "DAI", "EURI", "EUR", "U"
}


def _d(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _first_or_none(
    client: BinancePublicClient, symbol: str, *, start: datetime, end: datetime
) -> datetime | None:
    try:
        return client.first_available_open(symbol, start=start, end_exclusive=end)
    except BinanceApiError:
        return None


def main() -> None:
    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    exchange = client._request_json("/api/v3/exchangeInfo")
    tickers = client._request_json("/api/v3/ticker/24hr")
    if not isinstance(exchange, dict) or not isinstance(exchange.get("symbols"), list):
        raise RuntimeError("unexpected Binance exchangeInfo")
    if not isinstance(tickers, list):
        raise RuntimeError("unexpected Binance ticker response")

    symbol_meta = {
        str(row.get("symbol")): row
        for row in exchange["symbols"]
        if isinstance(row, dict)
    }
    ticker_by_symbol = {
        str(row.get("symbol")): row for row in tickers if isinstance(row, dict)
    }
    core = set(V6_COIN_STRATEGY.symbols)
    raw: list[dict[str, object]] = []
    for symbol, item in symbol_meta.items():
        quote = str(item.get("quoteAsset", ""))
        base = str(item.get("baseAsset", ""))
        order_types = {str(x) for x in item.get("orderTypes", [])}
        if (
            symbol in core
            or quote != "USDC"
            or base in EXCLUDED_BASE_ASSETS
            or item.get("status") != "TRADING"
            or item.get("isSpotTradingAllowed") is not True
            or "MARKET" not in order_types
        ):
            continue
        ticker = ticker_by_symbol.get(symbol, {})
        volume = _d(ticker.get("quoteVolume", "0"))
        if volume < MIN_24H_QUOTE_VOLUME_USDC:
            continue
        raw.append(
            {
                "symbol": symbol,
                "base_asset": base,
                "quote_volume_24h_usdc": str(volume),
                "trade_count_24h": int(ticker.get("count", 0) or 0),
                "last_price": str(ticker.get("lastPrice", "")),
            }
        )

    raw.sort(
        key=lambda row: (
            _d(row["quote_volume_24h_usdc"]),
            int(row["trade_count_24h"]),
        ),
        reverse=True,
    )

    _, report_start, report_end = safe_closed_window()
    warmup_start = report_start - timedelta(hours=400)
    checked: list[dict[str, object]] = []
    for row in raw[:MAX_CHECKS]:
        symbol = str(row["symbol"])
        base = str(row["base_asset"])
        usdc_first = _first_or_none(
            client, symbol, start=HISTORY_EPOCH, end=report_end
        )
        usdc_days = (
            0 if usdc_first is None else int((report_end - usdc_first).total_seconds() // 86400)
        )
        direct_full = usdc_first is not None and usdc_first <= warmup_start + timedelta(hours=1)

        proxy_symbol = f"{base}USDT"
        proxy_meta = symbol_meta.get(proxy_symbol)
        proxy_spot = bool(
            isinstance(proxy_meta, dict)
            and proxy_meta.get("status") == "TRADING"
            and proxy_meta.get("isSpotTradingAllowed") is True
            and "MARKET" in {str(x) for x in proxy_meta.get("orderTypes", [])}
        )
        proxy_first_near_required = None
        proxy_full = False
        if proxy_spot:
            proxy_first_near_required = _first_or_none(
                client,
                proxy_symbol,
                start=warmup_start,
                end=warmup_start + timedelta(days=7),
            )
            proxy_full = (
                proxy_first_near_required is not None
                and proxy_first_near_required <= warmup_start + timedelta(hours=1)
            )

        real_holdout_ok = usdc_days >= MIN_REAL_USDC_HOLDOUT_DAYS
        proxy_eligible = direct_full or (proxy_full and real_holdout_ok)
        history_source = (
            symbol if direct_full else proxy_symbol if proxy_eligible else None
        )
        checked.append(
            {
                **row,
                "usdc_first_available_utc": (
                    None if usdc_first is None else usdc_first.isoformat()
                ),
                "real_usdc_history_days": usdc_days,
                "real_usdc_holdout_required_days": MIN_REAL_USDC_HOLDOUT_DAYS,
                "real_usdc_holdout_available": real_holdout_ok,
                "direct_three_year_usdc_history": direct_full,
                "proxy_symbol": proxy_symbol if proxy_spot else None,
                "proxy_three_year_history": proxy_full,
                "history_source_for_research": history_source,
                "satellite_history_eligible": proxy_eligible,
                "regional_account_availability_check_required": True,
            }
        )

    eligible = [r for r in checked if r["satellite_history_eligible"]]
    eligible.sort(
        key=lambda row: (
            _d(row["quote_volume_24h_usdc"]),
            int(row["real_usdc_history_days"]),
        ),
        reverse=True,
    )
    eligible = eligible[:MAX_PROXY_ELIGIBLE]

    output = {
        "schema_version": 1,
        "study": "IDLE_SATELLITE_UNIVERSE_DISCOVERY",
        "research_only": True,
        "activation_performed": False,
        "protected_core_symbols": list(V6_COIN_STRATEGY.symbols),
        "target_satellite_count": 5,
        "minimum_24h_quote_volume_usdc": str(MIN_24H_QUOTE_VOLUME_USDC),
        "minimum_real_usdc_holdout_days": MIN_REAL_USDC_HOLDOUT_DAYS,
        "screened_current_usdc_markets": len(raw),
        "history_checked": len(checked),
        "proxy_eligible_candidates": eligible,
        "checked": checked,
        "selection_rule": (
            "This step only establishes data/liquidity eligibility. The final five are "
            "selected later by incremental shared-portfolio profit earned during core-idle "
            "capacity after costs and forced core-handoff losses."
        ),
        "safety": {
            "core_priority_absolute": False,
            "no_live_addition_from_discovery": True,
            "regional_account_preflight_required": True,
            "proxy_history_cannot_replace_real_usdc_holdout": True,\n            "core_signal_alone_forces_exit": False,\n            "opportunity_router_required": True,
        },
    }
    out = Path("evidence/satellite-universe-discovery.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in output.items() if k != "checked"}, indent=2))


if __name__ == "__main__":
    main()
