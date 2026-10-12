"""Process-scoped idle sleep requests; no changes to the Windows power plan."""

from __future__ import annotations

import ctypes
import os
from typing import Protocol

from hixton.ui.lifecycle import _windows_library


class PowerBackend(Protocol):
    def create(self) -> int: ...
    def set(self, handle: int, kind: int) -> bool: ...
    def clear(self, handle: int, kind: int) -> None: ...
    def close(self, handle: int) -> None: ...


class _Detailed(ctypes.Structure):
    _fields_ = [
        ("module", ctypes.c_void_p),
        ("id", ctypes.c_uint32),
        ("count", ctypes.c_uint32),
        ("strings", ctypes.c_void_p),
    ]


class _Reason(ctypes.Union):
    _fields_ = [("detailed", _Detailed), ("simple", ctypes.c_wchar_p)]


class _Context(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("flags", ctypes.c_uint32), ("reason", _Reason)]


class WindowsPowerBackend:
    def __init__(self) -> None:
        self.dll = _windows_library("kernel32")
        self.dll.PowerCreateRequest.argtypes = [ctypes.POINTER(_Context)]
        self.dll.PowerCreateRequest.restype = ctypes.c_void_p
        for method in (self.dll.PowerSetRequest, self.dll.PowerClearRequest):
            method.argtypes = [ctypes.c_void_p, ctypes.c_int]
            method.restype = ctypes.c_int
        self.dll.CloseHandle.argtypes = [ctypes.c_void_p]
        self.dll.CloseHandle.restype = ctypes.c_int

    def create(self) -> int:
        context = _Context(
            0, 1, _Reason(simple="Hixton überwacht sichtbare Bot-Sitzung und Positionen")
        )
        handle = self.dll.PowerCreateRequest(ctypes.byref(context))
        if not handle or handle == ctypes.c_void_p(-1).value:
            raise OSError("Windows konnte Leerlauf-Schutz nicht anlegen")
        return int(handle)

    def set(self, handle: int, kind: int) -> bool:
        return bool(self.dll.PowerSetRequest(handle, kind))

    def clear(self, handle: int, kind: int) -> None:
        self.dll.PowerClearRequest(handle, kind)

    def close(self, handle: int) -> None:
        self.dll.CloseHandle(handle)


class SleepGuard:
    def __init__(self, backend: PowerBackend | None = None) -> None:
        self.backend = (
            backend if backend is not None else (WindowsPowerBackend() if os.name == "nt" else None)
        )
        self.handle: int | None = None
        self.requests: list[int] = []
        self.active = False

    def start(self) -> bool:
        if self.handle is not None:
            return self.active
        if self.backend is None:
            return False
        try:
            self.handle = self.backend.create()
            for kind in (1, 3):  # SystemRequired and ExecutionRequired; display may turn off.
                if not self.backend.set(self.handle, kind):
                    raise OSError("Windows konnte Leerlauf-Schutz nicht aktivieren")
                self.requests.append(kind)
            self.active = True
        except OSError:
            self.close()
        return self.active

    def close(self) -> None:
        if self.backend is not None and self.handle is not None:
            try:
                for kind in reversed(self.requests):
                    self.backend.clear(self.handle, kind)
            finally:
                self.backend.close(self.handle)
        self.requests.clear()
        self.handle = None
        self.active = False
