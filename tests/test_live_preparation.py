from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from hixton.config import ProjectConfig
from hixton.constants import SYMBOLS
from hixton.live.binance import BinanceCheckError, BinanceReadOnlyClient, assess_account
from hixton.live.credentials import (
    BinanceCredentials,
    CredentialService,
    LocalAccess,
    VaultError,
    WindowsVault,
)
from hixton.live.preparation import LivePreparation
from hixton.paper.storage import PaperStore
from hixton.runtime.supervisor import RuntimeSupervisor
from hixton.ui.api import create_app

HEADERS = {"Origin": "http://127.0.0.1:8765", "X-Hixton-Action": "local-ui-v1"}
# Generated-looking fixtures are deliberately not API keys for any real account.
KEY = "TESTONLY" * 8
SECRET = "NOTAREAL" * 8
PASSWORD = "local-only-test-password"


class MemoryVault:
    def __init__(self) -> None:
        self.records: dict[str, str] = {}

    def read(self, name: str) -> str | None:
        return self.records.get(name)

    def write(self, name: str, value: str) -> None:
        self.records[name] = value

    def delete(self, name: str) -> None:
        self.records.pop(name, None)


def config_for(tmp_path: Path) -> ProjectConfig:
    return ProjectConfig(
        strategy_key="v6",
        database_path=tmp_path / "hixton.sqlite3",
        run_output_root=tmp_path / "backtests" / "v6" / "runs",
        binance_base_url="https://api.binance.com",
        starting_usdc_per_symbol=Decimal("250"),
        target_notional_usdc=Decimal("250"),
        run_baseline_and_stress=True,
        paper_poll_seconds=30,
        paper_starting_cash_usdc=Decimal("250"),
        paper_slot_count=3,
        paper_target_notional_usdc=Decimal("80"),
        daily_audit_utc="00:05",
        ui_bind="127.0.0.1",
        ui_port=8765,
        ui_timezone="Europe/Berlin",
        ui_default_range="1m",
        sha256="test-only",
    )


def client_for(tmp_path: Path, vault: MemoryVault | None = None):
    config = config_for(tmp_path)
    supervisor = RuntimeSupervisor(config)
    with PaperStore(config.database_path) as store:
        store.initialize(
            strategy_key="v6",
            strategy_version=supervisor.strategy.version,
            starting_cash_usdc=Decimal("250"),
        )
        checkpoints = dict.fromkeys(SYMBOLS, datetime.now(UTC))
        store.save_checkpoints(checkpoints)
        store.ensure_soak_started(checkpoints)
    app = create_app(config, supervisor, live_vault=vault or MemoryVault())
    client = TestClient(app, base_url="http://127.0.0.1:8765")
    return client, config, app.state.live_preparation


def unlock(client: TestClient) -> None:
    response = client.post(
        "/api/live/unlock", headers=HEADERS, json={"password": PASSWORD, "repeat": PASSWORD}
    )
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Max-Age=900" in cookie


def save_key(client: TestClient) -> None:
    response = client.post(
        "/api/live/credentials",
        headers=HEADERS,
        json={
            "api_key": KEY,
            "secret_key": SECRET,
            "confirmation": "SCHLUESSEL SPEICHERN",
        },
    )
    assert response.status_code == 200
    assert KEY not in response.text and SECRET not in response.text


def account_fixture():
    permissions = dict.fromkeys(
        [
            "enableWithdrawals",
            "enableMargin",
            "enableFutures",
            "enableInternalTransfer",
            "permitsUniversalTransfer",
            "enableVanillaOptions",
            "enablePortfolioMarginTrading",
            "enableFixApiTrade",
        ],
        False,
    )
    permissions.update(enableReading=True, enableSpotAndMarginTrading=True, ipRestrict=True)
    account = {
        "canTrade": True,
        "accountType": "SPOT",
        "balances": [
            {"asset": "USDC", "free": "100", "locked": "0"},
            {"asset": "BNB", "free": "0.03", "locked": "0"},
        ],
    }
    markets = {
        "symbols": [
            {
                "symbol": symbol,
                "baseAsset": symbol.removesuffix("USDC"),
                "quoteAsset": "USDC",
                "status": "TRADING",
                "isSpotTradingAllowed": True,
                "orderTypes": ["MARKET"],
                "quoteOrderQtyMarketAllowed": True,
                "filters": [
                    {"filterType": "MIN_NOTIONAL", "minNotional": "5"},
                    {"filterType": "LOT_SIZE"},
                    {"filterType": "MARKET_LOT_SIZE"},
                ],
            }
            for symbol in SYMBOLS
        ]
    }
    return permissions, account, [], markets


