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
from pathlib import Path

from hixton.backtest.availability import audit_observed, global_gap_hours
from hixton.backtest.models import ExecutionRules
from hixton.data.binance import BinanceApiError, BinancePublicClient
from hixton.data.storage import CandleStore
from hixton.data.sync import _missing_ranges
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
    requested_years: int = 3
    gap_hours: tuple[datetime, ...] = ()


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
    native_database_path: Path | None = None,
    cache_path: Path | None = None,
    requested_years: int = 3,
) -> ContinuityHistory:
    """Load the selected fixed market window for the active USDC strategy.

    Only market candles use the USDT proxy. Strategy parameters, symbol identity,
    portfolio/risk state, cost model and exchange rules remain those of the
    active USDC system.
    """

    if type(requested_years) is not int or requested_years not in (3, 5):
        raise ValueError("Backtest duration must be 3 or 5 years")
    allow_late = requested_years == 5
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

    def fetch_history(symbol: str, start: datetime, end: datetime) -> list[Candle]:
        if cache_path is None:
            return public.fetch_klines(symbol, start=start, end_exclusive=end)
        # Historical storage is separate from Paper/Live candles and accounts.
        with CandleStore(cache_path) as cache:
            missing = _missing_ranges(
                cache.load_open_times(symbol, start=start, end_exclusive=end),
                start=start,
                end_exclusive=end,
            )
            for missing_start, missing_end in missing:
                cache.put_candles(
                    public.fetch_klines(symbol, start=missing_start, end_exclusive=missing_end)
                )
            return cache.load_candles(symbol, start=start, end_exclusive=end)

    for target_symbol in symbols:
        market_proxy = proxy_symbol(target_symbol)
        native: list[Candle] = []
        if native_database_path is not None:
            with CandleStore(native_database_path, read_only=True) as store:
                native = store.load_candles(
                    target_symbol, start=warmup_start, end_exclusive=report_end_utc
                )
            if native:
                if allow_late and native[-1].open_time_utc + BAR < report_end_utc:
                    # An offline bot may lag behind the click's closed hour.
                    # Fetch real USDC bars into backtest storage only.
                    native += fetch_history(
                        target_symbol, native[-1].open_time_utc + BAR, report_end_utc
                    )
                audit_observed(
                    native,
                    target_symbol,
                    native[0].open_time_utc,
                    report_end_utc,
                    allow_gaps=allow_late,
                )
        proxy_end = native[0].open_time_utc if native else report_end_utc
        proxy_candles: list[Candle] = []
        proxy_start = warmup_start
        if allow_late and proxy_start < proxy_end:
            try:
                proxy_start = public.first_available_open(
                    market_proxy, start=proxy_start, end_exclusive=proxy_end
                )
            except BinanceApiError as error:
                # Only a successful empty provider response denotes no history.
                # Transport/API failures remain errors, never invented listing gaps.
                if str(error) != f"{market_proxy}: no first available hourly candle":
                    raise
                proxy_start = proxy_end
        if proxy_start < proxy_end:
            proxy_candles = fetch_history(market_proxy, proxy_start, proxy_end)
        if proxy_start < proxy_end and (
            not proxy_candles or proxy_candles[0].open_time_utc != proxy_start
        ):
            raise ValueError(f"{market_proxy}: full three-year proxy warm-up is unavailable")
        expected_last = report_end_utc - BAR
        adapted = [
            replace(
                candle,
                symbol=target_symbol,
                source="binance_spot_usdt_market_proxy_for_usdc_backtest",
            )
            for candle in proxy_candles
        ] + native
        if not adapted and not allow_late:
            raise ValueError(f"{target_symbol}: history does not reach {expected_last.isoformat()}")
        if adapted:
            audit_observed(
                adapted,
                target_symbol,
                adapted[0].open_time_utc if allow_late else warmup_start,
                report_end_utc,
                allow_gaps=allow_late,
            )
        first = adapted[0].open_time_utc if adapted else None
        required_bars = strategy.parameters_for(target_symbol).warmup_bars
        tradable_from = (
            max(report_start_utc, adapted[required_bars - 1].open_time_utc + BAR)
            if len(adapted) >= required_bars
            else None
        )
        candles_by_symbol[target_symbol] = adapted
        provenance_by_symbol[target_symbol] = {
            "target_market": target_symbol,
            "market_proxy": market_proxy,
            "proxy_quote": PROXY_QUOTE,
            "target_quote": TARGET_QUOTE,
            "first_open_utc": first.isoformat() if first else None,
            "last_open_utc": adapted[-1].open_time_utc.isoformat() if adapted else None,
            "requested_report_start_utc": report_start_utc.isoformat(),
            "tradable_from_utc": tradable_from.isoformat() if tradable_from else None,
            "unavailable_until_utc": (
                min(tradable_from, report_end_utc).isoformat()
                if tradable_from and tradable_from > report_start_utc
                else report_end_utc.isoformat()
                if tradable_from is None
                else None
            ),
            "availability_note": (
                "NO_HISTORY"
                if not adapted
                else "INSUFFICIENT_WARMUP"
                if tradable_from is None
                else "LATE_HISTORY_AND_WARMUP"
                if first and first > warmup_start
                else "FULL_WINDOW"
            ),
            "candle_count": len(adapted),
            "execution_rules_from": target_symbol,
            "native_usdc_candle_count": len(native),
            "proxy_candle_count": len(proxy_candles),
            "native_usdc_first_open_utc": native[0].open_time_utc.isoformat() if native else None,
            "proxy_end_exclusive_utc": proxy_end.isoformat() if proxy_candles else None,
        }

    return ContinuityHistory(
        candles_by_symbol=candles_by_symbol,
        execution_rules=execution_rules,
        provenance_by_symbol=provenance_by_symbol,
        requested_years=requested_years,
        gap_hours=global_gap_hours(candles_by_symbol) if allow_late else (),
    )


