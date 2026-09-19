"""Known-safe deterministic repairs for A10.

This module is intentionally narrow. It may repair stale product-contract tests,
the exact-three-calendar-year backtest window contract, the current-only V6
continuity scenario, and the reproducible shipped UI bundle. It must never
change strategy parameters, Paper account state, Live code, or swarm governance.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from scripts.swarm_core import validate_cloud_patch_paths

ROOT = Path(__file__).resolve().parents[1]

ALLOWED_PREFIXES = (
    "src/hixton/runtime/analysis.py",
    "src/hixton/runtime/continuity_supervisor.py",
    "tests/test_cli_portfolio.py",
    "tests/test_backtest_exact_three_year.py",
    "tests/test_usdc_runtime_migration.py",
    "src/hixton/ui/static/",
)


class RepairError(RuntimeError):
    pass


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _replace_once(path: str, old: str, new: str) -> bool:
    content = _read(path)
    if new in content:
        return False
    count = content.count(old)
    if count != 1:
        raise RepairError(f"{path}: expected one repair anchor, found {count}")
    _write(path, content.replace(old, new))
    return True


def repair_current_only_continuity() -> bool:
    changed = False
    changed |= _replace_once(
        "src/hixton/runtime/continuity_supervisor.py",
        "from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS, ExecutionRules",
        "from hixton.backtest.models import CURRENT_COSTS, ExecutionRules",
    )
    changed |= _replace_once(
        "src/hixton/runtime/continuity_supervisor.py",
        "        for costs in (BASELINE_COSTS, STRESS_COSTS):",
        "        for costs in (CURRENT_COSTS,):",
    )
    return changed


def repair_exact_history_gate() -> bool:
    old = """    actual = max(requested_start, max(starts))
    if actual >= end:
        raise ValueError("Insufficient common history after 400 warm-up bars")
    return actual
"""
    new = """    common_start = max(starts)
    if common_start > requested_start:
        raise ValueError(
            "Insufficient exact three-year history after 400 warm-up bars: "
            f"required report start {requested_start.isoformat()}, "
            f"first common report start {common_start.isoformat()}"
        )
    if requested_start >= end:
        raise ValueError("Insufficient exact three-year history after 400 warm-up bars")
    return requested_start