@pytest.mark.parametrize("amount", ["500", "80", "NaN", "Infinity", "-50"])
def test_trial_endpoint_rejects_non_fifty_budget(tmp_path: Path, amount: str) -> None:
    client, _, _ = client_for(tmp_path)
    unlock(client)
    response = client.post(
        "/api/live/trial/start",
        headers=HEADERS,
        json={"confirmation": "TEST 50 USDC", "quote_asset": "USDC", "notional_quote": amount},
    )
    assert response.status_code == 400


def test_trial_route_is_authenticated_and_fail_closed_without_runtime_adapter(
    tmp_path: Path,
) -> None:
    client, config, service = client_for(tmp_path)
    before = client.get("/api/status").json()["paper"]
    body = {"confirmation": "TEST 50 USDC", "quote_asset": "USDC", "notional_quote": "50.00"}
    assert client.post("/api/live/trial/start", headers=HEADERS, json=body).status_code == 401
    unlock(client)
    save_key(client)
    response = client.post("/api/live/trial/start", headers=HEADERS, json=body)
    assert response.status_code == 409
    assert response.json()["trial_dispatch_available"] is False
    assert response.json()["paper_settings_preview"] == {
        "slot_count": 3,
        "target_notional_usdc": "80.00",
    }
    assert response.json()["trial"]["state"] == "NOT_STARTED"
    assert service.trial is not None and service.runtime is not None
    assert response.json()["trial_readiness"]["runtime_connected"] is True
    assert response.json()["trial_readiness"]["production_submission_accepted"] is False
    assert (
        client.post(
            "/api/live/trial/start", headers=HEADERS, json={**body, "force_live": True}
        ).status_code
        == 400
    )
    assert client.post("/api/live/trial/stop", headers=HEADERS, json={}).status_code == 200
    assert client.get("/api/status").json()["paper"] == before
    with sqlite3.connect(config.database_path) as connection:
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE name IN ('signal_trial','trial_intents')"
            ).fetchall()
            == []
        )


def test_live_off_does_not_sell_open_trial_and_keys_cannot_orphan_it(tmp_path: Path) -> None:
    from tests.test_live_trial import arm, open_position, trial

    client, _, service = client_for(tmp_path)
    unlock(client)
    save_key(client)
    controller, exchange = trial(tmp_path / "fake-exchange-only")
    service.trial = controller
    arm(controller)
    open_position(controller)
    for endpoint in ("/api/live/disable", "/api/live/trial/stop"):
        response = client.post(endpoint, headers=HEADERS, json={})
        assert response.status_code == 200
        assert response.json()["state"] == "EXIT_ONLY"
    assert controller.report()["state"] == "OPEN"
    assert len(exchange.submits) == 1
    assert client.get("/api/status").json()["runtime"]["live_state"] == "TRIAL_OPEN"
    assert client.get("/api/live/status").json()["trial"]["state"] == "OPEN"
    response = client.post(
        "/api/live/credentials/delete",
        headers=HEADERS,
        json={"confirmation": "SCHLUESSEL ENTFERNEN"},
    )
    assert response.status_code == 400
    response = client.post(
        "/api/live/credentials",
        headers=HEADERS,
        json={"confirmation": "SCHLUESSEL SPEICHERN", "api_key": KEY, "secret_key": SECRET},
    )
    assert response.status_code == 400
    assert service.credentials.status()["configured"] is True


def test_one_by_fifty_persists_without_reset(tmp_path: Path) -> None:
    client, config, _ = client_for(tmp_path)
    before = client.get("/api/status").json()["paper"]
    response = client.post(
        "/api/paper/settings",
        headers=HEADERS,
        json={
            "slot_count": 1,
            "target_notional_usdc": "50.00",
            "emergency_stop": False,
            "confirmation": "ANWENDEN",
        },
    )
    assert response.status_code == 200
    restarted = TestClient(
        create_app(config, RuntimeSupervisor(config), live_vault=MemoryVault()),
        base_url="http://127.0.0.1:8765",
    )
    after = restarted.get("/api/status").json()["paper"]
    assert after["settings"]["slot_count"] == 1
    assert after["settings"]["target_notional_usdc"] == "50.00"
    for field in ("cash_usdc", "equity_usdc", "positions", "strategy_session", "soak"):
        assert before[field] == after[field]


