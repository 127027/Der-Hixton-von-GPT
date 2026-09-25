"""Key-free deterministic roles for the GitHub-hosted Hixton swarm.

These roles inspect and test the key-free engineering system. They never read
Binance credentials and never submit real or testnet orders. Live execution is
verified only through source inspection, fake exchanges and offline regressions.
"""

# ruff: noqa: RUF001

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from hixton.domain.capital import DEFAULT_MAX_CAPITAL_USDC, capital_plan
from scripts.swarm_core import (
    AGENT_IDS,
    load_json,
    load_mission,
    required_evidence_by_agent,
    validate_cloud_ready,
)

ROOT = Path(__file__).resolve().parents[1]
MARKET_DATA_URL = "https://data-api.binance.vision"
STATE_DB = ROOT / "runtime_state" / "hixton-usdc.sqlite3"
STATE_MANIFEST = ROOT / "runtime_state" / "manifest.json"


class CheckFailure(RuntimeError):
    """Raised when one deterministic role cannot satisfy its duty."""


def run(command: list[str], *, timeout: int = 900) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    output = (completed.stdout + "\n" + completed.stderr).strip()
    return {
        "command": " ".join(command),
        "returncode": completed.returncode,
        "output_tail": output[-6000:],
    }


def require_command(command: list[str], *, timeout: int = 900) -> dict[str, Any]:
    result = run(command, timeout=timeout)
    if result["returncode"] != 0:
        message = f"command failed: {result['command']}\n{result['output_tail']}"
        raise CheckFailure(message)
    return result


def existing_tests(*patterns: str) -> list[str]:
    paths: set[Path] = set()
    for pattern in patterns:
        paths.update((ROOT / "tests").glob(pattern))
    return [str(path.relative_to(ROOT)) for path in sorted(paths)]


def coverage(*tags: str) -> dict[str, Any]:
    return {"coverage_tags": list(tags)}


def report_coverage(report: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    evidence = report.get("evidence")
    if not isinstance(evidence, list):
        return result
    for item in evidence:
        if not isinstance(item, dict):
            continue
        tags = item.get("coverage_tags")
        if isinstance(tags, list):
            result.update(str(tag) for tag in tags)
    return result


def evidence_flag(report: dict[str, Any], key: str) -> Any:
    evidence = report.get("evidence")
    if not isinstance(evidence, list):
        return None
    for item in evidence:
        if isinstance(item, dict) and key in item:
            return item[key]
    return None


def paper_runtime_contract() -> dict[str, Any]:
    board = load_json(ROOT / "agent_memory" / "swarm" / "taskboard.json")
    runtime = board.get("agent_runtime")
    if not isinstance(runtime, dict):
        raise CheckFailure("taskboard.agent_runtime missing")
    expected = {
        "agent_execution_mode": "deterministic_key_free",
        "openai_api_key_required": False,
        "trading_mode": "paper_only",
        "market_data_source": "binance_public_live_usdc",
        "paper_account_persistence_required": True,
        "continuous_operation_target": "24x7",
        "real_money_orders_allowed": False,
        "testnet_orders_allowed": False,
        "binance_private_credentials_allowed": False,
        "automatic_merge_allowed": False,
    }
    wrong = {
        key: (runtime.get(key), value)
        for key, value in expected.items()
        if runtime.get(key) != value
    }
    if wrong:
        raise CheckFailure(f"Paper-only taskboard invariant mismatch: {wrong}")
    return expected


def check_state_db() -> dict[str, Any]:
    if not STATE_DB.is_file():
        raise CheckFailure(f"persistent Paper database not restored: {STATE_DB}")
    with sqlite3.connect(STATE_DB) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise CheckFailure(f"Paper SQLite integrity failed: {integrity}")
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        required = {
            "paper_account",
            "paper_settings",
            "paper_checkpoints",
            "paper_positions",
            "paper_events",
            "paper_strategy_state",
        }
        missing = sorted(required - tables)
        if missing:
            raise CheckFailure(f"Paper tables missing: {missing}")
        account = connection.execute(
            "SELECT cash_text, starting_cash_text, high_water_text, halted, "
            "halt_reason FROM paper_account WHERE singleton=1"
        ).fetchone()
        settings = connection.execute(
            "SELECT max_capital_text, slot_count, target_notional_text, emergency_stop "
            "FROM paper_settings WHERE singleton=1"
        ).fetchone()
        checkpoint_count = connection.execute(
            "SELECT COUNT(*) FROM paper_checkpoints"
        ).fetchone()[0]
        latest_checkpoint = connection.execute(
            "SELECT MAX(last_close_utc) FROM paper_checkpoints"
        ).fetchone()[0]
    if account is None or settings is None:
        raise CheckFailure("Paper account/settings are not initialized")
    plan = capital_plan(DEFAULT_MAX_CAPITAL_USDC)
    if (
        str(settings[0]) != str(plan.max_capital_usdc)
        or int(settings[1]) != plan.slot_count
        or str(settings[2]) != str(plan.target_notional_usdc)
    ):
        raise CheckFailure(f"Paper sizing drifted from canonical max-budget plan: {settings}")
    if int(settings[3]) != 0:
        raise CheckFailure("Paper emergency stop is active")
    if int(checkpoint_count) != 10:
        raise CheckFailure(f"expected 10 Paper checkpoints, got {checkpoint_count}")
    return {
        "cash_usdc": str(account[0]),
        "starting_cash_usdc": str(account[1]),
        "high_water_usdc": str(account[2]),
        "halted": bool(account[3]),
        "halt_reason": account[4],
        "max_capital_usdc": str(settings[0]),
        "slot_count": int(settings[1]),
        "target_notional_usdc": str(settings[2]),
        "allocator_version": plan.version,
        "checkpoint_count": int(checkpoint_count),
        "latest_checkpoint_utc": latest_checkpoint,
    }



LIVE_AUDIT_CASE = "LIVE_READINESS_AUDIT"


def live_audit_enabled() -> bool:
    mission = load_mission(ROOT)
    cases = mission.get("regression_cases") or []
    return LIVE_AUDIT_CASE in cases


OPTIMIZATION_AUDIT_CASE = "COIN_IMPROVEMENT_AUDIT"


def optimization_audit_enabled() -> bool:
    mission = load_mission(ROOT)
    cases = mission.get("regression_cases") or []
    return OPTIMIZATION_AUDIT_CASE in cases


CAPITAL_100_AUDIT_CASE = "CAPITAL_100_AUDIT"


def capital100_audit_enabled() -> bool:
    mission = load_mission(ROOT)
    cases = mission.get("regression_cases") or []
    return CAPITAL_100_AUDIT_CASE in cases


CAPITAL_BUDGET_AUDIT_CASE = "CAPITAL_BUDGET_AUDIT"


def capital_budget_audit_enabled() -> bool:
    mission = load_mission(ROOT)
    cases = mission.get("regression_cases") or []
    return CAPITAL_BUDGET_AUDIT_CASE in cases


def _current_strategy_activity() -> dict[str, Any]:
    state = check_state_db()
    with sqlite3.connect(STATE_DB) as connection:
        connection.row_factory = sqlite3.Row
        strategy = connection.execute(
            "SELECT strategy_key, strategy_version, activated_at_utc, starting_equity_text "
            "FROM paper_strategy_state WHERE singleton=1"
        ).fetchone()
        if strategy is None:
            raise CheckFailure("Paper strategy state missing")
        activated_at = str(strategy["activated_at_utc"])
        open_positions = int(
            connection.execute("SELECT COUNT(*) FROM paper_positions").fetchone()[0]
        )
        filled_entries = int(
            connection.execute(
                "SELECT COUNT(*) FROM paper_events "
                "WHERE occurred_at_utc>=? AND action='ENTER_LONG' AND status='FILLED'",
                (activated_at,),
            ).fetchone()[0]
        )
        blocked_entries = int(
            connection.execute(
                "SELECT COUNT(*) FROM paper_events "
                "WHERE occurred_at_utc>=? AND action='ENTER_LONG' AND status='BLOCKED'",
                (activated_at,),
            ).fetchone()[0]
        )
        recent = [
            dict(row)
            for row in connection.execute(
                "SELECT occurred_at_utc,symbol,action,status,reason,strategy_version "
                "FROM paper_events WHERE occurred_at_utc>=? ORDER BY occurred_at_utc DESC LIMIT 20",
                (activated_at,),
            ).fetchall()
        ]
        checkpoints = [
            row[0]
            for row in connection.execute(
                "SELECT last_close_utc FROM paper_checkpoints ORDER BY symbol"
            ).fetchall()
        ]
    activated = datetime.fromisoformat(activated_at).astimezone(UTC)
    return {
        "paper_state": state,
        "strategy_key": str(strategy["strategy_key"]),
        "strategy_version": str(strategy["strategy_version"]),
        "activated_at_utc": activated.isoformat(),
        "strategy_age_hours": max(
            0.0, (datetime.now(UTC) - activated).total_seconds() / 3600
        ),
        "starting_equity_at_activation_usdc": str(strategy["starting_equity_text"]),
        "open_positions": open_positions,
        "filled_entries_since_activation": filled_entries,
        "blocked_entries_since_activation": blocked_entries,
        "recent_events_since_activation": recent,
        "all_ten_checkpoints_present": len(checkpoints) == 10,
        "latest_checkpoint_utc": max(checkpoints) if checkpoints else None,
    }


def _live_audit_a01() -> list[dict[str, Any]]:
    dms_files = sorted((ROOT / "DMS").glob("*.md"))
    required = {
        "02_VERBINDLICHE_ANFORDERUNGEN.md": (
            "Maximalbudget",
            "2 × 50 %",
            "1×50 USDC",
        ),
        "07_AUSFUEHRUNG_ORDERS.md": (
            "1 × 50 USDC",
            "Maximalbudget",
            "nicht blind erneut gesendet",
        ),
        "08_UI_UX_SPEZIFIKATION.md": (
            "Maximaler USDC-Einsatz",
            "CAPITAL-V1-2X50PCT",
        ),
        "20_BETRIEBSRUNBOOK.md": (
            "1 × 50 USDC",
            "Maximalbudget",
        ),
    }
    missing: dict[str, list[str]] = {}
    for name, snippets in required.items():
        path = ROOT / "DMS" / name
        if not path.is_file():
            missing[name] = ["FILE_MISSING"]
            continue
        text = path.read_text(encoding="utf-8")
        absent = [snippet for snippet in snippets if snippet not in text]
        if absent:
            missing[name] = absent
    if missing:
        raise CheckFailure(f"Live-readiness DMS contract mismatch: {missing}")
    return [
        {
            "live_documentation_audit": {
                "dms_files_scanned": len(dms_files),
                "portfolio_contract": (
                    "saved max_capital_usdc / CAPITAL-V1-2X50PCT / ranked_repeat"
                ),
                "default_plan": "250 USDC -> 2 x 125 USDC",
                "diagnostic_only": "10x250",
                "documented_release_state": "STAGED_LOCAL_LIVE_CLOUD_KEY_FREE",
            }
        },
        coverage("live_documentation_contract", "live_release_scope"),
    ]


def _live_audit_a02() -> list[dict[str, Any]]:
    command = require_command(
        [sys.executable, "scripts/dashboard_backtest_e2e.py"],
        timeout=2100,
    )
    output = ROOT / "evidence" / "dashboard-backtest-e2e.json"
    if not output.is_file():
        raise CheckFailure("fresh dashboard E2E evidence missing")
    payload = json.loads(output.read_text(encoding="utf-8"))
    portfolio = payload.get("portfolio_max_budget", {})
    summary = portfolio.get("summary", {})
    timing = portfolio.get("trade_timing", {})
    plan = capital_plan(DEFAULT_MAX_CAPITAL_USDC)
    if (
        payload.get("credentials_used") is not False
        or payload.get("orders_sent") is not False
        or summary.get("slot_count") != plan.slot_count
        or str(summary.get("target_notional")) != str(plan.target_notional_usdc)
        or summary.get("slot_allocation") != plan.allocation_policy
        or int(summary.get("completed_trades", 0)) <= 0
        or int(timing.get("max_slot_occupancy", 99)) > plan.slot_count
    ):
        raise CheckFailure("fresh max-budget E2E violates allocator invariants")
    return [
        command,
        {
            "backtest_execution_realism": {
                "strategy": payload.get("strategy"),
                "report_start_utc": portfolio.get("report_start_utc"),
                "report_end_utc": portfolio.get("report_end_utc"),
                "max_capital_usdc": str(plan.max_capital_usdc),
                "slot_count": plan.slot_count,
                "target_notional_usdc": str(plan.target_notional_usdc),
                "allocator_version": plan.version,
                "ending_equity_usdc": summary.get("ending_equity"),
                "return_pct": summary.get("return_pct"),
                "position_cycles": summary.get("completed_trades"),
                "slot_trades": summary.get("completed_slot_trades"),
                "max_drawdown_pct": summary.get("max_drawdown_pct"),
                "blocked_reasons": summary.get("blocked_reasons"),
                "trade_timing": timing,
                "per_symbol_trades": portfolio.get("per_symbol_trades"),
                "history_mode": portfolio.get("history_mode"),
                "runtime_quote": portfolio.get("runtime_quote"),
                "market_proxy_quote": portfolio.get("market_proxy_quote"),
                "historical_execution_claim": "SIMULATION_NOT_ACTUAL_BINANCE_FILL_PROOF",
            }
        },
        coverage("backtest_execution_realism", "trade_frequency_analysis"),
    ]


def _live_audit_a03() -> list[dict[str, Any]]:
    activity = _current_strategy_activity()
    tests = require_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_owner_slot_capacity_semantics.py",
            "tests/test_paper_slot_parity.py",
            "tests/test_runtime_parity.py",
        ],
        timeout=1200,
    )
    plan = capital_plan(DEFAULT_MAX_CAPITAL_USDC)
    if activity["open_positions"] > plan.slot_count:
        raise CheckFailure("Paper state exceeds allocator slot capacity")
    return [
        tests,
        {"paper_live_activity": activity, "allocator_version": plan.version},
        coverage("paper_live_signal_parity", "slot_reuse_contract"),
    ]


