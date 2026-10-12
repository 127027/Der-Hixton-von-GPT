"""Second autonomous-performance opt-in has explicit independent persistence and no Live arming."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hixton.config import ProjectConfig
from hixton.paper.models import PaperSettings
from hixton.paper.storage import PaperStore
from hixton.runtime.supervisor import RuntimeSupervisor
from hixton.ui.api import create_app


def config(tmp: Path) -> ProjectConfig:
    return ProjectConfig(
        strategy_key="v8",
        database_path=tmp / "hixton-usdc.sqlite3",
        run_output_root=tmp / "backtests" / "v8" / "runs",
        binance_base_url="https://data-api.binance.vision",
        starting_usdc_per_symbol=Decimal("250"),
        target_notional_usdc=Decimal("250"),
        run_baseline_and_stress=True,
        paper_poll_seconds=30,
        paper_starting_cash_usdc=Decimal("1100"),
        paper_slot_count=2,
        paper_target_notional_usdc=Decimal("550"),
        daily_audit_utc="00:05",
        ui_bind="127.0.0.1",
        ui_port=8765,
        ui_timezone="Europe/Berlin",
        ui_default_range="1m",
        sha256="research-dual-mode-test",
    )


def test_new_mode_is_explicit_off_by_default_and_boolean() -> None:
    assert PaperSettings().autonomous_performance_enabled is False
    for bad in (0, 1, "true", None):
        with pytest.raises(ValueError, match="autonomous_performance_enabled"):
            PaperSettings(autonomous_performance_enabled=bad)


def test_second_mode_independent_from_auto_budget_and_restart_safe(tmp_path: Path) -> None:
    db = tmp_path / "example.sqlite3"
    with PaperStore(db) as store:
        store.initialize(
            strategy_key="v8", strategy_version="research-test", starting_cash_usdc=Decimal("1100")
        )
        store.save_settings(
            PaperSettings(
                max_capital_usdc=Decimal("1100"),
                auto_budget_enabled=False,
                autonomous_performance_enabled=True,
            )
        )
    with PaperStore(db) as store:
        s = store.load_settings()
        assert s.autonomous_performance_enabled is True
        assert s.auto_budget_enabled is False
        assert s.max_capital_usdc == Decimal("1100")


def test_ui_can_save_second_opt_in_but_marks_it_not_live_ready(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    client = TestClient(create_app(cfg, RuntimeSupervisor(cfg)), base_url="http://127.0.0.1:8765")
    payload = {
        "confirmation": "ANWENDEN",
        "max_capital_usdc": "1100",
        "auto_budget_enabled": True,
        "autonomous_performance_enabled": True,
        "emergency_stop": False,
        "gap_fillers_enabled": True,
    }
    rejected = client.post("/api/trading/settings", json=payload)
    assert rejected.status_code == 403
    saved = client.post(
        "/api/trading/settings",
        json=payload,
        headers={"X-Hixton-Action": "local-ui-v1", "Origin": "http://127.0.0.1:8765"},
    )
    assert saved.status_code == 200
    result = saved.json()["settings"]
    assert result["auto_budget_enabled"] is True
    assert result["autonomous_performance_enabled"] is True
    assert result["auto_budget_live_available"] is False
    assert result["autonomous_performance_live_available"] is False
    status = client.get("/api/status").json()
    assert status["trading_settings"]["autonomous_performance_enabled"] is True
    assert status["runtime"]["live_state"] == "LIVE_DISABLED"


def test_false_by_default_for_backwards_compatible_api(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    client = TestClient(create_app(cfg, RuntimeSupervisor(cfg)), base_url="http://127.0.0.1:8765")
    saved = client.post(
        "/api/trading/settings",
        json={"confirmation": "ANWENDEN", "max_capital_usdc": "1100"},
        headers={"X-Hixton-Action": "local-ui-v1", "Origin": "http://127.0.0.1:8765"},
    )
    assert saved.status_code == 200
    assert saved.json()["settings"]["autonomous_performance_enabled"] is False
