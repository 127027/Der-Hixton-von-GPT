"""Brief real-money summaries with honest cumulative PnL and fresh balances."""

import json
import sqlite3
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D

import pytest

from hixton.notifications.compact import balance_line, compact_message
from hixton.notifications.events import collect_notices
from tests.test_notification_events import AT, Fixture
from tests.test_notifications import save, setup_service


def automatic_trial(data):
    data.trial_buy(fee="0.001", asset="BNB")
    data.sql("UPDATE signal_trial SET entry_signal_json=?", (json.dumps({
        "bar_close": AT.isoformat(), "reason": "HIXTON_ENTER_LONG",
    }),))
    data.sql("INSERT INTO trial_order_audit(intent_id,action,at_utc) VALUES(?,?,?)",
             (data.trial_id, "ENTRY_RESERVED", AT.isoformat()))
    data.trial_sell(price="110", fee="0.002", asset="BNB")
    data.sql("UPDATE signal_trial SET exit_signal_json=?", (json.dumps({
        "bar_close": AT.isoformat(), "reason": "HIXTON_EXIT_LONG",
    }),))
    data.sql("INSERT INTO trial_order_audit(intent_id,action,at_utc) VALUES(?,?,?)",
             (data.trial_id, "EXIT_RESERVED", AT.isoformat()))


def current_balance(at, free="1050", total="1050"):
    return {"state": "CURRENT", "free_usdc": free, "total_usdc": total,
            "observed_at_utc": at.isoformat()}


def test_trial_compact_summary_excludes_internal_ids_and_preserves_precise_detail(tmp_path):
    data = Fixture(tmp_path)
    automatic_trial(data)
    entry, exit_notice = collect_notices(data.path)
    title, body = compact_message(exit_notice)
    assert "beendet" in title and "XRP/USDC" in title
    assert "50,00 → 55,00 USDC · +5,00 USDC vor BNB" in body
    assert "Bot abgeschlossen (1): +5,00 USDC vor BNB" in body
    assert "0.003 BNB" in body and "Abgleich OK" in body
    assert "Order" not in body and "Strategie-Signal" not in body
    assert len(body.splitlines()) <= 6
    assert "tb-order" in exit_notice.body and "Strategie-Signal" in entry.body
    assert entry.trade.completed_count == 0


def test_only_final_cycle_counts_partial_cash_returns_once_and_future_not_backfilled(tmp_path):
    data = Fixture(tmp_path)
    data.order("b1", "BUY", quantity="1", fee="0.1")
    data.event("b1", "ENTER_LONG")
    data.order("p1", "SELL", quantity="0.4", price="110", at=AT + timedelta(minutes=2))
    data.event("p1", "EXIT_LONG", minute=2, partial=True, anchor="b1-signal")
    data.order("s1", "SELL", quantity="0.6", price="120", at=AT + timedelta(minutes=3))
    data.event("s1", "EXIT_LONG", minute=3)
    data.order("b2", "BUY", quantity="1", at=AT + timedelta(minutes=4))
    data.event("b2", "ENTER_LONG", minute=4)
    data.order("s2", "SELL", quantity="1", price="90", at=AT + timedelta(minutes=5))
    data.event("s2", "EXIT_LONG", minute=5)
    notices = collect_notices(data.path)
    assert [n.trade.total_realized for n in notices] == [D(0), D(0), D("15.9"), D("15.9"), D("5.9")]
    assert [n.trade.completed_count for n in notices] == [0, 0, 1, 1, 2]
    assert "kein endgültiges Ergebnis" in compact_message(notices[1])[1]


def test_manual_test_and_residual_dust_are_not_summed_as_realized_bot_profit(tmp_path):
    data = Fixture(tmp_path / "manual")
    data.trial_buy()
    data.trial_sell(price="110")
    assert collect_notices(data.path)[-1].trade.completed_count == 0
    data = Fixture(tmp_path / "automatic")
    automatic_trial(data)
    data.sql("UPDATE signal_trial SET residual_quantity='0.001'")
    assert collect_notices(data.path)[-1].kind == "review"
    assert collect_notices(data.path)[-1].trade.completed_count == 0


def test_completed_live_dust_is_disclosed_and_excluded_from_total_profit(tmp_path):
    data = Fixture(tmp_path)
    data.order("b", "BUY", quantity="1")
    data.event("b", "ENTER_LONG")
    data.order("s", "SELL", quantity="0.99", price="110", at=AT + timedelta(minutes=1))
    data.event("s", "EXIT_LONG", minute=1)
    data.sql("INSERT INTO live_dust(symbol,quantity) VALUES(?,?)", ("XRPUSDC", "0.01"))
    notice = collect_notices(data.path)[-1]
    assert notice.kind == "exit"
    assert notice.trade.completed_count == 0
    assert "nicht bewertet" in compact_message(notice)[1]


