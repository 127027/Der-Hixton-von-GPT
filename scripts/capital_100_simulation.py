"""Research-only 100-USDC capital-layout simulation.

Compares ten isolated 100-USDC ledgers with two shared 1,000-USDC / 10x100
portfolio allocation policies. Runs both the current canonical V6 profiles and
the last A01-A11-approved research candidate profile map. Never mutates V6,
Paper state or Live state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from hixton.backtest.continuity import continuity_manifest_data, load_continuity_history
from hixton.backtest.engine import run_single_backtest
from hixton.backtest.metrics import drawdown
from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS, EquityPoint
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.domain.allocation import ONE_PER_SYMBOL, RANKED_REPEAT
from hixton.domain.versions import V6_COIN_STRATEGY
from hixton.runtime.supervisor import safe_closed_window
from scripts.coin_optimization_cycle import Candidate, _rules, candidate_catalog

D = Decimal
RESEARCH_OVERRIDES = {
    "XRPUSDC": "cmo15",
    "AVAXUSDC": "band_plus_06",
    "DOTUSDC": "cmo35",
}


def _candidate_map(*, research: bool) -> dict[str, Candidate]:
    result: dict[str, Candidate] = {}
    for symbol in V6_COIN_STRATEGY.symbols:
        current = Candidate(
            "current",
            V6_COIN_STRATEGY.parameters_for(symbol),
            V6_COIN_STRATEGY.policy_for(symbol),
        )
        if not research or symbol not in RESEARCH_OVERRIDES:
            result[symbol] = current
            continue
        catalog = {candidate.name: candidate for candidate in candidate_catalog(symbol)}
        name = RESEARCH_OVERRIDES[symbol]
        if name not in catalog:
            raise RuntimeError(f"{symbol}: research candidate {name} missing")
        result[symbol] = catalog[name]
    return result


def _profile_hashes(profiles: dict[str, Candidate]) -> dict[str, str]:
    return {
        symbol: hashlib.sha256(
            json.dumps(
                {
                    "parameters": asdict(candidate.parameters),
                    "trade_policy": asdict(candidate.policy),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        for symbol, candidate in profiles.items()
    }


def _isolated(
    candles: dict[str, list[Any]],
    rules: dict[str, Any],
    profiles: dict[str, Candidate],
    start: Any,
    end: Any,
    costs: Any,
) -> dict[str, object]:
    results = []
    for symbol in V6_COIN_STRATEGY.symbols:
        candidate = profiles[symbol]
        results.append(
            run_single_backtest(
                symbol=symbol,
                candles=candles[symbol],
                report_start_utc=start,
                report_end_utc=end,
                starting_cash=D("100"),
                target_notional=D("100"),
                costs=costs,
                execution_rules=rules[symbol],
                strategy_parameters=candidate.parameters,
                strategy_semantics=V6_COIN_STRATEGY.semantics,
                strategy_version="HIXTON-V6-CAPITAL100-RESEARCH",
                trade_policy=candidate.policy,
            )
        )
    combined_curve = tuple(
        EquityPoint(
            points[0].time_utc,
            D("0"),
            D("0"),
            sum((point.equity for point in points), D("0")),
            any(point.active_position for point in points),
        )
        for points in zip(*(result.equity_curve for result in results), strict=True)
    )
    _, max_drawdown_pct = drawdown(combined_curve)
    ending = sum((result.metrics.ending_equity for result in results), D("0"))
    return {
        "profile_hash_by_symbol": _profile_hashes(profiles),
        "starting_equity": "1000.00",
        "ending_equity": str(ending),
        "net_pnl": str(ending - D("1000")),
        "return_pct": str((ending / D("1000") - D("1")) * D("100")),
        "completed_trades": sum(result.metrics.completed_trades for result in results),
        "max_drawdown_pct": str(max_drawdown_pct),
        "per_symbol": {
            result.symbol: {
                "starting_equity": "100.00",
                "ending_equity": str(result.metrics.ending_equity),
                "net_pnl": str(result.metrics.net_pnl),
                "return_pct": str(result.metrics.return_pct),
                "completed_trades": result.metrics.completed_trades,
                "max_drawdown_pct": str(result.metrics.max_drawdown_pct),
                "blocked_reasons": sorted(
                    {
                        item.rsplit(":", 1)[-1]
                        for item in result.blocked_signals
                    }
                ),
            }
            for result in results
        },
    }


def _portfolio(
    candles: dict[str, list[Any]],
    rules: dict[str, Any],
    profiles: dict[str, Candidate],
    start: Any,
    end: Any,
    costs: Any,
    allocation: str,
) -> dict[str, object]:
    parameters = {symbol: candidate.parameters for symbol, candidate in profiles.items()}
    policies = {symbol: candidate.policy for symbol, candidate in profiles.items()}
    result = run_shared_portfolio_backtest(
        candles_by_symbol=candles,
        report_start_utc=start,
        report_end_utc=end,
        starting_cash=D("1000"),
        target_notional=D("100"),
        slot_count=10,
        costs=costs,
        execution_rules=rules,
        strategy_parameters=V6_COIN_STRATEGY.parameters,
        strategy_parameters_by_symbol=parameters,
        trade_policies_by_symbol=policies,
        strategy_semantics=V6_COIN_STRATEGY.semantics,
        strategy_version="HIXTON-V6-CAPITAL100-RESEARCH",
        slot_allocation=allocation,
        apply_risk_limits=True,
        symbols=V6_COIN_STRATEGY.symbols,
    )
    by_symbol: dict[str, dict[str, object]] = {}
    for trade in result.trades:
        item = by_symbol.setdefault(
            trade.symbol,
            {"position_cycles": 0, "slot_trades": 0, "realized_pnl": D("0")},
        )
        item["position_cycles"] = int(item["position_cycles"]) + 1
        item["slot_trades"] = int(item["slot_trades"]) + trade.slot_count
        item["realized_pnl"] = D(str(item["realized_pnl"])) + trade.realized_pnl
    return {
        "profile_hash_by_symbol": _profile_hashes(profiles),
        "starting_equity": "1000.00",
        "ending_equity": str(result.metrics.ending_equity),
        "net_pnl": str(result.metrics.net_pnl),
        "return_pct": str(result.metrics.return_pct),
        "position_cycles": result.metrics.completed_trades,
        "slot_trades": result.metrics.completed_slot_trades,
        "max_drawdown_pct": str(result.metrics.max_drawdown_pct),
        "risk_halted_at_utc": (
            None if result.risk_halted_at_utc is None else result.risk_halted_at_utc.isoformat()
        ),
        "blocked_reasons": {
            reason: sum(
                1 for item in result.blocked_signals if item.rsplit(":", 1)[-1] == reason
            )
            for reason in sorted(
                {item.rsplit(":", 1)[-1] for item in result.blocked_signals}
            )
        },
        "per_symbol": {
            symbol: {
                **item,
                "realized_pnl": str(item["realized_pnl"]),
            }
            for symbol, item in sorted(by_symbol.items())
        },
    }


def run(output: Path) -> dict[str, object]:
    _, report_start, report_end = safe_closed_window()
    rules = _rules()
    history = load_continuity_history(
        strategy=V6_COIN_STRATEGY,
        report_start_utc=report_start,
        report_end_utc=report_end,
        execution_rules=rules,
    )
    current = _candidate_map(research=False)
    research = _candidate_map(research=True)
    variants: dict[str, object] = {}
    for label, profiles in (("current", current), ("research_candidate", research)):
        variants[label] = {
            "profile_hash_by_symbol": _profile_hashes(profiles),
            "baseline": {
                "isolated_10x100": _isolated(
                    history.candles_by_symbol,
                    rules,
                    profiles,
                    report_start,
                    report_end,
                    BASELINE_COSTS,
                ),
                "shared_10x100_one_per_symbol": _portfolio(
                    history.candles_by_symbol,
                    rules,
                    profiles,
                    report_start,
                    report_end,
                    BASELINE_COSTS,
                    ONE_PER_SYMBOL,
                ),
                "shared_10x100_ranked_repeat": _portfolio(
                    history.candles_by_symbol,
                    rules,
                    profiles,
                    report_start,
                    report_end,
                    BASELINE_COSTS,
                    RANKED_REPEAT,
                ),
            },
            "stress": {
                "isolated_10x100": _isolated(
                    history.candles_by_symbol,
                    rules,
                    profiles,
                    report_start,
                    report_end,
                    STRESS_COSTS,
                ),
                "shared_10x100_one_per_symbol": _portfolio(
                    history.candles_by_symbol,
                    rules,
                    profiles,
                    report_start,
                    report_end,
                    STRESS_COSTS,
                    ONE_PER_SYMBOL,
                ),
                "shared_10x100_ranked_repeat": _portfolio(
                    history.candles_by_symbol,
                    rules,
                    profiles,
                    report_start,
                    report_end,
                    STRESS_COSTS,
                    RANKED_REPEAT,
                ),
            },
        }
    for profile_label, payload in variants.items():
        model_hashes = [
            payload["baseline"][model]["profile_hash_by_symbol"]
            for model in (
                "isolated_10x100",
                "shared_10x100_one_per_symbol",
                "shared_10x100_ranked_repeat",
            )
        ]
        payload["profile_match_across_models"] = (
            model_hashes[0] == model_hashes[1] == model_hashes[2]
        )
        if payload["profile_match_across_models"] is not True:
            raise RuntimeError(
                f"{profile_label}: profile maps diverged across 100-USDC models"
            )

    baseline_models = {
        f"{profile}:{model}": D(str(payload["baseline"][model]["ending_equity"]))
        for profile, payload in variants.items()
        for model in (
            "isolated_10x100",
            "shared_10x100_one_per_symbol",
            "shared_10x100_ranked_repeat",
        )
    }
    stress_models = {
        f"{profile}:{model}": D(str(payload["stress"][model]["ending_equity"]))
        for profile, payload in variants.items()
        for model in (
            "isolated_10x100",
            "shared_10x100_one_per_symbol",
            "shared_10x100_ranked_repeat",
        )
    }
    result = {
        "schema_version": 1,
        "study": "TEN_COINS_100_USDC_CAPITAL_LAYOUT",
        "research_only": True,
        "activation_performed": False,
        "report_start_utc": report_start.isoformat(),
        "report_end_utc": report_end.isoformat(),
        "history": continuity_manifest_data(history),
        "execution_quote_asset": "USDC",
        "research_overrides": RESEARCH_OVERRIDES,
        "variants": variants,
        "baseline_best_by_ending_equity": max(
            baseline_models, key=lambda key: baseline_models[key]
        ),
        "stress_best_by_ending_equity": max(
            stress_models, key=lambda key: stress_models[key]
        ),
        "baseline_ending_equity_by_model": {
            key: str(value) for key, value in baseline_models.items()
        },
        "stress_ending_equity_by_model": {
            key: str(value) for key, value in stress_models.items()
        },
        "limitations": [
            "Historical simulation, not a forecast or guaranteed live result.",
            "10x100 isolated has ten independent 100-USDC ledgers; shared variants "
            "have one 1,000-USDC ledger.",
            "ranked_repeat may allocate multiple 100-USDC slots to the strongest "
            "simultaneous signal.",
            "Research candidate is not automatically promoted into canonical V6 or Live.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    return result


def main() -> None:
    result = run(Path("evidence") / "capital-100-simulation.json")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
