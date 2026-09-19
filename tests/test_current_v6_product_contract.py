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
    assert V6_COIN_STRATEGY.parameters_for("AVAXUSDC").band_multiplier == 4.6
    assert V6_COIN_STRATEGY.parameters_for("DOGEUSDC").momentum_length == 18
    assert len(V6_COIN_STRATEGY.coin_profiles) == 10


def test_product_ui_exposes_only_current_v6() -> None:
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    assert '<option value="v6">Aktuelle V6' in html
    assert '<option value="v1">' not in html
    assert '<option value="v2">' not in html
    assert '<option value="v3">' not in html
    assert "127027/Der-Hixton-von-GPT/blob/gpt/usdc-audit/" in html
    assert "127027/Der-Hixton/blob/codex/build-foundation-v1/" not in html


def test_product_is_paper_only_and_baseline_is_3x80() -> None:
    payload = json.loads(
        (ROOT / "config" / "examples" / "config.example.json").read_text(encoding="utf-8")
    )
    assert payload["paper"]["starting_cash_usdc"] == "250.00"
    assert payload["paper"]["slot_count"] == 3
    assert payload["paper"]["target_notional_usdc"] == "80.00"
    assert payload["markets"] == list(SYMBOLS)
