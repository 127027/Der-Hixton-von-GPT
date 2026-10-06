"""Exercise V8's actual product reports, historical fallback and Paper routing."""

import json
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from hixton.backtest.comparison import compare_run
from hixton.backtest.continuity import load_continuity_history
from hixton.backtest.models import CURRENT_COSTS, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.backtest.product import run_product_backtest
from hixton.backtest.reporting import source_fingerprint
from hixton.data.storage import CandleStore, StoredSymbolRules
from hixton.domain.models import SignalAction
from hixton.domain.strategy import evaluate_batch
from hixton.domain.versions import V8_SATELLITE_STRATEGY as STRATEGY
from hixton.paper.engine import initialize_paper_at_latest, process_new_closed_points
from hixton.paper.models import PaperEventStatus, PaperSettings
from hixton.paper.storage import PaperStore
from tests.golden_reference import deterministic_candles
from tests.test_live_preparation import config_for


@pytest.fixture
def history_fixture(tmp_path, monkeypatch):
    config = replace(
        config_for(tmp_path),
        strategy_key="v8",
        run_output_root=tmp_path / "backtests" / "v8" / "runs",
    )
    candles = {}
    for index, symbol in enumerate(STRATEGY.symbols):
        raw = deterministic_candles(symbol, 1800, index * 11)
        candles[symbol] = [
            replace(
                c,
                high=max(c.open, c.close) + 0.01,
                low=min(c.open, c.close) - 0.01,
            )
            for c in raw
        ]
    first = candles[STRATEGY.symbols[0]][0].open_time_utc
    start = first + timedelta(hours=400)
    end = first + timedelta(hours=1800)
    rules = dict.fromkeys(
        STRATEGY.symbols,
        ExecutionRules(
            step_size=Decimal(".001"),
            min_qty=Decimal(".001"),
            min_notional=Decimal("5"),
        ),
    )
    with CandleStore(config.database_path) as store:
        for index, symbol in enumerate(STRATEGY.symbols):
            store.put_candles(candles[symbol][index * 10 :])
            store.put_symbol_rules(
                StoredSymbolRules(
                    symbol,
                    "TRADING",
                    "USDC",
                    True,
                    ("MARKET",),
                    Decimal(".01"),
                    Decimal(".001"),
                    Decimal(".001"),
                    Decimal("5"),
                    end,
                )
            )
    requests = []

    class Public:
        def __init__(self, **kwargs):
            pass

        def fetch_klines(self, symbol, *, start, end_exclusive):
            requests.append((symbol, start, end_exclusive))
            native_symbol = symbol.removesuffix("USDT") + "USDC"
            return [
                replace(c, symbol=symbol)
                for c in candles[native_symbol]
                if start <= c.open_time_utc < end_exclusive
            ]

    monkeypatch.setattr("hixton.backtest.continuity.BinancePublicClient", Public)
    return config, candles, rules, start, end, requests


@pytest.mark.parametrize("mode", ["all", "portfolio", "single"])
def test_product_reports_cover_v8_window_and_saved_budget(history_fixture, mode):
    config, _candles, _rules, start, end, _requests = history_fixture
    with PaperStore(config.database_path) as store:
        store.initialize(strategy_key="v8", strategy_version=STRATEGY.version)
        store.save_settings(PaperSettings(max_capital_usdc=Decimal("300")))
        before = store.load_account()
    output = run_product_backtest(
        config,
        mode=mode,
        symbol="NEARUSDC" if mode == "single" else None,
        report_start_utc=start,
        report_end_utc=end,
        code_commit="TEST",
        source_sha256=source_fingerprint(),
    )
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    assert manifest["data"]["report_start_utc"] == start.isoformat()
    assert manifest["data"]["report_end_utc"] == end.isoformat()
    assert manifest["data"]["historical_usdc_liquidity_claimed"] is False
    with PaperStore(config.database_path) as store:
        assert store.load_account() == before
        comparison = compare_run(
            manifest,
            metrics,
            active=STRATEGY,
            settings=store.load_settings(),
            starting_cash=Decimal("300"),
            source_hash=source_fingerprint(),
        )
    assert comparison["status"] == "MATCHING", comparison
    current = metrics["current"]
    if mode == "all":
        assert set(current["per_symbol"]) == set(STRATEGY.symbols)
        assert Decimal(current["batch"]["starting_equity"]) == 4500
        assert all(Decimal(m["starting_equity"]) == 300 for m in current["per_symbol"].values())
    elif mode == "portfolio":
        assert current["portfolio"]["symbols"] == list(STRATEGY.symbols)
        assert Decimal(current["portfolio"]["starting_cash"]) == 300
        assert Decimal(current["portfolio"]["target_notional"]) == 150
        assert current["portfolio"]["slot_count"] == 2
    else:
        assert list(current["per_symbol"]) == ["NEARUSDC"]


