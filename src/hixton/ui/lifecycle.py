"""Visible-session lifetime: no trading before a UI, no hidden continuation after it."""

from __future__ import annotations

import asyncio
import ctypes
import hmac
import os
import secrets
import sys
import time
from collections.abc import Callable
from contextlib import suppress
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect

from hixton import __version__
from hixton.runtime.supervisor import RuntimeSupervisor

PROTOCOL = "hixton-visible-session-v1"


def console_present() -> bool:
    """Minimized consoles count as open; detached/hidden Windows launches do not."""
    if os.name != "nt":
        return sys.stdin.isatty()
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    user = ctypes.WinDLL("user32", use_last_error=True)
    kernel.GetConsoleWindow.restype = ctypes.c_void_p
    user.IsWindow.argtypes = [ctypes.c_void_p]
    user.IsWindowVisible.argtypes = [ctypes.c_void_p]
    window = kernel.GetConsoleWindow()
    if not window or not user.IsWindow(window):
        return False
    # Windows Terminal uses an invisible pseudoconsole window. Its shell lifetime
    # is checked separately below; a classic cmd console must actually be visible.
    return bool(user.IsWindowVisible(window) or os.environ.get("WT_SESSION"))


class ConsoleParent:
    """Pin the parent process handle (PID reuse cannot keep an orphan alive)."""

    def __init__(self) -> None:
        self.handle: Any = None
        self.kernel: Any = None
        self.shell_handles: list[Any] = []
        if os.name == "nt":
            self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            self.kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_uint32]
            self.kernel.OpenProcess.restype = ctypes.c_void_p
            self.kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            self.kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            self.handle = self.kernel.OpenProcess(0x00100000, False, os.getppid())
            if not self.handle:
                raise RuntimeError("Bot-Terminal kann nicht sicher überwacht werden.")
            # A venv launcher can be the direct parent. Also pin the actual attached
            # cmd/PowerShell shell, so killing that shell cannot orphan its children.
            ids = (ctypes.c_uint32 * 64)()
            count = self.kernel.GetConsoleProcessList(ids, 64)
            if count > 64:
                self.close()
                raise RuntimeError("Unübersichtlicher Konsolenbaum; kein sicherer Botstart")
            self.kernel.QueryFullProcessImageNameW.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint32,
                ctypes.c_wchar_p,
                ctypes.POINTER(ctypes.c_uint32),
            ]
            for pid in ids[:count]:
                if pid == os.getpid():
                    continue
                candidate = self.kernel.OpenProcess(0x00101000, False, pid)
                if not candidate:
                    continue
                path = ctypes.create_unicode_buffer(32768)
                size = ctypes.c_uint32(len(path))
                ok = self.kernel.QueryFullProcessImageNameW(candidate, 0, path, ctypes.byref(size))
                if ok and os.path.basename(path.value).lower() in {
                    "cmd.exe",
                    "powershell.exe",
                    "pwsh.exe",
                }:
                    self.shell_handles.append(candidate)
                else:
                    self.kernel.CloseHandle(candidate)

    def alive(self) -> bool:
        return (
            console_present()
            and (self.handle is None or self.kernel.WaitForSingleObject(self.handle, 0) == 258)
            and all(self.kernel.WaitForSingleObject(h, 0) == 258 for h in self.shell_handles)
        )

    def close(self) -> None:
        for handle in self.shell_handles:
            self.kernel.CloseHandle(handle)
        self.shell_handles.clear()
        if self.handle is not None:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


class BrowserLease:
    def __init__(self, *, now: float, startup_seconds: float = 60, grace_seconds: float = 5):
        self.start = now
        self.startup_seconds = startup_seconds
        self.grace_seconds = grace_seconds
        self.clients: set[str] = set()
        self.last_disconnect: float | None = None

    def join(self, client: str) -> None:
        self.clients.add(client)
        self.last_disconnect = None

    def leave(self, client: str, *, now: float) -> None:
        if client not in self.clients:
            return
        self.clients.remove(client)
        if not self.clients:
            self.last_disconnect = now

    def stop_reason(self, *, now: float) -> str | None:
        if self.clients:
            return None
        if self.last_disconnect is not None:
            if now - self.last_disconnect >= self.grace_seconds:
                return "Letzte Bot-Oberfläche geschlossen oder Verbindung verloren"
        elif now - self.start >= self.startup_seconds:
            return "Keine Bot-Oberfläche innerhalb von 60 Sekunden geöffnet"
        return None


