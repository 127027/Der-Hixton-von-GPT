from dataclasses import replace
from datetime import UTC, datetime, timedelta

from hixton.paper.storage import PaperStore
from hixton.runtime.supervisor import RuntimeSupervisor
from hixton.ui.api import _activity_payload
from tests.test_ui_api import _config


def test_checkpoints_without_fresh_feed_never_claim_liveness(tmp_path):
    config = _config(tmp_path)
    supervisor = RuntimeSupervisor(config)
    now = datetime.now(UTC)
    supervisor.state.set_status(health="HEALTHY", last_sync_utc=now - timedelta(minutes=5))
    with PaperStore(config.database_path) as store:
        store.initialize(strategy_key="v6", strategy_version=supervisor.strategy.version)
        store.save_checkpoints(
            dict.fromkeys(supervisor.strategy.symbols, now - timedelta(minutes=30))
        )
    result = _activity_payload(supervisor, config, {"positions": []})
    assert result["last_checked_closed_bar_utc"] is not None
    assert result["alive"] is False
    assert result["feed_fresh"] is False


def test_partial_processing_never_reports_all_markets_checked(tmp_path):
    from tests.test_satellite_product_rules import _point

    config = _config(tmp_path)
    supervisor = RuntimeSupervisor(config)
    now = datetime.now(UTC)
    checked = now - timedelta(minutes=10)
    supervisor.state.set_status(health="HEALTHY", last_sync_utc=now)
    # Supply actual finalized points and checkpoints, not merely a green health flag.
    supervisor.state._points = {
        s: (replace(_point(s, close_time=checked), strategy_version=supervisor.strategy.version),)
        for s in supervisor.strategy.symbols
    }
    with PaperStore(config.database_path) as store:
        store.initialize(strategy_key="v6", strategy_version=supervisor.strategy.version)
        store.save_checkpoints(dict.fromkeys(supervisor.strategy.symbols[:-1], checked))
    paper = {"positions": [], "settings": {"emergency_stop": False}}
    assert _activity_payload(supervisor, config, paper)["alive"] is False
    with PaperStore(config.database_path) as store:
        store.save_checkpoints({supervisor.strategy.symbols[-1]: checked})
    result = _activity_payload(supervisor, config, paper)
    assert result["alive"] is True
    assert "wartet" in result["message"]
    paused = _activity_payload(supervisor, config, {**paper, "settings": {"emergency_stop": True}})
    assert "Einstiegspause" in paused["message"]
