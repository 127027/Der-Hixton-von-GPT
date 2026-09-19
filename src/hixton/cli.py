"""Only command surface for strategy, data and backtest operations."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from hixton import __version__
from hixton.backtest.engine import run_isolated_batch, run_single_backtest
from hixton.backtest.models import CURRENT_COSTS, BatchResult, ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.backtest.reporting import RunResult, write_report_bundle
from hixton.config import ProjectConfig, load_project_config
from hixton.constants import SYMBOLS, TIMEFRAME_DELTA
from hixton.data.binance import BinanceApiError, BinancePublicClient
from hixton.data.quality import audit_candles
from hixton.data.storage import CandleStore
from hixton.data.sync import synchronize_symbol
from hixton.domain.models import Candle
from hixton.domain.versions import StrategyDefinition, strategy_definition
from hixton.paper.engine import activate_paper_strategy
from hixton.paper.models import PaperSettings
from hixton.paper.storage import PaperStore
from hixton.runtime.analysis import available_report_start, rebuild_analysis

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "examples" / "config.example.json"


def parse_utc(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("time must contain a timezone, preferably Z or +00:00")
    parsed = parsed.astimezone(UTC)
    if parsed.minute != 0 or parsed.second != 0 or parsed.microsecond != 0:
        raise argparse.ArgumentTypeError("time must lie on a full hour")
    return parsed


def subtract_calendar_years(value: datetime, years: int) -> datetime:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, month=2, day=28)


def latest_safe_report_end(now: datetime | None = None) -> datetime:
    current = (now or datetime.now(UTC)).astimezone(UTC)
    boundary = current.replace(minute=0, second=0, microsecond=0)
    if current - boundary < timedelta(minutes=2):
        boundary -= TIMEFRAME_DELTA
    return boundary


def _window(end: datetime | None) -> tuple[datetime, datetime, datetime]:
    report_end = end or latest_safe_report_end()
    report_start = subtract_calendar_years(report_end, 3)
    warmup_start = report_start - 400 * TIMEFRAME_DELTA
    return warmup_start, report_start, report_end


def _config(path: Path) -> ProjectConfig:
    resolved = path if path.is_absolute() else PROJECT_ROOT / path
    return load_project_config(resolved, project_root=PROJECT_ROOT)


def _symbols(value: str) -> tuple[str, ...]:
    if value.upper() == "ALL":
        return SYMBOLS
    normalized = value.replace("/", "").upper()
    if normalized not in SYMBOLS:
        raise ValueError(f"unsupported symbol: {value}")
    return (normalized,)


def _execution_rules(store: CandleStore, symbol: str) -> ExecutionRules:
    stored = store.load_symbol_rules(symbol)
    if stored is None:
        raise ValueError(f"missing Binance filters for {symbol}; run data sync first")
    if stored.status != "TRADING" or not stored.spot_allowed or "MARKET" not in stored.order_types:
        raise ValueError(f"stored Binance rules do not permit V1 market trading for {symbol}")
    return ExecutionRules(
        tick_size=stored.tick_size,
        step_size=stored.step_size,
        min_qty=stored.min_qty,
        min_notional=stored.min_notional,
    )


def _code_commit() -> str:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={PROJECT_ROOT.as_posix()}", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "UNKNOWN"


def command_status(config: ProjectConfig) -> int:
    strategy = strategy_definition(config.strategy_key)
    payload = {
        "application_version": __version__,
        "strategy_key": strategy.key,
        "strategy_version": strategy.version,
        "slot_allocation": strategy.slot_allocation,
        "implemented": [
            "strategy",
            "binance_public_data",
            "sqlite_quality",
            "current_v6_backtest",
            "paper_versioned",
            "local_ui",
        ],
        "not_yet_implemented": ["live_execution"],
        "live_enabled": False,
        "database_path": str(config.database_path),
        "database_exists": config.database_path.exists(),
        "single_entrypoint": "src/main.py",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def command_data_sync(args: argparse.Namespace, config: ProjectConfig) -> int:
    warmup_start, report_start, report_end = _window(args.end)
    client = BinancePublicClient(base_url=config.binance_base_url)
    with CandleStore(config.database_path) as store:
        for symbol in _symbols(args.symbol):
            actual_start = client.first_available_open(
                symbol, start=warmup_start, end_exclusive=report_end
            )
            print(
                f"Synchronisiere {symbol}: {warmup_start.isoformat()} bis {report_end.isoformat()}"
            )
            result = synchronize_symbol(
                client=client,
                store=store,
                symbol=symbol,
                start=actual_start,
                end_exclusive=report_end,
                full_refresh=args.full_refresh,
            )
            print(
                f"{symbol}: {result.quality.candle_count} Bars, "
                f"{result.inserted} neu, {result.revised} revidiert, Qualität OK"
            )
    print(f"Primäres Berichtsfenster beginnt {report_start.isoformat()}")
    return 0


def command_data_audit(args: argparse.Namespace, config: ProjectConfig) -> int:
    warmup_start, _, report_end = _window(args.end)
    failed = False
    with CandleStore(config.database_path) as store:
        for symbol in _symbols(args.symbol):
            candles = store.load_candles(
                symbol,
                start=warmup_start,
                end_exclusive=report_end,
            )
            report = audit_candles(
                candles,
                expected_symbol=symbol,
                expected_start=warmup_start,
                expected_end_exclusive=report_end,
            )
            print(f"{symbol}: {'OK' if report.valid else 'FEHLER'} ({report.candle_count} Bars)")
            for issue in report.issues[:10]:
                print(f"  {issue.code}: {issue.message}")
            failed = failed or not report.valid
    return 1 if failed else 0


def _run_single_scenario(
    *,
    symbol: str,
    candles: list[Candle],
    report_start: datetime,
    report_end: datetime,
    rules: ExecutionRules,
    config: ProjectConfig,
    strategy: StrategyDefinition,
) -> dict[str, RunResult]:
    return {
        "current": run_single_backtest(
            symbol=symbol,
            candles=candles,
            report_start_utc=report_start,
            report_end_utc=report_end,
            starting_cash=config.starting_usdc_per_symbol,
            target_notional=config.target_notional_usdc,
            costs=CURRENT_COSTS,
            execution_rules=rules,
            strategy_parameters=strategy.parameters_for(symbol),
            trade_policy=strategy.policy_for(symbol),
            strategy_semantics=strategy.semantics,
            strategy_version=strategy.version,
        )
    }


def command_backtest_single(args: argparse.Namespace, config: ProjectConfig) -> int:
    warmup_start, report_start, report_end = _window(args.end)
    symbol = _symbols(args.symbol)[0]
    strategy = strategy_definition(args.strategy or config.strategy_key)
    with CandleStore(config.database_path) as store:
        candles = store.load_candles(symbol, start=warmup_start, end_exclusive=report_end)
        rules = _execution_rules(store, symbol)
    report_start = available_report_start({symbol: candles}, report_start, report_end)
    scenarios = _run_single_scenario(
        symbol=symbol,
        candles=candles,
        report_start=report_start,
        report_end=report_end,
        rules=rules,
        config=config,
        strategy=strategy,
    )
    output = write_report_bundle(
        scenarios=scenarios,
        output_root=PROJECT_ROOT / "backtests" / strategy.backtest_version / "runs",
        config_sha256=config.sha256,
        code_commit=_code_commit(),
        report_start_utc=report_start,
        report_end_utc=report_end,
        strategy=strategy,
    )
    print(f"Backtest gespeichert: {output}")
    return 0


def command_backtest_all(args: argparse.Namespace, config: ProjectConfig) -> int:
    warmup_start, report_start, report_end = _window(args.end)
    strategy = strategy_definition(args.strategy or config.strategy_key)
    candles_by_symbol = {}
    rules_by_symbol = {}
    with CandleStore(config.database_path) as store:
        for symbol in SYMBOLS:
            candles_by_symbol[symbol] = store.load_candles(
                symbol,
                start=warmup_start,
                end_exclusive=report_end,
            )
            rules_by_symbol[symbol] = _execution_rules(store, symbol)
    report_start = available_report_start(candles_by_symbol, report_start, report_end)
    batch: BatchResult = run_isolated_batch(
        candles_by_symbol=candles_by_symbol,
        report_start_utc=report_start,
        report_end_utc=report_end,
        costs=CURRENT_COSTS,
        execution_rules=rules_by_symbol,
        strategy_parameters=strategy.parameters,
        strategy_parameters_by_symbol=strategy.parameter_map(),
        trade_policies_by_symbol=strategy.policy_map(),
        strategy_semantics=strategy.semantics,
        strategy_version=strategy.version,
    )
    scenarios: dict[str, RunResult] = {"current": batch}
    output = write_report_bundle(
        scenarios=scenarios,
        output_root=PROJECT_ROOT / "backtests" / strategy.backtest_version / "runs",
        config_sha256=config.sha256,
        code_commit=_code_commit(),
        report_start_utc=report_start,
        report_end_utc=report_end,
        strategy=strategy,
    )
    print(f"10er-Batch gespeichert: {output}")
    return 0


def command_backtest_portfolio(args: argparse.Namespace, config: ProjectConfig) -> int:
    warmup_start, report_start, report_end = _window(args.end)
    strategy = strategy_definition(args.strategy or config.strategy_key)
    # Match the UI runner: operator-saved sizes override installation defaults.
    # Research without an initialized Paper account still uses the explicit config.
    with PaperStore(config.database_path) as store:
        try:
            paper_settings = store.load_settings()
        except RuntimeError:
            paper_settings = PaperSettings(
                slot_count=config.paper_slot_count,
                target_notional_usdc=config.paper_target_notional_usdc,
                emergency_stop=False,
            )
    candles_by_symbol = {}
    rules_by_symbol = {}
    with CandleStore(config.database_path) as store:
        for symbol in SYMBOLS:
            candles_by_symbol[symbol] = store.load_candles(
                symbol,
                start=warmup_start,
                end_exclusive=report_end,
            )
            rules_by_symbol[symbol] = _execution_rules(store, symbol)
    report_start = available_report_start(candles_by_symbol, report_start, report_end)
    scenarios: dict[str, RunResult] = {
        "current": run_shared_portfolio_backtest(
            candles_by_symbol=candles_by_symbol,
            report_start_utc=report_start,
            report_end_utc=report_end,
            starting_cash=config.paper_starting_cash_usdc,
            target_notional=paper_settings.target_notional_usdc,
            slot_count=paper_settings.slot_count,
            costs=CURRENT_COSTS,
            execution_rules=rules_by_symbol,
            strategy_parameters=strategy.parameters,
            strategy_parameters_by_symbol=strategy.parameter_map(),
            trade_policies_by_symbol=strategy.policy_map(),
            strategy_semantics=strategy.semantics,
            strategy_version=strategy.version,
            slot_allocation=strategy.slot_allocation,
        )
    }
    output = write_report_bundle(
        scenarios=scenarios,
        output_root=PROJECT_ROOT / "backtests" / strategy.backtest_version / "runs",
        config_sha256=config.sha256,
        code_commit=_code_commit(),
        report_start_utc=report_start,
        report_end_utc=report_end,
        strategy=strategy,
    )
    print(
        f"Portfolio {paper_settings.slot_count}x{paper_settings.target_notional_usdc} "
        f"gespeichert: {output}"
    )
    return 0


def command_paper_activate(args: argparse.Namespace, config: ProjectConfig) -> int:
    if args.confirmation != "AKTIVIEREN":
        raise ValueError("paper strategy activation requires --confirmation AKTIVIEREN")
    strategy = strategy_definition(args.strategy)
    if strategy.key != config.strategy_key:
        raise ValueError("activation target must equal the strategy selected in configuration")
    warmup_start, _, report_end = _window(None)
    rules_by_symbol: dict[str, ExecutionRules] = {}
    with CandleStore(config.database_path) as store:
        starts_by_symbol: dict[str, datetime] = {}
        for symbol in SYMBOLS:
            available = store.load_candles(
                symbol,
                start=warmup_start,
                end_exclusive=report_end,
            )
            if not available:
                raise ValueError(f"{symbol}: no stored candles available for Paper activation")
            starts_by_symbol[symbol] = available[0].open_time_utc
            rules_by_symbol[symbol] = _execution_rules(store, symbol)
    common_start = max(warmup_start, max(starts_by_symbol.values()))
    points, _ = rebuild_analysis(
        config.database_path,
        start=warmup_start,
        end_exclusive=report_end,
        strategy=strategy,
        starts_by_symbol=dict.fromkeys(SYMBOLS, common_start),
    )
    events = activate_paper_strategy(
        str(config.database_path),
        points,
        rules_by_symbol,
        strategy,
    )
    print(
        f"Paperstrategie aktiv: {strategy.version}; "
        f"kontrollierte Positionsschliessungen: {len(events)}"
    )
    return 0


def _not_ready(mode: str) -> int:
    print(
        f"{mode} ist sicher gesperrt: Paper und UI sind implementiert, "
        "echte Binance-Orders benoetigen jedoch das dokumentierte Live-Gate.",
        file=sys.stderr,
    )
    return 2


def command_start(args: argparse.Namespace, config: ProjectConfig) -> int:
    from hixton.ui.server import run_local_dashboard

    return run_local_dashboard(config, open_browser=not args.no_browser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hixton",
        description="Der Hixton - ein sauberer Einstieg",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="sicheren Implementierungsstatus anzeigen")
    start = commands.add_parser("start", help="Paper-Bot und lokale UI gemeinsam starten")
    start.add_argument("--no-browser", action="store_true")

    data = commands.add_parser("data", help="lokale Binance-Marktdaten verwalten")
    data_commands = data.add_subparsers(dest="data_command", required=True)
    sync = data_commands.add_parser("sync", help="3 Jahre plus Warm-up inkrementell laden")
    sync.add_argument("--symbol", default="ALL", help="ALL oder ein DMS-Symbol")
    sync.add_argument("--end", type=parse_utc)
    sync.add_argument("--full-refresh", action="store_true")
    audit = data_commands.add_parser("audit", help="lokale Daten vollständig prüfen")
    audit.add_argument("--symbol", default="ALL", help="ALL oder ein DMS-Symbol")
    audit.add_argument("--end", type=parse_utc)

    backtest = commands.add_parser("backtest", help="aktuelle V6 aus lokalen Daten testen")
    backtest_commands = backtest.add_subparsers(dest="backtest_command", required=True)
    single = backtest_commands.add_parser("single", help="einen Coin mit 250 USDC testen")
    single.add_argument("--symbol", required=True)
    single.add_argument("--end", type=parse_utc)
    single.add_argument("--strategy", choices=("v6",))
    all_ten = backtest_commands.add_parser("all", help="10x250-USDC-Batch testen")
    all_ten.add_argument("--end", type=parse_utc)
    all_ten.add_argument("--strategy", choices=("v6",))
    portfolio = backtest_commands.add_parser(
        "portfolio", help="gemeinsames Konto mit 3x80-USDC-Slots und Startcash laut Config testen"
    )
    portfolio.add_argument("--end", type=parse_utc)
    portfolio.add_argument("--strategy", choices=("v6",))
    paper = commands.add_parser("paper", help="24/7-Paper-Bot mit lokaler UI starten")
    paper.add_argument("--no-browser", action="store_true")
    activate = commands.add_parser(
        "paper-activate",
        help="versionierten Paper-Strategiewechsel kontrolliert ausfuehren",
    )
    activate.add_argument("--strategy", choices=("v6",), required=True)
    activate.add_argument("--confirmation", required=True)
    fresh = commands.add_parser(
        "paper-fresh-start",
        help="offline: altes Paperkonto archivieren und neu mit 250 starten",
    )
    fresh.add_argument("--archive", type=Path, required=True)
    fresh.add_argument("--confirmation", required=True)
    commands.add_parser("live", help="sicher gesperrter späterer Live-Modus")
    ui = commands.add_parser("ui", help="lokale UI mit Paper-Laufzeit starten")
    ui.add_argument("--no-browser", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = _config(args.config)
        if args.command == "status":
            return command_status(config)
        if args.command in {"start", "paper", "ui"}:
            return command_start(args, config)
        if args.command == "paper-activate":
            return command_paper_activate(args, config)
        if args.command == "paper-fresh-start":
            from hixton.paper.maintenance import fresh_start_paper

            archive = args.archive if args.archive.is_absolute() else PROJECT_ROOT / args.archive
            result = fresh_start_paper(
                config,
                project_root=PROJECT_ROOT,
                archive=archive,
                confirmation=args.confirmation,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "data" and args.data_command == "sync":
            return command_data_sync(args, config)
        if args.command == "data" and args.data_command == "audit":
            return command_data_audit(args, config)
        if args.command == "backtest" and args.backtest_command == "single":
            return command_backtest_single(args, config)
        if args.command == "backtest" and args.backtest_command == "all":
            return command_backtest_all(args, config)
        if args.command == "backtest" and args.backtest_command == "portfolio":
            return command_backtest_portfolio(args, config)
        if args.command == "live":
            return _not_ready(args.command.upper())
    except (BinanceApiError, OSError, ValueError, sqlite3.Error) as error:
        print(f"FEHLER: {error}", file=sys.stderr)
        return 2
    parser.error("unhandled command")
    return 2
