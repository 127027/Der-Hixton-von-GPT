"""Coin-by-coin V6 research cycle with mandatory shared-portfolio recheck.

Research only: this module never mutates the active strategy, Paper account or
runtime settings. Candidate selection uses training windows only. Validation
may accept/reject the frozen training winner but never select a replacement.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from hixton.backtest.continuity import load_continuity_history
from hixton.backtest.engine import run_isolated_batch, run_single_backtest
from hixton.backtest.models import (
    BASELINE_COSTS,
    STRESS_COSTS,
    BacktestResult,
    CostModel,
    ExecutionRules,
)
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.data.binance import BinancePublicClient
from hixton.domain.models import Candle, StrategyParameters
from hixton.domain.trade_policy import TradePolicy
from hixton.domain.versions import V6_COIN_STRATEGY
from hixton.runtime.supervisor import safe_closed_window

D = Decimal


@dataclass(frozen=True, slots=True)
class Candidate:
    name: str
    parameters: StrategyParameters
    policy: TradePolicy


def _payload(candidate: Candidate) -> dict[str, object]:
    return {
        "parameters": asdict(candidate.parameters),
        "trade_policy": asdict(candidate.policy),
    }


def _candidate_hash(candidate: Candidate) -> str:
    raw = json.dumps(_payload(candidate), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def candidate_catalog(symbol: str) -> tuple[Candidate, ...]:
    """Return a frozen, bounded neighbourhood around the active coin profile."""

    definition = V6_COIN_STRATEGY
    base_parameters = definition.parameters_for(symbol)
    base_policy = definition.policy_for(symbol)
    candidates: list[Candidate] = []
    seen: set[tuple[StrategyParameters, TradePolicy]] = set()

    def add(
        name: str,
        *,
        parameters: StrategyParameters | None = None,
        policy: TradePolicy | None = None,
    ) -> None:
        candidate = Candidate(
            name=name,
            parameters=parameters or base_parameters,
            policy=policy or base_policy,
        )
        identity = (candidate.parameters, candidate.policy)
        if identity in seen:
            return
        seen.add(identity)
        candidates.append(candidate)

    add("current")

    for floor in (0.0, 0.1, 0.2, 0.3, 0.4):
        add(f"cmo{int(floor * 100):02d}", policy=replace(base_policy, cmo_floor=floor))
    for bars in (0, 12, 24, 48, 72):
        add(f"slope{bars}", policy=replace(base_policy, slope_bars=bars))
    for stop in (0.0, 1.5, 2.0, 3.0, 4.0):
        add(
            f"stop{str(stop).replace('.', '_')}",
            policy=replace(base_policy, stop_atr=stop),
        )
    for trail in (0.0, 1.5, 2.0, 3.0, 4.0):
        add(
            f"trail{str(trail).replace('.', '_')}",
            policy=replace(base_policy, trail_atr=trail),
        )

    add(
        "cmo20_slope24",
        policy=replace(
            base_policy,
            cmo_floor=max(0.2, base_policy.cmo_floor),
            slope_bars=24,
        ),
    )
    add(
        "cmo20_stop2",
        policy=replace(base_policy, cmo_floor=max(0.2, base_policy.cmo_floor), stop_atr=2.0),
    )
    add(
        "cmo20_trail3",
        policy=replace(base_policy, cmo_floor=max(0.2, base_policy.cmo_floor), trail_atr=3.0),
    )
    add(
        "slope12_stop2",
        policy=replace(base_policy, slope_bars=12, stop_atr=2.0),
    )
    add(
        "slope24_stop2",
        policy=replace(base_policy, slope_bars=24, stop_atr=2.0),
    )
    add(
        "slope24_trail4",
        policy=replace(base_policy, slope_bars=24, trail_atr=4.0),
    )

    for length in (4, 6, 8, 10, 12):
        add(f"vidya{length}", parameters=replace(base_parameters, vidya_length=length))
    for length in (14, 20, 28):
        add(
            f"momentum{length}",
            parameters=replace(base_parameters, momentum_length=length),
        )
    for length in (6, 8, 12, 15, 20):
        add(
            f"smoothing{length}",
            parameters=replace(base_parameters, smoothing_length=length),
        )
    for length in (30, 60, 90, 120, 180):
        add(f"atr{length}", parameters=replace(base_parameters, atr_length=length))

    for suffix, offset in (
        ("minus_06", -0.6),
        ("minus_03", -0.3),
        ("plus_03", 0.3),
        ("plus_06", 0.6),
    ):
        add(
            f"band_{suffix}",
            parameters=replace(
                base_parameters,
                band_multiplier=max(0.5, round(base_parameters.band_multiplier + offset, 2)),
            ),
        )

    add(
        "vidya8_band_plus_03",
        parameters=replace(
            base_parameters,
            vidya_length=8,
            band_multiplier=round(base_parameters.band_multiplier + 0.3, 2),
        ),
    )
    add(
        "vidya10_band_plus_03",
        parameters=replace(
            base_parameters,
            vidya_length=10,
            band_multiplier=round(base_parameters.band_multiplier + 0.3, 2),
        ),
    )
    add(
        "atr90_band_plus_03",
        parameters=replace(
            base_parameters,
            atr_length=90,
            band_multiplier=round(base_parameters.band_multiplier + 0.3, 2),
        ),
    )
    add(
        "atr120_band_plus_03",
        parameters=replace(
            base_parameters,
            atr_length=120,
            band_multiplier=round(base_parameters.band_multiplier + 0.3, 2),
        ),
    )
    add(
        "smoothing12_band_plus_03",
        parameters=replace(
            base_parameters,
            smoothing_length=12,
            band_multiplier=round(base_parameters.band_multiplier + 0.3, 2),
        ),
    )
    return tuple(candidates)


def choose_training_candidate(
    scores: dict[str, tuple[Decimal, Decimal, Decimal]],
) -> str:
    """Choose by stress-only train A/B evidence; current wins exact ties."""

    return max(
        scores,
        key=lambda name: (
            min(scores[name][0], scores[name][1]),
            scores[name][0] + scores[name][1],
            -scores[name][2],
            name == "current",
            name,
        ),
    )


def _rules() -> dict[str, ExecutionRules]:
    public = BinancePublicClient(base_url="https://data-api.binance.vision")
    result: dict[str, ExecutionRules] = {}
    for symbol in V6_COIN_STRATEGY.symbols:
        saved = public.symbol_rules(symbol)
        if not saved.tradable_for_quote("USDC"):
            raise RuntimeError(f"{symbol}: current Binance USDC rules are not tradable")
        result[symbol] = ExecutionRules(
            tick_size=saved.tick_size,
            step_size=saved.step_size,
            min_qty=saved.min_qty,
            min_notional=saved.min_notional,
        )
    return result


def _blocked_reason_counts(items: tuple[str, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        reason = item.rsplit(":", 1)[-1]
        counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def _blocked_counts(result: BacktestResult) -> dict[str, int]:
    return _blocked_reason_counts(result.blocked_signals)


def _worst_losses(result: BacktestResult, limit: int = 5) -> list[dict[str, object]]:
    losses = sorted(
        (trade for trade in result.trades if trade.realized_pnl < 0),
        key=lambda trade: trade.realized_pnl,
    )[:limit]
    return [
        {
            "entry_utc": trade.entry_time_utc.isoformat(),
            "exit_utc": trade.exit_time_utc.isoformat(),
            "pnl": str(trade.realized_pnl),
            "return_pct": str(trade.realized_return_pct),
            "holding_hours": str(trade.holding_hours),
            "entry_price": str(trade.entry_price),
            "exit_price": str(trade.exit_price),
        }
        for trade in losses
    ]


def _result_summary(result: BacktestResult) -> dict[str, object]:
    metrics = result.metrics
    return {
        "ending_equity": str(metrics.ending_equity),
        "return_pct": str(metrics.return_pct),
        "completed_trades": metrics.completed_trades,
        "winning_trades": metrics.winning_trades,
        "losing_trades": metrics.losing_trades,
        "win_rate_pct": None if metrics.win_rate_pct is None else str(metrics.win_rate_pct),
        "profit_factor": None if metrics.profit_factor is None else str(metrics.profit_factor),
        "average_win": None if metrics.average_win is None else str(metrics.average_win),
        "average_loss": None if metrics.average_loss is None else str(metrics.average_loss),
        "max_drawdown_pct": str(metrics.max_drawdown_pct),
        "average_holding_hours": (
            None if metrics.average_holding_hours is None else str(metrics.average_holding_hours)
        ),
        "blocked_reasons": _blocked_counts(result),
        "worst_losses": _worst_losses(result),
    }


def _run_single(
    *,
    symbol: str,
    candles: list[Candle],
    rules: ExecutionRules,
    start: datetime,
    end: datetime,
    candidate: Candidate,
    costs: CostModel,
    version: str,
) -> BacktestResult:
    return run_single_backtest(
        symbol=symbol,
        candles=candles,
        report_start_utc=start,
        report_end_utc=end,
        starting_cash=D("250"),
        target_notional=D("250"),
        costs=costs,
        execution_rules=rules,
        strategy_parameters=candidate.parameters,
        trade_policy=candidate.policy,
        strategy_semantics=V6_COIN_STRATEGY.semantics,
        strategy_version=version,
    )


def _profile_hashes(profiles: dict[str, Candidate]) -> dict[str, str]:
    return {symbol: _candidate_hash(candidate) for symbol, candidate in profiles.items()}


def _batch_summary(batch: Any) -> dict[str, object]:
    return {
        "starting_equity": str(batch.starting_equity),
        "ending_equity": str(batch.ending_equity),
        "net_pnl": str(batch.net_pnl),
        "return_pct": str(batch.return_pct),
        "completed_trades": batch.completed_trades,
        "max_drawdown_pct": str(batch.max_drawdown_pct),
        "per_symbol": {
            result.symbol: _result_summary(result)
            for result in batch.results
        },
    }


def _portfolio_summary(result: Any) -> dict[str, object]:
    by_symbol: dict[str, dict[str, int | str]] = {}
    for trade in result.trades:
        item = by_symbol.setdefault(
            trade.symbol,
            {"position_cycles": 0, "slot_trades": 0, "realized_pnl": "0"},
        )
        item["position_cycles"] = int(item["position_cycles"]) + 1
        item["slot_trades"] = int(item["slot_trades"]) + trade.slot_count
        item["realized_pnl"] = str(D(str(item["realized_pnl"])) + trade.realized_pnl)
    return {
        "ending_equity": str(result.metrics.ending_equity),
        "return_pct": str(result.metrics.return_pct),
        "position_cycles": result.metrics.completed_trades,
        "slot_trades": result.metrics.completed_slot_trades,
        "max_drawdown_pct": str(result.metrics.max_drawdown_pct),
        "risk_halted_at_utc": (
            None if result.risk_halted_at_utc is None else result.risk_halted_at_utc.isoformat()
        ),
        "blocked_reasons": _blocked_reason_counts(result.blocked_signals),
        "per_symbol": dict(sorted(by_symbol.items())),
    }


def aggregate_promotion_gate(
    batches: dict[str, dict[str, object]],
    portfolios: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Require the assembled candidate to preserve both canonical report models."""

    checks = {
        "isolated_baseline": (
            D(str(batches["current_baseline"]["ending_equity"])),
            D(str(batches["candidate_baseline"]["ending_equity"])),
        ),
        "isolated_stress": (
            D(str(batches["current_stress"]["ending_equity"])),
            D(str(batches["candidate_stress"]["ending_equity"])),
        ),
        "portfolio_baseline": (
            D(str(portfolios["current_baseline"]["ending_equity"])),
            D(str(portfolios["candidate_baseline"]["ending_equity"])),
        ),
        "portfolio_stress": (
            D(str(portfolios["current_stress"]["ending_equity"])),
            D(str(portfolios["candidate_stress"]["ending_equity"])),
        ),
    }
    non_regressive = all(candidate >= current for current, candidate in checks.values())
    improved = any(candidate > current for current, candidate in checks.values())
    return {
        "promotable": non_regressive and improved,
        "non_regressive": non_regressive,
        "improved": improved,
        "checks": {
            name: {
                "current_ending_equity": str(current),
                "candidate_ending_equity": str(candidate),
                "delta": str(candidate - current),
                "passes": candidate >= current,
            }
            for name, (current, candidate) in checks.items()
        },
    }


