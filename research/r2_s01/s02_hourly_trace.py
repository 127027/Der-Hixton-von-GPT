"""S02 diagnostic-only observer of identical frozen f56 state, no trading actions."""
from __future__ import annotations
import gzip, json, pathlib
from decimal import Decimal as D
from datetime import timedelta

class Trace:
    def __init__(self, mode):
        self.mode=mode
        self.rows=[]
        self.last_fill=self.last_trade=self.last_block=self.last_signal=0

    def on_closed(self, *, at, cash, equity, position_value, positions, dust, pending, signals, fills, trades, blocked):
        # Observation occurs AFTER native closed candle decisions and before EquityPoint append.
        # No mutable native object escapes this callback; copies are stringified.
        def minimal_fill(f):
            return dict(id=f.signal_id, action=f.action.value, utc=f.fill_time_utc.isoformat(),
                        qty=str(f.base_quantity),gross=str(f.quote_value),
                        fee=str(f.fee_quote_equivalent),adverse=str(f.modeled_spread_slippage))
        def minimal_trade(t):
            return dict(entry=t.entry_signal_id,exit=t.exit_signal_id,symbol=t.symbol,
                        basis=str(t.entry_quote_spend),realized=str(t.realized_pnl))
        new_fills=[minimal_fill(x) for x in fills[self.last_fill:]]
        new_trades=[minimal_trade(x) for x in trades[self.last_trade:]]
        new_blocked=blocked[self.last_block:]
        new_signals=[dict(id=s.signal_id,symbol=s.symbol,action=s.action.value,
                          close=s.candle_close_time_utc.isoformat()) for s in signals[self.last_signal:]]
        self.last_fill=len(fills)
        self.last_trade=len(trades)
        self.last_block=len(blocked)
        self.last_signal=len(signals)
        row=dict(utc=at.isoformat(),cash=str(cash),equity=str(equity),position_value=str(position_value),
                 positions={sym:dict(qty=str(p.quantity),basis=str(p.cost_basis),slots=p.slots,
                                     units=p.allocation_units,entry=p.signal.signal_id)
                            for sym,p in sorted(positions.items())},
                 dust={sym:str(v) for sym,v in sorted(dust.items()) if v>0},
                 pending=[dict(id=s.signal_id,symbol=s.symbol,action=s.action.value) for s in pending],
                 signals=new_signals, fills=new_fills,trades=new_trades, blocked=list(new_blocked),
                 occupied_slots=sum(p.slots for p in positions.values()))
        if D(row["cash"])+D(row["position_value"])!=D(row["equity"]):
            raise RuntimeError("S02_TRACE_MONEY_CONSERVATION_FAIL")
        if self.rows:
            from datetime import datetime
            if datetime.fromisoformat(row["utc"])-datetime.fromisoformat(self.rows[-1]["utc"])!=timedelta(hours=1):
                raise RuntimeError("S02_TRACE_NONCONTIGUOUS_HOURS")
        self.rows.append(row)

    def ensure_native(self, result):
        if len(self.rows)!=len(result.equity_curve):
            raise RuntimeError("S02_TRACE_HOURLY_ROWS_MISMATCH")
        for row,pt in zip(self.rows,result.equity_curve,strict=True):
            if (row["utc"]!=pt.time_utc.isoformat() or D(row["cash"])!=pt.cash or
                D(row["position_value"])!=pt.position_value or D(row["equity"])!=pt.equity):
                raise RuntimeError("S02_TRACE_ORIGINAL_NATIVE_EQUITY_DRIFT")
        if sum(len(r["fills"]) for r in self.rows)!=len(result.fills):
            raise RuntimeError("S02_TRACE_FILL_COUNT_MISMATCH")

    def write(self, path, result, *, frozen, hash_policy):
        self.ensure_native(result)
        path=pathlib.Path(path)
        if path.exists():
            raise RuntimeError("S02_TRACE_NO_OVERWRITE")
        path.parent.mkdir(parents=True,exist_ok=True)
        with gzip.open(path,"wt",encoding="utf-8",compresslevel=6) as f:
            json.dump(dict(kind="R2-S02-DIAG-002",mode=self.mode,frozen=frozen,
                           source_policy_blob_sha=hash_policy,
                           ending_equity=str(result.metrics.ending_equity),
                           total_native_fills=len(result.fills),
                           total_native_trades=len(result.trades),
                           rows=self.rows),f,separators=(",",":"),ensure_ascii=False)

def instrument_trace(source):
    needle="            equity_curve.append(\n"
    if source.count(needle)!=1:
        raise RuntimeError("S02_TRACE_FROZEN_INSERTION_DRIFT")
    return source.replace(needle,
        """            R2_S02_TRACE.on_closed(
                at=max(candle.close_time_utc for candle in row),
                cash=cash,equity=equity,position_value=position_value,
                positions=positions,dust=dust,pending=pending,
                signals=signals,fills=fills,trades=trades,blocked=blocked)
            equity_curve.append(
""")