def test_common_settings_are_immediately_the_live_source_and_survive_restart(
    tmp_path: Path,
) -> None:
    client, config, _ = client_for(tmp_path)
    before = client.get("/api/status").json()["paper"]
    payload = {
        "slot_count": 1,
        "target_notional_usdc": "50.00",
        "emergency_stop": False,
        "confirmation": "ANWENDEN",
    }
    assert client.post("/api/trading/settings", json=payload).status_code == 403
    assert client.post("/api/trading/settings", json=payload, headers=HEADERS).status_code == 200
    restarted = TestClient(
        create_app(config, RuntimeSupervisor(config), live_vault=MemoryVault()),
        base_url="http://127.0.0.1:8765",
    )
    for active in (client, restarted):
        status = active.get("/api/status").json()
        after = status["paper"]
        settings = after["settings"]
        assert settings == {key: value for key, value in payload.items() if key != "confirmation"}
        live = active.get("/api/live/status").json()
        assert live["trading_settings"] == settings
        assert live["first_live_trial"]["target_notional_quote"] == "50.00"
        assert live["first_live_trial"]["quote_asset"] == "USDC"
        assert live["state"] == "LIVE_DISABLED"
        assert {key: value for key, value in after.items() if key != "settings"} == {
            key: value for key, value in before.items() if key != "settings"
        }
        assert status["trading_limits"] == {
            "max_slots": 10,
        }


@pytest.mark.parametrize("slots,amount", [(4, "45"), (5, "50"), (10, "100")])
def test_expanded_slot_allocation_persists_without_inventing_cash(
    tmp_path: Path,
    slots: int,
    amount: str,
) -> None:
    client, config, _ = client_for(tmp_path)
    before = client.get("/api/status").json()["paper"]
    payload = {
        "slot_count": slots,
        "target_notional_usdc": amount,
        "emergency_stop": False,
        "confirmation": "ANWENDEN",
    }
    assert client.post("/api/trading/settings", headers=HEADERS, json=payload).status_code == 200
    restarted = TestClient(
        create_app(config, RuntimeSupervisor(config), live_vault=MemoryVault()),
        base_url="http://127.0.0.1:8765",
    )
    after = restarted.get("/api/status").json()["paper"]
    assert after["settings"]["slot_count"] == slots
    assert after["settings"]["target_notional_usdc"] == amount
    assert restarted.get("/api/live/status").json()["trading_settings"] == after["settings"]
    for field in ("cash_usdc", "positions", "strategy_session", "soak"):
        assert after[field] == before[field]
    assert restarted.get("/").headers["cache-control"] == "no-store"


def test_existing_password_unlock_to_key_and_account_check_is_a_complete_local_flow(
    tmp_path: Path,
) -> None:
    vault = MemoryVault()
    original, config, _ = client_for(tmp_path, vault)
    unlock(original)
    # A real process restart invalidates sessions but must retain the existing password.
    app = create_app(config, RuntimeSupervisor(config), live_vault=vault)
    client = TestClient(app, base_url="http://127.0.0.1:8765")
    service = app.state.live_preparation
    assert client.get("/api/live/status").json()["password_configured"] is True
    wrong = client.post(
        "/api/live/unlock",
        headers=HEADERS,
        json={"password": "incorrect-password-123", "repeat": ""},
    )
    assert wrong.status_code == 400
    correct = client.post(
        "/api/live/unlock", headers=HEADERS, json={"password": PASSWORD, "repeat": ""}
    )
    assert correct.status_code == 200
    assert client.get("/api/live/status").json()["authenticated"] is True
    save_key(client)

    class FakeReadOnlyClient:
        def __init__(self, credentials: BinanceCredentials) -> None:
            assert credentials.api_key == KEY

        def inspect(self, notional: Decimal) -> dict[str, object]:
            assert notional == Decimal("50")
            return {
                "account_checks_passed": True,
                "blockers": [],
                "free_usdc": "250",
                "free_bnb": "0.01",
            }

    service.client_factory = FakeReadOnlyClient
    check = client.post("/api/live/check", headers=HEADERS, json={})
    assert check.status_code == 200
    assert check.json()["account_checks_passed"] is True
    assert client.post("/api/live/enable", headers=HEADERS, json={}).status_code == 409
    assert client.get("/api/status").json()["runtime"]["live_state"] == "LIVE_DISABLED"


