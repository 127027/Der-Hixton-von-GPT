from __future__ import annotations

import json
from pathlib import Path

from hixton.config import load_project_config
from hixton.constants import SYMBOLS
from hixton.domain.versions import V6_COIN_STRATEGY

ROOT = Path(__file__).resolve().parents[1]


def test_product_config_has_one_canonical_v6_source() -> None:
    config_path = ROOT / "config" / "examples" / "config.example.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["strategy"] == {"key": "v6"}
    config = load_project_config(config_path, project_root=ROOT)
    assert config.strategy_key == "v6"
    assert V6_COIN_STRATEGY.config_payload()["quote_asset"] == "USDC"
    assert tuple(V6_COIN_STRATEGY.symbols) == tuple(SYMBOLS)
    assert V6_COIN_STRATEGY.version.startswith("HIXTON-V6-COIN-PAPER-1-")


def test_promoted_profiles_are_the_active_canonical_map() -> None:
    assert V6_COIN_STRATEGY.parameters_for("BTCUSDC").vidya_length == 5
    assert V6_COIN_STRATEGY.parameters_for("ADAUSDC").band_multiplier == 4.4
    avax = V6_COIN_STRATEGY.parameters_for("AVAXUSDC")
    doge = V6_COIN_STRATEGY.parameters_for("DOGEUSDC")
    assert avax.vidya_length == 6
    assert avax.momentum_length == 20
    assert avax.smoothing_length == 8
    assert avax.atr_length == 90
    assert avax.band_multiplier == 5.5
    assert doge.vidya_length == 6
    assert doge.momentum_length == 16
    assert doge.smoothing_length == 14
    assert doge.atr_length == 120
    assert doge.band_multiplier == 4.3
    assert V6_COIN_STRATEGY.policy_for("DOGEUSDC").cmo_floor == 0.2
    assert V6_COIN_STRATEGY.policy_for("XRPUSDC").cmo_floor == 0.15
    assert V6_COIN_STRATEGY.policy_for("DOTUSDC").cmo_floor == 0.35
    assert V6_COIN_STRATEGY.version == "HIXTON-V6-COIN-PAPER-1-6b12dc290869"
    assert len(V6_COIN_STRATEGY.coin_profiles) == 10


def test_product_ui_exposes_only_current_v6() -> None:
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    assert '<option value="v6">Aktuelle V6' in html
    assert '<option value="v1">' not in html
    assert '<option value="v2">' not in html
    assert '<option value="v3">' not in html
    assert "127027/Der-Hixton-von-GPT/blob/gpt/usdc-audit/" in html
    assert "127027/Der-Hixton/blob/codex/build-foundation-v1/" not in html


def test_product_uses_one_budget_driven_ranked_repeat_allocator() -> None:
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
    assert V6_COIN_STRATEGY.slot_allocation == "ranked_repeat"
    assert payload["markets"] == list(SYMBOLS)
