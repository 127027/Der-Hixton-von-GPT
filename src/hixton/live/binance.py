"""Allowlisted read-only Binance preflight. Intentionally has NO order-send method."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from contextlib import suppress
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from hixton.domain.markets import symbols_for_quote
from hixton.live.credentials import BinanceCredentials

_BASE = "https://api.binance.com"
_PUBLIC = {"/api/v3/time", "/api/v3/exchangeInfo"}
_PRIVATE = {"/api/v3/account", "/api/v3/openOrders", "/sapi/v1/account/apiRestrictions"}
_STEPS = {
    "/api/v3/time": "Systemzeit",
    "/api/v3/exchangeInfo": "Marktfilter",
    "/api/v3/account": "Kontostatus",
    "/api/v3/openOrders": "offene Orders",
    "/sapi/v1/account/apiRestrictions": "API-Berechtigungen",
}
_ERROR_HINTS: dict[int | None, str] = {
    -1100: "Ungültiges Parameterformat der Anfrage. Kein Nachweis für einen defekten API-Key.",
    -1102: "Anfrageparameter fehlt oder ist falsch formatiert.",
    -1021: "Zeitstempel außerhalb der Toleranz. Windows-Uhr synchronisieren.",
    -1022: "Signatur ungültig. Zuordnung von API-Key und Secret prüfen.",
    -2014: "API-Key-Format ungültig. Eingabe prüfen.",
    -2015: "API-Key, Berechtigungen oder IP-Freigabe nicht akzeptiert.",
    -1003: "Binance-Anfragelimit erreicht. Vor erneutem Prüfen warten.",
}


class BinanceCheckError(RuntimeError):
    def __init__(self, message: str, retry_after: int = 0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        # Never forward API headers/signatures to any redirect destination.
        return None


class BinanceReadOnlyClient:
    def __init__(self, credentials: BinanceCredentials, *, quote_asset: str = "USDC") -> None:
        self._credentials = credentials
        self.quote_asset = quote_asset
        self.symbols = symbols_for_quote(quote_asset)
        self._offset_ms = 0
        # Ignore environment proxy overrides; TLS certificate verification stays enabled.
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())

    def _read(self, path: str, params: dict[str, str] | None = None) -> Any:
        if path not in _PUBLIC | _PRIVATE:
            raise BinanceCheckError("Nicht erlaubter Binance-Endpunkt.")
        query = dict(params or {})
        headers = {"Accept": "application/json", "User-Agent": "DerHixton-Preflight"}
        if path in _PRIVATE:
            query.update(
                timestamp=str(int(time.time() * 1000) + self._offset_ms), recvWindow="5000"
            )
            signature = hmac.new(
                self._credentials.secret_key.encode(), urlencode(query).encode(), hashlib.sha256
            ).hexdigest()
            query["signature"] = signature
            headers["X-MBX-APIKEY"] = self._credentials.api_key
        request = Request(
            _BASE + path + ("?" + urlencode(query) if query else ""), headers=headers, method="GET"
        )
        try:
            with self._opener.open(request, timeout=10) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise BinanceCheckError("Binance-Antwort überschreitet das Größenlimit.")
                return json.loads(raw)
        except HTTPError as error:
            # Do not expose URL, signature, raw JSON, headers or Binance's free-text message.
            code: int | None = None
            try:
                payload = json.loads(error.read(16_384))
                value = payload.get("code") if isinstance(payload, dict) else None
                code = value if type(value) is int else None
            except (ValueError, OSError):
                pass
            retry = 60 if error.code in {418, 429} else 0
            if retry:
                with suppress(ValueError):
                    retry = min(3600, max(60, int(error.headers.get("Retry-After", "60"))))
            raise BinanceCheckError(
                f"Binance-Prüfung: {_STEPS[path]} fehlgeschlagen "
                f"(HTTP {error.code}, Code {code}). "
                + _ERROR_HINTS.get(code, "Binance hat die Anfrage abgewiesen."),
                retry,
            ) from None
        except (URLError, OSError, ValueError):
            raise BinanceCheckError("Binance-Prüfung: Netzwerk-/TLS- oder Antwortfehler.") from None

    def inspect(self, notional: Decimal) -> dict[str, object]:
        before = time.time() * 1000
        server = self._read("/api/v3/time")
        after = time.time() * 1000
        if not isinstance(server, dict) or type(server.get("serverTime")) is not int:
            raise BinanceCheckError("Ungültige Binance-Zeitantwort.")
        self._offset_ms = int(server["serverTime"] - (before + after) / 2)
        if abs(self._offset_ms) > 1000 or after - before > 2000:
            raise BinanceCheckError("Systemuhr oder Netzwerklatenz außerhalb der Prüftoleranz.")
        permissions = self._read("/sapi/v1/account/apiRestrictions")
        account = self._read("/api/v3/account", {"omitZeroBalances": "true"})
        orders = self._read("/api/v3/openOrders")
        # Binance rejects spaces in this JSON-array parameter with -1100.
        markets = self._read(
            "/api/v3/exchangeInfo", {"symbols": json.dumps(self.symbols, separators=(",", ":"))}
        )
        return assess_account(
            permissions, account, orders, markets, notional, quote_asset=self.quote_asset
        )


def _amount(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0:
            raise ValueError
        return result
    except (ValueError, InvalidOperation):
        raise BinanceCheckError("Binance enthält ungültige Mengen-/Filterdaten.") from None


def assess_account(
    permissions: Any,
    account: Any,
    orders: Any,
    markets: Any,
    notional: Decimal,
    *,
    quote_asset: str = "USDC",
) -> dict[str, object]:
    """Strict data assessment; metadata only, never import account holdings into paper."""
    symbols = symbols_for_quote(quote_asset)
    if not notional.is_finite() or notional != Decimal("50"):
        raise BinanceCheckError("Einmaltest-Vorprüfung benötigt genau 50 Quote-Einheiten.")
    if not all(isinstance(value, dict) for value in (permissions, account, markets)):
        raise BinanceCheckError("Unvollständige Binance-Kontoantwort.")
    if not isinstance(orders, list) or not isinstance(account.get("balances"), list):
        raise BinanceCheckError("Unvollständige Binance-Order-/Saldoantwort.")
    blockers: list[str] = []
    allowed = {"enableReading", "enableSpotAndMarginTrading", "ipRestrict"}
    forbidden = {
        "enableWithdrawals",
        "enableMargin",
        "enableFutures",
        "enableInternalTransfer",
        "permitsUniversalTransfer",
        "enableVanillaOptions",
        "enablePortfolioMarginTrading",
        "enableFixApiTrade",
    }
    for name in sorted(allowed):
        if permissions.get(name) is not True:
            state = "deaktiviert" if permissions.get(name) is False else "nicht eindeutig gemeldet"
            hint = {
                "enableReading": "Leserecht für diesen gespeicherten Key prüfen.",
                "enableSpotAndMarginTrading": "Spot-Handel bei Binance freigeben und speichern.",
                "ipRestrict": "Vertrauenswürdige öffentliche Ausgangs-IP bei Binance hinterlegen.",
            }[name]
            blockers.append(f"API-Recht {state}: {name}. {hint}")
    for name in sorted(forbidden):
        if permissions.get(name) is not False:
            blockers.append(f"API-Recht muss ausdrücklich deaktiviert sein: {name}")
    if account.get("canTrade") is not True or account.get("accountType") != "SPOT":
        blockers.append("Binance-Konto ist nicht für Spot-Handel freigegeben.")
    if orders:
        blockers.append("Offene Binance-Orders vorhanden; kein automatischer Import oder Storno.")
    balances: dict[str, tuple[Decimal, Decimal]] = {}
    for balance in account["balances"]:
        if not isinstance(balance, dict) or not isinstance(balance.get("asset"), str):
            raise BinanceCheckError("Ungültige Binance-Saldostruktur.")
        asset = balance["asset"]
        if asset in balances:
            raise BinanceCheckError("Doppelte Binance-Saldozeile.")
        balances[asset] = (_amount(balance.get("free")), _amount(balance.get("locked")))
    if any(locked > 0 for _, locked in balances.values()):
        blockers.append("Gesperrte Guthaben vorhanden; Status muss vor Live geklärt werden.")
    # No hidden adoption of manual inventory; BNB may be an explicitly separate fee reserve.
    foreign = [
        asset
        for asset, (free, locked) in balances.items()
        if asset not in {quote_asset, "BNB"} and free + locked > 0
    ]
    if foreign:
        blockers.append(
            "Fremdbestände vorhanden: "
            + ", ".join(sorted(foreign))
            + ". Vorhandene Bestände müssen vom Bot-Bestand getrennt werden; "
            "nicht allein wegen dieser Meldung verkaufen."
        )
    free_quote = balances.get(quote_asset, (Decimal(0), Decimal(0)))[0]
    if free_quote < notional + Decimal("10"):
        blockers.append(
            f"Für den ersten 1x50-Test werden mindestens 60 freie {quote_asset} benötigt."
        )
    raw_symbols = markets.get("symbols")
    if not isinstance(raw_symbols, list):
        raise BinanceCheckError("Binance-Symbolfilter fehlen.")
    symbol_map = {item.get("symbol"): item for item in raw_symbols if isinstance(item, dict)}
    if len(symbol_map) != len(raw_symbols):
        raise BinanceCheckError("Doppelte oder ungültige Binance-Symbolfilter.")
    for symbol in symbols:
        item = symbol_map.get(symbol)
        if (
            not item
            or item.get("status") != "TRADING"
            or item.get("isSpotTradingAllowed") is not True
            or item.get("baseAsset") != symbol.removesuffix(quote_asset)
            or item.get("quoteAsset") != quote_asset
        ):
            blockers.append(f"{symbol}: Spot-Handel nicht bestätigt.")
            continue
        if (
            "MARKET" not in item.get("orderTypes", [])
            or item.get("quoteOrderQtyMarketAllowed") is not True
        ):
            blockers.append(f"{symbol}: Market-Kauf mit Quote-Budget nicht bestätigt.")
        filters = item.get("filters")
        if not isinstance(filters, list):
            blockers.append(f"{symbol}: Orderfilter fehlen.")
            continue
        by_kind = {f.get("filterType"): f for f in filters if isinstance(f, dict)}
        if not {"LOT_SIZE", "MARKET_LOT_SIZE"} <= by_kind.keys():
            blockers.append(f"{symbol}: Mengenfilter unvollständig.")
        notionals = [by_kind[k] for k in ("MIN_NOTIONAL", "NOTIONAL") if k in by_kind]
        if not notionals or any(_amount(f.get("minNotional")) > notional for f in notionals):
            blockers.append(f"{symbol}: Mindestnotional fehlt oder liegt über 50 {quote_asset}.")
    return {
        "account_checks_passed": not blockers,
        "permission_states": {
            name: permissions[name] if type(permissions.get(name)) is bool else None
            for name in sorted(allowed | forbidden)
        },
        "foreign_balances": [
            {"asset": asset, "free": str(balances[asset][0]), "locked": str(balances[asset][1])}
            for asset in sorted(foreign)
        ],
        "blockers": blockers,
        "quote_asset": quote_asset,
        "free_quote": str(free_quote),
        "free_usdt": str(free_quote) if quote_asset == "USDT" else None,
        "free_usdc": str(free_quote) if quote_asset == "USDC" else None,
        "free_bnb": str(balances.get("BNB", (Decimal(0), Decimal(0)))[0]),
        "open_order_count": len(orders),
        "checked_symbols": list(symbols),
        "fee_discount_verified": False,
        "note": "Read-only Vorprüfung, kein Order-/Fill-/Reconciliation-Nachweis.",
    }