def _live_audit_a04() -> list[dict[str, Any]]:
    preparation = (ROOT / "src" / "hixton" / "live" / "preparation.py").read_text(
        encoding="utf-8"
    )
    routes = (ROOT / "src" / "hixton" / "ui" / "live.py").read_text(encoding="utf-8")
    ui = (ROOT / "ui" / "src" / "live-preparation.ts").read_text(encoding="utf-8")
    settings_ui = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    required = (
        '"trial_dispatch_available": trial_available',
        '"order_dispatch_available": production_ready',
        '"minimum_free_usdc_at_enable"',
        'confirmation:"TEST 50 USDC"',
        'confirmation:"LIVE MAXIMALBUDGET AKTIVIEREN"',
        'id="capital-input"',
        "Maximaler USDC-Einsatz",
    )
    combined = "\n".join((preparation, routes, ui, settings_ui))
    missing = [value for value in required if value not in combined]
    if missing:
        raise CheckFailure(f"staged max-budget Live surface incomplete: {missing}")
    tests = require_command(
        [sys.executable, "-m", "pytest", "-q", "tests/test_live_preparation.py"],
        timeout=1200,
    )
    return [
        tests,
        {
            "controlled_trial_code_ready": True,
            "production_live_code_ready": True,
            "actual_live_activation_approved": False,
            "cloud_order_submission": False,
            "current_live_surface": "EXPLICIT_1X50_THEN_RUNTIME_GATED_MAX_BUDGET",
        },
        coverage("live_ui_fail_closed", "live_capital_semantics"),
    ]


def _live_audit_a05() -> list[dict[str, Any]]:
    activity = _current_strategy_activity()
    state = activity["paper_state"]
    plan = capital_plan(DEFAULT_MAX_CAPITAL_USDC)
    technical_blockers: list[str] = []
    if bool(state.get("halted")):
        technical_blockers.append("PAPER_HALTED")
    if not bool(activity.get("all_ten_checkpoints_present")):
        technical_blockers.append("MISSING_CHECKPOINTS")
    if int(activity.get("open_positions", 0)) > plan.slot_count:
        technical_blockers.append("TOO_MANY_OPEN_POSITIONS")
    diagnosis = (
        "NO_FILLED_ENTRY_SINCE_CURRENT_STRATEGY_ACTIVATION"
        if int(activity["filled_entries_since_activation"]) == 0
        else "FILLED_ENTRY_OBSERVED_SINCE_CURRENT_STRATEGY_ACTIVATION"
    )
    return [
        {
            "current_no_trade_diagnosis": diagnosis,
            "technical_blockers_observed": technical_blockers,
            "activity": activity,
            "allocator_version": plan.version,
        },
        coverage("current_no_trade_diagnosis", "live_runtime_blockers"),
    ]


