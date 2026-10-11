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
