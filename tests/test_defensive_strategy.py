from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import pytest

from hixton.backtest.models import ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.domain.strategy import evaluate_batch
from hixton.domain.versions import strategy_definition
from hixton.paper.engine import (
    initialize_paper_at_latest,
    load_paper_portfolio,
    process_new_closed_points,
)
from hixton.paper.models import PaperSettings
from hixton.paper.storage import PaperStore
from tests.golden_reference import deterministic_candles
from tests.test_live_production import controller, enable_now, universe


def test_candidate_is_explicit_research_and_preserves_all_signal_parameters():
    base = strategy_definition("v8")
    candidate = strategy_definition("v8d")
    assert not candidate.paper_approved
    assert candidate.coin_profiles == base.coin_profiles
    assert candidate.active_shared_satellites == base.active_shared_satellites
    assert candidate.slot_allocation == base.slot_allocation
    assert candidate.config_payload()["capital_exposure_fraction"] == "0.35"
    assert "capital_exposure_fraction" not in base.config_payload()
    assert candidate.version != base.version


@pytest.mark.parametrize("auto", [False, True])
def test_defensive_paper_matches_backtest_and_survives_restart(tmp_path, auto):
    strategy = strategy_definition("v8d")
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
    results = []
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
        results.append(portfolio.equity_usdc)
    assert results[0] == results[1]


@pytest.mark.parametrize("auto", [False, True])
def test_defensive_live_submits_same_scaled_budget_and_rejects_oversize(tmp_path, auto):
    at = datetime.now(UTC).replace(second=0, microsecond=0)
    c, exchange, account, _settings = controller(tmp_path)
    c.strategy = strategy_definition("v8d")

    def history(at, enter=()):
        old = universe(at, enter=enter)
        sample = old["BTCUSDC"]
        return {
            s: tuple(
                replace(
                    p,
                    symbol=s,
                    strategy_version=c.strategy.version,
                    candle=replace(p.candle, symbol=s),
                    flip_up=p.flip_up if s == "BTCUSDC" else False,
                )
                for p in old.get(s, sample)
            )
            for s in c.strategy.symbols
        }

    c.rules = lambda: {
        s: ExecutionRules(step_size=D(".000001"), min_notional=D(5)) for s in c.strategy.symbols
    }
    c.autonomous_spot = lambda: auto
    entry_points = history(at, enter=("BTCUSDC",))
    c.market_points = lambda: entry_points
    enable_now(c, account, history(at - timedelta(hours=1)))
    for _ in range(4):
        c.advance(entry_points, now=at, healthy=True)
    assert exchange.submits
    buy = exchange.submits[0]
    assert buy.quote_budget == D("87.5")
    assert account.balances["USDC"][0] == D("162.5")
    assert not c.pre_submit(
        replace(buy, intent_id="oversized", symbol="ETHUSDC", slot_count=1, quote_budget=D(100))
    )