def _live_audit_a06() -> list[dict[str, Any]]:
    sources = {
        "orders": (ROOT / "tests" / "test_live_orders.py").read_text(encoding="utf-8"),
        "trial": (ROOT / "tests" / "test_live_trial.py").read_text(encoding="utf-8"),
        "production": (ROOT / "tests" / "test_live_production.py").read_text(encoding="utf-8"),
        "preparation": (ROOT / "tests" / "test_live_preparation.py").read_text(
            encoding="utf-8"
        ),
    }
    required_tests = {
        "orders": ("test_concurrent_submit_claim_has_one_winner",),
        "trial": (
            "test_reserved_entry_restart_and_timeout_cannot_rebuy",
            "test_global_trial_budget_rejects_every_other_amount",
        ),
        "production": (
            "test_live_intent_accepts_only_two_budget_slots_and_explicit_quote",
            "test_ten_simultaneous_signals_never_exceed_two_slots",
            "test_timeout_restart_reconciles_without_duplicate_submit",
            "test_settings_change_or_emergency_stop_blocks_new_live_entry",
            "test_repeated_scheduler_ticks_do_not_duplicate_orders",
            "test_account_mismatch_fails_closed_before_order",
        ),
        "preparation": (
            "test_controlled_trial_arms_only_after_fresh_account_check_without_sending_order",
            "test_common_max_budget_is_immediately_the_live_source_and_survives_restart",
            "test_validated_max_budgets_persist_without_inventing_cash",
        ),
    }
    missing = {
        group: [name for name in names if name not in sources[group]]
        for group, names in required_tests.items()
    }
    missing = {group: names for group, names in missing.items() if names}
    if missing:
        raise CheckFailure(f"runaway-order failure matrix incomplete: {missing}")
    tests = require_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_live_orders.py",
            "tests/test_live_exchange.py",
            "tests/test_live_preparation.py",
            "tests/test_live_reconciliation_runtime.py",
            "tests/test_live_trial.py",
            "tests/test_live_production.py",
        ],
        timeout=1800,
    )
    return [
        tests,
        {
            "runaway_order_guard": "PERSIST_BEFORE_SUBMIT_QUERY_DONT_RESUBMIT",
            "production_max_budget_live_implemented": True,
            "controlled_trial_code_ready": True,
            "production_live_code_ready": True,
            "actual_live_activation_approved": False,
            "cloud_order_submission": False,
            "covered_failure_classes": [
                "concurrent_submit",
                "duplicate_delivery",
                "timeout_query_without_resubmit",
                "restart_reserved_entry",
                "ten_simultaneous_signals",
                "budget_change_while_live",
                "invalid_or_huge_notional",
                "account_reconciliation_mismatch",
                "repeated_scheduler_ticks",
            ],
        },
        coverage("live_failure_regression", "runaway_order_guard"),
    ]


def _live_audit_a07() -> list[dict[str, Any]]:
    exchange = _json_url("/api/v3/exchangeInfo")
    symbols = {str(item.get("symbol")): item for item in exchange.get("symbols", [])}
    from hixton.constants import SYMBOLS

    result: dict[str, dict[str, Any]] = {}
    for symbol in SYMBOLS:
        item = symbols.get(symbol)
        if not isinstance(item, dict):
            raise CheckFailure(f"{symbol}: exchangeInfo missing")
        filters = {
            str(value.get("filterType")): value
            for value in item.get("filters", [])
            if isinstance(value, dict)
        }
        lot = filters.get("LOT_SIZE", {})
        market_lot = filters.get("MARKET_LOT_SIZE", {})
        price = filters.get("PRICE_FILTER", {})
        notional = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL") or {}
        entry = {
            "status": item.get("status"),
            "quote_asset": item.get("quoteAsset"),
            "spot_allowed": item.get("isSpotTradingAllowed"),
            "order_types": item.get("orderTypes"),
            "tick_size": price.get("tickSize"),
            "step_size": lot.get("stepSize"),
            "market_step_size": market_lot.get("stepSize"),
            "min_qty": lot.get("minQty"),
            "market_min_qty": market_lot.get("minQty"),
            "min_notional": notional.get("minNotional"),
        }
        if (
            entry["status"] != "TRADING"
            or entry["quote_asset"] != "USDC"
            or entry["spot_allowed"] is not True
            or "MARKET" not in (entry["order_types"] or [])
            or not entry["step_size"]
            or not entry["market_step_size"]
            or not entry["min_qty"]
            or not entry["market_min_qty"]
            or not entry["min_notional"]
        ):
            raise CheckFailure(f"{symbol}: incomplete current Spot execution constraints {entry}")
        result[symbol] = entry
    tests = require_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_live_exchange.py",
            "tests/test_binance_adapter.py",
        ],
        timeout=1200,
    )
    return [
        tests,
        {"current_binance_spot_constraints": result},
        coverage("live_exchange_filters", "live_binance_constraints"),
    ]


def _live_audit_a08() -> list[dict[str, Any]]:
    tests = require_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_risk.py",
            "tests/test_strategy_slot_capacity.py",
            "tests/test_trade_policy.py",
            "tests/test_owner_slot_capacity_semantics.py",
            "tests/test_live_production.py",
        ],
        timeout=1200,
    )
    plan = capital_plan(DEFAULT_MAX_CAPITAL_USDC)
    return [
        tests,
        {
            "live_strategy_risk": {
                "default_max_capital_usdc": str(plan.max_capital_usdc),
                "default_slot_count": plan.slot_count,
                "default_target_notional_usdc": str(plan.target_notional_usdc),
                "allocator_version": plan.version,
                "research_10x250_is_live_capital": False,
                "production_submission_implemented": True,
                "actual_live_activation_approved": False,
                "cloud_order_submission": False,
            }
        },
        coverage("live_strategy_risk_limits", "live_slot_competition"),
    ]


def _live_audit_a10(reports_dir: Path | None) -> list[dict[str, Any]]:
    if reports_dir is None:
        raise CheckFailure("live A10 audit requires reports")
    reports = load_reports(reports_dir)
    a04 = reports.get("A04", {})
    a06 = reports.get("A06", {})
    if (
        evidence_flag(a04, "controlled_trial_code_ready") is not True
        or evidence_flag(a04, "production_live_code_ready") is not True
        or evidence_flag(a06, "production_max_budget_live_implemented") is not True
        or evidence_flag(a06, "actual_live_activation_approved") is not False
        or evidence_flag(a06, "cloud_order_submission") is not False
    ):
        raise CheckFailure("staged Live evidence is incomplete or overclaims activation")
    return [
        {
            "controlled_trial_code_ready": True,
            "production_live_code_ready": True,
            "actual_live_activation_approved": False,
            "audit_result": "CONTROLLED_TRIAL_CODE_READY",
            "reason": (
                "Offline safety gates pass. A real local 1x50 round-trip is still required "
                "before continuous max-budget Live can become operationally eligible."
            ),
        },
        coverage("live_audit_evidence_contract"),
    ]


def _live_audit_a09(reports_dir: Path | None) -> list[dict[str, Any]]:
    if reports_dir is None:
        raise CheckFailure("live A09 audit requires reports")
    reports = load_reports(reports_dir)
    a10 = reports.get("A10", {})
    if (
        evidence_flag(a10, "controlled_trial_code_ready") is not True
        or evidence_flag(a10, "production_live_code_ready") is not True
        or evidence_flag(a10, "actual_live_activation_approved") is not False
        or evidence_flag(a10, "audit_result") != "CONTROLLED_TRIAL_CODE_READY"
    ):
        raise CheckFailure("QA refuses incomplete or overclaimed Live readiness")
    return [
        {
            "controlled_trial_code_ready": True,
            "production_live_code_ready": True,
            "actual_live_activation_approved": False,
            "qa_live_decision": "AUDIT_PASS_CONTROLLED_TRIAL_CODE_READY",
        },
        coverage("live_audit_qa"),
    ]


def _live_audit_a11(reports_dir: Path | None) -> list[dict[str, Any]]:
    if reports_dir is None:
        raise CheckFailure("live A11 audit requires reports")
    reports = load_reports(reports_dir)
    a09 = reports.get("A09", {})
    a10 = reports.get("A10", {})
    if (
        evidence_flag(a09, "controlled_trial_code_ready") is not True
        or evidence_flag(a09, "production_live_code_ready") is not True
        or evidence_flag(a09, "actual_live_activation_approved") is not False
        or evidence_flag(a10, "actual_live_activation_approved") is not False
    ):
        raise CheckFailure("governance refuses implicit operational Live approval")
    return [
        {
            "controlled_trial_code_ready": True,
            "production_live_code_ready": True,
            "actual_live_activation_approved": False,
            "governance_live_decision": "CONTROLLED_TRIAL_CODE_READY",
        },
        coverage("live_audit_governance"),
    ]


def live_audit_evidence(role: str, reports_dir: Path | None) -> list[dict[str, Any]]:
    handlers = {
        "A01": lambda: _live_audit_a01(),
        "A02": lambda: _live_audit_a02(),
        "A03": lambda: _live_audit_a03(),
        "A04": lambda: _live_audit_a04(),
        "A05": lambda: _live_audit_a05(),
        "A06": lambda: _live_audit_a06(),
        "A07": lambda: _live_audit_a07(),
        "A08": lambda: _live_audit_a08(),
        "A09": lambda: _live_audit_a09(reports_dir),
        "A10": lambda: _live_audit_a10(reports_dir),
        "A11": lambda: _live_audit_a11(reports_dir),
    }
    return handlers[role]()



def _optimization_audit_a01() -> list[dict[str, Any]]:
    source = (ROOT / "scripts" / "coin_optimization_cycle.py").read_text(encoding="utf-8")
    required = (
        "training stress only freezes the ordered Top-8 challengers per coin",
        "every robust finalist is tested alone in shared 3x80",
        '"activation_performed": False',
        "3x80 portfolio is used only later as a compatibility check",
    )
    missing = [item for item in required if item not in source]
    if missing:
        raise CheckFailure(f"optimization methodology contract incomplete: {missing}")
    return [
        {
            "optimization_suggestions": [
                "Keep parameter discovery isolated in 10x250; never rank candidates "
                "by 3x80 outcome.",
                "Preserve training-only Top-K freeze and use validation/full windows "
                "only to reject.",
                "Prefer bounded local two-parameter interactions over a broad unconstrained grid.",
            ]
        },
        coverage("optimization_methodology", "optimization_scope"),
    ]


