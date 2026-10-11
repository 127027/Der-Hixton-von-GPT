"""Fresh, read-only Spot USDC balance used only as historical starting capital."""
from datetime import UTC, datetime
from decimal import Decimal
from hixton.config import ProjectConfig
from hixton.live.credentials import CredentialService, WindowsVault
from hixton.live.exchange import BinanceSpotTransport
from hixton.live.reconciliation import read_account_snapshot


def read_binance_starting_capital(config: ProjectConfig) -> dict[str, object]:
    credentials = CredentialService(WindowsVault(config.database_path)).load()
    if credentials is None:
        raise RuntimeError("Automatik-Portfolio: Binance-Schlüssel fehlt; kein Ersatzbudget verwendet.")
    try:
        transport = BinanceSpotTransport(credentials, base_url=config.binance_base_url)
        snapshot = read_account_snapshot(transport, account=credentials.fingerprint)
        snapshot.validate(datetime.now(UTC))
        free, locked = snapshot.balances.get("USDC", (Decimal(0), Decimal(0)))
        if not free.is_finite() or free <= 0:
            raise ValueError("No available USDC")
        return {"kind": "BINANCE_SPOT_FREE_USDC", "quote_asset": "USDC",
                "amount_usdc": str(free), "locked_usdc_excluded": str(locked),
                "observed_at_utc": snapshot.observed_at.isoformat(), "read_only": True,
                "existing_coins_included": False, "existing_positions_imported": False}
    except Exception:
        raise RuntimeError("Automatik-Portfolio: frische Binance-USDC-Abfrage fehlgeschlagen; kein Ersatzbudget verwendet.") from None
