from datetime import UTC, datetime
from decimal import Decimal as D
from types import SimpleNamespace
from pathlib import Path
import pytest
from hixton.backtest.account_capital import read_binance_starting_capital
from hixton.live.reconciliation import AccountSnapshot


def test_uses_only_free_usdc_and_never_sends_orders(monkeypatch):
    import hixton.backtest.account_capital as m
    credentials = SimpleNamespace(fingerprint="fake-account")
    monkeypatch.setattr(m.CredentialService, "load", lambda self: credentials)
    monkeypatch.setattr(m, "WindowsVault", lambda path: object())
    calls=[]
    class Transport:
        def __init__(self, credentials, *, base_url): pass
        def request(self, method, path, params):
            calls.append((method,path)); assert method == "GET"
            if path == "/api/v3/openOrders": return []
            assert path == "/api/v3/account"
            return {"balances":[{"asset":"USDC","free":"700.25","locked":"90"},
                                {"asset":"USDT","free":"9000","locked":"0"},
                                {"asset":"BTC","free":"2","locked":"0"}]}
    monkeypatch.setattr(m,"BinanceSpotTransport",Transport)
    result=read_binance_starting_capital(SimpleNamespace(database_path=Path("unused"),binance_base_url="https://fake.invalid"))
    assert result["amount_usdc"]=="700.25"
    assert result["locked_usdc_excluded"]=="90"
    assert result["existing_coins_included"] is False
    assert len(calls)==3 and all(method=="GET" for method,path in calls)


def test_missing_credentials_does_not_fall_back_to_1100(monkeypatch):
    import hixton.backtest.account_capital as m
    monkeypatch.setattr(m,"WindowsVault",lambda path: object())
    monkeypatch.setattr(m.CredentialService,"load",lambda self: None)
    with pytest.raises(RuntimeError,match="kein Ersatzbudget"):
        read_binance_starting_capital(SimpleNamespace(database_path=Path("unused")))


def test_failed_account_read_does_not_use_cached_or_fixed_capital(monkeypatch):
    import hixton.backtest.account_capital as m
    monkeypatch.setattr(m,"WindowsVault",lambda path: object())
    monkeypatch.setattr(m.CredentialService,"load",lambda self: SimpleNamespace(fingerprint="fake"))
    monkeypatch.setattr(m,"BinanceSpotTransport",lambda *args,**kw: object())
    monkeypatch.setattr(m,"read_account_snapshot",lambda *args,**kw: (_ for _ in ()).throw(ValueError()))
    with pytest.raises(RuntimeError,match="kein Ersatzbudget"):
        read_binance_starting_capital(SimpleNamespace(database_path=Path("unused"),binance_base_url="fake"))
