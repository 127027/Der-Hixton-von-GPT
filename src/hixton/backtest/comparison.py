"""Describe stored evidence against active settings without changing history."""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from typing import Any

from hixton.backtest.continuity import HISTORY_MODE
from hixton.backtest.models import BASELINE_COSTS, STRESS_COSTS
from hixton.domain.versions import StrategyDefinition
from hixton.paper.models import PaperSettings


def compare_run(
    manifest: dict[str, Any],
    metrics: dict[str, Any],
    *,
    active: StrategyDefinition,
    settings: PaperSettings | None,
    starting_cash: Decimal,
    source_hash: str,
) -> dict[str, object]:
    differences: list[str] = []
    unknown: list[str] = []
    stored = manifest.get("strategy")
    stored = stored if isinstance(stored, dict) else {}
    expected = {
        "version": active.version,
        "profiles": active.profiles_payload(),
        "parameters": None if active.coin_profiles else asdict(active.parameters),
        "semantics": active.semantics.value,
        "slot_allocation": active.slot_allocation,
    }
    for field, value in expected.items():
        if field not in stored:
            unknown.append(f"Strategienachweis fehlt: {field}")
        elif stored[field] != value:
            differences.append(f"Andere Handelsregeln: {field}")
    if manifest.get("quote_asset") != active.quote_asset:
        differences.append("Andere oder ungeklärte Handelswährung")
    proof = manifest.get("validation_scope")
    recorded_hash = proof.get("python_source_sha256") if isinstance(proof, dict) else None
    if not recorded_hash:
        unknown.append("Quellcode-Nachweis fehlt")
    elif recorded_hash != source_hash:
        differences.append("Anderer Python-Code; neuen Lauf erstellen")
    expected_costs = {
        cost.name: {k: str(v) if isinstance(v, Decimal) else v for k, v in asdict(cost).items()}
        for cost in (BASELINE_COSTS, STRESS_COSTS)
    }
    if "cost_models" not in manifest:
        unknown.append("Kostenmodell nicht im Manifest festgehalten")
    elif manifest["cost_models"] != expected_costs:
        differences.append("Andere Kostenmodelle")
    baseline = metrics.get("baseline", {})
    portfolio = baseline.get("portfolio") if isinstance(baseline, dict) else None
    is_portfolio = isinstance(portfolio, dict)
    if isinstance(portfolio, dict):
        if settings is None:
            unknown.append("Aktuelle Positionsgrößen nicht verfügbar")
        else:
            try:
                if portfolio.get("slot_count") != settings.slot_count:
                    differences.append("Andere Slotanzahl")
                if Decimal(str(portfolio.get("target_notional"))) != settings.target_notional_usdc:
                    differences.append("Anderer Betrag je Position")
                if Decimal(str(portfolio.get("starting_cash"))) != starting_cash:
                    differences.append("Anderes Startkapital")
            except InvalidOperation:
                unknown.append("Kapitalnachweis fehlt oder ist ungültig")
        if portfolio.get("risk_limits_applied") is not True:
            differences.append("Portfolio-Risikoschutz fehlt oder ist ungeklärt")

    data = manifest.get("data")
    data = data if isinstance(data, dict) else {}
    continuity = data.get("history_mode") == HISTORY_MODE
    if continuity and data.get("historical_usdc_liquidity_claimed") is not False:
        differences.append("Historische Proxy-Kennzeichnung ist unvollständig")

    status = "DIFFERENT" if differences else "UNVERIFIED" if unknown else "MATCHING"
    base_scope = (
        "Gemeinsames Konto mit Slotkonkurrenz und 5-%-UTC-Tagespause; "
        "kein permanenter Portfolio-Drawdown-Halt."
        if is_portfolio
        else "Isolierte Coin-Diagnose: je 250, keine Slotkonkurrenz und "
        "kein permanenter Portfolio-Drawdown-Halt. "
        "Kein vollständiger Spiegel des 3x80-Betriebs."
    )
    continuity_note = (
        " Drei-Jahres-Strategie-Kontinuität: dieselbe aktive USDC-Strategie, dasselbe Konto-, "
        "Risiko- und Kostenmodell sowie aktuelle USDC-Ausführungsregeln. Der reale Binance-"
        "USDT-Basismarkt liefert ausschließlich den historischen Preisweg, wo eine gleich lange "
        "USDC-Historie nicht verfügbar ist; dies ist kein Nachweis historischer USDC-Liquidität."
        if continuity
        else ""
    )
    return {
        "status": status,
        "reasons": differences + unknown,
        "model": "PORTFOLIO" if is_portfolio else "ISOLATED",
        "scope": base_scope + continuity_note,
        "window_note": "Gilt nur für das gespeicherte Testfenster; "
        "keine Aussage über neuere Kerzen. "
        "Neustart in Cash, ohne heutige Positionen, manuelle Pausen oder bestehende Kontohalts.",
    }