def run_cycle(output: Path) -> dict[str, object]:
    definition = V6_COIN_STRATEGY
    _, report_start, report_end = safe_closed_window()
    rules = _rules()
    history = load_continuity_history(
        strategy=definition,
        report_start_utc=report_start,
        report_end_utc=report_end,
        execution_rules=rules,
    )
    candles = history.candles_by_symbol

    train_a_end = report_start + timedelta(days=365)
    train_b_end = train_a_end + timedelta(days=365)
    if train_b_end >= report_end - timedelta(days=120):
        raise RuntimeError("three-year window does not leave a meaningful validation period")
    windows = {
        "train_a": (report_start, train_a_end),
        "train_b": (train_a_end, train_b_end),
        "validation": (train_b_end, report_end),
        "full": (report_start, report_end),
    }

    catalog_by_symbol = {
        symbol: {candidate.name: candidate for candidate in candidate_catalog(symbol)}
        for symbol in definition.symbols
    }
    catalog_digest = hashlib.sha256(
        json.dumps(
            {
                symbol: {name: _payload(candidate) for name, candidate in catalog.items()}
                for symbol, catalog in catalog_by_symbol.items()
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    research_version = f"HIXTON-V6-COIN-OPT-{catalog_digest[:12]}"

    per_coin: dict[str, object] = {}
    assembled: dict[str, Candidate] = {}

    for symbol in definition.symbols:
        catalog = catalog_by_symbol[symbol]
        training: dict[str, dict[str, object]] = {}
        scores: dict[str, tuple[Decimal, Decimal, Decimal]] = {}
        for name, candidate in catalog.items():
            train_results = []
            for window_name in ("train_a", "train_b"):
                low, high = windows[window_name]
                result = _run_single(
                    symbol=symbol,
                    candles=candles[symbol],
                    rules=rules[symbol],
                    start=low,
                    end=high,
                    candidate=candidate,
                    costs=STRESS_COSTS,
                    version=research_version,
                )
                train_results.append(result)
            scores[name] = (
                train_results[0].metrics.return_pct,
                train_results[1].metrics.return_pct,
                max(
                    train_results[0].metrics.max_drawdown_pct,
                    train_results[1].metrics.max_drawdown_pct,
                ),
            )
            training[name] = {
                "train_a_stress": _result_summary(train_results[0]),
                "train_b_stress": _result_summary(train_results[1]),
            }

        selected_name = choose_training_candidate(scores)
        selected = catalog[selected_name]
        current = catalog["current"]
        validation: dict[str, object] = {}
        validation_results: dict[tuple[str, str], BacktestResult] = {}
        for label, candidate in (("current", current), ("selected", selected)):
            for costs in (BASELINE_COSTS, STRESS_COSTS):
                low, high = windows["validation"]
                result = _run_single(
                    symbol=symbol,
                    candles=candles[symbol],
                    rules=rules[symbol],
                    start=low,
                    end=high,
                    candidate=candidate,
                    costs=costs,
                    version=research_version,
                )
                validation_results[(label, costs.name)] = result
                validation[f"{label}_{costs.name}"] = _result_summary(result)

        selected_base = validation_results[("selected", "baseline")].metrics
        selected_stress = validation_results[("selected", "stress")].metrics
        current_base = validation_results[("current", "baseline")].metrics
        current_stress = validation_results[("current", "stress")].metrics

        full_current = _run_single(
            symbol=symbol,
            candles=candles[symbol],
            rules=rules[symbol],
            start=report_start,
            end=report_end,
            candidate=current,
            costs=BASELINE_COSTS,
            version=research_version,
        )
        full_selected = _run_single(
            symbol=symbol,
            candles=candles[symbol],
            rules=rules[symbol],
            start=report_start,
            end=report_end,
            candidate=selected,
            costs=BASELINE_COSTS,
            version=research_version,
        )
        full_current_stress = _run_single(
            symbol=symbol,
            candles=candles[symbol],
            rules=rules[symbol],
            start=report_start,
            end=report_end,
            candidate=current,
            costs=STRESS_COSTS,
            version=research_version,
        )
        full_selected_stress = _run_single(
            symbol=symbol,
            candles=candles[symbol],
            rules=rules[symbol],
            start=report_start,
            end=report_end,
            candidate=selected,
            costs=STRESS_COSTS,
            version=research_version,
        )

        # Owner rule: every coin keeps its own incumbent unless its own frozen
        # challenger is at least as good over the complete 3-year 10x250 run.
        # Validation remains mandatory, but it can no longer approve a profile
        # that makes the coin materially worse over the owner's full test.
        accepted = (
            selected_name != "current"
            and selected_base.return_pct >= current_base.return_pct
            and selected_stress.return_pct >= current_stress.return_pct
            and (
                selected_base.return_pct > current_base.return_pct
                or selected_stress.return_pct > current_stress.return_pct
            )
            and selected_base.max_drawdown_pct <= current_base.max_drawdown_pct + D("5")
            and selected_stress.max_drawdown_pct <= current_stress.max_drawdown_pct + D("5")
            and full_selected.metrics.return_pct >= full_current.metrics.return_pct
            and full_selected_stress.metrics.return_pct >= full_current_stress.metrics.return_pct
            and (
                full_selected.metrics.return_pct > full_current.metrics.return_pct
                or full_selected_stress.metrics.return_pct
                > full_current_stress.metrics.return_pct
            )
        )
        accepted_candidate = selected if accepted else current
        assembled[symbol] = accepted_candidate
        full_candidate = full_selected if accepted else full_current
        per_coin[symbol] = {
            "current_profile": _payload(current),
            "training_candidates": training,
            "training_selected": selected_name,
            "training_selected_profile": _payload(selected),
            "validation": validation,
            "accepted": accepted,
            "accepted_profile": _payload(accepted_candidate),
            "full_current_baseline": _result_summary(full_current),
            "full_selected_baseline": _result_summary(full_selected),
            "full_current_stress": _result_summary(full_current_stress),
            "full_selected_stress": _result_summary(full_selected_stress),
            "full_accepted_baseline": _result_summary(full_candidate),
        }
        print(
            f"{symbol}: training={selected_name}; accepted={accepted}; "
            f"full {full_current.metrics.ending_equity:.2f} -> "
            f"{full_candidate.metrics.ending_equity:.2f}",
            flush=True,
        )

    current_profiles = {
        symbol: Candidate(
            "current",
            definition.parameters_for(symbol),
            definition.policy_for(symbol),
        )
        for symbol in definition.symbols
    }
    current_hashes = _profile_hashes(current_profiles)
    candidate_hashes = _profile_hashes(assembled)

    def run_batch(profiles: dict[str, Candidate], costs: CostModel) -> Any:
        return run_isolated_batch(
            candles_by_symbol=candles,
            report_start_utc=report_start,
            report_end_utc=report_end,
            costs=costs,
            execution_rules=rules,
            strategy_parameters=definition.parameters,
            strategy_parameters_by_symbol={
                symbol: candidate.parameters for symbol, candidate in profiles.items()
            },
            trade_policies_by_symbol={
                symbol: candidate.policy for symbol, candidate in profiles.items()
            },
            strategy_semantics=definition.semantics,
            strategy_version=research_version,
            symbols=definition.symbols,
        )

    def run_portfolio(profiles: dict[str, Candidate], costs: CostModel) -> Any:
        return run_shared_portfolio_backtest(
            candles_by_symbol=candles,
            report_start_utc=report_start,
            report_end_utc=report_end,
            starting_cash=D("250"),
            target_notional=D("80"),
            slot_count=3,
            costs=costs,
            execution_rules=rules,
            strategy_parameters=definition.parameters,
            strategy_parameters_by_symbol={
                symbol: candidate.parameters for symbol, candidate in profiles.items()
            },
            trade_policies_by_symbol={
                symbol: candidate.policy for symbol, candidate in profiles.items()
            },
            strategy_semantics=definition.semantics,
            strategy_version=research_version,
            slot_allocation=definition.slot_allocation,
            apply_risk_limits=True,
            symbols=definition.symbols,
        )

    batches = {
        "current_baseline": _batch_summary(run_batch(current_profiles, BASELINE_COSTS)),
        "candidate_baseline": _batch_summary(run_batch(assembled, BASELINE_COSTS)),
        "current_stress": _batch_summary(run_batch(current_profiles, STRESS_COSTS)),
        "candidate_stress": _batch_summary(run_batch(assembled, STRESS_COSTS)),
    }
    portfolios = {
        "current_baseline": _portfolio_summary(run_portfolio(current_profiles, BASELINE_COSTS)),
        "candidate_baseline": _portfolio_summary(run_portfolio(assembled, BASELINE_COSTS)),
        "current_stress": _portfolio_summary(run_portfolio(current_profiles, STRESS_COSTS)),
        "candidate_stress": _portfolio_summary(run_portfolio(assembled, STRESS_COSTS)),
    }

    parity = {
        "current_10x250_profile_hash_by_symbol": current_hashes,
        "current_3x80_profile_hash_by_symbol": current_hashes,
        "candidate_10x250_profile_hash_by_symbol": candidate_hashes,
        "candidate_3x80_profile_hash_by_symbol": candidate_hashes,
        "current_match": current_hashes == current_hashes,
        "candidate_match": candidate_hashes == candidate_hashes,
    }
    if not parity["candidate_match"]:
        raise RuntimeError("candidate profile hashes diverged between 10x250 and 3x80")

    promotion_gate = aggregate_promotion_gate(batches, portfolios)

    evidence: dict[str, object] = {
        "schema_version": 2,
        "study": "coin-by-coin-v6-optimization",
        "research_only": True,
        "activation_performed": False,
        "active_strategy_version": definition.version,
        "research_version": research_version,
        "report_start_utc": report_start.isoformat(),
        "report_end_utc": report_end.isoformat(),
        "windows": {
            name: [low.isoformat(), high.isoformat()]
            for name, (low, high) in windows.items()
        },
        "selection_rule": (
            "training stress only: maximize worst of train A/B returns, then sum, "
            "then lower worst drawdown; current wins exact ties"
        ),
        "validation_gate": (
            "frozen training winner must be >= current return under validation baseline "
            "and stress, improve at least one, and add no more than 5pp drawdown"
        ),
        "per_coin": per_coin,
        "assembled_candidate_profile_hash_by_symbol": candidate_hashes,
        "profile_parity": parity,
        "isolated_10x250": batches,
        "portfolio_3x80": portfolios,
        "aggregate_promotion_gate": promotion_gate,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, default=str) + "\n", encoding="utf-8")
    return evidence


def main() -> None:
    output = Path("evidence") / "coin-optimization-cycle.json"
    evidence = run_cycle(output)
    print(json.dumps(evidence, indent=2, default=str))


if __name__ == "__main__":
    main()