@pytest.mark.parametrize(
    "slot_count,amount", [(11, "80"), (0, "80"), (3, "NaN"), (3, "Infinity"), (3, "-50")]
)
def test_common_settings_reject_unapproved_limits_without_silent_fallback(
    tmp_path: Path,
    slot_count: int,
    amount: str,
) -> None:
    client, _, _ = client_for(tmp_path)
    before = client.get("/api/live/status").json()["trading_settings"]
    response = client.post(
        "/api/trading/settings",
        headers=HEADERS,
        json={
            "slot_count": slot_count,
            "target_notional_usdc": amount,
            "emergency_stop": False,
            "confirmation": "ANWENDEN",
        },
    )
    assert response.status_code == 400
    assert "Ungültige Handelseinstellungen" in response.json()["detail"]
    assert client.get("/api/live/status").json()["trading_settings"] == before


@pytest.mark.parametrize("already_open", [False, True])
def test_shared_entry_pause_stops_only_entries_and_never_rearms_or_sells(
    tmp_path: Path,
    already_open: bool,
) -> None:
    from tests.test_live_trial import arm, open_position, trial

    client, _, service = client_for(tmp_path)
    controller, exchange = trial(tmp_path / "fake-exchange-only")
    service.trial = controller
    arm(controller)
    if already_open:
        open_position(controller)
    previous_submits = len(exchange.submits)
    for pause in (True, False):
        response = client.post(
            "/api/trading/settings",
            headers=HEADERS,
            json={
                "slot_count": 3,
                "target_notional_usdc": "80.00",
                "emergency_stop": pause,
                "confirmation": "ANWENDEN",
            },
        )
        assert response.status_code == 200
        live = client.get("/api/live/status").json()
        assert live["trading_settings"]["emergency_stop"] is pause
        assert any("Einstiegspause aktiv" in reason for reason in live["blockers"]) is pause
        assert controller.report()["state"] == ("OPEN" if already_open else "CANCELED")
        assert len(exchange.submits) == previous_submits


@pytest.mark.parametrize("notional", ["NaN", "sNaN", "Infinity", "-Infinity", "bad", "0", "-1"])
def test_invalid_paper_amount_fails_cleanly(tmp_path: Path, notional: str) -> None:
    client, _, _ = client_for(tmp_path)
    result = client.post(
        "/api/paper/settings",
        headers=HEADERS,
        json={
            "slot_count": 1,
            "target_notional_usdc": notional,
            "confirmation": "ANWENDEN",
        },
    )
    assert result.status_code == 400


@pytest.mark.parametrize(
    "origin",
    [
        "http://evil.example",
        "http://127.0.0.1:8765@evil.example",
        "http://127.0.0.1:9999",
        "http://localhost:8765/evil",
    ],
)
def test_origin_prefix_bypass_is_rejected(tmp_path: Path, origin: str) -> None:
    client, _, _ = client_for(tmp_path)
    headers = {**HEADERS, "Origin": origin}
    assert client.post("/api/paper/settings", headers=headers, json={}).status_code == 403
    assert client.post("/api/live/unlock", headers=headers, json={}).status_code == 403


def test_credentials_require_password_never_echo_and_remain_separate(tmp_path: Path) -> None:
    vault = MemoryVault()
    client, config, service = client_for(tmp_path, vault)
    assert client.post("/api/live/credentials", headers=HEADERS, json={}).status_code == 401
    unlock(client)
    save_key(client)
    status = client.get("/api/live/status")
    assert status.headers["cache-control"] == "no-store"
    assert status.json()["credentials"]["configured"] is True
    assert KEY not in status.text and SECRET not in status.text and PASSWORD not in status.text
    assert PASSWORD not in vault.records["ui-password"]
    assert KEY not in repr(service.credentials.load())
    assert SECRET not in repr(service.credentials.load())
    with sqlite3.connect(service.database) as connection:
        audit = str(connection.execute("SELECT * FROM live_preparation_audit").fetchall())
    assert all(value not in audit for value in (KEY, SECRET, PASSWORD))
    with sqlite3.connect(config.database_path) as connection:
        assert "live_preparation_audit" not in str(
            connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        )
    assert client.post("/api/live/lock", headers=HEADERS, json={}).status_code == 200
    locked = client.get("/api/live/status").json()
    assert locked["authenticated"] is False
    assert "fingerprint" not in locked["credentials"]
    assert client.post("/api/live/check", headers=HEADERS, json={}).status_code == 401


