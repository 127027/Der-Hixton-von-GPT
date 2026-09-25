# 03 – Strategie Hixton V6

Status: CURRENT · 25.09.2026

V6 ist Long-only, 1h und entscheidet auf abgeschlossenen Kerzen mit 400 Warm-up-Bars. Coin-Profile sind keine separaten Bots, sondern zehn Profile derselben Strategie.

| Coin | VIDYA | Mom. | Smooth | ATR | Band | Policy |
|---|---:|---:|---:|---:|---:|---|
| BTC | 5 | 20 | 8 | 120 | 4,4 | CMO 0,2 |
| ETH | 6 | 20 | 8 | 60 | 3,8 | slope 24 |
| BNB | 10 | 20 | 8 | 120 | 5,0 | – |
| SOL | 6 | 20 | 15 | 60 | 3,8 | – |
| XRP | 6 | 20 | 8 | 120 | 3,2 | CMO 0,15 + Stop 4 Entry-ATR |
| ADA | 6 | 20 | 8 | 60 | 4,4 | – |
| LINK | 6 | 20 | 8 | 60 | 3,8 | slope 24 |
| AVAX | 6 | 20 | 8 | 60 | 5,2 | – |
| DOT | 6 | 20 | 8 | 60 | 3,8 | CMO 0,35 |
| DOGE | 6 | 18 | 15 | 120 | 4,4 | CMO 0,2 |

Kapitalvergabe im Hauptportfolio kommt ausschließlich aus dem zentralen Maximalbudget-Allocator und verwendet ranked_repeat. Der Allocator bevorzugt aktuelle Signale; historische Coin-Performance wird nicht als feste Coin-Gewichtung in die Runtime eingebaut.
