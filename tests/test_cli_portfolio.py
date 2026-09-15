from __future__ import annotations

from argparse import Namespace
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from hixton import cli
from hixton.backtest.models import ExecutionRules
from hixton.paper.models import PaperSettings
from hixton.paper.storage import PaperStore
from tests.test_ui_api import _config


@pytest.mark.parametrize("initialized", [True, False])
def test_cli_portfolio_mirrors_saved_sizes_not_installation_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    initialized: bool,
) -> None:
    config = replace(_config(tmp_path), paper_starting_cash_usdc=Decimal("250"))
    if initialized:
        with PaperStore(config.database_path) as store:
            store.initialize(starting_cash_usdc=Decimal("250"))
            store.save_settings(PaperSettings(slot_count=4, target_notional_usdc=Decimal("45")))
            before = store.load_account()
    calls = []
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cli, "_execution_rules", lambda *_: ExecutionRules())
    monkeypatch.setattr(cli, "_code_commit", lambda: "offline-test")
    monkeypatch.setattr(cli, "write_report_bundle", lambda **_: tmp_path / "report")
    # This unit isolates shared settings; real history coverage is tested separately.
    monkeypatch.setattr(cli, "available_report_start", lambda _candles, start, _end: start)

    def capture(**kwargs):
        calls.append(kwargs)
        return object()

    monkeypatch.setattr(cli, "run_shared_portfolio_backtest", capture)
    args = Namespace(end=datetime(2026, 9, 8, tzinfo=UTC), strategy=None, cost="both")
    assert cli.command_backtest_portfolio(args, config) == 0
    assert len(calls) == 2
    assert all(call["slot_count"] == (4 if initialized else 3) for call in calls)
    assert all(call["target_notional"] == Decimal("45" if initialized else "80") for call in calls)
    assert all(call["starting_cash"] == Decimal("250") for call in calls)
    if initialized:
        with PaperStore(config.database_path) as store:
            assert store.load_account() == before
