from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from hixton.backtest.models import ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.constants import SYMBOLS
from hixton.domain.strategy import evaluate_batch
from hixton.domain.versions import V2_RESEARCH_STRATEGY
from hixton.paper.engine import initialize_paper_at_latest, load_paper_portfolio
from hixton.paper.engine import process_new_closed_points as process_points
from hixton.paper.storage import PaperStore
from hixton.runtime.supervisor import safe_closed_window
from hixton.ui.chart import build_chart_payload
from tests.golden_reference import deterministic_candles
from tests.test_paper_engine import _mapping, _point, _rules


def test_runtime_includes_just_closed_bar_before_two_minute_grace() -> None:
    now = datetime(2026, 9, 5, 10, 0, 30, tzinfo=UTC)
    assert safe_closed_window(now)[2] == now.replace(second=0)


def test_paper_waits_for_actual_next_open_and_preserves_audit(tmp_path: Path) -> None:
    path = str(tmp_path / "paper.sqlite3")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    initialize_paper_at_latest(path, _mapping(start), at=start)
    at = start + timedelta(hours=1)
    points = _mapping(at)
    points[SYMBOLS[0]] = (_point(SYMBOLS[0], at, flip_up=True, strength=1),)
    assert process_points(path, points, _rules()) == ()
    with PaperStore(path) as store:
        assert store.checkpoint(SYMBOLS[0]) == start
    execution = {
        symbol: [
            replace(
                values[0].candle,
                open_time_utc=at,
                close_time_utc=at + timedelta(hours=1),
                open=150,
                high=151,
                low=149,
                close=150,
                closed=False,
            )
        ]
        for symbol, values in points.items()
    }
    events = process_points(path, points, _rules(), execution_candles_by_symbol=execution)
    assert len(events) == 1
    assert events[0].reference_price == Decimal("150")
    assert events[0].execution_price == Decimal("150.075")
    assert events[0].occurred_at_utc == at
    with PaperStore(path) as store:
        assert store.load_events()[0].execution_model == "NEXT_BAR_OPEN_V1"
        assert store.load_events()[0].processed_at_utc is not None
    chart = build_chart_payload(
        symbol=SYMBOLS[0],
        points=points[SYMBOLS[0]],
        range_key="today",
        timezone_name="UTC",
        now=at + timedelta(minutes=3),
        paper_events=events,
        live_candle=execution[SYMBOLS[0]][0],
    )
    assert chart["paper_events"][0]["display_time"] in {bar["time"] for bar in chart["bars"]}
    assert chart["bars"][-1]["provisional"] is True
    assert len(chart["signals"]) == 1
    midnight = start + timedelta(days=1)
    first_bar = replace(
        execution[SYMBOLS[0]][0],
        open_time_utc=midnight,
        close_time_utc=midnight + timedelta(hours=1),
    )
    midnight_chart = build_chart_payload(
        symbol=SYMBOLS[0],
        points=(_point(SYMBOLS[0], midnight),),
        range_key="today",
        timezone_name="UTC",
        now=midnight + timedelta(seconds=30),
        live_candle=first_bar,
    )
    assert midnight_chart["available"] is True
    assert len(midnight_chart["bars"]) == 1
    assert midnight_chart["signals"] == []


