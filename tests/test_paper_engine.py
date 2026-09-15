from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from hixton.backtest.models import ExecutionRules
from hixton.constants import HIXTON_SPEC_VERSION, SYMBOLS
from hixton.domain.models import Candle, IndicatorPoint, TrendState
from hixton.domain.versions import V2_RESEARCH_STRATEGY, V3_SLOT_STRATEGY
from hixton.paper.engine import (
    activate_paper_strategy,
    initialize_paper_at_latest,
)
from hixton.paper.engine import (
    process_new_closed_points as process_points,
)
from hixton.paper.models import PaperEvent, PaperEventStatus, PaperSettings
from hixton.paper.storage import PaperStore


def process_new_closed_points(
    path: str,
    points: dict[str, tuple[IndicatorPoint, ...]],
    rules: dict[str, ExecutionRules],
    *,
    strategy_key: str = "v1",
    strategy_version: str = HIXTON_SPEC_VERSION,
) -> tuple[PaperEvent, ...]:
    # Explicit next bars: these fixtures formerly hid the close-vs-open discrepancy.
    execution = {
        symbol: [
            replace(
                point.candle,
                open_time_utc=point.candle.open_time_utc + timedelta(hours=1),
                close_time_utc=point.candle.close_time_utc + timedelta(hours=1),
                open=101.0,
                closed=False,
            )
            for point in values
        ]
        for symbol, values in points.items()
    }
    return process_points(
        path,
        points,
        rules,
        strategy_key=strategy_key,
        strategy_version=strategy_version,
        execution_candles_by_symbol=execution,
    )


def _point(
    symbol: str,
    close_time: datetime,
    *,
    flip_up: bool = False,
    flip_down: bool = False,
    strength: float | None = None,
) -> IndicatorPoint:
    open_time = close_time - timedelta(hours=1)
    candle = Candle(
        symbol=symbol,
        open_time_utc=open_time,
        close_time_utc=close_time,
        open=100.0,
        high=102.0,
        low=98.0,
        close=101.0,
        volume=10.0,
    )
    return IndicatorPoint(
        symbol=symbol,
        strategy_version=HIXTON_SPEC_VERSION,
        index=500,
        candle=candle,
        abs_cmo=0.5,
        vidya_raw=100.0,
        vidya=100.0,
        true_range=4.0,
        atr=1.0,
        upper=100.5,
        lower=99.5,
        trend=TrendState.UP if flip_up else TrendState.DOWN,
        flip_up=flip_up,
        flip_down=flip_down,
        breakout_strength=strength,
        rank_strength=strength,
        tradable=True,
    )


def _mapping(at: datetime) -> dict[str, tuple[IndicatorPoint, ...]]:
    return {symbol: (_point(symbol, at),) for symbol in SYMBOLS}


def _rules() -> dict[str, ExecutionRules]:
    rules = ExecutionRules(
        step_size=Decimal("0.000001"),
        min_qty=Decimal("0.000001"),
        min_notional=Decimal("5"),
    )
    return dict.fromkeys(SYMBOLS, rules)


def test_startup_arms_at_latest_without_historical_orders(tmp_path: Path) -> None:
    path = tmp_path / "paper.sqlite3"
    start = datetime(2026, 1, 1, 0, tzinfo=UTC)
    points = {symbol: (_point(symbol, start, flip_up=True, strength=1.0),) for symbol in SYMBOLS}
    assert initialize_paper_at_latest(str(path), points, at=start) is True
    emitted = process_new_closed_points(str(path), points, _rules())
    assert emitted == ()
    with PaperStore(path) as store:
        assert store.load_account().cash_usdc == Decimal("240.00")
        assert store.load_positions() == ()


def test_restart_preserves_checkpoint_and_recovers_closed_bars(tmp_path: Path) -> None:
    path = tmp_path / "paper.sqlite3"
    start = datetime(2026, 1, 1, 0, tzinfo=UTC)
    assert initialize_paper_at_latest(str(path), _mapping(start), at=start) is True

    recovered_at = start + timedelta(hours=1)
    recovered = _mapping(recovered_at)
    recovered[SYMBOLS[0]] = (_point(SYMBOLS[0], recovered_at, flip_up=True, strength=2.0),)
    assert initialize_paper_at_latest(str(path), recovered, at=recovered_at) is False
    with PaperStore(path) as store:
        assert store.checkpoint(SYMBOLS[0]) == start

    emitted = process_new_closed_points(str(path), recovered, _rules())
    assert [(event.symbol, event.action) for event in emitted] == [(SYMBOLS[0], "ENTER_LONG")]
    with PaperStore(path) as store:
        assert store.checkpoint(SYMBOLS[0]) == recovered_at
        progress = store.load_soak_progress(at=recovered_at)
    assert progress.minimum_processed_closed_bars == 1
    assert progress.processed_closed_bars_by_symbol[SYMBOLS[0]] == 1