def test_total_profit_is_separate_for_each_api_key(tmp_path):
    data = Fixture(tmp_path)
    for index, account in enumerate(("FAKE", "OTHER")):
        buy, sell = f"buy{index}", f"sell{index}"
        data.order(buy, "BUY", quantity="1", at=AT + timedelta(minutes=index * 3))
        data.event(buy, "ENTER_LONG", minute=index * 3)
        data.order(sell, "SELL", quantity="1", price="110",
                   at=AT + timedelta(minutes=index * 3 + 1))
        data.event(sell, "EXIT_LONG", minute=index * 3 + 1)
        for table in ("live_intents", "live_fills"):
            data.sql(f"UPDATE {table} SET account=? WHERE intent_id IN (?,?)", (account, buy, sell))
    last = collect_notices(data.path)[-1].trade
    assert last.account == "OTHER" and last.completed_count == 1 and last.total_realized == D(10)


def test_operator_exit_after_automatic_buy_is_not_automatic_strategy_profit(tmp_path):
    data = Fixture(tmp_path)
    automatic_trial(data)
    data.sql("UPDATE signal_trial SET exit_signal_json=?",
             (json.dumps({"reason": "MANUAL_OPERATOR_TEST"}),))
    last = collect_notices(data.path)[-1]
    assert last.kind == "exit" and last.trade.completed_count == 0


@pytest.mark.parametrize("damage", ["stale", "pre-fill", "missing", "NaN", "negative", "foreign"])
def test_balance_never_invents_current_budget(damage):
    now = AT + timedelta(minutes=1)
    payload = current_balance(now)
    quote = "USDC"
    if damage == "stale":
        payload["observed_at_utc"] = AT.isoformat()
    elif damage == "pre-fill":
        payload["observed_at_utc"] = (AT - timedelta(seconds=1)).isoformat()
    elif damage == "missing":
        payload = {}
    elif damage == "NaN":
        payload["free_usdc"] = "NaN"
    elif damage == "negative":
        payload["free_usdc"] = "-1"
    else:
        quote = "USDT"
    assert "nicht verfügbar" in balance_line(payload, quote=quote, after=AT, now=now)


def test_fresh_balance_has_total_free_and_own_observation_time():
    now = AT + timedelta(minutes=1)
    text = balance_line(current_balance(now, "1000", "1050"), quote="USDC", after=AT, now=now)
    assert "1.050,00" in text and "frei 1.000,00" in text and "Stand 14:01:00" in text


def test_retry_seals_event_summary_but_refreshes_budget_for_each_attempt(tmp_path):
    data = Fixture(tmp_path / "fills")
    automatic_trial(data)
    original = collect_notices(data.path)[-1]
    service, sender, notices, clock = setup_service(tmp_path / "delivery")
    clock[0] = AT - timedelta(minutes=1)
    save(service)
    notices.append(original)
    clock[0] = AT + timedelta(minutes=12)
    service.balance_provider = lambda _: current_balance(clock[0], "1050", "1050")
    sender.fail = True
    service.cycle()
    notices[0] = replace(original, trade=replace(original.trade, total_realized=D(999)))
    clock[0] += timedelta(minutes=10)
    sender.fail = False
    service.balance_provider = lambda _: current_balance(clock[0], "1099", "1099")
    service.cycle()
    assert len(sender.sent) == 1
    body = sender.sent[0][2]
    assert "Bot abgeschlossen (1): +5,00" in body and "999" not in body
    assert "1.099,00" in body and "1.050,00" not in body
    assert "Meldung:" not in body and "Order" not in body
    with sqlite3.connect(service.path) as connection:
        detail, delivered = connection.execute(
            "SELECT detail_body,last_payload FROM notification_outbox"
        ).fetchone()
        assert "tb-order" in detail and delivered == body


def test_failed_balance_read_still_sends_the_execution_with_explicit_warning(tmp_path):
    data = Fixture(tmp_path / "fills")
    automatic_trial(data)
    service, sender, notices, clock = setup_service(tmp_path / "delivery")
    clock[0] = AT - timedelta(minutes=1)
    save(service)
    notices.append(collect_notices(data.path)[-1])
    clock[0] = AT + timedelta(minutes=12)

    def unavailable(_):
        raise OSError("simulated account outage")

    service.balance_provider = unavailable
    service.cycle()
    assert len(sender.sent) == 1
    assert "Binance-USDC-Stand nicht verfügbar" in sender.sent[0][2]
    assert "+5,00 USDC vor BNB" in sender.sent[0][2]


def test_runtime_never_attaches_another_keys_balance(tmp_path, monkeypatch):
    from hixton.live.credentials import BinanceCredentials
    from tests.test_live_preparation import KEY, SECRET, client_for

    reads = []

    class Display:
        def __init__(self, *args, **kwargs):
            assert kwargs["refresh_seconds"] == 0

        def read(self):
            reads.append(True)
            return current_balance(AT)

    monkeypatch.setattr("hixton.ui.live.AccountBalanceDisplay", Display)
    client, _, service = client_for(tmp_path)
    credentials = BinanceCredentials(KEY, SECRET)
    service.credentials.save(credentials)
    provider = client.app.state.notifications.balance_provider
    assert provider("another-key") == {} and reads == []
    assert provider(credentials.fingerprint)["free_usdc"] == "1050" and len(reads) == 1