class VisibleSession:
    def __init__(
        self,
        *,
        installation: str,
        token: str,
        terminal_alive: Callable[[], bool],
        request_exit: Callable[[], None],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.installation = installation
        self.token = token
        self.instance = secrets.token_hex(16)
        self.terminal_alive = terminal_alive
        self.request_exit = request_exit
        self.clock = clock
        self.lease = BrowserLease(now=clock())
        self.stopping = False
        self.started_trading = False
        self.supervisor: RuntimeSupervisor | None = None
        self.task: asyncio.Task[None] | None = None

    def info(self) -> dict[str, object]:
        return {
            "protocol": PROTOCOL,
            "instance": self.instance,
            "installation": self.installation,
            "pid": os.getpid(),
            "application_version": __version__,
            "stopping": self.stopping,
            "ui_connections": len(self.lease.clients),
            "trading_started": self.started_trading,
        }

    def start(self, supervisor: RuntimeSupervisor) -> None:
        self.supervisor = supervisor
        supervisor.state.set_status(
            health="STARTING", message="Wartet auf sichtbare Bot-Oberfläche; Handel noch aus"
        )
        self.task = asyncio.create_task(self._watch(), name="visible-session-watchdog")

    def stop(self, reason: str) -> None:
        if self.stopping:
            return
        self.stopping = True
        print(f"[Hixton] STOPP: {reason}. Keine automatische Liquidation.", flush=True)
        if self.supervisor is not None:
            # Block subsequent cycles immediately, before Uvicorn finishes its shutdown.
            self.supervisor._stop.set()
        self.request_exit()

    async def close(self) -> None:
        if self.task is not None:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task

    async def _watch(self) -> None:
        while not self.stopping:
            try:
                reason = (
                    "Bot-Terminal geschlossen"
                    if not self.terminal_alive()
                    else self.lease.stop_reason(now=self.clock())
                )
            except Exception:
                self.stop("Sichtbarkeitsüberwachung fehlgeschlagen")
                return
            if reason:
                self.stop(reason)
                return
            await asyncio.sleep(0.5)

    def install(self, app: FastAPI) -> None:
        @app.get("/api/session/info")
        def info() -> dict[str, object]:
            return self.info()

        @app.post("/api/session/shutdown")
        async def shutdown(request: Request) -> dict[str, bool]:
            # Launcher authentication is installation-local, never the Binance key.
            supplied = request.headers.get("X-Hixton-Session", "")
            if not hmac.compare_digest(supplied, self.token):
                raise HTTPException(403, "Fremde Instanz darf nicht beendet werden")
            body = await request.json()
            if not isinstance(body, dict) or body.get("instance") != self.instance:
                raise HTTPException(409, "Instanz wurde zwischenzeitlich gewechselt")
            self.stop("Neuer Start löst diese Bot-Instanz ab")
            return {"stopping": True}

        @app.websocket("/api/session/presence")
        async def presence(websocket: WebSocket) -> None:
            origin = websocket.headers.get("origin", "")
            if (
                origin
                not in {
                    f"http://127.0.0.1:{websocket.url.port}",
                    f"http://localhost:{websocket.url.port}",
                }
                or self.stopping
            ):
                await websocket.close(code=1008)
                return
            await websocket.accept()
            if self.stopping:
                await websocket.close(code=1001)
                return
            client = secrets.token_hex(16)
            self.lease.join(client)
            try:
                if not self.started_trading and self.terminal_alive() and self.supervisor:
                    self.started_trading = True
                    self.supervisor.start()
                await websocket.send_json(self.info())
                while not self.stopping:
                    if await websocket.receive_text() == "stop":
                        self.stop("Benutzer hat Bot beenden gewählt")
            except WebSocketDisconnect:
                pass
            finally:
                self.lease.leave(client, now=self.clock())
