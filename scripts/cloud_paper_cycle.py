"""Run one headless Paper recovery/sync cycle on real public Binance market data.

This script is intentionally a thin operational wrapper around RuntimeSupervisor.
It does not implement strategy, risk, allocation, fills or exchange logic itself.
No Binance credentials are read and no real/testnet order path is invoked.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import replace
from pathlib import Path

from hixton.config import ProjectConfig, load_project_config
from hixton.paper.storage import PaperStore
from hixton.runtime.supervisor import RuntimeSupervisor

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "examples" / "config.example.json"
BINANCE_MARKET_DATA_ONLY_URL = "https://data-api.binance.vision"


def cloud_market_data_config(config: ProjectConfig) -> ProjectConfig:
    """Keep all bot settings identical while forcing Binance's public-data-only host."""
    return replace(config, binance_base_url=BINANCE_MARKET_DATA_ONLY_URL)


async def run_cycle(config_path: Path) -> dict[str, object]:
    resolved = config_path if config_path.is_absolute() else PROJECT_ROOT / config_path
    config = cloud_market_data_config(load_project_config(resolved, project_root=PROJECT_ROOT))
    supervisor = RuntimeSupervisor(config)

    # Reuse the canonical startup recovery path. On the first ever Paper account
    # this initializes at the latest closed bar without backtrading history. On
    # every later run it processes all finalized bars since the persisted
    # checkpoints exactly once using real Binance candles and the current bar's
    # immutable OPEN as the execution reference.
    await supervisor._sync_and_analyze(initial=True)  # noqa: SLF001
    snapshot = supervisor.state.snapshot()
    if snapshot.health != "HEALTHY":
        raise RuntimeError(f"cloud Paper cycle did not become healthy: {snapshot.health}")

    with PaperStore(config.database_path) as store:
        account = store.load_account()
        settings = store.load_settings()
        session = store.load_strategy_session()
        positions = store.load_positions()
        checkpoints = store.all_checkpoints()
        recent_events = store.load_events(limit=20)
        soak = store.load_soak_progress()

    return {
        "mode": "PAPER_ONLY",
        "market_data": "BINANCE_PUBLIC_USDC",
        "market_data_base_url": config.binance_base_url,
        "strategy_key": session.strategy_key,
        "strategy_version": session.strategy_version,
        "cash_usdc": str(account.cash_usdc),
        "starting_cash_usdc": str(account.starting_cash_usdc),
        "high_water_equity_usdc": str(account.high_water_equity_usdc),
        "halted": account.halted,
        "halt_reason": account.halt_reason,
        "slot_count": settings.slot_count,
        "target_notional_usdc": str(settings.target_notional_usdc),
        "emergency_stop": settings.emergency_stop,
        "open_positions": [position.symbol for position in positions],
        "checkpoint_count": len(checkpoints),
        "latest_checkpoint_utc": max(checkpoints.values()).isoformat() if checkpoints else None,
        "recent_event_count": len(recent_events),
        "soak_status": soak.status,
        "last_sync_utc": snapshot.last_sync_utc.isoformat() if snapshot.last_sync_utc else None,
        "real_money_orders_allowed": False,
        "testnet_orders_allowed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one cloud Paper cycle")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)
    result = asyncio.run(run_cycle(args.config))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
