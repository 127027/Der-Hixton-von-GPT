"""User-scoped Windows Credential Manager; no file/env/plaintext fallback."""

from __future__ import annotations

import ctypes
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from collections import deque
from ctypes import wintypes
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, Protocol


class VaultError(RuntimeError):
    """Sanitized error safe to display; never include credential payloads."""


class Vault(Protocol):
    def read(self, name: str) -> str | None: ...
    def write(self, name: str, value: str) -> None: ...
    def delete(self, name: str) -> None: ...


class _Credential(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


class WindowsVault:
    """Only exact app targets, never enumerate the user's stored credentials."""

    def __init__(self, installation: Path) -> None:
        # The default quote migration must not move existing passwords/API keys
        # to a new namespace. No secret read/copy/reset is needed for this alias.
        if installation.name == "hixton-usdc.sqlite3":
            installation = installation.with_name("hixton.sqlite3")
        digest = hashlib.sha256(str(installation.resolve()).casefold().encode()).hexdigest()[:24]
        self.prefix = f"DerHixton/{digest}/"

    def _target(self, name: str) -> str:
        if name not in {"binance-hmac", "ui-password"}:
            raise VaultError("Unbekannter Hixton-Schlüsselspeicher.")
        return self.prefix + name

    @staticmethod
    def _library() -> Any:
        if os.name != "nt":
            raise VaultError("Sichere Schlüsselablage erfordert Windows. Kein Klartext-Fallback.")
        dll = ctypes.WinDLL("advapi32", use_last_error=True)
        pointer = ctypes.POINTER(_Credential)
        dll.CredReadW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(pointer),
        ]
        dll.CredReadW.restype = wintypes.BOOL
        dll.CredWriteW.argtypes = [pointer, wintypes.DWORD]
        dll.CredWriteW.restype = wintypes.BOOL
        dll.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        dll.CredDeleteW.restype = wintypes.BOOL
        dll.CredFree.argtypes = [ctypes.c_void_p]
        dll.CredFree.restype = None
        return dll

    def read(self, name: str) -> str | None:
        target = self._target(name)
        dll = self._library()
        pointer = ctypes.POINTER(_Credential)()
        if not dll.CredReadW(target, 1, 0, ctypes.byref(pointer)):
            if ctypes.get_last_error() == 1168:  # ERROR_NOT_FOUND, not an empty/failed vault
                return None
            raise VaultError("Windows-Anmeldedatenspeicher konnte nicht gelesen werden.")
        try:
            record = pointer.contents
            if record.CredentialBlobSize > 2560:
                raise VaultError("Ungültiger Datensatz im Windows-Anmeldedatenspeicher.")
            try:
                return ctypes.string_at(record.CredentialBlob, record.CredentialBlobSize).decode()
            except UnicodeError:
                raise VaultError("Ungültiger Datensatz im Windows-Anmeldedatenspeicher.") from None
        finally:
            if pointer.contents.CredentialBlob:
                ctypes.memset(
                    pointer.contents.CredentialBlob, 0, pointer.contents.CredentialBlobSize
                )
            dll.CredFree(pointer)

    def write(self, name: str, value: str) -> None:
        target = self._target(name)
        encoded = value.encode()
        if not encoded or len(encoded) > 2560:
            raise VaultError("Schlüsseldatensatz hat eine ungültige Größe.")
        buffer = (ctypes.c_ubyte * len(encoded)).from_buffer_copy(encoded)
        record = _Credential()
        record.Type = 1  # CRED_TYPE_GENERIC
        record.TargetName = target
        record.UserName = "Der Hixton local application"
        record.CredentialBlobSize = len(encoded)
        record.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
        record.Persist = 2  # Same Windows user and machine; no enterprise roaming.
        try:
            if not self._library().CredWriteW(ctypes.byref(record), 0):
                raise VaultError("Windows konnte den Schlüssel nicht sicher speichern.")
        finally:
            ctypes.memset(buffer, 0, len(encoded))

    def delete(self, name: str) -> None:
        target = self._target(name)
        if not self._library().CredDeleteW(target, 1, 0) and ctypes.get_last_error() != 1168:
            raise VaultError("Windows konnte den Hixton-Schlüssel nicht entfernen.")


