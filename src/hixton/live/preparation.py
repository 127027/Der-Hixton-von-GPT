"""Audited preparation, not a simulated LIVE status or a production dispatcher."""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from functools import partial
from pathlib import Path
from threading import RLock

from hixton.domain.versions import StrategyDefinition
from hixton.live.binance import BinanceCheckError, BinanceReadOnlyClient
from hixton.live.credentials import CredentialService, LocalAccess, Vault
from hixton.live.exchange import BinanceSpotExchange, BinanceSpotTransport
from hixton.live.orders import ExchangeOrder, OrderJournal, TrialIntent, TrialOrderExecutor
from hixton.live.reconciliation import AccountSnapshot, TrialReconciler, read_account_snapshot
from hixton.live.runtime import TrialRuntime
from hixton.live.trial import SignalTrial

RELEASE_BLOCKERS = (
    "USDC-Migration und Echtorder-Anschluss benötigen gemeinsame Betriebsabnahme; "
    "USDT-Signale werden nicht als USDC ausgeführt.",
    "Einmaltest-Laufzeit und exakter Saldoabgleich sind angeschlossen und offline getestet; "
    "produktive Orderfreigabe, Markt-/Preisfilter, Restmengen und vollständige Fremdorderprüfung "
    "sind noch nicht abgenommen.",
    "Keine Livefreigabe für die aktive Strategie; Paper-Freigabe ist keine Echtgeldfreigabe.",
    "Paper-/Live-Ausführungsabgleich, Störfalltests und Binance-Testnet-Nachweis fehlen.",
)
_USDC_CLIENT = partial(BinanceReadOnlyClient, quote_asset="USDC")


