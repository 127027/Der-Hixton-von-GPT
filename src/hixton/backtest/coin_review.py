"""V5: per-coin loss attribution and frozen Hixton-derived policy experiments."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from statistics import mean

from hixton.backtest.engine import candle_snapshot_sha256, run_single_backtest
from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS, BacktestResult, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.constants import SYMBOLS
from hixton.data.quality import audit_candles
from hixton.data.storage import CandleStore
from hixton.domain.models import (
    Candle,
    IndicatorPoint,
    Signal,
    SignalAction,
    StrategyParameters,
    StrategySemantics,
)
from hixton.domain.strategy import evaluate_batch
from hixton.domain.trade_policy import TradePolicy, TradePolicyGate
from hixton.domain.versions import V2_RESEARCH_STRATEGY, V6_COIN_STRATEGY

START = datetime(2023, 9, 1, 12, tzinfo=UTC)
YEAR1, YEAR2, END = (START.replace(year=year) for year in (2024, 2025, 2026))
OLDER = (datetime(2021, 10, 16, 1, tzinfo=UTC), datetime(2023, 3, 24, 13, tzinfo=UTC))
POLICIES = {
    "unchanged": TradePolicy(),
    "cmo20": TradePolicy(cmo_floor=0.2),
    "slope24": TradePolicy(slope_bars=24),
    "slope72": TradePolicy(slope_bars=72),
    "stop4": TradePolicy(stop_atr=4),
    "stop6": TradePolicy(stop_atr=6),
    "trail4": TradePolicy(trail_atr=4),
    "trail6": TradePolicy(trail_atr=6),
    "cmo20_trail6": TradePolicy(cmo_floor=0.2, trail_atr=6),
    "slope24_trail6": TradePolicy(slope_bars=24, trail_atr=6),
    "slope72_trail6": TradePolicy(slope_bars=72, trail_atr=6),
    "slope24_stop4": TradePolicy(slope_bars=24, stop_atr=4),
}


def variant_version(parameters: StrategyParameters, policy: TradePolicy) -> str:
    payload = json.dumps([asdict(parameters), asdict(policy)], sort_keys=True)
    return "HIXTON-V5-" + hashlib.sha256(payload.encode()).hexdigest()[:16]


def screen_policy(
    points: list[IndicatorPoint],
    start: datetime,
    end: datetime,
    policy: TradePolicy,
) -> dict[str, float | int]:
    """Stress screening with identical policy decisions; no quantity rounding."""
    gate = TradePolicyGate(policy)
    cash, quantity, basis = 250.0, 0.0, 0.0
    entry, entry_atr, high = None, 0.0, 0.0
    peak, dd, equity = 250.0, 0.0, 250.0
    completed, winners, filtered = 0, 0, 0
    fee_rate = float(STRESS_COSTS.fee_rate)
    adverse_rate = float(STRESS_COSTS.adverse_price_rate)
    pending: Signal | None = None
    for point in points:
        if point.candle.open_time_utc >= end:
            break
        in_report = point.candle.open_time_utc >= start
        if in_report and pending is not None:
            if pending.action is SignalAction.ENTER_LONG and cash >= 5:
                entry = point.candle.open * (1 + adverse_rate)
                entry_atr = pending.atr
                high, basis = entry, min(250.0, cash)
                quantity = basis / entry * (1 - fee_rate)
                cash -= basis
            elif pending.action is SignalAction.EXIT_LONG and quantity:
                receive = quantity * point.candle.open * (1 - adverse_rate) * (1 - fee_rate)
                winners += int(receive > basis)
                cash += receive
                quantity, entry = 0.0, None
                completed += 1
            pending = None
        if entry is not None:
            high = max(high, point.candle.close)
        decision = gate.decide(point, entry_price=entry, entry_atr=entry_atr, highest_close=high)
        if in_report:
            if decision.block_reason:
                filtered += 1
            else:
                pending = decision.signal
            equity = cash + quantity * point.candle.close
            peak = max(peak, equity)
            dd = max(dd, 100 * (1 - equity / peak))
    return {
        "ending_equity": equity,
        "return_pct": 100 * (equity / 250 - 1),
        "max_drawdown_pct": dd,
        "trades": completed,
        "winners": winners,
        "filtered_entries": filtered,
    }


def diagnose(result: BacktestResult, candles: list[Candle]) -> dict[str, object]:
    """Retrospective attribution only. MFE/MAE never enter selection or signals."""
    rows: list[dict[str, str | float]] = []
    for trade in result.trades:
        held = [c for c in candles if trade.entry_time_utc <= c.open_time_utc < trade.exit_time_utc]
        entry = float(trade.entry_price)
        mfe = 100 * (max((c.high for c in held), default=entry) / entry - 1)
        mae = 100 * (min((c.low for c in held), default=entry) / entry - 1)
        rows.append(
            {
                "entry": trade.entry_time_utc.isoformat(),
                "exit": trade.exit_time_utc.isoformat(),
                "pnl": float(trade.realized_pnl),
                "return_pct": float(trade.realized_return_pct),
                "hours": float(trade.holding_hours),
                "mfe_pct": mfe,
                "mae_pct": mae,
            }
        )
    losses = [r for r in rows if float(r["pnl"]) < 0]
    buckets = {}
    for label, lo, hi in (
        ("under_72h", 0, 72),
        ("72h_to_week", 72, 168),
        ("over_week", 168, float("inf")),
    ):
        chosen = [r for r in rows if lo <= float(r["hours"]) < hi]
        buckets[label] = {"trades": len(chosen), "pnl": sum(float(r["pnl"]) for r in chosen)}
    return {
        "metrics": asdict(result.metrics),
        "holding_buckets": buckets,
        "losses": len(losses),
        "losers_previously_up_2pct": sum(float(r["mfe_pct"]) >= 2 for r in losses),
        "mean_loser_mae_pct": mean(float(r["mae_pct"]) for r in losses) if losses else None,
        "top5_profit_share": (
            sum(sorted((max(0.0, float(r["pnl"])) for r in rows), reverse=True)[:5])
            / sum(max(0.0, float(r["pnl"])) for r in rows)
        )
        if any(float(r["pnl"]) > 0 for r in rows)
        else None,
        "worst_trades": sorted(rows, key=lambda r: float(r["pnl"]))[:5],
    }


def run_coin_review(database: Path, output: Path) -> None:
    if output.exists():
        raise ValueError("output already exists; choose a new V5 run")
    root = Path(__file__).parents[3]
    v4 = json.loads(
        (root / "backtests/v4/reports/review-20260905.json").read_text(encoding="utf-8")
    )
    payload: dict[str, object] = {
        "schema": "HIXTON-COIN-REVIEW-1",
        "status": "RESEARCH_ONLY",
        "paper_changed": False,
        "reference_pine_sha256": hashlib.sha256(
            (root / "strategy/pine/Der_Hixton_Indikator_v6.pine").read_bytes()
        ).hexdigest(),
        "training": [
            [START.isoformat(), YEAR1.isoformat()],
            [YEAR1.isoformat(), YEAR2.isoformat()],
        ],
        "validation": [YEAR2.isoformat(), END.isoformat()],
        "older_diagnostic": [t.isoformat() for t in OLDER],
        "selection": (
            "at least 6 completed trades in each training year; maximize worst stress return, "
            "then lower worst drawdown, then summed return; stable catalogue order breaks ties"
        ),
        "limitations": [
            "All periods were previously inspected; no untouched holdout.",
            "Screening omits Binance rounding; exact finalists use production engines.",
            "MFE/MAE and holding buckets are hindsight diagnostics, not tradable entry filters.",
            "Stops trigger on closed bars and execute at next OPEN; not guaranteed stop prices.",
            "Older diagnostic overlaps no training period; it is not used to reselect candidates.",
        ],
        "policies": {key: asdict(p) for key, p in POLICIES.items()},
        "source_sha256": {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ("backtest", "domain")
            for p in sorted((root / "src/hixton" / folder).glob("*.py"))
        },
        "costs": [asdict(BASELINE_COSTS), asdict(STRESS_COSTS)],
    }
    coins, markets, older_markets, rules = {}, {}, {}, {}
    selected_parameters: dict[str, StrategyParameters] = {}
    selected_policies: dict[str, TradePolicy] = {}
    with CandleStore(database) as store:
        for symbol in SYMBOLS:
            markets[symbol] = store.load_candles(
                symbol, start=START - timedelta(hours=400), end_exclusive=END
            )
            older_markets[symbol] = store.load_candles(
                symbol, start=OLDER[0] - timedelta(hours=400), end_exclusive=OLDER[1]
            )
            for data, lo, hi in ((markets[symbol], START, END), (older_markets[symbol], *OLDER)):
                audit_candles(
                    data,
                    expected_symbol=symbol,
                    expected_start=lo - timedelta(hours=400),
                    expected_end_exclusive=hi,
                ).require_valid()
            rule = store.load_symbol_rules(symbol)
            if rule is None:
                raise ValueError(f"missing Binance filters: {symbol}")
            rules[symbol] = ExecutionRules(
                rule.tick_size, rule.step_size, rule.min_qty, rule.min_notional
            )
    incumbent = V2_RESEARCH_STRATEGY.parameters
    for symbol in SYMBOLS:
        print(f"{symbol}: training frozen policy catalogue, then exact validation", flush=True)
        bases = {
            "v2": incumbent,
            "pine_original": StrategyParameters(),
            "v4_training": StrategyParameters(**v4["coins"][symbol]["selected"]),
        }
        candidates = []
        best_key = (-float("inf"), -float("inf"), -float("inf"))
        best = (incumbent, TradePolicy(), "v2/unchanged")
        seen = set()
        for base_name, parameters in bases.items():
            if parameters in seen:
                continue
            seen.add(parameters)
            training_points = [
                evaluate_batch(
                    symbol,
                    [
                        c
                        for c in markets[symbol]
                        if lo - timedelta(hours=400) <= c.open_time_utc < hi
                    ],
                    parameters=parameters,
                    semantics=StrategySemantics.PINE_V6,
                )
                for lo, hi in ((START, YEAR1), (YEAR1, YEAR2))
            ]
            for name, policy in POLICIES.items():
                train = [
                    screen_policy(points, lo, hi, policy)
                    for points, (lo, hi) in zip(
                        training_points, ((START, YEAR1), (YEAR1, YEAR2)), strict=True
                    )
                ]
                eligible = all(t["trades"] >= 6 for t in train)
                key = (
                    min(t["return_pct"] for t in train),
                    -max(t["max_drawdown_pct"] for t in train),
                    sum(t["return_pct"] for t in train),
                )
                candidates.append(
                    {
                        "name": f"{base_name}/{name}",
                        "parameters": asdict(parameters),
                        "policy": asdict(policy),
                        "training": train,
                        "eligible": eligible,
                    }
                )
                if eligible and key > best_key:
                    best_key, best = key, (parameters, policy, f"{base_name}/{name}")
        parameters, policy, name = best
        selected_parameters[symbol], selected_policies[symbol] = parameters, policy
        exact, diagnostics, balances = {}, {}, {}
        for label, params, overlay in (
            ("v2", incumbent, TradePolicy()),
            ("pine_original", StrategyParameters(), TradePolicy()),
            ("selected", parameters, policy),
        ):
            for window, data, lo, hi in (
                ("full", markets[symbol], START, END),
                ("recent", markets[symbol], YEAR2, END),
                ("older", older_markets[symbol], *OLDER),
            ):
                if label == "pine_original" and window == "older":
                    continue
                for cost in (BASELINE_COSTS, STRESS_COSTS):
                    result = run_single_backtest(
                        symbol=symbol,
                        candles=data,
                        report_start_utc=lo,
                        report_end_utc=hi,
                        costs=cost,
                        execution_rules=rules[symbol],
                        strategy_parameters=params,
                        strategy_semantics=StrategySemantics.PINE_V6,
                        trade_policy=overlay,
                        strategy_version=variant_version(params, overlay),
                    )
                    exact[f"{label}_{window}_{cost.name}"] = asdict(result.metrics)
                    balances[f"{label}_{window}_{cost.name}"] = {
                        "cash": result.equity_curve[-1].cash,
                        "marked_position_and_dust": result.equity_curve[-1].position_value,
                        "realized_pnl": sum(t.realized_pnl for t in result.trades),
                        "open_position": result.open_position_at_end,
                        "open_quantity": result.open_position_quantity,
                        "dust_quantity": result.dust_quantity,
                        "blocked_signals": len(result.blocked_signals),
                    }
                    if label == "v2" and window in ("full", "recent") and cost == BASELINE_COSTS:
                        diagnostics[window] = diagnose(result, data)
        required = (
            "full_baseline",
            "full_stress",
            "recent_baseline",
            "recent_stress",
            "older_baseline",
            "older_stress",
        )
        regressions = [
            w
            for w in required
            if float(exact[f"selected_{w}"]["ending_equity"])
            < float(exact[f"v2_{w}"]["ending_equity"])
        ]
        coins[symbol] = {
            "selected_name": name,
            "parameters": asdict(parameters),
            "policy": asdict(policy),
            "candidates": candidates,
            "eligible_candidates": sum(bool(c["eligible"]) for c in candidates),
            "fallback_to_v2": not any(c["eligible"] for c in candidates),
            "exact": exact,
            "balances": balances,
            "diagnostics": diagnostics,
            "regression_windows": regressions,
            "paper_approved": False,
            "data_sha256": candle_snapshot_sha256(markets[symbol]),
            "older_data_sha256": candle_snapshot_sha256(older_markets[symbol]),
        }
        print(
            f"{symbol}: {name}; recent stress {exact['v2_recent_stress']['ending_equity']} "
            f"-> {exact['selected_recent_stress']['ending_equity']}; regressions {regressions}",
            flush=True,
        )
    # Post-selection diagnosis announced only after the initial catalogue run:
    # isolate XRP's incremental effect; never reselect other coins on validation.
    xrp_parameters = dict.fromkeys(SYMBOLS, incumbent)
    xrp_parameters["XRPUSDC"] = selected_parameters["XRPUSDC"]
    xrp_policies = dict.fromkeys(SYMBOLS, TradePolicy())
    xrp_policies["XRPUSDC"] = selected_policies["XRPUSDC"]
    portfolios = {}
    for label, parameter_map, policies in (
        ("v2", None, None),
        ("selected", selected_parameters, selected_policies),
        ("xrp_only_diagnostic", xrp_parameters, xrp_policies),
    ):
        print(f"Portfolio {label}: full, recent, older; baseline + stress", flush=True)
        portfolio_version = (
            "HIXTON-V5-"
            + hashlib.sha256(
                json.dumps(
                    [
                        {s: asdict(p) for s, p in (parameter_map or {}).items()},
                        {s: asdict(p) for s, p in (policies or {}).items()},
                    ],
                    sort_keys=True,
                ).encode()
            ).hexdigest()[:16]
        )
        for window, lo, hi, market_set in (
            ("full", START, END, markets),
            ("recent", YEAR2, END, markets),
            ("older", *OLDER, older_markets),
        ):
            for cost in (BASELINE_COSTS, STRESS_COSTS):
                result_portfolio = run_shared_portfolio_backtest(
                    candles_by_symbol=market_set,
                    report_start_utc=lo,
                    report_end_utc=hi,
                    execution_rules=rules,
                    strategy_parameters=incumbent,
                    strategy_parameters_by_symbol=parameter_map,
                    trade_policies_by_symbol=policies,
                    strategy_semantics=StrategySemantics.PINE_V6,
                    strategy_version=portfolio_version
                    if policies
                    else V2_RESEARCH_STRATEGY.version,
                    costs=cost,
                )
                portfolios[f"{label}_{window}_{cost.name}"] = {
                    "metrics": asdict(result_portfolio.metrics),
                    "halt": result_portfolio.risk_halted_at_utc,
                }
    xrp_base, xrp_policy = selected_parameters["XRPUSDC"], selected_policies["XRPUSDC"]
    neighbors = {}
    for label, params, overlay in (
        ("center", xrp_base, xrp_policy),
        ("stop3.5", xrp_base, replace(xrp_policy, stop_atr=3.5)),
        ("stop4.5", xrp_base, replace(xrp_policy, stop_atr=4.5)),
        ("atr100", replace(xrp_base, atr_length=100), xrp_policy),
        ("atr140", replace(xrp_base, atr_length=140), xrp_policy),
        ("band3.0", replace(xrp_base, band_multiplier=3.0), xrp_policy),
        ("band3.4", replace(xrp_base, band_multiplier=3.4), xrp_policy),
    ):
        neighbor_metrics = {}
        for window, data, lo, hi in (
            ("full", markets["XRPUSDC"], START, END),
            ("recent", markets["XRPUSDC"], YEAR2, END),
            ("older", older_markets["XRPUSDC"], *OLDER),
        ):
            neighbor_result = run_single_backtest(
                symbol="XRPUSDC",
                candles=data,
                report_start_utc=lo,
                report_end_utc=hi,
                costs=STRESS_COSTS,
                execution_rules=rules["XRPUSDC"],
                strategy_parameters=params,
                strategy_semantics=StrategySemantics.PINE_V6,
                trade_policy=overlay,
                strategy_version=variant_version(params, overlay),
            )
            neighbor_metrics[window] = asdict(neighbor_result.metrics)
        neighbors[label] = {
            "parameters": asdict(params),
            "policy": asdict(overlay),
            "metrics": neighbor_metrics,
        }
    payload.update(
        coins=coins,
        portfolios=portfolios,
        execution_rules={s: asdict(r) for s, r in rules.items()},
        xrp_followup={
            "status": "POST_SELECTION_DIAGNOSTIC_NOT_HOLDOUT",
            "reason": "Only XRP improved all six isolated ending values in the first run. "
            "Freeze that finalist; test XRP-only portfolio and six one-axis neighbors. "
            "No neighbor is substituted based on validation performance.",
            "neighbors": neighbors,
        },
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Saved {output}", flush=True)


def run_frozen_profile_review(database: Path, output: Path) -> None:
    """Validate frozen V6 profiles; never select parameters or change a Paper ledger."""
    if output.exists():
        raise ValueError("output already exists; choose a new V6 run")
    root = Path(__file__).parents[3]
    payload: dict[str, object] = {
        "schema": "HIXTON-FROZEN-PROFILES-1",
        "status": "RETROSPECTIVE_DIAGNOSTIC_NOT_HOLDOUT",
        "strategy": V6_COIN_STRATEGY.config_payload(),
        "selection": "Between V2 and each V5 finalist, maximize minimum ending equity across "
        "full/recent/older stress windows; tie: more full-stress closed trades, then V2. "
        "All these windows influenced this retrospective selection. No robustness proof.",
        "capital": {"isolated": "250", "shared": "250", "slots": 3, "slot_notional": "80"},
        "costs": [asdict(BASELINE_COSTS), asdict(STRESS_COSTS)],
        "source_sha256": {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((root / "src/hixton").rglob("*.py"))
        },
        "reference_pine_sha256": hashlib.sha256(
            (root / "strategy/pine/Der_Hixton_Indikator_v6.pine").read_bytes()
        ).hexdigest(),
        "limitations": [
            "Historical winners do not establish future profitability or all-ten robustness.",
            "Isolated accounts use strategy-only sizing; shared account applies Paper risk gates.",
            "Reserve is initial unallocated cash, not a guarantee against losses.",
            "Existing Paper ledger remains unchanged; historical V2 240-USDC reports stay intact.",
            "V2 also starts at 250 here, separating the strategy effect from added capital.",
        ],
    }
    windows: dict[str, object] = {}
    with CandleStore(database) as store:
        rules = {}
        for symbol in SYMBOLS:
            rule = store.load_symbol_rules(symbol)
            if rule is None:
                raise ValueError(f"missing Binance filters: {symbol}")
            rules[symbol] = ExecutionRules(
                rule.tick_size, rule.step_size, rule.min_qty, rule.min_notional
            )
        payload["execution_rules"] = {s: asdict(r) for s, r in rules.items()}
        for label, lo, hi, warmup_start in (
            ("full", START, END, START - timedelta(hours=400)),
            ("recent", YEAR2, END, START - timedelta(hours=400)),
            ("older", *OLDER, OLDER[0] - timedelta(hours=400)),
        ):
            markets = {
                s: store.load_candles(s, start=warmup_start, end_exclusive=hi) for s in SYMBOLS
            }
            for s, candles in markets.items():
                audit_candles(
                    candles,
                    expected_symbol=s,
                    expected_start=warmup_start,
                    expected_end_exclusive=hi,
                ).require_valid()
            coins, portfolios = {}, {}
            for strategy in (V2_RESEARCH_STRATEGY, V6_COIN_STRATEGY):
                for symbol in SYMBOLS:
                    print(f"{label}/{strategy.key}/{symbol}: baseline + stress", flush=True)
                    for cost in (BASELINE_COSTS, STRESS_COSTS):
                        result = run_single_backtest(
                            symbol=symbol,
                            candles=markets[symbol],
                            report_start_utc=lo,
                            report_end_utc=hi,
                            costs=cost,
                            execution_rules=rules[symbol],
                            strategy_parameters=strategy.parameters_for(symbol),
                            strategy_semantics=strategy.semantics,
                            strategy_version=strategy.version,
                            trade_policy=strategy.policy_for(symbol),
                        )
                        coins[f"{strategy.key}_{symbol}_{cost.name}"] = {
                            "metrics": asdict(result.metrics),
                            "diagnosis": diagnose(result, markets[symbol]),
                        }
                for cost in (BASELINE_COSTS, STRESS_COSTS):
                    print(f"{label}/{strategy.key}/shared: {cost.name}", flush=True)
                    portfolio = run_shared_portfolio_backtest(
                        candles_by_symbol=markets,
                        report_start_utc=lo,
                        report_end_utc=hi,
                        starting_cash=Decimal("250.00"),
                        target_notional=Decimal("80.00"),
                        slot_count=3,
                        costs=cost,
                        execution_rules=rules,
                        strategy_parameters=strategy.parameters,
                        strategy_parameters_by_symbol=strategy.parameter_map(),
                        trade_policies_by_symbol=strategy.policy_map(),
                        strategy_semantics=strategy.semantics,
                        strategy_version=strategy.version,
                        slot_allocation=strategy.slot_allocation,
                    )
                    portfolios[f"{strategy.key}_{cost.name}"] = {
                        "metrics": asdict(portfolio.metrics),
                        "halt": portfolio.risk_halted_at_utc,
                        "max_concurrent_positions": portfolio.max_concurrent_positions,
                        "open_symbols_at_end": portfolio.open_symbols_at_end,
                    }
            windows[label] = {
                "start": lo,
                "end_exclusive": hi,
                "history_start": warmup_start,
                "data_sha256": {s: candle_snapshot_sha256(c) for s, c in markets.items()},
                "coins": coins,
                "portfolios": portfolios,
            }
    payload["windows"] = windows
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Saved {output}", flush=True)
