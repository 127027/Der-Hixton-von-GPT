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
from hixton.domain.capital import capital_plan
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

    def _cache_check(self, result: dict[str, object]) -> dict[str, object]:
        self._check = {**result, "checked_at_utc": datetime.now(UTC).isoformat()}
        self._check_time = time.monotonic()
        return dict(self._check)

    def _action_check(
        self,
        *,
        trade_notional: Decimal,
        minimum_free_quote: Decimal,
        audit_prefix: str,
    ) -> dict[str, object]:
        """Run/reuse a sufficient read-only preflight inside the explicit action."""
        fresh = self._fresh_check()
        if fresh is not None and fresh.get("account_checks_passed") is True:
            try:
                checked = Decimal(str(fresh.get("checked_trade_notional", "0")))
                minimum = Decimal(str(fresh.get("minimum_free_quote", "0")))
            except Exception:
                checked = Decimal(0)
                minimum = Decimal(0)
            if checked >= trade_notional and minimum >= minimum_free_quote:
                return fresh
        credentials = self.credentials.load()
        if credentials is None:
            raise BinanceCheckError("Binance API-Schlüssel fehlt. Bitte lokal sicher eintragen.")
        self.audit(audit_prefix + "_PREFLIGHT_REQUESTED")
        try:
            result = self.client_factory(credentials).inspect(
                trade_notional,
                minimum_free_quote=minimum_free_quote,
            )
        except BinanceCheckError:
            self.audit(audit_prefix + "_PREFLIGHT_FAILED")
            raise
        cached = self._cache_check(result)
        self.audit(
            audit_prefix + "_PREFLIGHT_COMPLETE",
            {
                "passed": result.get("account_checks_passed") is True,
                "fingerprint": credentials.fingerprint,
                "trade_notional": str(trade_notional),
                "minimum_free_quote": str(minimum_free_quote),
            },
        )
        if result.get("account_checks_passed") is not True:
            blockers = result.get("blockers")
            detail = "; ".join(str(item) for item in blockers) if isinstance(blockers, list) else ""
            raise BinanceCheckError(
                "Binance-Kontovorprüfung blockiert diese Freigabe."
                + (f" {detail}" if detail else "")
            )
        return cached

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
                result = self.client_factory(credentials).inspect(
                    Decimal("50"), minimum_free_quote=Decimal("50")
                )
                return result.get("account_checks_passed") is True
            base = intent.symbol.removesuffix("USDC")
            return snapshot.balances.get(base, (Decimal(0), Decimal(0)))[0] >= intent.base_quantity
        except Exception:
            return False

    def connect_runtime(
        self,
        strategy: StrategyDefinition,
        *,
        settings_provider: Callable[[], tuple[Decimal, bool]],
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
                result = self.client_factory(credentials).inspect(
                    Decimal("50"), minimum_free_quote=Decimal("60")
                )
            except BinanceCheckError as error:
                self._next_check = max(self._next_check, time.monotonic() + error.retry_after)
                self.audit("BINANCE_READ_ONLY_CHECK_FAILED")
                raise
            cached = self._cache_check(result)
            self.audit(
                "BINANCE_READ_ONLY_CHECK_COMPLETE",
                {
                    "passed": result.get("account_checks_passed") is True,
                    "fingerprint": credentials.fingerprint,
                },
            )
            return cached

    def start_trial(
        self,
        *,
        healthy: bool,
        emergency_stop: bool,
    ) -> dict[str, object]:
        with self.lock:
            if self.trial is None or self.trial_reconciler is None:
                raise BinanceCheckError("Einmaltest-Runtime fehlt")
            # Arming itself sends no order. Runtime health is enforced again on every
            # execution tick before a future signal can reach the order adapter.
            if emergency_stop:
                raise BinanceCheckError("Einstiegspause ist aktiv; 50-USDC-Test bleibt gesperrt")
            state = str(self.trial.report()["state"])
            if state == "CANCELED":
                try:
                    self.trial.prepare_retry()
                except RuntimeError as error:
                    raise BinanceCheckError(
                        "Abgebrochener Test enthält bereits Orderhistorie und benötigt Abgleich."
                    ) from error
                state = str(self.trial.report()["state"])
            if state != "NOT_STARTED":
                raise BinanceCheckError(
                    f"Der kontrollierte 50-USDC-Test ist bereits im Zustand {state}."
                )
            if self.live is not None and self.live.report()["state"] != "LIVE_DISABLED":
                raise BinanceCheckError("Kontinuierlicher Livebetrieb ist bereits aktiv")
            self._action_check(
                trade_notional=Decimal("50"),
                minimum_free_quote=Decimal("60"),
                audit_prefix="CONTROLLED_50_USDC",
            )
            credentials = self.credentials.load()
            if credentials is None:
                raise BinanceCheckError("Binance-Schlüssel fehlt")
            try:
                snapshot = self._account_snapshot()
            except Exception as error:
                self.audit("CONTROLLED_50_USDC_BASELINE_READ_FAILED")
                raise BinanceCheckError(
                    "Kontobaseline konnte nicht stabil gelesen werden; bitte erneut versuchen."
                ) from error
            try:
                self.trial_reconciler.capture(snapshot, now=datetime.now(UTC))
            except (RuntimeError, ValueError, sqlite3.DatabaseError) as error:
                self.audit("CONTROLLED_50_USDC_BASELINE_CAPTURE_FAILED")
                raise BinanceCheckError(
                    "Kontobaseline konnte nicht sicher vorbereitet werden; "
                    "es wurde keine Order ausgelöst. Erneuter Start ist vor einer Order "
                    "sicher möglich."
                ) from error
            self._trial_authorized = True
            try:
                self.trial.arm(
                    str(uuid4()),
                    credentials.fingerprint,
                    now=datetime.now(UTC),
                    notional=Decimal("50"),
                )
            except (RuntimeError, ValueError, sqlite3.DatabaseError) as error:
                self._trial_authorized = bool(self.trial.report().get("has_unsettled"))
                self.audit("CONTROLLED_50_USDC_ARM_FAILED")
                raise BinanceCheckError(
                    "50-USDC-Test konnte vor der ersten Order nicht scharfgeschaltet werden; "
                    "der Vorbereitungszustand ist wiederholbar."
                ) from error
            self.audit(
                "CONTROLLED_50_USDC_TRIAL_ARMED",
                {"runtime_health_at_arm": "HEALTHY" if healthy else "DEGRADED"},
            )
            return self.trial.report()

    def enable_live(
        self,
        points: Mapping[str, tuple[IndicatorPoint, ...]],
        *,
        healthy: bool,
        max_capital: Decimal,
        emergency_stop: bool,
    ) -> dict[str, object]:
        with self.lock:
            if self.live is None:
                raise BinanceCheckError("Produktive Live-Runtime fehlt")
            if not healthy:
                raise BinanceCheckError("Marktdaten/Bot sind nicht gesund")
            try:
                plan = capital_plan(max_capital)
            except ValueError as error:
                raise BinanceCheckError(str(error)) from error
            if emergency_stop:
                raise BinanceCheckError("Einstiegspause ist aktiv")
            if self.trial is None or self.trial.report()["state"] != "COMPLETED":
                raise BinanceCheckError(
                    "Zuerst muss der kontrollierte 50-USDC-Roundtrip fertig sein"
                )
            # Live performs its own fresh/sufficient preflight. A separate manual
            # connection-check click is diagnostic only, never a required ritual.
            self._action_check(
                trade_notional=plan.max_capital_usdc,
                minimum_free_quote=plan.max_capital_usdc,
                audit_prefix="PRODUCTION_LIVE",
            )
            credentials = self.credentials.load()
            if credentials is None:
                raise BinanceCheckError("Binance-Schlüssel fehlt")
            try:
                snapshot = self._live_snapshot()
                self.live.enable(
                    credentials.fingerprint,
                    points,
                    snapshot,
                    now=datetime.now(UTC),
                )
            except (RuntimeError, ValueError, sqlite3.DatabaseError) as error:
                self.audit("PRODUCTION_LIVE_ENABLE_FAILED")
                raise BinanceCheckError(
                    "Live-Freigabe konnte Konto, Marktdaten oder Ledger nicht sicher binden; "
                    "es wurde keine neue Order ausgelöst."
                ) from error
            self.audit(
                "PRODUCTION_LIVE_ENABLED",
                {
                    "max_capital_usdc": str(plan.max_capital_usdc),
                    "slot_count": plan.slot_count,
                    "target_notional_usdc": str(plan.target_notional_usdc),
                    "allocator_version": plan.version,
                },
            )
            return self.live.report()

    def status(
        self,
        *,
        authenticated: bool,
        soak_ready: bool,
        healthy: bool,
        max_capital: Decimal | None = None,
        emergency_stop: bool = True,
    ) -> dict[str, object]:
        with self.lock:
            credential_status = self.credentials.status()
            fresh = self._fresh_check()
            trial = self.trial.report() if self.trial is not None else {"state": "NOT_STARTED"}
            live = self.live.report() if self.live is not None else {
                "initialized": False,
                "state": "LIVE_DISABLED",
                "positions": [],
                "unresolved_intents": [],
            }
            trial_settings_ok = emergency_stop is False
            try:
                production_plan = (
                    capital_plan(max_capital) if max_capital is not None else None
                )
            except ValueError:
                production_plan = None
            production_settings_ok = (
                production_plan is not None and emergency_stop is False
            )
            trial_state = str(trial.get("state", "NOT_STARTED"))
            trial_blockers: list[str] = []
            if not credential_status["configured"]:
                trial_blockers.append("Binance API-Schlüssel fehlt.")
            if not trial_settings_ok:
                trial_blockers.append(
                    "Gemeinsame Einstiegspause ist aktiv. "
                    "In Einstellungen deaktivieren und übernehmen."
                )
            if trial_state not in {"NOT_STARTED", "CANCELED"}:
                trial_blockers.append(f"50-USDC-Test ist bereits im Zustand {trial_state}.")
            if live.get("state") != "LIVE_DISABLED":
                trial_blockers.append("Normaler Livebetrieb ist nicht vollständig deaktiviert.")
            if self.runtime is None:
                trial_blockers.append("Einmaltest-Runtime ist nicht verbunden.")
            trial_available = not trial_blockers
            trial_completed = trial_state == "COMPLETED"
            production_ready = bool(
                credential_status["configured"]
                and healthy
                and trial_completed
                and production_settings_ok
                and production_plan is not None
                and self.live is not None
                and live.get("state") != "NEEDS_REVIEW"
            )
            blockers: list[str] = []
            if not credential_status["configured"]:
                blockers.append("Binance API-Schlüssel fehlt.")
            if not healthy:
                blockers.append(
                    "Marktdaten/Bot derzeit nicht vollständig gesund. "
                    "Der 50-USDC-Test kann vorbereitet werden, sendet aber erst bei HEALTHY."
                )
            if fresh is not None and fresh.get("account_checks_passed") is not True:
                blockers.append(
                    "Letzte Binance-Kontoprüfung enthält Blockierungen; "
                    "Test/Live prüfen beim Klick automatisch erneut."
                )
            if not trial_completed:
                blockers.append(
                    "Vor dauerhaftem Livebetrieb ist ein kontrollierter 1x50-Roundtrip nötig."
                )
            if not production_settings_ok:
                blockers.append("Maximalbudget oder Einstiegspause verhindert die Live-Freigabe.")
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
                "trial_blockers": trial_blockers,
                "trial_quote_asset": "USDC",
                "trial_readiness": {
                    "automatic_preflight_on_start": True,
                    "manual_account_check_required": False,
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
                    "free_slots": live.get("free_slots", 2),
                },
                "first_live_trial": {
                    "slot_count": 1,
                    "quote_asset": "USDC",
                    "target_notional_quote": "50.00",
                    "minimum_free_quote": "60.00",
                },
                "production_live": (
                    {
                        "max_capital_usdc": str(production_plan.max_capital_usdc),
                        "slot_count": production_plan.slot_count,
                        "target_notional_usdc": str(
                            production_plan.target_notional_usdc
                        ),
                        "max_committed_usdc": str(
                            production_plan.max_commitment_usdc
                        ),
                        "reserve_usdc": str(production_plan.reserve_usdc),
                        "allocator_version": production_plan.version,
                        "minimum_free_usdc_at_enable": str(
                            production_plan.max_capital_usdc
                        ),
                        "spot_only": True,
                        "quote_asset": "USDC",
                        "automatic_preflight_on_enable": True,
                        "paper_soak_required": False,
                    }
                    if production_plan is not None
                    else None
                ),
            }
