from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import timedelta

import pytest

from hixton.data.storage import CandleStore
from tests.golden_reference import deterministic_candles


def test_read_only_store_never_creates_or_modifies_data(tmp_path) -> None:
    path = tmp_path / "market.sqlite3"
    candles = deterministic_candles("BTCUSDC", 4)
    with CandleStore(path) as store:
        store.put_candles(candles)
    before = path.read_bytes()
    with CandleStore(path, read_only=True) as store:
        assert store.load_candles("BTCUSDC") == candles
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            store.put_candles([replace(candles[0], close=candles[0].close + 0.1)])
    assert path.read_bytes() == before
    missing = tmp_path / "absent" / "missing.sqlite3"
    with pytest.raises(sqlite3.OperationalError):
        CandleStore(missing, read_only=True)
    assert not missing.parent.exists()


def test_store_is_idempotent_and_keeps_revision_history(tmp_path) -> None:
    path = tmp_path / "market.sqlite3"
    candles = deterministic_candles("BTCUSDC", 4)
    with CandleStore(path) as store:
        first = store.put_candles(candles)
        second = store.put_candles(candles)
        revised_candle = replace(candles[2], close=candles[2].close + 0.25)
        revised = store.put_candles([revised_candle], revision_reason="provider_revision")
        loaded = store.load_candles("BTCUSDC")

        assert first.inserted == 4
        assert second.unchanged == 4
        assert revised.revised == 1
        assert store.revision_count() == 1
        assert loaded[2].close == revised_candle.close
        assert store.integrity_check()


def test_snapshot_hash_is_stable_and_window_sensitive(tmp_path) -> None:
    candles = deterministic_candles("ETHUSDC", 10, 1)
    with CandleStore(tmp_path / "market.sqlite3") as store:
        store.put_candles(candles)
        full_end = candles[-1].open_time_utc + timedelta(hours=1)
        full_a = store.snapshot_sha256(
            "ETHUSDC", start=candles[0].open_time_utc, end_exclusive=full_end
        )
        full_b = store.snapshot_sha256(
            "ETHUSDC", start=candles[0].open_time_utc, end_exclusive=full_end
        )
        shorter = store.snapshot_sha256(
            "ETHUSDC", start=candles[1].open_time_utc, end_exclusive=full_end
        )

    assert full_a == full_b
    assert full_a != shorter


def test_closed_only_excludes_provisional_candle(tmp_path) -> None:
    candles = deterministic_candles("BNBUSDC", 2, 2)
    provisional = replace(candles[1], closed=False)
    with CandleStore(tmp_path / "market.sqlite3") as store:
        store.put_candles([candles[0], provisional])
        assert len(store.load_candles("BNBUSDC")) == 1
        assert len(store.load_candles("BNBUSDC", closed_only=False)) == 2