def _optimization_audit_a02() -> list[dict[str, Any]]:
    output = ROOT / "evidence" / "coin-optimization-cycle.json"
    if output.exists():
        output.unlink()
    run_result = require_command(
        [sys.executable, "scripts/coin_optimization_cycle.py"],
        timeout=3600,
    )
    if not output.is_file():
        raise CheckFailure("fresh optimization evidence was not produced")
    evidence = json.loads(output.read_text(encoding="utf-8"))
    parity = evidence.get("profile_parity", {})
    if parity.get("current_match") is not True or parity.get("candidate_match") is not True:
        raise CheckFailure("10x250/3x80 profile parity failed")
    per_coin_raw = evidence.get("per_coin", {})
    per_coin: dict[str, object] = {}
    suggestions: dict[str, str] = {}
    for symbol, raw in per_coin_raw.items():
        robust = list(raw.get("robust_finalists", []))
        accepted = bool(raw.get("accepted"))
        current = raw.get("full_current_baseline", {})
        marginal = raw.get("marginal_3x80", {})
        per_coin[symbol] = {
            "current_ending_equity": current.get("ending_equity"),
            "current_max_drawdown_pct": current.get("max_drawdown_pct"),
            "completed_trades": current.get("completed_trades"),
            "training_top_k_challengers": raw.get("training_top_k_challengers", []),
            "robust_finalists": robust,
            "accepted": accepted,
            "accepted_candidate_name": raw.get("accepted_candidate_name", "current"),
            "portfolio_selected": marginal.get("selected_for_combination", "current"),
            "loss_cluster_analysis": raw.get("loss_cluster_analysis", {}),
        }
        if accepted:
            suggestions[symbol] = (
                "Research assembly improved both canonical models; candidate is eligible only "
                "for a separate audited canonical-profile promotion."
            )
        elif robust:
            suggestions[symbol] = (
                "At least one isolated robust improvement exists but loses in shared 3x80. "
                "Search a nearby isolated timing/band compromise that retains the coin gain "
                "with lower slot opportunity cost; do not tune directly on 3x80."
            )
        else:
            suggestions[symbol] = (
                "No robust holdout finalist yet. Continue bounded isolated local interactions "
                "around the training Top-K and the measured loss regimes."
            )
    aggregate = evidence.get("aggregate_promotion_gate", {})
    result = {
        "report_start_utc": evidence.get("report_start_utc"),
        "report_end_utc": evidence.get("report_end_utc"),
        "profile_parity": parity,
        "per_coin": per_coin,
        "aggregate_promotion_gate": aggregate,
        "isolated_10x250": evidence.get("isolated_10x250"),
        "portfolio_3x80": evidence.get("portfolio_3x80"),
        "suggestions_by_symbol": suggestions,
        "automatic_activation_performed": evidence.get("activation_performed"),
    }
    return [
        run_result,
        {"optimization_result": result},
        {"optimization_suggestions": list(suggestions.values())},
        coverage("optimization_fresh_run", "per_coin_improvement_evidence"),
    ]


def _optimization_audit_a03() -> list[dict[str, Any]]:
    source = (ROOT / "scripts" / "coin_optimization_cycle.py").read_text(encoding="utf-8")
    if "_runner_profile_hashes" not in source:
        raise CheckFailure("independent runner profile fingerprinting missing")
    if '"current_match": current_hashes == current_hashes' in source:
        raise CheckFailure("tautological current profile parity check remains")
    tests = require_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_coin_engine_parity.py",
            "tests/test_backtest_coin_optimization.py",
        ],
        timeout=1200,
    )
    return [
        tests,
        {
            "optimization_suggestions": [
                "Treat any per-symbol fingerprint mismatch between isolated and portfolio runners "
                "as a hard failure before comparing performance."
            ],
            "same_bot_contract": "INDEPENDENT_RUNNER_PROFILE_HASHES_REQUIRED",
        },
        coverage("optimization_profile_parity", "single_bot_contract"),
    ]


def _optimization_audit_a04() -> list[dict[str, Any]]:
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    if "10×250 isoliert (Forschung)" not in html:
        raise CheckFailure("10x250 research model is not explicitly labelled Forschung")
    return [
        {
            "optimization_suggestions": [
                "Keep candidate tables internal; the normal UI should continue to show only the "
                "single promoted canonical V6 profile per coin."
            ]
        },
        coverage("optimization_product_semantics"),
    ]


def _optimization_audit_a05() -> list[dict[str, Any]]:
    source = (ROOT / "scripts" / "coin_optimization_cycle.py").read_text(encoding="utf-8")
    loss_cluster_line = (
        'per_coin[symbol]["loss_cluster_analysis"] = _loss_signal_clusters(full_current)'
    )
    if loss_cluster_line not in source:
        raise CheckFailure("loss-cluster analysis is not produced for all ten coins")
    return [
        {
            "optimization_suggestions": [
                "Use each coin's loss clusters to propose the next bounded isolated neighborhood: "
                "holding-time, ATR regime and breakout-strength patterns before adding new filters."
            ]
        },
        coverage("optimization_loss_clusters"),
    ]


def _optimization_audit_a06() -> list[dict[str, Any]]:
    tests = require_command(
        [sys.executable, "-m", "pytest", "-q", "tests/test_backtest_coin_optimization.py"],
        timeout=1200,
    )
    return [
        tests,
        {
            "optimization_suggestions": [
                "Do not relax the independent validation gate to rescue attractive full-window "
                "candidates; if the expanded local search still fails, add a future rolling "
                "walk-forward research layer rather than reusing the holdout for selection."
            ]
        },
        coverage("optimization_overfit_regression", "optimization_search_bounds"),
    ]


def _optimization_audit_a07() -> list[dict[str, Any]]:
    rules = _json_url("/api/v3/exchangeInfo")
    symbols = {str(item.get("symbol")): item for item in rules.get("symbols", [])}
    from hixton.constants import SYMBOLS

    missing = [symbol for symbol in SYMBOLS if symbol not in symbols]
    if missing:
        raise CheckFailure(f"optimization universe missing current Binance symbols: {missing}")
    return [
        {
            "optimization_suggestions": [
                "Retain current public Binance execution filters in every candidate replay; "
                "do not accept a theoretical parameter gain that depends on invalid order sizes."
            ]
        },
        coverage("optimization_binance_execution_rules"),
    ]


def _optimization_audit_a08() -> list[dict[str, Any]]:
    source = (ROOT / "scripts" / "coin_optimization_cycle.py").read_text(encoding="utf-8")
    required = (
        "portfolio_compatible =",
        "baseline_delta >= D(\"0\")",
        "stress_delta >= D(\"0\")",
        "combination_baseline_delta_usdc",
        "combination_stress_delta_usdc",
    )
    missing = [item for item in required if item not in source]
    if missing:
        raise CheckFailure(f"3x80 follow-up gate incomplete: {missing}")
    return [
        {
            "optimization_suggestions": [
                "Use 3x80 only as a post-search opportunity-cost gate. A coin improvement that "
                "steals slots from stronger signals must remain research-only even when its "
                "isolated 250-USDC account improves."
            ]
        },
        coverage("optimization_portfolio_followup", "optimization_slot_effect"),
    ]


def _optimization_audit_a10(reports_dir: Path | None) -> list[dict[str, Any]]:
    if reports_dir is None:
        raise CheckFailure("optimization A10 requires reports")
    reports = load_reports(reports_dir)
    a02 = evidence_flag(reports.get("A02", {}), "optimization_result")
    if not isinstance(a02, dict):
        raise CheckFailure("A02 fresh optimization result missing")
    all_suggestions: list[object] = []
    for agent in [f"A{i:02d}" for i in range(1, 9)]:
        value = evidence_flag(reports.get(agent, {}), "optimization_suggestions")
        if isinstance(value, list):
            all_suggestions.extend(value)
    return [
        {
            "optimization_synthesis": {
                "fresh_result": a02,
                "specialist_suggestions": all_suggestions,
                "promotion_policy": (
                    "No automatic promotion. If aggregate_promotion_gate.promotable is true, "
                    "a separate canonical-profile change plus fresh full A01-A11 is required."
                ),
            }
        },
        coverage("optimization_synthesis"),
    ]


def _optimization_audit_a09(reports_dir: Path | None) -> list[dict[str, Any]]:
    if reports_dir is None:
        raise CheckFailure("optimization A09 requires reports")
    reports = load_reports(reports_dir)
    synthesis = evidence_flag(reports.get("A10", {}), "optimization_synthesis")
    if not isinstance(synthesis, dict):
        raise CheckFailure("optimization synthesis missing")
    fresh = synthesis.get("fresh_result", {})
    parity = fresh.get("profile_parity", {}) if isinstance(fresh, dict) else {}
    if parity.get("current_match") is not True or parity.get("candidate_match") is not True:
        raise CheckFailure("QA rejects optimization without exact profile parity")
    return [
        {
            "optimization_suggestions": [
                "Only compare improvements from the fresh optimization window on this exact "
                "commit; "
                "do not mix metrics from older windows when deciding whether to promote."
            ]
        },
        coverage("optimization_qa"),
    ]


