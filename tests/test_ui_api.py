from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from hixton.config import ProjectConfig
from hixton.constants import SYMBOLS
from hixton.paper.storage import PaperStore
from hixton.runtime.supervisor import RuntimeSupervisor
from hixton.ui.api import create_app


def _config(tmp_path: Path) -> ProjectConfig:
    return ProjectConfig(
        strategy_key="v2",
        database_path=tmp_path / "hixton.sqlite3",
        run_output_root=tmp_path / "backtests" / "v2" / "runs",
        binance_base_url="https://api.binance.com",
        starting_usdc_per_symbol=Decimal("250.00"),
        target_notional_usdc=Decimal("250.00"),
        run_baseline_and_stress=True,
        paper_poll_seconds=30,
        paper_starting_cash_usdc=Decimal("240.00"),
        paper_slot_count=3,
        paper_target_notional_usdc=Decimal("80.00"),
        daily_audit_utc="00:05",
        ui_bind="127.0.0.1",
        ui_port=8765,
        ui_timezone="Europe/Berlin",
        ui_default_range="1m",
        sha256="test-config",
    )


def test_local_ui_status_and_ten_market_placeholders(tmp_path: Path) -> None:
    config = _config(tmp_path)
    client = TestClient(
        create_app(config, RuntimeSupervisor(config)),
        base_url="http://127.0.0.1:8765",
    )
    status = client.get("/api/status")
    assert status.status_code == 200
    assert status.json()["runtime"]["live_state"] == "LIVE_DISABLED"
    assert status.headers["x-frame-options"] == "DENY"
    markets = client.get("/api/markets")
    assert markets.status_code == 200
    assert [item["symbol"] for item in markets.json()["markets"]] == list(SYMBOLS)
    logs = client.get("/api/logs")
    assert logs.status_code == 200
    assert logs.json()["logs"][0]["event_code"] == "PROCESS_START"


def test_reconnected_stream_clears_only_its_own_error(tmp_path: Path) -> None:
    supervisor = RuntimeSupervisor(_config(tmp_path))
    stream_error = "keepalive ping timeout"
    supervisor.state.set_status(
        health="DEGRADED",
        stream_connected=False,
        feed_mode="REST_FALLBACK",
        last_error=stream_error,
    )

    supervisor._mark_stream_connected(stream_error)

    recovered = supervisor.state.snapshot()
    assert recovered.health == "HEALTHY"
    assert recovered.stream_connected is True
    assert recovered.feed_mode == "WEBSOCKET"
    assert recovered.last_error is None

    supervisor.state.set_status(health="DEGRADED", last_error="data audit failed")
    supervisor._mark_stream_connected(stream_error)

    unrelated = supervisor.state.snapshot()
    assert unrelated.health == "DEGRADED"
    assert unrelated.last_error == "data audit failed"


def test_setting_write_requires_local_action_header_and_confirmation(tmp_path: Path) -> None:
    config = _config(tmp_path)
    client = TestClient(
        create_app(config, RuntimeSupervisor(config)),
        base_url="http://127.0.0.1:8765",
    )
    payload = {
        "slot_count": 2,
        "target_notional_usdc": "60.00",
        "emergency_stop": True,
        "confirmation": "ANWENDEN",
    }
    denied = client.post("/api/paper/settings", json=payload)
    assert denied.status_code == 403
    saved = client.post(
        "/api/paper/settings",
        json=payload,
        headers={"X-Hixton-Action": "local-ui-v1", "Origin": "http://127.0.0.1:8765"},
    )
    assert saved.status_code == 200
    with PaperStore(config.database_path) as store:
        settings = store.load_settings()
    assert settings.slot_count == 2
    assert settings.target_notional_usdc == Decimal("60.00")
    assert settings.emergency_stop is True


def test_status_exposes_restart_persistent_paper_soak_gate(tmp_path: Path) -> None:
    config = _config(tmp_path)
    started = datetime.now(UTC)
    checkpoints = dict.fromkeys(SYMBOLS, started)
    with PaperStore(config.database_path) as store:
        store.initialize(
            at=started,
            strategy_key="v2",
            strategy_version="HIXTON-V2-RESEARCH-CANDIDATE-1",
        )
        store.save_checkpoints(checkpoints)
        store.ensure_soak_started(checkpoints, at=started)
    client = TestClient(
        create_app(config, RuntimeSupervisor(config)),
        base_url="http://127.0.0.1:8765",
    )
    paper = client.get("/api/status").json()["paper"]
    assert paper["soak"]["status"] == "RUNNING"
    assert paper["soak"]["minimum_processed_closed_bars"] == 0
    assert paper["soak"]["completed_trades"] == 0
    assert paper["soak"]["ready"] is False


