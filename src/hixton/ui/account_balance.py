"""Read-only, rate-limited Binance USDC display; never changes trading state."""
from datetime import UTC, datetime
from decimal import Decimal
from threading import Lock
from time import monotonic

from hixton.live.exchange import BinanceSpotTransport


class AccountBalanceDisplay:
    def __init__(self, credentials, *, base_url, transport_factory=BinanceSpotTransport,
                 clock=monotonic, refresh_seconds=30, retry_seconds=60):
        self.credentials = credentials
        self.base_url = base_url
        self.transport_factory = transport_factory
        self.clock = clock
        self.refresh_seconds = refresh_seconds
        self.retry_seconds = retry_seconds
        self._lock = Lock()
        self._fingerprint = None
        self._until = 0
        self._payload = None

    def read(self):
        with self._lock:
            try:
                credentials = self.credentials.load()
                if credentials is None:
                    self._fingerprint = None
                    self._payload = None
                    return self._unavailable("KEY_MISSING", "Binance-Schlüssel in den Einstellungen speichern.")
                fingerprint = credentials.fingerprint
                now = self.clock()
                if fingerprint == self._fingerprint and self._payload is not None and now < self._until:
                    return dict(self._payload)
                self._fingerprint = fingerprint
                transport = self.transport_factory(credentials, base_url=self.base_url)
                account = transport.request("GET", "/api/v3/account", {})
                if not isinstance(account, dict) or account.get("accountType") != "SPOT":
                    raise ValueError("Invalid Spot account")
                balances = account.get("balances")
                if not isinstance(balances, list):
                    raise ValueError("Invalid balances")
                found = [row for row in balances if isinstance(row, dict) and row.get("asset") == "USDC"]
                if len(found) > 1:
                    raise ValueError("Duplicate USDC")
                row = found[0] if found else {"free": "0", "locked": "0"}
                if not isinstance(row.get("free"), str) or not isinstance(row.get("locked"), str):
                    raise ValueError("Invalid amount type")
                free, locked = Decimal(row["free"]), Decimal(row["locked"])
                if not free.is_finite() or not locked.is_finite() or min(free, locked) < 0:
                    raise ValueError("Invalid amount")
                self._payload = {"state": "CURRENT", "free_usdc": str(free),
                                 "locked_usdc": str(locked), "total_usdc": str(free + locked),
                                 "observed_at_utc": datetime.now(UTC).isoformat(),
                                 "refresh_seconds": self.refresh_seconds, "read_only": True,
                                 "message": "Spot-USDC; bestehende Coins sind nicht enthalten."}
                self._until = self.clock() + self.refresh_seconds
            except Exception:
                self._payload = self._unavailable("UNAVAILABLE", "Binance-Guthaben nicht abrufbar. Verbindung, Schlüssel und IP-Freigabe prüfen.")
                self._until = self.clock() + self.retry_seconds
            return dict(self._payload)

    def _unavailable(self, state, message):
        return {"state": state, "free_usdc": None, "locked_usdc": None,
                "total_usdc": None, "observed_at_utc": None,
                "refresh_seconds": self.retry_seconds, "read_only": True, "message": message}