class LivePreparation:
    def __init__(
        self,
        database: Path,
        vault: Vault,
        client_factory: Callable[..., BinanceReadOnlyClient] = _USDC_CLIENT,
    ) -> None:
        self.database = database
        self.credentials = CredentialService(vault)
        self.access = LocalAccess(vault)
        self.lock = RLock()
        self.client_factory = client_factory
        self._check: dict[str, object] | None = None
        self._check_time = 0.0
        self._next_check = 0.0
        # Installed routes connect the runtime; this never grants production release.
        self.trial: SignalTrial | None = None
        self.runtime: TrialRuntime | None = None

    def connect_runtime(self, strategy: StrategyDefinition) -> TrialRuntime:
        """Wire durable recovery without granting a BUY or loading keys at startup."""
        service = self

        def bound_exchange() -> BinanceSpotExchange:
            credentials = service.credentials.load()
            if credentials is None:
                raise BinanceCheckError("Binance-Schlüssel fehlt")
            transport = BinanceSpotTransport(credentials, base_url="https://api.binance.com")
            return BinanceSpotExchange(
                transport, account_fingerprint=credentials.fingerprint, quote_asset="USDC"
            )

        class DeferredExchange:
            def submit(self, intent: TrialIntent) -> ExchangeOrder:
                return bound_exchange().submit(intent)

            def query(self, intent: TrialIntent) -> ExchangeOrder | None:
                return bound_exchange().query(intent)

        def snapshot() -> AccountSnapshot:
            exchange = bound_exchange()
            return read_account_snapshot(exchange.transport, account=exchange.account_fingerprint)

        journal = OrderJournal(self.database)
        # Deliberate build-release gate, NOT a permissive default or UI Boolean.
        # Current public routes cannot arm. Market/price/ownership gates and external
        # acceptance must be implemented before this can allow production dispatch.
        self.trial = SignalTrial(
            journal,
            TrialOrderExecutor(journal, DeferredExchange(), lambda _: False),
            strategy,
            lambda: False,
        )
        self.runtime = TrialRuntime(self.trial, TrialReconciler(journal), snapshot)
        return self.runtime

    def require_settled_for_key_change(self) -> None:
        if self.trial is not None and self.trial.report()["has_unsettled"]:
            raise BinanceCheckError(
                "Laufender/ungeklärter Einmaltest: Schlüssel nicht entfernen oder ersetzen. "
                "Zuerst Orders und Bestände vollständig abgleichen."
            )

    def execution_state(self) -> str:
        if self.runtime is not None and self.runtime.last_error:
            return "TRIAL_NEEDS_REVIEW"
        if self.trial is None:
            return "LIVE_DISABLED"
        report = self.trial.report()
        return "TRIAL_" + str(report["state"]) if report["has_unsettled"] else "LIVE_DISABLED"

    def stop_entries(self) -> dict[str, object]:
        with self.lock:
            if self.trial is not None:
                self.trial.disable_entries()
                report = self.trial.report()
            else:
                report = {"state": "NOT_STARTED", "has_unsettled": False}
            self.audit("LIVE_NEW_ENTRIES_DISABLED")
            return {
                "state": "EXIT_ONLY" if report["has_unsettled"] else "LIVE_DISABLED",
                "trial": report,
                "message": "Neue Echtgeld-Einstiege gesperrt; keine Position automatisch "
                "verkauft und keine Order blind storniert. Paper bleibt unverändert. "
                "Bei offenen/unklaren echten Beständen bleibt deren Betreuung erforderlich.",
            }

    def audit(self, action: str, details: dict[str, object] | None = None) -> None:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database, timeout=10) as connection:
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS live_preparation_audit ("
                "id INTEGER PRIMARY KEY, at_utc TEXT NOT NULL, action TEXT NOT NULL, "
                "details_json TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO live_preparation_audit(at_utc, action, details_json) VALUES (?, ?, ?)",
                (datetime.now(UTC).isoformat(), action, json.dumps(details or {})),
            )

    def invalidate_check(self) -> None:
        self._check = None
        self._check_time = 0

    def check(self) -> dict[str, object]:
        # Serialize save/delete/check to avoid checking a replaced credential.
        with self.lock:
            if time.monotonic() < self._next_check:
                raise BinanceCheckError(
                    "Binance-Prüfung pausiert. Bitte nach der Wartezeit erneut prüfen."
                )
            credentials = self.credentials.load()
            if credentials is None:
                raise BinanceCheckError(
                    "Binance API-Schlüssel fehlt. Bitte lokal sicher eintragen."
                )
            self.invalidate_check()
            self._next_check = time.monotonic() + 30
            self.audit("BINANCE_READ_ONLY_CHECK_REQUESTED")
            try:
                result = self.client_factory(credentials).inspect(Decimal("50"))
            except BinanceCheckError as error:
                self._next_check = max(self._next_check, time.monotonic() + error.retry_after)
                self.audit("BINANCE_READ_ONLY_CHECK_FAILED")
                raise
            self._check = {**result, "checked_at_utc": datetime.now(UTC).isoformat()}
            self._check_time = time.monotonic()
            # Do not persist complete Binance account balances or raw API responses.
            self.audit(
                "BINANCE_READ_ONLY_CHECK_COMPLETE",
                {
                    "passed": result.get("account_checks_passed") is True,
                    "fingerprint": credentials.fingerprint,
                },
            )
            return dict(self._check)

    def status(self, *, authenticated: bool, soak_ready: bool, healthy: bool) -> dict[str, object]:
        with self.lock:
            credential_status = self.credentials.status()
            blockers = list(RELEASE_BLOCKERS)
            if self.runtime is not None and self.runtime.last_error:
                blockers.append(
                    "Einmaltest-Laufzeit/Abgleich benötigt Klärung; System & Logs prüfen."
                )
            if not credential_status["configured"]:
                blockers.insert(0, "Binance API-Schlüssel fehlt. Bitte hier lokal eintragen.")
            if not soak_ready:
                blockers.append(
                    "Paper-Dauertest noch nicht bestanden (mindestens 30 Tage / 20 Trades)."
                )
            if not healthy:
                blockers.append("Marktdaten/Bot derzeit nicht vollständig gesund.")
            fresh_check = self._check if time.monotonic() - self._check_time <= 60 else None
            if fresh_check is None:
                blockers.append("Keine frische Binance-Kontoprüfung (höchstens 60 Sekunden alt).")
            elif fresh_check.get("account_checks_passed") is not True:
                blockers.append("Binance-Kontoprüfung enthält Blockierungen.")
            return {
                "state": self.execution_state(),
                "order_dispatch_available": False,
                "ready": False,
                "authenticated": authenticated,
                "password_configured": self.access.configured(),
                "credentials": credential_status
                if authenticated
                else {
                    "configured": credential_status["configured"],
                },
                "blockers": blockers,
                "account_check": fresh_check if authenticated else None,
                "trial_dispatch_available": False,
                "trial_quote_asset": "USDC",
                "trial_readiness": {
                    "quote_aware_order_adapter_offline_tested": True,
                    "runtime_connected": self.runtime is not None,
                    "balance_conservation_connected": self.runtime is not None,
                    "production_submission_accepted": False,
                    "account_reconciliation_accepted": False,
                    "binance_testnet_accepted": False,
                },
                "trial": self.trial.report()
                if authenticated and self.trial is not None
                else {"state": "NOT_STARTED" if self.trial is None else "LOCKED"},
                "first_live_trial": {
                    "slot_count": 1,
                    "quote_asset": "USDC",
                    "target_notional_quote": "50.00",
                    "minimum_free_quote": "60.00",
                },
            }
