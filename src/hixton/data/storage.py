"""SQLite candle store with immutable revision history and stable snapshot hashes."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import TracebackType

from hixton.constants import EXCHANGE, TIMEFRAME
from hixton.domain.models import Candle

_SCHEMA_VERSION = 1


def _to_epoch_ms(value: datetime) -> int:
    return int(value.timestamp() * 1_000)


def _from_epoch_ms(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1_000, tz=UTC)


def _number(value: float) -> str:
    return repr(value)


def _utc_now_text() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class StoreResult:
    inserted: int = 0
    unchanged: int = 0
    revised: int = 0


@dataclass(frozen=True, slots=True)
class StoredSymbolRules:
    symbol: str
    status: str
    quote_asset: str
    spot_allowed: bool
    order_types: tuple[str, ...]
    tick_size: Decimal
    step_size: Decimal
    min_qty: Decimal
    min_notional: Decimal
    checked_at_utc: datetime


class CandleStore:
    """Owned SQLite connection; use as a context manager."""

    def __init__(self, path: Path | str, *, read_only: bool = False) -> None:
        self.path = Path(path)
        if read_only:
            self._connection = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA query_only=ON")
            return  # No mkdir, migrations, journal-mode changes or account writes.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._migrate()

    def __enter__(self) -> CandleStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is None:
            self._connection.commit()
        else:
            self._connection.rollback()
        self.close()

    def close(self) -> None:
        self._connection.close()

    def integrity_check(self) -> bool:
        row = self._connection.execute("PRAGMA integrity_check").fetchone()
        return row is not None and row[0] == "ok"

    def put_candles(
        self,
        candles: Iterable[Candle],
        *,
        exchange: str = EXCHANGE,
        timeframe: str = TIMEFRAME,
        revision_reason: str = "provider_sync",
    ) -> StoreResult:
        inserted = 0
        unchanged = 0
        revised = 0
        with self._connection:
            for candle in candles:
                key = (exchange, candle.symbol, timeframe, _to_epoch_ms(candle.open_time_utc))
                row = self._connection.execute(
                    """
                    SELECT * FROM candles
                    WHERE exchange=? AND symbol=? AND timeframe=? AND open_time_ms=?
                    """,
                    key,
                ).fetchone()
                values = self._candle_values(candle)
                if row is None:
                    self._connection.execute(
                        """
                        INSERT INTO candles (
                            exchange, symbol, timeframe, open_time_ms, close_time_ms,
                            open_text, high_text, low_text, close_text, volume_text,
                            quote_volume_text, trade_count, closed, source, revision, updated_at_utc
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                        """,
                        (*key, *values, _utc_now_text()),
                    )
                    inserted += 1
                    continue
                if self._row_values(row) == values:
                    unchanged += 1
                    continue
                # Live provisional updates are mutable by definition. Archiving every
                # stream tick would create an unbounded, meaningless revision trail.
                if bool(row["closed"]):
                    self._archive_revision(row, revision_reason)
                self._connection.execute(
                    """
                    UPDATE candles SET
                        close_time_ms=?, open_text=?, high_text=?, low_text=?, close_text=?,
                        volume_text=?, quote_volume_text=?, trade_count=?, closed=?, source=?,
                        revision=revision+1, updated_at_utc=?
                    WHERE exchange=? AND symbol=? AND timeframe=? AND open_time_ms=?
                    """,
                    (*values, _utc_now_text(), *key),
                )
                revised += 1
        return StoreResult(inserted=inserted, unchanged=unchanged, revised=revised)

    def load_candles(
        self,
        symbol: str,
        *,
        start: datetime | None = None,
        end_exclusive: datetime | None = None,
        exchange: str = EXCHANGE,
        timeframe: str = TIMEFRAME,
        closed_only: bool = True,
    ) -> list[Candle]:
        clauses = ["exchange=?", "symbol=?", "timeframe=?"]
        parameters: list[object] = [exchange, symbol.replace("/", "").upper(), timeframe]
        if start is not None:
            clauses.append("open_time_ms>=?")
            parameters.append(_to_epoch_ms(start))
        if end_exclusive is not None:
            clauses.append("open_time_ms<?")
            parameters.append(_to_epoch_ms(end_exclusive))
        if closed_only:
            clauses.append("closed=1")
        sql = f"SELECT * FROM candles WHERE {' AND '.join(clauses)} ORDER BY open_time_ms"
        rows = self._connection.execute(sql, parameters).fetchall()
        return [self._row_to_candle(row) for row in rows]

    def snapshot_sha256(
        self,
        symbol: str,
        *,
        start: datetime,
        end_exclusive: datetime,
        exchange: str = EXCHANGE,
        timeframe: str = TIMEFRAME,
    ) -> str:
        candles = self.load_candles(
            symbol,
            start=start,
            end_exclusive=end_exclusive,
            exchange=exchange,
            timeframe=timeframe,
        )
        digest = hashlib.sha256()
        for candle in candles:
            payload = (
                exchange,
                candle.symbol,
                timeframe,
                _to_epoch_ms(candle.open_time_utc),
                _to_epoch_ms(candle.close_time_utc),
                _number(candle.open),
                _number(candle.high),
                _number(candle.low),
                _number(candle.close),
                _number(candle.volume),
                _number(candle.quote_volume),
                candle.trade_count,
                candle.closed,
                candle.source,
            )
            digest.update(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
            digest.update(b"\n")
        return digest.hexdigest()

    def revision_count(self) -> int:
        row = self._connection.execute("SELECT COUNT(*) FROM candle_revisions").fetchone()
        return int(row[0]) if row is not None else 0

    def put_symbol_rules(self, rules: StoredSymbolRules) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO symbol_rules (
                    symbol, status, quote_asset, spot_allowed, order_types_json,
                    tick_size_text, step_size_text, min_qty_text, min_notional_text,
                    checked_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    status=excluded.status,
                    quote_asset=excluded.quote_asset,
                    spot_allowed=excluded.spot_allowed,
                    order_types_json=excluded.order_types_json,
                    tick_size_text=excluded.tick_size_text,
                    step_size_text=excluded.step_size_text,
                    min_qty_text=excluded.min_qty_text,
                    min_notional_text=excluded.min_notional_text,
                    checked_at_utc=excluded.checked_at_utc
                """,
                (
                    rules.symbol,
                    rules.status,
                    rules.quote_asset,
                    int(rules.spot_allowed),
                    json.dumps(rules.order_types, separators=(",", ":")),
                    str(rules.tick_size),
                    str(rules.step_size),
                    str(rules.min_qty),
                    str(rules.min_notional),
                    rules.checked_at_utc.astimezone(UTC).isoformat(),
                ),
            )

    def load_symbol_rules(self, symbol: str) -> StoredSymbolRules | None:
        row = self._connection.execute(
            "SELECT * FROM symbol_rules WHERE symbol=?",
            (symbol.replace("/", "").upper(),),
        ).fetchone()
        if row is None:
            return None
        raw_order_types = json.loads(str(row["order_types_json"]))
        if not isinstance(raw_order_types, list):
            raise ValueError("stored order types have invalid shape")
        return StoredSymbolRules(
            symbol=str(row["symbol"]),
            status=str(row["status"]),
            quote_asset=str(row["quote_asset"]),
            spot_allowed=bool(row["spot_allowed"]),
            order_types=tuple(str(value) for value in raw_order_types),
            tick_size=Decimal(str(row["tick_size_text"])),
            step_size=Decimal(str(row["step_size_text"])),
            min_qty=Decimal(str(row["min_qty_text"])),
            min_notional=Decimal(str(row["min_notional_text"])),
            checked_at_utc=datetime.fromisoformat(str(row["checked_at_utc"])).astimezone(UTC),
        )

    def _migrate(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS candles (
                    exchange TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    open_time_ms INTEGER NOT NULL,
                    close_time_ms INTEGER NOT NULL,
                    open_text TEXT NOT NULL,
                    high_text TEXT NOT NULL,
                    low_text TEXT NOT NULL,
                    close_text TEXT NOT NULL,
                    volume_text TEXT NOT NULL,
                    quote_volume_text TEXT NOT NULL,
                    trade_count INTEGER NOT NULL,
                    closed INTEGER NOT NULL CHECK (closed IN (0, 1)),
                    source TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY (exchange, symbol, timeframe, open_time_ms)
                );
                CREATE INDEX IF NOT EXISTS ix_candles_symbol_time
                ON candles(symbol, timeframe, open_time_ms);
                CREATE TABLE IF NOT EXISTS candle_revisions (
                    revision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exchange TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    open_time_ms INTEGER NOT NULL,
                    close_time_ms INTEGER NOT NULL,
                    open_text TEXT NOT NULL,
                    high_text TEXT NOT NULL,
                    low_text TEXT NOT NULL,
                    close_text TEXT NOT NULL,
                    volume_text TEXT NOT NULL,
                    quote_volume_text TEXT NOT NULL,
                    trade_count INTEGER NOT NULL,
                    closed INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    replaced_at_utc TEXT NOT NULL,
                    reason TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS symbol_rules (
                    symbol TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    quote_asset TEXT NOT NULL,
                    spot_allowed INTEGER NOT NULL CHECK (spot_allowed IN (0, 1)),
                    order_types_json TEXT NOT NULL,
                    tick_size_text TEXT NOT NULL,
                    step_size_text TEXT NOT NULL,
                    min_qty_text TEXT NOT NULL,
                    min_notional_text TEXT NOT NULL,
                    checked_at_utc TEXT NOT NULL
                );
                """
            )
            self._connection.execute(
                """
                INSERT INTO schema_meta(key, value) VALUES('schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (str(_SCHEMA_VERSION),),
            )

    @staticmethod
    def _candle_values(candle: Candle) -> tuple[object, ...]:
        return (
            _to_epoch_ms(candle.close_time_utc),
            _number(candle.open),
            _number(candle.high),
            _number(candle.low),
            _number(candle.close),
            _number(candle.volume),
            _number(candle.quote_volume),
            candle.trade_count,
            int(candle.closed),
            candle.source,
        )

    @staticmethod
    def _row_values(row: sqlite3.Row) -> tuple[object, ...]:
        return (
            row["close_time_ms"],
            row["open_text"],
            row["high_text"],
            row["low_text"],
            row["close_text"],
            row["volume_text"],
            row["quote_volume_text"],
            row["trade_count"],
            row["closed"],
            row["source"],
        )

    def _archive_revision(self, row: sqlite3.Row, reason: str) -> None:
        self._connection.execute(
            """
            INSERT INTO candle_revisions (
                exchange, symbol, timeframe, open_time_ms, close_time_ms,
                open_text, high_text, low_text, close_text, volume_text,
                quote_volume_text, trade_count, closed, source, revision,
                replaced_at_utc, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["exchange"],
                row["symbol"],
                row["timeframe"],
                row["open_time_ms"],
                row["close_time_ms"],
                row["open_text"],
                row["high_text"],
                row["low_text"],
                row["close_text"],
                row["volume_text"],
                row["quote_volume_text"],
                row["trade_count"],
                row["closed"],
                row["source"],
                row["revision"],
                _utc_now_text(),
                reason,
            ),
        )

    @staticmethod
    def _row_to_candle(row: sqlite3.Row) -> Candle:
        return Candle(
            symbol=str(row["symbol"]),
            open_time_utc=_from_epoch_ms(int(row["open_time_ms"])),
            close_time_utc=_from_epoch_ms(int(row["close_time_ms"])),
            open=float(row["open_text"]),
            high=float(row["high_text"]),
            low=float(row["low_text"]),
            close=float(row["close_text"]),
            volume=float(row["volume_text"]),
            quote_volume=float(row["quote_volume_text"]),
            trade_count=int(row["trade_count"]),
            closed=bool(row["closed"]),
            source=str(row["source"]),
        )
