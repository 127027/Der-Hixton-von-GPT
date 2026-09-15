from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from threading import Barrier

import pytest

from hixton.live.orders import (
    ExchangeFill,
    ExchangeOrder,
    OrderJournal,
    TrialIntent,
    TrialOrderExecutor,
)

D = Decimal


def buy() -> TrialIntent:
    return TrialIntent(
        "explicit-test-intent",
        "fake-account",
        "ETHUSDC",
        "BUY",
        "test-profile",
        D("2500"),
        quote_budget=D("50"),
    )


def filled(intent: TrialIntent) -> ExchangeOrder:
    return ExchangeOrder(
        intent.client_order_id,
        "1234",
        intent.symbol,
        intent.side,
        "FILLED",
        D("0.02"),
        D("50"),
        (ExchangeFill("trade1", D("0.02"), D("2500"), D("0.00002"), "ETH"),),
    )


class FakeExchange:
    def __init__(self, response: ExchangeOrder | None, *, timeout: bool = False) -> None:
        self.response = response
        self.timeout = timeout
        self.submits = 0
        self.queries = 0

    def submit(self, intent: TrialIntent) -> ExchangeOrder:
        self.submits += 1
        if self.timeout:
            raise TimeoutError("signed URL or credentials must not be logged")
        assert self.response is not None
        return self.response

    def query(self, intent: TrialIntent) -> ExchangeOrder | None:
        self.queries += 1
        return self.response


def test_unique_client_id_and_immutable_intent(tmp_path: Path) -> None:
    intent = buy()
    journal = OrderJournal(tmp_path / "orders.sqlite3")
    assert len(intent.client_order_id) == 36
    assert intent.client_order_id != replace(intent, account_fingerprint="other").client_order_id
    assert journal.create(intent)
    assert not journal.create(intent)
    assert not journal.create(replace(intent, quote_budget=D("50.00")))
    with pytest.raises(RuntimeError, match="different parameters"):
        journal.create(replace(intent, reference_price=D("2600")))


def test_concurrent_submit_claim_has_one_winner(tmp_path: Path) -> None:
    journal = OrderJournal(tmp_path / "orders.sqlite3")
    intent = buy()
    journal.create(intent)
    exchange = FakeExchange(filled(intent))
    barrier = Barrier(2)

    def gate(_: TrialIntent) -> bool:
        barrier.wait(timeout=5)
        return True

    executor = TrialOrderExecutor(journal, exchange, gate)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: executor.execute(intent.intent_id), range(2)))
    assert results == ["FILLED", "FILLED"]
    assert exchange.submits == 1
    assert journal.fill_summary(intent.intent_id)["fill_count"] == 1


def test_record_rejects_modified_persisted_intent(tmp_path: Path) -> None:
    journal = OrderJournal(tmp_path / "orders.sqlite3")
    intent = buy()
    journal.create(intent)
    journal.claim_submit(intent.intent_id)
    modified = replace(intent, symbol="BTCUSDC")
    with pytest.raises(RuntimeError, match="differs from the persisted"):
        journal.record(modified, filled(modified))
    assert journal.fill_summary(intent.intent_id)["fill_count"] == 0


def test_terminal_exchange_state_survives_pending_fill_details(tmp_path: Path) -> None:
    journal = OrderJournal(tmp_path / "orders.sqlite3")
    intent = buy()
    journal.create(intent)
    journal.claim_submit(intent.intent_id)
    journal.record(intent, replace(filled(intent), fills=()))
    assert journal.load(intent.intent_id)[1] == "FILL_DETAILS_PENDING"
    with pytest.raises(RuntimeError, match="Terminal exchange"):
        journal.record(intent, replace(filled(intent), state="PARTIALLY_FILLED"))
    journal.record(intent, filled(intent))
    assert journal.load(intent.intent_id)[1] == "FILLED"


def test_numerically_identical_fill_is_not_a_conflict(tmp_path: Path) -> None:
    journal = OrderJournal(tmp_path / "orders.sqlite3")
    intent = buy()
    journal.create(intent)
    journal.claim_submit(intent.intent_id)
    response = filled(intent)
    journal.record(intent, response)
    journal.record(
        intent,
        replace(response, fills=(replace(response.fills[0], quantity=D("0.02000000")),)),
    )
    assert journal.fill_summary(intent.intent_id)["fill_count"] == 1


@pytest.mark.parametrize("amount", ["0", "49", "51", "NaN", "Infinity", "-50"])
def test_first_trial_buy_has_fixed_fifty_budget(amount: str) -> None:
    with pytest.raises(ValueError):
        replace(buy(), quote_budget=D(amount))


