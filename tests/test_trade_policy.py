from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from hixton.backtest.coin_review import screen_policy, variant_version
from hixton.backtest.engine import run_single_backtest
from hixton.backtest.models import STRESS_COSTS
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.constants import SYMBOLS
from hixton.domain.models import SignalAction, StrategyParameters, StrategySemantics
from hixton.domain.strategy import evaluate_batch
from hixton.domain.trade_policy import TradePolicy, TradePolicyGate
from tests.golden_reference import deterministic_candles
from tests.test_paper_engine import _point


def test_identity_overlay_preserves_original_engine_exactly() -> None:
    candles = deterministic_candles("BTCUSDC", 1000)
    kwargs = {
        "symbol": "BTCUSDC",
        "candles": candles,
        "report_start_utc": candles[400].open_time_utc,
        "report_end_utc": candles[-1].open_time_utc + timedelta(hours=1),
    }
    assert run_single_backtest(**kwargs) == run_single_backtest(
        **kwargs, trade_policy=TradePolicy()
    )


def test_stop_requires_a_closed_price_and_never_changes_indicator() -> None:
    at = datetime(2026, 1, 1, tzinfo=UTC)
    point = _point("BTCUSDC", at)
    gate = TradePolicyGate(TradePolicy(stop_atr=4))
    wick = replace(point, candle=replace(point.candle, low=80, close=99))
    assert gate.decide(wick, entry_price=100, entry_atr=1, highest_close=103).signal is None
    closed = replace(point, candle=replace(point.candle, low=90, close=95))
    decision = gate.decide(closed, entry_price=100, entry_atr=1, highest_close=103)
    assert decision.exit_reason == "POLICY_STOP_ATR"
    assert decision.signal.action is SignalAction.EXIT_LONG
    assert point.flip_down is False


def test_filtered_buy_is_not_deferred_to_a_later_green_bar() -> None:
    at = datetime(2026, 1, 1, tzinfo=UTC)
    gate = TradePolicyGate(TradePolicy(cmo_floor=0.2))
    buy = replace(_point("BTCUSDC", at, flip_up=True), abs_cmo=0.1)
    assert gate.decide(buy).block_reason == "POLICY_CMO"
    assert gate.decide(replace(buy, flip_up=False, abs_cmo=0.9)).signal is None


def test_vidya_slope_uses_only_preceding_24_bars() -> None:
    at = datetime(2026, 1, 1, tzinfo=UTC)
    gate = TradePolicyGate(TradePolicy(slope_bars=24))
    for i in range(24):
        gate.decide(replace(_point("BTCUSDC", at + timedelta(hours=i)), vidya=100.0))
    buy = replace(_point("BTCUSDC", at + timedelta(hours=24), flip_up=True), vidya=99.0)
    assert gate.decide(buy).block_reason == "POLICY_VIDYA_SLOPE"


def test_screen_and_decimal_policy_engine_match_without_rounding() -> None:
    candles = deterministic_candles("BTCUSDC", 1600)
    parameters = replace(StrategyParameters(), band_multiplier=0.8)
    policy = TradePolicy(trail_atr=4, slope_bars=24)
    start, end = candles[400].open_time_utc, candles[-1].open_time_utc + timedelta(hours=1)
    points = evaluate_batch(
        "BTCUSDC", candles, parameters=parameters, semantics=StrategySemantics.PINE_V6
    )
    screened = screen_policy(points, start, end, policy)
    exact = run_single_backtest(
        symbol="BTCUSDC",
        candles=candles,
        report_start_utc=start,
        report_end_utc=end,
        strategy_parameters=parameters,
        strategy_semantics=StrategySemantics.PINE_V6,
        trade_policy=policy,
        strategy_version=variant_version(parameters, policy),
        costs=STRESS_COSTS,
    )
    assert exact.fills
    assert screened["trades"] == exact.metrics.completed_trades
    assert abs(Decimal(str(screened["ending_equity"])) - exact.metrics.ending_equity) < Decimal(
        "1e-8"
    )
    lookup = {c.open_time_utc: c.open for c in candles}
    assert all(float(fill.reference_open) == lookup[fill.fill_time_utc] for fill in exact.fills)


