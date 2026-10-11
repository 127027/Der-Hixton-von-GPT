from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from dataclasses import replace
import pytest
from hixton.data.binance import SymbolRules
from hixton.data.storage import CandleStore
from hixton.data.sync import synchronize_symbol
from tests.golden_reference import deterministic_candles

class Client:
    def __init__(self, candles):
        self.candles = candles
        self.calls = []
    def symbol_rules(self, symbol):
        return SymbolRules(symbol, "TRADING", "BTC", "USDC", True, ("MARKET",), D(".01"), D(".001"), D(".001"), D("5"))
    def fetch_klines(self, symbol, *, start, end_exclusive):
        self.calls.append((start, end_exclusive))
        return [c for c in self.candles if start <= c.open_time_utc < end_exclusive]

@pytest.mark.parametrize("next_open", [True, False])
def test_close_and_next_open_share_one_request_without_provisional_signals(tmp_path, next_open):
    candles = deterministic_candles("BTCUSDC", 60)
    end = candles[-1].open_time_utc
    closed = candles[:-1]
    client = Client(closed + ([replace(candles[-1], closed=False)] if next_open else []))
    with CandleStore(tmp_path / "candles.sqlite3") as store:
        store.put_candles(closed)
        if not next_open:
            # A cached provisional bar must not replace fresh REST confirmation.
            store.put_candles([replace(candles[-1], closed=False)])
        if not next_open:
            with pytest.raises(RuntimeError, match="next opening candle"):
                synchronize_symbol(client=client, store=store, symbol="BTCUSDC", start=closed[0].open_time_utc, end_exclusive=end, include_next_open=True)
        else:
            result = synchronize_symbol(client=client, store=store, symbol="BTCUSDC", start=closed[0].open_time_utc, end_exclusive=end, include_next_open=True)
            assert result.quality.valid
            assert result.quality.candle_count == len(closed)
            assert len(store.load_candles("BTCUSDC", closed_only=False)) == len(candles)
            assert len(store.load_candles("BTCUSDC")) == len(closed)
        assert client.calls == [(end - timedelta(hours=48), end + timedelta(hours=1))]


def test_public_requests_never_hold_the_writer_lock_and_invalid_batch_stays_out(tmp_path):
    candles = deterministic_candles("BTCUSDC", 60)
    end = candles[-1].open_time_utc
    path = tmp_path / "candles.sqlite3"
    with CandleStore(path) as store:
        store.put_candles(candles[:-1])
    with CandleStore(path) as store:
        class LockCheckingClient(Client):
            def fetch_klines(self, *args, **kwargs):
                assert not store._connection.in_transaction
                return super().fetch_klines(*args, **kwargs)
        client = LockCheckingClient(candles[:-1] + [replace(candles[-1], closed=False)])
        assert synchronize_symbol(client=client, store=store, symbol="BTCUSDC", start=candles[0].open_time_utc, end_exclusive=end, include_next_open=True).quality.valid
    with CandleStore(path) as store:
        bad = LockCheckingClient([replace(c, low=c.high+100) for c in candles[:-1]] + [replace(candles[-1], closed=False)])
        with pytest.raises(ValueError, match="data quality"):
            synchronize_symbol(client=bad, store=store, symbol="BTCUSDC", start=candles[0].open_time_utc, end_exclusive=end, include_next_open=True)
        assert store.load_candles("BTCUSDC")[0].ohlc_is_valid
        assert not store._connection.in_transaction


@pytest.mark.parametrize("healthy,complete", [(True,True),(False,True),(True,False)])
def test_recent_refresh_retains_full_history_validation(monkeypatch, healthy, complete):
    from types import SimpleNamespace
    from hixton.runtime import supervisor as module
    from hixton.runtime.state import RuntimeState
    from hixton.domain.versions import strategy_definition
    from tests.test_paper_engine import _point
    strategy = strategy_definition("v8")
    end = datetime.now(UTC).replace(minute=0,second=0,microsecond=0)
    start = end-timedelta(days=365)
    points = {s:(replace(_point(s,end-timedelta(milliseconds=1)),strategy_version=strategy.version),) for s in strategy.symbols}
    state = RuntimeState(symbols=strategy.symbols)
    state._points = points.copy()
    if not complete: state._points.pop(strategy.symbols[-1])
    state.health = "HEALTHY" if healthy else "DEGRADED"
    x = module.RuntimeSupervisor.__new__(module.RuntimeSupervisor)
    x.state=state;x.strategy=strategy
    x.config=SimpleNamespace(database_path="unused.sqlite3",binance_base_url="https://example.invalid")
    x._available_starts={s:start for s in strategy.symbols}
    starts=[];analysis=[]
    class Store:
        def __init__(self,*a,**k): pass
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def integrity_check(self): return True
        def load_symbol_rules(self,s): return SimpleNamespace(tick_size=D(".01"),step_size=D(".01"),min_qty=D(".01"),min_notional=D("5"))
    class Public:
        def __init__(self,*a,**k): pass
        def server_time(self): return datetime.now(UTC)
    def sync(**kw):
        starts.append(kw["start"])
        assert kw["include_next_open"] is True
    def rebuild(*a,**kw):
        analysis.append(kw)
        return points,{}
    monkeypatch.setattr(module,"CandleStore",Store)
    monkeypatch.setattr(module,"BinancePublicClient",Public)
    monkeypatch.setattr(module,"synchronize_symbol",sync)
    monkeypatch.setattr(module,"rebuild_analysis",rebuild)
    monkeypatch.setattr(module,"safe_closed_window",lambda:(start,start+timedelta(hours=400),end))
    x._synchronous_sync()
    assert len(starts)==15
    assert set(starts)=={end-timedelta(hours=48) if healthy and complete else start}
    assert analysis[0]["start"]==start  # Full-history quality and identical indicator seed remain required.
    assert analysis[0]["end_exclusive"]==end
