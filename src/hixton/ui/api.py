"""FastAPI surface for the localhost-only Hixton dashboard."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfoNotFoundError

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from hixton import __version__
from hixton.backtest.comparison import compare_run
from hixton.backtest.reporting import source_fingerprint
from hixton.config import ProjectConfig
from hixton.constants import SYMBOLS
from hixton.live.credentials import Vault
from hixton.paper.engine import load_paper_portfolio
from hixton.paper.models import MAX_TRADING_SLOTS, PaperSettings
from hixton.paper.storage import PaperStore
from hixton.runtime.state import RuntimeSnapshot
from hixton.runtime.supervisor import RuntimeSupervisor
from hixton.ui.chart import RANGE_LABELS, build_chart_payload
from hixton.ui.lifecycle import VisibleSession
from hixton.ui.live import install_live_routes

STATIC_ROOT = Path(__file__).with_name("static")


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value is not None else None


def _runtime_payload(snapshot: RuntimeSnapshot) -> dict[str, object]:
    return {
        "health": snapshot.health,
        "mode": snapshot.mode,
        "live_state": "LIVE_DISABLED",
        "message": snapshot.message,
        "started_at_utc": _iso(snapshot.started_at_utc),
        "last_sync_utc": _iso(snapshot.last_sync_utc),
        "last_stream_update_utc": _iso(snapshot.last_stream_update_utc),
        "stream_connected": snapshot.stream_connected,
        "feed_mode": snapshot.feed_mode,
        "next_daily_audit_utc": _iso(snapshot.next_daily_audit_utc),
        "last_daily_audit_utc": _iso(snapshot.last_daily_audit_utc),
        "last_error": snapshot.last_error,
        "sync_in_progress": snapshot.sync_in_progress,
        "backtest_status": snapshot.backtest_status,
    }


def _latest_prices(supervisor: RuntimeSupervisor) -> dict[str, Decimal]:
    return {
        symbol: Decimal(
            str(
                live[0].close
                if (live := supervisor.state.live_candle(symbol))
                else points[-1].candle.close
            )
        )
        for symbol, points in supervisor.state.points().items()
        if points
    }


def _paper_payload(
    supervisor: RuntimeSupervisor,
    config: ProjectConfig,
) -> dict[str, object] | None:
    try:
        portfolio = load_paper_portfolio(
            str(config.database_path),
            _latest_prices(supervisor),
            strategy_key=supervisor.strategy.key,
            strategy_version=supervisor.strategy.version,
            starting_cash_usdc=config.paper_starting_cash_usdc,
        )
        with PaperStore(config.database_path) as store:
            soak = store.load_soak_progress()
            session = store.load_strategy_session()
    except (OSError, RuntimeError, sqlite3.DatabaseError):
        return None
    return {
        "cash_usdc": str(portfolio.account.cash_usdc),
        "starting_cash_usdc": str(portfolio.account.starting_cash_usdc),
        "equity_usdc": str(portfolio.equity_usdc),
        "unrealized_pnl_usdc": str(portfolio.unrealized_pnl_usdc),
        "strategy_session": {
            "key": session.strategy_key,
            "version": session.strategy_version,
            "activated_at_utc": _iso(session.activated_at_utc),
            "starting_equity_usdc": str(session.starting_equity_usdc),
            "pnl_usdc": str(portfolio.equity_usdc - session.starting_equity_usdc),
        },
        "high_water_equity_usdc": str(portfolio.account.high_water_equity_usdc),
        "drawdown_pct": str(portfolio.drawdown_pct),
        "daily_loss_paused": portfolio.daily_loss_paused,
        "halted": portfolio.account.halted,
        "halt_reason": portfolio.account.halt_reason,
        "settings": {
            "slot_count": portfolio.settings.slot_count,
            "target_notional_usdc": str(portfolio.settings.target_notional_usdc),
            "emergency_stop": portfolio.settings.emergency_stop,
        },
        "soak": {
            "started_at_utc": _iso(soak.started_at_utc),
            "calendar_days": soak.calendar_days,
            "processed_closed_bars_by_symbol": dict(soak.processed_closed_bars_by_symbol),
            "minimum_processed_closed_bars": soak.minimum_processed_closed_bars,
            "completed_trades": soak.completed_trades,
            "minimum_days": soak.minimum_days,
            "minimum_closed_bars_per_symbol": soak.minimum_closed_bars_per_symbol,
            "minimum_completed_trades": soak.minimum_completed_trades,
            "maximum_days_when_trade_count_low": soak.maximum_days_when_trade_count_low,
            "status": soak.status,
            "ready": soak.ready,
            "blockers": list(soak.blockers),
        },
        "positions": [
            {
                "symbol": position.symbol,
                "quantity": str(position.quantity),
                "average_price": str(position.average_price),
                "cost_basis_usdc": str(position.cost_basis_usdc),
                "entry_time_utc": _iso(position.entry_time_utc),
                "entry_signal_id": position.entry_signal_id,
                "strategy_version": position.strategy_version,
                "slot_count": position.slot_count,
                "market_value_usdc": str(
                    position.quantity
                    * _latest_prices(supervisor).get(position.symbol, position.average_price)
                ),
            }
            for position in portfolio.positions
        ],
    }


def _market_payloads(
    supervisor: RuntimeSupervisor,
    config: ProjectConfig,
) -> list[dict[str, object]]:
    points_by_symbol = supervisor.state.points()
    quality = supervisor.state.quality()
    paper = _paper_payload(supervisor, config)
    raw_positions = paper.get("positions", []) if paper is not None else []
    position_items = raw_positions if isinstance(raw_positions, list) else []
    positions = {
        str(position["symbol"]): position
        for position in position_items
        if isinstance(position, dict) and "symbol" in position
    }
    payloads: list[dict[str, object]] = []
    for symbol in SYMBOLS:
        points = points_by_symbol.get(symbol, ())
        point = points[-1] if points else None
        last_signal = None
        if points:
            for candidate in reversed(points):
                if candidate.flip_up or candidate.flip_down:
                    last_signal = {
                        "action": "ENTER_LONG" if candidate.flip_up else "EXIT_LONG",
                        "time_utc": _iso(candidate.candle.close_time_utc),
                    }
                    break
        report = quality.get(symbol)
        live = supervisor.state.live_candle(symbol)
        entry_status = (
            "POSITION_OPEN"
            if symbol in positions
            else "WAITING_FOR_NEW_FLIP"
            if last_signal
            else "NO_SIGNAL_YET"
        )
        payloads.append(
            {
                "symbol": symbol,
                "display_symbol": symbol.removesuffix("USDC") + "/USDC",
                "strategy_profile": {
                    "parameters": asdict(supervisor.strategy.parameters_for(symbol)),
                    "trade_policy": asdict(supervisor.strategy.policy_for(symbol)),
                },
                "available": point is not None,
                "price": live[0].close if live else point.candle.close if point else None,
                "price_time_utc": _iso(live[1])
                if live
                else _iso(point.candle.close_time_utc)
                if point
                else None,
                "price_provisional": bool(live),
                "entry_status": entry_status,
                "trend": point.trend.value if point else "UNINITIALIZED",
                "last_signal": last_signal,
                "position": positions.get(symbol),
                "position_state": "LONG" if symbol in positions else "FLAT",
                "data": {
                    "candle_count": report.candle_count if report else 0,
                    "first_open_utc": _iso(report.first_open_time_utc) if report else None,
                    "last_open_utc": _iso(report.last_open_time_utc) if report else None,
                    "gap_count": report.gap_count if report else None,
                    "valid": report.valid if report else False,
                },
            }
        )
    return payloads


def _list_backtests(
    output_root: Path,
    *,
    mode: str | None = None,
    symbol: str | None = None,
) -> list[dict[str, object]]:
    if not output_root.exists():
        return []
    entries: list[dict[str, object]] = []
    for directory in output_root.iterdir():
        if not directory.is_dir():
            continue
        manifest_path = directory / "manifest.json"
        metrics_path = directory / "metrics.json"
        if not manifest_path.exists() or not metrics_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(manifest, dict) or not isinstance(metrics, dict):
            continue
        primary = metrics.get("current", metrics.get("baseline", {}))
        if not isinstance(primary, dict):
            continue
        run_mode = manifest.get("run_mode") or (
            "portfolio" if "portfolio" in primary else "batch" if "batch" in primary else "single"
        )
        if mode is not None and run_mode != ("batch" if mode == "all" else mode):
            continue
        if symbol is not None and set(primary.get("per_symbol", {})) != {symbol}:
            continue
        # Old reports are immutable USDT evidence, not USDC merely because the
        # active bot migrated. Infer only from actual symbol metadata, never UI defaults.
        data = manifest.get("data", {})
        hashes = data.get("snapshot_sha256_by_symbol", {}) if isinstance(data, dict) else {}
        names = set(hashes) if isinstance(hashes, dict) else set()
        singles = primary.get("per_symbol", {})
        if isinstance(singles, dict):
            names.update(singles)
        detected = {q for q in ("USDT", "USDC") if any(str(n).endswith(q) for n in names)}
        declared = manifest.get("quote_asset")
        quote = (
            declared
            if declared in {"USDT", "USDC"}
            else (next(iter(detected)) if len(detected) == 1 else "UNKNOWN")
        )
        if detected and detected != {quote}:
            quote = "UNKNOWN"
        entries.append({"manifest": {**manifest, "quote_asset": quote}, "metrics": metrics})

    def created_at(entry: dict[str, object]) -> datetime:
        manifest = entry["manifest"]
        assert isinstance(manifest, dict)
        try:
            moment = datetime.fromisoformat(str(manifest.get("created_at_utc", "")))
            return moment.astimezone(UTC) if moment.tzinfo else datetime.min.replace(tzinfo=UTC)
        except ValueError:
            return datetime.min.replace(tzinfo=UTC)

    # Copying/reproducing folders must not make an older run look like the newest.
    # Apply the 25-run display cap only AFTER filtering by selected test model.
    return sorted(entries, key=created_at, reverse=True)[:25]


def _origin_is_local(request: Request) -> bool:
    origin = request.headers.get("origin")
    action_header = request.headers.get("x-hixton-action")
    try:
        parsed = urlsplit(origin) if origin else None
        local_origin = parsed is None or (
            parsed.scheme == "http"
            and parsed.hostname in {"127.0.0.1", "localhost"}
            and parsed.port == request.url.port
            and not parsed.username
            and not parsed.password
            and not parsed.path
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        local_origin = False
    return local_origin and action_header == "local-ui-v1"


def create_app(
    config: ProjectConfig,
    supervisor: RuntimeSupervisor,
    *,
    live_vault: Vault | None = None,
    session: VisibleSession | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if session is None:
            supervisor.start()
        else:
            session.start(supervisor)
        try:
            yield
        finally:
            if session is not None:
                await session.close()
            await supervisor.stop()

    app = FastAPI(
        title="Der Hixton",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; font-src 'self'; frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    install_live_routes(app, config, supervisor, _origin_is_local, live_vault)
    if session is not None:
        session.install(app)

    app.mount("/assets", StaticFiles(directory=STATIC_ROOT / "assets"), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_ROOT / "index.html", headers={"Cache-Control": "no-store"})

    @app.get("/api/status")
    def status() -> dict[str, object]:
        runtime = _runtime_payload(supervisor.state.snapshot())
        runtime["live_state"] = app.state.live_preparation.execution_state()
        return {
            "application": "Der Hixton Trading Bot",
            "application_version": __version__,
            "strategy_version": supervisor.strategy.version,
            "strategy_key": supervisor.strategy.key,
            "strategy_profiles": supervisor.strategy.profiles_payload(),
            "runtime": runtime,
            "paper": _paper_payload(supervisor, config),
            "trading_limits": {
                "max_slots": MAX_TRADING_SLOTS,
            },
            "server_time_utc": _iso(datetime.now(UTC)),
            "ui_timezone": config.ui_timezone,
        }

    @app.get("/api/markets")
    def markets() -> dict[str, object]:
        return {"markets": _market_payloads(supervisor, config)}

    @app.get("/api/chart")
    def chart(
        symbol: str = Query(...),
        range_key: str = Query("1m", alias="range"),
        timezone: str = Query("Europe/Berlin"),
    ) -> dict[str, object]:
        normalized = symbol.replace("/", "").upper()
        if normalized not in SYMBOLS:
            raise HTTPException(status_code=400, detail="Unbekanntes DMS-Symbol")
        if range_key not in RANGE_LABELS:
            raise HTTPException(status_code=400, detail="Unbekannter Chartzeitraum")
        points = supervisor.state.points().get(normalized, ())
        live = supervisor.state.live_candle(normalized)
        try:
            with PaperStore(config.database_path) as store:
                events = store.load_events(symbol=normalized, limit=5_000)
        except (OSError, sqlite3.Error):
            events = ()
        try:
            return build_chart_payload(
                symbol=normalized,
                points=points,
                range_key=range_key,
                timezone_name=timezone,
                now=datetime.now(UTC),
                paper_events=events,
                trade_policy=supervisor.strategy.policy_for(normalized)
                if supervisor.strategy.coin_profiles
                else None,
                live_candle=live[0] if live else None,
            )
        except (ValueError, ZoneInfoNotFoundError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/paper/events")
    def paper_events(symbol: str | None = None, limit: int = 250) -> dict[str, object]:
        with PaperStore(config.database_path) as store:
            store.initialize(
                strategy_key=supervisor.strategy.key,
                strategy_version=supervisor.strategy.version,
                starting_cash_usdc=config.paper_starting_cash_usdc,
            )
            store.require_strategy(supervisor.strategy.key, supervisor.strategy.version)
            events = store.load_events(symbol=symbol, limit=limit)
        return {
            "events": [
                {
                    **asdict(event),
                    "status": event.status.value,
                    "occurred_at_utc": _iso(event.occurred_at_utc),
                }
                for event in events
            ]
        }

    @app.post("/api/trading/settings")
    @app.post("/api/paper/settings", include_in_schema=False)
    async def paper_settings(request: Request) -> dict[str, object]:
        if not _origin_is_local(request):
            raise HTTPException(status_code=403, detail="Nur lokale UI-Aufrufe sind erlaubt")
        payload: Any = await request.json()
        if not isinstance(payload, dict) or payload.get("confirmation") != "ANWENDEN":
            raise HTTPException(status_code=400, detail="Bestaetigung ANWENDEN fehlt")
        try:
            if type(payload.get("slot_count")) is not int:
                raise ValueError("Slots müssen eine ganze Zahl sein")
            if type(payload.get("emergency_stop", False)) is not bool:
                raise ValueError("Not-Aus muss wahr oder falsch sein")
            settings = PaperSettings(
                slot_count=payload["slot_count"],
                target_notional_usdc=Decimal(str(payload["target_notional_usdc"])),
                emergency_stop=payload.get("emergency_stop", False),
            )
        except (KeyError, TypeError, ValueError, InvalidOperation):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Ungültige Handelseinstellungen: 1-{MAX_TRADING_SLOTS} Slots, "
                    "positives endliches Notional."
                ),
            ) from None
        with PaperStore(config.database_path) as store:
            store.initialize(
                strategy_key=supervisor.strategy.key,
                strategy_version=supervisor.strategy.version,
                starting_cash_usdc=config.paper_starting_cash_usdc,
            )
            store.require_strategy(supervisor.strategy.key, supervisor.strategy.version)
            store.save_settings(settings)
        if settings.emergency_stop:
            # Entry-only safety action; never liquidate or re-enable on unpause.
            app.state.live_preparation.stop_entries()
        return {"saved": True, "settings": asdict(settings)}

    @app.post("/api/data/sync")
    async def data_sync(request: Request) -> dict[str, object]:
        if not _origin_is_local(request):
            raise HTTPException(status_code=403, detail="Nur lokale UI-Aufrufe sind erlaubt")
        await supervisor.request_sync()
        return {"started": True, "status": _runtime_payload(supervisor.state.snapshot())}

    @app.get("/api/data-quality")
    def data_quality() -> dict[str, object]:
        reports = supervisor.state.quality()
        return {
            "reports": [
                {
                    "symbol": symbol,
                    "valid": report.valid,
                    "candle_count": report.candle_count,
                    "expected_count": report.expected_count,
                    "first_open_utc": _iso(report.first_open_time_utc),
                    "last_open_utc": _iso(report.last_open_time_utc),
                    "gap_count": report.gap_count,
                    "issues": [asdict(issue) for issue in report.issues[:20]],
                }
                for symbol, report in reports.items()
            ]
        }

    @app.get("/api/backtests")
    def backtests(
        strategy: str = Query(default=config.strategy_key),
        mode: str | None = None,
        symbol: str | None = None,
    ) -> dict[str, object]:
        if mode not in {None, "portfolio", "all", "single"}:
            raise HTTPException(status_code=400, detail="Unbekannte Backtestart")
        normalized = symbol.replace("/", "").upper() if symbol else None
        if mode == "single" and normalized not in SYMBOLS:
            raise HTTPException(status_code=400, detail="Einzeltest benoetigt ein DMS-Symbol")
        if normalized is not None and mode != "single":
            raise HTTPException(status_code=400, detail="Coinfilter gilt nur fuer Einzeltests")
        if strategy.lower() != config.strategy_key:
            raise HTTPException(status_code=400, detail="Nur die aktuell aktive V6 ist verfügbar")
        definition = supervisor.strategy
        output_root = config.run_output_root.parents[1] / definition.backtest_version / "runs"
        try:
            with PaperStore(config.database_path) as store:
                settings = store.load_settings()
        except (OSError, sqlite3.Error, RuntimeError):
            settings = None
        runs = _list_backtests(output_root, mode=mode, symbol=normalized)
        disk_changed = source_fingerprint() != supervisor.execution_source_sha256
        for run in runs:
            manifest, metrics = run["manifest"], run["metrics"]
            assert isinstance(manifest, dict) and isinstance(metrics, dict)
            comparison = compare_run(
                manifest,
                metrics,
                active=supervisor.strategy,
                settings=settings,
                starting_cash=config.paper_starting_cash_usdc,
                source_hash=supervisor.execution_source_sha256,
            )
            if disk_changed:
                comparison["status"] = "UNVERIFIED"
                reasons = comparison["reasons"]
                assert isinstance(reasons, list)
                reasons.append("Dateien seit Botstart geändert: Neustart nötig")
            run["comparison"] = comparison
        return {
            "strategy": {
                "key": definition.key,
                "version": definition.version,
                "paper_approved": definition.paper_approved,
            },
            "runs": runs,
            "status": supervisor.state.snapshot().backtest_status,
        }

    @app.get("/api/logs")
    def logs(limit: int = 250) -> dict[str, object]:
        try:
            entries = supervisor.state.logs(limit=limit)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {
            "logs": [
                {
                    **asdict(entry),
                    "time_utc": _iso(entry.time_utc),
                }
                for entry in entries
            ]
        }

    @app.post("/api/backtests/run")
    async def run_backtest(request: Request) -> dict[str, object]:
        if not _origin_is_local(request):
            raise HTTPException(status_code=403, detail="Nur lokale UI-Aufrufe sind erlaubt")
        payload: Any = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Ungueltige Backtest-Anfrage")
        requested_strategy = str(payload.get("strategy", config.strategy_key)).lower()
        if requested_strategy != config.strategy_key:
            raise HTTPException(status_code=400, detail="Nur die aktuell aktive V6 ist verfügbar")
        try:
            started = supervisor.start_backtest(
                mode=str(payload.get("mode", "")),
                symbol=str(payload.get("symbol")) if payload.get("symbol") else None,
                strategy_key=config.strategy_key,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        if not started:
            raise HTTPException(status_code=409, detail="Ein Backtest laeuft bereits")
        return {"started": True, "status": "RUNNING"}

    return app
