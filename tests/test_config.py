from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from hixton.cli import main
from hixton.config import load_project_config
from hixton.domain.versions import strategy_definition


def test_windows_runtime_timezone_is_available() -> None:
    assert ZoneInfo("Europe/Berlin").key == "Europe/Berlin"


def _payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "strategy": {"key": "v6"},
        "markets": list(strategy_definition("v6").symbols),
        "backtest": {
            "starting_usdc_per_symbol": "250.00",
            "target_notional_usdc": "250.00",
            "primary_window_years": 3,
        },
        "paper": {
            "starting_cash_usdc": "250.00",
            "max_capital_usdc": "250.00",
            "poll_seconds": 30,
            "daily_audit_utc": "00:05",
        },
        "ui": {
            "bind": "127.0.0.1",
            "port": 8765,
            "timezone": "Europe/Berlin",
            "default_range": "1m",
        },
        "runtime": {
            "database_path": "data/hixton-usdc.sqlite3",
            "run_output_root": "backtests/v6/runs",
            "binance_base_url": "https://api.binance.com",
        },
    }


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_valid_active_v6_config_resolves_runtime_paths(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    _write(path, _payload())
    config = load_project_config(path, project_root=tmp_path)
    assert config.database_path == tmp_path / "data" / "hixton-usdc.sqlite3"
    assert config.strategy_key == "v6"
    assert config.ui_port == 8765
    assert config.paper_poll_seconds == 30
    assert config.paper_starting_cash_usdc == Decimal("250.00")
    assert config.paper_max_capital_usdc == Decimal("250.00")
    assert config.paper_slot_count == 2
    assert config.paper_target_notional_usdc == Decimal("125.00")


def test_unknown_root_field_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    payload = _payload()
    payload["unexpected"] = True
    _write(path, payload)
    with pytest.raises(ValueError, match="unknown root"):
        load_project_config(path, project_root=tmp_path)


def test_paper_capital_scales_modularly(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    payload = _payload()
    paper = payload["paper"]
    assert isinstance(paper, dict)
    paper["starting_cash_usdc"] = "1000.00"
    paper["max_capital_usdc"] = "1000.00"
    _write(path, payload)
    config = load_project_config(path, project_root=tmp_path)
    assert config.paper_max_capital_usdc == Decimal("1000.00")
    assert config.paper_slot_count == 2
    assert config.paper_target_notional_usdc == Decimal("500.00")


def test_paper_starting_cash_must_match_max_capital(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    payload = _payload()
    paper = payload["paper"]
    assert isinstance(paper, dict)
    paper["starting_cash_usdc"] = "250.00"
    paper["max_capital_usdc"] = "1000.00"
    _write(path, payload)
    with pytest.raises(ValueError, match="must equal configured max capital"):
        load_project_config(path, project_root=tmp_path)


def test_live_command_remains_technically_locked(capsys: pytest.CaptureFixture[str]) -> None:
    result = main(["live"])
    assert result == 2
    assert "sicher gesperrt" in capsys.readouterr().err
