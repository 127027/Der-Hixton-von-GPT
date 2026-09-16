"""Fresh, read-only quote replay for the documented V6 strategy.

The script deliberately runs inside either the historical USDT checkout or the
current USDC checkout. It uses public Binance Spot data only, writes no Paper
state and sends no orders. The active runtime remains USDC-only.
"""

from __future__ import annotations

import argparse
import inspect
import json
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from hixton.backtest.engine import run_isolated_batch
from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.data.binance import BinancePublicClient
from hixton.data.quality import audit_candles
from hixton.domain.versions import V6_COIN_STRATEGY


BINANCE_PUBLIC_BASE_URL = "https://data-api.binance.vision"
WARMUP_BARS = 400
BAR = timedelta(hours=1)


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    if parsed.minute or parsed.second or parsed.microsecond:
        raise ValueError("timestamps must be exact UTC hours")
    return parsed


def _primitive(value: Any) -> Any:
    if is_dataclass(value):
        return _primitive(asdict(value))
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, dict):
        return {str(key): _primitive(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_primitive(item) for item in value]
    return value


def _strategy_symbols() -> tuple[str, ...]:
    """Derive the universe from V6 profiles across old and current definitions."""
    profiles = V6_COIN_STRATEGY.coin_profiles
    if not profiles:
        raise ValueError("V6 replay requires ten explicit coin profiles")
    symbols = tuple(profile.symbol for profile in profiles)
    if len(symbols) != 10 or len(set(symbols)) != 10:
        raise ValueError(f"V6 replay requires ten unique profile symbols: {symbols}")
    return symbols


def _optional_symbols_kwarg(function: Callable[..., object]) -> dict[str, tuple[str, ...]]:
    """Use current explicit-universe APIs while remaining compatible with old V6."""
    if "symbols" in inspect.signature(function).parameters:
        return {"symbols": _strategy_symbols()}
    return {}


def _profile_payload() -> dict[str, object]:
    result: dict[str, object] = {}
    for profile in V6_COIN_STRATEGY.coin_profiles:
        base = profile.symbol[:-4]
        result[base] = {
            "parameters": asdict(profile.parameters),
            "trade_policy": asdict(profile.trade_policy),
        }
    return result


def _load_market_data(
    *, quote: str, requested_start: datetime, end: datetime
) -> tuple[dict[str, list[Any]], dict[str, ExecutionRules], datetime, dict[str, object]]:
    symbols = _strategy_symbols()
    if any(not symbol.endswith(quote) for symbol in symbols):
        raise ValueError(
            f"checkout strategy symbols do not match requested quote {quote}: {symbols}"
        )
    client = BinancePublicClient(base_url=BINANCE_PUBLIC_BASE_URL)
    warmup_start = requested_start - WARMUP_BARS * BAR
    candles_by_symbol: dict[str, list[Any]] = {}
    rules_by_symbol: dict[str, ExecutionRules] = {}
    coverage: dict[str, object] = {}
    usable_starts: list[datetime] = []

    for symbol in symbols:
        rule = client.symbol_rules(symbol)
        if not (
            rule.status == "TRADING"
            and rule.quote_asset == quote
            and rule.symbol == symbol
            and rule.spot_allowed
            and "MARKET" in rule.order_types
        ):
            raise ValueError(f"{symbol}: public Spot market is not tradable for {quote}")
        rules_by_symbol[symbol] = ExecutionRules(
            tick_size=rule.tick_size,
            step_size=rule.step_size,
            min_qty=rule.min_qty,
            min_notional=rule.min_notional,
        )
        first = client.first_available_open(symbol, start=warmup_start, end_exclusive=end)
        candles = client.fetch_klines(symbol, start=first, end_exclusive=end)
        audit = audit_candles(candles, expected_symbol=symbol)
        audit.require_valid()
        if not candles or candles[-1].open_time_utc != end - BAR:
            raise ValueError(f"{symbol}: latest requested closed 1h candle is missing")
        usable = max(requested_start, first + WARMUP_BARS * BAR)
        usable_starts.append(usable)
        candles_by_symbol[symbol] = candles
        coverage[symbol] = {
            "first_open_utc": first,
            "usable_report_start_utc": usable,
            "candle_count": len(candles),
        }
        print(
            f"{quote} {symbol}: {len(candles)} bars; usable from {usable.isoformat()}",
            flush=True,
        )

    return candles_by_symbol, rules_by_symbol, max(usable_starts), coverage


def _evaluate(
    *,
    start: datetime,
    end: datetime,
    candles_by_symbol: dict[str, list[Any]],
    rules_by_symbol: dict[str, ExecutionRules],
) -> dict[str, object]:
    strategy = V6_COIN_STRATEGY
    result: dict[str, object] = {}
    for costs in (BASELINE_COSTS, STRESS_COSTS):
        batch = run_isolated_batch(
            candles_by_symbol=candles_by_symbol,
            report_start_utc=start,
            report_end_utc=end,
            costs=costs,
            execution_rules=rules_by_symbol,
            strategy_parameters=strategy.parameters,
            strategy_parameters_by_symbol=strategy.parameter_map(),
            trade_policies_by_symbol=strategy.policy_map(),
            strategy_semantics=strategy.semantics,
            strategy_version=strategy.version,
            **_optional_symbols_kwarg(run_isolated_batch),
        )
        portfolio = run_shared_portfolio_backtest(
            candles_by_symbol=candles_by_symbol,
            report_start_utc=start,
            report_end_utc=end,
            starting_cash=Decimal("250"),
            target_notional=Decimal("80"),
            slot_count=3,
            costs=costs,
            execution_rules=rules_by_symbol,
            strategy_parameters=strategy.parameters,
            strategy_parameters_by_symbol=strategy.parameter_map(),
            trade_policies_by_symbol=strategy.policy_map(),
            strategy_semantics=strategy.semantics,
            strategy_version=strategy.version,
            slot_allocation=strategy.slot_allocation,
            **_optional_symbols_kwarg(run_shared_portfolio_backtest),
        )
        result[costs.name] = {
            "portfolio_3x80": {
                "metrics": portfolio.metrics,
                "risk_halted_at_utc": portfolio.risk_halted_at_utc,
                "max_concurrent_positions": portfolio.max_concurrent_positions,
                "open_symbols_at_end": portfolio.open_symbols_at_end,
                "blocked_signal_count": len(portfolio.blocked_signals),
            },
            "isolated_10x250": {
                "starting_equity": batch.starting_equity,
                "ending_equity": batch.ending_equity,
                "net_pnl": batch.net_pnl,
                "return_pct": batch.return_pct,
                "completed_trades": batch.completed_trades,
                "max_drawdown": batch.max_drawdown,
                "max_drawdown_pct": batch.max_drawdown_pct,
                "per_coin": {single.symbol: single.metrics for single in batch.results},
            },
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quote", choices=("USDT", "USDC"), required=True)
    parser.add_argument("--requested-start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--compare-start")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    requested_start = _parse(args.requested_start)
    end = _parse(args.end)
    if requested_start >= end:
        raise ValueError("requested start must precede end")
    candles, rules, available_start, coverage = _load_market_data(
        quote=args.quote, requested_start=requested_start, end=end
    )
    compare_start = _parse(args.compare_start) if args.compare_start else available_start
    if compare_start < available_start:
        raise ValueError(
            f"compare start {compare_start.isoformat()} precedes usable {args.quote} history "
            f"{available_start.isoformat()}"
        )

    windows: dict[str, tuple[datetime, datetime]] = {
        "fresh_common": (compare_start, end),
    }
    if available_start <= requested_start:
        windows["requested_full"] = (requested_start, end)
    elif available_start != compare_start:
        windows["available_quote_history"] = (available_start, end)

    payload = {
        "schema_version": 1,
        "quote_asset": args.quote,
        "strategy_version": V6_COIN_STRATEGY.version,
        "strategy_symbols": _strategy_symbols(),
        "requested_start_utc": requested_start,
        "end_utc": end,
        "available_common_start_utc": available_start,
        "comparison_start_utc": compare_start,
        "profile_by_base_asset": _profile_payload(),
        "coverage": coverage,
        "windows": {
            label: {
                "start_utc": start,
                "end_utc": window_end,
                "results": _evaluate(
                    start=start,
                    end=window_end,
                    candles_by_symbol=candles,
                    rules_by_symbol=rules,
                ),
            }
            for label, (start, window_end) in windows.items()
        },
        "safety": {
            "market_data": "public_binance_spot_1h",
            "orders_sent": False,
            "paper_state_modified": False,
            "credentials_required": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(_primitive(payload), indent=2) + "\n", encoding="utf-8")
    print(f"saved {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
