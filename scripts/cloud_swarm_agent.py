"""Key-free deterministic roles for the GitHub-hosted Hixton swarm.

These roles inspect and test the Paper-only system. They never read Binance
credentials, never submit orders and never import the unreleased live adapter.
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
            "SELECT slot_count, target_notional_text, emergency_stop "
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
    if int(settings[0]) != 3 or str(settings[1]) != "80.00":
        raise CheckFailure(f"Paper sizing drifted from 3x80: {settings}")
    if int(settings[2]) != 0:
        raise CheckFailure("Paper emergency stop is active")
    if int(checkpoint_count) != 10:
        raise CheckFailure(f"expected 10 Paper checkpoints, got {checkpoint_count}")
    return {
        "cash_usdc": str(account[0]),
        "starting_cash_usdc": str(account[1]),
        "high_water_usdc": str(account[2]),
        "halted": bool(account[3]),
        "halt_reason": account[4],
        "slot_count": int(settings[0]),
        "target_notional_usdc": str(settings[1]),
        "checkpoint_count": int(checkpoint_count),
        "latest_checkpoint_utc": latest_checkpoint,
    }



LIVE_AUDIT_CASE = "LIVE_READINESS_AUDIT"


def live_audit_enabled() -> bool:
    mission = load_mission(ROOT)
    cases = mission.get("regression_cases") or []
    return LIVE_AUDIT_CASE in cases


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
        open_positions = int(connection.execute("SELECT COUNT(*) FROM paper_positions").fetchone()[0])
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
    if not dms_files:
        raise CheckFailure("DMS documentation missing")
    required = {
        "02_VERBINDLICHE_ANFORDERUNGEN.md": (
            "250 USDC",
            "drei 80-USDC-Slots",
            "Echtgeld/Testnet bleiben gesperrt",
        ),
        "06_BACKTEST_UND_VALIDIERUNG.md": (
            "portfolio: 250 USDC gemeinsam, 3×80, ranked_repeat",
            "10×250 USDC isoliert",
        ),
        "07_AUSFUEHRUNG_ORDERS.md": (
            "Paper ist die einzige freigegebene Ausführung",
            "Real- und Testnet-Orderpfade bleiben technisch/organisatorisch gesperrt",
        ),
        "18_BACKTEST_STATUS_UND_ERGEBNISFORMAT.md": (
            "3×80 aktuell",
            "Simulationen sind ausdrücklich keine Binance-Ausführungs- oder Zukunftsnachweise",
        ),
        "22_QUELLEN_UND_BINANCE_PRUEFUNG.md": (
            "Öffentliche Preisreihen beweisen keine reale Fillqualität",
            "Private Binance-Endpunkte",
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
                "portfolio_contract": "250 USDC shared / max 3 x 80 USDC / 10 symbols",
                "diagnostic_only": "10x250",
                "documented_release_state": "PAPER_ONLY_LIVE_BLOCKED",
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
    portfolio = payload.get("portfolio_3x80", {})
    summary = portfolio.get("summary", {})
    timing = portfolio.get("trade_timing", {})
    if (
        payload.get("credentials_used") is not False
        or payload.get("orders_sent") is not False
        or summary.get("slot_count") != 3
        or str(summary.get("target_notional")) != "80.00"
        or summary.get("slot_allocation") != "ranked_repeat"
        or int(summary.get("completed_trades", 0)) <= 0
        or int(timing.get("max_slot_occupancy", 99)) > 3
    ):
        raise CheckFailure("fresh 3x80 E2E violates audit invariants")
    return [
        command,
        {
            "backtest_execution_realism": {
                "strategy": payload.get("strategy"),
                "report_start_utc": portfolio.get("report_start_utc"),
                "report_end_utc": portfolio.get("report_end_utc"),
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
    if activity["open_positions"] > 3:
        raise CheckFailure("Paper state exceeds three-position capacity")
    return [
        tests,
        {"paper_live_activity": activity},
        coverage("paper_live_signal_parity", "slot_reuse_contract"),
    ]


def _live_audit_a04() -> list[dict[str, Any]]:
    preparation = (ROOT / "src" / "hixton" / "live" / "preparation.py").read_text(
        encoding="utf-8"
    )
    routes = (ROOT / "src" / "hixton" / "ui" / "live.py").read_text(encoding="utf-8")
    required = (
        '"order_dispatch_available": False',
        '"ready": False',
        '"trial_dispatch_available": False',
        '"slot_count": 1',
        '"target_notional_quote": "50.00"',
    )
    if any(value not in preparation for value in required) or "status_code=409" not in routes:
        raise CheckFailure("Live UI/preparation no longer fails closed")
    tests = require_command(
        [sys.executable, "-m", "pytest", "-q", "tests/test_live_preparation.py"],
        timeout=1200,
    )
    return [
        tests,
        {
            "live_release_ready": False,
            "live_order_dispatch_available": False,
            "current_live_surface": "BLOCKED_PREPARATION_AND_SINGLE_50_USDC_TRIAL_ONLY",
            "main_3x80_live_controls_available": False,
        },
        coverage("live_ui_fail_closed", "live_capital_semantics"),
    ]


def _live_audit_a05() -> list[dict[str, Any]]:
    activity = _current_strategy_activity()
    state = activity["paper_state"]
    technical_blockers: list[str] = []
    if bool(state.get("halted")):
        technical_blockers.append("PAPER_HALTED")
    if not bool(activity.get("all_ten_checkpoints_present")):
        technical_blockers.append("MISSING_CHECKPOINTS")
    if int(activity.get("open_positions", 0)) > 3:
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
        },
        coverage("current_no_trade_diagnosis", "live_runtime_blockers"),
    ]


def _live_audit_a06() -> list[dict[str, Any]]:
    sources = {
        "orders": (ROOT / "tests" / "test_live_orders.py").read_text(encoding="utf-8"),
        "trial": (ROOT / "tests" / "test_live_trial.py").read_text(encoding="utf-8"),
        "preparation": (ROOT / "tests" / "test_live_preparation.py").read_text(
            encoding="utf-8"
        ),
    }
    required_tests = {
        "orders": ("test_concurrent_submit_claim_has_one_winner",),
        "trial": (
            "test_ten_simultaneous_signals_reserve_one_entry_in_dms_rank_order",
            "test_reserved_entry_restart_and_timeout_cannot_rebuy",
            "test_global_trial_budget_rejects_every_other_amount",
        ),
        "preparation": (
            "test_clean_account_is_not_live_approval",
            "test_common_settings_reject_unapproved_limits_without_silent_fallback",
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
        ],
        timeout=1800,
    )
    return [
        tests,
        {
            "runaway_order_guard": "FAIL_CLOSED_BEFORE_PRODUCTION_RELEASE",
            "production_3x80_live_implemented": False,
            "live_release_ready": False,
            "covered_failure_classes": [
                "concurrent_submit",
                "duplicate_delivery",
                "timeout_query_without_resubmit",
                "restart_reserved_entry",
                "ten_simultaneous_signals",
                "invalid_or_huge_notional",
                "clean_account_does_not_enable_live",
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
        price = filters.get("PRICE_FILTER", {})
        notional = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL") or {}
        entry = {
            "status": item.get("status"),
            "quote_asset": item.get("quoteAsset"),
            "spot_allowed": item.get("isSpotTradingAllowed"),
            "order_types": item.get("orderTypes"),
            "tick_size": price.get("tickSize"),
            "step_size": lot.get("stepSize"),
            "min_qty": lot.get("minQty"),
            "min_notional": notional.get("minNotional"),
        }
        if (
            entry["status"] != "TRADING"
            or entry["quote_asset"] != "USDC"
            or entry["spot_allowed"] is not True
            or "MARKET" not in (entry["order_types"] or [])
            or not entry["step_size"]
            or not entry["min_qty"]
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
        ],
        timeout=1200,
    )
    preparation = (ROOT / "src" / "hixton" / "live" / "preparation.py").read_text(
        encoding="utf-8"
    )
    if "production_submission_accepted\": False" not in preparation:
        raise CheckFailure("production submission gate is not explicitly closed")
    return [
        tests,
        {
            "live_strategy_risk": {
                "main_portfolio": "250 USDC / max 3 x 80 USDC",
                "research_10x250_is_live_capital": False,
                "production_submission_accepted": False,
                "live_release_ready": False,
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
        evidence_flag(a04, "live_release_ready") is not False
        or evidence_flag(a06, "live_release_ready") is not False
        or evidence_flag(a06, "production_3x80_live_implemented") is not False
    ):
        raise CheckFailure("live audit did not preserve explicit not-ready state")
    return [
        {
            "live_release_ready": False,
            "audit_result": "LIVE_NOT_READY",
            "reason": "Production 3x80 live dispatcher is intentionally not implemented/released.",
        },
        coverage("live_audit_evidence_contract"),
    ]


def _live_audit_a09(reports_dir: Path | None) -> list[dict[str, Any]]:
    if reports_dir is None:
        raise CheckFailure("live A09 audit requires reports")
    reports = load_reports(reports_dir)
    a10 = reports.get("A10", {})
    if (
        evidence_flag(a10, "live_release_ready") is not False
        or evidence_flag(a10, "audit_result") != "LIVE_NOT_READY"
    ):
        raise CheckFailure("QA must not turn an incomplete Live path into a release")
    return [
        {
            "live_release_ready": False,
            "qa_live_decision": "AUDIT_PASS_LIVE_NOT_READY",
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
        evidence_flag(a09, "live_release_ready") is not False
        or evidence_flag(a10, "live_release_ready") is not False
    ):
        raise CheckFailure("governance refuses any implicit Live approval")
    return [
        {
            "live_release_ready": False,
            "governance_live_decision": "AUDIT_GOVERNANCE_PASS_LIVE_NOT_READY",
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
