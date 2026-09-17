from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast

from hixton.backtest.continuity import (
    HISTORY_MODE,
    continuity_manifest_data,
    load_continuity_history,
)
from hixton.backtest.models import ExecutionRules
from hixton.data.binance import BinancePublicClient
from hixton.domain.models import Candle
from hixton.domain.versions import V6_COIN_STRATEGY

BAR = timedelta(hours=1)


class FakePublicClient:
    def __init__(self) -> None:
        self.requests: list[str] = []

    def fetch_klines(
        self,
        symbol: str,
        *,
        start: datetime,
        end_exclusive: datetime,
    ) -> list[Candle]:
        self.requests.append(symbol)
        candles: list[Candle] = []
        current = start
        while current < end_exclusive:
            candles.append(
                Candle(
                    symbol=symbol,
                    open_time_utc=current,
                    close_time_utc=current + BAR,
                    open=100.0,
                    high=101.0,
                    low=99.0,
                    close=100.5,
                    volume=10.0,
                )
            )
            current += BAR
        return candles


def _rules() -> dict[str, ExecutionRules]:
    rule = ExecutionRules(
        tick_size=Decimal("0.01"),
        step_size=Decimal("0.0001"),
        min_qty=Decimal("0.0001"),
        min_notional=Decimal("5"),
    )
    return {profile.symbol: rule for profile in V6_COIN_STRATEGY.coin_profiles}


def test_continuity_adapter_keeps_usdc_identity_and_uses_usdt_market_path() -> None:
    client = FakePublicClient()
    start = datetime(2026, 9, 14, tzinfo=UTC)
    end = datetime(2026, 9, 17, tzinfo=UTC)

    history = load_continuity_history(
        strategy=V6_COIN_STRATEGY,
        report_start_utc=start,
        report_end_utc=end,
        execution_rules=_rules(),
        client=cast(BinancePublicClient, client),
    )

    assert len(client.requests) == 10
    assert all(symbol.endswith("USDT") for symbol in client.requests)
    assert set(history.candles_by_symbol) == {
        profile.symbol for profile in V6_COIN_STRATEGY.coin_profiles
    }
    for symbol, candles in history.candles_by_symbol.items():
        assert candles[0].symbol == symbol
        assert candles[-1].symbol == symbol
        assert all(
            candle.source == "binance_spot_usdt_market_proxy_for_usdc_backtest"
            for candle in candles
        )
        assert history.provenance_by_symbol[symbol]["market_proxy"].endswith("USDT")
        assert history.provenance_by_symbol[symbol]["execution_rules_from"] == symbol

    manifest_data = continuity_manifest_data(history)
    assert manifest_data["history_mode"] == HISTORY_MODE
    assert manifest_data["runtime_quote"] == "USDC"
    assert manifest_data["market_proxy_quote"] == "USDT"
    assert manifest_data["historical_usdc_liquidity_claimed"] is False
    assert manifest_data["paper_state_modified"] is False
    assert manifest_data["orders_sent"] is False


def test_continuity_adapter_rejects_incomplete_usdc_rule_map() -> None:
    rules = _rules()
    rules.pop("DOGEUSDC")

    try:
        load_continuity_history(
            strategy=V6_COIN_STRATEGY,
            report_start_utc=datetime(2026, 9, 14, tzinfo=UTC),
            report_end_utc=datetime(2026, 9, 17, tzinfo=UTC),
            execution_rules=rules,
            client=cast(BinancePublicClient, FakePublicClient()),
        )
    except ValueError as error:
        assert "execution rules" in str(error)
    else:
        raise AssertionError("incomplete active USDC rule map must fail closed")