def continuity_manifest_data(history: ContinuityHistory) -> dict[str, object]:
    """Machine-readable disclosure added to the immutable run manifest."""

    return {
        "history_mode": HISTORY_MODE if history.requested_years == 3 else "FIVE_YEAR_LISTING_AWARE",
        "purpose": "THREE_YEAR_STRATEGY_CONTINUITY"
        if history.requested_years == 3
        else "FIVE_YEAR_STRATEGY_CONTINUITY",
        "requested_years": history.requested_years,
        "missing_history_policy": "UNTRADABLE_UNTIL_REAL_HISTORY_AND_WARMUP",
        "invented_candles": False,
        "global_gap_hours_utc": [at.isoformat() for at in history.gap_hours],
        "gap_model": "GLOBAL_OUTAGE_OBSERVED_BARS_V1" if history.gap_hours else None,
        "gap_execution_assumption": (
            "NO_EXECUTION; ORIGINAL_PENDING_DEFERRED_TO_FIRST_COMPLETE_REAL_OPEN; "
            "LAST_OBSERVED_VALUATION; UNKNOWN_INTRAGAP_DRAWDOWN"
            if history.gap_hours
            else None
        ),
        "runtime_quote": TARGET_QUOTE,
        "market_proxy_quote": PROXY_QUOTE,
        "proxy_scope": "HISTORICAL_MARKET_CANDLES_ONLY",
        "paper_state_modified": False,
        "orders_sent": False,
        "historical_usdc_liquidity_claimed": False,
        "provenance_by_symbol": history.provenance_by_symbol,
        "note": (
            "Ein durchgehender Backtest der aktiven USDC-Strategie. Vorhandene USDC-Kerzen "
            "werden verwendet; historische USDT-Kerzen ergänzen ausschließlich fehlende "
            "ältere Historie, sofern native_usdc_candle_count dokumentiert ist. "
            "Strategie, Konto, Risiko, Kosten und aktuelle "
            "USDC-Ausfuehrungsregeln bleiben unveraendert."
            + (
                " Simulation mit Datenlückenmodell: Bei gemeinsamen fehlenden Stunden "
                "pausieren Indikatoren und Ausführung. Ursprüngliche Signale werden zum "
                "ersten vollständigen realen Open verschoben; Bewertungen stammen vom "
                "letzten beobachteten Close. Kursbewegungen, Ausführungen und Drawdowns "
                "innerhalb dieser Lücken sind unbekannt; keine vollständige historische "
                "Ausführungsparität."
                if history.gap_hours
                else ""
            )
        ),
    }
