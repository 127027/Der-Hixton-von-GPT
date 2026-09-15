"""Exact, persistent balance conservation for a single isolated trial ledger.

An unchanged foreign holding is never owned by the bot. This is a necessary
balance proof, not proof that no offsetting manual trades happened in between.
Production release still requires the separate order-history/operational audit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from hixton.domain.markets import split_market
from hixton.live.exchange import SpotTransport
from hixton.live.orders import OrderJournal

ZERO = Decimal(0)
FINAL = {"FILLED", "CANCELED", "REJECTED", "EXPIRED", "EXPIRED_IN_MATCH"}


@dataclass(frozen=True)
class AccountSnapshot:
    account: str
    observed_at: datetime
    balances: dict[str, tuple[Decimal, Decimal]]
    open_orders: tuple[str, ...]

    def validate(self, now: datetime) -> None:
        if not self.account or now.tzinfo is None or self.observed_at.tzinfo is None:
            raise ValueError("Account identity and timezone-aware clocks required")
        if not 0 <= (now - self.observed_at).total_seconds() <= 15:
            raise ValueError("Account snapshot expired or from the future")
        for asset, (free, locked) in self.balances.items():
            if not asset or not asset.isascii() or not asset.isalnum():
                raise ValueError("Invalid account asset")
            if any(not amount.is_finite() or amount < 0 for amount in (free, locked)):
                raise ValueError("Invalid account balance")


def _balances(payload: Any) -> dict[str, tuple[Decimal, Decimal]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("balances"), list):
        raise ValueError("Incomplete account snapshot")
    result = {}
    for row in payload["balances"]:
        if not isinstance(row, dict) or not isinstance(row.get("asset"), str):
            raise ValueError("Invalid balance row")
        asset = row["asset"]
        if asset in result or not all(isinstance(row.get(key), str) for key in ("free", "locked")):
            raise ValueError("Duplicate or non-decimal balance row")
        result[asset] = (Decimal(row["free"]), Decimal(row["locked"]))
    return result


def read_account_snapshot(transport: SpotTransport, *, account: str) -> AccountSnapshot:
    """Read twice around openOrders: an inconsistent moving account cannot pass."""
    before = datetime.now(UTC)
    first = _balances(transport.request("GET", "/api/v3/account", {}))
    orders = transport.request("GET", "/api/v3/openOrders", {})
    second = _balances(transport.request("GET", "/api/v3/account", {}))
    if first != second or not isinstance(orders, list):
        raise ValueError("Account changed during snapshot; retry read-only")
    identities = []
    for row in orders:
        if not isinstance(row, dict) or not isinstance(row.get("clientOrderId"), str):
            raise ValueError("Incomplete open-order response")
        identities.append(row["clientOrderId"])
    snapshot = AccountSnapshot(account, before, first, tuple(identities))
    snapshot.validate(datetime.now(UTC))
    return snapshot


class TrialReconciler:
    """Durable immutable baseline plus actual journal fills; no UI 'matches' flag."""

    def __init__(self, journal: OrderJournal):
        self.journal = journal
        with journal._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS trial_account_baseline ("
                "singleton INTEGER PRIMARY KEY CHECK(singleton=1), account TEXT NOT NULL, "
                "observed_at TEXT NOT NULL, balances_json TEXT NOT NULL)"
            )

    def capture(self, snapshot: AccountSnapshot, *, now: datetime) -> None:
        snapshot.validate(now)
        if snapshot.open_orders or any(locked != 0 for _, locked in snapshot.balances.values()):
            raise ValueError("Baseline requires no open orders or locked balances")
        encoded = json.dumps(
            {asset: str(free) for asset, (free, _) in snapshot.balances.items()}, sort_keys=True
        )
        with self.journal._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM trial_intents LIMIT 1").fetchone():
                raise RuntimeError("Cannot establish baseline after an order intent")
            if connection.execute("SELECT 1 FROM trial_account_baseline").fetchone():
                raise RuntimeError("Account baseline cannot be replaced")
            connection.execute(
                "INSERT INTO trial_account_baseline VALUES(1,?,?,?)",
                (snapshot.account, snapshot.observed_at.isoformat(), encoded),
            )
            self.journal._audit(connection, "ACCOUNT", "BASELINE_CAPTURED")

    def check(self, snapshot: AccountSnapshot, *, now: datetime) -> dict[str, object]:
        snapshot.validate(now)
        with self.journal._connect() as connection:
            baseline = connection.execute("SELECT * FROM trial_account_baseline").fetchone()
            intents = connection.execute("SELECT * FROM trial_intents").fetchall()
            fills = connection.execute(
                "SELECT f.*, i.side FROM trial_fills f JOIN trial_intents i USING(intent_id)"
            ).fetchall()
        if baseline is None:
            raise RuntimeError("Persisted pre-trade account baseline missing")
        if baseline["account"] != snapshot.account:
            raise RuntimeError("Account identity mismatch")
        if any(row["account"] != snapshot.account for row in intents):
            raise RuntimeError("Foreign journal account")
        expected = {
            asset: Decimal(value) for asset, value in json.loads(baseline["balances_json"]).items()
        }
        movements: dict[str, Decimal] = {}

        def move(asset: str, amount: Decimal) -> None:
            movements[asset] = movements.get(asset, ZERO) + amount
            expected[asset] = expected.get(asset, ZERO) + amount

        for fill in fills:
            base, quote = split_market(fill["symbol"])
            sign = Decimal(1) if fill["side"] == "BUY" else Decimal(-1)
            move(base, sign * Decimal(fill["quantity"]))
            move(quote, -sign * self.journal._fill_quote(fill))
            move(fill["commission_asset"], -Decimal(fill["commission"]))
        mismatches = sorted(
            asset
            for asset in expected.keys() | snapshot.balances.keys()
            if expected.get(asset, ZERO) != sum(snapshot.balances.get(asset, (ZERO, ZERO)))
        )
        unresolved = [row["intent_id"] for row in intents if row["state"] not in FINAL]
        locked = any(amount != 0 for _, amount in snapshot.balances.values())
        passed = not (mismatches or unresolved or locked or snapshot.open_orders)
        with self.journal._connect() as connection:
            self.journal._audit(
                connection, "ACCOUNT", "BALANCES_MATCH" if passed else "BALANCES_UNRESOLVED"
            )
        return {
            "balances_match": passed,
            "no_open_orders": not snapshot.open_orders,
            "mismatched_assets": mismatches,
            "unresolved_intents": unresolved,
            "movements": {asset: str(value) for asset, value in movements.items()},
            "observed_at_utc": snapshot.observed_at.isoformat(),
        }

    def complete_if_proven(self, trial: Any, snapshot: AccountSnapshot, *, now: datetime) -> bool:
        with trial.lock:
            report = trial.report()
            if report["state"] != "AWAITING_RECONCILIATION":
                return False
            proof = self.check(snapshot, now=now)
            base, _ = split_market(str(report["symbol"]))
            movements = proof["movements"]
            assert isinstance(movements, dict)
            remaining = Decimal(movements.get(base, "0"))
            if proof["balances_match"] is not True or remaining != ZERO:
                return False
            trial.confirm_reconciled(
                no_open_orders=True, owned_remaining=remaining, account_matches=True, now=now
            )
            return True
