"""Research-only auto-budget checkbox preference must never silently arm Live."""

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
        paper_starting_cash_usdc=Decimal("250"),
        paper_slot_count=2,
        paper_target_notional_usdc=Decimal("125"),
        daily_audit_utc="00:05",
        ui_bind="127.0.0.1",
        ui_port=8765,
        ui_timezone="Europe/Berlin",
        ui_default_range="1m",
        sha256="auto-budget-ui-test",
    )


def test_disabled_by_default_and_rejects_non_boolean() -> None:
    assert PaperSettings().auto_budget_enabled is False
    for invalid in ("true", "false", 1, 0, None):
        with pytest.raises(ValueError, match="auto_budget_enabled"):
            PaperSettings(auto_budget_enabled=invalid)


def test_auto_budget_setting_survives_database_reopen(tmp_path: Path) -> None:
    db = tmp_path / "hixton.sqlite3"
    with PaperStore(db) as store:
        store.initialize(
            strategy_key="v8",
            strategy_version="research-test",
            starting_cash_usdc=Decimal("1100"),
        )
        saved = PaperSettings(max_capital_usdc=Decimal("1100"), auto_budget_enabled=True)
        store.save_settings(saved)
        assert store.load_settings().auto_budget_enabled is True
    with PaperStore(db) as store:
        assert store.load_settings().auto_budget_enabled is True
        assert store.load_settings().max_capital_usdc == Decimal("1100")


def test_local_ui_preference_is_saved_but_live_remains_locked(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    client = TestClient(
        create_app(cfg, RuntimeSupervisor(cfg)),
        base_url="http://127.0.0.1:8765",
    )
    payload = {
        "confirmation": "ANWENDEN",
        "max_capital_usdc": "1100",
        "emergency_stop": False,
        "gap_fillers_enabled": True,
        "auto_budget_enabled": True,
    }
    blocked = client.post("/api/trading/settings", json=payload)
    assert blocked.status_code == 403
    saved = client.post(
        "/api/trading/settings",
        json=payload,
        headers={"X-Hixton-Action": "local-ui-v1", "Origin": "http://127.0.0.1:8765"},
    )
    assert saved.status_code == 200
    assert saved.json()["settings"]["auto_budget_enabled"] is True
    assert saved.json()["settings"]["auto_budget_live_available"] is False
    with PaperStore(cfg.database_path) as store:
        assert store.load_settings().auto_budget_enabled is True
    status = client.get("/api/status").json()
    assert status["trading_settings"]["auto_budget_enabled"] is True
    assert status["trading_settings"]["auto_budget_live_available"] is False
    assert status["runtime"]["live_state"] == "LIVE_DISABLED"


def test_legacy_fixed_mode_can_stay_disabled(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    client = TestClient(
        create_app(cfg, RuntimeSupervisor(cfg)),
        base_url="http://127.0.0.1:8765",
    )
    saved = client.post(
        "/api/trading/settings",
        json={"confirmation": "ANWENDEN", "max_capital_usdc": "1100", "auto_budget_enabled": False},
        headers={"X-Hixton-Action": "local-ui-v1", "Origin": "http://127.0.0.1:8765"},
    )
    assert saved.status_code == 200
    assert saved.json()["settings"]["auto_budget_enabled"] is False
