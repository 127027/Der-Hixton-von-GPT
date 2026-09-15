from __future__ import annotations

import hashlib
import json
import socket
import sqlite3
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from hixton.domain.versions import V6_COIN_STRATEGY as V6
from hixton.paper.maintenance import PAPER_TABLES, fresh_start_paper
from hixton.paper.storage import PaperStore
from tests.test_ui_api import _config


def _prepared(tmp_path: Path):
    config = replace(
        _config(tmp_path), strategy_key="v6", paper_starting_cash_usdc=Decimal("250"),
        ui_port=0,
    )
    with PaperStore(config.database_path) as store:
        store.initialize(strategy_key="v2", strategy_version="old-v2")
        store.save_account(replace(store.load_account(), cash_usdc=Decimal("123"), halted=True))
    with sqlite3.connect(config.database_path) as connection:
        connection.execute("CREATE TABLE candles (data TEXT)")
        connection.execute("INSERT INTO candles VALUES ('preserve market data')")
        connection.execute("INSERT INTO paper_dust VALUES ('ETHUSDC', '0.001')")
        connection.execute(
            "INSERT INTO paper_checkpoints VALUES ('ETHUSDC', '2026-09-06T12:00:00+00:00')"
        )
    return config, tmp_path / "backups" / "before-fresh.sqlite3"


def test_fresh_start_archives_everything_and_only_resets_paper(tmp_path: Path) -> None:
    config, archive = _prepared(tmp_path)
    result = fresh_start_paper(
        config, project_root=tmp_path, archive=archive, confirmation="NEUSTART",
    )
    with archive.open("rb") as handle:
        assert result["archive_sha256"] == hashlib.file_digest(handle, "sha256").hexdigest()
    with sqlite3.connect(archive) as backup:
        assert backup.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert backup.execute("SELECT cash_text FROM paper_account").fetchone() == ("123",)
        assert backup.execute("SELECT COUNT(*) FROM paper_dust").fetchone() == (1,)
    with sqlite3.connect(config.database_path) as current:
        assert current.execute("SELECT * FROM candles").fetchone() == ("preserve market data",)
        for table in PAPER_TABLES:
            expected = int(table in {
                "paper_account", "paper_settings", "paper_strategy_state", "paper_audit",
            })
            assert current.execute(f"SELECT COUNT(*) FROM {table}").fetchone() == (expected,)
        audit = current.execute("SELECT action, details_json FROM paper_audit").fetchone()
        assert audit[0] == "PAPER_FRESH_START"
        assert json.loads(audit[1]) == result
    with PaperStore(config.database_path) as store:
        store.require_strategy(V6.key, V6.version)
        assert store.load_settings().target_notional_usdc == 80
        assert store.load_settings().slot_count == 3
        assert store.load_account().cash_usdc == 250
        assert not store.load_account().halted
        store.save_account(replace(store.load_account(), cash_usdc=Decimal("231")))
        assert not store.initialize(strategy_key=V6.key, strategy_version=V6.version)
        assert store.load_account().cash_usdc == 231  # Normal restart never resets.


@pytest.mark.parametrize("failure", ["confirmation", "existing", "outside", "schema", "port"])
def test_failed_preconditions_leave_account_untouched(tmp_path: Path, failure: str) -> None:
    config, archive = _prepared(tmp_path)
    confirmation = "NEUSTART"
    with socket.socket() as occupied:
        if failure == "confirmation":
            confirmation = "AKTIVIEREN"
        elif failure == "existing":
            archive.parent.mkdir()
            archive.write_text("existing backup", encoding="utf-8")
        elif failure == "outside":
            archive = tmp_path / "outside.sqlite3"
        elif failure == "schema":
            with sqlite3.connect(config.database_path) as connection:
                connection.execute("CREATE TABLE paper_future (data TEXT)")
        else:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen(1)
            config = replace(config, ui_port=occupied.getsockname()[1])
        with pytest.raises(ValueError):
            fresh_start_paper(
                config, project_root=tmp_path, archive=archive, confirmation=confirmation,
            )
    with PaperStore(config.database_path) as store:
        assert store.load_account().cash_usdc == 123
        assert store.load_account().halted
    if failure == "existing":
        assert archive.read_text(encoding="utf-8") == "existing backup"
    else:
        assert not archive.exists()


def test_reset_transaction_rolls_back_on_failure_and_keeps_archive(tmp_path: Path) -> None:
    config, archive = _prepared(tmp_path)
    with sqlite3.connect(config.database_path) as connection:
        connection.execute(
            "CREATE TRIGGER refuse_reset BEFORE INSERT ON paper_account BEGIN "
            "SELECT RAISE(ABORT, 'test failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="test failure"):
        fresh_start_paper(
            config, project_root=tmp_path, archive=archive, confirmation="NEUSTART",
        )
    with PaperStore(config.database_path) as store:
        assert store.load_account().cash_usdc == 123
        assert store.all_checkpoints()  # Original checkpoint also survived rollback.
    assert archive.is_file()
