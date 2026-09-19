# 18 – Backteststatus und Ergebnisformat

Status: CURRENT · 19.09.2026

## Aktueller Referenzlauf
Coin Optimization Run 35463131378, Artifact 10590881515.
Fenster: 2023-09-19T19:00:00Z bis 2026-09-19T19:00:00Z.

| Modell | Incumbent | Kandidat | Delta |
|---|---:|---:|---:|
| 10×250 Baseline | 8.187,22 | **8.217,01** | +29,79 |
| 10×250 Stress | 7.659,23 | **7.692,51** | +33,28 |
| 3×80 Baseline | 1.212,98 | **1.217,91** | +4,92 |
| 3×80 Stress | 1.128,65 | **1.133,41** | +4,75 |

Kandidat 3×80 Baseline: 94 Positionszyklen / 210 Slot-Trades / 24,10 % Max-DD.
Kandidat 3×80 Stress: 94 Positionszyklen / 210 Slot-Trades / 28,62 % Max-DD.
Promotion-Gate: promotable=true.

Finaler Schritt dieses Runs: BTC VIDYA 6 -> 5. Bereits im Incumbent enthalten waren ADA Band 4,4, AVAX Band 4,6 und DOGE Momentum 18.

Maschinenlesbarer kompakter Nachweis: backtests/v6/current-evidence.json.

## Ergebnisformat
Jeder aktuelle Run dokumentiert mindestens Strategie-/Profilhash, Datenfenster, Kostenmodell, Startkapital, Slots, Endkapital, Trade-/Slotzahlen, Drawdown, Datenprovenienz und Quellcommit. Simulationen sind ausdrücklich keine Binance-Ausführungs- oder Zukunftsnachweise.
