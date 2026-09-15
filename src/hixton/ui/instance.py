"""Exclusive port reservation and authenticated replacement of this installation only."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import secrets
import socket
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from hixton.ui.lifecycle import PROTOCOL, VisibleSession


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None  # Never forward the local replacement token to another destination.


class PreviousProcess:
    def __init__(self, pid: int) -> None:
        if type(pid) is not int or pid <= 0 or pid == os.getpid():
            raise ValueError("Ungültige Vorgängerinstanz")
        self.pid = pid
        self.handle = None
        self.kernel = None
        if os.name == "nt":
            self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            self.kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_uint32]
            self.kernel.OpenProcess.restype = ctypes.c_void_p
            self.kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            self.kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            self.handle = self.kernel.OpenProcess(0x00100000, False, pid)
            if not self.handle:
                raise OSError("Vorgängerprozess nicht sicher identifizierbar")

    def exited(self) -> bool:
        if self.kernel is not None:
            return bool(self.kernel.WaitForSingleObject(self.handle, 0) == 0)
        try:
            os.kill(self.pid, 0)
            return False
        except ProcessLookupError:
            return True

    def close(self) -> None:
        if self.kernel is not None and self.handle is not None:
            self.kernel.CloseHandle(self.handle)


def installation_id(database: Path) -> str:
    return hashlib.sha256(str(database.resolve()).casefold().encode()).hexdigest()


def bind_local(port: int) -> socket.socket:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(("127.0.0.1", port))
        listener.listen(128)
        return listener
    except OSError:
        listener.close()
        raise


def reserve_instance(database: Path, port: int) -> socket.socket:
    try:
        return bind_local(port)
    except OSError as error:
        initial_error = error
    control = database.parent / "runtime-session.json"
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    url = f"http://127.0.0.1:{port}"
    previous = None
    try:
        recorded = json.loads(control.read_text(encoding="utf-8"))
        with opener.open(url + "/api/session/info", timeout=3) as response:
            active = json.loads(response.read(16_384))
        if not (
            isinstance(active, dict)
            and isinstance(recorded, dict)
            and isinstance(recorded.get("token"), str)
            and len(recorded["token"]) == 64
            and active.get("protocol") == PROTOCOL
            and active.get("installation") == installation_id(database)
            and active.get("instance") == recorded["instance"]
            and recorded.get("installation") == active["installation"]
        ):
            raise ValueError("Andere Installation oder veralteter Instanznachweis")
        previous = PreviousProcess(active["pid"])
        request = Request(
            url + "/api/session/shutdown",
            method="POST",
            data=json.dumps({"instance": active["instance"]}).encode(),
            headers={"Content-Type": "application/json", "X-Hixton-Session": recorded["token"]},
        )
        with opener.open(request, timeout=3) as response:
            if json.loads(response.read(4096)).get("stopping") is not True:
                raise ValueError("Beenden nicht bestätigt")
    except (OSError, URLError, ValueError, KeyError, TypeError) as error:
        if previous is not None:
            previous.close()
        raise RuntimeError(
            f"Port {port} ist belegt, aber keine sicher ablösbare Hixton-Instanz erkannt. "
            "Alten Bot in seinem Terminal schließen; fremde Programme werden nicht beendet."
        ) from error
    print("[Hixton] Vorherige Instanz wird geordnet beendet ...", flush=True)
    deadline = time.monotonic() + 60
    try:
        while time.monotonic() < deadline:
            if previous.exited():
                try:
                    return bind_local(port)
                except OSError:
                    pass
            time.sleep(0.2)
    finally:
        previous.close()
    raise RuntimeError(
        "Vorherige Instanz noch nicht beendet; kein paralleler Bot gestartet."
    ) from initial_error


def write_control(database: Path, session: VisibleSession) -> None:
    database.parent.mkdir(parents=True, exist_ok=True)
    target = database.parent / "runtime-session.json"
    temporary = target.with_suffix("." + secrets.token_hex(8) + ".tmp")
    try:
        temporary.write_text(
            json.dumps({**session.info(), "token": session.token}), encoding="utf-8"
        )
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def remove_control(database: Path, instance: str) -> None:
    target = database.parent / "runtime-session.json"
    try:
        if json.loads(target.read_text(encoding="utf-8")).get("instance") == instance:
            target.unlink()
    except (OSError, ValueError):
        pass  # Never remove a newer owner's control file.