def _optimization_audit_a11(reports_dir: Path | None) -> list[dict[str, Any]]:
    if reports_dir is None:
        raise CheckFailure("optimization A11 requires reports")
    reports = load_reports(reports_dir)
    synthesis = evidence_flag(reports.get("A10", {}), "optimization_synthesis")
    if not isinstance(synthesis, dict):
        raise CheckFailure("governance optimization synthesis missing")
    fresh = synthesis.get("fresh_result", {})
    if not isinstance(fresh, dict) or fresh.get("automatic_activation_performed") is not False:
        raise CheckFailure("optimization must remain research-only until separate promotion")
    return [
        {
            "optimization_suggestions": [
                "Governance permits a later profile promotion only after the research gate is "
                "promotable, canonical versions.py is updated once, and the exact new profile map "
                "passes fresh 10x250, 3x80, Paper parity and A01-A11."
            ]
        },
        coverage("optimization_governance"),
    ]


def optimization_audit_evidence(
    role: str,
    reports_dir: Path | None,
) -> list[dict[str, Any]]:
    handlers = {
        "A01": lambda: _optimization_audit_a01(),
        "A02": lambda: _optimization_audit_a02(),
        "A03": lambda: _optimization_audit_a03(),
        "A04": lambda: _optimization_audit_a04(),
        "A05": lambda: _optimization_audit_a05(),
        "A06": lambda: _optimization_audit_a06(),
        "A07": lambda: _optimization_audit_a07(),
        "A08": lambda: _optimization_audit_a08(),
        "A09": lambda: _optimization_audit_a09(reports_dir),
        "A10": lambda: _optimization_audit_a10(reports_dir),
        "A11": lambda: _optimization_audit_a11(reports_dir),
    }
    return handlers[role]()



def _capital100_audit_a01() -> list[dict[str, Any]]:
    source = (ROOT / "scripts" / "capital_100_simulation.py").read_text(encoding="utf-8")
    required = (
        'starting_cash=D("100")',
        'target_notional=D("100")',
        'starting_cash=D("1000")',
        'slot_count=10',
        '"research_only": True',
        '"activation_performed": False',
    )
    missing = [item for item in required if item not in source]
    if missing:
        raise CheckFailure(f"100-USDC methodology incomplete: {missing}")
    return [
        {
            "capital100_assessment": [
                "Compare all layouts on exactly 1,000 USDC total starting capital.",
                "Treat isolated 10x100 and shared 10x100 as different capital mechanics, "
                "not different strategies.",
            ]
        },
        coverage("capital100_methodology", "capital100_scope"),
    ]


def _capital100_audit_a02() -> list[dict[str, Any]]:
    output = ROOT / "evidence" / "capital-100-simulation.json"
    if output.exists():
        output.unlink()
    command = require_command(
        [sys.executable, "-m", "scripts.capital_100_simulation"],
        timeout=3600,
    )
    if not output.is_file():
        raise CheckFailure("fresh 100-USDC simulation evidence missing")
    payload = json.loads(output.read_text(encoding="utf-8"))
    if payload.get("research_only") is not True or payload.get("activation_performed") is not False:
        raise CheckFailure("100-USDC simulation is not research-only")
    variants = payload.get("variants", {})
    for label in ("current", "research_candidate"):
        item = variants.get(label, {})
        if item.get("profile_match_across_models") is not True:
            raise CheckFailure(f"{label}: profile maps diverge across capital layouts")
    return [
        command,
        {"capital100_result": payload},
        coverage("capital100_fresh_simulation"),
    ]


def _capital100_audit_a03() -> list[dict[str, Any]]:
    source = (ROOT / "scripts" / "capital_100_simulation.py").read_text(encoding="utf-8")
    if "profile_match_across_models" not in source:
        raise CheckFailure("capital model profile-consistency gate missing")
    return [
        {
            "capital100_profile_contract": (
                "ONE_PROFILE_MAP_REUSED_ACROSS_ISOLATED_ONE_PER_SYMBOL_AND_RANKED_REPEAT"
            )
        },
        coverage("capital100_profile_consistency"),
    ]


def _capital100_audit_a04() -> list[dict[str, Any]]:
    source = (ROOT / "scripts" / "capital_100_simulation.py").read_text(encoding="utf-8")
    forbidden = ("versions.py", "PaperStore(", "enable_live(", "start_trial(")
    present = [item for item in forbidden if item in source]
    if present:
        raise CheckFailure(f"100-USDC research script crosses product boundary: {present}")
    return [
        {
            "capital100_product_state": "RESEARCH_ONLY_NO_CANONICAL_OR_LIVE_MUTATION",
        },
        coverage("capital100_product_separation"),
    ]


def _capital100_audit_a05() -> list[dict[str, Any]]:
    output = ROOT / "evidence" / "capital-100-simulation.json"
    if not output.is_file():
        payload = _capital100_audit_a02()[1]["capital100_result"]
    else:
        payload = json.loads(output.read_text(encoding="utf-8"))
    current = payload["variants"]["current"]["baseline"]["isolated_10x100"]
    research = payload["variants"]["research_candidate"]["baseline"]["isolated_10x100"]
    summary = {
        symbol: {
            "current_ending_equity": current["per_symbol"][symbol]["ending_equity"],
            "research_ending_equity": research["per_symbol"][symbol]["ending_equity"],
            "current_blocked_reasons": current["per_symbol"][symbol]["blocked_reasons"],
            "research_blocked_reasons": research["per_symbol"][symbol]["blocked_reasons"],
        }
        for symbol in current["per_symbol"]
    }
    return [
        {"capital100_per_coin": summary},
        coverage("capital100_per_coin_distribution"),
    ]


def _capital100_audit_a06() -> list[dict[str, Any]]:
    output = ROOT / "evidence" / "capital-100-simulation.json"
    if not output.is_file():
        payload = _capital100_audit_a02()[1]["capital100_result"]
    else:
        payload = json.loads(output.read_text(encoding="utf-8"))
    baseline_best = payload["baseline_best_by_ending_equity"]
    stress_best = payload["stress_best_by_ending_equity"]
    return [
        {
            "capital100_stress_assessment": {
                "baseline_best": baseline_best,
                "stress_best": stress_best,
                "same_leader_under_stress": baseline_best == stress_best,
                "baseline_models": payload["baseline_ending_equity_by_model"],
                "stress_models": payload["stress_ending_equity_by_model"],
            }
        },
        coverage("capital100_stress_comparison"),
    ]


def _capital100_audit_a07() -> list[dict[str, Any]]:
    exchange = _json_url("/api/v3/exchangeInfo")
    symbols = {str(item.get("symbol")): item for item in exchange.get("symbols", [])}
    from hixton.constants import SYMBOLS

    invalid = [
        symbol
        for symbol in SYMBOLS
        if symbol not in symbols
        or symbols[symbol].get("status") != "TRADING"
        or symbols[symbol].get("quoteAsset") != "USDC"
    ]
    if invalid:
        raise CheckFailure(f"100-USDC Binance universe invalid: {invalid}")
    return [
        {"capital100_binance_symbols": list(SYMBOLS)},
        coverage("capital100_binance_rules"),
    ]


def _capital100_audit_a08() -> list[dict[str, Any]]:
    output = ROOT / "evidence" / "capital-100-simulation.json"
    if not output.is_file():
        payload = _capital100_audit_a02()[1]["capital100_result"]
    else:
        payload = json.loads(output.read_text(encoding="utf-8"))
    comparison: dict[str, object] = {}
    for profile in ("current", "research_candidate"):
        baseline = payload["variants"][profile]["baseline"]
        comparison[profile] = {
            model: {
                "ending_equity": baseline[model]["ending_equity"],
                "max_drawdown_pct": baseline[model]["max_drawdown_pct"],
                "slot_trades": baseline[model].get("slot_trades"),
                "blocked_reasons": baseline[model].get("blocked_reasons", {}),
            }
            for model in (
                "isolated_10x100",
                "shared_10x100_one_per_symbol",
                "shared_10x100_ranked_repeat",
            )
        }
    return [
        {"capital100_allocation_comparison": comparison},
        coverage("capital100_allocation_comparison"),
    ]


def _capital100_audit_a10(reports_dir: Path | None) -> list[dict[str, Any]]:
    if reports_dir is None:
        raise CheckFailure("capital100 A10 requires reports")
    reports = load_reports(reports_dir)
    result = evidence_flag(reports.get("A02", {}), "capital100_result")
    stress = evidence_flag(reports.get("A06", {}), "capital100_stress_assessment")
    allocation = evidence_flag(reports.get("A08", {}), "capital100_allocation_comparison")
    if (
        not isinstance(result, dict)
        or not isinstance(stress, dict)
        or not isinstance(allocation, dict)
    ):
        raise CheckFailure("capital100 specialist evidence incomplete")
    return [
        {
            "capital100_synthesis": {
                "report_start_utc": result.get("report_start_utc"),
                "report_end_utc": result.get("report_end_utc"),
                "baseline_best": result.get("baseline_best_by_ending_equity"),
                "stress_best": result.get("stress_best_by_ending_equity"),
                "baseline_models": result.get("baseline_ending_equity_by_model"),
                "stress_models": result.get("stress_ending_equity_by_model"),
                "allocation_detail": allocation,
                "research_only": True,
                "automatic_live_change": False,
            }
        },
        coverage("capital100_synthesis"),
    ]


