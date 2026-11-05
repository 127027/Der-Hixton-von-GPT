"""Offline archive/environment verification; never loads trading modules or submits orders."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import platform
import sys
from zipfile import ZipFile

ARTIFACT_ID = 13353475540
ARCHIVE_SHA = "4c333fb26aae06dde163c46bc0ed81c699e9eff34764957dee4cde3572255272"
COMMIT = "f56d48536525830dd6ea50bf5bc174a6f9aeff8c"
SOURCE_SHA = "5cf39658dc6b1ee827ec0daefd73b2384a9edd0ff116ba0203f9ab8bb7737797"
PORTFOLIO_SHA = "06da08bf4e63613a5c655eaa34a3361d0b192645e1d128cf545e4075c0401dfd"
INPUT_SHA = "eaf4de1fc87b9ba14500a0a68d2f86b6b150ed572d87dbf0a4ecd5dc9fda0961"
MAX_MEMBER = 40_000_000


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_fingerprint(root):
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_text(encoding="utf-8").encode())
        digest.update(b"\0")
    return digest.hexdigest()


def verify_archive(path, expected_sha=ARCHIVE_SHA):
    if sha(path) != expected_sha:
        raise ValueError("Original archive SHA256 mismatch")
    with ZipFile(path) as archive:
        members = archive.namelist()
        required = ["C0-native-hourly.json.gz", "S01-native-hourly.json.gz",
                    "C0-native-summary.json", "S01-native-summary.json",
                    "S02-DIAG-002-Report.json"]
        if len(members) != len(set(members)) or set(members) != set(required):
            raise ValueError("Unexpected/duplicate archive members")
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failure")
        if any(item.file_size > MAX_MEMBER for item in archive.infolist()):
            raise ValueError("Oversized archive member")
        with gzip.GzipFile(fileobj=io.BytesIO(archive.read(required[0]))) as stream:
            raw = stream.read(MAX_MEMBER + 1)
        if len(raw) > MAX_MEMBER:
            raise ValueError("Oversized expanded C0 ledger")
        ledger = json.loads(raw)
        summary = json.loads(archive.read("C0-native-summary.json"))
        if ledger["frozen"] != COMMIT or summary["frozen_product"] != COMMIT:
            raise ValueError("Native commit mismatch")
        if summary["source_sha256"] != SOURCE_SHA:
            raise ValueError("Native source binding mismatch")
        if summary["original_input_contract_sha256"] != INPUT_SHA:
            raise ValueError("Original input contract mismatch")
        if summary["native_source_sha256"] != PORTFOLIO_SHA:
            raise ValueError("Portfolio source mismatch")
        if len(ledger["rows"]) != 26304:
            raise ValueError("Unexpected C0 row count")
        return {"archive_sha256": expected_sha, "artifact_id": ARTIFACT_ID,
                "members": required, "c0_hours_read": len(ledger["rows"]),
                "source_commit": COMMIT, "source_sha256": SOURCE_SHA,
                "input_contract_sha256": INPUT_SHA,
                "member_sha256": {n: hashlib.sha256(archive.read(n)).hexdigest()
                                  for n in required}}


def verify_source(product_root):
    root = Path(product_root)
    fingerprint = source_fingerprint(root / "src/hixton")
    portfolio = root / "src/hixton/backtest/portfolio.py"
    portfolio_sha = hashlib.sha256(portfolio.read_text(encoding="utf-8").encode()).hexdigest()
    if fingerprint != SOURCE_SHA or portfolio_sha != PORTFOLIO_SHA:
        raise ValueError("Read-only product reference does not match frozen source")
    return {"source_sha256": fingerprint, "portfolio_sha256": portfolio_sha}


def forbid_network(event, args):
    if event.startswith("socket."):
        raise RuntimeError("Offline verifier forbids network activity")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--product-reference", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError("Use a fresh output; existing evidence is never overwritten")
    sys.addaudithook(forbid_network)
    report = verify_archive(args.archive)
    report["reference"] = verify_source(args.product_reference)
    report.update(status="OFFLINE_ENVIRONMENT_AND_ORIGINAL_BINDINGS_PASS",
                  python=platform.python_version(), implementation=platform.python_implementation(),
                  verifier_sha256=sha(__file__), redis_required=False,
                  third_party_dependencies=[], financial_replay_executed=False,
                  independent_multifill_qa_executed_by_this_script=False,
                  product_modified=False,
                  scope="Archive integrity/schema/provenance smoke test, not a strategy or financial QA approval.")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(json.dumps({"status": report["status"], "c0_hours_read": report["c0_hours_read"]}))


if __name__ == "__main__":
    main()
