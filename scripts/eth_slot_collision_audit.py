"""Deterministic ETH M19/M20 shared-slot collision audit.

Research-only diagnostic. It reconstructs the previously observed ETH M19
counterfactual and attributes changed/blocked entry opportunities to the trades
occupying the fixed two 125-USDC slots at that instant. It does not rank or
promote candidates and cannot mutate Paper/Live state.
"""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from pathlib import Path
from typing import Any

from hixton.backtest.continuity import load_continuity_history
from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.domain.capital import capital_plan
from hixton.domain.models import SignalAction
from hixton.domain.versions import V6_COIN_STRATEGY
from hixton.runtime.supervisor import safe_closed_window
from scripts.capital_100_simulation import _candidate_map
from scripts.coin_optimization_cycle import Candidate, _rules


def _run(candles: dict[str, list[Any]], rules: dict[str, Any], profiles: dict[str, Candidate], start: Any, end: Any, costs: Any):
    plan = capital_plan(D("250"))
    return run_shared_portfolio_backtest(
        candles_by_symbol=candles,
        report_start_utc=start,
        report_end_utc=end,
        starting_cash=D("250"),
        target_notional=plan.target_notional_usdc,
        slot_count=plan.slot_count,
        costs=costs,
        execution_rules=rules,
        strategy_parameters=V6_COIN_STRATEGY.parameters,
        strategy_parameters_by_symbol={s:p.parameters for s,p in profiles.items()},
        trade_policies_by_symbol={s:p.policy for s,p in profiles.items()},
        strategy_semantics=V6_COIN_STRATEGY.semantics,
        strategy_version="HIXTON-V6-ETH-M19-COLLISION-AUDIT",
        slot_allocation=plan.allocation_policy,
        apply_risk_limits=True,
        symbols=V6_COIN_STRATEGY.symbols,
    )


def _trade_key(t: Any) -> tuple[str, str, str]:
    return (t.symbol, t.entry_time_utc.isoformat(), t.exit_time_utc.isoformat())


def _trade_row(t: Any) -> dict[str, object]:
    return {
        "symbol": t.symbol,
        "entry_time_utc": t.entry_time_utc.isoformat(),
        "exit_time_utc": t.exit_time_utc.isoformat(),
        "holding_hours": str(t.holding_hours),
        "slot_count": t.slot_count,
        "realized_pnl_usdc": str(t.realized_pnl),
    }


def _blocked_no_slot(result: Any) -> list[dict[str, object]]:
    signal_by_id = {s.signal_id:s for s in result.signals}
    rows = []
    for item in result.blocked_signals:
        if not item.endswith(":NO_FREE_SLOT"):
            continue
        signal_id = item.rsplit(":",1)[0]
        signal = signal_by_id.get(signal_id)
        if signal is None or signal.action is not SignalAction.ENTER_LONG:
            continue
        attempted_fill = signal.candle_close_time_utc + timedelta(hours=1)
        occupiers = [
            t for t in result.trades
            if t.entry_time_utc <= attempted_fill < t.exit_time_utc
        ]
        rows.append({
            "blocked_symbol": signal.symbol,
            "signal_close_time_utc": signal.candle_close_time_utc.isoformat(),
            "attempted_fill_time_utc": attempted_fill.isoformat(),
            "breakout_strength": signal.breakout_strength,
            "occupying_trades": [_trade_row(t) for t in occupiers],
            "occupying_realized_pnl_usdc": str(sum((t.realized_pnl for t in occupiers), D("0"))),
        })
    return rows


def _compare(current: Any, m19: Any) -> dict[str, object]:
    current_map = {_trade_key(t):t for t in current.trades}
    m19_map = {_trade_key(t):t for t in m19.trades}
    removed = [current_map[k] for k in current_map.keys()-m19_map.keys()]
    added = [m19_map[k] for k in m19_map.keys()-current_map.keys()]
    return {
        "current_ending_equity": str(current.metrics.ending_equity),
        "m19_ending_equity": str(m19.metrics.ending_equity),
        "m19_equity_delta_usdc": str(m19.metrics.ending_equity-current.metrics.ending_equity),
        "current_position_cycles": current.metrics.completed_trades,
        "m19_position_cycles": m19.metrics.completed_trades,
        "removed_current_trades": [_trade_row(t) for t in sorted(removed,key=lambda x:x.entry_time_utc)],
        "added_m19_trades": [_trade_row(t) for t in sorted(added,key=lambda x:x.entry_time_utc)],
        "removed_realized_pnl_usdc": str(sum((t.realized_pnl for t in removed),D("0"))),
        "added_realized_pnl_usdc": str(sum((t.realized_pnl for t in added),D("0"))),
        "current_no_free_slot_events": _blocked_no_slot(current),
        "m19_no_free_slot_events": _blocked_no_slot(m19),
    }


def main() -> None:
    _, start, end = safe_closed_window()
    rules = _rules()
    history = load_continuity_history(
        strategy=V6_COIN_STRATEGY,
        report_start_utc=start,
        report_end_utc=end,
        execution_rules=rules,
    )
    current_profiles = _candidate_map(research=False)
    m19_profiles = dict(current_profiles)
    eth = current_profiles["ETHUSDC"]
    m19_profiles["ETHUSDC"] = Candidate(
        "eth_m19_counterfactual",
        replace(eth.parameters, momentum_length=19),
        eth.policy,
    )
    payload = {
        "schema_version": 1,
        "study": "ETH_M19_M20_SHARED_SLOT_COLLISION_AUDIT",
        "research_only": True,
        "promotion_candidate": False,
        "activation_performed": False,
        "report_start_utc": start.isoformat(),
        "report_end_utc": end.isoformat(),
        "baseline": _compare(
            _run(history.candles_by_symbol,rules,current_profiles,start,end,BASELINE_COSTS),
            _run(history.candles_by_symbol,rules,m19_profiles,start,end,BASELINE_COSTS),
        ),
        "stress": _compare(
            _run(history.candles_by_symbol,rules,current_profiles,start,end,STRESS_COSTS),
            _run(history.candles_by_symbol,rules,m19_profiles,start,end,STRESS_COSTS),
        ),
    }
    out=Path("evidence/eth-m19-slot-collision-audit.json")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload,indent=2))


if __name__=="__main__":
    main()
