"""Contact setup shares the existing exact-origin, local-password session."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from hixton.notifications.service import NotificationService
from hixton.notifications.telegram import DeliveryError


def install_notification_routes(
    app: FastAPI,
    service: NotificationService,
    require_session: Callable[[Request], None],
    authorized: Callable[[Request], bool],
    payload: Callable[[Request], Awaitable[dict[str, Any]]],
) -> None:
    @app.get("/api/live/notifications")
    def status(request: Request) -> dict[str, object]:
        return service.status(authorized(request))

    @app.post("/api/live/notifications")
    async def save(request: Request) -> dict[str, object]:
        require_session(request)
        data = await payload(request)
        try:
            return await run_in_threadpool(service.save, data)
        except ValueError as error:
            raise HTTPException(400, str(error)) from None

    @app.post("/api/live/notifications/discover")
    async def discover(request: Request) -> dict[str, object]:
        require_session(request)
        data = await payload(request)
        token = data.get("secret", "")
        if not isinstance(token, str):
            raise HTTPException(400, "Ungültiger Telegram-Token.")
        try:
            chats = await run_in_threadpool(service.discover, token)
            return {"chats": chats}
        except ValueError as error:
            raise HTTPException(400, str(error)) from None
        except DeliveryError as error:
            raise HTTPException(502, str(error)) from None

    @app.post("/api/live/notifications/test")
    async def test(request: Request) -> dict[str, object]:
        require_session(request)
        try:
            return await run_in_threadpool(service.test)
        except ValueError as error:
            raise HTTPException(400, str(error)) from None
        except DeliveryError as error:
            raise HTTPException(502, str(error)) from None

    @app.post("/api/live/notifications/delete")
    async def delete(request: Request) -> dict[str, object]:
        require_session(request)
        return await run_in_threadpool(service.delete)
