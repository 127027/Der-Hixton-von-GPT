"""Fast 250-USDC stress-only hybrid slot comparison."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from research_hybrid_gap_slots import _delta, _run
from validate_15coin_satellite_integration import _histories, _rules

from hixton.backtest.models import STRESS_COSTS
from hixton.data.binance import BinancePublicClient
from hixton.domain.satellite_layer import ACTIVE_SHARED_SATELLITES, SATELLITE_SYMBOLS

D = Decimal
OUTPUT = Path("evidence/hybrid-gap-slot-quick.json")


def main() -> None:
    client = BinancePublicClient(base_url="https://data-api.binance.vision")
    rules = _rules(client)
    report_start, report_end, candles, _provenance = _histories(client)
    capital = D("250")
    core = _run(
        capital=capital,
        satellites=(),
        satellite_count=2,
        costs=STRESS_COSTS,
        candles=candles,
        rules=rules,
        report_start=report_start,
        report_end=report_end,
    )
    payload = {"core": core, "universes": {}}
    for name, satellites in (
        ("VALIDATED", ACTIVE_SHARED_SATELLITES),
        ("ALL_FIVE", SATELLITE_SYMBOLS),
    ):
        rows = {}
        for count in (2, 3, 4, 5):
            mixed = _run(
                capital=capital,
                satellites=satellites,
                satellite_count=count,
                costs=STRESS_COSTS,
                candles=candles,
                rules=rules,
                report_start=report_start,
                report_end=report_end,
            )
            rows[str(count)] = {**mixed, "delta_vs_core": _delta(core, mixed)}
        payload["universes"][name] = rows
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
