"""Training-only filtered-entry micro-harvest research.

Run #84 showed that changing exits alone cannot rescue unchanged V1 flip-up entries.
This study therefore keeps the protected Core untouched and tests a bounded,
point-in-time entry filter family on the five primary Satellites.

Only features available at signal close are permitted:
- absolute CMO strength,
- normalized breakout strength,
- positive 24h VIDYA slope.

A small fixed exit family is evaluated jointly on TRAINING only. The single winner
per market is then frozen and Direct-USDC holdout is rejection-only.
"""

from __future__ import annotations

import json
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from statistics import median
from typing import Any

from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS, CostModel
from hixton.data.binance import BinancePublicClient
from hixton.domain.strategy import evaluate_batch
from hixton.domain.versions import V1_STRATEGY, V6_COIN_STRATEGY
from scripts.satellite_shared_portfolio_research import _load_histories, _rules

D = Decimal
ONE = D("1")
HUNDRED = D("100")
SOURCES = Path("agent_memory/autonomy/satellite_v1_idle_horizon_sources.json")
OUTPUT = Path("evidence/satellite-micro-filtered-entry-research.json")
NOTIONAL = D("125")

CMO_FLOORS = (0.15, 0.30, 0.45)
BREAKOUT_FLOORS = (0.0, 0.25, 0.50)
SLOPE_MODES = ("NONE", "POSITIVE_24H")
EXIT_FAMILY = (
    (D("1.00"), D("0.75"), 4),
    (D("1.50"), D("1.00"), 6),
    (D("2.00"), D("1.50"), 6),
    (D("2.00"), D("1.50"), 12),
)


def _round_down(value: D, step: D) -> D:
    if step <= 0:
        return value
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def _eligible(point, points, cmo_floor: float, breakout_floor: float, slope_mode: str) -> bool:
    if not (point.tradable and point.flip_up):
        return False
    if (point.abs_cmo or 0.0) < cmo_floor:
        return False
    if (point.breakout_strength or 0.0) < breakout_floor:
        return False
    if slope_mode == "POSITIVE_24H":
        if point.index < 24:
            return False
        prev = points[point.index - 24]
        if point.vidya is None or prev.vidya is None or point.vidya <= prev.vidya:
            return False
    return True


def _simulate(
    *,
    candles: list[Any],
    points: list[Any],
    start,
    end,
    costs: CostModel,
    rules,
    cmo_floor: float,
    breakout_floor: float,
    slope_mode: str,
    tp_pct: D,
    sl_pct: D,
    horizon: int,
) -> dict[str, object]:
    idx_by_close = {c.close_time_utc: i for i, c in enumerate(candles)}
    signal_indices = [
        idx_by_close[p.candle.close_time_utc]
        for p in points
        if _eligible(p, points, cmo_floor, breakout_floor, slope_mode)
        and start <= p.candle.close_time_utc < end
        and p.candle.close_time_utc in idx_by_close
    ]

    pnl = D("0")
    wins = losses = timeouts = blocked = 0
    holds: list[float] = []
    next_free_index = -1

    for signal_idx in signal_indices:
        entry_idx = signal_idx + 1
        if entry_idx <= next_free_index or entry_idx >= len(candles):
            continue
        entry_candle = candles[entry_idx]
        if not (start <= entry_candle.open_time_utc < end):
            continue

        entry_ref = D(str(entry_candle.open))
        buy_fill = entry_ref * (ONE + costs.adverse_price_rate)
        gross_qty = _round_down(NOTIONAL / buy_fill, rules.step_size)
        spend = min(gross_qty * buy_fill, NOTIONAL)
        if gross_qty < rules.min_qty or spend < rules.min_notional or spend <= 0:
            blocked += 1
            continue

        net_qty = gross_qty * (ONE - costs.fee_rate)
        tp_ref = buy_fill * (ONE + tp_pct / HUNDRED)
        sl_ref = buy_fill * (ONE - sl_pct / HUNDRED)
        exit_ref = None
        exit_idx = None
        outcome = "TIMEOUT"
        last_idx = min(len(candles) - 1, entry_idx + horizon - 1)

        for i in range(entry_idx, last_idx + 1):
            c = candles[i]
            if c.open_time_utc >= end:
                break
            high = D(str(c.high))
            low = D(str(c.low))
            hit_tp = high >= tp_ref
            hit_sl = low <= sl_ref
            if hit_tp and hit_sl:
                exit_ref, exit_idx, outcome = sl_ref, i, "LOSS_AMBIGUOUS_STOP_FIRST"
                break
            if hit_sl:
                exit_ref, exit_idx, outcome = sl_ref, i, "LOSS"
                break
            if hit_tp:
                exit_ref, exit_idx, outcome = tp_ref, i, "WIN"
                break

        if exit_ref is None:
            exit_idx = last_idx
            exit_ref = D(str(candles[exit_idx].close))
            outcome = "TIMEOUT"

        sell_fill = exit_ref * (ONE - costs.adverse_price_rate)
        sell_qty = _round_down(net_qty, rules.step_size)
        gross_quote = sell_qty * sell_fill
        if sell_qty < rules.min_qty or gross_quote < rules.min_notional:
            blocked += 1
            next_free_index = exit_idx
            continue
        net_quote = gross_quote * (ONE - costs.fee_rate)
        trade_pnl = net_quote - spend
        pnl += trade_pnl
        if outcome == "WIN":
            wins += 1
        elif outcome.startswith("LOSS"):
            losses += 1
        else:
            timeouts += 1
        holds.append(float(exit_idx - entry_idx + 1))
        next_free_index = exit_idx

    cycles = wins + losses + timeouts
    return {
        "net_pnl_usdc": str(pnl),
        "completed_cycles": cycles,
        "wins": wins,
        "losses": losses,
        "timeouts": timeouts,
        "blocked": blocked,
        "win_rate_pct": (wins / cycles * 100.0) if cycles else None,
        "median_holding_hours": median(holds) if holds else None,
        "average_holding_hours": (sum(holds) / len(holds)) if holds else None,
        "profit_per_cycle_usdc": str(pnl / D(cycles)) if cycles else None,
        "pass": cycles >= 20 and pnl > 0,
    }


