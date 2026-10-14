"""Independent ledger/CSV verification and chart for concentration research."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as md
import matplotlib.pyplot as plt

ROOT = Path(
    r"C:\Users\andre\OneDrive\Desktop\Neuer Ordner\Pruefergebnisse\Konzentration-DD-Switch-20261013"
)
d = json.loads((ROOT / "Results.json").read_text(encoding="utf-8"))
assert d["status"] == "COMPLETED_RESEARCH_ONLY"
checks = []
all_ledger_checks = []
for f in ROOT.glob("*-ledger.jsonl.gz"):
    if f.name.startswith("Attempt-"):
        continue
    peak = None
    dd = D(0)
    last = None
    max_coins = 0
    cashsum = D(0)
    n = 0
    by_time = {}
    previous_quantities = {}
    with gzip.open(f, "rt", encoding="utf-8") as h:
        for line in h:
            x = json.loads(line)
            e = D(x["equity"])
            cash = D(x["cash"])
            assert e > 0 and cash >= 0
            if peak is None:
                peak = D(x["previous_equity"])
            peak = max(peak, e)
            dd = max(dd, (peak - e) / peak * 100)
            assert e >= cash
            assert sum((D(p["value"]) for p in x["positions"].values()), D(0)) + cash <= e + D(
                "1e-18"
            )
            for event in x["events"]:
                decision = datetime.fromisoformat(event["decision_close"])
                execution = datetime.fromisoformat(event["execution_open"])
                assert decision < execution <= datetime.fromisoformat(x["time"])
                if event["kind"] == "SWITCH":
                    assert D(event["previous_equity"]) == D(x["previous_equity"])
                    if not event["oracle"]:
                        name = f.name.removesuffix("-ledger.jsonl.gz").rsplit("-", 1)[0]
                        if name.startswith("full-"):
                            policy = d["catalogue"][name.removeprefix("full-")]
                            assert D(event["previous_equity"]) >= D(policy["min_equity"])
                            assert D(event["previous_dd_pct"]) >= D(policy["dd_trigger"])
                if event["kind"] == "PARTIAL_TRIM":
                    target = (
                        D(event["previous_equity"])
                        / D(
                            4
                            if "ORACLE" in f.name or "_4_" in f.name or "quarters" in f.name
                            else 6
                        )
                        / D(event["previous_price"])
                    )
                    assert target == D(event["target_quantity"])
                    assert D(event["sold_quantity"]) > 0 and D(event["remaining_quantity"]) > 0
                    assert D(event["released_cash"]) > 0
            max_coins = max(max_coins, len(x["positions"]))
            cashsum += cash / e * 100
            n += 1
            last = x
    # Match independently reconstructed metrics to the experiment results.
    label = f.name.removesuffix("-ledger.jsonl.gz")
    cost = label.rsplit("-", 1)[1]
    name = label.rsplit("-", 1)[0]
    if name.startswith("full-"):
        r = d["full"][name.removeprefix("full-")][cost]
    elif name.startswith("last-year-"):
        r = d["last_year_probe"][name.removeprefix("last-year-")][cost]
    else:
        r = d["oracle"]["results"][cost]
    assert D(last["equity"]) == D(r["ending_usdc"]) and abs(dd - D(r["dd_pct"])) < D("1e-9")
    assert max_coins == r["max_distinct_coins"]
    assert abs(cashsum / D(n) - D(r["mean_cash_pct"])) < D("1e-20")
    all_ledger_checks.append(
        {
            "file": f.name,
            "rows": n,
            "ending": last["equity"],
            "dd_pct": str(dd),
            "max_distinct_coins": max_coins,
        }
    )
for mf in (ROOT / "reports").rglob("manifest.json"):
    folder = mf.parent
    m = json.loads((folder / "metrics.json").read_text(encoding="utf-8"))
    curves = {}
    counts = {}
    with (folder / "equity.csv").open(encoding="utf-8", newline="") as f:
        for x in csv.DictReader(f):
            curves.setdefault(x["scenario"], []).append(D(x["equity"]))
    with (folder / "trades.csv").open(encoding="utf-8", newline="") as f:
        for x in csv.DictReader(f):
            counts[x["scenario"]] = counts.get(x["scenario"], 0) + 1
    for cost, curve in curves.items():
        mm = m[cost]["portfolio"]["metrics"]
        peak = D(mm["starting_equity"])
        dd = D(0)
        for e in curve:
            peak = max(peak, e)
            dd = max(dd, (peak - e) / peak * 100)
        assert curve[-1] == D(mm["ending_equity"]) and abs(dd - D(mm["max_drawdown_pct"])) < D(
            "1e-9"
        )
        assert counts[cost] == mm["completed_trades"]
        checks.append(
            {
                "report": str(folder),
                "cost": cost,
                "ending": str(curve[-1]),
                "dd_pct": str(dd),
                "realized_lots": counts[cost],
            }
        )
    # This is an overlay on the BASE contract, not an active product certificate.
    # Keep native reports immutable and attach an unambiguous research contract.
    name = folder.parent.name
    supplement = {
        "scope": "ISOLATED_CONCENTRATION_OVERLAY_NOT_PRODUCT_OR_LIVE",
        "model_version": "CONCENTRATION-RESEARCH-" + name,
        "base_strategy": d["base_strategy"],
        "base_native_source_sha256": d["source_sha256"],
        "research_algorithm_hashes": d["script_hashes"],
        "overlay_policy": d["catalogue"][name],
        "partial_realization_lots_are_not_closed_position_cycles": True,
        "product_adoption": False,
        "live_release_granted": False,
        "native_file_hashes": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (
                folder / "manifest.json",
                folder / "metrics.json",
                folder / "equity.csv",
                folder / "trades.csv",
            )
        },
    }
    (folder / "Research-Contract.json").write_text(
        json.dumps(supplement, indent=2), encoding="utf-8"
    )
(ROOT / "Independent-Validation.json").write_text(
    json.dumps(
        {"passed": True, "native_csv_scenarios": checks, "ledger_scenarios": all_ledger_checks},
        indent=2,
    ),
    encoding="utf-8",
)

# Scientific plot, hourly ledger downsampled for readability only.
selected = [
    ("baseline", "Aktueller Bot", "#172a46"),
    ("switch_6_30k", "6 verschiedene Coins ab 30k + Teilverkauf", "#009b83"),
    ("dd3_4_30k", "4 Coins ab 30k + 3% DD + Teilverkauf", "#d7841c"),
]
fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
for name, label, color in selected:
    xs = []
    ys = []
    ds = []
    peak = D(d["seed"])
    with gzip.open(ROOT / f"full-{name}-current-ledger.jsonl.gz", "rt", encoding="utf-8") as f:
        for j, line in enumerate(f):
            x = json.loads(line)
            e = D(x["equity"])
            peak = max(peak, e)
            dd = (peak - e) / peak * 100
            if j % 12 == 0:
                xs.append(datetime.fromisoformat(x["time"]))
                ys.append(float(e))
                ds.append(float(dd))
    axes[0].plot(xs, ys, label=label, color=color, lw=1.6)
    axes[1].plot(xs, ds, color=color, lw=1.5)
worst = d["drawdown_attribution"][0]["original_episode"]
peakdt = datetime.fromisoformat(worst["peak_utc"])
troughdt = datetime.fromisoformat(worst["trough_utc"])
for ax in axes:
    ax.axvspan(peakdt, troughdt, color="#172a46", alpha=0.065)
    ax.grid(alpha=0.22)
    ax.spines[["top", "right"]].set_visible(False)
axes[0].scatter(
    [peakdt, troughdt],
    [float(worst["peak_equity"]), float(worst["trough_equity"])],
    color="#172a46",
    s=25,
    zorder=3,
)
axes[0].annotate(
    "94,7% in DOT am Hoch",
    (peakdt, float(worst["peak_equity"])),
    xytext=(-175, 28),
    textcoords="offset points",
    fontsize=9,
    arrowprops={"arrowstyle": "->", "color": "#172a46"},
)
axes[0].set_ylabel("Simulierte Equity (USDC)")
axes[0].legend(loc="upper left", fontsize=9)
axes[1].set_ylabel("Drawdown (%)")
axes[1].invert_yaxis()
axes[1].xaxis.set_major_locator(md.MonthLocator(interval=6))
axes[1].xaxis.set_major_formatter(md.DateFormatter("%m/%Y"))
fig.suptitle(
    "Konzentration und Drawdown: verschiedene Coins senken Risiko, kosten hier Rendite", fontsize=12
)
fig.text(
    0.5,
    0.015,
    (
        "Identische ETH8-Basis und historische Daten; normale Modellkosten. "
        "Forschungsvarianten, keine Live-Übernahme."
    ),
    ha="center",
    fontsize=9,
    color="#555555",
)
fig.tight_layout(rect=(0, 0.035, 1, 0.96))
fig.savefig(ROOT / "Vergleich.png", dpi=160)
plt.close(fig)
print(
    json.dumps(
        {
            "csv_scenarios": len(checks),
            "ledger_scenarios": len(all_ledger_checks),
            "plot": str(ROOT / "Vergleich.png"),
        }
    )
)
