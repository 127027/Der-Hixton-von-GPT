"""Independent capacity audit for the three night hypotheses."""

import argparse
import csv
import json
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
            folder = Path(results["report"])
            equity = {}
            with (folder / "equity.csv").open(newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    equity[(row["scenario"], row["time_utc"])] = row
            for cost in ("current", "stress"):
                previous_equity = seed
                previous_positions = {}
                count = 0
                transitions = 0
                previous_target = 2
                distinctmax = 0
                with (folder / f"capacity-{cost}.csv").open(newline="", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        assert D(row["capacity_basis_equity"]) == previous_equity
                        target = 2
                        for threshold, n in data["catalogue"][name]["schedule"]:
                            if previous_equity >= D(threshold):
                                target = n
                        assert int(row["target_slots"]) == target
                        marked = equity[(cost, row["time_utc"])]
                        assert D(row["equity"]) == D(marked["equity"])
                        assert D(row["cash"]) == D(marked["cash"]) >= 0
                        positions = json.loads(row["positions"])
                        assert len(positions) == int(row["distinct_coins"])
                        occupied = sum(p["slots"] for p in positions.values())
                        assert occupied == int(row["occupied_slots"])
                        for symbol, position in positions.items():
                            if symbol in previous_positions:
                                assert position == previous_positions[symbol], (
                                    name,
                                    cost,
                                    row["time_utc"],
                                    symbol,
                                )
                            elif data["catalogue"][name]["schedule"] and target >= 4:
                                assert position["slots"] == 1
                            if (
                                symbol in data["catalogue"][name]["single_slot_symbols"]
                                and symbol not in previous_positions
                            ):
                                assert position["slots"] == 1
                        new = set(positions) - set(previous_positions)
                        held = set(positions) & set(previous_positions)
                        held_slots = sum(positions[s]["slots"] for s in held)
                        if new:
                            assert occupied <= target
                            assert held_slots < target
                        assert row["existing_positions_unchanged"] == "True"
                        assert D(row["largest_coin_weight_pct"]) >= 0
                        previous_equity = D(row["equity"])
                        previous_positions = positions
                        transitions += int(previous_target != target)
                        previous_target = target
                        count += 1
                        distinctmax = max(distinctmax, len(positions))
                assert distinctmax == results[cost]["capacity"]["max_actual_distinct_coins"]
                proofs.append(
                    {
                        "period": label,
                        "candidate": name,
                        "cost": cost,
                        "bars": count,
                        "transitions": transitions,
                        "max_distinct_coins": distinctmax,
                        "status": "PASS",
                    }
                )
    out = {"status": "PASS", "checked_scenarios": len(proofs), "proofs": proofs}
    (args.root / "Independent-Capacity-Validation.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "Independent capacity, immutable holdings and cash checks passed:", len(proofs), "scenarios"
    )


if __name__ == "__main__":
    main()
