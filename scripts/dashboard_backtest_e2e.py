"""Run the real dashboard backtest API against public Binance history.

This is CI-only evidence. It uses the same FastAPI route and canonical runtime
supervisor as the local dashboard, sends no orders, uses no credentials and
writes only to a temporary Paper/database directory.
"""

from __future__ import annotations

import asyncio
import csv
import json
import tempfile
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

from hixton.backtest.continuity import HISTORY_MODE
from hixton.config import load_project_config
from hixton.constants import SYMBOLS
from hixton.data.binance import BinancePublicClient
from hixton.data.storage import CandleStore, StoredSymbolRules
from hixton.domain.allocation import RANKED_REPEAT
from hixton.domain.versions import strategy_definition
from hixton.paper.storage import PaperStore
from hixton.runtime.continuity_supervisor import RuntimeSupervisor
from hixton.ui.api import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "examples" / "config.example.json"
ACTION_HEADERS = {
    "X-Hixton-Action": "local-ui-v1",
    "Origin": "http://127.0.0.1:8765",
}


def _seed_current_usdc_rules(database_path: Path) -> None:
    # GitHub-hosted runners can be geoblocked on api.binance.com. Binance's
    # public data endpoint exposes the same read-only exchange metadata needed
    # by this CI proof and is already the continuity-history source.
    public = BinancePublicClient(base_url="https://data-api.binance.vision")
    checked_at = datetime.now(UTC)
    with CandleStore(database_path) as store:
        for symbol in SYMBOLS:
            rules = public.symbol_rules(symbol)
            if not rules.tradable_for_quote("USDC"):
                raise RuntimeError(f"{symbol}: current Binance USDC rules are not tradable")
            store.put_symbol_rules(
                StoredSymbolRules(
                    symbol=rules.symbol,
                    status=rules.status,
                    quote_asset=rules.quote_asset,
                    spot_allowed=rules.spot_allowed,
                    order_types=rules.order_types,
                    tick_size=rules.tick_size,
                    step_size=rules.step_size,
                    min_qty=rules.min_qty,
                    min_notional=rules.min_notional,
                    checked_at_utc=checked_at,
                )
            )


def _initialize_paper(database_path: Path) -> None:
    strategy = strategy_definition("v6")
    with PaperStore(database_path) as store:
        store.initialize(
            strategy_key=strategy.key,
            strategy_version=strategy.version,
            starting_cash_usdc=None,
        )
        store.require_strategy(strategy.key, strategy.version)


def _baseline_summary(run: dict[str, Any], mode: str) -> dict[str, Any]:
    baseline = run["metrics"]["baseline"]
    if mode == "portfolio":
        portfolio = baseline["portfolio"]
        metrics = portfolio["metrics"]
        cycles = metrics["completed_trades"]
        slot_trades = metrics.get("completed_slot_trades")
        if not isinstance(slot_trades, int):
            raise RuntimeError("portfolio backtest did not expose completed_slot_trades")
        if slot_trades < cycles:
            raise RuntimeError("slot-equivalent trades cannot be fewer than position cycles")
        if portfolio.get("slot_allocation") != RANKED_REPEAT:
            raise RuntimeError("dashboard portfolio is not using owner-approved ranked_repeat")
        return {
            "ending_equity": metrics["ending_equity"],
            "return_pct": metrics["return_pct"],
            "completed_trades": cycles,
            "completed_slot_trades": slot_trades,
            "max_drawdown_pct": metrics["max_drawdown_pct"],
            "risk_halted_at_utc": portfolio.get("risk_halted_at_utc"),
            "slot_count": portfolio["slot_count"],
            "slot_allocation": portfolio["slot_allocation"],
            "target_notional": portfolio["target_notional"],
            "blocked_reasons": portfolio.get("blocked_reasons", {}),
        }
    batch = baseline["batch"]
    per_symbol = baseline.get("per_symbol", {})
    return {
        "ending_equity": batch["ending_equity"],
        "return_pct": batch["return_pct"],
        "completed_trades": batch["completed_trades"],
        "max_drawdown_pct": batch["max_drawdown_pct"],
        "per_symbol": {
            symbol: {
                "ending_equity": metrics["ending_equity"],
                "completed_trades": metrics["completed_trades"],
                "max_drawdown_pct": metrics["max_drawdown_pct"],
            }
            for symbol, metrics in per_symbol.items()
        },
    }


