"""Read-only network sampling and durable, opt-in IPv4/access notices.

Only the separate sampler performs bounded reads. Evaluation changes the outbox
database only; no order, credential mutation or trading callback exists here.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import sqlite3
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

from hixton.live.binance import _NoRedirect
from hixton.notifications.events import Notice


def public_ipv4(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 15:
        return None
    try:
        address = ipaddress.IPv4Address(value)
        return str(address) if address.is_global and not address.is_multicast else None
    except ValueError:
        return None


def read_public_ipv4() -> str | None:
    # Same direct, proxy-free HTTPS policy as the Binance transport. No keys,
    # account data, custom endpoint, redirect or unbounded response is accepted.
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    request = Request("https://api.ipify.org", headers={"User-Agent": "Hixton-IP-check"})
    with opener.open(request, timeout=3) as response:
        raw = response.read(64)
    return public_ipv4(raw.decode("ascii").strip())


@dataclass(frozen=True)
class NetworkObservation:
    ipv4: str | None = None
    ip_at: datetime | None = None
    account_state: str = "UNKNOWN"
    account_code: int | None = None
    account_at: datetime | None = None
    account_scope: str | None = None


def _time(value: object) -> datetime | None:
    try:
        moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        return moment.astimezone(UTC) if moment.tzinfo is not None else None
    except (TypeError, ValueError):
        return None


def _fresh(moment: datetime | None, now: datetime) -> bool:
    return (moment is not None and moment.tzinfo is not None
            and 0 <= (now - moment).total_seconds() <= 90)


class NetworkMonitor:
    """Independent 30s read-only sampler; delivery and trading never wait on it."""

    def __init__(
        self, *, enabled: Callable[[], bool],
        account_read: Callable[[], object],
        account_health: Callable[[], Mapping[str, object]],
        ip_reader: Callable[[], str | None] = read_public_ipv4,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.enabled, self.account_read, self.account_health = enabled, account_read, account_health
        self.ip_reader, self.clock = ip_reader, clock
        self._lock = Lock()
        self._observation = NetworkObservation()
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def snapshot(self) -> NetworkObservation:
        with self._lock:
            return self._observation

    def sample(self) -> None:
        if not self.enabled():
            with self._lock:
                self._observation = NetworkObservation()
            return
        ip, ip_at = None, None
        try:
            ip = public_ipv4(self.ip_reader())
            if ip is not None:
                ip_at = self.clock()
        except Exception:
            pass  # Never log provider errors/URLs; absence is not a recovered IP.
        health: Mapping[str, object] = {}
        try:
            self.account_read()  # Existing signed GET cache; never a preflight/order.
            health = self.account_health()
        except Exception:
            pass
        fresh = health.get("fresh") is True
        observation = NetworkObservation(
            ip, ip_at,
            str(health.get("state")) if fresh else "UNKNOWN",
            -2015 if fresh and health.get("code") == -2015 else None,
            _time(health.get("observed_at_utc")) if fresh else None,
            str(health["account_scope"]) if fresh and health.get("account_scope") else None,
        )
        with self._lock:
            self._observation = observation

    def start(self) -> None:
        if self._task is None:
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name="hixton-network-observer")

    async def _run(self) -> None:
        while not self._stop.is_set():
            with suppress(Exception):  # A failed sample cannot kill the observer.
                await asyncio.to_thread(self.sample)
            with suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=30)

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task  # Finish bounded reads; leave no orphan reader at restart.
            self._task = None


def initialize_network(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS network_notice_state("
        "singleton INTEGER PRIMARY KEY CHECK(singleton=1), generation TEXT NOT NULL,"
        "ipv4 TEXT, episode TEXT, started_at TEXT, level INTEGER NOT NULL DEFAULT 0,"
        "account_scope TEXT)"
    )


def reset_network(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM network_notice_state")


def evaluate_network(
    connection: sqlite3.Connection, generation: str, observation: NetworkObservation,
    now: datetime, *, owned_real: bool | None,
) -> tuple[Notice, ...]:
    """Enqueue results in the caller's SAME transaction; survive restart/outages.

    -2015 is deliberately ambiguous: a different IP is an observation, not proof
    that this alone caused Binance's rejection. Success proves account access,
    never sell execution, reconciliation or eligibility to open another trade.
    """
    if not connection.in_transaction or now.tzinfo is None:
        raise ValueError("Network episodes require a transaction and aware time")
    now = now.astimezone(UTC)
    row = connection.execute("SELECT * FROM network_notice_state WHERE singleton=1").fetchone()
    if row is None or row["generation"] != generation:
        reset_network(connection)
        connection.execute(
            "INSERT INTO network_notice_state(singleton,generation) VALUES(1,?)", (generation,)
        )
        previous, episode, started, level, scope = None, None, None, 0, None
    else:
        previous, episode, started, level, scope = (row[k] for k in (
            "ipv4", "episode", "started_at", "level", "account_scope"
        ))
    ip = public_ipv4(observation.ipv4) if _fresh(observation.ip_at, now) else None
    account_fresh = _fresh(observation.account_at, now)
    rejected = account_fresh and observation.account_code == -2015
    changed = ip is not None and previous is not None and ip != previous
    ip_became_known = ip is not None and previous is None and episode is not None
    if episode is None and not changed and not rejected:
        scope = observation.account_scope or scope
    if changed or (rejected and episode is None):
        episode, started, level = uuid4().hex, now.isoformat(), 0
        scope = scope or observation.account_scope
    if episode is not None and scope is None:
        scope = observation.account_scope
    if ip is not None:
        previous = ip
    notices: list[Notice] = []
    if episode is not None:
        identity = hashlib.sha256(f"network|{generation}|{episode}".encode()).hexdigest()
        start = _time(started)
        recovered = bool(
            account_fresh and observation.account_state == "CURRENT"
            and observation.account_code is None
            and scope is not None and scope == observation.account_scope
            and start is not None and observation.account_at is not None
            and observation.account_at >= start
        )
        new_level = 3 if rejected and ip is not None else 2 if rejected else 1
        if level < new_level:
            ip_line = "Öffentliche IPv4 derzeit nicht ermittelbar."
            if ip:
                ip_line = f"Gemessene öffentliche IPv4: {ip}."
            elif previous:
                ip_line = f"Zuletzt gemessene IPv4: {previous}; aktuell unbestätigt."
            exposure = (
                "Echtgeldposition noch offen; Ausstieg kann blockiert sein."
                if owned_real is True else "Offene Echtgeldpositionen/Orders im Bot prüfen."
            )
            body = (
                f"{ip_line}\nBinance lehnt den Zugriff ab (-2015). "
                "IP-Freigabe des bestehenden API-Schlüssels auf Binance prüfen/aktualisieren; "
                "auch Schlüssel oder Berechtigungen können die Ursache sein.\n"
                f"{exposure}\nDanach Binance-Verbindung im Bot prüfen."
                if rejected else
                f"{ip_line}\nIPv4 geändert. Binance-Zugriff noch nicht frisch bestätigt. "
                f"IP-Freigabe auf Binance prüfen.\n{exposure}"
            )
            notices.append(Notice(
                f"operation:{identity}-{new_level}:alert", "operation_alert", now,
                "⚠ Hixton · IPv4 zur Binance-Zugriffsprüfung" if ip_became_known and rejected else
                "⚠ Hixton · Binance-Zugriff abgelehnt" if rejected else
                "⚠ Hixton · Öffentliche IPv4 geändert", body,
            ))
            level = new_level
        if recovered:
            notices.append(Notice(
                f"operation:{identity}-{level}:recovery", "operation_recovery", now,
                "✅ Hixton · Binance-Kontozugriff wieder bestätigt",
                "Frische signierte Kontoabfrage erfolgreich.\n"
                "Offene Positionen und Ausstiege werden separat abgeglichen; "
                "diese Nachricht bestätigt keinen Verkauf.",
            ))
            episode, started, level = None, None, 0
    connection.execute(
        "UPDATE network_notice_state SET ipv4=?,episode=?,started_at=?,level=?,account_scope=? "
        "WHERE singleton=1", (previous, episode, started, level, scope),
    )
    return tuple(notices)
