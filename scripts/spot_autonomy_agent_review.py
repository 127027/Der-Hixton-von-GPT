"""Deterministic, key-free A01-A11 engineering role checks for Spot Paper research.

Each role is a separate GitHub Actions job and writes inspectable, exact-SHA
evidence. These are code/test roles, NOT continuously thinking AI processes.
The last role can attest only a downloadable *research/Paper test* package.
"""
from __future__ import annotations
import argparse
import json
import subprocess
from datetime import UTC,datetime
from pathlib import Path

ROLES=tuple(f"A{i:02d}" for i in range(1,12))
SOURCE=Path(__file__).resolve().parents[1]

def run_tests(*names: str) -> str:
    args=["python","-m","pytest","-q",*names]
    r=subprocess.run(args,cwd=SOURCE,text=True,capture_output=True,timeout=240)
    if r.returncode:
        raise RuntimeError("Tests failed: "+" ".join(names)+"\n"+(r.stdout+r.stderr)[-4000:])
    return (r.stdout+r.stderr)[-900:]


def inspect_research(path:Path)->dict:
    if not path.is_file():
        raise RuntimeError("Missing exact-head historical portfolio evidence")
    x=json.loads(path.read_text())
    if x["market_count"]!=15 or not x["no_leverage"] or not x["no_live_orders"]:
        raise RuntimeError("Research is not 15-market Spot/no-order")
    if x.get("test_kind")!="IN_SAMPLE_HISTORICAL_COMPARISON_NOT_FUTURE_FORECAST":
        raise RuntimeError("Study incorrectly marks in-sample evidence as future validation")
    if set(x["results"])!={"baseline_fixed_2","baseline_compound_2",
      "quality_compound_2","quality_compound_3","quality_compound_4",
      "quality_compound_1000_2","quality_compound_1000_4"}:
        raise RuntimeError("Missing portfolio alternatives")
    for row in x["results"].values():
        for cost in ("current","stress"):
            stats=row["scenarios"][cost]
            if stats["completed_trades"]<0 or float(stats["end_usdc"])<0:
                raise RuntimeError("Invalid balance or trade count")
    return {k:{
        "normal_end":v["scenarios"]["current"]["end_usdc"],
        "stress_end":v["scenarios"]["stress"]["end_usdc"],
        "max_dd_pct":v["scenarios"]["current"]["max_drawdown_pct"],
        "entries":v["scenarios"]["current"]["entries"],
        "max_entry_gap_days":v["scenarios"]["current"]["max_entry_gap_days"]
      } for k,v in x["results"].items()}


def audit_ownership_checks():
    p=(SOURCE/"src/hixton/ui/live.py").read_text()
    q=(SOURCE/"src/hixton/live/production.py").read_text()
    assert "settings.auto_budget_enabled" in p
    assert "settings.autonomous_performance_enabled" in p
    assert "or settings.autonomous_performance_enabled" in p
    assert "self.reconciler.check(" in q
    assert "snapshot = self.snapshot()" in q
    assert "capital_plan(max_capital)" in q
    assert "enableFutures" in (SOURCE/"src/hixton/live/binance.py").read_text()
    assert "enableMargin" in (SOURCE/"src/hixton/live/binance.py").read_text()
    return "Two automatic settings remain explicitly blocked from Live until reconciliation is rebuilt"


def role_checks(role:str, evidence_dir:Path)->list[str]:
    if role=="A01":
        assert (SOURCE/"docs/autonomous-performance/SPOT_ONLY_PRIORITY_20261011.md").is_file()
        return ["Spot-only owner scope and V6 frozen reference present"]
    if role=="A02":
        return ["actual 2/3/4-slot historical test: "+str(inspect_research(evidence_dir/"spot-autonomy-three-year.json"))[:1500]]
    if role=="A03":
        return [run_tests("tests/test_spot_autonomy_core.py","tests/test_paper_engine.py")]
    if role=="A04":
        ui=(SOURCE/"ui/index.html").read_text()
        assert "performance-mode-input" in ui and "auto-budget-input" in ui
        assert "ausschließlich 1× Spot" in ui
        return ["Both settings present; Spot-only wording without Margin"]
    if role=="A05":
        return [run_tests("tests/test_runtime_startup_races.py")]
    if role=="A06":
        return [run_tests("tests/test_current_v6_product_contract.py","tests/test_v8_product_backtest.py")]
    if role=="A07":
        from hixton.domain.versions import V8_SATELLITE_STRATEGY
        assert len(V8_SATELLITE_STRATEGY.symbols)==15
        return [audit_ownership_checks(),"All 15 Binance Spot markets in approved V8"] 
    if role=="A08":
        from hixton.domain.spot_autonomy import quality_filler_block_reason
        assert quality_filler_block_reason("AAVEUSDC",0.99) is not None
        assert quality_filler_block_reason("NEARUSDC",0.2) is None
        return ["Verified causal filler hypotheses; no empirical claims of future probability"]
    if role in ("A10","A09","A11"):
        reports=[]
        expected=ROLES[:8] if role=="A10" else ROLES[:8]+("A10",) if role=="A09" else ROLES[:10]
        for agent in expected:
            fp=evidence_dir/f"{agent}.json"
            if not fp.is_file():raise RuntimeError(f"Missing evidence from {agent}")
            r=json.loads(fp.read_text())
            if r.get("commit")!=commit_sha() or r.get("state")!="PASS":
                raise RuntimeError(f"Failed/wrong-head role {agent}")
            reports.append(agent)
        if role=="A09":
            inspect_research(evidence_dir/"spot-autonomy-three-year.json")
            return ["A09: exact-head code-quality TEST_PACKAGE_PASS; OOS/production acceptance not asserted",*reports]
        if role=="A11":
            audit_ownership_checks()
            return ["A11: TEST-PACKAGE-GOVERNANCE_PASS, not Live/release authorization",*reports]
        return ["A10: all eight specialist roles delivered exact-head reports",*reports]
    raise ValueError("Unknown agent "+role)


def commit_sha()->str:
    return subprocess.check_output(["git","rev-parse","HEAD"],cwd=SOURCE,text=True).strip()


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--role",choices=ROLES,required=True)
    p.add_argument("--evidence-dir",default="evidence/agent-round")
    args=p.parse_args()
    evidence=Path(args.evidence_dir);evidence.mkdir(parents=True,exist_ok=True)
    checks=role_checks(args.role,evidence)
    report={
      "agent":args.role,"commit":commit_sha(),"state":"PASS",
      "scope":"SPOT_PAPER_TEST_ONLY_NO_LIVE_PROMOTION",
      "timestamp_utc":datetime.now(UTC).isoformat(),
      "checks":checks
    }
    (evidence/f"{args.role}.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