def test_credential_delete_does_not_delete_password_or_paper(tmp_path: Path) -> None:
    vault = MemoryVault()
    client, _, _ = client_for(tmp_path, vault)
    unlock(client)
    save_key(client)
    before = client.get("/api/status").json()["paper"]
    denied = client.post("/api/live/credentials/delete", headers=HEADERS, json={})
    assert denied.status_code == 400
    deleted = client.post(
        "/api/live/credentials/delete",
        headers=HEADERS,
        json={"confirmation": "SCHLUESSEL ENTFERNEN"},
    )
    assert deleted.status_code == 200 and deleted.json()["revoked_at_binance"] is False
    assert "binance-hmac" not in vault.records and "ui-password" in vault.records
    assert client.get("/api/status").json()["paper"] == before


def test_login_expiry_rate_limit_and_restart(monkeypatch: pytest.MonkeyPatch) -> None:
    vault = MemoryVault()
    access = LocalAccess(vault)
    now = [100.0]
    monkeypatch.setattr("hixton.live.credentials.time.monotonic", lambda: now[0])
    token = access.unlock(PASSWORD, PASSWORD)
    assert access.authorized(token)
    assert not LocalAccess(vault).authorized(token)
    now[0] += 901
    assert not access.authorized(token)
    for _ in range(5):
        with pytest.raises(VaultError):
            access.unlock("incorrect-test-password")
    with pytest.raises(VaultError, match="60 Sekunden"):
        access.unlock(PASSWORD)
    now[0] += 61
    assert access.authorized(access.unlock(PASSWORD))


def test_first_enrollment_does_not_take_over_existing_key() -> None:
    vault = MemoryVault()
    CredentialService(vault).save(BinanceCredentials(KEY, SECRET))
    with pytest.raises(VaultError, match="Recovery"):
        LocalAccess(vault).unlock(PASSWORD, PASSWORD)


def test_size_limit_does_not_echo_secrets(tmp_path: Path) -> None:
    client, _, _ = client_for(tmp_path)
    result = client.post("/api/live/unlock", headers=HEADERS, content=KEY * 100)
    assert result.status_code == 413 and KEY not in result.text


def test_clean_account_is_not_live_approval(tmp_path: Path) -> None:
    client, _, service = client_for(tmp_path)
    unlock(client)
    save_key(client)

    class Client:
        def inspect(self, notional):
            return assess_account(*account_fixture(), notional)

    service.client_factory = lambda _: Client()
    check = client.post("/api/live/check", headers=HEADERS, json={})
    assert check.status_code == 200 and check.json()["account_checks_passed"] is True
    # Even simulated completed soak + healthy runtime MUST NOT enable an absent dispatcher.
    assert service.status(authenticated=True, soak_ready=True, healthy=True)["ready"] is False
    result = client.post("/api/live/enable", headers=HEADERS, json={})
    assert result.status_code == 409
    assert result.json()["state"] == "LIVE_DISABLED"
    status = client.get("/api/status").json()
    assert status["runtime"]["mode"] == "PAPER"
    assert status["paper"]["cash_usdc"] == "250"
    assert client.post("/api/live/disable", headers=HEADERS, json={}).status_code == 200


@pytest.mark.parametrize(
    "flag",
    [
        "enableWithdrawals",
        "enableMargin",
        "enableFutures",
        "enableInternalTransfer",
        "permitsUniversalTransfer",
        "enableVanillaOptions",
        "enablePortfolioMarginTrading",
    ],
)
def test_dangerous_key_rights_block(flag: str) -> None:
    permissions, account, orders, markets = account_fixture()
    permissions[flag] = True
    result = assess_account(permissions, account, orders, markets, Decimal("50"))
    assert result["account_checks_passed"] is False
    assert flag in str(result["blockers"])