def test_production_paper_and_portfolio_match_with_gaps_rounding_and_mixed_close_times(
    tmp_path: Path,
) -> None:
    strategy = replace(
        V2_RESEARCH_STRATEGY,
        parameters=replace(V2_RESEARCH_STRATEGY.parameters, band_multiplier=0.8),
    )
    candles = {}
    points = {}
    for number, symbol in enumerate(SYMBOLS):
        candles[symbol] = [
            replace(
                candle,
                open=candle.open * 1.008,
                high=max(candle.high, candle.open * 1.008),
                close_time_utc=candle.open_time_utc
                + timedelta(hours=1)
                - timedelta(milliseconds=1 + number),
            )
            for candle in deterministic_candles(symbol, 1600)
        ]
        points[symbol] = tuple(
            evaluate_batch(
                symbol,
                candles[symbol],
                parameters=strategy.parameters,
                semantics=strategy.semantics,
                strategy_version=strategy.version,
            )
        )
    rule = ExecutionRules(
        step_size=Decimal("0.01"), min_qty=Decimal("0.01"), min_notional=Decimal("5")
    )
    rules = dict.fromkeys(SYMBOLS, rule)
    start = candles[SYMBOLS[0]][400].open_time_utc
    end = candles[SYMBOLS[0]][-1].open_time_utc + timedelta(hours=1)
    reference = run_shared_portfolio_backtest(
        candles_by_symbol=candles,
        report_start_utc=start,
        report_end_utc=end,
        execution_rules=rules,
        strategy_parameters=strategy.parameters,
        strategy_semantics=strategy.semantics,
        strategy_version=strategy.version,
    )
    assert reference.fills, "fixture must exercise actual fills"
    path = str(tmp_path / "paper.sqlite3")
    initialize_paper_at_latest(
        path,
        {s: p[:400] for s, p in points.items()},
        at=start,
        strategy_key=strategy.key,
        strategy_version=strategy.version,
    )
    events = process_points(
        path,
        points,
        rules,
        strategy_key=strategy.key,
        strategy_version=strategy.version,
        execution_candles_by_symbol=candles,
    )
    fills = [event for event in events if event.status == "FILLED"]
    assert [
        (e.signal_id, e.reference_price, e.execution_price, e.base_quantity) for e in fills
    ] == [(f.signal_id, f.reference_open, f.fill_price, f.base_quantity) for f in reference.fills]
    prices = {s: Decimal(str(c[-1].close)) for s, c in candles.items()}
    actual = load_paper_portfolio(
        path, prices, strategy_key=strategy.key, strategy_version=strategy.version
    )
    assert abs(actual.equity_usdc - reference.metrics.ending_equity) < Decimal("1e-20")
    with PaperStore(path) as store:
        assert sum(store.load_dust().values()) > 0
    # The same replay split by a process restart must produce the identical ledger.
    restart_path = str(tmp_path / "restart.sqlite3")
    initialize_paper_at_latest(
        restart_path,
        {s: p[:400] for s, p in points.items()},
        at=start,
        strategy_key=strategy.key,
        strategy_version=strategy.version,
    )
    for stop in (850, 1600):
        process_points(
            restart_path,
            {s: p[:stop] for s, p in points.items()},
            rules,
            strategy_key=strategy.key,
            strategy_version=strategy.version,
            execution_candles_by_symbol={s: c[:stop] for s, c in candles.items()},
        )
    with PaperStore(path) as whole, PaperStore(restart_path) as restarted:
        assert whole.load_account() == restarted.load_account()
        assert whole.load_positions() == restarted.load_positions()
        assert whole.load_dust() == restarted.load_dust()
        assert [e.event_id for e in whole.load_events()] == [
            e.event_id for e in restarted.load_events()
        ]


def test_live_candle_expires_and_old_updates_cannot_replace_it() -> None:
    from hixton.runtime.state import RuntimeState

    state = RuntimeState()
    now = datetime.now(UTC)
    candle = replace(deterministic_candles(SYMBOLS[0], 1)[0], closed=False)
    state.set_live_candle(candle, at=now)
    state.set_live_candle(
        replace(candle, open_time_utc=candle.open_time_utc - timedelta(hours=1)), at=now
    )
    assert state.live_candle(SYMBOLS[0], now=now)[0] == candle
    assert state.live_candle(SYMBOLS[0], now=now + timedelta(seconds=89)) is not None
    assert state.live_candle(SYMBOLS[0], now=now + timedelta(seconds=91)) is None


def test_execution_upgrade_preserves_account_positions_and_history(tmp_path: Path) -> None:
    from tests.test_paper_engine import process_new_closed_points

    path = str(tmp_path / "legacy.sqlite3")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    initialize_paper_at_latest(path, _mapping(start), at=start)
    points = _mapping(start + timedelta(hours=1))
    points[SYMBOLS[0]] = (_point(SYMBOLS[0], start + timedelta(hours=1), flip_up=True),)
    process_new_closed_points(path, points, _rules())
    with PaperStore(path) as store:
        # Emulate an old database without an execution epoch; no production history is edited.
        store._connection.execute(
            "DELETE FROM paper_audit WHERE action='EXECUTION_NEXT_BAR_OPEN_V1_ACTIVATED'"
        )
        store._connection.commit()
        before = (store.load_account(), store.load_positions(), store.load_events())
        assert store.ensure_execution_epoch(store.all_checkpoints(), at=start + timedelta(days=3))
        assert before == (store.load_account(), store.load_positions(), store.load_events())
        assert (
            store.load_soak_progress(at=start + timedelta(days=3)).minimum_processed_closed_bars
            == 0
        )
        assert not store.ensure_execution_epoch(
            store.all_checkpoints(), at=start + timedelta(days=4)
        )


def test_coin_parameter_map_requires_all_ten_symbols() -> None:
    import pytest

    with pytest.raises(ValueError, match="all ten"):
        run_shared_portfolio_backtest(
            candles_by_symbol={symbol: [] for symbol in SYMBOLS},
            report_start_utc=datetime(2023, 1, 1, tzinfo=UTC),
            report_end_utc=datetime(2026, 1, 1, tzinfo=UTC),
            strategy_parameters_by_symbol={"BTCUSDC": V2_RESEARCH_STRATEGY.parameters},
        )