def test_closed_gate_never_submits(tmp_path: Path) -> None:
    journal = OrderJournal(tmp_path / "orders.sqlite3")
    intent = buy()
    journal.create(intent)
    exchange = FakeExchange(filled(intent))
    executor = TrialOrderExecutor(journal, exchange, lambda _: False)
    assert executor.execute(intent.intent_id) == "BLOCKED"
    assert exchange.submits == 0 and exchange.queries == 0


def test_one_submit_fill_fee_and_repeated_ui_calls(tmp_path: Path) -> None:
    journal = OrderJournal(tmp_path / "orders.sqlite3")
    intent = buy()
    journal.create(intent)
    exchange = FakeExchange(filled(intent))
    executor = TrialOrderExecutor(journal, exchange, lambda _: True)
    for _ in range(5):
        assert executor.execute(intent.intent_id) == "FILLED"
    assert exchange.submits == 1
    summary = journal.fill_summary(intent.intent_id)
    assert summary["gross_quote_usdc"] == "50.00"
    assert summary["net_received_base"] == "0.01998"
    assert summary["fees_by_asset"] == {"ETH": "0.00002"}


def test_timeout_then_restart_reconciles_without_rebuy(tmp_path: Path) -> None:
    path = tmp_path / "orders.sqlite3"
    journal = OrderJournal(path)
    intent = buy()
    journal.create(intent)
    exchange = FakeExchange(filled(intent), timeout=True)
    executor = TrialOrderExecutor(journal, exchange, lambda _: True)
    assert executor.execute(intent.intent_id) == "UNKNOWN"
    restarted = TrialOrderExecutor(OrderJournal(path), exchange, lambda _: True)
    assert restarted.execute(intent.intent_id) == "FILLED"
    assert exchange.submits == 1 and exchange.queries == 1


def test_crash_after_claim_before_send_never_guesses_retry(tmp_path: Path) -> None:
    path = tmp_path / "orders.sqlite3"
    journal = OrderJournal(path)
    intent = buy()
    journal.create(intent)
    assert journal.claim_submit(intent.intent_id)
    exchange = FakeExchange(None)
    restarted = TrialOrderExecutor(OrderJournal(path), exchange, lambda _: True)
    for _ in range(3):
        assert restarted.execute(intent.intent_id) == "UNKNOWN"
    assert exchange.submits == 0 and exchange.queries == 3


def test_partial_fill_and_duplicate_query_book_each_trade_once(tmp_path: Path) -> None:
    journal = OrderJournal(tmp_path / "orders.sqlite3")
    intent = buy()
    journal.create(intent)
    first = ExchangeFill("trade1", D("0.01"), D("2500"), D("0.00001"), "ETH")
    second = ExchangeFill("trade2", D("0.01"), D("2500"), D("0.00001"), "ETH")
    response = ExchangeOrder(
        intent.client_order_id,
        "1234",
        "ETHUSDC",
        "BUY",
        "PARTIALLY_FILLED",
        D("0.01"),
        D("25"),
        (first,),
    )
    exchange = FakeExchange(response)
    executor = TrialOrderExecutor(journal, exchange, lambda _: True)
    assert executor.execute(intent.intent_id) == "PARTIALLY_FILLED"
    assert executor.reconcile(intent.intent_id) == "PARTIALLY_FILLED"
    assert journal.fill_summary(intent.intent_id)["fill_count"] == 1
    exchange.response = replace(
        response,
        state="FILLED",
        executed_quantity=D("0.02"),
        cumulative_quote=D("50"),
        fills=(first, second),
    )
    assert executor.reconcile(intent.intent_id) == "FILLED"
    assert journal.fill_summary(intent.intent_id)["fill_count"] == 2
    assert journal.fill_summary(intent.intent_id)["net_received_base"] == "0.01998"
    assert exchange.submits == 1


def test_order_filled_without_fill_details_is_not_complete(tmp_path: Path) -> None:
    journal = OrderJournal(tmp_path / "orders.sqlite3")
    intent = buy()
    journal.create(intent)
    exchange = FakeExchange(replace(filled(intent), fills=()))
    executor = TrialOrderExecutor(journal, exchange, lambda _: True)
    assert executor.execute(intent.intent_id) == "FILL_DETAILS_PENDING"
    exchange.response = filled(intent)
    assert executor.reconcile(intent.intent_id) == "FILLED"
    assert exchange.submits == 1


def test_conflicting_trade_data_rolls_back(tmp_path: Path) -> None:
    journal = OrderJournal(tmp_path / "orders.sqlite3")
    intent = buy()
    journal.create(intent)
    journal.claim_submit(intent.intent_id)
    response = replace(filled(intent), state="PARTIALLY_FILLED")
    journal.record(intent, response)
    before = journal.fill_summary(intent.intent_id)
    conflicting = replace(response, fills=(replace(response.fills[0], commission=D("0.00003")),))
    with pytest.raises(RuntimeError, match="Conflicting duplicate"):
        journal.record(intent, conflicting)
    assert journal.fill_summary(intent.intent_id) == before


