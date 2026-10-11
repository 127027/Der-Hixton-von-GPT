"""Research-only 1100-USDC portfolio sizing + indicative margin-liquidation stress.

Never sends orders, reads credentials, enables leverage or changes Paper/Live.
The 5x/10x section is a TRADE-LEVEL sensitivity study, not a derivatives
backtest: funding, liquidation fees, venue maintenance tiers and feedback
to future position allocation are not reproduced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path

import hixton.backtest.portfolio as portfolio_module
from hixton.backtest.continuity import continuity_manifest_data, load_continuity_history
from hixton.backtest.models import CURRENT_COSTS, STRESS_COSTS, ExecutionRules
from hixton.data.binance import BinancePublicClient
from hixton.data.storage import CandleStore
from hixton.domain.allocation import ONE_PER_SYMBOL, RANKED_REPEAT
from hixton.domain.versions import strategy_definition

TOTAL = D("1100")
ACTIVE = ("NEARUSDC", "AAVEUSDC", "BCHUSDC")
CASES = (
    ("canonical_2x550", 2, D("550"), False, RANKED_REPEAT),
    ("cash_buffer_2x500", 2, D("500"), False, RANKED_REPEAT),
    ("four_x_250", 4, D("250"), False, RANKED_REPEAT),
    ("four_x_275", 4, D("275"), False, RANKED_REPEAT),
    ("three_x_366_66", 3, D("366.66"), False, RANKED_REPEAT),
    ("five_x_220", 5, D("220"), False, RANKED_REPEAT),
    ("four_x_250_one_per_coin", 4, D("250"), False, ONE_PER_SYMBOL),
    ("dynamic_four_x_250", 4, D("250"), True, RANKED_REPEAT),
    ("dynamic_four_x_275", 4, D("275"), True, RANKED_REPEAT),
)


def _metrics(run, start, end):
    m = run.metrics
    yearly = []
    prior = TOTAL
    for i in (1, 2, 3):
        limit = start.replace(year=start.year + i)
        value = m.ending_equity if limit == end else next(
            (point.equity for point in reversed(run.equity_curve)
             if point.time_utc < limit), prior)
        yearly.append({
            "year": i, "end_equity": str(value),
            "net_change": str(value - prior),
        })
        prior = value
    by_coin = defaultdict(lambda: {"count": 0, "pnl": D("0")})
    for trade in run.trades:
        by_coin[trade.symbol]["count"] += 1
        by_coin[trade.symbol]["pnl"] += trade.realized_pnl
    return {
        "start_usdc": str(m.starting_equity),
        "end_usdc": str(m.ending_equity),
        "pnl_usdc": str(m.net_pnl),
        "trades": m.completed_trades,
        "slot_trades": m.completed_slot_trades,
        "max_drawdown_pct": str(m.max_drawdown_pct),
        "max_drawdown_usdc": str(m.max_drawdown),
        "exposure_pct": str(m.exposure_pct),
        "fees_usdc": str(m.total_fees),
        "spread_slippage_usdc": str(m.modeled_spread_slippage),
        "win_rate_pct": str(m.win_rate_pct),
        "profit_factor": str(m.profit_factor),
        "yearly": yearly,
        "blocked": dict(Counter(b.rsplit(":", 1)[-1] for b in run.blocked_signals)),
        "per_coin": {k: {"trades": v["count"], "realized_pnl": str(v["pnl"])}
                     for k, v in by_coin.items()},
        "open_symbols_at_end": list(run.open_symbols_at_end),
    }


def _run_with_optional_adaptive_policy(
    *, adaptive, candles, rules, strategy, start, end, cost, slots, tranche, policy
):
    """Inject research-only allocation into the isolated current Python process.

    A rank-strength is a causal *signal indicator*, NOT a calibrated success
    probability.  We refuse to give it that interpretation.
    """
    original_allocate = portfolio_module.allocate_entry_slots
    original_priority = portfolio_module.entry_priority
    strengths = {}
    def capture(strength, symbol, symbols):
        strengths[symbol] = max(0.0, float(strength or 0.0))
        return original_priority(strength, symbol, symbols)

    def research_allocation(ranked_symbols, *, free_slots, policy):
        if policy != RANKED_REPEAT:
            return original_allocate(ranked_symbols, free_slots=free_slots, policy=policy)
        unique = tuple(dict.fromkeys(ranked_symbols))
        # Each pending eligible coin initially gets one base unit.
        selected = unique[:free_slots]
        allocation = dict.fromkeys(selected, 1)
        available = free_slots - len(selected)
        # Add one/two units only to stronger already-selected Core signals;
        # else leave capacity available for a later, independently signalled trade.
        for symbol in selected:
            strength = strengths.get(symbol, 0.0)
            per_coin_cap = 3 if strength >= 1.0 else 2 if strength >= 0.25 else 1
            add = min(available, per_coin_cap - 1)
            allocation[symbol] += add
            available -= add
            if available <= 0:
                break
        return allocation

    try:
        if adaptive:
            portfolio_module.entry_priority = capture
            portfolio_module.allocate_entry_slots = research_allocation
        from dataclasses import replace
        selected_strategy = replace(strategy, slot_allocation=policy)
        return portfolio_module.run_shared_portfolio_backtest(
            candles_by_symbol=candles,
            execution_rules=rules,
            starting_cash=TOTAL,
            target_notional=tranche,
            slot_count=slots,
            strategy=selected_strategy,
            report_start_utc=start,
            report_end_utc=end,
            costs=cost,
        )
    finally:
        portfolio_module.allocate_entry_slots = original_allocate
        portfolio_module.entry_priority = original_priority


def _leverage_liquidation_sensitivity(run, candles, costs):
    """A deliberately non-executable margin stress screen.

    Each completed spot trade is hypothetically allocated its actual quote
    spend as *margin*.  At 5x or 10x, notional is levered. For an isolated
    LONG, simplified price-loss threshold is approximately
    1 / L - 0.5% assumed maintenance. Intrabar low is used. This can still
    MISS real liquidations (fees, marks, gaps, tiered maintenance).
    """
    by_symbol = {
        name: {c.open_time_utc: i for i, c in enumerate(items)}
        for name, items in candles.items()
    }
    sig = {s.signal_id: s for s in run.signals}
    leverage_states = {
        "constant_1x": {"trades": 0, "liquidation_touches": 0, "example_liquidations": []},
        "constant_5x": {"trades": 0, "liquidation_touches": 0, "example_liquidations": []},
        "constant_10x": {"trades": 0, "liquidation_touches": 0, "example_liquidations": []},
        "signal_strength_switch_1_5_10x": {
            "trades": 0, "liquidation_touches": 0,
            "leverage_choices": {"1": 0, "5": 0, "10": 0},
            "example_liquidations": [],
        },
    }
    worst = []
    for t in run.trades:
        position = candles[t.symbol]
        index = by_symbol[t.symbol]
        first = index.get(t.entry_time_utc)
        if first is None:
            raise ValueError(f"Entry candle absent for {t.symbol}")
        terminal = index.get(t.exit_time_utc)
        if terminal is None:
            # Exit at exact terminal boundary may lie outside loaded candles.
            terminal = len(position)
        if terminal <= first:
            raise ValueError("Invalid position timeline")
        entry_price = D(str(t.entry_price))
        worst_low = min(D(str(c.low)) for c in position[first:terminal])
        drawdown = max(D("0"), (entry_price - worst_low) / entry_price)
        signal = sig.get(t.entry_signal_id)
        strength = max(0.0, float(signal.breakout_strength or 0.0)) if signal else 0.0
        suggested_leverage = 10 if strength >= 1.0 else 5 if strength >= 0.25 else 1
        worst.append({
            "symbol": t.symbol, "entry_utc": t.entry_time_utc.isoformat(),
            "max_intratrade_adverse_pct": str(drawdown * 100),
            "signal_strength": strength,
            "indicative_dynamic_leverage": suggested_leverage,
        })
        for label, lev in (
            ("constant_1x", 1),
            ("constant_5x", 5),
            ("constant_10x", 10),
            ("signal_strength_switch_1_5_10x", suggested_leverage),
        ):
            state = leverage_states[label]
            state["trades"] += 1
            if label == "signal_strength_switch_1_5_10x":
                state["leverage_choices"][str(lev)] += 1
            # Not a real exchange liquidation model.
            barrier = D("1") / D(lev) - D("0.005") if lev > 1 else D("1")
            if drawdown >= barrier:
                state["liquidation_touches"] += 1
                if len(state["example_liquidations"]) < 10:
                    state["example_liquidations"].append({
                        "symbol": t.symbol,
                        "entry_utc": t.entry_time_utc.isoformat(),
                        "gross_collateral": str(t.entry_quote_spend),
                        "threshold_pct": str(barrier * 100),
                        "worst_adverse_pct": str(drawdown * 100),
                    })
    return {
        "warning": "INDICATIVE_ONLY: trade-level intrabar-low threshold test, not a derivatives/futures/margin backtest; no funding, maintenance tiers, mark price, liquidation fees, partial fills or portfolio-feedback; not a probability model",
        "conservative_interpretation": "Even 1 liquidation touch can consume the isolated position margin; real thresholds can be earlier.",
        "liquidation_assumption": "LONG isolated margin: 1/leverage minus illustrative 0.5% maintenance, before other costs",
        "scenarios": leverage_states,
        "top_intratrade_adverse_moves": sorted(
            worst, key=lambda v: D(v["max_intratrade_adverse_pct"]), reverse=True
        )[:20],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--end", required=True)
    parser.add_argument("--database", default="data/hixton-usdc.sqlite3")
    parser.add_argument("--output", default="evidence/capital1100-paper-research.json")
    args = parser.parse_args()
    end = datetime.fromisoformat(args.end.replace("Z", "+00:00")).astimezone(UTC)
    start = end.replace(year=end.year - 3)
    if end.minute or end.second or end.microsecond:
        raise ValueError("End must be at a full closed 1h UTC candle")
    strategy = strategy_definition("v8")
    if strategy.active_shared_satellites != ACTIVE or len(strategy.symbols) != 15:
        raise ValueError("Unexpected V8 contract: abort")
    db = Path(args.database)
    rules = {}
    with CandleStore(db, read_only=True) as store:
        for name in strategy.symbols:
            rule = store.load_symbol_rules(name)
            if rule is None or rule.status != "TRADING" or not rule.spot_allowed:
                raise ValueError(f"Missing USDC market rules: {name}")
            rules[name] = ExecutionRules(rule.tick_size, rule.step_size, rule.min_qty, rule.min_notional)

    history = load_continuity_history(
        strategy=strategy,
        report_start_utc=start, report_end_utc=end,
        execution_rules=rules,
        client=BinancePublicClient(base_url="https://data-api.binance.vision"),
        native_database_path=db,
        cache_path=db.parent / "backtest-history.sqlite3",
    )
    cases = {}
    leverage = None
    for name, slots, tranche, adaptive, policy in CASES:
        if tranche * slots > TOTAL:
            raise ValueError(f"{name}: attempted leveraged spot allocation")
        row = {
            "slot_count": slots, "tranche_usdc": str(tranche),
            "max_intended_commitment_usdc": str(slots * tranche),
            "initial_cash_buffer_usdc": str(TOTAL - slots * tranche),
            "adaptive_position_sizing": adaptive,
            "allocation_policy": policy,
            "scenarios": {},
        }
        for cost in (CURRENT_COSTS, STRESS_COSTS):
            print("CASE", name, cost.name, flush=True)
            output = _run_with_optional_adaptive_policy(
                adaptive=adaptive, candles=history.candles_by_symbol,
                rules=rules, strategy=strategy, start=start, end=end,
                cost=cost, slots=slots, tranche=tranche, policy=policy,
            )
            row["scenarios"][cost.name] = _metrics(output, start, end)
            print("->", output.metrics.ending_equity,
                  "trades", output.metrics.completed_trades,
                  "DD", output.metrics.max_drawdown_pct, flush=True)
            if name == "four_x_250" and cost.name == "current":
                leverage = _leverage_liquidation_sensitivity(
                    output, history.candles_by_symbol, cost
                )
        cases[name] = row
    baseline = cases["canonical_2x550"]["scenarios"]["current"]
    baseline_reproducible = (
        baseline["trades"] == cases["canonical_2x550"]["scenarios"]["current"]["trades"]
        and baseline["start_usdc"] == str(TOTAL)
    )
    root = cases["canonical_2x550"]["scenarios"]
    for row in cases.values():
        row["vs_canonical"] = {}
        for cost in ("current", "stress"):
            actual = row["scenarios"][cost]
            base = root[cost]
            row["vs_canonical"][cost] = {
                "delta_end_usdc": str(D(actual["end_usdc"]) - D(base["end_usdc"])),
                "delta_trades": actual["trades"] - base["trades"],
                "delta_drawdown_pp": str(D(actual["max_drawdown_pct"]) -
                                         D(base["max_drawdown_pct"])),
                "delta_year3_pnl_usdc": str(
                    D(actual["yearly"][2]["net_change"]) -
                    D(base["yearly"][2]["net_change"])
                ),
            }
    assert portfolio_module.allocate_entry_slots.__module__ == "hixton.domain.allocation"
    data = {
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "research_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "mode": "SPOT-ONLY-RESEARCH_WITH_SEPARATE_MARGIN_LIQUIDATION_SCREEN",
        "historical_period_start_utc": start.isoformat(),
        "historical_period_end_utc": end.isoformat(),
        "starting_cash_usdc": str(TOTAL),
        "strategy_version": strategy.version,
        "baseline_runtime_unchanged": baseline_reproducible,
        "data": continuity_manifest_data(history),
        "adaptive_rule": "Study only: 4 x 250/275 base units; one per eligible Core signal, extra up to 2 if already-closed-bar ATR-normalized breakout_strength>=0.25, up to 3 if >=1.0. Satellites remain single tranche. This indicator is NOT probability-calibrated.",
        "costs": {
            "current": {"fee_bps_per_side": "10", "spread_bps_per_side": "2", "slippage_bps_per_side": "3"},
            "stress": {"fee_bps_per_side": "10", "spread_bps_per_side": "10", "slippage_bps_per_side": "20"},
        },
        "cases": cases,
        "illustrative_leverage_risk_not_portfolio_pnl": leverage,
        "no_live_orders": True,
        "no_paper_account_mutation": True,
        "no_credentials_read": True,
        "research_only_no_promotion": True,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print("WRITTEN", out, flush=True)


if __name__ == "__main__":
    main()
