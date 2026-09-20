# 18 – Backteststatus und Ergebnisformat

Status: CURRENT · 19.09.2026

## Aktueller Referenzlauf
Coin Optimization Run 35463131378, Artifact 10590881515.
Fenster: 2023-09-19T19:00:00Z bis 2026-09-19T19:00:00Z.

| Modell | Aktueller kanonischer Lauf |
|---|---:|
| 10×250 isoliert | **8.217,01 USDC** |
| 3×80 Portfolio | **1.217,91 USDC** |

3×80 aktuell: 94 Positionszyklen / 210 Slot-Trades / 24,10 % Max-DD.
Der aktuelle kanonische Coin-Mix enthält BTC VIDYA 5, ADA Band 4,4, AVAX Band 4,6 und DOGE Momentum 18.

Forschungsalternativen einschließlich Buy-and-Hold, Stress-/Robustheitsvarianten und verworfener Kandidaten bleiben im Forschungsjournal. Im Produkt gibt es pro Coin nur eine kanonische aktive Methode und in der normalen UI nur deren Ergebnis.

Maschinenlesbarer kompakter Nachweis: backtests/v6/current-evidence.json.

## Ergebnisformat
Jeder aktuelle Run dokumentiert mindestens Strategie-/Profilhash, Datenfenster, Kostenmodell, Startkapital, Slots, Endkapital, Trade-/Slotzahlen, Drawdown, Datenprovenienz und Quellcommit. Simulationen sind ausdrücklich keine Binance-Ausführungs- oder Zukunftsnachweise.
