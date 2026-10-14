"""Offline exact native/shared implementation verification; no private API access."""
import sys
import json
from dataclasses import replace
from pathlib import Path
from decimal import Decimal as D
from research_coin_policies_20261011 import SnapshotOnly
from datetime import datetime
INPUTS = json.loads(Path(r"C:/Users/andre/OneDrive/Desktop/Neuer Ordner/Pruefergebnisse/Coin-Nachoptimierung-20261013/Inputs.json").read_text(encoding="utf-8"))
START = datetime.fromisoformat(INPUTS["start"])
END = datetime.fromisoformat(INPUTS["end"])
SEED = D(INPUTS["portfolio_seed"])
from hixton.backtest.continuity import load_continuity_history
from hixton.backtest.models import CURRENT_COSTS, STRESS_COSTS, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.data.storage import CandleStore
from hixton.domain.versions import strategy_definition
from weighted_tranche_portfolio_20261013 import run_shared_portfolio_backtest as research_run

root = Path(INPUTS["market_snapshot"])
strategy = strategy_definition("v8r")
rules = {}
with CandleStore(root / "hixton-usdc.sqlite3", read_only=True) as store:
    for symbol in strategy.symbols:
        r = store.load_symbol_rules(symbol)
        rules[symbol] = ExecutionRules(r.tick_size, r.step_size, r.min_qty, r.min_notional)
history = load_continuity_history(
    strategy=strategy, report_start_utc=START, report_end_utc=END,
    execution_rules=rules, native_database_path=root / "hixton-usdc.sqlite3",
    cache_path=root / "backtest-history.sqlite3", client=SnapshotOnly(),
)
rows = []
for cost, ending in ([] if len(sys.argv) > 1 and sys.argv[1] != "--cost-only" else [(CURRENT_COSTS, "31825.37351337113595000000"), (STRESS_COSTS, "22399.5587092068570000000")]):
    args = dict(candles_by_symbol=history.candles_by_symbol, report_start_utc=START,
                report_end_utc=END, starting_cash=SEED, target_notional=SEED / 2,
                execution_rules=rules, strategy=strategy, reinvest_profits=True,
                autonomous_spot=True, costs=cost)
    product = run_shared_portfolio_backtest(**args)
    reference = research_run(**args, research_weights=(10,5,5), research_dd_trigger_pct=D(10))
    assert product.metrics.ending_equity == D(ending)
    assert product.equity_curve == reference.equity_curve
    assert product.fills == reference.fills
    assert product.metrics.max_drawdown_pct == reference.metrics.max_drawdown_pct
    rows.append(dict(cost=cost.name, ending=str(product.metrics.ending_equity),
                     dd=str(product.metrics.max_drawdown_pct), fills=len(product.fills),
                     distinct_positions_max=product.max_concurrent_positions, status="PASS"))
    print(rows[-1], flush=True)
if rows:
    Path(r"C:/Users/andre/OneDrive/Desktop/Neuer Ordner/Pruefergebnisse/Update-ETH8-20261013/native-replay.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
if len(sys.argv)>1 and sys.argv[1]=="--cost-only":
    raise SystemExit(0)

from datetime import timedelta
from hixton.domain.strategy import evaluate_batch
from hixton.paper.engine import initialize_paper_at_latest, process_new_closed_points, load_paper_portfolio
from hixton.paper.models import PaperSettings
from hixton.paper.storage import PaperStore
from tempfile import mkdtemp

if len(sys.argv) > 1:
    path = Path(sys.argv[1])
else:
    print("Full 3-year Paper parity starting", flush=True)
    points = {
        sym: tuple(evaluate_batch(sym, candles, parameters=strategy.parameters_for(sym),
                                  semantics=strategy.semantics_for(sym), strategy_version=strategy.version))
        for sym, candles in history.candles_by_symbol.items()
    }
    path = Path(mkdtemp(prefix="hixton-dd10-full-paper-")) / "paper.sqlite3"
    initialize_paper_at_latest(str(path), {s: p[:400] for s, p in points.items()},
        strategy_key=strategy.key, strategy_version=strategy.version, starting_cash_usdc=SEED)
    with PaperStore(path) as store:
        store.save_settings(PaperSettings(max_capital_usdc=SEED, auto_budget_enabled=True,
                                         autonomous_performance_enabled=True))
    process_new_closed_points(str(path), points, rules, strategy_key=strategy.key,
        strategy_version=strategy.version, execution_candles_by_symbol=history.candles_by_symbol,
        trade_policies_by_symbol=strategy.policy_map())
portfolio = load_paper_portfolio(str(path), {s: D(str(c[-1].close)) for s,c in history.candles_by_symbol.items()},
    strategy_key=strategy.key, strategy_version=strategy.version)
with PaperStore(path) as store:
    events = [store._row_to_event(row) for row in store._connection.execute("SELECT * FROM paper_events WHERE status='FILLED'")]
    peak_positions_units = [p.allocation_units for p in store.load_positions()]
args = dict(candles_by_symbol=history.candles_by_symbol, report_start_utc=START,
                report_end_utc=END, starting_cash=SEED, target_notional=SEED / 2,
                execution_rules=rules, strategy=strategy, reinvest_profits=True,
                autonomous_spot=True, costs=CURRENT_COSTS)
native = run_shared_portfolio_backtest(**args)
assert abs(portfolio.equity_usdc-native.metrics.ending_equity) < D("1e-18"), (portfolio.equity_usdc,native.metrics.ending_equity)
import hashlib
# Ledger-specific handoff namespaces predate this patch. Normalize ONLY the
# documented forced-handoff identity from its same Core trigger and execution time.
def canonical_paper_signal(event):
    if event.reason and event.reason.startswith("CORE_CAPACITY_HANDOFF::"):
        core_id = event.reason.split("::",1)[1]
        return hashlib.sha256(
            f"CORE_CAPACITY_HANDOFF|{event.symbol}|{core_id}|{event.occurred_at_utc.isoformat()}".encode()
        ).hexdigest()
    return event.signal_id
assert sorted((canonical_paper_signal(e),e.base_quantity) for e in events)==sorted((f.signal_id,f.base_quantity) for f in native.fills)
by_id={s.signal_id:s for s in native.signals}
assert sorted((e.symbol,e.action,e.occurred_at_utc,e.base_quantity,e.execution_price) for e in events)==sorted((by_id[f.signal_id].symbol,f.action.value,f.fill_time_utc,f.base_quantity,f.fill_price) for f in native.fills)
payload = dict(status="PASS", period=[START.isoformat(),END.isoformat()],
               paper_ending=str(portfolio.equity_usdc), backtest_ending=str(native.metrics.ending_equity),
               matching_fills=len(events), normalized_legacy_handoff_ids=sum(bool(e.reason and e.reason.startswith("CORE_CAPACITY_HANDOFF::")) for e in events), paper_database=str(path))
Path(r"C:/Users/andre/OneDrive/Desktop/Neuer Ordner/Pruefergebnisse/Update-ETH8-20261013/full-paper-parity.json").write_text(json.dumps(payload,indent=2),encoding="utf-8")
print(payload,flush=True)
