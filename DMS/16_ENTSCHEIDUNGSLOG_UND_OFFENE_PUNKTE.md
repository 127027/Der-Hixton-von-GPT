# 16 – Entscheidungslog und offene Punkte

Status: CURRENT · 25.09.2026

## DEC-061 – 19.09.2026
Coin-Optimierung läuft regelmäßig automatisiert, bleibt research-only. Kein Auto-Merge und keine automatische Paper-/Live-Aktivierung.

## DEC-062 – 25.09.2026
Das feste 3×80-Hauptmodell wird durch eine einzige Kapitalvorgabe ersetzt: `max_capital_usdc`. Der validierte Allocator `CAPITAL-V1-2X50PCT` leitet daraus zwei ranked-repeat-Tranchen zu je 50 % ab. Standard: 250 USDC → 2 × 125 USDC.

10×250 bleibt isoliertes Coin-Labor. Kandidaten werden isoliert gesucht und anschließend gegen das kanonische Maximalbudget-Portfolio geprüft. Backtest, Paper und normaler Livebetrieb müssen denselben Kapitalplan konsumieren.

Der erste Echtgeldtest bleibt unabhängig davon exakt 1 × 50 USDC und ändert das gespeicherte Maximalbudget nicht.

Offen bis zur echten lokalen Inbetriebnahme:
- kontrollierten 1×50-Binance-Roundtrip durchführen und vollständig reconciliieren;
- tatsächliche Fill-/Fee-Evidenz prüfen;
- erst danach normalen Maximalbudget-Livebetrieb durch die vorhandenen Gates freigeben.