def _capital100_audit_a09(reports_dir: Path | None) -> list[dict[str, Any]]:
    if reports_dir is None:
        raise CheckFailure("capital100 A09 requires reports")
    reports = load_reports(reports_dir)
    synthesis = evidence_flag(reports.get("A10", {}), "capital100_synthesis")
    if not isinstance(synthesis, dict) or synthesis.get("research_only") is not True:
        raise CheckFailure("capital100 QA rejects non-research synthesis")
    return [
        {"capital100_qa_decision": "PASS_RESEARCH_COMPARISON_ONLY"},
        coverage("capital100_qa"),
    ]


def _capital100_audit_a11(reports_dir: Path | None) -> list[dict[str, Any]]:
    if reports_dir is None:
        raise CheckFailure("capital100 A11 requires reports")
    reports = load_reports(reports_dir)
    synthesis = evidence_flag(reports.get("A10", {}), "capital100_synthesis")
    if (
        not isinstance(synthesis, dict)
        or synthesis.get("research_only") is not True
        or synthesis.get("automatic_live_change") is not False
    ):
        raise CheckFailure("capital100 governance denied")
    return [
        {
            "capital100_governance": (
                "PASS_RESEARCH_ONLY_NO_AUTOMATIC_LIVE_CONFIGURATION"
            )
        },
        coverage("capital100_governance"),
    ]


def capital100_audit_evidence(
    role: str,
    reports_dir: Path | None,
) -> list[dict[str, Any]]:
    handlers = {
        "A01": lambda: _capital100_audit_a01(),
        "A02": lambda: _capital100_audit_a02(),
        "A03": lambda: _capital100_audit_a03(),
        "A04": lambda: _capital100_audit_a04(),
        "A05": lambda: _capital100_audit_a05(),
        "A06": lambda: _capital100_audit_a06(),
        "A07": lambda: _capital100_audit_a07(),
        "A08": lambda: _capital100_audit_a08(),
        "A09": lambda: _capital100_audit_a09(reports_dir),
        "A10": lambda: _capital100_audit_a10(reports_dir),
        "A11": lambda: _capital100_audit_a11(reports_dir),
    }
    return handlers[role]()



def _capital_budget_audit_a01() -> list[dict[str, Any]]:
    source = (ROOT / "scripts" / "capital_budget_optimizer.py").read_text(encoding="utf-8")
    required = (
        'CAPITAL = D("1000")',
        'MIN_TRANCHE = D("50")',
        "FULL_UTILIZATION_SLOT_RANGE",
        "Unused capital remains cash",
        '"activation_performed": False',
    )
    missing = [item for item in required if item not in source]
    if missing:
        raise CheckFailure(f"capital-budget methodology incomplete: {missing}")
    return [
        {
            "capital_budget_methodology": {
                "fixed_account_equity_usdc": "1000",
                "searches_slots_tranche_policy_and_reserve": True,
                "unused_budget_remains_cash": True,
                "research_only": True,
            }
        },
        coverage("capital_budget_methodology", "capital_budget_scope"),
    ]


def _capital_budget_audit_a02() -> list[dict[str, Any]]:
    output = ROOT / "evidence" / "capital-budget-optimizer.json"
    if output.exists():
        output.unlink()
    command = require_command(
        [sys.executable, "-m", "scripts.capital_budget_optimizer"],
        timeout=7200,
    )
    if not output.is_file():
        raise CheckFailure("fresh capital-budget optimizer evidence missing")
    payload = json.loads(output.read_text(encoding="utf-8"))
    if payload.get("research_only") is not True or payload.get("activation_performed") is not False:
        raise CheckFailure("capital-budget optimizer crossed research boundary")
    if str(payload.get("maximum_account_capital_usdc")) != "1000":
        raise CheckFailure("capital-budget search did not use fixed 1000-USDC account")
    return [
        command,
        {"capital_budget_result": payload},
        coverage("capital_budget_fresh_search"),
    ]


def _capital_budget_audit_a03() -> list[dict[str, Any]]:
    source = (ROOT / "scripts" / "capital_budget_optimizer.py").read_text(encoding="utf-8")
    required = (
        "_candidate_map(research=True)",
        "strategy_parameters_by_symbol=",
        "trade_policies_by_symbol=",
        "_profile_hashes(profiles)",
    )
    missing = [item for item in required if item not in source]
    if missing:
        raise CheckFailure(f"capital-budget profile consistency incomplete: {missing}")
    return [
        {
            "capital_budget_profile_contract": (
                "ONE_RESEARCH_PROFILE_MAP_REUSED_ACROSS_ALL_LAYOUTS"
            )
        },
        coverage("capital_budget_profile_consistency"),
    ]


def _capital_budget_audit_a04() -> list[dict[str, Any]]:
    source = (ROOT / "scripts" / "capital_budget_optimizer.py").read_text(encoding="utf-8")
    forbidden = ("PaperStore(", "enable_live(", "start_trial(", "versions.py")
    present = [item for item in forbidden if item in source]
    if present:
        raise CheckFailure(f"capital-budget research crosses product boundary: {present}")
    return [
        {
            "capital_budget_product_state": (
                "RESEARCH_ONLY_NO_CANONICAL_UI_PAPER_OR_LIVE_MUTATION"
            )
        },
        coverage("capital_budget_product_separation"),
    ]


def _capital_budget_payload() -> dict[str, Any]:
    output = ROOT / "evidence" / "capital-budget-optimizer.json"
    if output.is_file():
        return json.loads(output.read_text(encoding="utf-8"))
    evidence = _capital_budget_audit_a02()
    result = evidence[1].get("capital_budget_result")
    if not isinstance(result, dict):
        raise CheckFailure("capital-budget result unavailable")
    return result


def _capital_budget_audit_a05() -> list[dict[str, Any]]:
    payload = _capital_budget_payload()
    interesting = [payload["best_baseline"], payload["best_robust"]]
    refs = payload.get("references", {})
    for key in (
        "ranked_repeat:3x80",
        "ranked_repeat:5x50",
        "ranked_repeat:4x250",
        "ranked_repeat:10x100",
        "ranked_repeat:12x80",
        "ranked_repeat:20x50",
    ):
        item = refs.get(key)
        if isinstance(item, dict):
            interesting.append(item)
    detail = {
        str(row["layout"]): {
            "ending_equity": row["ending_equity"],
            "position_cycles": row["position_cycles"],
            "slot_trades": row["slot_trades"],
            "max_concurrent_slots": row["max_concurrent_slots"],
            "blocked_no_free_slot": row["blocked_no_free_slot"],
            "capital_utilization_pct": row["capital_utilization_pct"],
            "max_drawdown_pct": row["max_drawdown_pct"],
        }
        for row in interesting
    }
    return [
        {"capital_budget_trade_utilization": detail},
        coverage("capital_budget_trade_utilization"),
    ]


def _capital_budget_audit_a06() -> list[dict[str, Any]]:
    payload = _capital_budget_payload()
    best_baseline = payload["best_baseline"]
    best_stress = payload["best_stress"]
    best_robust = payload["best_robust"]
    return [
        {
            "capital_budget_stress": {
                "best_baseline": best_baseline,
                "best_stress": best_stress,
                "best_robust": best_robust,
                "leader_stable": (
                    best_baseline["layout"] == best_stress["layout"]
                    == best_robust["layout"]
                ),
            }
        },
        coverage("capital_budget_stress_robustness"),
    ]


def _capital_budget_audit_a07() -> list[dict[str, Any]]:
    exchange = _json_url("/api/v3/exchangeInfo")
    symbols = {str(item.get("symbol")): item for item in exchange.get("symbols", [])}
    from hixton.constants import SYMBOLS

    invalid = [
        symbol
        for symbol in SYMBOLS
        if symbol not in symbols
        or symbols[symbol].get("status") != "TRADING"
        or symbols[symbol].get("quoteAsset") != "USDC"
    ]
    if invalid:
        raise CheckFailure(f"capital-budget Binance universe invalid: {invalid}")
    return [
        {"capital_budget_binance_symbols": list(SYMBOLS)},
        coverage("capital_budget_binance_rules"),
    ]


def _capital_budget_audit_a08() -> list[dict[str, Any]]:
    payload = _capital_budget_payload()
    scaling = ROOT / "evidence" / "capital-scaling-sanity.json"
    scaling_payload: dict[str, Any] | None = None
    if scaling.is_file():
        scaling_payload = json.loads(scaling.read_text(encoding="utf-8"))
    return [
        {
            "capital_budget_layout_assessment": {
                "best_robust": payload["best_robust"],
                "reference_layouts": payload.get("references", {}),
                "scaling_sanity": scaling_payload,
                "interpretation": (
                    "Separate true capital/notional scaling from extra opportunity capture "
                    "created by more independently reusable slots."
                ),
            }
        },
        coverage("capital_budget_scaling_and_layout"),
    ]