def test_historical_proxy_fills_only_missing_prefix_and_is_cached(history_fixture):
    config, candles, rules, start, end, requests = history_fixture
    kwargs = {
        "strategy": STRATEGY,
        "report_start_utc": start,
        "report_end_utc": end,
        "execution_rules": rules,
        "native_database_path": config.database_path,
        "cache_path": config.database_path.parent / "backtest-history.sqlite3",
    }
    history = load_continuity_history(**kwargs)
    assert len(requests) == 14  # BTC has the entire native USDC history.
    for index, symbol in enumerate(STRATEGY.symbols):
        assert history.provenance_by_symbol[symbol]["proxy_candle_count"] == index * 10
        series = history.candles_by_symbol[symbol]
        assert series[index * 10 :] == candles[symbol][index * 10 :]
    requests.clear()
    assert load_continuity_history(**kwargs).candles_by_symbol == history.candles_by_symbol
    assert requests == []
    with CandleStore(config.database_path) as store:
        assert store.load_candles("NEARUSDT") == []


@pytest.mark.parametrize("fillers_enabled", [True, False])
def test_v8_shared_execution_matches_paper_with_filler_capacity_handoffs(
    history_fixture, fillers_enabled
):
    config, candles, rules, start, end, _requests = history_fixture
    result = run_shared_portfolio_backtest(
        candles_by_symbol=candles,
        report_start_utc=start,
        report_end_utc=end,
        execution_rules=rules,
        costs=CURRENT_COSTS,
        strategy=replace(
            STRATEGY,
            active_shared_satellites=STRATEGY.active_shared_satellites if fillers_enabled else (),
        ),
    )
    points = {
        s: tuple(
            evaluate_batch(
                s,
                values,
                parameters=STRATEGY.parameters_for(s),
                semantics=STRATEGY.semantics_for(s),
                strategy_version=STRATEGY.version,
            )
        )
        for s, values in candles.items()
    }
    initialize_paper_at_latest(
        str(config.database_path),
        {s: p[:400] for s, p in points.items()},
        strategy_key="v8",
        strategy_version=STRATEGY.version,
        starting_cash_usdc=Decimal("250"),
    )
    with PaperStore(config.database_path) as store:
        store.save_settings(PaperSettings(gap_fillers_enabled=fillers_enabled))
    events = process_new_closed_points(
        str(config.database_path),
        points,
        rules,
        strategy_key="v8",
        strategy_version=STRATEGY.version,
        execution_candles_by_symbol=candles,
        trade_policies_by_symbol=STRATEGY.policy_map(),
        slot_allocation=STRATEGY.slot_allocation,
    )
    filled = [e for e in events if e.status == PaperEventStatus.FILLED]
    assert len(filled) > 10
    assert len(filled) == len(result.fills)
    for event, fill in zip(filled, result.fills, strict=True):
        assert event.action == fill.action.value
        assert event.occurred_at_utc == fill.fill_time_utc
        assert event.execution_price == fill.fill_price
        assert event.base_quantity == fill.base_quantity
    research = set(STRATEGY.satellite_symbols) - set(STRATEGY.active_shared_satellites)
    assert not research.intersection(e.symbol for e in filled)
    assert any(e.symbol in STRATEGY.active_shared_satellites for e in filled) == fillers_enabled
    if fillers_enabled:
        assert any(e.reason and e.reason.startswith("CORE_CAPACITY_HANDOFF") for e in filled)
    assert any(e.action == SignalAction.ENTER_LONG.value and e.symbol == "BTCUSDC" for e in filled)


