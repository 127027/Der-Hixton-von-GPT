from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from hixton.backtest.engine import run_single_backtest
from hixton.backtest.models import BacktestMetrics
from hixton.backtest.weak_coin_review import (
    WEAK_COINS,
    acceptance,
    candidates,
    run_weak_coin_review,
    select_training,
)
from hixton.cli import build_parser
from hixton.domain.versions import V6_COIN_STRATEGY
from tests.golden_reference import deterministic_candles


@pytest.fixture
def metrics() -> BacktestMetrics:
    candles = deterministic_candles("DOTUSDC", 800, 0)
    result = run_single_backtest(
        symbol="DOTUSDC",
        candles=candles,
        report_start_utc=candles[400].open_time_utc,
        report_end_utc=candles[-1].open_time_utc + timedelta(hours=1),
    )
    return replace(
        result.metrics,
        ending_equity=Decimal(300),
        net_pnl=Decimal(50),
        return_pct=Decimal(20),
        max_drawdown_pct=Decimal(20),
        completed_trades=10,
    )


def test_catalog_is_bounded_and_does_not_mutate_active_profiles() -> None:
    before = V6_COIN_STRATEGY.config_payload()
    for symbol in WEAK_COINS:
        variants = candidates(symbol)
        assert len(variants) == 6
        assert variants[0].name == "current"
        assert variants[0].parameters == V6_COIN_STRATEGY.parameters_for(symbol)
        assert all(c.parameters.warmup_bars == 400 for c in variants)
        assert variants[1].parameters.band_multiplier < variants[0].parameters.band_multiplier
    assert V6_COIN_STRATEGY.config_payload() == before
    with pytest.raises(ValueError):
        candidates("BTCUSDC")


def test_training_selection_favors_worst_window_not_largest_single_gain(
    metrics: BacktestMetrics,
) -> None:
    steady = replace(metrics, net_pnl=Decimal(60), return_pct=Decimal(24))
    boom = replace(metrics, net_pnl=Decimal(200), return_pct=Decimal(80))
    bust = replace(metrics, net_pnl=Decimal(10), return_pct=Decimal(4))
    assert (
        select_training(
            {"current": (metrics, metrics), "steady": (steady, steady), "unstable": (boom, bust)}
        )
        == "steady"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"completed_trades": 4},
        {"completed_trades": 9},
        {"max_drawdown_pct": Decimal("22.01")},
        {"net_pnl": Decimal(49)},
    ],
)
def test_ineligible_training_candidate_falls_back_to_current(
    metrics: BacktestMetrics,
    change: dict,
) -> None:
    trial = replace(metrics, **change)
    assert select_training({"current": (metrics, metrics), "trial": (trial, trial)}) == "current"


@pytest.mark.parametrize(
    "change",
    [
        {"ending_equity": Decimal(299)},
        {"net_pnl": Decimal(0)},
        {"max_drawdown_pct": Decimal("22.01")},
        {"completed_trades": 9},
    ],
)
def test_extra_return_cannot_override_acceptance_failures(
    metrics: BacktestMetrics,
    change: dict,
) -> None:
    assert not acceptance(metrics, replace(metrics, **change))


def test_missing_database_does_not_create_file_or_output(tmp_path: Path) -> None:
    import sqlite3

    database, output = tmp_path / "missing.sqlite3", tmp_path / "output"
    with pytest.raises(sqlite3.OperationalError):
        run_weak_coin_review(database, output, datetime(2026, 9, 14, 13, tzinfo=UTC))
    assert not database.exists()
    assert not output.exists()


def test_v8_uses_existing_entry_point_with_explicit_end() -> None:
    args = build_parser().parse_args(
        [
            "backtest",
            "research",
            "--study",
            "v8",
            "--end",
            "2026-09-14T13:00:00Z",
            "--output",
            "backtests/v8/runs/test",
        ]
    )
    assert args.study == "v8"
    assert args.end == datetime(2026, 9, 14, 13, tzinfo=UTC)
