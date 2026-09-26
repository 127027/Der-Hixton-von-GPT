"""Independent audit of the downloadable Hixton Windows release package."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


EXPECTED_MARKETS = [
    "BTCUSDC",
    "ETHUSDC",
    "BNBUSDC",
    "SOLUSDC",
    "XRPUSDC",
    "ADAUSDC",
    "LINKUSDC",
    "AVAXUSDC",
    "DOTUSDC",
    "DOGEUSDC",
]
EXPECTED_VERSION = "0.5.0"
EXPECTED_ALLOCATOR = "CAPITAL-V1-2X50PCT"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def read(root: Path, relative: str) -> str:
    path = root / relative
    require(path.is_file(), f"missing required release file: {relative}")
    return path.read_text(encoding="utf-8")


def audit(root: Path, role: str, expected_source: str) -> dict[str, object]:
    manifest_path = root / "RELEASE_MANIFEST.json"
    require(manifest_path.is_file(), "RELEASE_MANIFEST.json missing from downloaded ZIP")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest.get("release_version") == EXPECTED_VERSION, "wrong release version in manifest")
    require(manifest.get("source_commit") == expected_source, "downloaded ZIP source commit is not the tested commit")
    require(manifest.get("source_branch") == "gpt/usdc-audit", "wrong source branch in release manifest")

    init_py = read(root, "src/hixton/__init__.py")
    require('__version__ = "0.5.0"' in init_py, "package code is not Hixton 0.5.0")

    config = json.loads(read(root, "config/examples/config.example.json"))
    require(config["markets"] == EXPECTED_MARKETS, "release does not contain the canonical ten USDC markets")
    require(config["backtest"]["primary_window_years"] == 3, "release backtest window is not three years")
    paper = config["paper"]
    require(paper.get("max_capital_usdc") == "250.00", "release is missing canonical max_capital_usdc")
    require("slot_count" not in paper, "old editable/fixed paper slot_count leaked into release config")
    require("target_notional_usdc" not in paper, "old fixed paper target_notional leaked into release config")

    capital = read(root, "src/hixton/domain/capital.py")
    require(EXPECTED_ALLOCATOR in capital, "new allocator version missing")
    require('slots = 2' in capital, "current allocator is not the validated two-tranche plan")
    require('DEFAULT_MAX_CAPITAL_USDC = Decimal("250.00")' in capital, "default maximum capital changed unexpectedly")

    ui_source = read(root, "ui/index.html")
    ui_shipped = read(root, "src/hixton/ui/static/index.html")
    for label, ui in (("source UI", ui_source), ("shipped UI", ui_shipped)):
        require(ui.count('id="capital-input"') == 1, f"{label} does not expose exactly one max-capital input")
        require("Maximaler USDC-Einsatz" in ui, f"{label} missing max-capital label")
        require("1 × 50 USDC" in ui, f"{label} missing separate controlled 50-USDC trial")
        require("20 % Haltgrenze" not in ui, f"{label} still contains obsolete permanent drawdown-halt text")
        require("3×80" not in ui and "3 × 80" not in ui, f"{label} still exposes old 3x80 product wording")

    dms_ui = read(root, "DMS/08_UI_UX_SPEZIFIKATION.md")
    require("genau eine editierbare Kapitalvorgabe" in dms_ui, "DMS does not define one editable max-capital input")
    require("1×50-USDC-Test" in dms_ui, "DMS missing separate controlled 1x50 test")
    require("ändert das Maximalbudget nicht" in dms_ui, "DMS does not preserve X during the 1x50 test")

    requirements = read(root, "DMS/02_VERBINDLICHE_ANFORDERUNGEN.md")
    risk = read(root, "DMS/04_MARKT_KAPITAL_RISIKO.md")
    require("CAPITAL-V1-2X50PCT" in requirements, "normative requirements missing current allocator")
    require("kein permanenter Portfolio-Drawdown-Halt" in risk, "risk contract does not match current no-permanent-halt design")

    startbot = root / "Startbot.bat"
    require(startbot.is_file(), "Windows Startbot.bat missing from downloaded ZIP")

    stale_product = re.compile(r"(?i)(3\s*[×x]\s*80\s*USDC.*(?:produkt|live|paper)|(?:produkt|live|paper).*3\s*[×x]\s*80\s*USDC)")
    for relative in ("README.md", "DMS/02_VERBINDLICHE_ANFORDERUNGEN.md", "DMS/08_UI_UX_SPEZIFIKATION.md"):
        require(not stale_product.search(read(root, relative)), f"old 3x80 product contract found in {relative}")

    role_checks: list[str] = ["manifest_identity", "version_0_5_0", "downloaded_zip_contract"]
    if role == "A01":
        role_checks += ["requirements_docs", "old_product_wording_absent"]
    elif role == "A02":
        require((root / "tests/test_backtest_exact_three_year.py").is_file(), "exact-three-year regression missing")
        role_checks += ["exact_three_year_contract"]
    elif role == "A03":
        storage = read(root, "src/hixton/paper/storage.py")
        require("max_capital_text" in storage and "capital_plan" in storage, "Paper max-capital migration missing")
        role_checks += ["paper_schema_migration"]
    elif role == "A04":
        role_checks += ["one_capital_input", "shipped_ui_matches_new_contract"]
    elif role == "A05":
        role_checks += ["release_manifest", "startbot_present"]
    elif role == "A06":
        subprocess.run(
            [sys.executable, "-m", "compileall", "-q", str(root / "src"), str(root / "scripts")],
            check=True,
        )
        role_checks += ["python_compile"]
    elif role == "A07":
        constants = read(root, "src/hixton/constants.py")
        require('QUOTE_ASSET = "USDC"' in constants, "release quote asset is not USDC")
        role_checks += ["ten_usdc_markets"]
    elif role == "A08":
        require("two ranked-repeat tranches" in capital, "allocator description drifted")
        role_checks += ["capital_allocator_2x50pct"]
    elif role == "A09":
        pyproject = read(root, "pyproject.toml")
        require('version = "0.5.0"' in pyproject, "pyproject version is not 0.5.0")
        role_checks += ["package_version_consistency"]
    elif role == "A10":
        role_checks += ["download_identity_supervision", "single_source_capital_contract"]
    elif role == "A11":
        role_checks += ["download_governance", "old_release_rejected"]
    else:
        raise RuntimeError(f"unknown role {role}")

    return {
        "schema_version": 1,
        "agent": role,
        "verdict": "PASS",
        "release_version": EXPECTED_VERSION,
        "source_commit": expected_source,
        "archive_name": manifest.get("archive_name"),
        "checks": role_checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--role", required=True, choices=[f"A{i:02d}" for i in range(1, 12)])
    parser.add_argument("--expected-source", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        result = audit(args.root, args.role, args.expected_source)
    except Exception as exc:
        result = {
            "schema_version": 1,
            "agent": args.role,
            "verdict": "FAIL",
            "error": f"{type(exc).__name__}: {exc}",
            "source_commit": args.expected_source,
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
