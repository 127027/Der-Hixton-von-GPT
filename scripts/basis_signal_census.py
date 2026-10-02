"""Census and forward-excursion study for the original Hixton basis signal stream.

Research only. The original Pine defaults are treated as a high-frequency sensor,
not as an executable product strategy. For every raw flip-up we measure only
future prices after the signal timestamp and ask whether small upside excursions
occur before adverse moves across bounded horizons.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from hixton.backtest.continuity import load_continuity_history
from hixton.domain.models import StrategyParameters, StrategySemantics
from hixton.domain.strategy import evaluate_batch
from hixton.domain.versions import V6_COIN_STRATEGY
from hixton.runtime.supervisor import safe_closed_window
from scripts.coin_optimization_cycle import _rules

BASIS = StrategyParameters(
    vidya_length=10,
    momentum_length=20,
    smoothing_length=15,
    atr_length=200,
    band_multiplier=2.0,
    warmup_bars=400,
)
HORIZONS = (6, 12, 24, 48, 72)
UPSIDE_TARGETS = (0.25, 0.50, 1.00, 1.50, 2.00)
DOWNSIDE_LEVELS = (-0.25, -0.50, -1.00, -1.50, -2.00)


def _future_slice(candles: list[Any], index: int, hours: int) -> list[Any]:
    return candles[index + 1 : min(len(candles), index + 1 + hours)]


def _excursion(entry: float, future: list[Any]) -> tuple[float, float]:
    if not future:
        return 0.0, 0.0
    mfe = max((c.high / entry - 1.0) * 100.0 for c in future)
    mae = min((c.low / entry - 1.0) * 100.0 for c in future)
    return mfe, mae


def _first_touch(entry: float, future: list[Any], up_pct: float, down_pct: float) -> str:
    up = entry * (1.0 + up_pct / 100.0)
    down = entry * (1.0 + down_pct / 100.0)
    for candle in future:
        up_hit = candle.high >= up
        down_hit = candle.low <= down
        if up_hit and down_hit:
            return "AMBIGUOUS_SAME_BAR"
        if up_hit:
            return "UP_FIRST"
        if down_hit:
            return "DOWN_FIRST"
    return "NONE"


def evaluate() -> dict[str, object]:
    _, start, end = safe_closed_window()
    rules = _rules()
    history = load_continuity_history(
        strategy=V6_COIN_STRATEGY,
        report_start_utc=start,
        report_end_utc=end,
        execution_rules=rules,
    )
    rows: list[dict[str, object]] = []
    symbol_summary: dict[str, dict[str, object]] = {}

    for symbol in V6_COIN_STRATEGY.symbols:
        candles = history.candles_by_symbol[symbol]
        points = evaluate_batch(
            symbol,
            candles,
            parameters=BASIS,
            semantics=StrategySemantics.PINE_V6,
            strategy_version="HIXTON-BASIS-SENSOR-RESEARCH",
        )
        index_by_close = {c.close_time_utc: i for i, c in enumerate(candles)}
        up_points = [
            p for p in points
            if p.tradable and p.flip_up and start <= p.candle.close_time_utc <= end
        ]
        down_points = [
            p for p in points
            if p.tradable and p.flip_down and start <= p.candle.close_time_utc <= end
        ]
        symbol_summary[symbol] = {
            "flip_up_count": len(up_points),
            "flip_down_count": len(down_points),
            "total_flips": len(up_points) + len(down_points),
        }
        for point in up_points:
            idx = index_by_close[point.candle.close_time_utc]
            entry = point.candle.close
            row: dict[str, object] = {
                "symbol": symbol,
                "signal_close_utc": point.candle.close_time_utc.isoformat(),
                "entry_reference_close": entry,
            }
            for h in HORIZONS:
                future = _future_slice(candles, idx, h)
                mfe, mae = _excursion(entry, future)
                row[f"mfe_{h}h_pct"] = mfe
                row[f"mae_{h}h_pct"] = mae
            future24 = _future_slice(candles, idx, 24)
            for up in UPSIDE_TARGETS:
                down = -up
                row[f"first_touch_24h_up{up}_down{abs(down)}"] = _first_touch(
                    entry, future24, up, down
                )
            rows.append(row)

    aggregate: dict[str, object] = {
        "flip_up_count": sum(int(v["flip_up_count"]) for v in symbol_summary.values()),
        "flip_down_count": sum(int(v["flip_down_count"]) for v in symbol_summary.values()),
        "total_flips": sum(int(v["total_flips"]) for v in symbol_summary.values()),
        "samples": len(rows),
    }
    for h in HORIZONS:
        if rows:
            aggregate[f"mean_mfe_{h}h_pct"] = sum(float(r[f"mfe_{h}h_pct"]) for r in rows) / len(rows)
            aggregate[f"mean_mae_{h}h_pct"] = sum(float(r[f"mae_{h}h_pct"]) for r in rows) / len(rows)
    for up in UPSIDE_TARGETS:
        key=f"first_touch_24h_up{up}_down{up}"
        values=[str(r[key]) for r in rows]
        aggregate[key]={
            "UP_FIRST": values.count("UP_FIRST"),
            "DOWN_FIRST": values.count("DOWN_FIRST"),
            "AMBIGUOUS_SAME_BAR": values.count("AMBIGUOUS_SAME_BAR"),
            "NONE": values.count("NONE"),
        }

    return {
        "schema_version": 1,
        "study": "ORIGINAL_HIXTON_BASIS_SIGNAL_CENSUS",
        "research_only": True,
        "activation_performed": False,
        "report_start_utc": start.isoformat(),
        "report_end_utc": end.isoformat(),
        "basis_parameters": asdict(BASIS),
        "symbol_summary": symbol_summary,
        "aggregate": aggregate,
        "forward_excursions": rows,
        "interpretation_contract": {
            "raw_flip_is_not_trade": True,
            "future_data_used_only_for_post_signal_evaluation": True,
            "next_step_if_promising": "build isolated micro-harvest strategy with explicit fees/slippage and walk-forward validation",
        },
    }


def main() -> None:
    result=evaluate()
    out=Path("evidence/basis-signal-census.json")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="forward_excursions"},indent=2))


if __name__=="__main__":
    main()
