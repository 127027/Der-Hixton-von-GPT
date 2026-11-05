"""Duration, prelisting cash, native parity, and UI/API separation regressions."""

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from hixton import cli
from hixton.backtest.continuity import load_continuity_history
from hixton.backtest.models import CURRENT_COSTS, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.data.binance import BinanceApiError, BinancePublicClient
from hixton.data.storage import CandleStore
from hixton.domain.strategy import HixtonStrategy, StrategyInputError
from hixton.domain.versions import V8_VOLATILITY_PAPER_STRATEGY
from hixton.runtime.supervisor import RuntimeSupervisor, safe_closed_window
from hixton.ui.api import _list_backtests, create_app
from tests.golden_reference import deterministic_candles
from tests.test_ui_api import _config

STRATEGY = V8_VOLATILITY_PAPER_STRATEGY
BAR = timedelta(hours=1)


@pytest.mark.parametrize("years", [3, 5])
def test_calendar_window_preserves_leap_day_and_last_closed_hour(years):
    warm, start, end = safe_closed_window(datetime(2024, 2, 29, 10, 49, tzinfo=UTC), years=years)
    assert end == datetime(2024, 2, 29, 10, tzinfo=UTC)
    assert start == datetime(2024 - years, 2, 28, 10, tzinfo=UTC)
    assert warm == start - 400 * BAR
    assert cli._window(end, years) == (warm, start, end)


@pytest.mark.parametrize("bad", [0, 4, 6, True, "5"])
def test_duration_rejects_invalid_values(bad):
    with pytest.raises(ValueError):
        safe_closed_window(years=bad)


def data(count=1100):
    return {
        s: deterministic_candles(s, count, index * 11) for index, s in enumerate(STRATEGY.symbols)
    }


def run(candles, late=False, only=None):
    # Tests always retain full ETH history to anchor this fixture's fixed window.
    first = candles["ETHUSDC"][0]
    return run_shared_portfolio_backtest(
        candles_by_symbol=candles,
        strategy=STRATEGY,
        report_start_utc=first.open_time_utc + 400 * BAR,
        report_end_utc=first.open_time_utc + 1100 * BAR,
        starting_cash=Decimal("1000"),
        target_notional=Decimal("500"),
        slot_count=2,
        costs=CURRENT_COSTS,
        reinvest_profits=True,
        allow_late_listings=late,
        allowed_entry_symbols=only,
    )


def test_listing_aware_engine_is_exact_when_all_history_exists():
    candles = data()
    assert run(candles) == run(candles, True)


def test_missing_coin_has_no_fake_history_and_keeps_full_cash_window():
    candles = data()
    candles["BTCUSDC"] = []
    result = run(candles, True, frozenset({"BTCUSDC"}))
    assert len(result.equity_curve) == 700
    assert result.metrics.ending_equity == Decimal("1000")
    assert all(p.cash == Decimal("1000") and p.position_value == 0 for p in result.equity_curve)
    assert result.fills == ()
    assert not any(s.symbol == "BTCUSDC" for s in result.signals)


def test_late_coin_never_signals_or_fills_before_real_warmup():
    candles = data()
    candles["BTCUSDC"] = candles["BTCUSDC"][500:]
    available = candles["BTCUSDC"][0].open_time_utc
    result = run(candles, True, frozenset({"BTCUSDC"}))
    assert result.report_start_utc == candles["ETHUSDC"][400].open_time_utc
    assert len(result.equity_curve) == 700
    assert all(f.fill_time_utc >= available + 400 * BAR for f in result.fills)
    assert all(
        s.candle_close_time_utc >= available + 400 * BAR - timedelta(milliseconds=1)
        for s in result.signals
        if s.symbol == "BTCUSDC"
    )
    assert all(
        p.cash == Decimal("1000") for p in result.equity_curve if p.time_utc < available + 400 * BAR
    )
    with pytest.raises(ValueError):
        run(candles, False)


@pytest.mark.parametrize("missing_index", [500, -1])
def test_listing_mode_still_rejects_internal_and_trailing_gaps(missing_index):
    candles = data()
    del candles["BTCUSDC"][missing_index]
    with pytest.raises(ValueError):
        run(candles, True)


def test_synchronized_gap_has_no_candle_or_fill_and_preserves_original_signal():
    candles = data()
    original = run(candles)
    first_fill = original.fills[0]
    gap = first_fill.fill_time_utc
    for symbol, values in candles.items():
        candles[symbol] = [c for c in values if c.open_time_utc != gap]
    result = run(candles, True)
    assert len(result.equity_curve) == 700
    assert not any(f.fill_time_utc == gap for f in result.fills)
    assert not any(
        s.candle_close_time_utc == gap + BAR - timedelta(milliseconds=1) for s in result.signals
    )
    delayed = next(f for f in result.fills if f.signal_id == first_fill.signal_id)
    assert delayed.fill_time_utc == gap + BAR
    at = next(i for i, p in enumerate(result.equity_curve) if gap <= p.time_utc < gap + BAR)
    assert result.equity_curve[at].equity == result.equity_curve[at - 1].equity
    assert any("DATA_GAP_DEFERRED" in reason for reason in result.blocked_signals)
    with pytest.raises(ValueError):
        run(candles, False)


def test_gap_option_keeps_native_default_strict_and_rejects_invalid_actual_bars():
    first, second, third = data()["BTCUSDC"][:3]
    strict = HixtonStrategy("BTCUSDC")
    strict.update(first)
    with pytest.raises(StrategyInputError):
        strict.update(third)
    replay = HixtonStrategy("BTCUSDC", allow_time_gaps=True)
    replay.update(first)
    with pytest.raises(StrategyInputError):
        replay.update(replace(third, closed=False))
    with pytest.raises(StrategyInputError):
        replay.update(replace(third, low=third.high + 1))
    replay.update(third)
    with pytest.raises(StrategyInputError):
        replay.update(second)
    with pytest.raises(StrategyInputError):
        replay.update(third)


