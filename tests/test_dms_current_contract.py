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
    structure = _read("23_ORDNERSTRUKTUR_UND_EINSTIEGSPUNKT.md")

    assert "BTCUSDC" in requirements and "DOGEUSDC" in requirements
    assert "Maximalbudget" in requirements
    assert "CAPITAL-V1-2X50PCT" in requirements
    assert "2 × 50 %" in requirements
    assert "keinen permanenten Drawdown-Halt" in requirements
    assert "kanonische V6" in requirements

    assert "Status: CURRENT · 25.09.2026" in strategy
    assert "| BTC | 5 |" in strategy
    assert "| XRP | 6 | 20 | 8 | 120 | 3,2 | CMO 0,15" in strategy
    assert "| AVAX | 6 | 20 | 8 | 60 | 5,2 |" in strategy
    assert "| DOT | 6 | 20 | 8 | 60 | 3,8 | CMO 0,35" in strategy

    assert "kein permanenter Portfolio-Drawdown-Halt" in risk
    assert "10×250 USDC" in risk
    assert "2 × 125 USDC" in risk

    assert "exakt drei Kalenderjahre" in validation
    assert "Top-K" in validation
    assert "Maximalbudget-Portfolio" in validation

    assert "Maximaler USDC-Einsatz" in ui
    assert "CAPITAL-V1-2X50PCT" in ui
    assert "1×50-USDC-Test" in ui

    assert '"strategy": { "key": "v6" }' in schema
    assert "max_capital_usdc" in schema
    assert "DEC-062" in decisions

    assert "Statische alte 3×80-Ergebniswerte sind keine aktuelle Produktreferenz mehr" in status
    assert "2 × 125 USDC" in status

    assert "Maximaler USDC-Einsatz" in runbook
    assert "1 × 50 USDC" in runbook

    assert "backtests/v6" in structure
    assert "V1–V5" not in structure
