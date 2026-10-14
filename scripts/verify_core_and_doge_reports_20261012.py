"""Independently recompute report equity, return, drawdown and trade counts from CSV."""

import argparse
import csv
import hashlib
import json
from decimal import Decimal as D
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--roots", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    proof = []
    for root in args.roots:
        for metrics_file in sorted(root.rglob("metrics.json")):
            folder = metrics_file.parent
            manifest = json.loads((folder / "manifest.json").read_text())
            metrics = json.loads(metrics_file.read_text())
            series = {}
            with (folder / "equity.csv").open(newline="") as handle:
                for row in csv.DictReader(handle):
                    scenario = row["scenario"]
                    state = series.setdefault(scenario, {"peak": D(0), "dd": D(0), "bars": 0})
                    equity = D(row["equity"])
                    state["peak"] = max(state["peak"], equity)
                    state["dd"] = max(state["dd"], (state["peak"] - equity) / state["peak"] * 100)
                    state["last"] = equity
                    state["bars"] += 1
                    assert row["time_utc"] >= manifest["data"]["report_start_utc"]
                    assert row["time_utc"] < manifest["data"]["report_end_utc"]
            counts = {}
            with (folder / "trades.csv").open(newline="") as handle:
                for row in csv.DictReader(handle):
                    counts[row["scenario"]] = counts.get(row["scenario"], 0) + 1
            for scenario, state in series.items():
                expected = metrics[scenario]["portfolio"]["metrics"]
                end = D(expected["ending_equity"])
                returned = (state["last"] / D(expected["starting_equity"]) - 1) * 100
                assert abs(state["last"] - end) < D("1e-12"), folder
                assert abs(state["dd"] - D(expected["max_drawdown_pct"])) < D("1e-12"), folder
                assert abs(returned - D(expected["return_pct"])) < D("1e-12"), folder
                assert counts.get(scenario, 0) == expected["completed_trades"], folder
                proof.append(
                    {
                        "run_id": manifest["run_id"],
                        "strategy": manifest["strategy"]["version"],
                        "scenario": scenario,
                        "bars": state["bars"],
                        "ending_usdc": str(end),
                        "drawdown_pct": str(state["dd"]),
                        "completed_trades": counts.get(scenario, 0),
                        "equity_csv_sha256": hashlib.sha256(
                            (folder / "equity.csv").read_bytes()
                        ).hexdigest(),
                    }
                )
    args.out.write_text(
        json.dumps({"status": "PASS", "checked_scenarios": len(proof), "reports": proof}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print("Independent CSV validation passed:", len(proof), "report scenarios")


if __name__ == "__main__":
    main()
