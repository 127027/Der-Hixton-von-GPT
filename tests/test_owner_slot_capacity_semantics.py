from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from hixton.backtest.metrics import calculate_metrics
from hixton.backtest.models import EquityPoint, Trade
from hixton.constants import HIXTON_SPEC_VERSION, SYMBOLS
from hixton.domain.allocation import RANKED_REPEAT
from hixton.domain.models import Candle, IndicatorPoint, TrendState
from hixton.domain.versions import V6_COIN_STRATEGY
from hixton.paper.engine import initialize_paper_at_latest, process_new_closed_points
from hixton.paper.storage import PaperStore
from hixton.backtest.models import ExecutionRules


def _point(
    symbol: str,
    close_time: datetime,
    *,
    flip_up: bool = False,
    strength: float | None = None,
) -> IndicatorPoint:
    candle = Candle(
        symbol=symbol,
        open_time_utc=close_time - timedelta(hours=1),
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
        flip_down=False,
        breakout_strength=strength,
        rank_strength=strength,
        tradable=True,
    )


def _mapping(at: datetime) -> dict[str, tuple[IndicatorPoint, ...]]:
    return {symbol: (_point(symbol, at),) for symbol in SYMBOLS}


def _rules() -> dict[str, ExecutionRules]:
    rule = ExecutionRules(
        step_size=Decimal("0.000001"),
        min_qty=Decimal("0.000001"),
        min_notional=Decimal("5"),
    )
    return dict.fromkeys(SYMBOLS, rule)


def _execution(points: dict[str, tuple[IndicatorPoint, ...]]) -> dict[str, list[Candle]]:
    result: dict[str, list[Candle]] = {}
    for symbol, values in points.items():
        point = values[-1]
        result[symbol] = [
            Candle(
                symbol=symbol,
                open_time_utc=point.candle.open_time_utc + timedelta(hours=1),
                close_time_utc=point.candle.close_time_utc + timedelta(hours=1),
                open=101.0,
                high=103.0,
                low=99.0,
                close=102.0,
                volume=10.0,
                closed=False,
            )
        ]
    return result


def _run_entries(
    tmp_path: Path,
    strengths: dict[str, float],
) -> tuple[object, ...]:
    path = tmp_path / "paper.sqlite3"
    start = datetime(2026, 1, 1, 0, tzinfo=UTC)
    initialize_paper_at_latest(
        str(path),
        _mapping(start),
        at=start,
        starting_cash_usdc=Decimal("250"),
    )
    signal_time = start + timedelta(hours=1)
    points = _mapping(signal_time)
    for symbol, strength in strengths.items():
        points[symbol] = (_point(symbol, signal_time, flip_up=True, strength=strength),)
    process_new_closed_points(
        str(path),
        points,
        _rules(),
        execution_candles_by_symbol=_execution(points),
        slot_allocation=RANKED_REPEAT,
    )
    with PaperStore(path) as store:
        return store.load_positions()


def test_active_v6_uses_ranked_repeat_slot_capacity() -> None:
    assert V6_COIN_STRATEGY.slot_allocation == RANKED_REPEAT


def test_one_candidate_gets_all_three_free_80_usdc_slots(tmp_path: Path) -> None:
    positions = _run_entries(tmp_path, {SYMBOLS[0]: 2.0})
    assert len(positions) == 1
    assert positions[0].symbol == SYMBOLS[0]
    assert positions[0].slot_count == 3
    assert Decimal("239") < positions[0].cost_basis_usdc <= Decimal("240")


def test_two_candidates_use_two_plus_one_slots(tmp_path: Path) -> None:
    positions = _run_entries(tmp_path, {SYMBOLS[0]: 2.0, SYMBOLS[1]: 1.0})
    by_symbol = {position.symbol: position for position in positions}
    assert by_symbol[SYMBOLS[0]].slot_count == 2
    assert by_symbol[SYMBOLS[1]].slot_count == 1
    assert sum(position.slot_count for position in positions) == 3


def test_three_candidates_use_one_slot_each(tmp_path: Path) -> None:
    positions = _run_entries(
        tmp_path,
        {SYMBOLS[0]: 3.0, SYMBOLS[1]: 2.0, SYMBOLS[2]: 1.0},
    )
    assert len(positions) == 3
    assert all(position.slot_count == 1 for position in positions)


def test_metrics_separate_position_cycles_from_slot_round_trips() -> None:
    start = datetime(2026, 1, 1, 0, tzinfo=UTC)
    end = start + timedelta(hours=2)
    trade = Trade(
        symbol="BTCUSDC",
        entry_signal_id="entry",
        exit_signal_id="exit",
        entry_time_utc=start,
        exit_time_utc=end,
        entry_quote_spend=Decimal("240"),
        exit_quote_receive=Decimal("264"),
        realized_pnl=Decimal("24"),
        realized_return_pct=Decimal("10"),
        entry_price=Decimal("100"),
        exit_price=Decimal("110"),
        sold_base_quantity=Decimal("2.4"),
        residual_dust_quantity=Decimal("0"),
        holding_hours=Decimal("2"),
        slot_count=3,
    )
    curve = (
        EquityPoint(start, Decimal("10"), Decimal("240"), Decimal("250"), True),
        EquityPoint(end, Decimal("274"), Decimal("0"), Decimal("274"), False),
    )
    metrics = calculate_metrics(
        starting_equity=Decimal("250"),
        ending_equity=Decimal("274"),
        report_start_utc=start,
        report_end_utc=end,
        trades=(trade,),
        fills=(),
        equity_curve=curve,
        buy_and_hold_ending_equity=Decimal("250"),
    )
    assert metrics.completed_trades == 1
    assert metrics.completed_slot_trades == 3
