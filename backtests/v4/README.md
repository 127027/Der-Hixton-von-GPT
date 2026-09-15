# Backtest V4 – Prüfung vom 05.09.2026

Status: **RESEARCH_ONLY / NICHT AKTIVIEREN**. Aktive Paperstrategie bleibt V2. V4 ist ein Forschungsbericht, keine freigegebene Strategie und kein zusätzlicher Botstarter.

## Versuchsaufbau

- Daten: Binance Spot, zehn feste DMS-Coins, 1h, 400 Warm-up-Bars; je Coin 26.704 lückenlos geprüfte Kerzen.
- Gesamtfenster: [01.09.2023 12:00 UTC, 01.09.2026 12:00 UTC).
- Training: zwei separat gestartete Jahresfenster vom 01.09.2023 bis 01.09.2025. Je Coin 24 Kandidaten: VIDYA 6/10, Momentum 20, SMA 8/15, ATR 60/120, Band 3,2/3,8/4,4.
- Auswahl: höchste schlechteste Jahresrendite unter Stresskosten, bei Gleichstand höchste Summe beider Trainingsrenditen. Danach werden die Parameter eingefroren.
- Nachprüfung: neuer Start am 01.09.2025 mit 250 USDT je Coin bzw. gemeinsam 240 USDT. Vergleich bis 01.09.2026, jeweils auch Baseline. Das Fenster war bereits in der V2-Forschung sichtbar: **kein unangetasteter Holdout**.
- Screening mit Float ohne Mengenrundung; endgültige Einzel- und Portfoliowerte mit produktiver Decimal-Ausführung, Binance-Filtern und Next-bar-Open. Der gemeinsame 3×80-Test enthält unverändert 5-%-Tagespause und 20-%-Drawdown-Halt. Isolierte 250-USDT-Tests bewerten die Einzelstrategie ohne gemeinsamen Portfoliohalt.
- Baseline je Seite: 10 bp Gebühr + 2 bp Spread + 3 bp Slippage. Stress: 10 + 10 + 20 bp. BNB-Rabatt wird nicht vorausgesetzt. Keine automatische Kapitalhochskalierung.

## Warum das gute Dreijahresergebnis nicht genügt

Alle Werte sind Endkapital in USDT; Start je Spalte 250 USDT. Die Einjahreswerte sind **neue Konten**, nicht der Kontostand eines bereits 2023 begonnenen Bots.

| Coin | V2 volle 3 Jahre Baseline | V2 jüngstes Jahr Baseline | V2 jüngstes Jahr Stress | Coin-Kandidat jüngstes Jahr Stress |
|---|---:|---:|---:|---:|
| BTCUSDT | 414,47 | 182,27 | 162,99 | 206,64 |
| ETHUSDT | 649,16 | 237,46 | 213,63 | 213,63 |
| BNBUSDT | 388,69 | 205,02 | 183,90 | 210,90 |
| SOLUSDT | 1.508,45 | 219,44 | 201,11 | 192,86 |
| XRPUSDT | 557,38 | 169,83 | 153,37 | 206,33 |
| ADAUSDT | 678,79 | 127,67 | 114,86 | 108,42 |
| LINKUSDT | 612,46 | 212,28 | 195,53 | 181,16 |
| AVAXUSDT | 526,69 | 131,50 | 116,51 | 120,44 |
| DOTUSDT | 447,99 | 157,15 | 145,47 | 105,59 |
| DOGEUSDT | 808,14 | 193,82 | 175,17 | 190,34 |

Im vollen Fenster sind alle zehn positiv, aber BTC, BNB und DOT erreichen nicht 500 USDT. Im jüngsten Neustartjahr verlieren alle zehn, sogar bei Baselinekosten. Coinparameter verbessern fünf Stress-Einzelwerte, lassen ETH unverändert und verschlechtern vier. Das ist kein stabiler Vorteil für alle zehn Coins.

## Gemeinsames 3×80-Konto

| Variante / Startfenster | Ende Baseline | Ende Stress | abgeschlossene Trades Baseline / Stress |
|---|---:|---:|---:|
| V2, volle 3 Jahre | 542,49 | 406,29 | 108 / 30 |
| Coin-Kandidat, volle 3 Jahre | 712,90 | 680,52 | 104 / 101 |
| V2, Neustart jüngstes Jahr | 216,71 | 210,47 | 17 / 17 |
| Coin-Kandidat, Neustart jüngstes Jahr | 205,70 | 201,51 | 12 / 12 |

Die hohen Dreijahreswerte enthalten Trainingsdaten und einen vorzeitigen Risikohalt; sie belegen keine drei Jahre durchgehenden Handel. V2 hält in der Dreijahres-Baseline am 06.02.2025, unter Stress bereits am 05.02.2024. Der Coin-Kandidat verschlechtert das jüngste Neustartfenster. Er wird deshalb trotz höherem Gesamtwert nicht übernommen. Exakte Haltzeiten, Drawdowns, Kosten, Parameter und Daten-/Quellhashes stehen im [kuratierten JSON](reports/review-20260905.json).

## Getrennte Hypothese: sukzessive Nachkäufe

Anders als V3 kopiert dieser Versuch nicht einen einzigen Kauf in drei Slots. Nach dem ersten Hixton-Kauf erlaubt er einen weiteren bestätigten Cross über das obere Band, frühestens 24 Bars nach dem vorigen Kauf und mindestens einen ATR über dessen Ausführungspreis; maximal drei getrennte 80-USDT-Einstiege. Ein Hixton-Verkauf schließt den Gesamtbestand.

Dies ist nur ein vereinfachter Stress-Screen des jüngsten Jahres mit jeweils eigenem 240-USDT-Konto pro Coin, ohne Binance-Mengenrundung und ohne Portfolio-Risikohalt. Keine Vermischung mit dem produktiven gemeinsamen Konto. Er erhöht die Einstiegszahl, verschlechtert jedoch acht von zehn Endwerte und erhöht alle zehn maximalen Drawdowns. BTC verbessert sich von 228,11 auf 252,84 USDT, DOT verschlechtert sich von 180,24 auf 137,40 USDT. Mangels breitem Vorteil erfolgt keine Aktivierung und keine Behauptung exakter Live-Fill-Parität dieses Screens.

## Reproduktion und nächste Arbeit

Ein Einstiegspunkt, ein Befehl:

```powershell
py -3 src/main.py backtest research --output backtests/v4/runs/neuer-review/research.json
```

Die Läufe `review-20260905` und `review-20260905-verified` liefern identische Coin- und Portfoliomesswerte. Der zweite Lauf enthält zusätzlich Kosten-, Filter- und Quellhash-Metadaten. SHA-256 seiner vollständigen lokalen Datei: `80BDF589BF30F078834158277B430AFFD3D141064E2438DCACBA49DC1B22265D`. Große Runs bleiben lokal; der kompakte JSON-Auszug wird versioniert. Es gibt keine Zufallsauswahl.

Nächster fachlicher Schwerpunkt ist der Schutz in Verlust-/Seitwärtsphasen mit vorab festgelegten chronologischen Prüfregeln, nicht weiteres Optimieren auf die bereits betrachtete Zielrendite. Zuerst muss die korrigierte Paper-Ausführung vorwärts beobachtet werden. Weitere Live-Blocker: realistischer Latenz-/Orderbuch-/Teilfillnachweis, privater Orderadapter mit Reconciliation/Accountfiltern, Not-Aus-/Restore-/Fehlerfälle, dediziertes Konto und Eigentümerfreigabe. Keine Renditegarantie.
