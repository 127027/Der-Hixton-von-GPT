"""Password/session protected localhost routes for credential and preflight setup."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from hixton.config import ProjectConfig
from hixton.live.binance import BinanceCheckError
from hixton.live.credentials import BinanceCredentials, Vault, VaultError, WindowsVault
from hixton.live.preparation import LivePreparation
from hixton.paper.storage import PaperStore
from hixton.runtime.supervisor import RuntimeSupervisor

_COOKIE = "hixton_live_session"


def install_live_routes(
    app: FastAPI,
    config: ProjectConfig,
    supervisor: RuntimeSupervisor,
    local_action: Callable[[Request], bool],
    vault: Vault | None = None,
) -> None:
    service = LivePreparation(
        config.database_path.with_name("live-preparation.sqlite3"),
        vault if vault is not None else WindowsVault(config.database_path),
    )
    app.state.live_preparation = service
    supervisor.trial_runtime = service.connect_runtime(supervisor.strategy)

    def require_local(request: Request) -> None:
        # Unlike legacy read/Paper endpoints, private actions require an exact origin.
        if not local_action(request) or request.headers.get("origin") != str(
            request.base_url
        ).rstrip("/"):
            raise HTTPException(403, "Nur bestätigte Aktionen aus der lokalen Hixton-Oberfläche.")

    def require_session(request: Request) -> None:
        require_local(request)
        if not service.access.authorized(request.cookies.get(_COOKIE)):
            raise HTTPException(
                401, "Geschützten Bereich zuerst mit dem lokalen Passwort entsperren."
            )

    async def payload(request: Request) -> dict[str, Any]:
        # Manual parsing prevents framework validation responses from echoing secret inputs.
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 4096:
                raise HTTPException(413, "Eingabe überschreitet das Größenlimit.")
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError
            return data
        except (ValueError, UnicodeError):
            raise HTTPException(400, "Ungültige Eingabe.") from None
        finally:
            raw[:] = b"\x00" * len(raw)

    def get_status(authenticated: bool) -> dict[str, object]:
        soak_ready = False
        preview: dict[str, object] | None = None
        shared: dict[str, object] | None = None
        try:
            with PaperStore(config.database_path) as store:
                soak_ready = store.load_soak_progress().ready
                settings = store.load_settings()
                preview = {
                    "slot_count": settings.slot_count,
                    "target_notional_usdc": str(settings.target_notional_usdc),
                }
                shared = {**preview, "emergency_stop": settings.emergency_stop}
        except (RuntimeError, sqlite3.DatabaseError, KeyError):
            pass
        result = service.status(
            authenticated=authenticated,
            soak_ready=soak_ready,
            healthy=supervisor.state.snapshot().health == "HEALTHY",
        )
        result["paper_settings_preview"] = preview
        # One existing persistent record, not a second editable Live configuration.
        result["trading_settings"] = shared
        blockers = result["blockers"]
        assert isinstance(blockers, list)
        if shared is None:
            blockers.append("Gemeinsame Handelseinstellungen nicht verfügbar.")
        elif shared["emergency_stop"]:
            blockers.append("Gemeinsame Einstiegspause aktiv; keine neuen Einstiege.")
        return result

    @app.exception_handler(VaultError)
    async def vault_error(_: Request, error: VaultError) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=400)

    @app.exception_handler(BinanceCheckError)
    async def check_error(_: Request, error: BinanceCheckError) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=400)

    @app.get("/api/live/status")
    def live_status(request: Request) -> dict[str, object]:
        return get_status(service.access.authorized(request.cookies.get(_COOKIE)))

    @app.post("/api/live/unlock")
    async def unlock(request: Request) -> JSONResponse:
        require_local(request)
        data = await payload(request)
        password, repeat = data.get("password"), data.get("repeat")
        if not isinstance(password, str) or (repeat is not None and not isinstance(repeat, str)):
            raise HTTPException(400, "Lokales Passwort fehlt oder ist ungültig.")
        try:
            token = await run_in_threadpool(service.access.unlock, password, repeat)
        except VaultError:
            await run_in_threadpool(service.audit, "LOCAL_UNLOCK_FAILED")
            raise
        await run_in_threadpool(service.audit, "LOCAL_UNLOCKED")
        response = JSONResponse({"authenticated": True, "expires_in_seconds": 900})
        # Loopback HTTP only; remote/TLS access is NOT supported by this application.
        response.set_cookie(
            _COOKIE, token, max_age=900, httponly=True, samesite="strict", path="/api/live"
        )
        return response

    @app.post("/api/live/lock")
    async def lock(request: Request) -> JSONResponse:
        require_session(request)
        service.access.logout()
        await run_in_threadpool(service.audit, "LOCAL_LOCKED")
        response = JSONResponse({"authenticated": False})
        response.delete_cookie(_COOKIE, path="/api/live")
        return response

    @app.post("/api/live/credentials")
    async def save_credentials(request: Request) -> dict[str, object]:
        require_session(request)
        data = await payload(request)
        if data.get("confirmation") != "SCHLUESSEL SPEICHERN":
            raise HTTPException(400, "Schlüsselspeicherung ausdrücklich bestätigen.")
        key, secret = data.get("api_key"), data.get("secret_key")
        if not isinstance(key, str) or not isinstance(secret, str):
            raise HTTPException(400, "API-Key und Secret fehlen oder sind ungültig.")
        credentials = BinanceCredentials(key, secret)

        def save() -> dict[str, object]:
            with service.lock:
                service.require_settled_for_key_change()
                service.audit("BINANCE_CREDENTIAL_SAVE_REQUESTED")
                service.credentials.save(credentials)
                service.invalidate_check()
                service.audit("BINANCE_CREDENTIAL_SAVED", {"fingerprint": credentials.fingerprint})
                return service.credentials.status()

        return await run_in_threadpool(save)

    @app.post("/api/live/credentials/delete")
    async def delete_credentials(request: Request) -> dict[str, bool]:
        require_session(request)
        data = await payload(request)
        if data.get("confirmation") != "SCHLUESSEL ENTFERNEN":
            raise HTTPException(400, "Entfernen des gespeicherten Schlüssels bestätigen.")

        def delete() -> None:
            with service.lock:
                service.require_settled_for_key_change()
                service.audit("BINANCE_CREDENTIAL_DELETE_REQUESTED")
                service.credentials.vault.delete("binance-hmac")
                service.invalidate_check()
                service.audit("BINANCE_CREDENTIAL_REMOVED")

        await run_in_threadpool(delete)
        return {"removed": True, "revoked_at_binance": False}

    @app.post("/api/live/check")
    async def check(request: Request) -> dict[str, object]:
        require_session(request)
        return await run_in_threadpool(service.check)

    @app.post("/api/live/enable")
    async def enable(request: Request) -> JSONResponse:
        require_session(request)
        # This endpoint must NEVER toggle RuntimeState.mode merely for a green UI badge.
        result = await run_in_threadpool(get_status, True)
        await run_in_threadpool(service.audit, "LIVE_REQUEST_BLOCKED")
        return JSONResponse(result, status_code=409)

    @app.post("/api/live/disable")
    async def disable(request: Request) -> dict[str, object]:
        require_session(request)
        return await run_in_threadpool(service.stop_entries)

    @app.post("/api/live/trial/start")
    async def start_trial(request: Request) -> JSONResponse:
        require_session(request)
        data = await payload(request)
        if (
            set(data) != {"confirmation", "notional_quote", "quote_asset"}
            or data.get("confirmation") != "TEST 50 USDC"
            or data.get("quote_asset") != "USDC"
            or not isinstance(data.get("notional_quote"), str)
        ):
            raise HTTPException(400, "Genau einen 50-USDC-Test ausdrücklich bestätigen.")
        try:
            amount = Decimal(data["notional_quote"])
            if not amount.is_finite() or amount != Decimal("50"):
                raise ValueError
        except (InvalidOperation, ValueError):
            raise HTTPException(400, "Einmaltest: ausschließlich 50 USDC Kaufbudget.") from None
        # No URL parameter, key presence or green preflight bypasses incomplete implementation.
        # Runtime wiring and balance checks do not release the pre-submit gates.
        result = await run_in_threadpool(get_status, True)
        await run_in_threadpool(service.audit, "TRIAL_REQUEST_BLOCKED")
        return JSONResponse(result, status_code=409)

    @app.post("/api/live/trial/stop")
    async def stop_trial(request: Request) -> dict[str, object]:
        require_session(request)
        return await run_in_threadpool(service.stop_entries)
