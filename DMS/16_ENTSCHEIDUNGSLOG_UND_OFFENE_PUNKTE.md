# 16 – Entscheidungslog und offene Punkte

Status: CURRENT · 19.09.2026

## DEC-056 – 18.09.2026
Der permanente 20-%-Portfolio-Drawdown-Einstiegshalt wird aus der aktiven V6 entfernt. Drawdown bleibt Messgröße; 5-%-UTC-Tagespause und technische Gates bleiben.

## DEC-057 – 18.09.2026
Hauptmodell ist 250 USDC / 3×80 ranked_repeat. 10×250 ist isoliertes Coin-Labor und kein Hauptkontomodell.

## DEC-058 – 19.09.2026
Optimierung nutzt Training-only Top-K, getrennte Validation/full/stress und zwingenden marginalen 3×80-Gate vor Kombination.

## DEC-059 – 19.09.2026
src/hixton/domain/versions.py ist einzige V6-Profil-/Digestquelle. Runtime-Config speichert nur strategy.key = v6.

## DEC-060 – 19.09.2026
Normale UI/API/CLI zeigen ausschließlich aktuelle V6. Historische Produktmodi werden nicht mehr auswählbar gehalten.

## DEC-061 – 19.09.2026
Coin-Optimierung läuft regelmäßig automatisiert, bleibt aber research-only. Kein Auto-Merge und keine automatische Paper-/Live-Aktivierung.

## DEC-062 – 19.09.2026
Aktueller Branch enthält nur backtests/v6 als Produkt-Backtestordner. Historie bleibt über Git und kompaktes Lernjournal nachvollziehbar.

## Offene Punkte
- Finalen Cleanup-Commit durch Preflight, E2E, vollständige Regression und A01–A11 bringen.
- Nach final validierter V6-ID den persistenten Paper-State explizit ohne Reset aktivieren und A05-Freshness erneut bestätigen.
- Weitere Optimierungen nur über den bestehenden Top-K-/Portfolio-Gate.
- Live-Trading bleibt außerhalb des aktuellen Releaseumfangs.
