"""Local-only migration and closed-bar wake-up regression tests."""

import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import UTC, datetime
from threading import Barrier

from hixton.constants import SYMBOLS
from hixton.data.quality import audit_candles
from hixton.paper.storage import PaperStore
from hixton.runtime.supervisor import RuntimeSupervisor
from tests.test_live_preparation import config_for
from tests.test_paper_engine import _point


def test_parallel_legacy_position_migration_is_atomic(tmp_path):
    path = tmp_path / "paper.sqlite3"
    with PaperStore(path):
        pass
    with sqlite3.connect(path) as connection:
        connection.execute("ALTER TABLE paper_positions DROP COLUMN highest_close_text")
        connection.execute("ALTER TABLE paper_positions DROP COLUMN entry_atr_text")
    barrier = Barrier(8)

    def open_store(_):
        barrier.wait(timeout=10)
        with PaperStore(path) as store:
            columns = {
                row["name"]
                for row in store._connection.execute("PRAGMA table_info(paper_positions)")
            }
            assert {"entry_atr_text", "highest_close_text"} <= columns

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(open_store, range(8)))
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_closed_bar_wakes_watchdog_without_waiting_for_poll_interval(tmp_path, monkeypatch):
    async def scenario():
        supervisor = RuntimeSupervisor(config_for(tmp_path))
        now = datetime.now(UTC)
        supervisor.state.last_stream_update_utc = now
        points = {
            symbol: (_point(symbol, now.replace(minute=0, second=0, microsecond=0)),)
            for symbol in SYMBOLS
        }
        quality = {
            symbol: audit_candles([values[0].candle], expected_symbol=symbol)
            for symbol, values in points.items()
        }
        supervisor.state.replace_analysis(points, quality)
        synced = asyncio.Event()
        original_sleep = asyncio.sleep

        async def debounce(seconds):
            assert seconds == 2
            await original_sleep(0)

        async def sync(**kwargs):
            synced.set()
            supervisor._stop.set()

        monkeypatch.setattr("hixton.runtime.supervisor.asyncio.sleep", debounce)
        monkeypatch.setattr(supervisor, "_sync_and_analyze", sync)
        task = asyncio.create_task(supervisor._watchdog_loop())
        try:
            await original_sleep(0.02)
            assert not synced.is_set()
            supervisor._closed_bar_event.set()
            await asyncio.wait_for(synced.wait(), timeout=1)
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    asyncio.run(scenario())


def test_signal_readiness_is_logged_before_slow_paper_bookkeeping(tmp_path, monkeypatch):
    from dataclasses import replace
    from datetime import timedelta

    import hixton.runtime.supervisor as runtime_module

    boundary = datetime(2026, 9, 27, 19, tzinfo=UTC)
    clock = [boundary + timedelta(seconds=10)]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0]

    supervisor = RuntimeSupervisor(config_for(tmp_path))
    points = {symbol: (_point(symbol, boundary),) for symbol in SYMBOLS}
    prior = {
        symbol: (replace(values[0], candle=replace(
            values[0].candle,
            open_time_utc=values[0].candle.open_time_utc - timedelta(hours=1),
            close_time_utc=values[0].candle.close_time_utc - timedelta(hours=1),
        )),) for symbol, values in points.items()
    }
    quality = {
        symbol: audit_candles([values[0].candle], expected_symbol=symbol)
        for symbol, values in points.items()
    }
    supervisor.state.replace_analysis(prior, quality)
    monkeypatch.setattr(runtime_module, "datetime", Clock)
    monkeypatch.setattr(supervisor, "_synchronous_sync", lambda: (points, quality, {}))

    def slow_paper(*_):
        assert any(log.event_code == "CLOSED_BAR_SIGNALS_READY" for log in supervisor.state.logs())
        clock[0] = boundary + timedelta(seconds=120)
        return ()

    monkeypatch.setattr(supervisor, "_process_paper", slow_paper)
    asyncio.run(supervisor._sync_and_analyze(initial=False))
    logs = supervisor.state.logs()
    assert not any(log.event_code == "CLOSED_BAR_PROCESSING_LATE" for log in logs)
    assert any("10.0 Sekunden" in log.message for log in logs)
