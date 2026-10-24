"""Read-only, rate-limited Binance USDC display; never changes trading state."""

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from threading import Lock
from time import monotonic

from hixton.live.credentials import CredentialService
from hixton.live.exchange import BinanceSpotTransport, ExchangeRequestError, SpotTransport


class AccountBalanceDisplay:
    def __init__(
        self,
        credentials: CredentialService,
        *,
        base_url: str,
        transport_factory: Callable[..., SpotTransport] = BinanceSpotTransport,
        clock: Callable[[], float] = monotonic,
        refresh_seconds: int = 30,
        retry_seconds: int = 60,
    ) -> None:
        self.credentials = credentials
        self.base_url = base_url
        self.transport_factory = transport_factory
        self.clock = clock
        self.refresh_seconds = refresh_seconds
        self.retry_seconds = retry_seconds
        self._lock = Lock()
        self._fingerprint: str | None = None
        self._until = 0.0
        self._payload: dict[str, object] | None = None
        self._health: dict[str, object] = {"state": "UNKNOWN", "code": None}
        self._health_at: float | None = None

    def health_observation(self) -> dict[str, object]:
        """Passive sanitized observation; never issue or wait for an account request."""
        if not self._lock.acquire(blocking=False):
            return {"state": "UNKNOWN", "code": None, "fresh": False}
        try:
            age = self.clock() - self._health_at if self._health_at is not None else -1
            return {**self._health, "fresh": 0 <= age <= 90}
        finally:
            self._lock.release()

    def read(self) -> dict[str, object]:
        with self._lock:
            try:
                credentials = self.credentials.load()
                if credentials is None:
                    self._health = {"state": "KEY_MISSING", "code": None}
                    self._health_at = self.clock()
                    self._fingerprint = None
                    self._payload = None
                    return self._unavailable(
                        "KEY_MISSING", "Binance-Schlüssel in den Einstellungen speichern."
                    )
                fingerprint = credentials.fingerprint
                now = self.clock()
                if (
                    fingerprint == self._fingerprint
                    and self._payload is not None
                    and now < self._until
                ):
                    return dict(self._payload)
                self._fingerprint = fingerprint
                transport = self.transport_factory(credentials, base_url=self.base_url)
                account = transport.request("GET", "/api/v3/account", {})
                if not isinstance(account, dict) or account.get("accountType") != "SPOT":
                    raise ValueError("Invalid Spot account")
                balances = account.get("balances")
                if not isinstance(balances, list):
                    raise ValueError("Invalid balances")
                found = [
                    row for row in balances if isinstance(row, dict) and row.get("asset") == "USDC"
                ]
                if len(found) > 1:
                    raise ValueError("Duplicate USDC")
                row = found[0] if found else {"free": "0", "locked": "0"}
                if not isinstance(row.get("free"), str) or not isinstance(row.get("locked"), str):
                    raise ValueError("Invalid amount type")
                free, locked = Decimal(row["free"]), Decimal(row["locked"])
                if not free.is_finite() or not locked.is_finite() or min(free, locked) < 0:
                    raise ValueError("Invalid amount")
                self._payload = {
                    "state": "CURRENT",
                    "free_usdc": str(free),
                    "locked_usdc": str(locked),
                    "total_usdc": str(free + locked),
                    "observed_at_utc": datetime.now(UTC).isoformat(),
                    "refresh_seconds": self.refresh_seconds,
                    "read_only": True,
                    "message": "Spot-USDC; bestehende Coins sind nicht enthalten.",
                }
                self._until = self.clock() + self.refresh_seconds
                self._health = {"state": "CURRENT", "code": None}
                self._health_at = self.clock()
            except Exception as error:
                code = error.code if isinstance(error, ExchangeRequestError) else None
                self._health = {
                    "state": "UNAVAILABLE", "code": code if code in {-2015, -1021} else None,
                }
                self._health_at = self.clock()
                self._payload = self._unavailable(
                    "UNAVAILABLE",
                    "Binance-Guthaben nicht abrufbar. Verbindung, Schlüssel "
                    "und IP-Freigabe prüfen.",
                )
                self._until = self.clock() + self.retry_seconds
            assert self._payload is not None
            return dict(self._payload)

    def _unavailable(self, state: str, message: str) -> dict[str, object]:
        return {
            "state": state,
            "free_usdc": None,
            "locked_usdc": None,
            "total_usdc": None,
            "observed_at_utc": None,
            "refresh_seconds": self.retry_seconds,
            "read_only": True,
            "message": message,
        }
