"""Three-year research replay for current USDC V6 using USDT as market-history proxy.

This does not pretend that pre-listing USDC candles existed. It deliberately
uses public Binance USDT candles as a labelled proxy for the same base-asset
market while keeping the current USDC strategy profiles and USDC execution
rules. It is research-only, writes no Paper state and sends no orders.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from hixton.backtest.engine import run_isolated_batch
from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.data.binance import BinancePublicClient
from hixton.data.quality import audit_candles
from hixton.domain.models import Candle
from hixton.domain.versions import V6_COIN_STRATEGY

BINANCE_PUBLIC_BASE_URL = "https://data-api.binance.vision"
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


def _usdc_symbols() -> tuple[str, ...]:
    symbols = tuple(profile.symbol for profile in V6_COIN_STRATEGY.coin_profiles)
    if len(symbols) != 10 or any(not symbol.endswith("USDC") for symbol in symbols):
        raise ValueError(f"current V6 must contain ten USDC profiles: {symbols}")
    return symbols


def _proxy_symbol(usdc_symbol: str) -> str:
    return f"{usdc_symbol[:-4]}USDT"


def _load_proxy_history(
    *, start: datetime, end: datetime
) -> tuple[dict[str, list[Candle]], dict[str, ExecutionRules], dict[str, object]]:
    client = BinancePublicClient(base_url=BINANCE_PUBLIC_BASE_URL)
    strategy = V6_COIN_STRATEGY
    warmup_start = start - strategy.parameters.warmup_bars * BAR
    candles_by_symbol: dict[str, list[Candle]] = {}
    rules_by_symbol: dict[str, ExecutionRules] = {}
    provenance: dict[str, object] = {}

    for usdc_symbol in _usdc_symbols():
        usdt_symbol = _proxy_symbol(usdc_symbol)
        usdc_rule = client.symbol_rules(usdc_symbol)
        if not (
            usdc_rule.status == "TRADING"
            and usdc_rule.quote_asset == "USDC"
            and usdc_rule.spot_allowed
            and "MARKET" in usdc_rule.order_types
        ):
            raise ValueError(f"{usdc_symbol}: current USDC market is not tradable")
        rules_by_symbol[usdc_symbol] = ExecutionRules(
            tick_size=usdc_rule.tick_size,
            step_size=usdc_rule.step_size,
            min_qty=usdc_rule.min_qty,
            min_notional=usdc_rule.min_notional,
        )

        proxy = client.fetch_klines(usdt_symbol, start=warmup_start, end_exclusive=end)
        if not proxy or proxy[0].open_time_utc != warmup_start:
            raise ValueError(f"{usdt_symbol}: full proxy warm-up history is unavailable")
        if proxy[-1].open_time_utc != end - BAR:
            raise ValueError(f"{usdt_symbol}: proxy history does not reach requested end")
        adapted = [
            replace(
                candle,
                symbol=usdc_symbol,
                source="binance_spot_usdt_proxy_for_usdc_research",
            )
            for candle in proxy
        ]
        audit_candles(
            adapted,
            expected_symbol=usdc_symbol,
            expected_start=warmup_start,
            expected_end_exclusive=end,
        ).require_valid()
        candles_by_symbol[usdc_symbol] = adapted
        provenance[usdc_symbol] = {
            "proxy_market": usdt_symbol,
            "target_market": usdc_symbol,
            "first_open_utc": adapted[0].open_time_utc,
            "last_open_utc": adapted[-1].open_time_utc,
            "candle_count": len(adapted),
            "execution_rules_from": usdc_symbol,
        }
        print(f"{usdc_symbol} <= {usdt_symbol}: {len(adapted)} proxy bars", flush=True)

    return candles_by_symbol, rules_by_symbol, provenance


def _evaluate(
    *,
    start: datetime,
    end: datetime,
    candles_by_symbol: dict[str, list[Candle]],
    rules_by_symbol: dict[str, ExecutionRules],
) -> dict[str, object]:
    strategy = V6_COIN_STRATEGY
    symbols = _usdc_symbols()
    result: dict[str, object] = {}
    for costs in (BASELINE_COSTS, STRESS_COSTS):
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
            symbols=symbols,
        )
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
            symbols=symbols,
        )
        result[costs.name] = {
            "portfolio_3x80": {
                "metrics": portfolio.metrics,
                "risk_halted_at_utc": portfolio.risk_halted_at_utc,
                "blocked_signal_count": len(portfolio.blocked_signals),
                "max_concurrent_positions": portfolio.max_concurrent_positions,
            },
            "isolated_10x250": {
                "starting_equity": batch.starting_equity,
                "ending_equity": batch.ending_equity,
                "net_pnl": batch.net_pnl,
                "return_pct": batch.return_pct,
                "completed_trades": batch.completed_trades,
                "max_drawdown_pct": batch.max_drawdown_pct,
                "per_coin": {single.symbol: single.metrics for single in batch.results},
            },
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    start = _parse(args.start)
    end = _parse(args.end)
    if start >= end:
        raise ValueError("start must precede end")

    candles, rules, provenance = _load_proxy_history(start=start, end=end)
    payload = {
        "schema_version": 1,
        "research_mode": "USDT_BASE_MARKET_PROXY_FOR_CURRENT_USDC_STRATEGY",
        "start_utc": start,
        "end_utc": end,
        "strategy_version": V6_COIN_STRATEGY.version,
        "target_quote": "USDC",
        "proxy_quote": "USDT",
        "profiles": {
            profile.symbol: {
                "parameters": asdict(profile.parameters),
                "trade_policy": asdict(profile.trade_policy),
            }
            for profile in V6_COIN_STRATEGY.coin_profiles
        },
        "provenance": provenance,
        "results": _evaluate(
            start=start,
            end=end,
            candles_by_symbol=candles,
            rules_by_symbol=rules,
        ),
        "limitations": [
            "Pre-listing candles are real Binance USDT candles relabelled only for research.",
            "This is not historical proof of USDC liquidity or fills before USDC listing.",
            "Current USDC exchange rules are applied to the whole proxy period.",
        ],
        "safety": {
            "orders_sent": False,
            "paper_state_modified": False,
            "credentials_required": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(_primitive(payload), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_primitive(payload["results"]["baseline"]), indent=2), flush=True)
    print(f"saved {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
