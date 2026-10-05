"""Rejection-only final-year check of the pre-specified all-five Satellite setup.

No parameters or subset are selected here. The five accepted isolated profiles were
fixed before this check; the final year is used only to accept or reject shared use.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from validate_15coin_satellite_integration import _histories, _rules, _shared

from hixton.backtest.models import STRESS_COSTS
from hixton.data.binance import BinancePublicClient

D = Decimal
OUTPUT = Path("evidence/fixed-allfive-shared-validation.json")


def main() -> None:
    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    rules = _rules(client)
    report_start, report_end, candles, provenance = _histories(client)
    validation_start = report_start.replace(year=report_start.year + 2)

    core = _shared(
        STRESS_COSTS,
        candles,
        rules,
        validation_start,
        report_end,
        False,
    )
    integrated = _shared(
        STRESS_COSTS,
        candles,
        rules,
        validation_start,
        report_end,
        True,
    )
    delta = {
        "net_pnl": str(D(integrated["net_pnl"]) - D(core["net_pnl"])),
        "ending_equity": str(
            D(integrated["ending_equity"]) - D(core["ending_equity"])
        ),
        "max_drawdown_pct": str(
            D(integrated["max_drawdown_pct"]) - D(core["max_drawdown_pct"])
        ),
        "zero_position_hours_reduced": str(
            D(core["zero_position_hours"]) - D(integrated["zero_position_hours"])
        ),
        "completed_trades": int(integrated["completed_trades"])
        - int(core["completed_trades"]),
    }
    passed = (
        D(delta["net_pnl"]) > 0
        and D(delta["max_drawdown_pct"]) <= D("2")
        and D(delta["zero_position_hours_reduced"]) > 0
    )
    evidence = {
        "schema_version": 1,
        "purpose": "FIXED_ALL_FIVE_SHARED_REJECTION_ONLY_VALIDATION",
        "validation_start": validation_start.isoformat(),
        "validation_end": report_end.isoformat(),
        "rejection_only": True,
        "core_only": core,
        "all_five": integrated,
        "delta": delta,
        "pass": passed,
        "provenance": provenance,
        "orders_sent": False,
        "paper_state_modified": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
