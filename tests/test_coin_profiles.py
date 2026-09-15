from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hixton.backtest.engine import run_isolated_batch, run_single_backtest
from hixton.backtest.models import ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.config import load_project_config
from hixton.constants import SYMBOLS
from hixton.domain.strategy import evaluate_batch
from hixton.domain.versions import STRATEGY_DEFINITIONS
from hixton.domain.versions import V6_COIN_STRATEGY as V6
from hixton.paper.engine import (
    activate_paper_strategy,
    initialize_paper_at_latest,
    load_paper_portfolio,
)
from hixton.paper.engine import process_new_closed_points as process_points
from hixton.paper.models import PaperPosition, PaperSettings
from hixton.paper.storage import PaperStore
from hixton.runtime.supervisor import RuntimeSupervisor
from hixton.ui.api import create_app
from hixton.ui.chart import strategy_markers
from tests.golden_reference import deterministic_candles
from tests.test_config import _payload
from tests.test_paper_engine import _mapping, _point, _rules
from tests.test_ui_api import _config


def _profile_candles(symbol: str, count: int):
    # Narrower ranges produce crossings with the real wide-band profiles.
    return [
        replace(c, high=max(c.open, c.close) + 0.01, low=min(c.open, c.close) - 0.01)
        for c in deterministic_candles(symbol, count)
    ]


def test_profiles_are_complete_individual_and_strictly_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert tuple(V6.parameter_map()) == SYMBOLS
    assert len(set(V6.parameter_map().values())) > 1
    assert V6.parameters_for("btc/usdc").atr_length == 120
    assert V6.policy_for("ETHUSDC").slope_bars == 24
    assert V6.policy_for("XRPUSDC").stop_atr == 4
    payload = _payload()
    payload["strategy"] = V6.config_payload()
    payload["paper"]["starting_cash_usdc"] = "250.00"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert V6.paper_approved  # DEC-045: Paper experiment only.
    assert load_project_config(path, project_root=tmp_path).strategy_key == "v6"
    payload["strategy"]["profiles"]["BTCUSDC"]["parameters"]["atr_length"] = 60
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="deviates"):
        load_project_config(path, project_root=tmp_path)
    with pytest.raises(ValueError, match="all ten"):
        replace(V6, coin_profiles=V6.coin_profiles[:-1])
    with pytest.raises(ValueError, match="unsupported"):
        V6.parameters_for("UNKNOWN")


def test_coin_profiles_paper_backtest_and_restart_are_exact(tmp_path: Path) -> None:
    # Different symbol profiles compete for the same three slots, with real rounding
    # and costs. A stop/filter or changed ranking must produce identical fills.
    candles = {s: _profile_candles(s, 2200) for s in SYMBOLS}
    points = {
        s: tuple(
            evaluate_batch(
                s,
                c,
                parameters=V6.parameters_for(s),
                semantics=V6.semantics,
                strategy_version=V6.version,
            )
        )
        for s, c in candles.items()
    }
    start = candles[SYMBOLS[0]][400].open_time_utc
    end = candles[SYMBOLS[0]][-1].open_time_utc + timedelta(hours=1)
    rules = dict.fromkeys(
        SYMBOLS,
        ExecutionRules(
            step_size=Decimal("0.01"), min_qty=Decimal("0.01"), min_notional=Decimal("5")
        ),
    )
    expected = run_shared_portfolio_backtest(
        candles_by_symbol=candles,
        report_start_utc=start,
        report_end_utc=end,
        execution_rules=rules,
        strategy_parameters=V6.parameters,
        strategy_parameters_by_symbol=V6.parameter_map(),
        trade_policies_by_symbol=V6.policy_map(),
        strategy_semantics=V6.semantics,
        strategy_version=V6.version,
        starting_cash=Decimal("250.00"),
    )
    assert expected.fills
    accounts = []
    for name, stops in (("whole", (2200,)), ("restart", (800, 1300, 2200))):
        path = str(tmp_path / f"{name}.sqlite3")
        initialize_paper_at_latest(
            path,
            {s: p[:400] for s, p in points.items()},
            at=start,
            strategy_key=V6.key,
            strategy_version=V6.version,
        )
        for stop in stops:
            process_points(
                path,
                {s: p[:stop] for s, p in points.items()},
                rules,
                strategy_key=V6.key,
                strategy_version=V6.version,
                execution_candles_by_symbol={s: c[:stop] for s, c in candles.items()},
                trade_policies_by_symbol=V6.policy_map(),
            )
        with PaperStore(path) as store:
            fills = sorted(
                (e for e in store.load_events(limit=5000) if e.status == "FILLED"),
                key=lambda e: (
                    e.occurred_at_utc,
                    0 if e.action == "EXIT_LONG" else 1,
                    next(i for i, f in enumerate(expected.fills) if f.signal_id == e.signal_id),
                ),
            )
            assert [(e.signal_id, e.execution_price, e.base_quantity) for e in fills] == [
                (f.signal_id, f.fill_price, f.base_quantity) for f in expected.fills
            ]
            accounts.append((store.load_account(), store.load_positions(), store.load_dust()))
        actual = load_paper_portfolio(
            path,
            {s: Decimal(str(c[-1].close)) for s, c in candles.items()},
            strategy_key=V6.key,
            strategy_version=V6.version,
        )
        assert abs(actual.equity_usdc - expected.metrics.ending_equity) < Decimal("1e-20")
    assert accounts[0] == accounts[1]


