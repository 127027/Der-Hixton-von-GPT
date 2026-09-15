"""SQLite persistence for paper settings, account, checkpoints and audit events."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import TracebackType
from uuid import uuid4

from hixton.constants import HIXTON_SPEC_VERSION, SYMBOLS
from hixton.paper.models import (
    PaperAccount,
    PaperEvent,
    PaperEventStatus,
    PaperPosition,
    PaperSettings,
    PaperSoakProgress,
    PaperStrategySession,
)

_SOAK_MINIMUM_DAYS = 30
_SOAK_MINIMUM_BARS_PER_SYMBOL = 720
_SOAK_MINIMUM_COMPLETED_TRADES = 20
_SOAK_MAXIMUM_DAYS_WHEN_TRADE_COUNT_LOW = 90


def _now() -> datetime:
    return datetime.now(UTC)


def _time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _parse_time(value: object) -> datetime:
    return datetime.fromisoformat(str(value)).astimezone(UTC)


class PaperStore:
    """Short-lived SQLite connection; instantiate per worker or API request."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path, timeout=30)
        self._connection.row_factory = sqlite3.Row
        # Fail before any schema migration when pointed at the old USDT ledger.
        # A new quote requires a separate account, never relabelling old cash.
        tables = {
            row[0]
            for row in self._connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if (
            "paper_account" in tables
            and self._connection.execute("SELECT 1 FROM paper_account LIMIT 1").fetchone()
        ):
            markers: set[str] = set()
            for table in ("paper_checkpoints", "paper_positions", "paper_events"):
                if table in tables:
                    markers.update(
                        str(row[0])
                        for row in self._connection.execute(f"SELECT DISTINCT symbol FROM {table}")
                    )
            if any(symbol.endswith("USDT") for symbol in markers):
                self._connection.close()
                raise RuntimeError("Legacy USDT Paper ledger: use a separate USDC database")
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._migrate()

    def __enter__(self) -> PaperStore:
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

    def initialize(
        self,
        *,
        at: datetime | None = None,
        strategy_key: str = "v1",
        strategy_version: str = HIXTON_SPEC_VERSION,
        starting_cash_usdc: Decimal | None = None,
    ) -> bool:
        moment = (at or _now()).astimezone(UTC)
        # Only INSERT a new seed; never top up or reset an existing ledger.
        seed = starting_cash_usdc
        if seed is None:
            seed = Decimal("250.00" if strategy_key == "v6" else "240.00")
        if not seed.is_finite() or seed <= 0:
            raise ValueError("initial paper cash must be finite and positive")
        initial_cash = str(seed)
        with self._connection:
            cursor = self._connection.execute(
                """
                INSERT OR IGNORE INTO paper_account (
                    singleton, cash_text, starting_cash_text, high_water_text,
                    day_start_equity_text, day_start_date_utc, halted,
                    halt_reason, created_at_utc, updated_at_utc
                ) VALUES (1, ?, ?, ?, ?, ?, 0, NULL, ?, ?)
                """,
                (
                    initial_cash,
                    initial_cash,
                    initial_cash,
                    initial_cash,
                    moment.date().isoformat(),
                    _time(moment),
                    _time(moment),
                ),
            )
            self._connection.execute(
                """
                INSERT OR IGNORE INTO paper_settings (
                    singleton, slot_count, target_notional_text, emergency_stop, updated_at_utc
                ) VALUES (1, 3, '80.00', 0, ?)
                """,
                (_time(moment),),
            )
            session = self._connection.execute(
                "SELECT singleton FROM paper_strategy_state WHERE singleton=1"
            ).fetchone()
            if session is None:
                legacy_rows = sum(
                    int(self._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                    for table in ("paper_events", "paper_positions", "paper_checkpoints")
                )
                initial_key = "v1" if legacy_rows else strategy_key
                initial_version = HIXTON_SPEC_VERSION if legacy_rows else strategy_version
                account_row = self._connection.execute(
                    "SELECT created_at_utc, starting_cash_text FROM paper_account WHERE singleton=1"
                ).fetchone()
                if account_row is None:
                    raise RuntimeError("paper account disappeared during initialization")
                activated_at = str(account_row["created_at_utc"]) if legacy_rows else _time(moment)
                starting_equity = str(account_row["starting_cash_text"])
                self._connection.execute(
                    """
                    INSERT INTO paper_strategy_state (
                        singleton, strategy_key, strategy_version,
                        activated_at_utc, starting_equity_text
                    ) VALUES (1, ?, ?, ?, ?)
                    """,
                    (initial_key, initial_version, activated_at, starting_equity),
                )
        return cursor.rowcount == 1

    def load_strategy_session(self) -> PaperStrategySession:
        row = self._connection.execute(
            "SELECT * FROM paper_strategy_state WHERE singleton=1"
        ).fetchone()
        if row is None:
            raise RuntimeError("paper strategy session is not initialized")
        return PaperStrategySession(
            strategy_key=str(row["strategy_key"]),
            strategy_version=str(row["strategy_version"]),
            activated_at_utc=_parse_time(row["activated_at_utc"]),
            starting_equity_usdc=Decimal(str(row["starting_equity_text"])),
        )

    def require_strategy(self, strategy_key: str, strategy_version: str) -> None:
        session = self.load_strategy_session()
        if session.strategy_key != strategy_key or session.strategy_version != strategy_version:
            raise RuntimeError(
                "paper strategy mismatch: ledger uses "
                f"{session.strategy_key}/{session.strategy_version}, configuration uses "
                f"{strategy_key}/{strategy_version}; explicit activation required"
            )

    def load_account(self) -> PaperAccount:
        row = self._connection.execute("SELECT * FROM paper_account WHERE singleton=1").fetchone()
        if row is None:
            raise RuntimeError("paper account is not initialized")
        return PaperAccount(
            cash_usdc=Decimal(str(row["cash_text"])),
            starting_cash_usdc=Decimal(str(row["starting_cash_text"])),
            high_water_equity_usdc=Decimal(str(row["high_water_text"])),
            day_start_equity_usdc=Decimal(str(row["day_start_equity_text"])),
            day_start_date_utc=str(row["day_start_date_utc"]),
            halted=bool(row["halted"]),
            halt_reason=str(row["halt_reason"]) if row["halt_reason"] is not None else None,
            created_at_utc=_parse_time(row["created_at_utc"]),
            updated_at_utc=_parse_time(row["updated_at_utc"]),
        )

    def save_account(self, account: PaperAccount) -> None:
        with self._connection:
            self._connection.execute(
                """
                UPDATE paper_account SET
                    cash_text=?, starting_cash_text=?, high_water_text=?,
                    day_start_equity_text=?, day_start_date_utc=?, halted=?,
                    halt_reason=?, updated_at_utc=?
                WHERE singleton=1
                """,
                (
                    str(account.cash_usdc),
                    str(account.starting_cash_usdc),
                    str(account.high_water_equity_usdc),
                    str(account.day_start_equity_usdc),
                    account.day_start_date_utc,
                    int(account.halted),
                    account.halt_reason,
                    _time(account.updated_at_utc),
                ),
            )

    def load_settings(self) -> PaperSettings:
        row = self._connection.execute("SELECT * FROM paper_settings WHERE singleton=1").fetchone()
        if row is None:
            raise RuntimeError("paper settings are not initialized")
        return PaperSettings(
            slot_count=int(row["slot_count"]),
            target_notional_usdc=Decimal(str(row["target_notional_text"])),
            emergency_stop=bool(row["emergency_stop"]),
        )

    def save_settings(self, settings: PaperSettings, *, at: datetime | None = None) -> None:
        moment = (at or _now()).astimezone(UTC)
        previous = self.load_settings()
        with self._connection:
            self._connection.execute(
                """
                UPDATE paper_settings SET slot_count=?, target_notional_text=?,
                    emergency_stop=?, updated_at_utc=?
                WHERE singleton=1
                """,
                (
                    settings.slot_count,
                    str(settings.target_notional_usdc),
                    int(settings.emergency_stop),
                    _time(moment),
                ),
            )
            self._connection.execute(
                """
                INSERT INTO paper_audit(
                    audit_id, occurred_at_utc, actor, action, details_json
                ) VALUES (?, ?, 'LOCAL_UI', 'PAPER_SETTINGS_CHANGED', ?)
                """,
                (
                    str(uuid4()),
                    _time(moment),
                    json.dumps(
                        {
                            "before": {
                                "slot_count": previous.slot_count,
                                "target_notional_usdc": str(previous.target_notional_usdc),
                                "emergency_stop": previous.emergency_stop,
                            },
                            "after": {
                                "slot_count": settings.slot_count,
                                "target_notional_usdc": str(settings.target_notional_usdc),
                                "emergency_stop": settings.emergency_stop,
                            },
                            "scope": "future_entries_only",
                        },
                        separators=(",", ":"),
                    ),
                ),
            )

    def load_positions(self) -> tuple[PaperPosition, ...]:
        rows = self._connection.execute("SELECT * FROM paper_positions ORDER BY symbol").fetchall()
        return tuple(
            PaperPosition(
                symbol=str(row["symbol"]),
                quantity=Decimal(str(row["quantity_text"])),
                average_price=Decimal(str(row["average_price_text"])),
                cost_basis_usdc=Decimal(str(row["cost_basis_text"])),
                entry_time_utc=_parse_time(row["entry_time_utc"]),
                entry_signal_id=str(row["entry_signal_id"]),
                entry_fee_usdc=Decimal(str(row["entry_fee_text"])),
                updated_at_utc=_parse_time(row["updated_at_utc"]),
                strategy_version=str(row["strategy_version"]),
                slot_count=int(row["slot_count"]),
                entry_atr=Decimal(str(row["entry_atr_text"])),
                highest_close=Decimal(str(row["highest_close_text"])),
            )
            for row in rows
        )

    def upsert_position(self, position: PaperPosition) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO paper_positions (
                    symbol, quantity_text, average_price_text, cost_basis_text,
                    entry_time_utc, entry_signal_id, entry_fee_text, updated_at_utc,
                    strategy_version, slot_count, entry_atr_text, highest_close_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    quantity_text=excluded.quantity_text,
                    average_price_text=excluded.average_price_text,
                    cost_basis_text=excluded.cost_basis_text,
                    entry_time_utc=excluded.entry_time_utc,
                    entry_signal_id=excluded.entry_signal_id,
                    entry_fee_text=excluded.entry_fee_text,
                    updated_at_utc=excluded.updated_at_utc,
                    strategy_version=excluded.strategy_version,
                    slot_count=excluded.slot_count,
                    entry_atr_text=excluded.entry_atr_text,
                    highest_close_text=excluded.highest_close_text
                """,
                (
                    position.symbol,
                    str(position.quantity),
                    str(position.average_price),
                    str(position.cost_basis_usdc),
                    _time(position.entry_time_utc),
                    position.entry_signal_id,
                    str(position.entry_fee_usdc),
                    _time(position.updated_at_utc),
                    position.strategy_version,
                    position.slot_count,
                    str(position.entry_atr),
                    str(position.highest_close),
                ),
            )

    def delete_position(self, symbol: str) -> None:
        with self._connection:
            self._connection.execute(
                "DELETE FROM paper_positions WHERE symbol=?",
                (symbol.replace("/", "").upper(),),
            )

    def append_event(self, event: PaperEvent) -> bool:
        with self._connection:
            cursor = self._connection.execute(
                """
                INSERT OR IGNORE INTO paper_events (
                    event_id, signal_id, occurred_at_utc, symbol, action, status,
                    reason, reference_price_text, execution_price_text,
                    base_quantity_text, quote_amount_text, fee_text,
                    realized_pnl_text, breakout_strength_text, strategy_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.signal_id,
                    _time(event.occurred_at_utc),
                    event.symbol,
                    event.action,
                    event.status.value,
                    event.reason,
                    str(event.reference_price),
                    str(event.execution_price) if event.execution_price is not None else None,
                    str(event.base_quantity) if event.base_quantity is not None else None,
                    str(event.quote_amount_usdc) if event.quote_amount_usdc is not None else None,
                    str(event.fee_usdc) if event.fee_usdc is not None else None,
                    (str(event.realized_pnl_usdc) if event.realized_pnl_usdc is not None else None),
                    (str(event.breakout_strength) if event.breakout_strength is not None else None),
                    event.strategy_version,
                ),
            )
        return cursor.rowcount == 1

    def apply_cycle(
        self,
        *,
        account: PaperAccount,
        positions: Mapping[str, PaperPosition],
        events: tuple[PaperEvent, ...],
        checkpoints: Mapping[str, datetime],
        processed_bars: Mapping[str, int],
        dust: Mapping[str, Decimal] | None = None,
    ) -> None:
        """Atomically persist one deterministic bar-close processing cycle."""

        unknown = set(processed_bars) - set(SYMBOLS)
        if unknown or any(value < 0 for value in processed_bars.values()):
            raise ValueError("processed paper bars must be non-negative DMS symbol counts")

        with self._connection:
            if dust is not None:
                self._connection.executemany(
                    "INSERT INTO paper_dust(symbol, quantity_text) VALUES (?, ?) "
                    "ON CONFLICT(symbol) DO UPDATE SET quantity_text=excluded.quantity_text",
                    [(symbol, str(qty)) for symbol, qty in dust.items()],
                )
            self._connection.executemany(
                "INSERT OR IGNORE INTO paper_execution_audit "
                "(event_id, processed_at_utc, execution_model) VALUES (?, ?, ?)",
                [(event.event_id, _time(_now()), "NEXT_BAR_OPEN_V1") for event in events],
            )
            self._connection.execute(
                """
                UPDATE paper_account SET
                    cash_text=?, starting_cash_text=?, high_water_text=?,
                    day_start_equity_text=?, day_start_date_utc=?, halted=?,
                    halt_reason=?, updated_at_utc=?
                WHERE singleton=1
                """,
                (
                    str(account.cash_usdc),
                    str(account.starting_cash_usdc),
                    str(account.high_water_equity_usdc),
                    str(account.day_start_equity_usdc),
                    account.day_start_date_utc,
                    int(account.halted),
                    account.halt_reason,
                    _time(account.updated_at_utc),
                ),
            )
            self._connection.execute("DELETE FROM paper_positions")
            self._connection.executemany(
                """
                INSERT INTO paper_positions (
                    symbol, quantity_text, average_price_text, cost_basis_text,
                    entry_time_utc, entry_signal_id, entry_fee_text, updated_at_utc,
                    strategy_version, slot_count, entry_atr_text, highest_close_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        position.symbol,
                        str(position.quantity),
                        str(position.average_price),
                        str(position.cost_basis_usdc),
                        _time(position.entry_time_utc),
                        position.entry_signal_id,
                        str(position.entry_fee_usdc),
                        _time(position.updated_at_utc),
                        position.strategy_version,
                        position.slot_count,
                        str(position.entry_atr),
                        str(position.highest_close),
                    )
                    for position in positions.values()
                ],
            )
            self._connection.executemany(
                """
                INSERT OR IGNORE INTO paper_events (
                    event_id, signal_id, occurred_at_utc, symbol, action, status,
                    reason, reference_price_text, execution_price_text,
                    base_quantity_text, quote_amount_text, fee_text,
                    realized_pnl_text, breakout_strength_text, strategy_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        event.event_id,
                        event.signal_id,
                        _time(event.occurred_at_utc),
                        event.symbol,
                        event.action,
                        event.status.value,
                        event.reason,
                        str(event.reference_price),
                        (str(event.execution_price) if event.execution_price is not None else None),
                        str(event.base_quantity) if event.base_quantity is not None else None,
                        (
                            str(event.quote_amount_usdc)
                            if event.quote_amount_usdc is not None
                            else None
                        ),
                        str(event.fee_usdc) if event.fee_usdc is not None else None,
                        (
                            str(event.realized_pnl_usdc)
                            if event.realized_pnl_usdc is not None
                            else None
                        ),
                        (
                            str(event.breakout_strength)
                            if event.breakout_strength is not None
                            else None
                        ),
                        event.strategy_version,
                    )
                    for event in events
                ],
            )
            self._connection.executemany(
                """
                INSERT INTO paper_checkpoints(symbol, last_close_utc) VALUES (?, ?)
                ON CONFLICT(symbol) DO UPDATE SET last_close_utc=excluded.last_close_utc
                """,
                [(symbol, _time(value)) for symbol, value in checkpoints.items()],
            )
            for symbol, count in processed_bars.items():
                cursor = self._connection.execute(
                    """
                    UPDATE paper_soak_symbols
                    SET processed_closed_bars=processed_closed_bars+?
                    WHERE symbol=?
                    """,
                    (count, symbol),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError(f"paper soak counter missing for {symbol}")
            self._connection.execute(
                "UPDATE paper_soak SET updated_at_utc=? WHERE singleton=1",
                (_time(account.updated_at_utc),),
            )

    def load_events(
        self,
        *,
        symbol: str | None = None,
        limit: int = 500,
    ) -> tuple[PaperEvent, ...]:
        if limit <= 0 or limit > 5_000:
            raise ValueError("paper event limit must be between 1 and 5000")
        parameters: list[object] = []
        clause = ""
        if symbol is not None:
            clause = "WHERE symbol=?"
            parameters.append(symbol.replace("/", "").upper())
        parameters.append(limit)
        rows = self._connection.execute(
            "SELECT paper_events.*, paper_execution_audit.processed_at_utc, "
            "paper_execution_audit.execution_model FROM paper_events "
            "LEFT JOIN paper_execution_audit USING(event_id) "
            f"{clause} ORDER BY occurred_at_utc DESC LIMIT ?",
            parameters,
        ).fetchall()
        return tuple(self._row_to_event(row) for row in rows)

    def load_dust(self) -> dict[str, Decimal]:
        return {
            str(row["symbol"]): Decimal(row["quantity_text"])
            for row in self._connection.execute("SELECT * FROM paper_dust")
        }

    def checkpoint(self, symbol: str) -> datetime | None:
        row = self._connection.execute(
            "SELECT last_close_utc FROM paper_checkpoints WHERE symbol=?",
            (symbol.replace("/", "").upper(),),
        ).fetchone()
        return _parse_time(row["last_close_utc"]) if row is not None else None

    def save_checkpoints(self, values: Mapping[str, datetime]) -> None:
        with self._connection:
            self._connection.executemany(
                """
                INSERT INTO paper_checkpoints(symbol, last_close_utc) VALUES (?, ?)
                ON CONFLICT(symbol) DO UPDATE SET last_close_utc=excluded.last_close_utc
                """,
                [
                    (symbol.replace("/", "").upper(), _time(value))
                    for symbol, value in values.items()
                ],
            )

    def apply_strategy_activation(
        self,
        *,
        account: PaperAccount,
        events: tuple[PaperEvent, ...],
        checkpoints: Mapping[str, datetime],
        strategy_key: str,
        strategy_version: str,
        starting_equity_usdc: Decimal,
        at: datetime,
        dust: Mapping[str, Decimal] | None = None,
    ) -> None:
        """Close the old paper session and atomically start a clean strategy soak."""

        if set(checkpoints) != set(SYMBOLS):
            raise ValueError("strategy activation requires all ten checkpoints")
        previous = self.load_strategy_session()
        if previous.strategy_key == strategy_key and previous.strategy_version == strategy_version:
            return
        with self._connection:
            self._connection.execute(
                """
                UPDATE paper_account SET cash_text=?, starting_cash_text=?,
                    high_water_text=?, day_start_equity_text=?, day_start_date_utc=?,
                    halted=?, halt_reason=?, updated_at_utc=? WHERE singleton=1
                """,
                (
                    str(account.cash_usdc),
                    str(account.starting_cash_usdc),
                    str(account.high_water_equity_usdc),
                    str(account.day_start_equity_usdc),
                    account.day_start_date_utc,
                    int(account.halted),
                    account.halt_reason,
                    _time(account.updated_at_utc),
                ),
            )
            self._connection.execute("DELETE FROM paper_positions")
            if dust is not None:
                self._connection.execute("DELETE FROM paper_dust")
                self._connection.executemany(
                    "INSERT INTO paper_dust(symbol, quantity_text) VALUES (?, ?)",
                    [(s, str(q)) for s, q in dust.items() if q > 0],
                )
            self._connection.executemany(
                """
                INSERT INTO paper_events (
                    event_id, signal_id, occurred_at_utc, symbol, action, status,
                    reason, reference_price_text, execution_price_text,
                    base_quantity_text, quote_amount_text, fee_text,
                    realized_pnl_text, breakout_strength_text, strategy_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        event.event_id,
                        event.signal_id,
                        _time(event.occurred_at_utc),
                        event.symbol,
                        event.action,
                        event.status.value,
                        event.reason,
                        str(event.reference_price),
                        str(event.execution_price),
                        str(event.base_quantity),
                        str(event.quote_amount_usdc),
                        str(event.fee_usdc),
                        str(event.realized_pnl_usdc),
                        None,
                        event.strategy_version,
                    )
                    for event in events
                ],
            )
            self._connection.executemany(
                """
                INSERT INTO paper_checkpoints(symbol, last_close_utc) VALUES (?, ?)
                ON CONFLICT(symbol) DO UPDATE SET last_close_utc=excluded.last_close_utc
                """,
                [(symbol, _time(value)) for symbol, value in checkpoints.items()],
            )
            self._connection.execute("DELETE FROM paper_soak_symbols")
            self._connection.execute("DELETE FROM paper_soak")
            self._connection.execute(
                """
                INSERT INTO paper_soak(singleton, started_at_utc, updated_at_utc)
                VALUES (1, ?, ?)
                """,
                (_time(at), _time(at)),
            )
            self._connection.executemany(
                """
                INSERT INTO paper_soak_symbols(
                    symbol, baseline_close_utc, processed_closed_bars
                ) VALUES (?, ?, 0)
                """,
                [(symbol, _time(checkpoints[symbol])) for symbol in SYMBOLS],
            )
            self._connection.execute(
                """
                UPDATE paper_strategy_state SET strategy_key=?, strategy_version=?,
                    activated_at_utc=?, starting_equity_text=? WHERE singleton=1
                """,
                (
                    strategy_key,
                    strategy_version,
                    _time(at),
                    str(starting_equity_usdc),
                ),
            )
            self._connection.execute(
                """
                INSERT INTO paper_audit(
                    audit_id, occurred_at_utc, actor, action, details_json
                ) VALUES (?, ?, 'OWNER_DECISION', 'PAPER_STRATEGY_ACTIVATED', ?)
                """,
                (
                    str(uuid4()),
                    _time(at),
                    json.dumps(
                        {
                            "before": {
                                "key": previous.strategy_key,
                                "version": previous.strategy_version,
                            },
                            "after": {
                                "key": strategy_key,
                                "version": strategy_version,
                            },
                            "starting_equity_usdc": str(starting_equity_usdc),
                            "forced_paper_exits": len(events),
                            "decision": "DEC-043" if strategy_key == "v6" else "DEC-037",
                        },
                        separators=(",", ":"),
                    ),
                ),
            )

    def all_checkpoints(self) -> dict[str, datetime]:
        rows = self._connection.execute(
            "SELECT symbol, last_close_utc FROM paper_checkpoints"
        ).fetchall()
        return {str(row["symbol"]): _parse_time(row["last_close_utc"]) for row in rows}

    def ensure_soak_started(
        self,
        checkpoints: Mapping[str, datetime],
        *,
        at: datetime | None = None,
    ) -> None:
        if set(checkpoints) != set(SYMBOLS):
            raise ValueError("paper soak baseline requires all ten DMS symbols")
        moment = (at or _now()).astimezone(UTC)
        with self._connection:
            self._connection.execute(
                """
                INSERT OR IGNORE INTO paper_soak (
                    singleton, started_at_utc, updated_at_utc
                ) VALUES (1, ?, ?)
                """,
                (_time(moment), _time(moment)),
            )
            self._connection.executemany(
                """
                INSERT OR IGNORE INTO paper_soak_symbols (
                    symbol, baseline_close_utc, processed_closed_bars
                ) VALUES (?, ?, 0)
                """,
                [(symbol, _time(checkpoints[symbol])) for symbol in SYMBOLS],
            )

    def ensure_execution_epoch(
        self, checkpoints: Mapping[str, datetime], *, at: datetime | None = None
    ) -> bool:
        """Restart the technical soak once, preserving ledger, cash and positions."""
        if set(checkpoints) != set(SYMBOLS):
            raise ValueError("execution epoch requires all ten checkpoints")
        action = "EXECUTION_NEXT_BAR_OPEN_V1_ACTIVATED"
        if self._connection.execute(
            "SELECT 1 FROM paper_audit WHERE action=?", (action,)
        ).fetchone():
            return False
        moment = (at or _now()).astimezone(UTC)
        previous = self.load_soak_progress(at=moment)
        with self._connection:
            self._connection.execute(
                "INSERT INTO paper_audit VALUES (?, ?, 'TECHNICAL_UPGRADE', ?, ?)",
                (
                    str(uuid4()),
                    _time(moment),
                    action,
                    json.dumps(
                        {
                            "previous_soak_start": _time(previous.started_at_utc),
                            "previous_bars": dict(previous.processed_closed_bars_by_symbol),
                            "previous_completed_trades": previous.completed_trades,
                            "preserved_positions": [p.symbol for p in self.load_positions()],
                            "decision": "DEC-040",
                        }
                    ),
                ),
            )
            self._connection.execute(
                "UPDATE paper_soak SET started_at_utc=?, updated_at_utc=? WHERE singleton=1",
                (_time(moment), _time(moment)),
            )
            self._connection.executemany(
                "UPDATE paper_soak_symbols SET baseline_close_utc=?, processed_closed_bars=0 "
                "WHERE symbol=?",
                [(_time(value), symbol) for symbol, value in checkpoints.items()],
            )
        return True

    def load_soak_progress(self, *, at: datetime | None = None) -> PaperSoakProgress:
        moment = (at or _now()).astimezone(UTC)
        state = self._connection.execute(
            "SELECT started_at_utc FROM paper_soak WHERE singleton=1"
        ).fetchone()
        if state is None:
            raise RuntimeError("paper soak is not initialized")
        started_at = _parse_time(state["started_at_utc"])
        rows = self._connection.execute(
            """
            SELECT symbol, processed_closed_bars
            FROM paper_soak_symbols
            ORDER BY symbol
            """
        ).fetchall()
        bars = {str(row["symbol"]): int(row["processed_closed_bars"]) for row in rows}
        if set(bars) != set(SYMBOLS):
            raise RuntimeError("paper soak counters are incomplete")
        session = self.load_strategy_session()
        completed_row = self._connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM paper_events AS exits
            WHERE action='EXIT_LONG' AND status='FILLED' AND occurred_at_utc>=?
                AND strategy_version=?
                AND EXISTS (
                    SELECT 1 FROM paper_events AS entries
                    WHERE entries.symbol=exits.symbol AND entries.action='ENTER_LONG'
                        AND entries.status='FILLED' AND entries.occurred_at_utc>=?
                        AND entries.occurred_at_utc<exits.occurred_at_utc
                )
            """,
            (_time(started_at), session.strategy_version, _time(started_at)),
        ).fetchone()
        completed_trades = int(completed_row["count"] if completed_row is not None else 0)
        calendar_days = max(0, (moment.date() - started_at.date()).days)
        minimum_bars = min(bars.values())
        blockers: list[str] = []
        if calendar_days < _SOAK_MINIMUM_DAYS:
            blockers.append(f"DAYS_{calendar_days}_OF_{_SOAK_MINIMUM_DAYS}")
        if minimum_bars < _SOAK_MINIMUM_BARS_PER_SYMBOL:
            blockers.append(f"BARS_{minimum_bars}_OF_{_SOAK_MINIMUM_BARS_PER_SYMBOL}_PER_SYMBOL")
        if completed_trades < _SOAK_MINIMUM_COMPLETED_TRADES:
            blockers.append(f"TRADES_{completed_trades}_OF_{_SOAK_MINIMUM_COMPLETED_TRADES}")
        ready = not blockers
        if ready:
            status = "PASSED"
        elif (
            calendar_days >= _SOAK_MAXIMUM_DAYS_WHEN_TRADE_COUNT_LOW
            and completed_trades < _SOAK_MINIMUM_COMPLETED_TRADES
        ):
            status = "REVIEW_REQUIRED"
        else:
            status = "RUNNING"
        return PaperSoakProgress(
            started_at_utc=started_at,
            calendar_days=calendar_days,
            processed_closed_bars_by_symbol=bars,
            minimum_processed_closed_bars=minimum_bars,
            completed_trades=completed_trades,
            minimum_days=_SOAK_MINIMUM_DAYS,
            minimum_closed_bars_per_symbol=_SOAK_MINIMUM_BARS_PER_SYMBOL,
            minimum_completed_trades=_SOAK_MINIMUM_COMPLETED_TRADES,
            maximum_days_when_trade_count_low=_SOAK_MAXIMUM_DAYS_WHEN_TRADE_COUNT_LOW,
            status=status,
            ready=ready,
            blockers=tuple(blockers),
        )

    def _migrate(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS paper_account (
                    singleton INTEGER PRIMARY KEY CHECK (singleton=1),
                    cash_text TEXT NOT NULL,
                    starting_cash_text TEXT NOT NULL,
                    high_water_text TEXT NOT NULL,
                    day_start_equity_text TEXT NOT NULL,
                    day_start_date_utc TEXT NOT NULL,
                    halted INTEGER NOT NULL CHECK (halted IN (0, 1)),
                    halt_reason TEXT,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS paper_settings (
                    singleton INTEGER PRIMARY KEY CHECK (singleton=1),
                    slot_count INTEGER NOT NULL CHECK (slot_count > 0),
                    target_notional_text TEXT NOT NULL,
                    emergency_stop INTEGER NOT NULL CHECK (emergency_stop IN (0, 1)),
                    updated_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS paper_positions (
                    symbol TEXT PRIMARY KEY,
                    quantity_text TEXT NOT NULL,
                    average_price_text TEXT NOT NULL,
                    cost_basis_text TEXT NOT NULL,
                    entry_time_utc TEXT NOT NULL,
                    entry_signal_id TEXT NOT NULL,
                    entry_fee_text TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    strategy_version TEXT NOT NULL DEFAULT 'HIXTON-SPEC-1.0',
                    slot_count INTEGER NOT NULL DEFAULT 1 CHECK (slot_count > 0)
                );
                CREATE TABLE IF NOT EXISTS paper_events (
                    event_id TEXT PRIMARY KEY,
                    signal_id TEXT NOT NULL UNIQUE,
                    occurred_at_utc TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT,
                    reference_price_text TEXT NOT NULL,
                    execution_price_text TEXT,
                    base_quantity_text TEXT,
                    quote_amount_text TEXT,
                    fee_text TEXT,
                    realized_pnl_text TEXT,
                    breakout_strength_text TEXT,
                    strategy_version TEXT NOT NULL DEFAULT 'HIXTON-SPEC-1.0'
                );
                CREATE INDEX IF NOT EXISTS idx_paper_events_symbol_time
                ON paper_events(symbol, occurred_at_utc);
                CREATE INDEX IF NOT EXISTS idx_paper_events_time
                ON paper_events(occurred_at_utc);
                CREATE TABLE IF NOT EXISTS paper_checkpoints (
                    symbol TEXT PRIMARY KEY,
                    last_close_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS paper_soak (
                    singleton INTEGER PRIMARY KEY CHECK (singleton=1),
                    started_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS paper_soak_symbols (
                    symbol TEXT PRIMARY KEY,
                    baseline_close_utc TEXT NOT NULL,
                    processed_closed_bars INTEGER NOT NULL
                        CHECK (processed_closed_bars >= 0)
                );
                CREATE TABLE IF NOT EXISTS paper_audit (
                    audit_id TEXT PRIMARY KEY,
                    occurred_at_utc TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_paper_audit_time
                ON paper_audit(occurred_at_utc);
                CREATE TABLE IF NOT EXISTS paper_strategy_state (
                    singleton INTEGER PRIMARY KEY CHECK (singleton=1),
                    strategy_key TEXT NOT NULL,
                    strategy_version TEXT NOT NULL,
                    activated_at_utc TEXT NOT NULL,
                    starting_equity_text TEXT NOT NULL
                );
                """
            )
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS paper_dust "
                "(symbol TEXT PRIMARY KEY, quantity_text TEXT NOT NULL)"
            )
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS paper_execution_audit "
                "(event_id TEXT PRIMARY KEY, processed_at_utc TEXT NOT NULL, "
                "execution_model TEXT NOT NULL)"
            )
            event_columns = {
                str(row["name"])
                for row in self._connection.execute("PRAGMA table_info(paper_events)").fetchall()
            }
            if "realized_pnl_text" not in event_columns:
                self._connection.execute(
                    "ALTER TABLE paper_events ADD COLUMN realized_pnl_text TEXT"
                )
            if "strategy_version" not in event_columns:
                self._connection.execute(
                    "ALTER TABLE paper_events ADD COLUMN strategy_version TEXT "
                    f"NOT NULL DEFAULT '{HIXTON_SPEC_VERSION}'"
                )
            position_columns = {
                str(row["name"])
                for row in self._connection.execute("PRAGMA table_info(paper_positions)").fetchall()
            }
            if "strategy_version" not in position_columns:
                self._connection.execute(
                    "ALTER TABLE paper_positions ADD COLUMN strategy_version TEXT "
                    f"NOT NULL DEFAULT '{HIXTON_SPEC_VERSION}'"
                )
            if "slot_count" not in position_columns:
                self._connection.execute(
                    "ALTER TABLE paper_positions ADD COLUMN slot_count INTEGER NOT NULL DEFAULT 1"
                )
            for column in ("entry_atr_text", "highest_close_text"):
                if column not in position_columns:
                    self._connection.execute(
                        f"ALTER TABLE paper_positions ADD COLUMN {column} TEXT NOT NULL DEFAULT '0'"
                    )
            self._connection.execute("PRAGMA optimize")

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> PaperEvent:
        def decimal_or_none(name: str) -> Decimal | None:
            value = row[name]
            return Decimal(str(value)) if value is not None else None

        return PaperEvent(
            event_id=str(row["event_id"]),
            signal_id=str(row["signal_id"]),
            occurred_at_utc=_parse_time(row["occurred_at_utc"]),
            symbol=str(row["symbol"]),
            action=str(row["action"]),
            status=PaperEventStatus(str(row["status"])),
            reason=str(row["reason"]) if row["reason"] is not None else None,
            reference_price=Decimal(str(row["reference_price_text"])),
            execution_price=decimal_or_none("execution_price_text"),
            base_quantity=decimal_or_none("base_quantity_text"),
            quote_amount_usdc=decimal_or_none("quote_amount_text"),
            fee_usdc=decimal_or_none("fee_text"),
            realized_pnl_usdc=decimal_or_none("realized_pnl_text"),
            breakout_strength=decimal_or_none("breakout_strength_text"),
            strategy_version=str(row["strategy_version"]),
            processed_at_utc=(
                _parse_time(row["processed_at_utc"])
                if "processed_at_utc" in set(row.keys()) and row["processed_at_utc"]
                else None
            ),
            execution_model=(
                str(row["execution_model"])
                if "execution_model" in set(row.keys()) and row["execution_model"]
                else "LEGACY_CLOSE_OR_MIGRATION"
            ),
        )

    def missing_checkpoint_symbols(self) -> tuple[str, ...]:
        present = set(self.all_checkpoints())
        return tuple(symbol for symbol in SYMBOLS if symbol not in present)