def test_missing_permissions_foreign_inventory_and_insufficient_usdc_fail_closed() -> None:
    permissions, account, orders, markets = account_fixture()
    del permissions["enableWithdrawals"]
    account["balances"][0]["free"] = "0"
    account["balances"].append({"asset": "BUSD", "free": "1000", "locked": "0"})
    orders.append({"symbol": "BTCUSDC", "clientOrderId": "foreign"})
    result = assess_account(permissions, account, orders, markets, Decimal("50"))
    reasons = str(result["blockers"])
    assert all(term in reasons for term in ("enableWithdrawals", "Fremdbestände", "60", "Orders"))
    assert result["free_usdc"] == "0"


def test_preflight_explains_false_unknown_and_each_foreign_asset_without_relaxing_gate() -> None:
    permissions, account, orders, markets = account_fixture()
    permissions["enableSpotAndMarginTrading"] = False
    del permissions["ipRestrict"]
    account["balances"].append({"asset": "BTC", "free": "0.0001", "locked": "0"})
    result = assess_account(permissions, account, orders, markets, Decimal("50"))
    assert result["account_checks_passed"] is False
    assert result["permission_states"]["enableSpotAndMarginTrading"] is False
    assert result["permission_states"]["ipRestrict"] is None
    assert result["foreign_balances"] == [{"asset": "BTC", "free": "0.0001", "locked": "0"}]
    assert "deaktiviert" in str(result["blockers"])
    assert "nicht eindeutig gemeldet" in str(result["blockers"])
    assert "BTC" in str(result["blockers"])


def test_usdc_preflight_checks_actual_quote_not_usdt_and_never_changes_paper(tmp_path):
    permissions, account, orders, markets = account_fixture()
    account["balances"][0].update(asset="USDC", free="1200")
    for item in markets["symbols"]:
        item["symbol"] = item["baseAsset"] + "USDC"
        item["quoteAsset"] = "USDC"
    result = assess_account(
        permissions, account, orders, markets, Decimal("50"), quote_asset="USDC"
    )
    assert result["account_checks_passed"] is True
    assert result["free_quote"] == "1200" and result["free_usdt"] is None
    assert result["quote_asset"] == "USDC"
    assert all(symbol.endswith("USDC") for symbol in result["checked_symbols"])
    client, _, service = client_for(tmp_path)
    before = client.get("/api/status").json()["paper"]
    # Default production read-only factory is now explicitly USDC; no network here.
    assert service.client_factory(BinanceCredentials(KEY, SECRET)).quote_asset == "USDC"
    unlock(client)
    old_request = {"confirmation": "TEST 50 USDT", "notional_usdt": "50.00"}
    assert (
        client.post("/api/live/trial/start", headers=HEADERS, json=old_request).status_code == 400
    )
    assert client.get("/api/status").json()["paper"] == before
    markets["symbols"][0]["quoteAsset"] = "USDT"
    assert not assess_account(
        permissions, account, orders, markets, Decimal("50"), quote_asset="USDC"
    )["account_checks_passed"]


def test_malformed_or_nan_balances_fail_closed() -> None:
    permissions, account, orders, markets = account_fixture()
    account["balances"][0]["free"] = "NaN"
    with pytest.raises(BinanceCheckError):
        assess_account(permissions, account, orders, markets, Decimal("50"))


def test_readonly_transport_signs_and_cannot_reach_order_endpoints() -> None:
    client = BinanceReadOnlyClient(BinanceCredentials(KEY, SECRET))
    seen = []

    class Opener:
        def open(self, request, timeout):
            seen.append(request)
            return io.BytesIO(b'{"canTrade": true}')

    client._opener = Opener()
    assert client._read("/api/v3/account")["canTrade"] is True
    request = seen[0]
    assert request.method == "GET" and request.get_header("X-mbx-apikey") == KEY
    url = urlsplit(request.full_url)
    unsigned, signature = url.query.rsplit("&signature=", 1)
    assert url.hostname == "api.binance.com" and url.scheme == "https"
    assert signature == hmac.new(SECRET.encode(), unsigned.encode(), hashlib.sha256).hexdigest()
    assert parse_qs(unsigned)["recvWindow"] == ["5000"]
    for path in ("/api/v3/order", "/api/v3/order/test", "https://evil.example"):
        with pytest.raises(BinanceCheckError):
            client._read(path)
    assert len(seen) == 1


