"""Small human messages; precise execution details remain in the local outbox."""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from hixton.domain.markets import split_market
from hixton.notifications.events import Notice, _amount, _fee_text


def money(value: Decimal, *, signed: bool = False) -> str:
    if value.adjusted() > 24:
        return format(value, "+.4E" if signed else ".4E").replace(".", ",")
    text = format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                  "+,.2f" if signed else ",.2f")
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def compact_message(notice: Notice) -> tuple[str, str]:
    facts = notice.trade
    if facts is None:
        return notice.title, notice.body
    base, quote = split_market(facts.symbol)
    foreign = sorted(a for a, v in facts.fees if v and a not in {base, quote})
    caveat = " vor " + "/".join(foreign) + "-Gebühren" if foreign else ""
    stamp = notice.occurred_at.astimezone(ZoneInfo("Europe/Berlin")).strftime("%d.%m. %H:%M")
    market = f"{base}/{quote}"
    if notice.kind == "entry":
        title = f"🟢 {facts.label} · {market} eröffnet"
        if "Teil-Ausführung" in notice.title:
            title = f"🟡 {facts.label} · {market} teilweise gekauft"
        lines = [f"Einsatz: {money(facts.spent)} {quote} · {_amount(facts.quantity)} {base}"]
    elif notice.kind == "exit":
        title = f"✅ {facts.label} · {market} beendet"
        assert facts.received is not None
        lines = [f"{money(facts.spent)} → {money(facts.received)} {quote} · "
                 f"{money(facts.received - facts.spent, signed=True)} {quote}{caveat}",
                 "Abgleich OK"]
    else:
        title = f"🟡 {facts.label} · {market} Teilverkauf" if notice.kind == "partial_exit" else (
            f"⚠ {facts.label} · {market} prüfen"
        )
        lines = [f"Rückfluss bisher: {money(facts.received or Decimal(0))} {quote}",
                 "Position/Abgleich noch offen · kein endgültiges Ergebnis"]
    if facts.remaining:
        lines.append(f"Rest: {_amount(facts.remaining)} {base} · nicht bewertet")
    total_foreign = [a for a, v in facts.total_foreign_fees if v]
    total_caveat = " vor " + "/".join(total_foreign) + "-Gebühren" if total_foreign else ""
    lines.append(f"Bot abgeschlossen ({facts.completed_count}): "
                 f"{money(facts.total_realized, signed=True)} {quote}{total_caveat}")
    if any(v for _, v in facts.fees):
        lines.append("Gebühren: " + _fee_text(dict(facts.fees)))
    lines.append("Erfasst: " + stamp)
    return title, "\n".join(lines)


def balance_line(payload: dict[str, object], *, quote: str, after: datetime,
                 now: datetime) -> str:
    """Never replace missing, stale or pre-fill data with a fabricated balance."""
    try:
        if not isinstance(payload, dict) or quote != "USDC" or payload.get("state") != "CURRENT":
            raise ValueError("Unverified quote balance")
        observed = datetime.fromisoformat(str(payload["observed_at_utc"]))
        if (observed.tzinfo is None or observed < after
            or not 0 <= (now - observed).total_seconds() <= 15):
            raise ValueError("Stale balance")
        free = Decimal(str(payload["free_usdc"]))
        total = Decimal(str(payload["total_usdc"]))
        if not free.is_finite() or not total.is_finite() or not 0 <= free <= total:
            raise ValueError("Invalid balance")
        stamp = observed.astimezone(ZoneInfo("Europe/Berlin")).strftime("%H:%M:%S")
        return f"Binance-USDC: {money(total)} · frei {money(free)} (Stand {stamp})"
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return f"⚠ Binance-{quote}-Stand nicht verfügbar · Verbindung prüfen"