def test_backtest_api_keeps_v1_and_v2_run_views_separate(tmp_path: Path) -> None:
    config = _config(tmp_path)
    client = TestClient(
        create_app(config, RuntimeSupervisor(config)),
        base_url="http://127.0.0.1:8765",
    )

    v1 = client.get("/api/backtests?strategy=v1")
    v2 = client.get("/api/backtests?strategy=v2")
    invalid = client.get("/api/backtests?strategy=unknown")

    assert v1.status_code == 200
    assert v1.json()["strategy"]["version"] == "HIXTON-SPEC-1.0"
    assert v1.json()["strategy"]["paper_approved"] is False
    assert v2.status_code == 200
    assert v2.json()["strategy"]["version"] == "HIXTON-V2-RESEARCH-CANDIDATE-1"
    assert v2.json()["strategy"]["paper_approved"] is True
    assert invalid.status_code == 400


def test_backtest_filters_mode_coin_and_sorts_creation_before_display_cap(tmp_path: Path) -> None:
    config = _config(tmp_path)

    def write_run(key: str, mode: str, day: int, symbols: tuple[str, ...]) -> None:
        path = config.run_output_root / key
        path.mkdir(parents=True)
        (path / "manifest.json").write_text(
            json.dumps(
                {
                    "run_id": key,
                    "run_mode": mode,
                    "created_at_utc": f"2026-09-{day:02}T12:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )
        (path / "metrics.json").write_text(
            json.dumps(
                {
                    "baseline": {"per_symbol": {symbol: {} for symbol in symbols}},
                }
            ),
            encoding="utf-8",
        )
        # Copied older directories look newer on disk; creation time must win.
        os.utime(path, (1_800_000_000 - day * 100, 1_800_000_000 - day * 100))

    write_run("portfolio-old", "portfolio", 1, ())
    write_run("portfolio-new", "portfolio", 6, ())
    write_run("single-eth", "single", 2, ("ETHUSDC",))
    write_run("single-btc", "single", 3, ("BTCUSDC",))
    # >25 other runs must not make the selected old portfolio disappear.
    for index in range(30):
        write_run(f"batch-{index}", "batch", 5, SYMBOLS)
    broken = config.run_output_root / "incomplete"
    broken.mkdir()
    (broken / "manifest.json").write_text("[invalid", encoding="utf-8")
    client = TestClient(
        create_app(config, RuntimeSupervisor(config)),
        base_url="http://127.0.0.1:8765",
    )
    for query, expected in (
        ("mode=portfolio", ["portfolio-new", "portfolio-old"]),
        ("mode=single&symbol=eth/usdc", ["single-eth"]),
        ("mode=single&symbol=BTCUSDC", ["single-btc"]),
        ("strategy=v6&mode=portfolio", []),
    ):
        response = client.get(f"/api/backtests?{query}")
        assert response.status_code == 200
        assert [r["manifest"]["run_id"] for r in response.json()["runs"]] == expected
    assert len(client.get("/api/backtests?mode=all").json()["runs"]) == 25
    for query in ("mode=unknown", "mode=single", "mode=single&symbol=FAKE", "symbol=ETHUSDC"):
        assert client.get(f"/api/backtests?{query}").status_code == 400
    assert len(list(config.run_output_root.iterdir())) == 35  # Nothing deleted.


def test_ui_documentation_uses_runtime_strategy_and_current_branch(tmp_path: Path) -> None:
    config = _config(tmp_path)
    client = TestClient(
        create_app(config, RuntimeSupervisor(config)),
        base_url="http://127.0.0.1:8765",
    )
    html = client.get("/").text
    assert 'id="doc-strategy-version"' in html
    assert 'id="backtest-history"' in html
    assert 'aria-label="Backtestart"' in html
    assert "/blob/main/" not in html
    assert "BACKTEST V1" not in html
    assert "<strong>HIXTON-SPEC-1.0</strong>" not in html


def test_legacy_backtest_currency_not_relabelled_or_written(tmp_path: Path) -> None:
    from hixton.ui.api import _list_backtests

    for quote in ("USDT", "USDC"):
        directory = tmp_path / quote
        directory.mkdir()
        manifest = {"run_id": quote, "data": {"snapshot_sha256_by_symbol": {"BTC" + quote: "hash"}}}
        original = json.dumps(manifest)
        (directory / "manifest.json").write_text(original, encoding="utf-8")
        (directory / "metrics.json").write_text('{"baseline":{"portfolio":{}}}', encoding="utf-8")
    results = _list_backtests(tmp_path)
    assert {r["manifest"]["run_id"]: r["manifest"]["quote_asset"] for r in results} == {
        "USDT": "USDT",
        "USDC": "USDC",
    }
    for quote in ("USDT", "USDC"):
        stored = json.loads((tmp_path / quote / "manifest.json").read_text(encoding="utf-8"))
        assert "quote_asset" not in stored
