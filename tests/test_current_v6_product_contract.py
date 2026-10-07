from __future__ import annotations

import json
from pathlib import Path

from hixton.config import load_project_config
from hixton.constants import SYMBOLS
from hixton.domain.satellite_layer import ACTIVE_SHARED_SATELLITES, SATELLITE_SYMBOLS
from hixton.domain.versions import V6_COIN_STRATEGY, V8_SATELLITE_STRATEGY

ROOT = Path(__file__).resolve().parents[1]


def test_v6_core_remains_the_frozen_ten_coin_regression_anchor() -> None:
    assert tuple(V6_COIN_STRATEGY.symbols) == tuple(SYMBOLS)
    assert len(V6_COIN_STRATEGY.coin_profiles) == 10
    assert V6_COIN_STRATEGY.version == "HIXTON-V6-COIN-PAPER-1-6b12dc290869"
    assert V6_COIN_STRATEGY.satellite_symbols == ()
    assert V6_COIN_STRATEGY.active_shared_satellites == ()


def test_product_config_selects_v8_without_mutating_v6() -> None:
    config_path = ROOT / "config" / "examples" / "config.example.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["strategy"] == {"key": "v8"}
    config = load_project_config(config_path, project_root=ROOT)
    assert config.strategy_key == "v8"
    assert V8_SATELLITE_STRATEGY.config_payload()["quote_asset"] == "USDC"
    assert payload["markets"] == list(V8_SATELLITE_STRATEGY.symbols)
    assert tuple(V8_SATELLITE_STRATEGY.symbols[:10]) == tuple(SYMBOLS)
    assert tuple(V8_SATELLITE_STRATEGY.symbols[10:]) == tuple(SATELLITE_SYMBOLS)


def test_v8_preserves_core_indicators_and_applies_only_verified_dot_overlay() -> None:
    for symbol in SYMBOLS:
        assert V8_SATELLITE_STRATEGY.parameters_for(symbol) == V6_COIN_STRATEGY.parameters_for(
            symbol
        )
        if symbol == "DOTUSDC":
            policy = V8_SATELLITE_STRATEGY.policy_for(symbol)
            assert policy.cmo_floor == 0.35
            assert policy.slope_bars == 24
            assert policy.stop_atr == policy.trail_atr == 0
            assert V6_COIN_STRATEGY.policy_for(symbol).slope_bars == 0
        else:
            assert V8_SATELLITE_STRATEGY.policy_for(symbol) == V6_COIN_STRATEGY.policy_for(symbol)
    assert V8_SATELLITE_STRATEGY.satellite_symbols == SATELLITE_SYMBOLS
    assert V8_SATELLITE_STRATEGY.active_shared_satellites == ACTIVE_SHARED_SATELLITES
    assert ACTIVE_SHARED_SATELLITES == ("NEARUSDC", "AAVEUSDC", "BCHUSDC")


def test_promoted_core_profiles_stay_exact() -> None:
    assert V6_COIN_STRATEGY.parameters_for("BTCUSDC").vidya_length == 5
    assert V6_COIN_STRATEGY.parameters_for("ADAUSDC").band_multiplier == 4.4
    avax = V6_COIN_STRATEGY.parameters_for("AVAXUSDC")
    doge = V6_COIN_STRATEGY.parameters_for("DOGEUSDC")
    assert (avax.vidya_length, avax.momentum_length, avax.smoothing_length) == (6, 20, 8)
    assert (avax.atr_length, avax.band_multiplier) == (90, 5.5)
    assert (doge.vidya_length, doge.momentum_length, doge.smoothing_length) == (6, 16, 14)
    assert (doge.atr_length, doge.band_multiplier) == (120, 4.3)
    assert V6_COIN_STRATEGY.policy_for("DOGEUSDC").cmo_floor == 0.2
    assert V6_COIN_STRATEGY.policy_for("XRPUSDC").cmo_floor == 0.15
    assert V6_COIN_STRATEGY.policy_for("DOTUSDC").cmo_floor == 0.35


def test_product_ui_exposes_only_current_v8() -> None:
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    assert '<option value="v8">Aktuelle V8' in html
    assert '<option value="v6">' not in html
    assert '<option value="v1">' not in html
    assert '<option value="v2">' not in html
    assert '<option value="v3">' not in html


def test_product_uses_one_modular_two_slot_allocator() -> None:
    config_path = ROOT / "config" / "examples" / "config.example.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    config = load_project_config(config_path, project_root=ROOT)
    assert payload["paper"]["starting_cash_usdc"] == "250.00"
    assert payload["paper"]["max_capital_usdc"] == "250.00"
    assert "slot_count" not in payload["paper"]
    assert "target_notional_usdc" not in payload["paper"]
    assert config.paper_max_capital_usdc == 250
    assert config.paper_slot_count == 2
    assert config.paper_target_notional_usdc == 125
    assert V8_SATELLITE_STRATEGY.slot_allocation == "ranked_repeat"
