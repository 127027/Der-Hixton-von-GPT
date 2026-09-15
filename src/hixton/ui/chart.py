"""Chart range semantics and display-only OHLC aggregation."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from hixton.backtest.models import BASELINE_COSTS
from hixton.domain.models import Candle, IndicatorPoint, Signal, SignalAction
from hixton.domain.strategy import HixtonStrategy
from hixton.domain.trade_policy import TradePolicy, TradePolicyGate
from hixton.paper.models import PaperEvent

RANGE_LABELS = {
    "today": "Heute",
    "1w": "1 Woche",
    "1m": "1 Monat",
    "1y": "1 Jahr",
    "3y": "3 Jahre",
}
RESOLUTION_BY_RANGE = {
    "today": "1h",
    "1w": "1h",
    "1m": "1h",
    "1y": "4h",
    "3y": "1d",
}


def range_start(value: str, *, now: datetime, timezone_name: str) -> datetime:
    if value not in RANGE_LABELS:
        raise ValueError(f"unsupported chart range: {value}")
    current = now.astimezone(UTC)
    if value == "today":
        timezone = ZoneInfo(timezone_name)
        local = current.astimezone(timezone)
        return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
    if value == "1w":
        return current - timedelta(days=7)
    if value == "1m":
        return current - timedelta(days=30)
    if value == "1y":
        return current - timedelta(days=365)
    try:
        return current.replace(year=current.year - 3)
    except ValueError:
        return current.replace(year=current.year - 3, month=2, day=28)


def _bucket(value: datetime, resolution: str) -> datetime:
    value = value.astimezone(UTC)
    if resolution == "1h":
        return value.replace(minute=0, second=0, microsecond=0)
    if resolution == "4h":
        return value.replace(hour=value.hour - value.hour % 4, minute=0, second=0, microsecond=0)
    if resolution == "1d":
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    raise ValueError(f"unsupported chart resolution: {resolution}")


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _bars(points: Iterable[IndicatorPoint], resolution: str) -> list[dict[str, object]]:
    buckets: dict[datetime, list[IndicatorPoint]] = {}
    for point in points:
        buckets.setdefault(_bucket(point.candle.open_time_utc, resolution), []).append(point)
    bars: list[dict[str, object]] = []
    for bucket_time, group in sorted(buckets.items()):
        first = group[0]
        last = group[-1]
        bars.append(
            {
                "time": _iso(bucket_time),
                "close_time": _iso(last.candle.close_time_utc),
                "open": first.candle.open,
                "high": max(point.candle.high for point in group),
                "low": min(point.candle.low for point in group),
                "close": last.candle.close,
                "volume": sum(point.candle.volume for point in group),
                "vidya": last.vidya,
                "upper": last.upper,
                "lower": last.lower,
                "trend": last.trend.value,
                "provisional": False,
                "native_bar_count": len(group),
            }
        )
    return bars


def strategy_markers(
    points: Iterable[IndicatorPoint], trade_policy: TradePolicy | None = None
) -> list[dict[str, object]]:
    markers: list[dict[str, object]] = []
    is_long = False
    gate = TradePolicyGate(trade_policy)
    pending: Signal | None = None
    entry_price: float | None = None
    entry_atr, highest_close = 0.0, 0.0
    for point in points:
        reason = None
        if trade_policy is None:
            signal = HixtonStrategy.signal_for(point, is_long=is_long)
        else:
            if pending is not None:
                if pending.action is SignalAction.ENTER_LONG:
                    entry_price = point.candle.open * (1 + float(BASELINE_COSTS.adverse_price_rate))
                    entry_atr, highest_close = pending.atr, entry_price
                else:
                    entry_price = None
                pending = None
            if entry_price is not None:
                highest_close = max(highest_close, point.candle.close)
            decision = gate.decide(
                point, entry_price=entry_price, entry_atr=entry_atr, highest_close=highest_close
            )
            signal = decision.signal if not decision.block_reason else None
            reason = decision.exit_reason
            pending = signal
        if signal is None:
            continue
        is_long = signal.action.value == "ENTER_LONG"
        markers.append(
            {
                "time": _iso(signal.candle_close_time_utc),
                "bar_time": _iso(point.candle.open_time_utc),
                "symbol": signal.symbol,
                "action": signal.action.value,
                "price": signal.close,
                "signal_id": signal.signal_id,
                "strength": signal.breakout_strength,
                "reason": reason,
            }
        )
    return markers


def build_chart_payload(
    *,
    symbol: str,
    points: tuple[IndicatorPoint, ...],
    range_key: str,
    timezone_name: str,
    now: datetime,
    paper_events: tuple[PaperEvent, ...] = (),
    live_candle: Candle | None = None,
    trade_policy: TradePolicy | None = None,
) -> dict[str, object]:
    start = range_start(range_key, now=now, timezone_name=timezone_name)
    resolution = RESOLUTION_BY_RANGE[range_key]
    selected = tuple(point for point in points if point.candle.open_time_utc >= start)
    markers = []
    for marker in strategy_markers(points, trade_policy):
        if str(marker["time"]) < _iso(start):
            continue
        marker = dict(marker)
        native_bar_time = datetime.fromisoformat(str(marker["bar_time"]))
        marker["display_time"] = _iso(_bucket(native_bar_time, resolution))
        markers.append(marker)
    fills = [
        {
            "time": _iso(event.occurred_at_utc),
            "display_time": _iso(_bucket(event.occurred_at_utc, resolution)),
            "action": event.action,
            "status": event.status.value,
            "price": float(event.execution_price or event.reference_price),
            "quantity": float(event.base_quantity) if event.base_quantity is not None else None,
            "reason": event.reason,
            "event_id": event.event_id,
        }
        for event in paper_events
        if event.occurred_at_utc >= start
    ]
    bars = _bars(selected, resolution)
    if (
        live_candle is not None
        and live_candle.open_time_utc >= start
        and (not points or live_candle.open_time_utc > points[-1].candle.open_time_utc)
    ):
        time = _iso(_bucket(live_candle.open_time_utc, resolution))
        if bars and bars[-1]["time"] == time:
            last = bars[-1]
            last.update(
                high=max(float(str(last["high"])), live_candle.high),
                low=min(float(str(last["low"])), live_candle.low),
                close=live_candle.close,
                volume=float(str(last["volume"])) + live_candle.volume,
                provisional=True,
            )
        else:
            bars.append(
                {
                    "time": time,
                    "close_time": _iso(live_candle.close_time_utc),
                    "open": live_candle.open,
                    "high": live_candle.high,
                    "low": live_candle.low,
                    "close": live_candle.close,
                    "volume": live_candle.volume,
                    "vidya": None,
                    "upper": None,
                    "lower": None,
                    "trend": "PROVISIONAL",
                    "provisional": True,
                    "native_bar_count": 1,
                }
            )
    return {
        "available": bool(bars),
        "symbol": symbol,
        "range": range_key,
        "range_label": RANGE_LABELS[range_key],
        "timezone": timezone_name,
        "trading_timeframe": "1h",
        "display_resolution": resolution,
        "start_utc": _iso(start),
        "end_utc": _iso(now),
        "bars": bars,
        "signals": markers,
        "paper_events": fills,
    }
