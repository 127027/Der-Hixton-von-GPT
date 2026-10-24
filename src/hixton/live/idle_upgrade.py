"""Migrate only a never-used, disabled v5 Live binding to its entry-only v6 update."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

from hixton.domain.spot_autonomy import ENTRY_CAPITAL_BASIS
from hixton.domain.versions import V8_DIV32_PAPER_STRATEGY, StrategyDefinition

_EXPECTED = replace(
    V8_DIV32_PAPER_STRATEGY,
    version="HIXTON-V8-LINK8-ATR075-DOGE50-DD10-ETH8-DIV32-CLOSECAP-PAPER-6",
    reference="docs/entry-capital-parity-20261022.md",
    entry_capital_basis=ENTRY_CAPITAL_BASIS,
)
_UNUSED_TABLES = (
    "live_intents",
    "live_fills",
    "live_order_audit",
    "live_request_diagnostics",
    "live_positions",
    "live_events",
    "live_dust",
    "live_diversification_decisions",
    "live_entry_risk_decisions",
)


def upgrade_unused_live_binding(
    connection: sqlite3.Connection,
    strategy: StrategyDefinition,
    *,
    application_version: str,
    execution_source_sha256: str,
    source_is_current: bool,
    current_account_fingerprint: Callable[[], str | None] | None,
) -> bool:
    """No activation, account lookup or order; keep historical evidence untouched.

    This deliberately does not migrate previously traded/uncertain ledgers or
    arbitrary future releases. Their exposure and history require separate review.
    The caller holds an IMMEDIATE transaction across all eligibility checks/write.
    """
    if not connection.in_transaction:
        raise RuntimeError("Idle Live upgrade requires a write transaction")
    if not source_is_current or strategy.config_payload() != _EXPECTED.config_payload():
        return False
    row = connection.execute("SELECT * FROM live_control WHERE singleton=1").fetchone()
    if row is None or row["state"] != "LIVE_DISABLED" or row["entries_enabled"] != 0:
        return False
    try:
        old_strategy = json.loads(row["strategy_json"])
    except (ValueError, TypeError):
        return False
    if old_strategy != V8_DIV32_PAPER_STRATEGY.config_payload():
        return False
    if current_account_fingerprint is None:
        return False
    account = current_account_fingerprint()
    if not account or row["account"] != account:
        return False
    # Empty positions alone are insufficient: unknown orders, dust, reserved
    # events or past executions must never be silently rebound to a new strategy.
    for table in _UNUSED_TABLES:
        if connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() is not None:
            return False
    baseline = connection.execute("SELECT account FROM live_account_baseline").fetchall()
    if not row["account"] or len(baseline) != 1 or baseline[0]["account"] != row["account"]:
        return False
    current_json = json.dumps(strategy.config_payload(), sort_keys=True, allow_nan=False)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS live_idle_upgrade_audit("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,at_utc TEXT NOT NULL,"
        "old_control_json TEXT NOT NULL,new_strategy_json TEXT NOT NULL,"
        "new_source_sha256 TEXT NOT NULL,new_application_version TEXT NOT NULL)"
    )
    connection.execute(
        "INSERT INTO live_idle_upgrade_audit("
        "at_utc,old_control_json,new_strategy_json,new_source_sha256,"
        "new_application_version) VALUES(?,?,?,?,?)",
        (
            datetime.now(UTC).isoformat(),
            json.dumps(dict(row), sort_keys=True),
            current_json,
            execution_source_sha256,
            application_version,
        ),
    )
    connection.execute(
        "UPDATE live_control SET strategy_json=?,application_version=?,"
        "execution_source_sha256=? WHERE singleton=1 AND state='LIVE_DISABLED' "
        "AND entries_enabled=0",
        (current_json, application_version, execution_source_sha256),
    )
    return True