async def _run_mode(
    client: httpx.AsyncClient,
    supervisor: RuntimeSupervisor,
    mode: str,
) -> dict[str, Any]:
    response = await client.post(
        "/api/backtests/run",
        headers=ACTION_HEADERS,
        json={"mode": mode, "strategy": "v6"},
    )
    response.raise_for_status()
    if response.json().get("started") is not True:
        raise RuntimeError(f"dashboard did not start {mode} backtest")

    for _ in range(7_200):
        status = supervisor.state.snapshot()
        if status.backtest_status == "COMPLETE":
            break
        if status.backtest_status == "FAILED":
            raise RuntimeError(f"dashboard {mode} backtest failed: {status.last_error}")
        await asyncio.sleep(0.25)
    else:
        raise TimeoutError(f"dashboard {mode} backtest did not finish")

    listing = await client.get(
        "/api/backtests",
        params={"strategy": "v6", "mode": mode},
    )
    listing.raise_for_status()
    runs = listing.json().get("runs", [])
    if not runs:
        raise RuntimeError(f"dashboard returned no {mode} run")
    run = runs[0]
    manifest = run["manifest"]
    data = manifest.get("data", {})
    if data.get("history_mode") != HISTORY_MODE:
        raise RuntimeError(f"dashboard {mode} run is not the canonical continuity mode")
    if data.get("runtime_quote") != "USDC" or data.get("market_proxy_quote") != "USDT":
        raise RuntimeError("dashboard continuity provenance is incomplete")
    if data.get("paper_state_modified") is not False or data.get("orders_sent") is not False:
        raise RuntimeError("historical dashboard test must not mutate Paper or send orders")

    start = datetime.fromisoformat(data["report_start_utc"]).astimezone(UTC)
    end = datetime.fromisoformat(data["report_end_utc"]).astimezone(UTC)
    if (end - start).days < 1_095:
        raise RuntimeError(f"dashboard {mode} window is shorter than three years: {start} -> {end}")

    return {
        "mode": mode,
        "comparison": run.get("comparison"),
        "report_start_utc": data["report_start_utc"],
        "report_end_utc": data["report_end_utc"],
        "history_mode": data["history_mode"],
        "runtime_quote": data["runtime_quote"],
        "market_proxy_quote": data["market_proxy_quote"],
        "summary": _baseline_summary(run, mode),
    }



def _portfolio_trade_breakdown(run_output_root: Path) -> dict[str, dict[str, object]]:
    candidates: list[tuple[datetime, Path]] = []
    for directory in run_output_root.iterdir():
        if not directory.is_dir():
            continue
        manifest_path = directory / "manifest.json"
        trades_path = directory / "trades.csv"
        if not manifest_path.exists() or not trades_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("run_mode") != "portfolio":
            continue
        created = datetime.fromisoformat(manifest["created_at_utc"]).astimezone(UTC)
        candidates.append((created, trades_path))
    if not candidates:
        raise RuntimeError("portfolio trades.csv missing after dashboard backtest")

    trades_path = max(candidates, key=lambda item: item[0])[1]
    breakdown: dict[str, dict[str, object]] = {}
    with trades_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["scenario"] != "baseline":
                continue
            symbol = row["symbol"]
            item = breakdown.setdefault(
                symbol,
                {
                    "position_cycles": 0,
                    "slot_trades": 0,
                    "one_slot_cycles": 0,
                    "two_slot_cycles": 0,
                    "three_slot_cycles": 0,
                    "wins": 0,
                    "losses": 0,
                    "realized_pnl": "0",
                    "entry_quote_spend": "0",
                    "exit_quote_receive": "0",
                },
            )
            slots = int(row["slot_count"])
            pnl = Decimal(row["realized_pnl"])
            item["position_cycles"] = int(item["position_cycles"]) + 1
            item["slot_trades"] = int(item["slot_trades"]) + slots
            key = {1: "one_slot_cycles", 2: "two_slot_cycles", 3: "three_slot_cycles"}.get(slots)
            if key is None:
                raise RuntimeError(f"unexpected slot_count in portfolio trades: {slots}")
            item[key] = int(item[key]) + 1
            item["wins"] = int(item["wins"]) + int(pnl > 0)
            item["losses"] = int(item["losses"]) + int(pnl <= 0)
            item["realized_pnl"] = str(Decimal(str(item["realized_pnl"])) + pnl)
            item["entry_quote_spend"] = str(
                Decimal(str(item["entry_quote_spend"])) + Decimal(row["entry_quote_spend"])
            )
            item["exit_quote_receive"] = str(
                Decimal(str(item["exit_quote_receive"])) + Decimal(row["exit_quote_receive"])
            )
    return dict(sorted(breakdown.items()))


async def main() -> None:
    base_config = load_project_config(CONFIG_PATH, project_root=PROJECT_ROOT)
    with tempfile.TemporaryDirectory(prefix="hixton-dashboard-e2e-") as temporary:
        root = Path(temporary)
        database_path = root / "data" / "hixton.sqlite3"
        run_output_root = root / "backtests" / "v6" / "runs"
        config = replace(
            base_config,
            database_path=database_path,
            run_output_root=run_output_root,
        )
        _seed_current_usdc_rules(database_path)
        _initialize_paper(database_path)
        supervisor = RuntimeSupervisor(config)
        app = create_app(config, supervisor)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://127.0.0.1:8765",
            timeout=30.0,
        ) as client:
            portfolio = await _run_mode(client, supervisor, "portfolio")
            portfolio["per_symbol_trades"] = _portfolio_trade_breakdown(run_output_root)
            isolated = await _run_mode(client, supervisor, "all")

        evidence = {
            "schema_version": 2,
            "route": "/api/backtests/run",
            "strategy": supervisor.strategy.version,
            "single_runtime_supervisor": "hixton.runtime.continuity_supervisor.RuntimeSupervisor",
            "public_binance_data": True,
            "credentials_used": False,
            "orders_sent": False,
            "portfolio_3x80": portfolio,
            "isolated_10x250": isolated,
        }
        output = PROJECT_ROOT / "evidence" / "dashboard-backtest-e2e.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