def _capital_budget_audit_a10(reports_dir: Path | None) -> list[dict[str, Any]]:
    if reports_dir is None:
        raise CheckFailure("capital-budget A10 requires reports")
    reports = load_reports(reports_dir)
    result = evidence_flag(reports.get("A02", {}), "capital_budget_result")
    stress = evidence_flag(reports.get("A06", {}), "capital_budget_stress")
    layout = evidence_flag(reports.get("A08", {}), "capital_budget_layout_assessment")
    if not isinstance(result, dict) or not isinstance(stress, dict) or not isinstance(layout, dict):
        raise CheckFailure("capital-budget specialist evidence incomplete")
    return [
        {
            "capital_budget_synthesis": {
                "best_baseline": result.get("best_baseline"),
                "best_stress": result.get("best_stress"),
                "best_robust": result.get("best_robust"),
                "candidate_layout_count": result.get("candidate_layout_count"),
                "stress_assessment": stress,
                "layout_assessment": layout,
                "research_only": True,
                "automatic_product_change": False,
            }
        },
        coverage("capital_budget_synthesis"),
    ]


def _capital_budget_audit_a09(reports_dir: Path | None) -> list[dict[str, Any]]:
    if reports_dir is None:
        raise CheckFailure("capital-budget A09 requires reports")
    reports = load_reports(reports_dir)
    synthesis = evidence_flag(reports.get("A10", {}), "capital_budget_synthesis")
    if not isinstance(synthesis, dict) or synthesis.get("research_only") is not True:
        raise CheckFailure("capital-budget QA rejects non-research result")
    return [
        {"capital_budget_qa": "PASS_RESEARCH_ONLY"},
        coverage("capital_budget_qa"),
    ]


def _capital_budget_audit_a11(reports_dir: Path | None) -> list[dict[str, Any]]:
    if reports_dir is None:
        raise CheckFailure("capital-budget A11 requires reports")
    reports = load_reports(reports_dir)
    synthesis = evidence_flag(reports.get("A10", {}), "capital_budget_synthesis")
    if (
        not isinstance(synthesis, dict)
        or synthesis.get("research_only") is not True
        or synthesis.get("automatic_product_change") is not False
    ):
        raise CheckFailure("capital-budget governance denied")
    return [
        {
            "capital_budget_governance": (
                "PASS_RESEARCH_ONLY_NO_AUTOMATIC_PRODUCT_OR_LIVE_CONFIGURATION"
            )
        },
        coverage("capital_budget_governance"),
    ]


def capital_budget_audit_evidence(
    role: str,
    reports_dir: Path | None,
) -> list[dict[str, Any]]:
    handlers = {
        "A01": lambda: _capital_budget_audit_a01(),
        "A02": lambda: _capital_budget_audit_a02(),
        "A03": lambda: _capital_budget_audit_a03(),
        "A04": lambda: _capital_budget_audit_a04(),
        "A05": lambda: _capital_budget_audit_a05(),
        "A06": lambda: _capital_budget_audit_a06(),
        "A07": lambda: _capital_budget_audit_a07(),
        "A08": lambda: _capital_budget_audit_a08(),
        "A09": lambda: _capital_budget_audit_a09(reports_dir),
        "A10": lambda: _capital_budget_audit_a10(reports_dir),
        "A11": lambda: _capital_budget_audit_a11(reports_dir),
    }
    return handlers[role]()


def role_a01() -> list[dict[str, Any]]:
    ready = validate_cloud_ready(ROOT)
    contract = paper_runtime_contract()
    documents = (
        "README.md",
        "AGENTS.md",
        "agent_memory/architecture.md",
        "agent_memory/dataflows.md",
    )
    for path in documents:
        if not (ROOT / path).is_file():
            raise CheckFailure(f"required documentation missing: {path}")
    product_docs = (
        (ROOT / "README.md").read_text(encoding="utf-8")
        + "\n"
        + (ROOT / "DMS" / "18_BACKTEST_STATUS_UND_ERGEBNISFORMAT.md").read_text(
            encoding="utf-8"
        )
    )
    stale_product_terms = (
        "10×250 Baseline",
        "10×250 Stress",
        "3×80 Baseline",
        "3×80 Stress",
        "Buy & Hold Ende",
    )
    found_stale = [term for term in stale_product_terms if term in product_docs]
    if found_stale:
        raise CheckFailure(
            "current product documentation still exposes research alternatives: "
            + ", ".join(found_stale)
        )
    return [
        {"cloud_ready": ready},
        {"paper_contract": contract},
        coverage("requirements_contract", "paper_only_contract", "mission_lifecycle"),
    ]


def role_a02() -> list[dict[str, Any]]:
    tests = existing_tests(
        "test_backtest*.py",
        "test_*portfolio*.py",
        "test_*parity*.py",
        "test_coin_profiles.py",
    )
    if not tests:
        raise CheckFailure("no backtest/research regression tests found")
    command = [sys.executable, "-m", "pytest", "-q", *tests]
    result = require_command(command, timeout=1200)
    return [
        result,
        coverage("current_v6_backtest", "topk_validation", "portfolio_gate"),
    ]


def role_a03() -> list[dict[str, Any]]:
    state = check_state_db()
    tests = existing_tests(
        "test_paper*.py",
        "test_*parity*.py",
        "test_cloud_paper_cycle.py",
        "test_current_v6_product_contract.py",
    )
    evidence: list[dict[str, Any]] = [{"paper_state": state}]
    if tests:
        command = [sys.executable, "-m", "pytest", "-q", *tests]
        evidence.append(require_command(command, timeout=1200))
    evidence.append(coverage("paper_shared_parity", "persistent_paper_state"))
    return evidence


def role_a04() -> list[dict[str, Any]]:
    static = ROOT / "src" / "hixton" / "ui" / "static"
    files = [path for path in static.rglob("*") if path.is_file()]
    if not files:
        raise CheckFailure("tracked UI static bundle is empty")
    source_html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    source_ts = (ROOT / "ui" / "src" / "main.ts").read_text(encoding="utf-8")
    visible_source = source_html + "\n" + source_ts
    ambiguous_labels = {
        "Buy & Hold Ende": (
            "Buy & Hold is research-only and must not appear as a parallel product result."
        ),
        "backtest-comparison": (
            "The current V6 product must not render a separate historical comparison banner."
        ),
        "Historischer Vergleich:": (
            "Historical comparison prose belongs in research evidence, not the current result."
        ),
    }
    found = [label for label in ambiguous_labels if label in visible_source]
    if found:
        detail = "; ".join(f"{label}: {ambiguous_labels[label]}" for label in found)
        raise CheckFailure(f"ambiguous financial UI semantics: {detail}")
    tests = existing_tests(
        "test_ui*.py",
        "test_*api*.py",
        "test_chart*.py",
        "test_current_v6_product_contract.py",
    )
    evidence: list[dict[str, Any]] = [{"static_file_count": len(files)}]
    if tests:
        command = [sys.executable, "-m", "pytest", "-q", *tests]
        evidence.append(require_command(command, timeout=900))
    evidence.append(coverage("current_v6_ui", "shipped_ui_bundle", "ui_metric_semantics"))
    return evidence