def test_overlay_cannot_masquerade_as_active_v2() -> None:
    candles = deterministic_candles("BTCUSDC", 500)
    with pytest.raises(ValueError, match="explicit HIXTON-V5"):
        run_single_backtest(
            symbol="BTCUSDC",
            candles=candles,
            report_start_utc=candles[400].open_time_utc,
            report_end_utc=candles[-1].close_time_utc,
            trade_policy=TradePolicy(stop_atr=4),
        )


@pytest.mark.parametrize(
    "policy",
    [{"cmo_floor": 2}, {"stop_atr": float("nan")}, {"trail_atr": -1}, {"slope_bars": 24.0}],
)
def test_invalid_policy_rejected(policy: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        TradePolicy(**policy)


def test_portfolio_identity_and_policy_match_isolated_execution() -> None:
    # All ten identical markets, ten independent equal budgets, risk disabled only
    # in this parity fixture: allocation cannot hide a policy-engine divergence.
    markets = {s: deterministic_candles(s, 1200) for s in SYMBOLS}
    candles = markets["BTCUSDC"]
    parameters = replace(StrategyParameters(), band_multiplier=0.8)
    kwargs = {
        "candles_by_symbol": markets,
        "report_start_utc": candles[400].open_time_utc,
        "report_end_utc": candles[-1].open_time_utc + timedelta(hours=1),
        "starting_cash": Decimal("2500"),
        "target_notional": Decimal("250"),
        "slot_count": 10,
        "apply_risk_limits": False,
        "strategy_parameters": parameters,
        "strategy_semantics": StrategySemantics.PINE_V6,
        "costs": STRESS_COSTS,
    }
    original = run_shared_portfolio_backtest(**kwargs)
    assert original == run_shared_portfolio_backtest(
        **kwargs, trade_policies_by_symbol=dict.fromkeys(SYMBOLS, TradePolicy())
    )
    policy = TradePolicy(trail_atr=4, slope_bars=24)
    version = variant_version(parameters, policy)
    combined = run_shared_portfolio_backtest(
        **kwargs,
        trade_policies_by_symbol=dict.fromkeys(SYMBOLS, policy),
        strategy_version=version,
    )
    isolated = run_single_backtest(
        symbol="BTCUSDC",
        candles=candles,
        report_start_utc=kwargs["report_start_utc"],
        report_end_utc=kwargs["report_end_utc"],
        strategy_parameters=parameters,
        strategy_semantics=StrategySemantics.PINE_V6,
        trade_policy=policy,
        strategy_version=version,
        costs=STRESS_COSTS,
    )
    assert isolated.trades
    assert tuple(t for t in combined.trades if t.symbol == "BTCUSDC") == isolated.trades


def test_future_candles_cannot_change_past_policy_fills() -> None:
    candles = deterministic_candles("BTCUSDC", 1600)
    parameters = replace(StrategyParameters(), band_multiplier=0.8)
    policy = TradePolicy(trail_atr=4, slope_bars=24)
    common = {
        "symbol": "BTCUSDC",
        "candles": candles,
        "report_start_utc": candles[400].open_time_utc,
        "strategy_parameters": parameters,
        "strategy_semantics": StrategySemantics.PINE_V6,
        "trade_policy": policy,
        "strategy_version": variant_version(parameters, policy),
    }
    boundary = candles[1000].open_time_utc
    short = run_single_backtest(**common, report_end_utc=boundary)
    full = run_single_backtest(
        **common, report_end_utc=candles[-1].open_time_utc + timedelta(hours=1)
    )
    assert short.fills
    assert short.fills == tuple(f for f in full.fills if f.fill_time_utc < boundary)
