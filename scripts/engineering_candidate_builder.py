"""Deterministically materialize a validated autonomous coin-profile candidate.

The builder is deliberately narrow: it can only change canonical V6 coin profiles
and their exact product-contract expectations. It never changes Paper/Live state,
credentials, exchange code, safety limits, or order routing.

Capital-layout promotion remains a separate engineering task because allocation
changes affect sizing semantics beyond the fixed-250 research experiment.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("HIXTON_REPO_ROOT", str(Path(__file__).resolve().parents[1]))).resolve()
VERSIONS = ROOT / "src" / "hixton" / "domain" / "versions.py"
PRODUCT_TEST = ROOT / "tests" / "test_current_v6_product_contract.py"


class CandidateBuildError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CandidateBuildError(f"{path} must contain a JSON object")
    return value


def _number(value: Any) -> str:
    d = Decimal(str(value))
    if d == d.to_integral():
        return str(int(d))
    return format(d.normalize(), "f")


def _coin_block(symbol: str, profile: dict[str, Any]) -> str:
    params = profile.get("parameters")
    policy = profile.get("trade_policy")
    if not isinstance(params, dict) or not isinstance(policy, dict):
        raise CandidateBuildError(f"{symbol}: accepted_profile is incomplete")
    required_params = (
        "vidya_length",
        "momentum_length",
        "smoothing_length",
        "atr_length",
        "band_multiplier",
        "warmup_bars",
    )
    required_policy = ("cmo_floor", "slope_bars", "stop_atr", "trail_atr")
    missing = [key for key in required_params if key not in params]
    missing += [key for key in required_policy if key not in policy]
    if missing:
        raise CandidateBuildError(f"{symbol}: missing fields {sorted(missing)}")
    return (
        "    CoinProfile(\n"
        f'        "{symbol}",\n'
        "        StrategyParameters(\n"
        f'            vidya_length={_number(params["vidya_length"])},\n'
        f'            momentum_length={_number(params["momentum_length"])},\n'
        f'            smoothing_length={_number(params["smoothing_length"])},\n'
        f'            atr_length={_number(params["atr_length"])},\n'
        f'            band_multiplier={_number(params["band_multiplier"])},\n'
        f'            warmup_bars={_number(params["warmup_bars"])},\n'
        "        ),\n"
        "        TradePolicy("
        f'cmo_floor={_number(policy["cmo_floor"])}, '
        f'slope_bars={_number(policy["slope_bars"])}, '
        f'stop_atr={_number(policy["stop_atr"])}, '
        f'trail_atr={_number(policy["trail_atr"])}'
        "),\n"
        "    ),"
    )


def _replace_coin_block(text: str, symbol: str, replacement: str) -> str:
    marker = f'"{symbol}"'
    marker_pos = text.find(marker)
    if marker_pos < 0:
        raise CandidateBuildError(f"canonical profile not found: {symbol}")
    start = text.rfind("    CoinProfile(", 0, marker_pos)
    if start < 0:
        raise CandidateBuildError(f"CoinProfile start not found: {symbol}")
    depth = 0
    end = None
    for idx in range(start, len(text)):
        char = text[idx]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                end = idx + 1
                if end < len(text) and text[end] == ",":
                    end += 1
                break
    if end is None:
        raise CandidateBuildError(f"CoinProfile end not found: {symbol}")
    return text[:start] + replacement + text[end:]


def _accepted_profiles(
    decision: dict[str, Any], coin: dict[str, Any], shifted: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    if decision.get("action") != "BUILD_ENGINEERING_CANDIDATE_AND_RUN_A01_A11":
        return {}
    validated = decision.get("validated_candidates")
    if not isinstance(validated, list):
        return {}
    coin_candidates = [
        row for row in validated
        if isinstance(row, dict) and row.get("type") == "COIN_PROFILE"
    ]
    if len(coin_candidates) != 1:
        return {}
    expected = sorted(str(x) for x in coin_candidates[0].get("accepted_symbols", []))
    shifted_coin = shifted.get("coin_profile")
    if not isinstance(shifted_coin, dict) or shifted_coin.get("shifted_window_pass") is not True:
        raise CandidateBuildError("shifted full-window coin gate is not PASS")
    observed = sorted(str(x) for x in shifted_coin.get("accepted_symbols", []))
    if not expected or expected != observed:
        raise CandidateBuildError(
            f"validated/shifted accepted symbols differ: {expected} != {observed}"
        )
    per_coin = coin.get("per_coin")
    if not isinstance(per_coin, dict):
        raise CandidateBuildError("per_coin evidence missing")
    result: dict[str, dict[str, Any]] = {}
    for symbol in expected:
        row = per_coin.get(symbol)
        profile = row.get("accepted_profile") if isinstance(row, dict) else None
        if not isinstance(profile, dict):
            raise CandidateBuildError(f"{symbol}: accepted_profile missing")
        result[symbol] = profile
    return result


def _version() -> str:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from hixton.domain.versions import V6_COIN_STRATEGY; print(V6_COIN_STRATEGY.version)",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise CandidateBuildError(completed.stderr.strip() or "cannot import patched strategy")
    return completed.stdout.strip().splitlines()[-1]


def _patch_product_test(text: str, profiles: dict[str, dict[str, Any]], version: str) -> str:
    import re

    aliases = {"AVAXUSDC": "avax", "DOGEUSDC": "doge"}
    for symbol, profile in profiles.items():
        alias = aliases.get(symbol)
        params = profile["parameters"]
        if alias:
            for attr in (
                "vidya_length",
                "momentum_length",
                "smoothing_length",
                "atr_length",
                "band_multiplier",
            ):
                pattern = rf"assert {alias}\.{attr} == [^\n]+"
                replacement = f"assert {alias}.{attr} == {_number(params[attr])}"
                text, count = re.subn(pattern, replacement, text)
                if count != 1:
                    raise CandidateBuildError(
                        f"expected one product-contract assertion for {alias}.{attr}"
                    )
    text, count = re.subn(
        r'assert V6_COIN_STRATEGY\.version == "HIXTON-V6-COIN-PAPER-1-[0-9a-f]+"',
        f'assert V6_COIN_STRATEGY.version == "{version}"',
        text,
    )
    if count != 1:
        raise CandidateBuildError("exact V6 version assertion not found")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--coin-evidence", type=Path, required=True)
    parser.add_argument("--shifted-evidence", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    decision = _load(args.decision)
    coin = _load(args.coin_evidence)
    shifted = _load(args.shifted_evidence)
    profiles = _accepted_profiles(decision, coin, shifted)

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "candidate_type": "COIN_PROFILE" if profiles else None,
        "symbols": sorted(profiles),
        "eligible": bool(profiles),
        "applied": False,
        "changed_paths": [],
        "real_money_orders_allowed": False,
        "paper_auto_activate": False,
        "live_auto_activate": False,
    }

    if profiles and args.apply:
        versions_text = VERSIONS.read_text(encoding="utf-8")
        for symbol, profile in profiles.items():
            versions_text = _replace_coin_block(
                versions_text, symbol, _coin_block(symbol, profile)
            )
        VERSIONS.write_text(versions_text, encoding="utf-8")

        version = _version()
        test_text = PRODUCT_TEST.read_text(encoding="utf-8")
        PRODUCT_TEST.write_text(
            _patch_product_test(test_text, profiles, version), encoding="utf-8"
        )
        manifest.update(
            {
                "applied": True,
                "strategy_version": version,
                "changed_paths": [
                    str(VERSIONS.relative_to(ROOT)),
                    str(PRODUCT_TEST.relative_to(ROOT)),
                ],
            }
        )

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
