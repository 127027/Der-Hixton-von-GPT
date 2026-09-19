# 03 – Strategie Hixton V6

Status: CURRENT · 19.09.2026

## Aktueller V6-Strategiestand 19.09.2026
V6 ist Long-only, 1h, Close-basierte Indikatorauswertung mit 400 Warm-up-Bars. Die Strategie folgt der Hixton/Pine-v6-Semantik und besitzt coinindividuelle Profile.

| Coin | VIDYA | Mom. | Smooth | ATR | Band | Policy |
|---|---:|---:|---:|---:|---:|---|
| BTC | 5 | 20 | 8 | 120 | 4,4 | CMO 0,2 |
| ETH | 6 | 20 | 8 | 60 | 3,8 | slope 24 |
| BNB | 10 | 20 | 8 | 120 | 5,0 | – |
| SOL | 6 | 20 | 15 | 60 | 3,8 | – |
| XRP | 6 | 20 | 8 | 120 | 3,2 | Stop 4 Entry-ATR |
| ADA | 6 | 20 | 8 | 60 | 4,4 | – |
| LINK | 6 | 20 | 8 | 60 | 3,8 | slope 24 |
| AVAX | 6 | 20 | 8 | 60 | 4,6 | – |
| DOT | 6 | 20 | 8 | 60 | 3,8 | – |
| DOGE | 6 | 18 | 15 | 120 | 4,4 | CMO 0,2 |

Slotvergabe im Hauptportfolio ist ranked_repeat. Coin-Parameter sind keine separaten Bots, sondern Profile einer gemeinsamen V6.

Neue Regeln dürfen nicht aus einem Holdout-Zeitraum nachträglich erfunden werden. A08 formuliert kausale Hypothesen; A02 prüft sie reproduzierbar.
