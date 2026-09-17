"""Historical market adapter for one continuous V6 USDC strategy backtest.

Paper and future Live execution remain USDC-only. The adapter exists only for
historical simulation: where a three-year USDC history is unavailable, the
corresponding public Binance USDT market supplies the base-asset price path.
Candles are relabelled to the active USDC symbol before entering the unchanged
strategy/backtest engine. Current USDC exchange rules are applied separately by
the caller.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from hixton.backtest.models import ExecutionRules
from hixton.data.binance import BinancePublicClient
from hixton.data.quality import audit_candles
from hixton.domain.models import Candle
from hixton.domain.versions import StrategyDefinition

HISTORY_MODE = "THREE_YEAR_SCHEMA_F_CONTINUITY"
PROXY_QUOTE = "USDT"
TARGET_QUOTE = "USDC"
BINANCE_PUBLIC_HISTORY_URL = "https://data-api.binance.vision"
BAR = timedelta(hours=1)


@dataclass(frozen=True)
class ContinuityHistory:
    """Immutable backtest-only candle/rule package with explicit provenance."""

    candles_by_symbol: dict[str, list[Candle]]
    execution_rules: dict[str, ExecutionRules]
    provenance_by_symbol: dict[str, dict[str, object]]


def proxy_symbol(usdc_symbol: str) -> str:
    if not usdc_symbol.endswith(TARGET_QUOTE):
        raise ValueError(f"continuity adapter requires USDC target symbol: {usdc_symbol}")
    return f"{usdc_symbol.removesuffix(TARGET_QUOTE)}{PROXY_QUOTE}"


def continuity_symbols(strategy: StrategyDefinition) -> tuple[str, ...]:
    symbols = tuple(profile.symbol for profile in strategy.coin_profiles)
    if not symbols:
        raise ValueError("continuity adapter requires coin profiles")
    if any(not symbol.endswith(TARGET_QUOTE) for symbol in symbols):
        raise ValueError(f"continuity adapter requires USDC strategy symbols: {symbols}")
    return symbols


def load_continuity_history(
    *,
    strategy: StrategyDefinition,
    report_start_utc: datetime,
    report_end_utc: datetime,
    execution_rules: dict[str, ExecutionRules],
    client: BinancePublicClient | None = None,
) -> ContinuityHistory:
    """Load one continuous three-year market path for the active USDC strategy.

    Only market candles use the USDT proxy. Strategy parameters, symbol identity,
    portfolio/risk state, cost model and exchange rules remain those of the
    active USDC system.
    """

    symbols = continuity_symbols(strategy)
    if set(execution_rules) != set(symbols):
        raise ValueError("continuity execution rules must match active USDC symbols exactly")
    if report_start_utc >= report_end_utc:
        raise ValueError("continuity report start must precede report end")

    warmup_bars = max(strategy.parameters_for(symbol).warmup_bars for symbol in symbols)
    warmup_start = report_start_utc - warmup_bars * BAR
    public = client or BinancePublicClient(base_url=BINANCE_PUBLIC_HISTORY_URL)
    candles_by_symbol: dict[str, list[Candle]] = {}
    provenance_by_symbol: dict[str, dict[str, object]] = {}

    for target_symbol in symbols:
        market_proxy = proxy_symbol(target_symbol)
        proxy_candles = public.fetch_klines(
            market_proxy,
            start=warmup_start,
            end_exclusive=report_end_utc,
        )
        if not proxy_candles or proxy_candles[0].open_time_utc != warmup_start:
            raise ValueError(f"{market_proxy}: full three-year proxy warm-up is unavailable")
        expected_last = report_end_utc - BAR
        if proxy_candles[-1].open_time_utc != expected_last:
            raise ValueError(
                f"{market_proxy}: proxy history ends at "
                f"{proxy_candles[-1].open_time_utc.isoformat()}, expected {expected_last.isoformat()}"
            )
        adapted = [
            replace(
                candle,
                symbol=target_symbol,
                source="binance_spot_usdt_market_proxy_for_usdc_backtest",
            )
            for candle in proxy_candles
        ]
        audit_candles(
            adapted,
            expected_symbol=target_symbol,
            expected_start=warmup_start,
            expected_end_exclusive=report_end_utc,
        ).require_valid()
        candles_by_symbol[target_symbol] = adapted
        provenance_by_symbol[target_symbol] = {
            "target_market": target_symbol,
            "market_proxy": market_proxy,
            "proxy_quote": PROXY_QUOTE,
            "target_quote": TARGET_QUOTE,
            "first_open_utc": adapted[0].open_time_utc.isoformat(),
            "last_open_utc": adapted[-1].open_time_utc.isoformat(),
            "candle_count": len(adapted),
            "execution_rules_from": target_symbol,
        }

    return ContinuityHistory(
        candles_by_symbol=candles_by_symbol,
        execution_rules=execution_rules,
        provenance_by_symbol=provenance_by_symbol,
    )


def continuity_manifest_data(history: ContinuityHistory) -> dict[str, object]:
    """Machine-readable disclosure added to the immutable run manifest."""

    return {
        "history_mode": HISTORY_MODE,
        "purpose": "THREE_YEAR_STRATEGY_CONTINUITY",
        "runtime_quote": TARGET_QUOTE,
        "market_proxy_quote": PROXY_QUOTE,
        "proxy_scope": "HISTORICAL_MARKET_CANDLES_ONLY",
        "paper_state_modified": False,
        "orders_sent": False,
        "historical_usdc_liquidity_claimed": False,
        "provenance_by_symbol": history.provenance_by_symbol,
        "note": (
            "Ein durchgehender Backtest der aktiven USDC-Strategie. Historische USDT-Kerzen "
            "liefern nur den Basis-Marktpfad; Strategie, Konto, Risiko, Kosten und aktuelle "
            "USDC-Ausfuehrungsregeln bleiben unveraendert."
        ),
    }