def test_v8_future_price_changes_cannot_change_earlier_fills(history_fixture):
    from dataclasses import replace

    _config, candles, rules, start, end, _requests = history_fixture
    cutoff = start + (end - start) / 2
    changed = {
        s: [
            replace(c, open=c.open * 2, high=c.high * 2, low=c.low * 2, close=c.close * 2)
            if c.open_time_utc >= cutoff
            else c
            for c in bars
        ]
        for s, bars in candles.items()
    }
    results = [
        run_shared_portfolio_backtest(
            candles_by_symbol=data,
            report_start_utc=start,
            report_end_utc=end,
            execution_rules=rules,
            costs=CURRENT_COSTS,
            strategy=STRATEGY,
        )
        for data in (candles, changed)
    ]
    prefixes = [tuple(f for f in r.fills if f.fill_time_utc < cutoff) for r in results]
    assert len(prefixes[0]) > 5
    assert prefixes[0] == prefixes[1]


def test_v8_cli_activation_preserves_budget_and_cash_for_all_fifteen_markets(
    history_fixture, monkeypatch
):
    from argparse import Namespace

    from hixton import cli

    config, candles, _rules, start, end, _requests = history_fixture
    with PaperStore(config.database_path) as store:
        store.initialize(strategy_key="v8", strategy_version="HIXTON-V8-PREVIOUS")
        store.save_settings(PaperSettings(max_capital_usdc=Decimal("300")))
        before = store.load_account()
    first = candles[STRATEGY.symbols[0]][0].open_time_utc
    monkeypatch.setattr(cli, "_window", lambda _: (first, start, end))
    assert (
        cli.command_paper_activate(Namespace(strategy="v8", confirmation="AKTIVIEREN"), config) == 0
    )
    with PaperStore(config.database_path) as store:
        assert store.load_strategy_session().strategy_version == STRATEGY.version
        assert store.load_account().cash_usdc == before.cash_usdc
        assert store.load_settings().max_capital_usdc == 300
        assert set(store.all_checkpoints()) == set(STRATEGY.symbols)


def test_saved_filler_switch_disables_entries_and_invalidates_comparison(history_fixture):
    config, _candles, _rules, start, end, _requests = history_fixture
    with PaperStore(config.database_path) as store:
        store.initialize(strategy_key="v8", strategy_version=STRATEGY.version)
        store.save_settings(
            PaperSettings(max_capital_usdc=Decimal("300"), gap_fillers_enabled=False)
        )
        assert store.load_settings().gap_fillers_enabled is False
        account = store.load_account()
    output = run_product_backtest(
        config, mode="portfolio", symbol=None, report_start_utc=start, report_end_utc=end,
        code_commit="TEST", source_sha256=source_fingerprint(),
    )
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    assert manifest["strategy"]["active_shared_satellites"] == []
    for profile in STRATEGY.satellite_symbols:
        assert not (output / "trades.csv").read_text(encoding="utf-8").count(profile)
    with PaperStore(config.database_path) as store:
        assert store.load_account() == account
        settings = store.load_settings()
    kwargs = {
        "active": STRATEGY, "starting_cash": Decimal("300"), "source_hash": source_fingerprint(),
    }
    assert compare_run(manifest, metrics, settings=settings, **kwargs)["status"] == "MATCHING"
    enabled = PaperSettings(max_capital_usdc=Decimal("300"), gap_fillers_enabled=True)
    assert compare_run(manifest, metrics, settings=enabled, **kwargs)["status"] == "DIFFERENT"