@dataclass(frozen=True, slots=True)
class BinanceCredentials:
    api_key: str = field(repr=False)
    secret_key: str = field(repr=False)
    saved_at_utc: str = ""

    def __post_init__(self) -> None:
        if any(
            not re.fullmatch(r"[A-Za-z0-9]{32,256}", value)
            for value in (self.api_key, self.secret_key)
        ):
            raise VaultError("HMAC API-Key und Secret: jeweils 32-256 Buchstaben/Ziffern nötig.")

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.api_key.encode()).hexdigest()[:12]


class CredentialService:
    def __init__(self, vault: Vault) -> None:
        self.vault = vault
        self.lock = RLock()

    def load(self) -> BinanceCredentials | None:
        value = self.vault.read("binance-hmac")
        if value is None:
            return None
        try:
            data = json.loads(value)
            return BinanceCredentials(data["api_key"], data["secret_key"], data["saved_at_utc"])
        except (ValueError, KeyError, TypeError):
            raise VaultError("Gespeicherter Binance-Schlüssel ist beschädigt.") from None

    def save(self, credentials: BinanceCredentials) -> None:
        with self.lock:
            self.vault.write(
                "binance-hmac",
                json.dumps(
                    {
                        "api_key": credentials.api_key,
                        "secret_key": credentials.secret_key,
                        "saved_at_utc": datetime.now(UTC).isoformat(),
                    }
                ),
            )

    def status(self) -> dict[str, object]:
        credentials = self.load()
        return {
            "configured": credentials is not None,
            "fingerprint": credentials.fingerprint if credentials else None,
            "saved_at_utc": credentials.saved_at_utc if credentials else None,
            "storage": "WINDOWS_CREDENTIAL_MANAGER_CURRENT_USER",
        }


class LocalAccess:
    """Password-unlocked, expiring browser sessions, separate from Binance credentials."""

    def __init__(self, vault: Vault) -> None:
        self.vault = vault
        self.lock = RLock()
        self._sessions: dict[str, float] = {}
        self._failures: deque[float] = deque()

    def configured(self) -> bool:
        return self.vault.read("ui-password") is not None

    @staticmethod
    def _derive(password: str, salt: bytes) -> str:
        return hashlib.scrypt(
            password.encode(), salt=salt, n=32768, r=8, p=1, maxmem=128 * 1024 * 1024
        ).hex()

    def unlock(self, password: str, repeated: str | None = None) -> str:
        with self.lock:
            now = time.monotonic()
            while self._failures and self._failures[0] <= now - 60:
                self._failures.popleft()
            if len(self._failures) >= 5:
                raise VaultError("Zu viele Versuche. Bitte mindestens 60 Sekunden warten.")
            self._failures.append(now)
            if not isinstance(password, str) or not 12 <= len(password) <= 256:
                raise VaultError("Lokales Passwort muss 12-256 Zeichen lang sein.")
            saved = self.vault.read("ui-password")
            if saved is None:
                if self.vault.read("binance-hmac") is not None:
                    raise VaultError("Passwortdatensatz fehlt bei vorhandenem Key. Recovery nötig.")
                if password != repeated:
                    raise VaultError("Passwort-Wiederholung stimmt nicht überein.")
                salt = secrets.token_bytes(16)
                self.vault.write(
                    "ui-password",
                    json.dumps(
                        {
                            "salt": salt.hex(),
                            "hash": self._derive(password, salt),
                        }
                    ),
                )
            else:
                try:
                    verifier = json.loads(saved)
                    expected = verifier["hash"]
                    actual = self._derive(password, bytes.fromhex(verifier["salt"]))
                except (ValueError, TypeError, KeyError):
                    raise VaultError("Lokaler Passwortdatensatz ist beschädigt.") from None
                if not hmac.compare_digest(expected, actual):
                    raise VaultError("Lokales Passwort ist nicht korrekt.")
            self._failures.clear()
            self._sessions.clear()  # One protected browser session per installation.
            token = secrets.token_urlsafe(32)
            self._sessions[hashlib.sha256(token.encode()).hexdigest()] = now + 900
            return token

    def authorized(self, token: str | None) -> bool:
        if not token or len(token) > 128:
            return False
        with self.lock:
            return (
                self._sessions.get(hashlib.sha256(token.encode()).hexdigest(), 0) > time.monotonic()
            )

    def logout(self) -> None:
        with self.lock:
            self._sessions.clear()