def test_paper_soak_gate_is_persistent_and_requires_all_three_thresholds(
    tmp_path: Path,
) -> None:
    path = tmp_path / "paper.sqlite3"
    start = datetime(2026, 1, 1, 0, tzinfo=UTC)
    initialize_paper_at_latest(str(path), _mapping(start), at=start)
    events = tuple(
        PaperEvent(
            event_id=f"event-{index}",
            signal_id=f"signal-{index}",
            occurred_at_utc=start + timedelta(hours=index + 1),
            symbol=SYMBOLS[index % len(SYMBOLS)],
            action="EXIT_LONG",
            status=PaperEventStatus.FILLED,
            reason=None,
            reference_price=Decimal("100"),
            execution_price=Decimal("100"),
            base_quantity=Decimal("1"),
            quote_amount_usdc=Decimal("100"),
            fee_usdc=Decimal("0.10"),
            realized_pnl_usdc=Decimal("1"),
            breakout_strength=None,
        )
        for index in range(20)
    )
    end = start + timedelta(hours=720)
    entries = tuple(
        replace(
            event,
            event_id=f"entry-{index}",
            signal_id=f"entry-signal-{index}",
            action="ENTER_LONG",
            occurred_at_utc=event.occurred_at_utc - timedelta(minutes=30),
        )
        for index, event in enumerate(events)
    )
    with PaperStore(path) as store:
        store.apply_cycle(
            account=store.load_account(),
            positions={},
            events=entries + events,
            checkpoints=dict.fromkeys(SYMBOLS, end),
            processed_bars=dict.fromkeys(SYMBOLS, 720),
        )
        progress = store.load_soak_progress(at=start + timedelta(days=30))
    assert progress.ready is True
    assert progress.status == "PASSED"
    assert progress.calendar_days == 30
    assert progress.minimum_processed_closed_bars == 720
    assert progress.completed_trades == 20
    assert progress.blockers == ()


def test_slot_priority_is_deterministic_and_cycle_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "paper.sqlite3"
    start = datetime(2026, 1, 1, 0, tzinfo=UTC)
    initialize_paper_at_latest(str(path), _mapping(start), at=start)
    signal_time = start + timedelta(hours=1)
    points = _mapping(signal_time)
    for symbol in SYMBOLS[:5]:
        points[symbol] = (_point(symbol, signal_time, flip_up=True, strength=1.0),)

    emitted = process_new_closed_points(str(path), points, _rules())
    filled = [event for event in emitted if event.status is PaperEventStatus.FILLED]
    blocked = [event for event in emitted if event.status is PaperEventStatus.BLOCKED]
    assert [event.symbol for event in filled] == list(SYMBOLS[:3])
    assert [event.symbol for event in blocked] == list(SYMBOLS[3:5])
    assert all(event.reason == "NO_FREE_SLOT" for event in blocked)

    assert process_new_closed_points(str(path), points, _rules()) == ()
    with PaperStore(path) as store:
        positions = store.load_positions()
        assert [position.symbol for position in positions] == sorted(SYMBOLS[:3])
        assert store.load_account().cash_usdc >= Decimal("0")
        assert len(store.load_events()) == 5


def test_exit_frees_slot_before_same_bar_entry(tmp_path: Path) -> None:
    path = tmp_path / "paper.sqlite3"
    start = datetime(2026, 1, 1, 0, tzinfo=UTC)
    initialize_paper_at_latest(str(path), _mapping(start), at=start)
    first = start + timedelta(hours=1)
    entries = _mapping(first)
    for symbol in SYMBOLS[:3]:
        entries[symbol] = (_point(symbol, first, flip_up=True, strength=1.0),)
    process_new_closed_points(str(path), entries, _rules())

    second = first + timedelta(hours=1)
    cycle = _mapping(second)
    cycle[SYMBOLS[0]] = (_point(SYMBOLS[0], second, flip_down=True),)
    cycle[SYMBOLS[3]] = (_point(SYMBOLS[3], second, flip_up=True, strength=2.0),)
    emitted = process_new_closed_points(str(path), cycle, _rules())
    assert [(event.symbol, event.action) for event in emitted] == [
        (SYMBOLS[0], "EXIT_LONG"),
        (SYMBOLS[3], "ENTER_LONG"),
    ]
    with PaperStore(path) as store:
        assert {position.symbol for position in store.load_positions()} == {
            SYMBOLS[1],
            SYMBOLS[2],
            SYMBOLS[3],
        }


