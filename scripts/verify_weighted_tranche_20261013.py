"""Independent DD, capacity-unit, ownership and allocation-event checks."""

import argparse
import csv
import json
from datetime import datetime, timedelta
from decimal import Decimal as D
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    args = p.parse_args()
    data = json.loads((args.root / "results.json").read_text(encoding="utf-8"))
    proofs = []
    for label in ("full", "last_year_probe"):
        seed = D(
            data["full_seed"] if label == "full" else data["training_and_final_year_probe_seed"]
        )
        for name, results in data[label].items():
            config = data["catalogue"][name]
            folder = Path(results["report"])
            marked = {}
            with (folder / "equity.csv").open(newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    marked[(row["scenario"], row["time_utc"])] = row
            events = json.loads((folder / "allocation-events.json").read_text(encoding="utf-8"))
            for cost in ("current", "stress"):
                previous = seed
                peak = seed
                held = {}
                count = 0
                max_coins = 0
                by_open = {}
                with (folder / f"allocation-{cost}.csv").open(newline="", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        assert D(row["previous_closed_equity"]) == previous
                        assert D(row["previous_closed_dd_pct"]) == (peak - previous) / peak * 100
                        eq = marked[(cost, row["time_utc"])]
                        assert D(row["equity"]) == D(eq["equity"])
                        assert D(row["cash"]) == D(eq["cash"]) >= 0
                        capacity = 20 if config["weights"] else 2
                        assert int(row["ledger_capacity_units"]) == capacity
                        positions = json.loads(row["positions"])
                        assert len(positions) == int(row["distinct_coins"])
                        occupied = sum(p["units"] for p in positions.values())
                        assert occupied == int(row["occupied_units"]) <= capacity
                        for symbol, p in positions.items():
                            if symbol in held:
                                assert p == held[symbol], (name, cost, row["time_utc"], symbol)
                            assert (
                                D(p["quantity"]) > 0 and D(p["cost_basis"]) > 0 and p["units"] > 0
                            )
                        assert row["existing_positions_unchanged"] == "True"
                        previous = D(row["equity"])
                        peak = max(peak, previous)
                        held = positions
                        count += 1
                        max_coins = max(max_coins, len(positions))
                        by_open[
                            datetime.fromisoformat(row["time_utc"])
                            + timedelta(milliseconds=1)
                            - timedelta(hours=1)
                        ] = row
                for event in events[cost]:
                    row = by_open[datetime.fromisoformat(event["open_time_utc"])]
                    assert (
                        D(event["dd_basis_pct"])
                        == D(row["previous_closed_dd_pct"])
                        >= D(config["dd_trigger"])
                    )
                    weights = (
                        config["weights"]
                        if event["mode"] == "FLAT_PRIMARY_PLUS_REST"
                        else config["weights"][1:]
                    )
                    assert tuple(event["planned_units"].values()) == tuple(weights)
                    pos = json.loads(row["positions"])
                    for symbol in event["actual_new_symbols"]:
                        assert (
                            symbol in pos and pos[symbol]["units"] == event["planned_units"][symbol]
                        )
                assert max_coins == results[cost]["allocation"]["max_actual_distinct_coins"]
                proofs.append(
                    {
                        "period": label,
                        "candidate": name,
                        "cost": cost,
                        "bars": count,
                        "max_actual_coins": max_coins,
                        "planned_splits": len(events[cost]),
                        "status": "PASS",
                    }
                )
    out = {"status": "PASS", "checked_scenarios": len(proofs), "proofs": proofs}
    (args.root / "Independent-Allocation-Validation.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print("Independent DD, ownership and weighted allocation validation:", len(proofs), "PASS")


if __name__ == "__main__":
    main()
