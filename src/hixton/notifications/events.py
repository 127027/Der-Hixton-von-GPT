"""Read-only, coherent projections of confirmed real execution ledgers.

No Paper data, activation decisions, delivery state or exchange calls belong here.
The ledger does not retain Binance execution timestamps: ``occurred_at`` is the
first terminal confirmation recorded by this journal, never a candle timestamp.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast

from hixton.domain.markets import split_market

_ZERO = Decimal(0)
_TERMINAL = frozenset({"FILLED", "CANCELED", "EXPIRED", "EXPIRED_IN_MATCH", "REJECTED"})
_Row = dict[str, object]


@dataclass(frozen=True)
class Notice:
    key: str
    kind: str
    occurred_at: datetime
    title: str
    body: str


@dataclass(frozen=True)
class _Order:
    identity: str
    account: str
    symbol: str
    side: str
    order_id: str
    state: str
    quantity: Decimal
    quote: Decimal
    fees: dict[str, Decimal]
    trades: tuple[str, ...]
    recorded: datetime


@dataclass
class _Cycle:
    signal_id: str
    buy: _Order
    sells: list[_Order]
    valid: bool = True


def _text(row: _Row, name: str) -> str:
    value = row.get(name)
    return value if isinstance(value, str) else ""


def _number(value: object) -> Decimal:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise ValueError("Missing execution amount")
    number = Decimal(value)
    if not number.is_finite() or number < 0:
        raise ValueError("Invalid execution amount")
    return number


def _time(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Missing execution recording time")
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Unproven execution timezone")
    return result.astimezone(UTC)


def _json(value: object) -> _Row:
    try:
        result: object = json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        return {}
    if not isinstance(result, dict) or not all(isinstance(k, str) for k in result):
        return {}
    return cast(_Row, result)


def _records(value: object) -> list[_Row]:
    return [_json(row) for row in value] if isinstance(value, list) else []


def _rows(connection: sqlite3.Connection, table: str) -> list[_Row]:
    # Callers supply fixed internal table names, never request/user values.
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if exists is None:
        return []
    return [dict(row) for row in connection.execute(f'SELECT * FROM "{table}"')]


def _confirmed(intents: list[_Row], fills: list[_Row], audit: list[_Row]) -> dict[str, _Order]:
    result: dict[str, _Order] = {}
    for intent in intents:
        identity = _text(intent, "intent_id")
        state = _text(intent, "state")
        symbol = _text(intent, "symbol")
        side = _text(intent, "side")
        order_id = _text(intent, "order_id")
        if (
            not identity
            or not order_id
            or side not in {"BUY", "SELL"}
            or state not in _TERMINAL
            or _text(intent, "exchange_state") != state
        ):
            continue
        try:
            split_market(symbol)
            owned = [f for f in fills if _text(f, "intent_id") == identity]
            quantity, quote = _ZERO, _ZERO
            fees: dict[str, Decimal] = {}
            trade_ids: set[str] = set()
            for fill in owned:
                trade_id = _text(fill, "trade_id")
                asset = _text(fill, "commission_asset")
                if (
                    not trade_id
                    or trade_id in trade_ids
                    or not asset
                    or _text(fill, "symbol") != symbol
                    or _text(fill, "account") != _text(intent, "account")
                ):
                    raise ValueError("Inconsistent fill identity")
                q, price = _number(fill.get("quantity")), _number(fill.get("price"))
                amount = (
                    _number(fill["quote_quantity"])
                    if fill.get("quote_quantity") is not None
                    else q * price
                )
                if q <= 0 or price <= 0 or amount <= 0:
                    raise ValueError("Empty fill")
                trade_ids.add(trade_id)
                quantity += q
                quote += amount
                fees[asset] = fees.get(asset, _ZERO) + _number(fill.get("commission"))
            if (
                not trade_ids
                or quantity <= 0
                or quote <= 0
                or quantity != _number(intent.get("executed_quantity"))
                or quote != _number(intent.get("cumulative_quote"))
            ):
                continue
            confirmations = [
                _time(row.get("at_utc"))
                for row in audit
                if _text(row, "intent_id") == identity and _text(row, "action") == state
            ]
            recorded = min(confirmations) if confirmations else _time(intent.get("updated_at"))
            result[identity] = _Order(
                identity,
                _text(intent, "account"),
                symbol,
                side,
                order_id,
                state,
                quantity,
                quote,
                fees,
                tuple(sorted(trade_ids)),
                recorded,
            )
        except (ValueError, InvalidOperation, OverflowError):
            continue  # Unproven execution is never presented as a real trade.
    return result


def _amount(value: Decimal) -> str:
    exponent = value.as_tuple().exponent
    if value.adjusted() > 30 or (isinstance(exponent, int) and exponent < -30):
        return str(value)
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _fees(orders: list[_Order]) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for order in orders:
        for asset, amount in order.fees.items():
            totals[asset] = totals.get(asset, _ZERO) + amount
    return totals


def _fee_text(fees: dict[str, Decimal]) -> str:
    return ", ".join(f"{_amount(v)} {a}" for a, v in sorted(fees.items()) if v) or "0"


def _ids(order: _Order) -> str:
    ids = order.trades if len(order.trades) <= 4 else (*order.trades[:3], order.trades[-1])

    def short(value: str) -> str:
        return value if len(value) <= 36 else value[:33] + "…"

    limited = len(ids) != len(order.trades) or any(len(t) > 36 for t in ids)
    limited = limited or len(order.order_id) > 36
    return (
        f"Order {short(order.order_id)}; {len(order.trades)} Trades: "
        + ", ".join(short(t) for t in ids)
        + (" (ID-Auswahl; alle IDs im lokalen Ausführungsbericht)" if limited else "")
    )


def _order_ids(orders: list[_Order]) -> str:
    selected = orders if len(orders) <= 6 else orders[:3] + orders[-3:]
    text = "\n".join(_ids(order) for order in selected)
    if len(selected) != len(orders):
        text += (
            f"\nID-Auswahl aus {len(orders)} Orders / "
            f"{sum(len(o.trades) for o in orders)} Trades; alle IDs im lokalen Ausführungsbericht."
        )
    return text


def _stamp(at: datetime) -> str:
    return at.isoformat(timespec="milliseconds")


def _entry(key: str, label: str, buy: _Order, signal_time: object) -> Notice:
    base, quote = split_market(buy.symbol)
    partial = " · Teil-Ausführung" if buy.state != "FILLED" else ""
    return Notice(
        key,
        "entry",
        buy.recorded,
        f"{label} · Echtkauf bestätigt{partial}",
        f"{base}/{quote}\n"
        f"Tatsächlich gekauft: {_amount(buy.quantity)} {base} für {_amount(buy.quote)} {quote}\n"
        f"Mittlerer Fillpreis: {_amount(buy.quote / buy.quantity)} {quote}/{base}\n"
        f"Gebühren: {_fee_text(buy.fees)}\n"
        f"Binance-Bestätigung erfasst: {_stamp(buy.recorded)}\n"
        f"Strategie-Signal: {signal_time or 'nicht gespeichert'}\n{_ids(buy)}",
    )


def _remaining(buy: _Order, sells: list[_Order]) -> Decimal:
    base, _ = split_market(buy.symbol)
    return (
        buy.quantity
        - buy.fees.get(base, _ZERO)
        - sum((s.quantity + s.fees.get(base, _ZERO) for s in sells), _ZERO)
    )


def _exit(
    key: str,
    label: str,
    buy: _Order,
    sells: list[_Order],
    *,
    partial: bool,
    at: datetime | None = None,
    reconciled: bool = True,
) -> Notice | None:
    base, quote = split_market(buy.symbol)
    remaining = _remaining(buy, sells)
    if remaining < 0 or not sells or (partial and remaining == 0):
        return None
    fees = _fees([buy, *sells])
    spent = buy.quote + buy.fees.get(quote, _ZERO)
    received = sum((s.quote - s.fees.get(quote, _ZERO) for s in sells), _ZERO)
    foreign = sorted(
        asset for asset, amount in fees.items() if asset not in {base, quote} and amount
    )
    delta_label = (
        f"{quote}-Differenz vor {'/'.join(foreign)}-Gebühren"
        if foreign
        else f"{quote}-Cashdifferenz"
    )
    recorded = at or sells[-1].recorded
    suffix = (
        "Teilverkauf bestätigt · Position bleibt offen"
        if partial
        else "Position beendet"
        if reconciled
        else "Verkauf bestätigt · Abschluss noch ungeklärt"
    )
    details = (
        f"{base}/{quote}\nEinsatz inkl. {quote}-Gebühren: {_amount(spent)} {quote}\n"
        f"Rückfluss bisher inkl. {quote}-Gebühren: {_amount(received)} {quote}\n"
        f"{delta_label}: {_amount(received - spent)} {quote}"
        f"{' (kein abgeschlossenes Ergebnis)' if partial else ''}\n"
        f"Gebühren gesamt: {_fee_text(fees)}\nRest: {_amount(remaining)} {base}\n"
        + ("Cashdifferenz ohne Bewertung des Restbestands.\n" if remaining else "")
        + f"Kontenabgleich: {'bestätigt' if reconciled else 'noch offen; kein Abschluss'}\n"
        f"Beginn (Binance-Bestätigung erfasst): {_stamp(buy.recorded)}\n"
        f"Letzter Verkauf erfasst: {_stamp(sells[-1].recorded)}\n"
        f"{'Meldung erfasst' if partial or not reconciled else 'Abschluss erfasst'}: "
        f"{_stamp(recorded)}\n" + _order_ids([buy, *sells])
    )
    kind = "partial_exit" if partial else "exit" if reconciled else "review"
    return Notice(key, kind, recorded, f"{label} · {suffix}", details)


def _trial_notices(
    trial: _Row, intents: list[_Row], fills: list[_Row], audit: list[_Row]
) -> list[Notice]:
    identity = _text(trial, "trial_id")
    orders = _confirmed(intents, fills, audit)
    buy = orders.get(_text(trial, "buy_id"))
    if (
        not identity
        or buy is None
        or buy.side != "BUY"
        or _text(trial, "symbol") != buy.symbol
        or _text(trial, "account") != buy.account
    ):
        return []
    signal = _json(trial.get("entry_signal_json"))
    label = f"50-{split_market(buy.symbol)[1]}-Test"
    notices = [
        _entry(f"trial:{identity}:entry:{buy.identity}", label, buy, signal.get("bar_close"))
    ]
    sell = orders.get(_text(trial, "sell_id"))
    if (
        sell is None
        or sell.side != "SELL"
        or sell.symbol != buy.symbol
        or sell.account != buy.account
    ):
        return notices
    try:
        settled = (
            _text(trial, "state") == "COMPLETED"
            and _number(trial.get("residual_quantity")) == 0
            and _remaining(buy, [sell]) == 0
            and buy.state == sell.state == "FILLED"
        )
        at = max(_time(trial.get("completed_at")), sell.recorded) if settled else sell.recorded
    except (ValueError, InvalidOperation):
        settled, at = False, sell.recorded
    partial = _remaining(buy, [sell]) > 0
    kind = "exit" if settled else "partial_exit" if partial else "review"
    notice = _exit(
        f"trial:{identity}:{kind}:{sell.identity}",
        label,
        buy,
        [sell],
        partial=partial,
        at=at,
        reconciled=settled,
    )
    if notice is not None:
        notices.append(notice)
    return notices


def _live_notices(
    events: list[_Row], orders: dict[str, _Order], dust_rows: list[_Row]
) -> list[Notice]:
    notices: list[Notice] = []
    cycles: dict[str, _Cycle] = {}
    dust: dict[str, Decimal] = {}
    for row in dust_rows:
        try:
            dust[_text(row, "symbol")] = _number(row.get("quantity"))
        except (ValueError, InvalidOperation):
            continue
    # Signal boundaries establish causal ownership; recording times can be delayed
    # by recovery. They are never reused as Notice.occurred_at.
    ordered = sorted(
        events,
        key=lambda e: (_text(e, "occurred_at_utc"), _text(e, "signal_id")),
    )
    for event in ordered:
        if _text(event, "status") == "BLOCKED":
            continue
        order = orders.get(_text(event, "intent_id"))
        if order is None:
            cycle = cycles.get(_text(event, "symbol"))
            if cycle is not None:
                cycle.valid = False  # Missing confirmed leg cannot become a complete cycle.
            continue
        if order.symbol != _text(event, "symbol"):
            continue
        identity = _text(event, "signal_id")
        if not identity:
            continue
        prefix = f"live:{identity}"
        if _text(event, "action") == "ENTER_LONG" and order.side == "BUY":
            notices.append(
                _entry(
                    f"{prefix}:entry:{order.identity}", "Live", order, event.get("occurred_at_utc")
                )
            )
            cycles[order.symbol] = _Cycle(identity, order, [], _text(event, "status") == "FILLED")
        elif _text(event, "action") == "EXIT_LONG" and order.side == "SELL":
            cycle = cycles.get(order.symbol)
            if cycle is None:
                continue  # No guessed ownership or synthesized BUY from a SELL.
            payload = _json(event.get("payload_json"))
            partial = payload.get("partial_exit") is True
            anchor = _text(payload, "owned_entry_signal_id")
            if (
                order.account != cycle.buy.account
                or (partial and anchor != cycle.signal_id)
                or (anchor and anchor != cycle.signal_id)
            ):
                cycle.valid = False
                continue
            cycle.sells.append(order)
            settled = cycle.valid and _text(event, "status") == "FILLED"
            remaining = _remaining(cycle.buy, cycle.sells)
            if not partial and settled and remaining > 0:
                # Positive residual is only an accepted final dust balance when
                # the real ownership ledger explicitly booked it as such.
                available = dust.get(order.symbol, _ZERO)
                if remaining > available:
                    settled = False
                else:
                    dust[order.symbol] = available - remaining
            kind = "partial_exit" if partial else "exit" if settled else "review"
            notice = _exit(
                f"{prefix}:{kind}:{order.identity}",
                "Live",
                cycle.buy,
                cycle.sells,
                partial=partial,
                reconciled=settled,
            )
            if notice is not None:
                notices.append(notice)
            if not settled:
                cycle.valid = False
            if not partial:
                cycles.pop(order.symbol)
    return notices


def collect_notices(database: Path) -> tuple[Notice, ...]:
    """Project durable confirmed fills from one explicit SQLite read transaction.

    Missing databases/tables produce no trades. Storage errors propagate to the
    caller; they never authorize orders, schema repair or a synthetic notice.
    Historical activation filtering and durable delivery deduplication are the
    delivery service's responsibility, using ``key`` and ``occurred_at``.
    """
    if not database.is_file():
        return ()
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        notices: list[Notice] = []
        intents = _rows(connection, "trial_intents")
        fills = _rows(connection, "trial_fills")
        audit = _rows(connection, "trial_order_audit")
        for trial in _rows(connection, "signal_trial"):
            notices.extend(_trial_notices(trial, intents, fills, audit))
        for archive in _rows(connection, "trial_archives"):
            payload = _json(archive.get("payload_json"))
            trial = _json(payload.get("trial"))
            if _text(trial, "trial_id") != _text(archive, "trial_id"):
                continue
            notices.extend(
                _trial_notices(
                    trial,
                    _records(payload.get("intents")),
                    _records(payload.get("fills")),
                    audit,
                )
            )
        orders = _confirmed(
            _rows(connection, "live_intents"),
            _rows(connection, "live_fills"),
            _rows(connection, "live_order_audit"),
        )
        notices.extend(
            _live_notices(
                _rows(connection, "live_events"),
                orders,
                _rows(connection, "live_dust"),
            )
        )
        # Current + archived copies of one trial must not duplicate delivery keys.
        unique = {notice.key: notice for notice in reversed(notices)}
        return tuple(sorted(unique.values(), key=lambda n: (n.occurred_at, n.key)))
    finally:
        connection.rollback()
        connection.close()