def test_profile_batch_single_and_chart_share_the_same_decisions() -> None:
    candles = {s: _profile_candles(s, 1000) for s in SYMBOLS}
    start = candles[SYMBOLS[0]][400].open_time_utc
    end = candles[SYMBOLS[0]][-1].open_time_utc + timedelta(hours=1)
    batch = run_isolated_batch(
        candles_by_symbol=candles,
        report_start_utc=start,
        report_end_utc=end,
        strategy_parameters=V6.parameters,
        strategy_parameters_by_symbol=V6.parameter_map(),
        trade_policies_by_symbol=V6.policy_map(),
        strategy_semantics=V6.semantics,
        strategy_version=V6.version,
    )
    for symbol, result in zip(SYMBOLS, batch.results, strict=True):
        assert result.fills, symbol
        single = run_single_backtest(
            symbol=symbol,
            candles=candles[symbol],
            report_start_utc=start,
            report_end_utc=end,
            strategy_parameters=V6.parameters_for(symbol),
            trade_policy=V6.policy_for(symbol),
            strategy_semantics=V6.semantics,
            strategy_version=V6.version,
        )
        assert result == single
        points = evaluate_batch(
            symbol,
            candles[symbol],
            parameters=V6.parameters_for(symbol),
            semantics=V6.semantics,
            strategy_version=V6.version,
        )
        blocked = {item.split(":", 1)[0] for item in result.blocked_signals}
        assert [m["signal_id"] for m in strategy_markers(points, V6.policy_for(symbol))] == [
            signal.signal_id for signal in result.signals if signal.signal_id not in blocked
        ]


def test_v6_activation_preserves_global_risk_history_and_dust(tmp_path: Path) -> None:
    path = str(tmp_path / "migration.sqlite3")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    initialize_paper_at_latest(path, _mapping(start), at=start)
    with PaperStore(path) as store:
        account = replace(
            store.load_account(),
            cash_usdc=Decimal("160.00"),
            high_water_equity_usdc=Decimal("300"),
            halted=True,
            halt_reason="MAX_DRAWDOWN_20_PERCENT",
        )
        store.save_account(account)
        store.upsert_position(
            PaperPosition(
                symbol="BTCUSDC",
                quantity=Decimal("0.80345"),
                average_price=Decimal("100"),
                cost_basis_usdc=Decimal("80"),
                entry_time_utc=start,
                entry_signal_id="legacy-buy",
                entry_fee_usdc=Decimal("0.08"),
                updated_at_utc=start,
            )
        )
    rules = dict.fromkeys(SYMBOLS, ExecutionRules(step_size=Decimal("0.01")))
    approved = replace(V6, paper_approved=True)
    events = activate_paper_strategy(path, _mapping(start), rules, approved, at=start)
    assert len(events) == 1
    with PaperStore(path) as store:
        assert store.load_strategy_session().strategy_key == "v6"
        assert store.load_account().high_water_equity_usdc == Decimal("300")
        assert store.load_account().halted is True
        assert store.load_account().starting_cash_usdc == Decimal("240.00")
        assert store.load_account().cash_usdc == Decimal("160") + events[0].quote_amount_usdc
        assert store.load_dust()["BTCUSDC"] == Decimal("0.00345")
        assert store.load_positions() == ()
        assert store.load_strategy_session().starting_equity_usdc == (
            store.load_account().cash_usdc + Decimal("0.00345") * 101
        )
    assert activate_paper_strategy(path, _mapping(start), _rules(), approved, at=start) == ()


def test_runtime_api_exposes_the_actual_coin_profiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(STRATEGY_DEFINITIONS, V6.key, replace(V6, paper_approved=True))
    config = replace(_config(tmp_path), strategy_key="v6")
    client = TestClient(
        create_app(config, RuntimeSupervisor(config)), base_url="http://127.0.0.1:8765"
    )
    assert client.get("/api/status").json()["strategy_profiles"] == V6.profiles_payload()
    markets = client.get("/api/markets").json()["markets"]
    assert len(markets) == 10
    assert {m["symbol"]: m["strategy_profile"] for m in markets} == V6.profiles_payload()