def test_continuity_five_year_reports_missing_history_and_proxy_warmup():
    candles = data()
    first = candles["ETHUSDC"][0].open_time_utc
    start = first + 400 * BAR
    end = first + 1100 * BAR

    class Public:
        def first_available_open(self, symbol, *, start, end_exclusive):
            target = symbol.removesuffix("USDT") + "USDC"
            if target == "SUIUSDC":
                raise BinanceApiError(f"{symbol}: no first available hourly candle")
            return first + (500 * BAR if target == "BTCUSDC" else timedelta(0))

        def fetch_klines(self, symbol, *, start, end_exclusive):
            target = symbol.removesuffix("USDT") + "USDC"
            return [
                replace(c, symbol=symbol)
                for c in candles[target]
                if start <= c.open_time_utc < end_exclusive
            ]

    history = load_continuity_history(
        strategy=STRATEGY,
        report_start_utc=start,
        report_end_utc=end,
        execution_rules=dict.fromkeys(STRATEGY.symbols, ExecutionRules()),
        client=Public(),
        requested_years=5,
    )
    assert history.requested_years == 5
    assert history.candles_by_symbol["SUIUSDC"] == []
    assert history.provenance_by_symbol["SUIUSDC"]["availability_note"] == "NO_HISTORY"
    assert (
        history.provenance_by_symbol["BTCUSDC"]["tradable_from_utc"]
        == (first + 900 * BAR).isoformat()
    )
    assert history.candles_by_symbol["BTCUSDC"][0].open_time_utc == first + 500 * BAR


def test_five_year_fetches_stale_tail_without_writing_native_store(tmp_path):
    candles = data()
    first = candles["ETHUSDC"][0].open_time_utc
    native_path = tmp_path / "native.sqlite3"
    with CandleStore(native_path) as store:
        for values in candles.values():
            store.put_candles(values[:-20])

    class Public:
        def fetch_klines(self, symbol, *, start, end_exclusive):
            assert symbol.endswith("USDC")
            return [c for c in candles[symbol] if start <= c.open_time_utc < end_exclusive]

    history = load_continuity_history(
        strategy=STRATEGY,
        report_start_utc=first + 400 * BAR,
        report_end_utc=first + 1100 * BAR,
        execution_rules=dict.fromkeys(STRATEGY.symbols, ExecutionRules()),
        native_database_path=native_path,
        cache_path=tmp_path / "history.sqlite3",
        client=Public(),
        requested_years=5,
    )
    assert history.candles_by_symbol == candles
    with CandleStore(native_path, read_only=True) as store:
        assert len(store.load_candles("BTCUSDC")) == 1080


@pytest.mark.parametrize("payload", [{"code": -1000}, [[], []], None])
def test_invalid_provider_response_is_not_mislabelled_as_missing_history(monkeypatch, payload):
    client = BinancePublicClient()
    monkeypatch.setattr(client, "_request_json", lambda *args: payload)
    first = datetime(2021, 11, 5, tzinfo=UTC)
    with pytest.raises(BinanceApiError, match="invalid first available"):
        client.first_available_open("BTCUSDT", start=first, end_exclusive=first + BAR)


def test_three_and_five_year_reports_are_not_mixed(tmp_path):
    for name, years in [("legacy", None), ("three", 3), ("five", 5)]:
        folder = tmp_path / name
        folder.mkdir()
        metadata = {
            "created_at_utc": "2026-11-05T00:00:00+00:00",
            "run_mode": "portfolio",
            "data": {} if years is None else {"requested_years": years},
        }
        (folder / "manifest.json").write_text(json.dumps(metadata))
        (folder / "metrics.json").write_text(json.dumps({"current": {"portfolio": {}}}))
    assert len(_list_backtests(tmp_path, years=3)) == 2
    assert len(_list_backtests(tmp_path, years=5)) == 1


def test_api_transports_duration_and_rejects_bad_input(tmp_path, monkeypatch):
    config = replace(_config(tmp_path), strategy_key="v8r", paper_slot_count=2)
    supervisor = RuntimeSupervisor(config)
    received = []
    monkeypatch.setattr(supervisor, "start_backtest", lambda **kw: received.append(kw) or True)
    client = TestClient(create_app(config, supervisor), base_url="http://127.0.0.1:8765")
    response = client.post(
        "/api/backtests/run",
        headers={"X-Hixton-Action": "local-ui-v1"},
        json={"mode": "portfolio", "strategy": "v8r", "years": 5},
    )
    assert response.status_code == 200
    assert received[-1]["years"] == 5
    for bad in (True, "5", 4, None):
        response = client.post(
            "/api/backtests/run",
            headers={"X-Hixton-Action": "local-ui-v1"},
            json={"mode": "portfolio", "years": bad},
        )
        assert response.status_code == 400


def test_runtime_pins_request_time_before_async_worker(tmp_path, monkeypatch):
    config = replace(_config(tmp_path), strategy_key="v8r", paper_slot_count=2)
    supervisor = RuntimeSupervisor(config)
    seen = []

    async def capture(**kwargs):
        seen.append(kwargs)

    monkeypatch.setattr(supervisor, "_backtest_task", capture)

    async def invoke():
        assert supervisor.start_backtest(mode="portfolio", years=5)
        await supervisor._backtest_task_handle

    asyncio.run(invoke())
    assert seen[0]["years"] == 5
    assert seen[0]["requested_at_utc"].tzinfo is not None
