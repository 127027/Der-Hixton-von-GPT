"""Fail-closed guard against researching from a stale product baseline.

The autonomous research branch may contain additional research-only scripts and helpers,
but product-critical strategy/config files must exactly match the latest protected
engineering branch before a research cycle can claim to test the current bot.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

PROTECTED_REF = "origin/gpt/usdc-audit"
CRITICAL_PATHS = (
    "src/hixton/domain/versions.py",
    "src/hixton/domain/capital.py",
    "src/hixton/domain/allocation.py",
    "src/hixton/domain/trade_policy.py",
    "src/hixton/constants.py",
    "tests/test_current_v6_product_contract.py",
)


def _git(*args: str) -> str:
    return subprocess.check_output(("git", *args), text=True).strip()


def _bytes_from_ref(ref: str, path: str) -> bytes:
    return subprocess.check_output(("git", "show", f"{ref}:{path}"))


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    subprocess.run(
        ("git", "fetch", "--quiet", "origin", "gpt/usdc-audit"),
        check=True,
    )
    protected_sha = _git("rev-parse", PROTECTED_REF)
    research_sha = _git("rev-parse", "HEAD")
    rows = []
    stale = []
    missing = []
    for path in CRITICAL_PATHS:
        local_path = Path(path)
        if not local_path.exists():
            missing.append(path)
            continue
        local = local_path.read_bytes()
        protected = _bytes_from_ref(PROTECTED_REF, path)
        same = local == protected
        row = {
            "path": path,
            "matches_protected": same,
            "research_sha256": _sha(local),
            "protected_sha256": _sha(protected),
        }
        rows.append(row)
        if not same:
            stale.append(path)

    output = {
        "schema_version": 1,
        "study": "PROTECTED_ENGINEERING_BASELINE_FRESHNESS",
        "protected_branch": "gpt/usdc-audit",
        "protected_engineering_sha": protected_sha,
        "research_head_sha": research_sha,
        "critical_paths": list(CRITICAL_PATHS),
        "files": rows,
        "missing_paths": missing,
        "stale_paths": stale,
        "pass": not stale and not missing,
        "rule": (
            "Research may add research-only code, but every product-critical strategy/config "
            "file listed here must byte-match the newest protected engineering branch."
        ),
    }
    path = Path("evidence") / "baseline-freshness.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))
    if not output["pass"]:
        raise SystemExit(
            "STALE_PRODUCT_BASELINE: sync protected engineering files before research"
        )


if __name__ == "__main__":
    main()
