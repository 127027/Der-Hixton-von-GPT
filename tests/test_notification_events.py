"""Real journal schemas and isolated fills only; no exchange or network requests."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path
from uuid import uuid4

import pytest

import hixton.notifications.events as event_module
from hixton.domain.versions import V6_COIN_STRATEGY as V6
from hixton.live.orders import (
    ExchangeFill,
    ExchangeOrder,
    OrderJournal,
    TrialIntent,
    TrialOrderExecutor,
)
from hixton.live.production import LiveIntent
from hixton.live.trial import SignalTrial
from hixton.notifications.events import Notice, collect_notices
from tests.test_live_production import controller
from tests.test_live_trial import Exchange

AT = datetime(2026, 10, 21, 12, tzinfo=UTC)
SIGNAL = (AT - timedelta(hours=1)).isoformat()


class Fixture:
    def __init__(self, path: Path) -> None:
        self.live, _, _, _ = controller(path)
        self.path = path / "live.sqlite3"
        self.trial = OrderJournal(self.path)
        c = SignalTrial(
            self.trial,
            TrialOrderExecutor(self.trial, Exchange(), lambda _: True),
            V6,
            lambda: True,
        )
        self.trial_id = str(uuid4())
        c.arm(self.trial_id, "FAKE", now=AT - timedelta(hours=2), notional=D(50))

    def sql(self, query: str, values: tuple[object, ...] = ()) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(query, values)

    def order(
        self,
        identity: str,
        side: str,
        *,
        trial: bool = False,
        quantity: str = "0.5",
        price: str = "100",
        fee: str = "0",
        asset: str = "USDC",
        state: str = "FILLED",
        quote: str | None = None,
        at: datetime = AT,
        symbol: str = "XRPUSDC",
    ) -> None:
        q = D(quantity)
        intent: TrialIntent | LiveIntent
        if trial:
            intent = TrialIntent(
                identity,
                "FAKE",
                symbol,
                side,
                V6.version,
                D(price),
                quote_budget=D(50) if side == "BUY" else D(0),
                base_quantity=q if side == "SELL" else D(0),
            )
            journal = self.trial
        else:
            intent = LiveIntent(
                identity,
                "FAKE",
                symbol,
                side,
                V6.version,
                D(price),
                1,
                quote_budget=D(1000) if side == "BUY" else D(0),
                base_quantity=q if side == "SELL" else D(0),
            )
            journal = self.live.journal
        journal.create(intent)  # type: ignore[arg-type]
        journal.claim_submit(identity)
        fill = ExchangeFill(
            identity + "-trade", q, D(price), D(fee), asset, D(quote) if quote else None
        )
        journal.record(  # type: ignore[arg-type]
            intent,
            ExchangeOrder(
                intent.client_order_id,
                identity + "-order",
                symbol,
                side,
                state,
                q,
                fill.quote,
                (fill,),
            ),
        )
        prefix = "trial" if trial else "live"
        self.sql(
            f"UPDATE {prefix}_intents SET updated_at=? WHERE intent_id=?",
            (at.isoformat(), identity),
        )
        self.sql(
            f"UPDATE {prefix}_order_audit SET at_utc=? WHERE intent_id=?",
            (at.isoformat(), identity),
        )

    def trial_buy(self, **kwargs: object) -> None:
        self.order("tb", "BUY", trial=True, **kwargs)  # type: ignore[arg-type]
        self.sql(
            "UPDATE signal_trial SET buy_id='tb',symbol='XRPUSDC',state='OPEN',entry_signal_json=?",
            (json.dumps({"bar_close": SIGNAL}),),
        )

    def trial_sell(
        self, *, state: str = "COMPLETED", residual: str = "0", **kwargs: object
    ) -> None:
        self.order("ts", "SELL", trial=True, at=AT + timedelta(minutes=10), **kwargs)  # type: ignore[arg-type]
        self.sql(
            "UPDATE signal_trial SET sell_id='ts',state=?,residual_quantity=?,completed_at=?",
            (state, residual, (AT + timedelta(minutes=11)).isoformat()),
        )

    def event(
        self,
        identity: str,
        action: str,
        *,
        status: str = "FILLED",
        minute: int = 0,
        partial: bool = False,
        anchor: str | None = None,
    ) -> None:
        payload = {"partial_exit": partial, "owned_entry_signal_id": anchor}
        self.sql(
            "INSERT INTO live_events(signal_id,occurred_at_utc,symbol,action,status,reason,"
            "intent_id,payload_json) VALUES(?,?,?,?,?,NULL,?,?)",
            (
                identity + "-signal",
                (AT + timedelta(minutes=minute)).isoformat(),
                "XRPUSDC",
                action,
                status,
                identity,
                json.dumps(payload),
            ),
        )


@pytest.fixture
def data(tmp_path: Path) -> Fixture:
    return Fixture(tmp_path)


def test_missing_empty_and_paper_only_never_create_or_notify(tmp_path: Path) -> None:
    missing = tmp_path / "missing" / "db.sqlite3"
    assert collect_notices(missing) == () and not missing.parent.exists()
    path = tmp_path / "paper.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE paper_events(status TEXT)")
        connection.execute("INSERT INTO paper_events VALUES('FILLED')")
    assert collect_notices(path) == ()


def test_armed_is_silent(data: Fixture) -> None:
    assert collect_notices(data.path) == ()


@pytest.mark.parametrize("state", ["CREATED", "SUBMITTING", "UNKNOWN", "FILL_DETAILS_PENDING"])
def test_unproven_state_never_becomes_entry(data: Fixture, state: str) -> None:
    data.trial_buy()
    data.sql("UPDATE trial_intents SET state=?", (state,))
    assert collect_notices(data.path) == ()


@pytest.mark.parametrize(
    "damage", ["no_fill", "quantity", "quote", "order_id", "trade_id", "account"]
)
def test_fill_evidence_must_match_exactly(data: Fixture, damage: str) -> None:
    data.trial_buy()
    sql = {
        "no_fill": "DELETE FROM trial_fills",
        "quantity": "UPDATE trial_intents SET executed_quantity='0.6'",
        "quote": "UPDATE trial_intents SET cumulative_quote='49'",
        "order_id": "UPDATE trial_intents SET order_id=NULL",
        "trade_id": "UPDATE trial_fills SET trade_id=''",
        "account": "UPDATE trial_fills SET account='OTHER'",
    }
    data.sql(sql[damage])
    assert collect_notices(data.path) == ()


def test_entry_uses_actual_quote_net_quantity_and_recording_time(data: Fixture) -> None:
    data.trial_buy(quantity="0.49", quote="48.991", fee="0.001", asset="BNB")
    (notice,) = collect_notices(data.path)
    assert notice.kind == "entry" and notice.occurred_at == AT and notice.occurred_at.tzinfo is UTC
    assert "0.49 XRP für 48.991 USDC" in notice.body
    assert "0.001 BNB" in notice.body and "tb-order" in notice.body and "tb-trade" in notice.body
    assert SIGNAL in notice.body and "für 50 USDC" not in notice.body


def test_terminal_partial_buy_is_explicit(data: Fixture) -> None:
    data.trial_buy(quantity="0.2", state="EXPIRED")
    (notice,) = collect_notices(data.path)
    assert notice.kind == "entry" and "Teil-Ausführung" in notice.title
    assert "für 20 USDC" in notice.body


@pytest.mark.parametrize("field", ["account", "symbol"])
def test_trial_must_own_confirmed_order_account_and_symbol(data: Fixture, field: str) -> None:
    data.trial_buy()
    assert len(collect_notices(data.path)) == 1
    data.sql(f"UPDATE signal_trial SET {field}='FOREIGN'")
    assert collect_notices(data.path) == ()


def test_pending_partial_is_not_finalized_entry(data: Fixture) -> None:
    data.trial_buy(quantity="0.2", state="PARTIALLY_FILLED")
    assert collect_notices(data.path) == ()


def test_completed_trial_fees_and_cash_difference(data: Fixture) -> None:
    data.trial_buy(fee="0.001", asset="BNB")
    data.trial_sell(price="110", fee="0.002", asset="BNB")
    entry, exit_notice = collect_notices(data.path)
    assert entry.kind == "entry" and exit_notice.kind == "exit"
    assert exit_notice.occurred_at == AT + timedelta(minutes=11)
    assert "USDC-Differenz vor BNB-Gebühren: 5 USDC" in exit_notice.body
    assert "0.003 BNB" in exit_notice.body and "Rest: 0 XRP" in exit_notice.body
    assert "Kontenabgleich: bestätigt" in exit_notice.body


@pytest.mark.parametrize(
    "state,residual", [("AWAITING_RECONCILIATION", "0"), ("COMPLETED", "0.01")]
)
def test_trial_never_claims_completion_before_zero_reconciliation(
    data: Fixture,
    state: str,
    residual: str,
) -> None:
    data.trial_buy()
    data.trial_sell(state=state, residual=residual)
    notices = collect_notices(data.path)
    assert not any(n.kind == "exit" for n in notices)
    assert notices[-1].kind == "review"


def test_base_fee_is_not_lost_or_subtracted_as_quote(data: Fixture) -> None:
    data.trial_buy(fee="0.01", asset="XRP")
    data.trial_sell(quantity="0.49", price="110", fee="0.0539")
    end = collect_notices(data.path)[-1]
    assert end.kind == "exit" and "Rest: 0 XRP" in end.body
    assert "3.8461 USDC" in end.body and "0.01 XRP" in end.body


def test_live_partial_legs_and_later_same_symbol_cycles(data: Fixture) -> None:
    data.order("b1", "BUY", quantity="1", fee="0.1")
    data.event("b1", "ENTER_LONG")
    data.order("p1", "SELL", quantity="0.4", price="110", at=AT + timedelta(minutes=2))
    data.event("p1", "EXIT_LONG", minute=2, partial=True, anchor="b1-signal")
    data.order("s1", "SELL", quantity="0.6", price="120", at=AT + timedelta(minutes=3))
    data.event("s1", "EXIT_LONG", minute=3)
    data.order("b2", "BUY", quantity="0.5", at=AT + timedelta(minutes=4))
    data.event("b2", "ENTER_LONG", minute=4)
    data.order("s2", "SELL", quantity="0.5", price="90", at=AT + timedelta(minutes=5))
    data.event("s2", "EXIT_LONG", minute=5)
    notices = collect_notices(data.path)
    assert [n.kind for n in notices] == ["entry", "partial_exit", "exit", "entry", "exit"]
    assert (
        "15.9 USDC" in notices[2].body
        and "Rückfluss bisher inkl. USDC-Gebühren: 116 USDC" in notices[2].body
    )
    assert "-5 USDC" in notices[4].body and "b1-order" not in notices[4].body


@pytest.mark.parametrize("status", ["RECONCILING", "PARTIAL_REQUIRES_REVIEW"])
def test_live_sell_confirmation_is_not_account_completion(data: Fixture, status: str) -> None:
    data.order("b", "BUY")
    data.event("b", "ENTER_LONG")
    data.order("s", "SELL", at=AT + timedelta(minutes=1))
    data.event("s", "EXIT_LONG", minute=1, status=status)
    notices = collect_notices(data.path)
    assert [n.kind for n in notices] == ["entry", "review"]


def test_missing_partial_or_wrong_anchor_never_fakes_close(data: Fixture) -> None:
    data.order("b", "BUY", quantity="1")
    data.event("b", "ENTER_LONG")
    data.event(
        "unknown-partial",
        "EXIT_LONG",
        minute=1,
        status="RECONCILING",
        partial=True,
        anchor="b-signal",
    )
    data.order("s", "SELL", quantity="0.5", at=AT + timedelta(minutes=2))
    data.event("s", "EXIT_LONG", minute=2)
    assert not any(n.kind == "exit" for n in collect_notices(data.path))


def test_partial_anchor_must_match_owned_entry(data: Fixture) -> None:
    data.order("b", "BUY", quantity="1")
    data.event("b", "ENTER_LONG")
    data.order("p", "SELL", quantity="0.4", at=AT + timedelta(minutes=1))
    data.event("p", "EXIT_LONG", minute=1, partial=True, anchor="wrong-entry")
    assert [n.kind for n in collect_notices(data.path)] == ["entry"]


def test_live_settled_dust_is_reported_not_zeroed(data: Fixture) -> None:
    data.order("b", "BUY", quantity="0.5001")
    data.event("b", "ENTER_LONG")
    data.order("s", "SELL", quantity="0.5", at=AT + timedelta(minutes=1))
    data.event("s", "EXIT_LONG", minute=1)
    data.sql("INSERT INTO live_dust(symbol,quantity) VALUES('XRPUSDC','0.0001')")
    assert "Rest: 0.0001 XRP" in collect_notices(data.path)[-1].body


def test_unbooked_large_residual_is_not_a_completed_live_cycle(data: Fixture) -> None:
    data.order("b", "BUY", quantity="1")
    data.event("b", "ENTER_LONG")
    data.order("s", "SELL", quantity="0.5", at=AT + timedelta(minutes=1))
    data.event("s", "EXIT_LONG", minute=1)
    assert [n.kind for n in collect_notices(data.path)] == ["entry", "review"]


def test_archive_and_current_do_not_duplicate_restart_keys(data: Fixture) -> None:
    data.trial_buy()
    data.trial_sell()
    original = collect_notices(data.path)
    # A later exchange re-query must not turn an old archived buy into a new event.
    data.sql("UPDATE trial_intents SET updated_at=?", ((AT + timedelta(days=1)).isoformat(),))
    with sqlite3.connect(data.path) as connection:
        connection.row_factory = sqlite3.Row
        payload = {
            "trial": dict(connection.execute("SELECT * FROM signal_trial").fetchone()),
            "intents": [dict(r) for r in connection.execute("SELECT * FROM trial_intents")],
            "fills": [dict(r) for r in connection.execute("SELECT * FROM trial_fills")],
        }
        connection.execute(
            "CREATE TABLE trial_archives(trial_id TEXT PRIMARY KEY,payload_json TEXT)"
        )
        connection.execute(
            "INSERT INTO trial_archives VALUES(?,?)", (data.trial_id, json.dumps(payload))
        )
    assert collect_notices(data.path) == original
    data.sql("DELETE FROM signal_trial")
    assert [n.key for n in collect_notices(data.path)] == [n.key for n in original]
    assert collect_notices(data.path) == collect_notices(data.path)


def test_reader_does_not_migrate_or_write_and_allows_existing_writer(data: Fixture) -> None:
    data.trial_buy()
    before = hashlib.sha256(data.path.read_bytes()).hexdigest()
    writer = sqlite3.connect(data.path)
    try:
        writer.execute("BEGIN IMMEDIATE")
        (notice,) = collect_notices(data.path)
        assert isinstance(notice, Notice)
    finally:
        writer.rollback()
        writer.close()
    assert hashlib.sha256(data.path.read_bytes()).hexdigest() == before


def test_ids_are_explicitly_abbreviated_but_totals_preserved(data: Fixture) -> None:
    data.order("b", "BUY", quantity="10")
    data.event("b", "ENTER_LONG")
    for i in range(1, 11):
        data.order(f"p{i}", "SELL", quantity="0.5", at=AT + timedelta(minutes=i))
        data.event(f"p{i}", "EXIT_LONG", minute=i, partial=True, anchor="b-signal")
    last = collect_notices(data.path)[-1]
    assert (
        last.kind == "partial_exit"
        and "Rückfluss bisher inkl. USDC-Gebühren: 500 USDC" in last.body
    )
    assert "11 Orders" in last.body and "lokalen Ausführungsbericht" in last.body
    assert len(last.body) <= 3300


def test_coherent_transaction_keeps_fill_revision_with_prior_order(
    data: Fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data.trial_buy()
    with sqlite3.connect(data.path) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
    original = event_module._rows
    changed = False

    def rows(connection: sqlite3.Connection, table: str) -> list[dict[str, object]]:
        nonlocal changed
        result = original(connection, table)
        if table == "trial_intents" and not changed:
            changed = True
            data.sql("UPDATE trial_fills SET quantity='0.6'")
        return result

    monkeypatch.setattr(event_module, "_rows", rows)
    assert len(collect_notices(data.path)) == 1  # Earlier coherent transaction snapshot.
    assert collect_notices(data.path) == ()  # Next transaction sees inconsistent new data.


def test_first_confirmation_time_does_not_advance_on_later_order_query(data: Fixture) -> None:
    data.trial_buy()
    (first,) = collect_notices(data.path)
    data.sql("UPDATE trial_intents SET updated_at=?", ((AT + timedelta(days=1)).isoformat(),))
    data.sql(
        "INSERT INTO trial_order_audit(intent_id,action,at_utc) VALUES('tb','FILLED',?)",
        ((AT + timedelta(days=1)).isoformat(),),
    )
    assert collect_notices(data.path) == (first,)


def test_many_fills_keep_exact_totals_and_explicit_id_count(data: Fixture) -> None:
    data.trial_buy()
    with sqlite3.connect(data.path) as connection:
        connection.execute("DELETE FROM trial_fills")
        connection.executemany(
            "INSERT INTO trial_fills(account,symbol,trade_id,intent_id,quantity,price,"
            "commission,commission_asset,quote_quantity) VALUES(?,?,?,?,?,?,?,?,?)",
            [
                ("FAKE", "XRPUSDC", str(i), "tb", "0.001", "100", "0.000001", "BNB", "0.1")
                for i in range(500)
            ],
        )
    (notice,) = collect_notices(data.path)
    assert "0.5 XRP für 50 USDC" in notice.body and "0.0005 BNB" in notice.body
    assert "500 Trades" in notice.body and "ID-Auswahl" in notice.body
    assert len(notice.body) <= 3300


def test_legacy_usdt_is_never_relabelled_as_usdc(data: Fixture) -> None:
    data.trial_buy(symbol="XRPUSDT", asset="USDT")
    data.sql("UPDATE signal_trial SET symbol='XRPUSDT'")
    (notice,) = collect_notices(data.path)
    assert "XRP/USDT" in notice.body and "50-USDT-Test" in notice.title
    assert "USDC" not in notice.body
