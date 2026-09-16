"""Key-free deterministic roles for the GitHub-hosted Hixton swarm.

These roles inspect and test the Paper-only system. They never read Binance
credentials, never submit orders and never import the unreleased live adapter.
"""

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

from scripts.swarm_core import AGENT_IDS, load_json, validate_cloud_ready

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
    return [{"cloud_ready": ready}, {"paper_contract": contract}]


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
    return [require_command(command, timeout=1200)]


def role_a03() -> list[dict[str, Any]]:
    state = check_state_db()
    tests = existing_tests(
        "test_paper*.py",
        "test_*parity*.py",
        "test_cloud_paper_cycle.py",
    )
    evidence: list[dict[str, Any]] = [{"paper_state": state}]
    if tests:
        command = [sys.executable, "-m", "pytest", "-q", *tests]
        evidence.append(require_command(command, timeout=1200))
    return evidence


def role_a04() -> list[dict[str, Any]]:
    static = ROOT / "src" / "hixton" / "ui" / "static"
    files = [path for path in static.rglob("*") if path.is_file()]
    if not files:
        raise CheckFailure("tracked UI static bundle is empty")
    tests = existing_tests("test_ui*.py", "test_*api*.py", "test_chart*.py")
    evidence: list[dict[str, Any]] = [{"static_file_count": len(files)}]
    if tests:
        command = [sys.executable, "-m", "pytest", "-q", *tests]
        evidence.append(require_command(command, timeout=900))
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
    return [{"paper_state": state}, freshness]


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
    return [compile_result, tests]


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
        }
    ]


def role_a08() -> list[dict[str, Any]]:
    paper_runtime_contract()
    tests = existing_tests(
        "test_*risk*.py",
        "test_coin_profiles.py",
        "test_strategy*.py",
        "test_trade_policy*.py",
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
    drift = {key: paper.get(key) for key, value in expected.items() if paper.get(key) != value}
    if drift:
        raise CheckFailure(f"Paper baseline config drifted: {drift}")
    command = [sys.executable, "-m", "pytest", "-q", *tests]
    return [require_command(command, timeout=1200)]


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


def role_a10(reports_dir: Path) -> list[dict[str, Any]]:
    reports = load_reports(reports_dir)
    required = [f"A{i:02d}" for i in range(1, 9)]
    missing = [agent for agent in required if agent not in reports]
    failed = [
        agent for agent in required if reports.get(agent, {}).get("verdict") != "PASS"
    ]
    if missing or failed:
        detail = f"missing={missing}, failed={failed}"
        raise CheckFailure(f"dispatcher repair loop: {detail}")
    return [{"specialists_received": required, "repair_required": False}]


def role_a09(reports_dir: Path) -> list[dict[str, Any]]:
    reports = load_reports(reports_dir)
    required = [f"A{i:02d}" for i in range(1, 9)] + ["A10"]
    bad = [
        agent for agent in required if reports.get(agent, {}).get("verdict") != "PASS"
    ]
    if bad:
        raise CheckFailure(f"QA cannot pass; prior roles not PASS: {bad}")
    commands = (
        ([sys.executable, "-m", "compileall", "-q", "src", "scripts"], 900),
        ([sys.executable, "-m", "ruff", "check", "src", "scripts", "tests"], 900),
        ([sys.executable, "-m", "mypy", "src"], 1200),
        ([sys.executable, "-m", "pytest", "-q"], 1800),
        ([sys.executable, "src/main.py", "status"], 120),
    )
    return [require_command(command, timeout=timeout) for command, timeout in commands]


def role_a11(reports_dir: Path) -> list[dict[str, Any]]:
    reports = load_reports(reports_dir)
    required = [f"A{i:02d}" for i in range(1, 11)]
    missing = [agent for agent in required if agent not in reports]
    failed = [
        agent for agent in required if reports.get(agent, {}).get("verdict") != "PASS"
    ]
    qa = reports.get("A09", {})
    if missing or failed or qa.get("gate") != "QA_PASS":
        detail = (
            f"missing={missing}, failed={failed}, qa_gate={qa.get('gate')}"
        )
        raise CheckFailure(f"governance denied: {detail}")
    paper_runtime_contract()
    return [
        {
            "audited_agents": required,
            "qa_gate": "QA_PASS",
            "governance": "GOVERNANCE_PASS",
        }
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
        "schema_version": 1,
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
        report["verdict"] = "PASS"
        report["evidence"] = evidence
        if role == "A09":
            report["gate"] = "QA_PASS"
        if role == "A11":
            report["gate"] = "GOVERNANCE_PASS"
    except Exception as error:
        report["verdict"] = "FAIL"
        report["error"] = f"{type(error).__name__}: {error}"
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
