"""Strict, secret-free JSON configuration for the active paper strategy."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from hixton.constants import SYMBOLS
from hixton.domain.versions import strategy_definition


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    strategy_key: str
    database_path: Path
    run_output_root: Path
    binance_base_url: str
    starting_usdc_per_symbol: Decimal
    target_notional_usdc: Decimal
    run_baseline_and_stress: bool
    paper_poll_seconds: int
    paper_starting_cash_usdc: Decimal
    paper_slot_count: int
    paper_target_notional_usdc: Decimal
    daily_audit_utc: str
    ui_bind: str
    ui_port: int
    ui_timezone: str
    ui_default_range: str
    sha256: str


def _required_mapping(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _reject_unknown(mapping: dict[str, Any], allowed: set[str], name: str) -> None:
    unknown = set(mapping) - allowed
    if unknown:
        raise ValueError(f"unknown {name} fields: {', '.join(sorted(unknown))}")


def load_project_config(path: Path, *, project_root: Path) -> ProjectConfig:
    raw_text = path.read_text(encoding="utf-8")
    payload = json.loads(raw_text)
    root = _required_mapping(payload, "configuration")
    _reject_unknown(
        root,
        {"schema_version", "strategy", "markets", "backtest", "paper", "ui", "runtime"},
        "root",
    )
    if root.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")

    strategy = _required_mapping(root.get("strategy"), "strategy")
    strategy_key = str(strategy.get("key", "")).lower()
    definition = strategy_definition(strategy_key)
    expected_strategy = definition.config_payload()
    _reject_unknown(strategy, set(expected_strategy), "strategy")
    if strategy != expected_strategy:
        differences = sorted(
            key for key, expected in expected_strategy.items() if strategy.get(key) != expected
        )
        raise ValueError(f"configuration deviates from {definition.version}: {differences}")
    if not definition.paper_approved:
        raise ValueError(f"strategy {definition.version} is not approved for paper")

    markets = root.get("markets")
    if not isinstance(markets, list) or tuple(markets) != SYMBOLS:
        raise ValueError("markets must contain the ten DMS symbols in fixed order")

    backtest = _required_mapping(root.get("backtest"), "backtest")
    _reject_unknown(
        backtest,
        {
            "starting_usdc_per_symbol",
            "target_notional_usdc",
            "primary_window_years",
            "run_baseline_and_stress",
        },
        "backtest",
    )
    if backtest.get("primary_window_years") != 3:
        raise ValueError("primary_window_years must be 3")
    starting = Decimal(str(backtest.get("starting_usdc_per_symbol")))
    target = Decimal(str(backtest.get("target_notional_usdc")))
    if starting != Decimal("250.00") or target != Decimal("250.00"):
        raise ValueError("isolated backtests require fixed 250.00 USDC")

    paper = _required_mapping(root.get("paper"), "paper")
    allowed_starting_cash = ("250.00",) if definition.coin_profiles else ("240.00", "250.00")
    if paper.get("starting_cash_usdc") not in allowed_starting_cash:
        raise ValueError("paper starting cash must be 250.00 (legacy V2 also accepts 240.00)")
    expected_paper: dict[str, object] = {
        "starting_cash_usdc": paper["starting_cash_usdc"],
        "slot_count": 3,
        "target_notional_usdc": "80.00",
        "poll_seconds": 30,
        "daily_audit_utc": "00:05",
    }
    _reject_unknown(paper, set(expected_paper), "paper")
    if paper != expected_paper:
        raise ValueError("paper baseline must match the versioned starting cash with 3x80 USDC")

    ui = _required_mapping(root.get("ui"), "ui")
    expected_ui: dict[str, object] = {
        "bind": "127.0.0.1",
        "port": 8765,
        "timezone": "Europe/Berlin",
        "default_range": "1m",
    }
    _reject_unknown(ui, set(expected_ui), "ui")
    if ui != expected_ui:
        raise ValueError("UI baseline must use the documented localhost settings")

    runtime = _required_mapping(root.get("runtime"), "runtime")
    _reject_unknown(runtime, {"database_path", "run_output_root", "binance_base_url"}, "runtime")
    database_path = project_root / str(runtime.get("database_path", "data/hixton.sqlite3"))
    run_output_root = project_root / str(
        runtime.get("run_output_root", f"backtests/{definition.backtest_version}/runs")
    )
    digest = hashlib.sha256(
        json.dumps(root, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ProjectConfig(
        strategy_key=definition.key,
        database_path=database_path,
        run_output_root=run_output_root,
        binance_base_url=str(runtime.get("binance_base_url", "https://api.binance.com")),
        starting_usdc_per_symbol=starting,
        target_notional_usdc=target,
        run_baseline_and_stress=bool(backtest.get("run_baseline_and_stress", True)),
        paper_poll_seconds=int(paper["poll_seconds"]),
        paper_starting_cash_usdc=Decimal(str(paper["starting_cash_usdc"])),
        paper_slot_count=int(paper["slot_count"]),
        paper_target_notional_usdc=Decimal(str(paper["target_notional_usdc"])),
        daily_audit_utc=str(paper["daily_audit_utc"]),
        ui_bind=str(ui["bind"]),
        ui_port=int(ui["port"]),
        ui_timezone=str(ui["timezone"]),
        ui_default_range=str(ui["default_range"]),
        sha256=digest,
    )