"""
    return _replace_once("src/hixton/runtime/analysis.py", old, new)


def repair_single_scenario_test() -> bool:
    return _replace_once(
        "tests/test_cli_portfolio.py",
        "    assert len(calls) == 2\n",
        "    assert len(calls) == 1\n",
    )


def repair_legacy_shortened_window_tests() -> bool:
    changed = False
    changed |= _replace_once(
        "tests/test_usdc_runtime_migration.py",
        "    assert available_report_start({SYMBOLS[0]: later}, start, end) == candles[500].open_time_utc\n",
        (
            '    with pytest.raises(ValueError, match="exact three-year history"):\n'
            "        available_report_start({SYMBOLS[0]: later}, start, end)\n"
        ),
    )
    changed |= _replace_once(
        "tests/test_usdc_runtime_migration.py",
        (
            '    assert available_report_start(snapshot, first + timedelta(hours=400), end) == (\n'
            '        common + timedelta(hours=400)\n'
            '    )\n'
        ),
        (
            '    with pytest.raises(ValueError, match="exact three-year history"):\n'
            '        available_report_start(snapshot, first + timedelta(hours=400), end)\n'
        ),
    )
    return changed


def ensure_exact_three_year_tests() -> bool:
    path = "tests/test_backtest_exact_three_year.py"
    desired = '''from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from hixton import cli
from hixton.domain.models import Candle
from hixton.runtime import analysis
from hixton.runtime.supervisor import safe_closed_window


class _ValidAudit:
    def require_valid(self) -> None:
        return None


def _candle(symbol: str, open_time: datetime) -> Candle:
    return Candle(
        symbol=symbol,
        open_time_utc=open_time,
        close_time_utc=open_time + timedelta(hours=1),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=1.0,
    )


def test_cli_window_is_exactly_three_calendar_years_plus_400_warmup_hours() -> None:
    end = datetime(2026, 9, 19, 19, tzinfo=UTC)
    warmup, start, actual_end = cli._window(end)
    assert actual_end == end
    assert start == datetime(2023, 9, 19, 19, tzinfo=UTC)
    assert warmup == start - timedelta(hours=400)


def test_ui_runtime_window_is_exactly_three_calendar_years_plus_warmup() -> None:
    now = datetime(2026, 9, 19, 19, 37, tzinfo=UTC)
    warmup, start, end = safe_closed_window(now)
    assert end == datetime(2026, 9, 19, 19, tzinfo=UTC)
    assert start == datetime(2023, 9, 19, 19, tzinfo=UTC)
    assert warmup == start - timedelta(hours=400)


def test_available_report_start_fails_closed_instead_of_shortening(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested = datetime(2023, 9, 19, 19, tzinfo=UTC)
    end = datetime(2026, 9, 19, 19, tzinfo=UTC)
    # One warm-up hour is missing: a former implementation silently shortened
    # the report window by one hour. The product contract now rejects it.
    first = requested - timedelta(hours=399)
    monkeypatch.setattr(analysis, "audit_candles", lambda *args, **kwargs: _ValidAudit())
    with pytest.raises(ValueError, match="exact three-year history"):
        analysis.available_report_start(
            {"BTCUSDC": [_candle("BTCUSDC", first)]},
            requested,
            end,
        )


def test_available_report_start_keeps_requested_start_when_full_warmup_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested = datetime(2023, 9, 19, 19, tzinfo=UTC)
    end = datetime(2026, 9, 19, 19, tzinfo=UTC)
    first = requested - timedelta(hours=400)
    monkeypatch.setattr(analysis, "audit_candles", lambda *args, **kwargs: _ValidAudit())
    assert (
        analysis.available_report_start(
            {"BTCUSDC": [_candle("BTCUSDC", first)]},
            requested,
            end,
        )
        == requested
    )
'''
    target = ROOT / path
    if target.is_file() and target.read_text(encoding="utf-8") == desired:
        return False
    _write(path, desired)
    return True


def sync_ui_bundle() -> bool:
    before = subprocess.run(
        ["git", "status", "--porcelain", "--", "src/hixton/ui/static"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    subprocess.run(["npm", "--prefix", "ui", "ci"], cwd=ROOT, check=True)
    subprocess.run(["npm", "--prefix", "ui", "test"], cwd=ROOT, check=True)
    subprocess.run(["npm", "--prefix", "ui", "run", "check"], cwd=ROOT, check=True)
    subprocess.run(["npm", "--prefix", "ui", "run", "build"], cwd=ROOT, check=True)
    after = subprocess.run(
        ["git", "status", "--porcelain", "--", "src/hixton/ui/static"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return after != before or bool(after.strip())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    reports = {}
    for path in args.reports_dir.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        agent = payload.get("agent")
        if isinstance(agent, str):
            reports[agent] = payload

    failed = {
        agent
        for agent in ("A02", "A04", "A06")
        if reports.get(agent, {}).get("verdict") == "FAIL"
    }
    if not failed:
        result = {"changed": False, "reason": "no known-safe A02/A04/A06 repair required"}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return 0

    changed = False
    changed |= repair_current_only_continuity()
    changed |= repair_exact_history_gate()
    changed |= repair_single_scenario_test()
    changed |= repair_legacy_shortened_window_tests()
    changed |= ensure_exact_three_year_tests()
    changed |= sync_ui_bundle()

    status = subprocess.run(
        [
            "git",
            "status",
            "--porcelain",
            "--",
            "src/hixton/runtime/analysis.py",
            "src/hixton/runtime/continuity_supervisor.py",
            "tests/test_cli_portfolio.py",
            "tests/test_backtest_exact_three_year.py",
            "tests/test_usdc_runtime_migration.py",
            "src/hixton/ui/static",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    paths = []
    for line in status.splitlines():
        raw = line[3:]
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        paths.append(raw)
    normalized = validate_cloud_patch_paths(paths)
    unexpected = [
        path
        for path in normalized
        if not any(path == prefix or path.startswith(prefix) for prefix in ALLOWED_PREFIXES)
    ]
    if unexpected:
        raise RepairError(f"known-safe A10 repair touched unexpected paths: {unexpected}")

    result = {
        "changed": changed,
        "failed_agents": sorted(failed),
        "changed_paths": list(normalized),
        "strategy_parameters_changed": False,
        "paper_state_changed": False,
        "live_code_changed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