def main() -> None:
    checkpoint = json.loads(SOURCES.read_text(encoding="utf-8"))
    rows = checkpoint["per_symbol"]
    satellites = tuple(rows)
    expected = ("SUIUSDC", "NEARUSDC", "UNIUSDC", "AAVEUSDC", "BCHUSDC")
    if satellites != expected:
        raise RuntimeError(f"primary Satellite set drifted: {satellites!r}")

    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    rules = _rules(client, V6_COIN_STRATEGY.symbols + satellites)
    (
        report_start,
        holdout_start,
        report_end,
        proxy_candles,
        validation_candles,
        provenance,
    ) = _load_histories(
        client=client,
        satellite_symbols=satellites,
        satellite_sources={
            symbol: str(rows[symbol]["history_source_for_training"])
            for symbol in satellites
        },
        execution_rules=rules,
    )

    training_points = {
        s: evaluate_batch(
            s,
            proxy_candles[s],
            parameters=V1_STRATEGY.parameters,
            semantics=V1_STRATEGY.semantics,
            strategy_version="SATELLITE-MICRO-FILTERED-ENTRY",
        )
        for s in satellites
    }
    holdout_points = {
        s: evaluate_batch(
            s,
            validation_candles[s],
            parameters=V1_STRATEGY.parameters,
            semantics=V1_STRATEGY.semantics,
            strategy_version="SATELLITE-MICRO-FILTERED-ENTRY",
        )
        for s in satellites
    }

    per_symbol: dict[str, object] = {}
    accepted: list[str] = []

    for symbol in satellites:
        candidates = []
        ranked = []
        for cmo in CMO_FLOORS:
            for breakout in BREAKOUT_FLOORS:
                for slope in SLOPE_MODES:
                    for tp, sl, horizon in EXIT_FAMILY:
                        base = _simulate(
                            candles=proxy_candles[symbol], points=training_points[symbol],
                            start=report_start, end=holdout_start,
                            costs=BASELINE_COSTS, rules=rules[symbol],
                            cmo_floor=cmo, breakout_floor=breakout, slope_mode=slope,
                            tp_pct=tp, sl_pct=sl, horizon=horizon,
                        )
                        stress = _simulate(
                            candles=proxy_candles[symbol], points=training_points[symbol],
                            start=report_start, end=holdout_start,
                            costs=STRESS_COSTS, rules=rules[symbol],
                            cmo_floor=cmo, breakout_floor=breakout, slope_mode=slope,
                            tp_pct=tp, sl_pct=sl, horizon=horizon,
                        )
                        row = {
                            "cmo_floor": cmo,
                            "breakout_floor": breakout,
                            "slope_mode": slope,
                            "take_profit_pct": str(tp),
                            "stop_loss_pct": str(sl),
                            "max_holding_hours": horizon,
                            "baseline": base,
                            "stress": stress,
                        }
                        candidates.append(row)
                        if base["pass"] and stress["pass"]:
                            min_pnl = min(D(base["net_pnl_usdc"]), D(stress["net_pnl_usdc"]))
                            min_ppc = min(D(base["profit_per_cycle_usdc"]), D(stress["profit_per_cycle_usdc"]))
                            cycles = min(int(base["completed_cycles"]), int(stress["completed_cycles"]))
                            ranked.append((min_pnl, min_ppc, cycles, row))

        ranked.sort(key=lambda x: x[:3], reverse=True)
        if not ranked:
            per_symbol[symbol] = {
                "training_candidates": candidates,
                "training_winner": None,
                "holdout": None,
                "advance_to_core_idle_replay": False,
                "rejection_reason": "NO_ROBUST_FILTERED_ENTRY_TRAINING_WINNER",
            }
            continue

        winner = ranked[0][-1]
        holdout = {}
        for costs in (BASELINE_COSTS, STRESS_COSTS):
            holdout[costs.name] = _simulate(
                candles=validation_candles[symbol], points=holdout_points[symbol],
                start=holdout_start, end=report_end,
                costs=costs, rules=rules[symbol],
                cmo_floor=float(winner["cmo_floor"]),
                breakout_floor=float(winner["breakout_floor"]),
                slope_mode=str(winner["slope_mode"]),
                tp_pct=D(winner["take_profit_pct"]),
                sl_pct=D(winner["stop_loss_pct"]),
                horizon=int(winner["max_holding_hours"]),
            )
        holdout_pass = bool(holdout["baseline"]["pass"]) and bool(holdout["stress"]["pass"])
        if holdout_pass:
            accepted.append(symbol)
        per_symbol[symbol] = {
            "training_candidates": candidates,
            "training_winner": winner,
            "holdout": holdout,
            "advance_to_core_idle_replay": holdout_pass,
            "rejection_reason": None if holdout_pass else "DIRECT_USDC_FILTERED_ENTRY_REJECTION",
        }

    result = {
        "schema_version": 1,
        "study": "SATELLITE_MICRO_FILTERED_ENTRY_RESEARCH",
        "research_only": True,
        "product_mutated": False,
        "protected_product_sha": checkpoint.get("protected_product_sha"),
        "notional_usdc": str(NOTIONAL),
        "entry_family": {
            "cmo_floors": list(CMO_FLOORS),
            "breakout_floors": list(BREAKOUT_FLOORS),
            "slope_modes": list(SLOPE_MODES),
            "all_features_point_in_time": True,
        },
        "exit_family": [
            {"take_profit_pct": str(tp), "stop_loss_pct": str(sl), "max_holding_hours": h}
            for tp, sl, h in EXIT_FAMILY
        ],
        "per_symbol": per_symbol,
        "accepted_for_exact_core_idle_replay": accepted,
        "next_stage": (
            "SATELLITE_MICRO_FILTERED_ENTRY_CORE_IDLE_REPLAY"
            if accepted else
            "SATELLITE_MICRO_FILTERED_ENTRY_DIAGNOSIS"
        ),
        "selection_contract": {
            "training_only_selects_entry_filter_and_exit": True,
            "direct_usdc_holdout_rejection_only": True,
            "holdout_may_retune": False,
            "minimum_training_cycles": 20,
            "baseline_and_stress_training_positive_required": True,
        },
        "provenance_by_symbol": provenance,
        "safety": {
            "protected_core_mutated": False,
            "orders_sent": False,
            "paper_or_live_activated": False,
            "private_credentials_used": False,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({
        "study": result["study"],
        "training_winners": {s: r["training_winner"] for s, r in per_symbol.items()},
        "accepted_for_exact_core_idle_replay": accepted,
        "next_stage": result["next_stage"],
    }, indent=2))


if __name__ == "__main__":
    main()