def role_a05() -> list[dict[str, Any]]:
    state = check_state_db()
    if not STATE_MANIFEST.is_file():
        raise CheckFailure("Paper state manifest not restored")
    manifest = json.loads(STATE_MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("mode") != "PAPER_ONLY":
        raise CheckFailure("state manifest is not PAPER_ONLY")
    if manifest.get("real_money_orders_allowed") is not False:
        raise CheckFailure("state manifest allows real orders")
    saved_at = datetime.fromisoformat(str(manifest["saved_at_utc"])).astimezone(UTC)
    age = datetime.now(UTC) - saved_at
    if age > timedelta(hours=2):
        raise CheckFailure(f"Paper state is stale by {age}")
    freshness = {
        "saved_at_utc": saved_at.isoformat(),
        "age_seconds": age.total_seconds(),
    }
    return [
        {"paper_state": state},
        freshness,
        coverage("runtime_freshness", "ledger_integrity"),
    ]


def _json_url(path: str) -> Any:
    request = urllib.request.Request(
        f"{MARKET_DATA_URL}{path}",
        headers={"User-Agent": "Hixton-Paper-Watchdog/1.0"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise CheckFailure(f"Binance market-data HTTP {response.status}: {path}")
        return json.loads(response.read().decode("utf-8"))


def role_a06() -> list[dict[str, Any]]:
    compile_result = require_command(
        [sys.executable, "-m", "compileall", "-q", "src", "scripts"]
    )
    tests = require_command(
        [sys.executable, "-m", "pytest", "-q"],
        timeout=1800,
    )
    return [
        compile_result,
        tests,
        coverage("integration_compile", "full_regression"),
    ]


def role_a07() -> list[dict[str, Any]]:
    paper_runtime_contract()
    exchange = _json_url("/api/v3/exchangeInfo")
    symbols = {str(item.get("symbol")): item for item in exchange.get("symbols", [])}
    from hixton.constants import SYMBOLS

    missing = [symbol for symbol in SYMBOLS if symbol not in symbols]
    nontrading = [
        symbol
        for symbol in SYMBOLS
        if symbol in symbols and symbols[symbol].get("status") != "TRADING"
    ]
    if missing or nontrading:
        detail = f"missing={missing} nontrading={nontrading}"
        raise CheckFailure(f"Binance USDC market problem {detail}")
    server_time = _json_url("/api/v3/time")
    sample_path = f"/api/v3/klines?symbol={SYMBOLS[0]}&interval=1h&limit=2"
    sample = _json_url(sample_path)
    if not isinstance(sample, list) or len(sample) < 2:
        raise CheckFailure("Binance public kline sample invalid")
    return [
        {
            "endpoint": MARKET_DATA_URL,
            "markets": list(SYMBOLS),
            "server_time": server_time,
            "kline_sample_count": len(sample),
        },
        coverage("binance_usdc_universe", "public_kline_sample"),
    ]


def role_a08() -> list[dict[str, Any]]:
    paper_runtime_contract()
    tests = existing_tests(
        "test_*risk*.py",
        "test_coin_profiles.py",
        "test_strategy*.py",
        "test_trade_policy*.py",
        "test_current_v6_product_contract.py",
    )
    if not tests:
        raise CheckFailure("no strategy/risk regression tests found")
    config = ROOT / "config" / "examples" / "config.example.json"
    payload = json.loads(config.read_text(encoding="utf-8"))
    paper = payload.get("paper", {})
    expected = {
        "starting_cash_usdc": "250.00",
        "slot_count": 3,
        "target_notional_usdc": "80.00",
    }
    drift = {
        key: paper.get(key)
        for key, value in expected.items()
        if paper.get(key) != value
    }
    if drift:
        raise CheckFailure(f"Paper baseline config drifted: {drift}")
    command = [sys.executable, "-m", "pytest", "-q", *tests]
    result = require_command(command, timeout=1200)
    return [
        result,
        coverage("strategy_risk_invariants", "loss_analysis"),
    ]


def load_reports(directory: Path) -> dict[str, dict[str, Any]]:
    reports: dict[str, dict[str, Any]] = {}
    for path in directory.rglob("*.json"):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        agent = report.get("agent")
        if agent in AGENT_IDS:
            reports[str(agent)] = report
    return reports


def coverage_defects(
    reports: dict[str, dict[str, Any]], agents: list[str]
) -> dict[str, list[str]]:
    mission = load_mission(ROOT)
    contract = required_evidence_by_agent(mission)
    defects: dict[str, list[str]] = {}
    for agent in agents:
        required = set(contract.get(agent, ()))
        actual = report_coverage(reports.get(agent, {}))
        missing = sorted(required - actual)
        if missing:
            defects[agent] = missing
    return defects


def role_a10(reports_dir: Path) -> list[dict[str, Any]]:
    ready = validate_cloud_ready(ROOT)
    reports = load_reports(reports_dir)
    required = [f"A{i:02d}" for i in range(1, 9)]
    missing = [agent for agent in required if agent not in reports]
    failed = [
        agent for agent in required if reports.get(agent, {}).get("verdict") != "PASS"
    ]
    evidence_missing = coverage_defects(reports, required)
    if missing or failed or evidence_missing:
        detail = (
            f"missing={missing}, failed={failed}, evidence_missing={evidence_missing}"
        )
        raise CheckFailure(f"dispatcher repair loop: {detail}")
    return [
        {
            "mission_id": ready["mission_id"],
            "mission_state": ready["mission_state"],
            "specialists_received": required,
            "evidence_contract_passed": True,
            "repair_required": False,
        },
        coverage("evidence_contract_audit", "repair_routing"),
    ]


def role_a09(reports_dir: Path) -> list[dict[str, Any]]:
    reports = load_reports(reports_dir)
    required = [f"A{i:02d}" for i in range(1, 9)] + ["A10"]
    bad = [
        agent for agent in required if reports.get(agent, {}).get("verdict") != "PASS"
    ]
    evidence_missing = coverage_defects(reports, required)
    a10 = reports.get("A10", {})
    if (
        bad
        or evidence_missing
        or evidence_flag(a10, "evidence_contract_passed") is not True
        or evidence_flag(a10, "repair_required") is not False
    ):
        detail = (
            f"bad={bad}, evidence_missing={evidence_missing}, "
            f"a10_contract={evidence_flag(a10, 'evidence_contract_passed')}, "
            f"a10_repair={evidence_flag(a10, 'repair_required')}"
        )
        raise CheckFailure(f"QA cannot pass; upstream contract incomplete: {detail}")
    commands = (
        ([sys.executable, "-m", "compileall", "-q", "src", "scripts"], 900),
        ([sys.executable, "-m", "ruff", "check", "src", "scripts", "tests"], 900),
        ([sys.executable, "-m", "mypy", "src"], 1200),
        ([sys.executable, "-m", "pytest", "-q"], 1800),
        ([sys.executable, "src/main.py", "status"], 120),
    )
    evidence = [require_command(command, timeout=timeout) for command, timeout in commands]
    evidence.append(coverage("independent_full_qa", "independent_ui_qa"))
    return evidence


def role_a11(reports_dir: Path) -> list[dict[str, Any]]:
    ready = validate_cloud_ready(ROOT)
    reports = load_reports(reports_dir)
    required = [f"A{i:02d}" for i in range(1, 11)]
    missing = [agent for agent in required if agent not in reports]
    failed = [
        agent for agent in required if reports.get(agent, {}).get("verdict") != "PASS"
    ]
    evidence_missing = coverage_defects(reports, required)
    qa = reports.get("A09", {})
    a10 = reports.get("A10", {})
    if (
        missing
        or failed
        or evidence_missing
        or qa.get("gate") != "QA_PASS"
        or evidence_flag(a10, "evidence_contract_passed") is not True
        or evidence_flag(a10, "repair_required") is not False
    ):
        detail = (
            f"missing={missing}, failed={failed}, evidence_missing={evidence_missing}, "
            f"qa_gate={qa.get('gate')}, "
            f"a10_contract={evidence_flag(a10, 'evidence_contract_passed')}, "
            f"a10_repair={evidence_flag(a10, 'repair_required')}"
        )
        raise CheckFailure(f"governance denied: {detail}")
    paper_runtime_contract()
    return [
        {
            "mission_id": ready["mission_id"],
            "mission_state": ready["mission_state"],
            "audited_agents": required,
            "evidence_contract_passed": True,
            "qa_gate": "QA_PASS",
            "repair_required": False,
            "governance": "GOVERNANCE_PASS",
        },
        coverage("governance_audit"),
    ]


SIMPLE_ROLES = {
    "A01": role_a01,
    "A02": role_a02,
    "A03": role_a03,
    "A04": role_a04,
    "A05": role_a05,
    "A06": role_a06,
    "A07": role_a07,
    "A08": role_a08,
}


def execute(role: str, reports_dir: Path | None) -> dict[str, Any]:
    started = datetime.now(UTC)
    report: dict[str, Any] = {
        "schema_version": 2,
        "agent": role,
        "started_at_utc": started.isoformat(),
        "execution_mode": "DETERMINISTIC_KEY_FREE",
        "openai_api_key_required": False,
        "binance_private_credentials_required": False,
        "real_money_orders_allowed": False,
        "testnet_orders_allowed": False,
    }
    try:
        if role in SIMPLE_ROLES:
            evidence = SIMPLE_ROLES[role]()
        elif role == "A10":
            if reports_dir is None:
                raise CheckFailure("A10 requires --reports-dir")
            evidence = role_a10(reports_dir)
        elif role == "A09":
            if reports_dir is None:
                raise CheckFailure("A09 requires --reports-dir")
            evidence = role_a09(reports_dir)
        elif role == "A11":
            if reports_dir is None:
                raise CheckFailure("A11 requires --reports-dir")
            evidence = role_a11(reports_dir)
        else:
            raise CheckFailure(f"unknown agent: {role}")
        if live_audit_enabled():
            evidence.extend(live_audit_evidence(role, reports_dir))
        if optimization_audit_enabled():
            evidence.extend(optimization_audit_evidence(role, reports_dir))
        if capital100_audit_enabled():
            evidence.extend(capital100_audit_evidence(role, reports_dir))
        if capital_budget_audit_enabled():
            evidence.extend(capital_budget_audit_evidence(role, reports_dir))
        report["verdict"] = "PASS"
        report["evidence"] = evidence
        if role == "A09":
            report["gate"] = "QA_PASS"
        if role == "A11":
            report["gate"] = "GOVERNANCE_PASS"
    except Exception as error:
        report["verdict"] = "FAIL"
        report["error"] = f"{type(error).__name__}: {error}"
        if role == "A10":
            report["repair_required"] = True
            report["repair_owner"] = "A10"
            report["defect_class"] = "LIFECYCLE_OR_EVIDENCE_CONTRACT"
        if role == "A09":
            report["gate"] = "QA_FAIL"
        if role == "A11":
            report["gate"] = "GOVERNANCE_FAIL"
    report["finished_at_utc"] = datetime.now(UTC).isoformat()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", required=True, choices=AGENT_IDS)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reports-dir", type=Path)
    args = parser.parse_args(argv)
    report = execute(args.role, args.reports_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    args.output.write_text(serialized, encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
