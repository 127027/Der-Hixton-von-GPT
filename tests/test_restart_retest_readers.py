"""Real writer overlap must not block inactive lifecycle/status readers."""

import sqlite3
from decimal import Decimal

import pytest

from hixton.data.storage import CandleStore
from hixton.paper.storage import PaperStore
from hixton.runtime.supervisor import RuntimeSupervisor
from tests.test_live_preparation import client_for


def test_status_and_private_lifecycle_read_committed_state_under_writer(tmp_path):
    client, config, service = client_for(tmp_path)
    supervisor = RuntimeSupervisor(config)
    supervisor.trial_runtime = service.runtime
    supervisor.live_runtime = service.live_runtime
    path = config.database_path
    with sqlite3.connect(path, timeout=0.1) as writer:
        writer.execute("BEGIN IMMEDIATE")
        writer.execute("UPDATE paper_settings SET max_capital_text='9000' WHERE singleton=1")
        # Make an accidental read-write constructor fail promptly, rather than
        # letting a regression spend the production busy timeout inside the test.
        original = sqlite3.connect

        def short_timeout(*args, **kwargs):
            kwargs["timeout"] = 0.1
            return original(*args, **kwargs)

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(sqlite3, "connect", short_timeout)
            status = client.get("/api/status").json()
            assert Decimal(status["trading_settings"]["max_capital_usdc"]) == Decimal(250)
            assert Decimal(status["paper"]["settings"]["max_capital_usdc"]) == Decimal(250)
            live = client.get("/api/live/status").json()
            assert Decimal(live["trading_settings"]["max_capital_usdc"]) == Decimal(250)
            assert client.get("/api/paper/events").status_code == 200
            supervisor._trial_cycle()
            assert supervisor.trial_runtime.last_error is None
        writer.rollback()
    with PaperStore(path, read_only=True) as store:
        assert store.load_settings().max_capital_usdc == Decimal(250)


@pytest.mark.parametrize("store_class", [CandleStore, PaperStore])
def test_failed_migration_closes_owned_connection(tmp_path, monkeypatch, store_class):
    observed = []

    def fail(self):
        observed.append(self._connection)
        raise sqlite3.OperationalError("simulated migration failure")

    monkeypatch.setattr(store_class, "_migrate", fail)
    with pytest.raises(sqlite3.OperationalError, match="simulated migration failure"):
        store_class(tmp_path / "store.sqlite3")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        observed[0].execute("SELECT 1")
