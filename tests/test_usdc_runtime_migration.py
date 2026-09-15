"""Migration regressions use public-data fixtures, never real keys/accounts."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from hixton.constants import SYMBOLS
from hixton.data.binance import SymbolRules
from hixton.domain.versions import V6_COIN_STRATEGY
from hixton.live.credentials import WindowsVault
from hixton.runtime.analysis import available_report_start
from hixton.runtime.supervisor import RuntimeSupervisor
from tests.golden_reference import deterministic_candles
from tests.test_live_preparation import config_for


def test_available_window_keeps_gaps_and_missing_tail_blocked():
    candles = deterministic_candles(SYMBOLS[0], 700, 10)
    start = candles[400].open_time_utc
    end = candles[-1].open_time_utc + timedelta(hours=1)
    later = candles[100:]
    assert available_report_start({SYMBOLS[0]: later}, start, end) == candles[500].open_time_utc
    for broken in (later[:-1], later[:30] + later[31:], []):
        with pytest.raises(ValueError):
            available_report_start({SYMBOLS[0]: broken}, start, end)


def test_usdc_startup_uses_common_real_history_and_matching_backtest_window(tmp_path, monkeypatch):
    all_data = {
        symbol: deterministic_candles(symbol, 1000, index) for index, symbol in enumerate(SYMBOLS)
    }
    first = all_data[SYMBOLS[0]][0].open_time_utc
    end = all_data[SYMBOLS[0]][-1].open_time_utc + timedelta(hours=1)
    starts = {symbol: first + timedelta(hours=index * 10) for index, symbol in enumerate(SYMBOLS)}

    class Public:
        def __init__(self, **kwargs):
            pass

        def server_time(self):
            from datetime import UTC, datetime

            return datetime.now(UTC)

        def first_available_open(self, symbol, **kwargs):
            return starts[symbol]

        def symbol_rules(self, symbol):
            return SymbolRules(
                symbol,
                "TRADING",
                symbol.removesuffix("USDC"),
                "USDC",
                True,
                ("MARKET",),
                Decimal("0.01"),
                Decimal("0.00001"),
                Decimal("0.00001"),
                Decimal("5"),
            )

        def fetch_klines(self, symbol, *, start, end_exclusive):
            if start == end:
                last = all_data[symbol][-1]
                return [
                    replace(
                        last,
                        open_time_utc=end,
                        close_time_utc=end + timedelta(hours=1) - timedelta(milliseconds=1),
                        closed=False,
                    )
                ]
            return [
                c
                for c in all_data[symbol]
                if max(start, starts[symbol]) <= c.open_time_utc < end_exclusive
            ]

    monkeypatch.setattr("hixton.runtime.supervisor.BinancePublicClient", Public)
    monkeypatch.setattr(
        "hixton.runtime.supervisor.safe_closed_window",
        lambda: (first, first + timedelta(hours=400), end),
    )
    supervisor = RuntimeSupervisor(config_for(tmp_path))
    points, quality, _ = supervisor._synchronous_sync()
    common = max(starts.values())
    assert all(p[0].candle.open_time_utc == common for p in points.values())
    assert all(q.valid for q in quality.values())
    assert all(p[-1].tradable for p in points.values())
    assert all(p[-1].strategy_version == V6_COIN_STRATEGY.version for p in points.values())
    snapshot = {s: [p.candle for p in series] for s, series in points.items()}
    assert available_report_start(snapshot, first + timedelta(hours=400), end) == (
        common + timedelta(hours=400)
    )


def test_default_usdc_database_keeps_original_credential_namespace(tmp_path):
    old = WindowsVault(tmp_path / "data" / "hixton.sqlite3")
    new = WindowsVault(tmp_path / "data" / "hixton-usdc.sqlite3")
    assert old.prefix == new.prefix
    assert new.prefix != WindowsVault(tmp_path / "other" / "hixton-usdc.sqlite3").prefix


def test_old_usdt_paper_database_is_rejected_before_mutation(tmp_path):
    import sqlite3

    from hixton.paper.storage import PaperStore

    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            "CREATE TABLE paper_account(cash_text TEXT);"
            "INSERT INTO paper_account VALUES('250');"
            "CREATE TABLE paper_checkpoints(symbol TEXT);"
            "INSERT INTO paper_checkpoints VALUES('BTCUSDT');"
        )
    before = path.read_bytes()
    with pytest.raises(RuntimeError, match="Legacy USDT"):
        PaperStore(path)
    assert path.read_bytes() == before
