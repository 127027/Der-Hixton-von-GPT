from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from hixton.cli import main
from hixton.config import load_project_config
from hixton.constants import SYMBOLS


def test_windows_runtime_timezone_is_available() -> None:
    assert ZoneInfo("Europe/Berlin").key == "Europe/Berlin"


def _payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "strategy": {
            "key": "v2",
            "quote_asset": "USDC",
            "version": "HIXTON-V2-RESEARCH-CANDIDATE-1",
            "timeframe": "1h",
            "source": "close",
            "vidya_length": 6,
            "momentum_length": 20,
            "smoothing_length": 8,
            "atr_length": 60,
            "band_multiplier": 3.8,
            "warmup_bars": 400,
            "slot_allocation": "one_per_symbol",
            "long_only": True,
            "compounding": False,
        },
        "markets": list(SYMBOLS),
        "backtest": {
            "starting_usdc_per_symbol": "250.00",
            "target_notional_usdc": "250.00",
            "primary_window_years": 3,
            "run_baseline_and_stress": True,
        },
        "paper": {
            "starting_cash_usdc": "240.00",
            "slot_count": 3,
            "target_notional_usdc": "80.00",
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
            "database_path": "data/hixton.sqlite3",
            "run_output_root": "backtests/v2/runs",
            "binance_base_url": "https://api.binance.com",
        },
    }


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_valid_active_v2_config_resolves_runtime_paths(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    _write(path, _payload())
    config = load_project_config(path, project_root=tmp_path)
    assert config.database_path == tmp_path / "data" / "hixton.sqlite3"
    assert config.strategy_key == "v2"
    assert config.ui_port == 8765
    assert config.paper_poll_seconds == 30
    assert config.paper_starting_cash_usdc == Decimal("240.00")
    assert config.paper_slot_count == 3
    assert config.paper_target_notional_usdc == Decimal("80.00")


def test_unknown_or_changed_paper_baseline_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    payload = _payload()
    payload["unexpected"] = True
    _write(path, payload)
    with pytest.raises(ValueError, match="unknown root"):
        load_project_config(path, project_root=tmp_path)

    payload = _payload()
    paper = payload["paper"]
    assert isinstance(paper, dict)
    paper["slot_count"] = 4
    _write(path, payload)
    with pytest.raises(ValueError, match="3x80"):
        load_project_config(path, project_root=tmp_path)


def test_live_command_remains_technically_locked(capsys: pytest.CaptureFixture[str]) -> None:
    result = main(["live"])
    assert result == 2
    assert "sicher gesperrt" in capsys.readouterr().err
