"""Offline upgrade checks: no production Binance clients or credentials."""

import json
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from hixton.domain.strategy import evaluate_batch
from hixton.domain.versions import strategy_definition
from hixton.live.frozen_trial import FrozenTrialPoints, continuation_strategy
from hixton.live.preparation import LivePreparation
from hixton.live.trial import SignalTrial
from tests.golden_reference import deterministic_candles
from tests.test_live_preparation import MemoryVault
from tests.test_live_trial import NOW, arm, open_position, trial, universe


def test_registered_candidate_has_exact_researched_parameters():
    old, new = strategy_definition("v8"), strategy_definition("v8r")
    assert new.entry_atr_target_fraction == "0.0075"
    assert old.entry_atr_target_fraction is None
    assert new.parameters_for("LINKUSDC").vidya_length == 8
    assert old.parameters_for("LINKUSDC").vidya_length == 6
    for symbol in old.symbols:
        if symbol != "LINKUSDC":
            assert old.parameters_for(symbol) == new.parameters_for(symbol)
        assert old.policy_for(symbol) == new.policy_for(symbol)


def test_owned_trial_restores_original_contract_and_exits_once_after_patch(tmp_path):
    controller, exchange = trial(tmp_path)
    arm(controller)
    open_position(controller)
    active = strategy_definition("v8r")
    frozen = continuation_strategy(controller.journal.path, active)
    assert frozen.key == "v6"
    restarted = SignalTrial(
        controller.journal,
        controller.executor,
        frozen,
        lambda: True,
        execution_source_sha256="new-patch",
        allocator_version="CAPITAL-V1-2X50PCT",
    )
    at = NOW + timedelta(hours=1)
    sell = universe(at, buy_symbol=None, sell_symbol="SOLUSDC")
    assert restarted.advance(sell, now=at, healthy=True)["state"] == "EXIT_PENDING"
    assert restarted.advance(sell, now=at, healthy=True)["state"] == "AWAITING_RECONCILIATION"
    restarted.advance(sell, now=at, healthy=True)
    assert [i.side for i in exchange.submits] == ["BUY", "SELL"]
    assert exchange.submits[-1].base_quantity == Decimal("0.5")
    with controller.journal._connect() as db:
        row = db.execute(
            "SELECT execution_source_sha256,strategy_json FROM signal_trial"
        ).fetchone()
    assert row[0] == "test-source-v1"
    assert json.loads(row[1]) == frozen.config_payload()


def test_unsubmitted_trial_is_not_restored_or_rearmed_after_patch(tmp_path):
    controller, exchange = trial(tmp_path)
    arm(controller)
    active = strategy_definition("v8r")
    assert continuation_strategy(controller.journal.path, active) is active
    assert not exchange.submits


def test_frozen_points_match_full_original_replay_with_changed_link_parameters():
    old, new = strategy_definition("v8"), strategy_definition("v8r")
    candles = {s: deterministic_candles(s, 650) for s in old.symbols}
    active = {
        s: tuple(
            evaluate_batch(
                s,
                candles[s],
                parameters=new.parameters_for(s),
                semantics=new.semantics_for(s),
                strategy_version=new.version,
            )
        )
        for s in new.symbols
    }
    mapper = FrozenTrialPoints(new, old)
    frozen = mapper(active)
    for symbol in old.symbols:
        expected = tuple(
            evaluate_batch(
                symbol,
                candles[symbol],
                parameters=old.parameters_for(symbol),
                semantics=old.semantics_for(symbol),
                strategy_version=old.version,
            )
        )
        assert frozen[symbol] == expected
    assert mapper(active)["LINKUSDC"] is frozen["LINKUSDC"]
    incomplete = dict(active)
    del incomplete["BTCUSDC"]
    assert mapper(incomplete) == {}
    invalid = dict(active)
    invalid["LINKUSDC"] = tuple(
        replace(p, candle=replace(p.candle, closed=False)) for p in active["LINKUSDC"]
    )
    with pytest.raises(ValueError):
        mapper(invalid)


def test_old_completed_certificate_cannot_release_new_runtime(tmp_path):
    service = LivePreparation(
        tmp_path / "trial.sqlite3", MemoryVault(), execution_source_sha256="current-source"
    )
    active = strategy_definition("v8r")
    service.connect_runtime(
        active, settings_provider=lambda: (Decimal(250), False), rules_provider=lambda: {}
    )
    report = {
        "state": "COMPLETED",
        "strategy": active.config_payload(),
        "execution_identity": {
            "source_matches_current": True,
            "allocator_matches_current": True,
            "frozen_application_version": service.application_version,
        },
    }
    assert service._trial_covers_current_runtime(report)
    report["strategy"] = strategy_definition("v8").config_payload()
    assert not service._trial_covers_current_runtime(report)
    report["strategy"] = active.config_payload()
    report["execution_identity"]["source_matches_current"] = False
    assert not service._trial_covers_current_runtime(report)


def test_service_keeps_owned_trial_separate_from_current_product(tmp_path):
    controller, _ = trial(tmp_path)
    arm(controller)
    open_position(controller)
    service = LivePreparation(
        controller.journal.path, MemoryVault(), execution_source_sha256="new-patch"
    )
    service.connect_runtime(
        strategy_definition("v8r"),
        settings_provider=lambda: (Decimal(250), False),
        rules_provider=lambda: {},
    )
    assert service.trial.strategy.key == "v6"
    assert service.live.strategy.key == "v8r"
    assert service.trial.report()["state"] == "OPEN"
    assert service.trial.report()["execution_identity"]["source_matches_current"] is False
