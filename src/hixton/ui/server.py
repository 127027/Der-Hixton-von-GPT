"""Local Uvicorn runner for the single Hixton process."""

from __future__ import annotations

import os
import secrets
import threading
import webbrowser

import uvicorn

from hixton.config import ProjectConfig
from hixton.runtime.supervisor import RuntimeSupervisor
from hixton.ui.api import create_app
from hixton.ui.instance import installation_id, remove_control, reserve_instance, write_control
from hixton.ui.lifecycle import ConsoleParent, VisibleSession


def run_local_dashboard(config: ProjectConfig, *, open_browser: bool = True) -> int:
    if config.ui_bind not in {"127.0.0.1", "localhost"}:
        raise ValueError("UI may bind only to localhost")
    parent = ConsoleParent()
    listener = None
    session = None
    timer = None
    shutdown_timer: threading.Timer | None = None
    try:
        if not parent.alive():
            raise RuntimeError(
                "Start nur in einem sichtbaren Bot-Terminal erlaubt. Startbot.bat öffnen."
            )
        listener = reserve_instance(config.database_path, config.ui_port)
        supervisor = RuntimeSupervisor(config)

        def request_exit() -> None:
            nonlocal shutdown_timer
            server.should_exit = True
            if shutdown_timer is None:
                # A cancelled to_thread download can outlive asyncio shutdown.
                # Never leave this process orphaned; SQLite rolls back unfinished
                # transactions. No other process is terminated by this deadline.
                def final_exit() -> None:
                    print("[Hixton] Stoppfrist erreicht; eigener Prozess wird beendet.", flush=True)
                    os._exit(0)

                shutdown_timer = threading.Timer(15, final_exit)
                shutdown_timer.daemon = True
                shutdown_timer.start()

        session = VisibleSession(
            installation=installation_id(config.database_path),
            token=secrets.token_hex(32),
            terminal_alive=parent.alive,
            request_exit=request_exit,
        )
        app = create_app(config, supervisor, session=session)
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=config.ui_port,
                log_level="info",
                access_log=False,
                ws_ping_interval=10,
                ws_ping_timeout=5,
                timeout_graceful_shutdown=10,
            )
        )
        write_control(config.database_path, session)
        print(
            "[Hixton] Terminal ODER letzte Bot-Seite schließen = Bot AUS (5 s Seiten-Schonfrist).",
            flush=True,
        )
        print(
            "[Hixton] Offene Positionen bleiben bestehen. Kein Hintergrundbetrieb.",
            flush=True,
        )
        if open_browser:
            timer = threading.Timer(
                1.25, lambda: webbrowser.open(f"http://127.0.0.1:{config.ui_port}/")
            )
            timer.daemon = True
            timer.start()
        server.run(sockets=[listener])
    finally:
        if shutdown_timer is not None:
            shutdown_timer.cancel()
        if timer is not None:
            timer.cancel()
        if session is not None:
            remove_control(config.database_path, session.instance)
        if listener is not None:
            listener.close()
        parent.close()
    print("[Hixton] Bot beendet. Keine weitere Überwachung/Handelsausführung.", flush=True)
    return 0