def test_larger_planned_budget_never_creates_account_cash(tmp_path: Path) -> None:
    path = tmp_path / "paper.sqlite3"
    start = datetime(2026, 1, 1, 0, tzinfo=UTC)
    initialize_paper_at_latest(str(path), _mapping(start), at=start)
    with PaperStore(path) as store:
        before = store.load_account().cash_usdc
        store.save_settings(PaperSettings(slot_count=10, target_notional_usdc=Decimal("100")))
        assert store.load_account().cash_usdc == before
    signal_time = start + timedelta(hours=1)
    points = {symbol: (_point(symbol, signal_time, flip_up=True, strength=1.0),)
              for symbol in SYMBOLS}
    process_new_closed_points(str(path), points, _rules())
    with PaperStore(path) as store:
        assert store.load_account().cash_usdc >= 0
        assert sum(p.cost_basis_usdc for p in store.load_positions()) <= before
        assert len(store.load_positions()) < 10


def test_four_slots_of_45_really_open_four_positions_and_keep_the_budget(tmp_path: Path) -> None:
    path = tmp_path / "paper.sqlite3"
    start = datetime(2026, 1, 1, 0, tzinfo=UTC)
    initialize_paper_at_latest(str(path), _mapping(start), at=start)
    with PaperStore(path) as store:
        store.save_settings(PaperSettings(slot_count=4, target_notional_usdc=Decimal("45")))
    signal_time = start + timedelta(hours=1)
    points = _mapping(signal_time)
    for symbol in SYMBOLS[:5]:
        points[symbol] = (_point(symbol, signal_time, flip_up=True, strength=1.0),)
    emitted = process_new_closed_points(str(path), points, _rules())
    filled = [event for event in emitted if event.status is PaperEventStatus.FILLED]
    assert [event.symbol for event in filled] == list(SYMBOLS[:4])
    assert all(event.quote_amount_usdc <= Decimal("45") for event in filled)
    assert any(event.reason == "NO_FREE_SLOT" for event in emitted)
    with PaperStore(path) as store:
        assert len(store.load_positions()) == 4
        assert store.load_account().cash_usdc > Decimal("59")


def test_explicit_strategy_activation_closes_old_position_and_resets_soak(
    tmp_path: Path,
) -> None:
    path = tmp_path / "paper.sqlite3"
    start = datetime(2026, 1, 1, 0, tzinfo=UTC)
    initialize_paper_at_latest(str(path), _mapping(start), at=start)
    entry_at = start + timedelta(hours=1)
    entry_points = _mapping(entry_at)
    entry_points[SYMBOLS[0]] = (_point(SYMBOLS[0], entry_at, flip_up=True, strength=2.0),)
    process_new_closed_points(str(path), entry_points, _rules())

    switch_at = entry_at + timedelta(minutes=30)
    exit_points = _mapping(entry_at)
    exits = activate_paper_strategy(
        str(path),
        exit_points,
        _rules(),
        V2_RESEARCH_STRATEGY,
        at=switch_at,
    )

    assert len(exits) == 1
    assert exits[0].action == "EXIT_LONG"
    assert exits[0].reason == ("STRATEGY_SWITCH_TO_HIXTON-V2-RESEARCH-CANDIDATE-1")
    assert exits[0].strategy_version == HIXTON_SPEC_VERSION
    with PaperStore(path) as store:
        assert store.load_positions() == ()
        session = store.load_strategy_session()
        progress = store.load_soak_progress(at=switch_at)
        all_events = store.load_events()
    assert session.strategy_key == "v2"
    assert session.strategy_version == V2_RESEARCH_STRATEGY.version
    assert session.starting_equity_usdc > Decimal("0")
    assert progress.minimum_processed_closed_bars == 0
    assert progress.completed_trades == 0
    assert len(all_events) == 2
    assert (
        activate_paper_strategy(
            str(path),
            exit_points,
            _rules(),
            V2_RESEARCH_STRATEGY,
            at=switch_at + timedelta(minutes=1),
        )
        == ()
    )


def test_rejected_multi_slot_strategy_cannot_activate_paper(tmp_path: Path) -> None:
    path = tmp_path / "paper.sqlite3"
    start = datetime(2026, 1, 1, 0, tzinfo=UTC)
    initialize_paper_at_latest(str(path), _mapping(start), at=start)
    with pytest.raises(ValueError, match="not approved for paper"):
        activate_paper_strategy(
            str(path),
            _mapping(start),
            _rules(),
            V3_SLOT_STRATEGY,
            at=start + timedelta(minutes=1),
        )


def test_paper_fails_closed_when_configuration_and_ledger_strategy_differ(
    tmp_path: Path,
) -> None:
    path = tmp_path / "paper.sqlite3"
    start = datetime(2026, 1, 1, 0, tzinfo=UTC)
    initialize_paper_at_latest(str(path), _mapping(start), at=start)
    with pytest.raises(RuntimeError, match="explicit activation required"):
        initialize_paper_at_latest(
            str(path),
            _mapping(start),
            at=start,
            strategy_key="v2",
            strategy_version=V2_RESEARCH_STRATEGY.version,
        )
