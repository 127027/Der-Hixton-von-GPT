"""Local credential, controlled-trial and production Live release service."""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from functools import partial
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from hixton.backtest.models import ExecutionRules
from hixton.domain.models import IndicatorPoint
from hixton.domain.versions import StrategyDefinition
from hixton.live.binance import BinanceCheckError, BinanceReadOnlyClient
from hixton.live.credentials import CredentialService, LocalAccess, Vault
from hixton.live.exchange import BinanceSpotExchange, BinanceSpotTransport
from hixton.live.orders import ExchangeOrder, OrderJournal, TrialIntent, TrialOrderExecutor
from hixton.live.production import (
    LiveAccountSnapshot,
    LiveBalanceReconciler,
    LiveOrderExecutor,
    LiveOrderJournal,
    LivePortfolioController,
    LivePortfolioRuntime,
)
from hixton.live.reconciliation import AccountSnapshot, TrialReconciler, read_account_snapshot
from hixton.live.runtime import TrialRuntime
from hixton.live.trial import SignalTrial

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
        self._trial_authorized = False
        self.trial: SignalTrial | None = None
        self.runtime: TrialRuntime | None = None
        self.trial_reconciler: TrialReconciler | None = None
        self.live: LivePortfolioController | None = None
        self.live_runtime: LivePortfolioRuntime | None = None
        self.live_reconciler: LiveBalanceReconciler | None = None

    def _bound_exchange(self) -> BinanceSpotExchange:
        credentials = self.credentials.load()
        if credentials is None:
            raise BinanceCheckError("Binance-Schlüssel fehlt")
        transport = BinanceSpotTransport(credentials, base_url="https://api.binance.com")
        return BinanceSpotExchange(
            transport,
            account_fingerprint=credentials.fingerprint,
            quote_asset="USDC",
        )

    def _account_snapshot(self) -> AccountSnapshot:
        exchange = self._bound_exchange()
        return read_account_snapshot(exchange.transport, account=exchange.account_fingerprint)

    def _live_snapshot(self) -> LiveAccountSnapshot:
        snapshot = self._account_snapshot()
        return LiveAccountSnapshot(
            snapshot.account,
            snapshot.observed_at,
            snapshot.balances,
            snapshot.open_orders,
        )

    def _fresh_check(self) -> dict[str, object] | None:
        if time.monotonic() - self._check_time > 60:
            return None
        return self._check

    def _trial_pre_submit(self, intent: TrialIntent) -> bool:
        if not self._trial_authorized or self.trial_reconciler is None:
            return False
        try:
            snapshot = self._account_snapshot()
            proof = self.trial_reconciler.check(
                snapshot,
                now=datetime.now(UTC),
                ignore_intent_id=intent.intent_id,
            )
            if proof["balances_match"] is not True or proof["no_open_orders"] is not True:
                return False
            if intent.side == "BUY":
                credentials = self.credentials.load()
                if credentials is None:
                    return False
                result = self.client_factory(credentials).inspect(Decimal("50"))
                return result.get("account_checks_passed") is True
            base = intent.symbol.removesuffix("USDC")
            return snapshot.balances.get(base, (Decimal(0), Decimal(0)))[0] >= intent.base_quantity
        except Exception:
            return False

    def connect_runtime(
        self,
        strategy: StrategyDefinition,
        *,
        settings_provider: Callable[[], tuple[int, Decimal, bool]],
        rules_provider: Callable[[], Mapping[str, ExecutionRules]],
    ) -> TrialRuntime:
        """Wire both durable execution runtimes without enabling either one."""
        service = self

        class DeferredExchange:
            def submit(self, intent: Any) -> ExchangeOrder:
                return service._bound_exchange().submit(intent)

            def query(self, intent: Any) -> ExchangeOrder | None:
                return service._bound_exchange().query(intent)

        trial_journal = OrderJournal(self.database)
        self.trial_reconciler = TrialReconciler(trial_journal)
        self.trial = SignalTrial(
            trial_journal,
            TrialOrderExecutor(trial_journal, DeferredExchange(), self._trial_pre_submit),
            strategy,
            lambda: self._trial_authorized
            and bool(self.credentials.status()["configured"]),
        )
        self.runtime = TrialRuntime(self.trial, self.trial_reconciler, self._account_snapshot)
        self._trial_authorized = bool(self.trial.report().get("has_unsettled"))

        live_journal = LiveOrderJournal(self.database)
        self.live_reconciler = LiveBalanceReconciler(live_journal)
        holder: dict[str, LivePortfolioController] = {}
        live_executor = LiveOrderExecutor(
            live_journal,
            DeferredExchange(),
            lambda intent: holder["controller"].pre_submit(intent),
        )
        self.live = LivePortfolioController(
            self.database,
            live_journal,
            live_executor,
            self.live_reconciler,
            self._live_snapshot,
            settings_provider,
            rules_provider,
            strategy,
            lambda: bool(self.credentials.status()["configured"]),
        )
        holder["controller"] = self.live
        self.live_runtime = LivePortfolioRuntime(self.live)
        return self.runtime

    def require_settled_for_key_change(self) -> None:
        if self.trial is not None and self.trial.report()["has_unsettled"]:
            raise BinanceCheckError(
                "Laufender/ungeklärter Einmaltest: Schlüssel nicht entfernen oder ersetzen."
            )
        if self.live is not None and self.live.report()["initialized"]:
            raise BinanceCheckError(
                "Live-Konto ist bereits an diesen Schlüssel gebunden. "
                "Schlüsselwechsel benötigt einen separaten Konto-/Ledger-Abgleich."
            )

    def execution_state(self) -> str:
        if self.live_runtime is not None and self.live_runtime.last_error:
            return "NEEDS_REVIEW"
        if self.live is not None:
            live_state = str(self.live.report()["state"])
            if live_state != "LIVE_DISABLED":
                return live_state
        if self.runtime is not None and self.runtime.last_error:
            return "TRIAL_NEEDS_REVIEW"
        if self.trial is not None:
            trial = self.trial.report()
            if trial["has_unsettled"]:
                return "TRIAL_" + str(trial["state"])
        return "LIVE_DISABLED"

    def stop_entries(self) -> dict[str, object]:
        with self.lock:
            if self.trial is not None:
                self.trial.disable_entries()
            if self.live is not None:
                self.live.disable_entries()
            self.audit("LIVE_NEW_ENTRIES_DISABLED")
            live = self.live.report() if self.live is not None else {"state": "LIVE_DISABLED"}
            trial = self.trial.report() if self.trial is not None else {"state": "NOT_STARTED"}
            return {
                "state": self.execution_state(),
                "trial": trial,
                "live": live,
                "message": (
                    "Neue Echtgeld-Einstiege gesperrt. Bereits gesendete/unklare Orders "
                    "werden nur abgeglichen; offene Positionen dürfen weiter regulär aussteigen."
                ),
            }

    def audit(self, action: str, details: dict[str, object] | None = None) -> None:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database, timeout=10) as connection:
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS live_preparation_audit("
                "id INTEGER PRIMARY KEY,at_utc TEXT NOT NULL,action TEXT NOT NULL,"
                "details_json TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO live_preparation_audit(at_utc,action,details_json) VALUES(?,?,?)",
                (datetime.now(UTC).isoformat(), action, json.dumps(details or {})),
            )

    def invalidate_check(self) -> None:
        self._check = None
        self._check_time = 0

    def check(self) -> dict[str, object]:
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
            self.audit(
                "BINANCE_READ_ONLY_CHECK_COMPLETE",
                {
                    "passed": result.get("account_checks_passed") is True,
                    "fingerprint": credentials.fingerprint,
                },
            )
            return dict(self._check)

    def start_trial(
        self,
        *,
        healthy: bool,
        slot_count: int,
        target_notional: Decimal,
        emergency_stop: bool,
    ) -> dict[str, object]:
        with self.lock:
            if self.trial is None or self.trial_reconciler is None:
                raise BinanceCheckError("Einmaltest-Runtime fehlt")
            if not healthy:
                raise BinanceCheckError("Marktdaten/Bot sind nicht gesund")
            if slot_count != 1 or target_notional != Decimal("50") or emergency_stop:
                raise BinanceCheckError("Erster Echtgeldtest benötigt Einstellungen 1 x 50 USDC")
            fresh = self._fresh_check()
            if fresh is None or fresh.get("account_checks_passed") is not True:
                raise BinanceCheckError("Zuerst eine frische Binance-Kontoprüfung durchführen")
            if self.trial.report()["state"] != "NOT_STARTED":
                raise BinanceCheckError("Der kontrollierte 50-USDC-Test wurde bereits angelegt")
            if self.live is not None and self.live.report()["state"] != "LIVE_DISABLED":
                raise BinanceCheckError("Kontinuierlicher Livebetrieb ist bereits aktiv")
            credentials = self.credentials.load()
            if credentials is None:
                raise BinanceCheckError("Binance-Schlüssel fehlt")
            snapshot = self._account_snapshot()
            self.trial_reconciler.capture(snapshot, now=datetime.now(UTC))
            self._trial_authorized = True
            self.trial.arm(
                str(uuid4()),
                credentials.fingerprint,
                now=datetime.now(UTC),
                notional=Decimal("50"),
            )
            self.audit("CONTROLLED_50_USDC_TRIAL_ARMED")
            return self.trial.report()

    def enable_live(
        self,
        points: Mapping[str, tuple[IndicatorPoint, ...]],
        *,
        healthy: bool,
        soak_ready: bool,
        slot_count: int,
        target_notional: Decimal,
        emergency_stop: bool,
    ) -> dict[str, object]:
        with self.lock:
            if self.live is None:
                raise BinanceCheckError("Produktive Live-Runtime fehlt")
            if not healthy:
                raise BinanceCheckError("Marktdaten/Bot sind nicht gesund")
            if not soak_ready:
                raise BinanceCheckError("Paper-Dauertest ist noch nicht freigegeben")
            if slot_count != 3 or target_notional != Decimal("80") or emergency_stop:
                raise BinanceCheckError("24/7-Livebetrieb benötigt exakt 3 x 80 USDC")
            if self.trial is None or self.trial.report()["state"] != "COMPLETED":
                raise BinanceCheckError(
                    "Zuerst muss der kontrollierte 50-USDC-Roundtrip fertig sein"
                )
            fresh = self._fresh_check()
            if fresh is None or fresh.get("account_checks_passed") is not True:
                raise BinanceCheckError("Zuerst eine frische Binance-Kontoprüfung durchführen")
            if Decimal(str(fresh.get("free_usdc", "0"))) < Decimal("250"):
                raise BinanceCheckError("Für 3 x 80 werden mindestens 250 freie USDC verlangt")
            credentials = self.credentials.load()
            if credentials is None:
                raise BinanceCheckError("Binance-Schlüssel fehlt")
            self.live.enable(
                credentials.fingerprint,
                points,
                self._live_snapshot(),
                now=datetime.now(UTC),
            )
            self.audit(
                "PRODUCTION_LIVE_ENABLED",
                {"slot_count": 3, "target_notional_usdc": "80.00"},
            )
            return self.live.report()

    def status(
        self,
        *,
        authenticated: bool,
        soak_ready: bool,
        healthy: bool,
        slot_count: int | None = None,
        target_notional: Decimal | None = None,
        emergency_stop: bool = True,
    ) -> dict[str, object]:
        with self.lock:
            credential_status = self.credentials.status()
            fresh = self._fresh_check()
            account_ok = fresh is not None and fresh.get("account_checks_passed") is True
            trial = self.trial.report() if self.trial is not None else {"state": "NOT_STARTED"}
            live = self.live.report() if self.live is not None else {
                "initialized": False,
                "state": "LIVE_DISABLED",
                "positions": [],
                "unresolved_intents": [],
            }
            trial_settings_ok = (
                slot_count == 1
                and target_notional == Decimal("50")
                and emergency_stop is False
            )
            production_settings_ok = (
                slot_count == 3
                and target_notional == Decimal("80")
                and emergency_stop is False
            )
            trial_available = bool(
                credential_status["configured"]
                and account_ok
                and healthy
                and trial_settings_ok
                and trial.get("state") == "NOT_STARTED"
                and live.get("state") == "LIVE_DISABLED"
            )
            trial_completed = trial.get("state") == "COMPLETED"
            free_usdc = (
                Decimal(str(fresh.get("free_usdc", "0")))
                if account_ok and fresh is not None
                else Decimal(0)
            )
            production_ready = bool(
                credential_status["configured"]
                and account_ok
                and healthy
                and soak_ready
                and trial_completed
                and production_settings_ok
                and free_usdc >= Decimal("250")
                and live.get("state") != "NEEDS_REVIEW"
            )
            blockers: list[str] = []
            if not credential_status["configured"]:
                blockers.append("Binance API-Schlüssel fehlt.")
            if not healthy:
                blockers.append("Marktdaten/Bot derzeit nicht vollständig gesund.")
            if fresh is None:
                blockers.append("Keine frische Binance-Kontoprüfung (höchstens 60 Sekunden alt).")
            elif fresh.get("account_checks_passed") is not True:
                blockers.append("Binance-Kontoprüfung enthält Blockierungen.")
            if not trial_completed:
                blockers.append(
                    "Vor dauerhaftem 3x80-Livebetrieb ist ein kontrollierter 1x50-Roundtrip nötig."
                )
            if not soak_ready:
                blockers.append("Paper-Dauertest noch nicht bestanden (30 Tage / 20 Trades).")
            if not production_settings_ok:
                blockers.append("Dauer-Liveprofil ist ausschließlich 3 x 80 USDC.")
            if live.get("state") == "NEEDS_REVIEW":
                blockers.append(
                    "Live-Ledger benötigt manuellen Abgleich; neue Orders sind gesperrt."
                )
            return {
                "state": self.execution_state(),
                "order_dispatch_available": production_ready,
                "ready": production_ready,
                "authenticated": authenticated,
                "password_configured": self.access.configured(),
                "credentials": (
                    credential_status
                    if authenticated
                    else {"configured": credential_status["configured"]}
                ),
                "blockers": blockers,
                "account_check": fresh if authenticated else None,
                "trial_dispatch_available": trial_available,
                "trial_quote_asset": "USDC",
                "trial_readiness": {
                    "quote_aware_order_adapter_offline_tested": True,
                    "runtime_connected": self.runtime is not None,
                    "balance_conservation_connected": self.trial_reconciler is not None,
                    "production_submission_accepted": True,
                    "account_reconciliation_accepted": True,
                    "binance_testnet_accepted": False,
                },
                "trial": trial if authenticated else {
                    "state": trial.get("state", "NOT_STARTED"),
                    "has_unsettled": trial.get("has_unsettled", False),
                },
                "live": live if authenticated else {
                    "state": live.get("state", "LIVE_DISABLED"),
                    "used_slots": live.get("used_slots", 0),
                    "free_slots": live.get("free_slots", 3),
                },
                "first_live_trial": {
                    "slot_count": 1,
                    "quote_asset": "USDC",
                    "target_notional_quote": "50.00",
                    "minimum_free_quote": "60.00",
                },
                "production_live": {
                    "slot_count": 3,
                    "target_notional_usdc": "80.00",
                    "max_committed_usdc": "240.00",
                    "minimum_free_usdc_at_enable": "250.00",
                    "spot_only": True,
                    "quote_asset": "USDC",
                },
            }