def test_wrong_response_identity_is_unknown_not_filled(tmp_path: Path) -> None:
    journal = OrderJournal(tmp_path / "orders.sqlite3")
    intent = buy()
    journal.create(intent)
    exchange = FakeExchange(replace(filled(intent), client_order_id="unrelated-order"))
    executor = TrialOrderExecutor(journal, exchange, lambda _: True)
    assert executor.execute(intent.intent_id) == "UNKNOWN"
    assert journal.fill_summary(intent.intent_id)["fill_count"] == 0


def test_bnb_commission_is_not_falsely_reported_as_usdc(tmp_path: Path) -> None:
    journal = OrderJournal(tmp_path / "orders.sqlite3")
    intent = buy()
    journal.create(intent)
    response = replace(
        filled(intent), fills=(ExchangeFill("trade1", D("0.02"), D("2500"), D("0.00005"), "BNB"),)
    )
    executor = TrialOrderExecutor(journal, FakeExchange(response), lambda _: True)
    assert executor.execute(intent.intent_id) == "FILLED"
    summary = journal.fill_summary(intent.intent_id)
    assert summary["net_received_base"] == "0.02"
    assert summary["fees_by_asset"] == {"BNB": "0.00005"}
    assert summary["fees_fully_valued_in_usdc"] is False


def test_offline_buy_sell_cycle_only_sells_received_base(tmp_path: Path) -> None:
    journal = OrderJournal(tmp_path / "orders.sqlite3")
    entry = buy()
    journal.create(entry)
    executor = TrialOrderExecutor(journal, FakeExchange(filled(entry)), lambda _: True)
    assert executor.execute(entry.intent_id) == "FILLED"
    received = D(str(journal.fill_summary(entry.intent_id)["net_received_base"]))
    exit_intent = TrialIntent(
        "explicit-test-exit",
        entry.account_fingerprint,
        "ETHUSDC",
        "SELL",
        entry.strategy_version,
        D("2510"),
        base_quantity=received,
    )
    journal.create(exit_intent)
    quote = received * D("2510")
    response = ExchangeOrder(
        exit_intent.client_order_id,
        "1235",
        "ETHUSDC",
        "SELL",
        "FILLED",
        received,
        quote,
        (ExchangeFill("trade2", received, D("2510"), quote * D("0.001"), "USDC"),),
    )
    exit_exchange = FakeExchange(response)
    closer = TrialOrderExecutor(
        journal, exit_exchange, lambda order: order.base_quantity <= received
    )
    assert closer.execute(exit_intent.intent_id) == "FILLED"
    assert exit_exchange.submits == 1
    assert D(str(journal.fill_summary(exit_intent.intent_id)["gross_quote"])) == quote


def test_quote_precision_uses_binance_cash_amount_and_rejects_changed_fill(tmp_path):
    journal = OrderJournal(tmp_path / "orders.sqlite3")
    entry = replace(buy(), symbol="ETHUSDC")
    journal.create(entry)
    journal.claim_submit(entry.intent_id)
    fill = ExchangeFill("1", D("0.3"), D("3.33333333"), D("0"), "USDC", D("1.00000000"))
    response = ExchangeOrder(
        entry.client_order_id,
        "1",
        entry.symbol,
        "BUY",
        "FILLED",
        D("0.3"),
        D("1.00000000"),
        (fill,),
    )
    journal.record(entry, response)
    assert journal.load(entry.intent_id)[1] == "FILLED"
    assert journal.fill_summary(entry.intent_id)["gross_quote"] == "1.00000000"
    with pytest.raises(RuntimeError, match="Conflicting duplicate"):
        journal.record(entry, replace(response, fills=(replace(fill, quote_quantity=D("0.999")),)))


def test_late_failed_concurrent_lookup_cannot_erase_terminal_success(tmp_path):
    journal = OrderJournal(tmp_path / "orders.sqlite3")
    entry = buy()
    journal.create(entry)
    journal.claim_submit(entry.intent_id)
    journal.record(entry, filled(entry))
    journal.unknown(entry.intent_id)
    assert journal.load(entry.intent_id)[1] == "FILLED"


def test_existing_ledger_migration_preserves_legacy_fills(tmp_path):
    import sqlite3

    path = tmp_path / "legacy.sqlite3"
    journal = OrderJournal(path)
    entry = buy()
    journal.create(entry)
    journal.claim_submit(entry.intent_id)
    journal.record(entry, filled(entry))
    before = journal.fill_summary(entry.intent_id)
    with sqlite3.connect(path) as connection:
        connection.execute("ALTER TABLE trial_fills DROP COLUMN quote_quantity")
    migrated = OrderJournal(path)
    assert migrated.fill_summary(entry.intent_id) == before
    migrated.record(entry, filled(entry))
    assert migrated.fill_summary(entry.intent_id)["fill_count"] == 1
