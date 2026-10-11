from decimal import Decimal
from types import SimpleNamespace

import pytest
from hixton.ui.account_balance import AccountBalanceDisplay


def fixture_display():
    credentials = SimpleNamespace(load=lambda: SimpleNamespace(fingerprint="one"))
    now = [0.0]
    response = [{"accountType": "SPOT", "balances": [
        {"asset": "USDC", "free": "700.12345678", "locked": "7.1"},
        {"asset": "USDT", "free": "9000", "locked": "0"}]}]
    calls = []
    class Transport:
        def __init__(self, *args, **kwargs): pass
        def request(self, method, path, params):
            calls.append((method, path))
            assert method == "GET" and path == "/api/v3/account"
            if isinstance(response[0], Exception): raise response[0]
            return response[0]
    display = AccountBalanceDisplay(credentials, base_url="https://api.binance.com",
                                    transport_factory=Transport, clock=lambda: now[0])
    return display, credentials, now, response, calls


def test_exact_usdc_only_and_refresh_without_orders():
    display, _, now, response, calls = fixture_display()
    first = display.read()
    assert first["free_usdc"] == "700.12345678"
    assert Decimal(first["total_usdc"]) == Decimal("707.22345678")
    assert first["observed_at_utc"] and first["read_only"] is True
    now[0] = 29
    assert display.read() == first
    assert len(calls) == 1
    now[0] = 30
    response[0]["balances"][0]["free"] = "1000"
    assert display.read()["free_usdc"] == "1000"
    assert len(calls) == 2


def test_failure_clears_old_balance_and_throttles_retries():
    display, _, now, response, calls = fixture_display()
    display.read()
    now[0] = 30
    response[0] = RuntimeError("secret api key and signed URL must not appear")
    failed = display.read()
    assert failed["state"] == "UNAVAILABLE"
    assert failed["free_usdc"] is None and failed["total_usdc"] is None
    assert "secret" not in str(failed)
    now[0] = 89
    display.read()
    assert len(calls) == 2
    now[0] = 90
    display.read()
    assert len(calls) == 3


def test_removed_or_replaced_key_never_reuses_old_account():
    display, credentials, _, response, calls = fixture_display()
    display.read()
    credentials.load = lambda: None
    assert display.read()["state"] == "KEY_MISSING"
    assert display.read()["total_usdc"] is None
    credentials.load = lambda: SimpleNamespace(fingerprint="two")
    response[0]["balances"][0]["free"] = "5"
    assert display.read()["free_usdc"] == "5"
    assert len(calls) == 2


@pytest.mark.parametrize("bad", ["-1", "NaN", "Infinity", 123, None])
def test_invalid_binance_balance_never_becomes_displayed_cash(bad):
    display, _, _, response, _ = fixture_display()
    response[0]["balances"][0]["free"] = bad
    assert display.read()["free_usdc"] is None


def test_zero_is_real_balance_not_missing_or_budget_fallback():
    display, _, _, response, _ = fixture_display()
    response[0]["balances"] = []
    assert display.read()["free_usdc"] == "0"
    assert display.read()["state"] == "CURRENT"


def test_status_keeps_real_balance_separate_from_paper(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from hixton.ui.api import create_app
    import hixton.ui.api as api
    from hixton.config import ProjectConfig
    from hixton.runtime.supervisor import RuntimeSupervisor
    display, _, _, _, _ = fixture_display()
    monkeypatch.setattr(api, "AccountBalanceDisplay", lambda *args, **kwargs: display)
    config = ProjectConfig(strategy_key="v8", database_path=tmp_path / "paper.sqlite3",
        run_output_root=tmp_path / "backtests/v8/runs", binance_base_url="https://api.binance.com",
        starting_usdc_per_symbol=Decimal("250"), target_notional_usdc=Decimal("125"),
        run_baseline_and_stress=True, paper_poll_seconds=30, paper_starting_cash_usdc=Decimal("1100"),
        paper_slot_count=2, paper_target_notional_usdc=Decimal("550"), daily_audit_utc="00:05",
        ui_bind="127.0.0.1", ui_port=8765, ui_timezone="Europe/Berlin", ui_default_range="1m", sha256="test")
    from hixton.paper.storage import PaperStore
    from hixton.domain.versions import strategy_definition
    with PaperStore(config.database_path) as store:
        store.initialize(strategy_key="v8", strategy_version=strategy_definition("v8").version,
                         starting_cash_usdc=Decimal("1100"))
        from datetime import UTC, datetime
        started = datetime.now(UTC)
        checkpoints = dict.fromkeys(strategy_definition("v8").symbols, started)
        store.save_checkpoints(checkpoints)
        store.ensure_soak_started(checkpoints, at=started)
    client = TestClient(create_app(config, RuntimeSupervisor(config)),base_url="http://127.0.0.1:8765")
    result = client.get("/api/status").json()
    assert result["binance_balance"]["free_usdc"] == "700.12345678"
    assert result["paper"]["cash_usdc"] == "1100"
    assert result["runtime"]["live_state"] == "LIVE_DISABLED"
