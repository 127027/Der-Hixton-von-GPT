"""Bounded after-cost micro-harvest exit research for the five primary Satellites.

Entry signal is frozen to unchanged V1/DMS_V1 flip-up. This study changes only the
exit family: asymmetric fixed take-profit/stop-loss plus a short maximum holding
horizon. Parameter ranking uses TRAINING proxy data only. Direct-USDC holdout is
rejection-only for the single training winner per market.

This is a diagnostic Satellite study. It does not mutate the protected Core and
does not send orders.
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
OUTPUT = Path("evidence/satellite-micro-harvest-research.json")
NOTIONAL = D("125")
TP_GRID = (D("0.75"), D("1.00"), D("1.50"), D("2.00"))
SL_GRID = (D("0.50"), D("0.75"), D("1.00"), D("1.50"))
HORIZONS = (2, 4, 6, 12)


def _round_down(value: D, step: D) -> D:
    if step <= 0:
        return value
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def _simulate(
    *,
    candles: list[Any],
    symbol: str,
    start,
    end,
    costs: CostModel,
    rules,
    tp_pct: D,
    sl_pct: D,
    horizon: int,
) -> dict[str, object]:
    points = evaluate_batch(
        symbol,
        candles,
        parameters=V1_STRATEGY.parameters,
        semantics=V1_STRATEGY.semantics,
        strategy_version="SATELLITE-MICRO-HARVEST",
    )
    idx_by_close = {c.close_time_utc: i for i, c in enumerate(candles)}
    signal_indices = [
        idx_by_close[p.candle.close_time_utc]
        for p in points
        if p.tradable and p.flip_up and start <= p.candle.close_time_utc < end
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

        exit_ref: D | None = None
        exit_idx: int | None = None
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
                # 1h bars cannot reveal touch order. Fail closed: stop first.
                exit_ref = sl_ref
                exit_idx = i
                outcome = "LOSS_AMBIGUOUS_STOP_FIRST"
                break
            if hit_sl:
                exit_ref = sl_ref
                exit_idx = i
                outcome = "LOSS"
                break
            if hit_tp:
                exit_ref = tp_ref
                exit_idx = i
                outcome = "WIN"
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
        "pass": cycles > 0 and pnl > 0,
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

    per_symbol: dict[str, object] = {}
    accepted: list[str] = []

    for symbol in satellites:
        candidates: list[dict[str, object]] = []
        ranked: list[tuple[D, D, int, D, D, int, dict[str, object]]] = []
        for tp in TP_GRID:
            for sl in SL_GRID:
                for horizon in HORIZONS:
                    baseline = _simulate(
                        candles=proxy_candles[symbol],
                        symbol=symbol,
                        start=report_start,
                        end=holdout_start,
                        costs=BASELINE_COSTS,
                        rules=rules[symbol],
                        tp_pct=tp,
                        sl_pct=sl,
                        horizon=horizon,
                    )
                    stress = _simulate(
                        candles=proxy_candles[symbol],
                        symbol=symbol,
                        start=report_start,
                        end=holdout_start,
                        costs=STRESS_COSTS,
                        rules=rules[symbol],
                        tp_pct=tp,
                        sl_pct=sl,
                        horizon=horizon,
                    )
                    row = {
                        "take_profit_pct": str(tp),
                        "stop_loss_pct": str(sl),
                        "max_holding_hours": horizon,
                        "baseline": baseline,
                        "stress": stress,
                    }
                    candidates.append(row)
                    if baseline["pass"] and stress["pass"]:
                        min_pnl = min(D(str(baseline["net_pnl_usdc"])), D(str(stress["net_pnl_usdc"])))
                        min_ppc = min(D(str(baseline["profit_per_cycle_usdc"])), D(str(stress["profit_per_cycle_usdc"])))
                        cycles = min(int(baseline["completed_cycles"]), int(stress["completed_cycles"]))
                        ranked.append((min_pnl, min_ppc, cycles, tp, sl, -horizon, row))

        ranked.sort(key=lambda x: x[:6], reverse=True)
        if not ranked:
            per_symbol[symbol] = {
                "training_candidates": candidates,
                "training_winner": None,
                "holdout": None,
                "advance_to_core_idle_replay": False,
                "rejection_reason": "NO_AFTER_COST_TRAINING_WINNER_BASELINE_AND_STRESS",
            }
            continue

        winner = ranked[0][-1]
        tp = D(str(winner["take_profit_pct"]))
        sl = D(str(winner["stop_loss_pct"]))
        horizon = int(winner["max_holding_hours"])
        holdout = {}
        for costs in (BASELINE_COSTS, STRESS_COSTS):
            holdout[costs.name] = _simulate(
                candles=validation_candles[symbol],
                symbol=symbol,
                start=holdout_start,
                end=report_end,
                costs=costs,
                rules=rules[symbol],
                tp_pct=tp,
                sl_pct=sl,
                horizon=horizon,
            )
        holdout_pass = bool(holdout["baseline"]["pass"]) and bool(holdout["stress"]["pass"])
        if holdout_pass:
            accepted.append(symbol)
        per_symbol[symbol] = {
            "training_candidates": candidates,
            "training_winner": {
                "take_profit_pct": str(tp),
                "stop_loss_pct": str(sl),
                "max_holding_hours": horizon,
                "baseline": winner["baseline"],
                "stress": winner["stress"],
            },
            "holdout": holdout,
            "advance_to_core_idle_replay": holdout_pass,
            "rejection_reason": None if holdout_pass else "DIRECT_USDC_HOLDOUT_REJECTION",
        }

    result = {
        "schema_version": 1,
        "study": "SATELLITE_MICRO_HARVEST_FIXED_EXIT_RESEARCH",
        "research_only": True,
        "product_mutated": False,
        "protected_product_sha": checkpoint.get("protected_product_sha"),
        "notional_usdc": str(NOTIONAL),
        "entry_contract": "UNCHANGED_V1_DMS_V1_FLIP_UP; ENTER_NEXT_OPEN; IGNORE_NEW_SIGNALS_WHILE_OPEN",
        "exit_grid_training_only": {
            "take_profit_pct": [str(x) for x in TP_GRID],
            "stop_loss_pct": [str(x) for x in SL_GRID],
            "max_holding_hours": list(HORIZONS),
            "same_bar_tp_sl_policy": "STOP_FIRST_CONSERVATIVE",
        },
        "per_symbol": per_symbol,
        "accepted_for_exact_core_idle_replay": accepted,
        "next_stage": (
            "SATELLITE_MICRO_HARVEST_CORE_IDLE_REPLAY"
            if accepted else
            "SATELLITE_MICRO_HARVEST_FILTERED_ENTRY_FAMILY"
        ),
        "selection_contract": {
            "training_only_selects_tp_sl_horizon": True,
            "direct_usdc_holdout_rejection_only": True,
            "holdout_may_not_retune": True,
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
        "training_winners": {
            s: row["training_winner"] for s, row in per_symbol.items()
        },
        "accepted_for_exact_core_idle_replay": accepted,
        "next_stage": result["next_stage"],
    }, indent=2))


if __name__ == "__main__":
    main()