def test_v6_paper_cannot_run_without_its_policy_map(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="complete coin-policy"):
        process_points(
            str(tmp_path / "missing.sqlite3"),
            _mapping(datetime.now(UTC)),
            _rules(),
            strategy_key=V6.key,
            strategy_version=V6.version,
        )


def test_xrp_stop_survives_restart_and_fills_at_next_open_not_stop_price(tmp_path: Path) -> None:
    path = str(tmp_path / "stop.sqlite3")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    points = {
        s: tuple(
            replace(_point(s, start + timedelta(hours=i)), strategy_version=V6.version)
            for i in range(24)
        )
        for s in SYMBOLS
    }
    initialize_paper_at_latest(
        path, points, at=start, strategy_key=V6.key, strategy_version=V6.version
    )
    for i in (24, 25):
        for s in SYMBOLS:
            p = replace(
                _point(
                    s, start + timedelta(hours=i), flip_up=s == "XRPUSDC" and i == 24, strength=1.0
                ),
                strategy_version=V6.version,
            )
            if s == "XRPUSDC" and i == 25:
                # ATR expansion must not move the frozen entry-ATR stop away.
                p = replace(p, candle=replace(p.candle, close=95, low=94), atr=100)
            points[s] += (p,)
        execution = {
            s: [
                replace(
                    p.candle,
                    open_time_utc=p.candle.close_time_utc,
                    close_time_utc=p.candle.close_time_utc + timedelta(hours=1),
                    open=90 if i == 25 else 100,
                    low=89 if i == 25 else 98,
                )
                for p in values
            ]
            for s, values in points.items()
        }
        events = process_points(
            path,
            points,
            _rules(),
            strategy_key=V6.key,
            strategy_version=V6.version,
            execution_candles_by_symbol=execution,
            trade_policies_by_symbol=V6.policy_map(),
        )
        assert len(events) == 1
        if i == 24:
            with PaperStore(path) as store:
                assert store.load_positions()[0].entry_atr == Decimal("1")
        else:
            assert events[0].reason == "POLICY_STOP_ATR"
            assert events[0].execution_price == Decimal("89.955")
            with PaperStore(path) as store:
                assert store.load_positions() == ()


def test_new_v6_account_has_reserve_but_reinitialization_never_gifts_cash(tmp_path: Path) -> None:
    with PaperStore(tmp_path / "cash.sqlite3") as store:
        store.initialize(strategy_key=V6.key, strategy_version=V6.version)
        assert store.load_account().cash_usdc == Decimal("250")
        store.save_account(replace(store.load_account(), cash_usdc=Decimal("231")))
        store.initialize(strategy_key=V6.key, strategy_version=V6.version)
        assert store.load_account().cash_usdc == Decimal("231")


def test_unapproved_mix_cannot_activate_or_start_paper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    unapproved = replace(V6, paper_approved=False)
    monkeypatch.setitem(STRATEGY_DEFINITIONS, V6.key, unapproved)
    with pytest.raises(ValueError, match="not approved"):
        RuntimeSupervisor(replace(_config(tmp_path), strategy_key=V6.key))
    with pytest.raises(ValueError, match="not approved"):
        activate_paper_strategy(str(tmp_path / "denied.sqlite3"), {}, {}, unapproved)
    assert not (tmp_path / "denied.sqlite3").exists()


def test_ten_slots_bound_the_market_universe_within_the_existing_capital() -> None:
    assert PaperSettings(slot_count=4, target_notional_usdc=Decimal("45")).slot_count == 4
    with pytest.raises(ValueError, match="10 simultaneous"):
        PaperSettings(slot_count=11, target_notional_usdc=Decimal("10"))


@pytest.mark.parametrize("first_endpoint", ["/api/status", "/api/paper/events"])
def test_new_v2_runtime_uses_configured_reserve_from_first_api_call(
    tmp_path: Path, first_endpoint: str,
) -> None:
    config = replace(_config(tmp_path), paper_starting_cash_usdc=Decimal("250.00"))
    client = TestClient(create_app(config, RuntimeSupervisor(config)),
                        base_url="http://127.0.0.1:8765")
    assert client.get(first_endpoint).status_code == 200
    # Before data initialization there is intentionally no complete Paper/soak payload.
    client.get("/api/status")
    with PaperStore(config.database_path) as store:
        assert store.load_account().cash_usdc == Decimal("250.00")
