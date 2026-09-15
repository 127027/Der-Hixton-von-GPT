from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from scripts import cloud_paper_cycle


def test_cloud_cycle_reuses_startup_recovery_without_live_credentials(monkeypatch, tmp_path: Path):
    calls: list[bool] = []
    database = tmp_path / "paper.sqlite3"
    config = SimpleNamespace(
        database_path=database,
        binance_base_url=cloud_paper_cycle.BINANCE_MARKET_DATA_ONLY_URL,
    )

    class FakeState:
        def snapshot(self):
            return SimpleNamespace(
                health="HEALTHY",
                last_sync_utc=datetime(2026, 9, 15, 20, 0, tzinfo=UTC),
            )

    class FakeSupervisor:
        def __init__(self, received_config):
            assert received_config is config
            self.state = FakeState()

        async def _sync_and_analyze(self, *, initial: bool):
            calls.append(initial)

    class FakeStore:
        def __init__(self, path):
            assert Path(path) == database

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def load_account(self):
            return SimpleNamespace(
                cash_usdc=Decimal("250"),
                starting_cash_usdc=Decimal("250"),
                high_water_equity_usdc=Decimal("250"),
                halted=False,
                halt_reason=None,
            )

        def load_settings(self):
            return SimpleNamespace(
                slot_count=3,
                target_notional_usdc=Decimal("80"),
                emergency_stop=False,
            )

        def load_strategy_session(self):
            return SimpleNamespace(strategy_key="v6", strategy_version="paper-v6")

        def load_positions(self):
            return (SimpleNamespace(symbol="ETHUSDC"),)

        def all_checkpoints(self):
            return {"ETHUSDC": datetime(2026, 9, 15, 19, 0, tzinfo=UTC)}

        def load_events(self, *, limit: int):
            assert limit == 20
            return ()

        def load_soak_progress(self):
            return SimpleNamespace(status="RUNNING")

    monkeypatch.setattr(cloud_paper_cycle, "load_project_config", lambda *args, **kwargs: config)
    monkeypatch.setattr(cloud_paper_cycle, "cloud_market_data_config", lambda value: value)
    monkeypatch.setattr(cloud_paper_cycle, "RuntimeSupervisor", FakeSupervisor)
    monkeypatch.setattr(cloud_paper_cycle, "PaperStore", FakeStore)

    result = asyncio.run(cloud_paper_cycle.run_cycle(Path("ignored.json")))

    assert calls == [True]
    assert result["mode"] == "PAPER_ONLY"
    assert result["market_data"] == "BINANCE_PUBLIC_USDC"
    assert result["market_data_base_url"] == cloud_paper_cycle.BINANCE_MARKET_DATA_ONLY_URL
    assert result["real_money_orders_allowed"] is False
    assert result["testnet_orders_allowed"] is False
    assert result["open_positions"] == ["ETHUSDC"]