def test_inspection_sends_compact_public_symbol_array(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BinanceReadOnlyClient(BinanceCredentials(KEY, SECRET))
    permissions, account, orders, markets = account_fixture()
    monkeypatch.setattr("hixton.live.binance.time.time", lambda: 1000.0)
    responses = {
        "/api/v3/time": {"serverTime": 1_000_000},
        "/sapi/v1/account/apiRestrictions": permissions,
        "/api/v3/account": account,
        "/api/v3/openOrders": orders,
        "/api/v3/exchangeInfo": markets,
    }
    seen = []

    class Opener:
        def open(self, request, timeout):
            seen.append(request)
            url = urlsplit(request.full_url)
            if url.path == "/api/v3/exchangeInfo":
                query = parse_qs(url.query)
                assert query == {"symbols": [json.dumps(SYMBOLS, separators=(",", ":"))]}
                assert " " not in query["symbols"][0]
                assert request.get_header("X-mbx-apikey") is None
                assert "signature" not in query
            return io.BytesIO(json.dumps(responses[url.path]).encode())

    client._opener = Opener()
    assert client.inspect(Decimal("50"))["account_checks_passed"] is True
    assert len(seen) == 5


@pytest.mark.parametrize(
    "code,hint", [(-1100, "Parameterformat"), (-2015, "IP-Freigabe"), (-1021, "Zeitstempel")]
)
def test_http_error_identifies_phase_and_code_without_leaking_payload(code: int, hint: str) -> None:
    client = BinanceReadOnlyClient(BinanceCredentials(KEY, SECRET))

    class Opener:
        def open(self, request, timeout):
            raise HTTPError(
                request.full_url,
                400,
                SECRET,
                {},
                io.BytesIO(json.dumps({"code": code, "msg": KEY}).encode()),
            )

    client._opener = Opener()
    with pytest.raises(BinanceCheckError) as error:
        client._read("/api/v3/exchangeInfo")
    assert "Marktfilter" in str(error.value) and hint in str(error.value)
    assert KEY not in str(error.value) and SECRET not in str(error.value)
    assert "https://" not in str(error.value)


def test_http_errors_and_timeouts_redact_secrets() -> None:
    client = BinanceReadOnlyClient(BinanceCredentials(KEY, SECRET))

    class Opener:
        def open(self, request, timeout):
            raise HTTPError(
                request.full_url,
                429,
                SECRET,
                {"Retry-After": "120"},
                io.BytesIO(json.dumps({"code": -1003, "msg": KEY}).encode()),
            )

    client._opener = Opener()
    with pytest.raises(BinanceCheckError) as error:
        client._read("/api/v3/account")
    assert error.value.retry_after == 120
    assert KEY not in str(error.value) and SECRET not in str(error.value)

    class TimeoutOpener:
        def open(self, request, timeout):
            raise URLError(SECRET)

    client._opener = TimeoutOpener()
    with pytest.raises(BinanceCheckError) as error:
        client._read("/api/v3/account")
    assert SECRET not in str(error.value)


def test_check_expiration_and_rate_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = LivePreparation(tmp_path / "live.sqlite3", MemoryVault())
    service.credentials.save(BinanceCredentials(KEY, SECRET))
    now = [100.0]
    monkeypatch.setattr("hixton.live.preparation.time.monotonic", lambda: now[0])

    class Client:
        def inspect(self, notional):
            return assess_account(*account_fixture(), notional)

    service.client_factory = lambda _: Client()
    service.check()
    assert service.status(authenticated=True, soak_ready=True, healthy=True)["account_check"]
    with pytest.raises(BinanceCheckError):
        service.check()
    now[0] += 61
    assert (
        service.status(authenticated=True, soak_ready=True, healthy=True)["account_check"] is None
    )


@pytest.mark.skipif(
    os.name != "nt" or os.environ.get("HIXTON_TEST_WINDOWS_VAULT") != "1",
    reason="Opt-in: creates/removes only a unique fake-key Windows vault entry",
)
def test_real_windows_vault_roundtrip(tmp_path: Path) -> None:
    vault = WindowsVault(tmp_path / f"test-only-{uuid4()}")
    assert vault.read("binance-hmac") is None
    try:
        vault.write("binance-hmac", "FAKE-KEY-ROUNDTRIP")
        assert vault.read("binance-hmac") == "FAKE-KEY-ROUNDTRIP"
        vault.write("binance-hmac", "REPLACED-FAKE-KEY")
        assert vault.read("binance-hmac") == "REPLACED-FAKE-KEY"
    finally:
        vault.delete("binance-hmac")
    assert vault.read("binance-hmac") is None
