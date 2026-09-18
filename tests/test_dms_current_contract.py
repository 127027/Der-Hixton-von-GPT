# ruff: noqa: RUF001
from __future__ import annotations

from pathlib import Path

DMS = Path("DMS")

EXPECTED_DMS_FILES = {
    "00_DOKUMENTENLENKUNG_UND_START.md",
    "01_PRODUKTVISION_SCOPE.md",
    "02_VERBINDLICHE_ANFORDERUNGEN.md",
    "03_STRATEGIE_HIXTON.md",
    "04_MARKT_KAPITAL_RISIKO.md",
    "05_MARKTDATEN_UND_AKTUALISIERUNG.md",
    "06_BACKTEST_UND_VALIDIERUNG.md",
    "07_AUSFUEHRUNG_ORDERS.md",
    "08_UI_UX_SPEZIFIKATION.md",
    "09_SYSTEMARCHITEKTUR_DATENMODELL.md",
    "10_BETRIEB_MONITORING_RECOVERY.md",
    "11_SICHERHEIT_COMPLIANCE.md",
    "12_TESTS_ABNAHMEKRITERIEN.md",
    "13_KONFIGURATION_UND_SCHEMATA.md",
    "14_BUILD_PLAN_UND_DEFINITION_OF_DONE.md",
    "15_TRACEABILITY_MATRIX.md",
    "16_ENTSCHEIDUNGSLOG_UND_OFFENE_PUNKTE.md",
    "17_GLOSSAR.md",
    "18_BACKTEST_STATUS_UND_ERGEBNISFORMAT.md",
    "19_RISIKOREGISTER.md",
    "20_BETRIEBSRUNBOOK.md",
    "21_GITHUB_ZUSAMMENARBEIT.md",
    "22_QUELLEN_UND_BINANCE_PRUEFUNG.md",
    "23_ORDNERSTRUKTUR_UND_EINSTIEGSPUNKT.md",
    "CHANGELOG.md",
    "VORLAGE_BACKTEST_RUN_MANIFEST.md",
    "VORLAGE_INCIDENT_REPORT.md",
}


def _read(name: str) -> str:
    return (DMS / name).read_text(encoding="utf-8")


def test_complete_dms_set_is_present() -> None:
    assert {path.name for path in DMS.iterdir() if path.is_file()} == EXPECTED_DMS_FILES


def test_current_normative_contract_matches_active_v6() -> None:
    requirements = _read("02_VERBINDLICHE_ANFORDERUNGEN.md")
    strategy = _read("03_STRATEGIE_HIXTON.md")
    risk = _read("04_MARKT_KAPITAL_RISIKO.md")
    validation = _read("06_BACKTEST_UND_VALIDIERUNG.md")
    ui = _read("08_UI_UX_SPEZIFIKATION.md")
    schema = _read("13_KONFIGURATION_UND_SCHEMATA.md")
    decisions = _read("16_ENTSCHEIDUNGSLOG_UND_OFFENE_PUNKTE.md")
    status = _read("18_BACKTEST_STATUS_UND_ERGEBNISFORMAT.md")
    runbook = _read("20_BETRIEBSRUNBOOK.md")
    manifest = _read("VORLAGE_BACKTEST_RUN_MANIFEST.md")

    assert "aktive Universum" in requirements
    assert "USDC" in requirements
    assert "`ranked_repeat`" in requirements
    assert "keinen permanenten Drawdown-Halt" in requirements
    assert "kanonischen `StrategyDefinition`" in requirements

    assert "## Aktueller V6-Strategiestand 18.09.2026" in strategy
    assert "`ranked_repeat`" in strategy

    assert "kein permanenter Portfolio-Drawdown-Halt" in risk
    assert "10×250 USDC" in risk
    assert "3×80" in risk

    assert "## Aktueller Validierungsvertrag 18.09.2026" in validation
    assert "Parameter-/Policy-Hashes" in validation

    assert "Positionszyklen" in ui
    assert "Slot-Trades" in ui

    assert "## Aktueller Konfigurationsvertrag 18.09.2026" in schema
    assert "`slot_allocation` ist `ranked_repeat`" in schema
    assert "permanenter globaler Drawdown-Halt" in schema
    assert "**kein** aktiver Konfigurationsparameter mehr" in schema

    assert "## DEC-056 – 18.09.2026" in decisions
    assert "## DEC-057 – 18.09.2026" in decisions

    assert "111 Positionszyklen / 246 Slot-Trades" in status
    assert "492 Positionszyklen" in status

    assert "10×250-USDC-Batch" in runbook
    assert "3×80-USDC-Portfolio" in runbook

    assert "250,00 USDC" in manifest
    assert "`ranked_repeat`" in manifest
