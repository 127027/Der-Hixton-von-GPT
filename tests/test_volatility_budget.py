"""Causal risk sizing, persistent submission guards and Paper/backtest parity."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import pytest

from hixton.backtest.models import ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.backtest.reporting import write_report_bundle
from hixton.domain.spot_autonomy import entry_volatility_fraction
from hixton.domain.strategy import evaluate_batch
from hixton.domain.versions import STRATEGY_DEFINITIONS, strategy_definition
from hixton.paper.engine import (
    initialize_paper_at_latest,
    load_paper_portfolio,
    process_new_closed_points,
)
from hixton.paper.models import PaperSettings
from hixton.paper.storage import PaperStore
from tests.golden_reference import deterministic_candles
from tests.test_live_production import controller, enable_now, universe


def candidate():
    return replace(
        strategy_definition("v8"),
        key="v8d",
        paper_approved=False,
        version="HIXTON-V8-VOLATILITY-RESEARCH-TEST",
        entry_atr_target_fraction="0.01",
    )


def test_size_uses_signal_volatility_without_borrowing_or_loss_guarantees():
    assert entry_volatility_fraction(
        atr=D(2), reference_close=D(100), target_atr_fraction=D(".01")
    ) == D(".5")
    assert entry_volatility_fraction(
        atr=D(".5"), reference_close=D(100), target_atr_fraction=D(".01")
    ) == D(1)
    assert entry_volatility_fraction(
        atr=D(2), reference_close=D(100), target_atr_fraction=D(".01"), capital_fraction=D(".35")
    ) == D(".175")
    assert entry_volatility_fraction(atr=D(2), reference_close=D(100)) == D(1)


@pytest.mark.parametrize(
    "atr,close,target",
    [
        ("0", "100", ".01"),
        ("2", "0", ".01"),
        ("NaN", "100", ".01"),
        ("2", "100", "0"),
        ("2", "100", "Infinity"),
    ],
)
def test_missing_or_invalid_risk_input_cannot_give_full_budget(atr, close, target):
    with pytest.raises(ValueError):
        entry_volatility_fraction(
            atr=D(atr), reference_close=D(close), target_atr_fraction=D(target)
        )


def test_default_profiles_and_config_identity_are_unchanged():
    for key in ("v6", "v8", "v8d"):
        assert strategy_definition(key).entry_atr_target_fraction is None
        assert "entry_atr_target_fraction" not in strategy_definition(key).config_payload()
    for invalid in ("NaN", "0", "-0.1", "1.1"):
        with pytest.raises(ValueError):
            replace(strategy_definition("v8"), entry_atr_target_fraction=invalid)


@pytest.mark.parametrize("auto", [False, True])
@pytest.mark.parametrize("registered", [False, True])
def test_volatility_sizing_has_identical_paper_fills_and_survives_restart(
    tmp_path, monkeypatch, auto, registered
):
    strategy = strategy_definition("v8r") if registered else candidate()
    monkeypatch.setitem(STRATEGY_DEFINITIONS, strategy.key, strategy)
    candles = {s: deterministic_candles(s, 1100) for s in strategy.symbols}
    points = {
        s: tuple(
            evaluate_batch(
                s,
                candles[s],
                parameters=strategy.parameters_for(s),
                semantics=strategy.semantics_for(s),
                strategy_version=strategy.version,
            )
        )
        for s in strategy.symbols
    }
    first = next(iter(candles.values()))
    start = first[400].open_time_utc
    end = first[-1].open_time_utc + timedelta(hours=1)
    rules = {s: ExecutionRules(step_size=D(".000001"), min_notional=D(5)) for s in strategy.symbols}
    reference = run_shared_portfolio_backtest(
        candles_by_symbol=candles,
        report_start_utc=start,
        report_end_utc=end,
        starting_cash=D(250),
        target_notional=D(125),
        execution_rules=rules,
        strategy=strategy,
        reinvest_profits=auto,
        autonomous_spot=True,
    )
    assert reference.fills
    bundle = write_report_bundle(
        scenarios={"current": reference},
        output_root=tmp_path / "reports",
        config_sha256="fixture",
        code_commit="OFFLINE_TEST",
        report_start_utc=start,
        report_end_utc=end,
        strategy=strategy,
    )
    manifest = json.loads((bundle / "manifest.json").read_text())
    assert manifest["strategy"]["entry_atr_target_fraction"] == strategy.entry_atr_target_fraction
    for name, stops in [("whole", [1100]), ("restart", [750, 1100])]:
        path = tmp_path / (name + ".sqlite3")
        initialize_paper_at_latest(
            str(path),
            {s: p[:400] for s, p in points.items()},
            at=start,
            strategy_key=strategy.key,
            strategy_version=strategy.version,
            starting_cash_usdc=D(250),
        )
        with PaperStore(path) as store:
            store.save_settings(
                PaperSettings(
                    max_capital_usdc=D(250),
                    auto_budget_enabled=auto,
                    autonomous_performance_enabled=True,
                )
            )
        for stop in stops:
            process_new_closed_points(
                str(path),
                {s: p[:stop] for s, p in points.items()},
                rules,
                strategy_key=strategy.key,
                strategy_version=strategy.version,
                execution_candles_by_symbol={s: c[:stop] for s, c in candles.items()},
                trade_policies_by_symbol=strategy.policy_map(),
                slot_allocation=strategy.slot_allocation,
            )
        with PaperStore(path) as store:
            events = [e for e in store.load_events(limit=5000) if e.status == "FILLED"]
        portfolio = load_paper_portfolio(
            str(path),
            {s: D(str(c[-1].close)) for s, c in candles.items()},
            strategy_key=strategy.key,
            strategy_version=strategy.version,
        )
        assert abs(portfolio.equity_usdc - reference.metrics.ending_equity) < D("1e-20")
        assert sorted((e.signal_id, e.base_quantity) for e in events) == sorted(
            (f.signal_id, f.base_quantity) for f in reference.fills
        )


@pytest.mark.parametrize("auto", [False, True])
def test_live_uses_frozen_signal_risk_after_pending_restart(tmp_path, auto):
    strategy = candidate()
    at = datetime.now(UTC).replace(second=0, microsecond=0)

    def history(at, enter=False, atr=4):
        old = universe(at, enter=("BTCUSDC",) if enter else ())
        sample = old["BTCUSDC"]
        return {
            s: tuple(
                replace(
                    p,
                    symbol=s,
                    strategy_version=strategy.version,
                    candle=replace(p.candle, symbol=s),
                    atr=float(atr),
                    flip_up=p.flip_up if s == "BTCUSDC" else False,
                )
                for p in old.get(s, sample)
            )
            for s in strategy.symbols
        }

    c, exchange, account, _settings = controller(tmp_path)
    c.strategy = strategy
    c.autonomous_spot = lambda: auto
    c.rules = lambda: {
        s: ExecutionRules(step_size=D(".000001"), min_notional=D(5)) for s in strategy.symbols
    }
    c.market_points = lambda: history(at, True)
    enable_now(c, account, history(at - timedelta(hours=1)))
    c.advance(history(at, True), now=at, healthy=True)  # Persist intent, do not submit.
    assert not exchange.submits
    # Reconstruct controller with changed current ATR: frozen entry ATR must win.
    resumed, new_exchange, new_account, _settings = controller(tmp_path)
    resumed.strategy = strategy
    resumed.autonomous_spot = lambda: auto
    resumed.rules = c.rules
    resumed.market_points = lambda: history(at, True, atr=1)
    for _ in range(4):
        resumed.advance(history(at, True, atr=1), now=at, healthy=True)
    assert len(new_exchange.submits) == 1
    expected = D("63.12") if auto else D("63.125")
    assert new_exchange.submits[0].quote_budget == expected
    assert new_account.balances["USDC"][0] == D(250) - expected
    assert not resumed.pre_submit(replace(new_exchange.submits[0], quote_budget=D(250)))
