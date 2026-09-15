"""Explicit offline Paper reset with a verified, non-overwriting full archive."""

from __future__ import annotations

import hashlib
import json
import socket
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from hixton.config import ProjectConfig
from hixton.domain.versions import strategy_definition

# Never enumerate and delete arbitrary tables. Unknown future Paper state blocks reset.
PAPER_TABLES = (
    "paper_execution_audit",
    "paper_events",
    "paper_positions",
    "paper_dust",
    "paper_checkpoints",
    "paper_soak_symbols",
    "paper_soak",
    "paper_audit",
    "paper_strategy_state",
    "paper_settings",
    "paper_account",
)


def fresh_start_paper(
    config: ProjectConfig,
    *,
    project_root: Path,
    archive: Path,
    confirmation: str,
) -> dict[str, object]:
    """Caller must stop the bot first; ordinary startup never calls this function.

    The UI port reservation rejects a running dashboard. BEGIN IMMEDIATE prevents
    other SQLite writers between backup and reset. The backup reads the committed
    snapshot through a separate connection, so it cannot deadlock on our own lock.
    """
    if confirmation != "NEUSTART":
        raise ValueError("fresh Paper start requires --confirmation NEUSTART")
    strategy = strategy_definition(config.strategy_key)
    if not strategy.paper_approved:
        raise ValueError("strategy is not approved for paper")
    if config.paper_starting_cash_usdc != 250 or (
        config.paper_slot_count != 3 or config.paper_target_notional_usdc != 80
    ):
        raise ValueError("fresh start requires 250 USDC and 3x80 slots")
    database = config.database_path.resolve(strict=True)
    archive = archive.resolve()
    backup_root = (project_root / "backups").resolve()
    if not archive.is_relative_to(backup_root) or archive == database:
        raise ValueError("archive must be a new file inside project backups")
    if archive.exists():
        raise ValueError("archive already exists; overwriting is forbidden")

    with closing(socket.socket()) as port_guard:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            port_guard.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            port_guard.bind((config.ui_bind, config.ui_port))
            port_guard.listen(1)
        except OSError as error:
            raise ValueError("stop the bot first; UI port is occupied") from error
        with closing(sqlite3.connect(database, timeout=5)) as connection:
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA foreign_keys=ON")
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                    if row[0].startswith("paper_")
                }
                if tables != set(PAPER_TABLES):
                    raise ValueError("unknown or incomplete Paper schema; reset refused")
                counts = {
                    table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    for table in PAPER_TABLES
                }
                archive.parent.mkdir(parents=True, exist_ok=True)
                # Reserve exclusively: never overwrite a backup even in a race.
                with archive.open("xb"):
                    pass
                with (
                    closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as reader,
                    closing(sqlite3.connect(archive)) as backup,
                ):
                    reader.backup(backup)
                    backup.execute("PRAGMA journal_mode=DELETE")
                    if backup.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                        raise ValueError("archive integrity check failed; reset refused")
                with archive.open("rb") as handle:
                    digest = hashlib.file_digest(handle, "sha256").hexdigest()
                moment = datetime.now(UTC).isoformat()
                details: dict[str, object] = {
                    "decision": "DEC-045",
                    "archive": str(archive),
                    "archive_sha256": digest,
                    "archived_row_counts": counts,
                    "strategy_key": strategy.key,
                    "strategy_version": strategy.version,
                    "starting_cash_usdc": "250.00",
                    "occurred_at_utc": moment,
                    "scope": "new simulated account; no liquidation, deposit profit or live orders",
                }
                for table in PAPER_TABLES:
                    connection.execute(f"DELETE FROM {table}")
                connection.execute(
                    "INSERT INTO paper_account VALUES "
                    "(1, '250.00', '250.00', '250.00', '250.00', ?, 0, NULL, ?, ?)",
                    (moment[:10], moment, moment),
                )
                connection.execute(
                    "INSERT INTO paper_settings VALUES (1, 3, '80.00', 0, ?)",
                    (moment,),
                )
                connection.execute(
                    "INSERT INTO paper_strategy_state VALUES (1, ?, ?, ?, '250.00')",
                    (strategy.key, strategy.version, moment),
                )
                connection.execute(
                    "INSERT INTO paper_audit VALUES (?, ?, 'OWNER_CLI', 'PAPER_FRESH_START', ?)",
                    (str(uuid4()), moment, json.dumps(details, sort_keys=True)),
                )
            return details
