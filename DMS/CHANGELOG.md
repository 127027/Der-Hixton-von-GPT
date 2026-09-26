# DMS Changelog

## 26.09.2026 – Hixton 0.5.0 Max-Budget Release Readiness
- Einzige aktuelle Kapitalvorgabe ist `max_capital_usdc`; `CAPITAL-V1-2X50PCT` leitet die zwei `ranked_repeat`-Tranchen ab.
- Alte 3×80-Angaben wurden aus aktuellen Produkt-, Agenten-, Architektur-, CLI- und Betriebsverträgen entfernt bzw. ausdrücklich als historische Forschung gekennzeichnet.
- Die sichtbare alte Drawdown-Haltbeschriftung wurde aus Quell- und ausgelieferter UI entfernt.
- Der kontrollierte lokale Ersttest bleibt vom Maximalbudget getrennt; Cloud/CI/A01–A11 bleiben ohne private Binance-Zugangsdaten und ohne Orderausführung.
- Frischer exakter Drei-Jahres-Dashboard-E2E: Run 36233820495; authoritative Zahlen liegen im zugehörigen maschinenlesbaren Artefakt.
- Der Download-Audit prüft Version, Source-Commit, SHA-256, UI, Allocator und A01–A11 gegen dasselbe ZIP-Artefakt.

## 19.09.2026 – V6 Product Cleanup
- Aktuelle V6 auf einen Produktpfad konsolidiert.
- Profilverbesserungen ADA Band 4,4, AVAX Band 4,6, DOGE Momentum 18 und BTC VIDYA 5 dokumentiert.
- Aktueller Researchcheckpoint: 10×250 8.217,01 USDC; 3×80 1.217,91 USDC.
- Config-Duplikation von V6-Digest/Profilen entfernt; nur strategy.key=v6 bleibt.
- UI/API/CLI auf aktuelle V6 reduziert; alte Backtestauswahl entfernt.
- Legacy-Backtestordner aus aktuellem Branch entfernt; Lernpunkte ins zentrale Journal übernommen.
- Agentenmission von alter USDT→USDC-Migration auf CURRENT_V6_PRODUCT umgestellt.
- Optimierungsworkflow als research-only alle sechs Stunden geplant.
- Root-Agent-Memory auf aktuelle A01–A11-Struktur reduziert.

## Historie
Frühere Versionen, Migrationsstudien und verworfene Forschungsstände bleiben vollständig in Git erhalten. Sie sind keine aktiven Anforderungen.
