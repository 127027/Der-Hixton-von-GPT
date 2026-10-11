# Einzelwährungen verbessern: Prüfung vom 11.10.2026

**Ergebnis:** Zwei konkrete Forschungsvarianten bestehen die Gegenprüfung für die jeweilige Einzelwährung: LINK mit VIDYA-Länge 8 statt 6 und SUI mit einer zusätzlichen positiven VIDYA-Steigung über 72 Stunden. Der Portfolio-Drawdown bleibt allerdings hoch. Keine Strategie wurde im laufenden Bot aktiviert.

## Umfang und Methode

Alle 15 Währungen wurden in drei Familien untersucht: Handelsfilter/ATR-Ausstiege, Indikatorparameter und gezielte Kombinationen. Insgesamt 822 native historische Läufe einschließlich Baselines, chronologischer Gegenprüfungen, gemeinsamer Portfolio-Läufe und abschließender Reproduktion. Identische Marktdaten, keine privaten Binance-Abfragen oder Orders.

Gemeinsamer Zeitraum: 11.10.2023 19:00 UTC bis 11.10.2026 19:00 UTC, davor 400 Warm-up-Stunden. Zwei Jahresabschnitte zur Auswahl, anschließend das letzte Jahr zur Ablehnung einer ausgewählten Variante. Alle Auswahlentscheidungen wurden vor dem letzten Jahr gespeichert und per Prüfsumme gebunden. Die Vergangenheit wurde bereits mehrfach untersucht; dies ist **kein unberührter Out-of-Sample-Test**. Auch die große Variantenanzahl erhöht das Risiko einer Anpassung an die Vergangenheit.

Die Auswahl behält vorhandene strengere Filter bei. Zwei Trainingsjahre unter Stresskosten müssen je mindestens drei abgeschlossene Trades haben, dürfen im Drawdown nicht schlechter sein und müssen mindestens min(0, bisherige Rendite) halten. Mindestens 70% der aufsummierten positiven bisherigen Jahresrenditen und mindestens 15% geringerer schlechtester Trainings-Drawdown sind erforderlich. Danach wird die Variante mit dem kleinsten schlechtesten Trainings-Drawdown gewählt. Im letzten Jahr müssen beide Kostenfälle bestehen: Drawdown nicht höher; mindestens 80% einer positiven bisherigen Rendite bzw. keine Verschlechterung einer negativen Rendite. Keine Neuauswahl anhand des letzten Jahres.

## Konkrete Einzelvarianten

| Währung | Änderung | Rendite vorher → Variante | Drawdown vorher → Variante | Trades vorher → Variante |
|---|---|---:|---:|---:|
| LINKUSDC | VIDYA 6 → 8 | 191,90% → 209,99% | 30,96% → 21,38% | 24 → 27 |
| SUIUSDC | zusätzliche VIDYA-Steigung 72h | 234,94% → 207,14% | 39,57% → 30,82% | 85 → 49 |

SUI: Bei normalen Kosten fällt das Endkapital von 3.684,29 auf 3.378,59 USDC. Dafür verbessert sich der Stressfall von +150,36% auf +185,17% bei 33,83% statt 49,67% Drawdown. SUI bleibt eine Forschungswährung und wird dadurch nicht für den gemeinsamen Handel freigegeben.

LINK: Einzel-Endkapital 3.210,87 → 3.409,84 USDC. Im letzten Jahr bleibt der Einzeltest negativ, aber verbessert sich von −4,91% auf −1,83% bei normalen Kosten und von −7,94% auf −4,97% unter Stress. Es wird nicht behauptet, dass alle Jahresabschnitte profitabel sind.

## Wirkung von LINK auf das gemeinsame Portfolio

Startkapital 1.092,05773944 USDC, zwei Slots, vollständige Gewinn-/Verlust-Wiederanlage, ursprüngliche Core-Priorität und aktiver Qualitätsfilter. Alle übrigen Profile und die Kapitalverteilung bleiben gleich.

| Zeitraum und Kosten | Bisheriges Endkapital | LINK-Variante Endkapital | Bisheriger DD | LINK-Variante DD |
|---|---:|---:|---:|---:|
| 3 Jahre, normal | 28.922,29 | 35.855,55 | 47,63% | 46,55% |
| 3 Jahre, Stress | 17.491,55 | 21.956,55 | 60,76% | 59,95% |
| letztes Jahr, normal | 1.147,05 | 1.147,05 | 37,50% | 37,50% |
| letztes Jahr, Stress | 885,69 | 885,69 | 51,18% | 51,18% |

Die LINK-Variante erhöht den historischen Endwert, senkt den Portfolio-Drawdown jedoch nur um rund 1,08 Prozentpunkte im normalen Fall. Im letzten Jahr sind die gemeinsamen Ergebnisse unverändert. Das vorab festgelegte Portfolio-Ziel von mindestens 20% relativer Drawdown-Senkung in beiden Vollzeit-Kostenfällen wurde **nicht** erreicht. Keine der drei Familien hat diesen Freigabe-Test bestanden. Die Werte unterscheiden sich vom früheren 28.452,83-USDC-Bericht, weil hier ein gemeinsamer vier Stunden später liegender Zeitraum verwendet wird; beide Portfolio-Varianten nutzen exakt denselben Zeitraum.

## Ursachen und Kostenempfindlichkeit

AVAX: 12 von 19 abgeschlossenen Trades negativ. Der schlechteste Trade verlor rund 38,91% nach einer vorherigen Aufwärtsbewegung; 11 von 12 Verlierern waren zeitweise mindestens 2% im Plus. ADA: 18 von 20 Verlierern waren vorher mindestens 2% im Plus; wenige lange Trends tragen den Gewinn. Ein engerer Ausstieg kann somit Verluste begrenzen, aber zugleich große Trendgewinne abschneiden. Die untersuchten Varianten liefern hierfür noch keine über die Abschnitte ausreichend stabile Lösung.

UNI: Die 60 Trades unter 72 Stunden verlieren zusammen rund 1.668 USDC, während die wenigen längeren Trades Gewinne erzeugen. NEAR: sehr hoher Umsatz mit 284 abgeschlossenen Trades; höhere Ausführungskosten kippen die Rendite. Diese rückblickenden Haltedauer-/MFE-Befunde werden nicht als zukünftige Signale oder Gewinnfilter verwendet. Abgeschlossene Trade-PnL-Summen enthalten keine offenen Positionen oder Dust-Bewertungen.

| Währung | Rendite normal | Rendite Stress | Drawdown normal | Drawdown Stress |
|---|---:|---:|---:|---:|
| AAVEUSDC | 133,79% | 65,39% | 30,25% | 45,50% |
| ADAUSDC | 141,34% | 117,54% | 46,96% | 49,37% |
| AVAXUSDC | -20,53% | -27,76% | 66,73% | 68,21% |
| BCHUSDC | 130,24% | 86,98% | 29,61% | 38,89% |
| BNBUSDC | 179,52% | 166,17% | 15,10% | 16,30% |
| BTCUSDC | 137,73% | 116,64% | 16,51% | 20,25% |
| DOGEUSDC | 254,26% | 230,03% | 31,28% | 32,79% |
| DOTUSDC | 105,16% | 95,17% | 22,65% | 24,27% |
| ETHUSDC | 195,72% | 177,30% | 23,25% | 25,13% |
| LINKUSDC | 191,90% | 178,73% | 30,96% | 33,11% |
| NEARUSDC | 145,50% | -34,88% | 51,76% | 85,39% |
| SOLUSDC | 567,82% | 537,06% | 23,81% | 23,81% |
| SUIUSDC | 234,94% | 150,36% | 39,57% | 49,67% |
| UNIUSDC | 27,28% | -27,33% | 72,75% | 81,62% |
| XRPUSDC | 155,11% | 79,47% | 43,41% | 49,69% |

## Verworfene Ansätze

ETH Stop-ATR 4: Besteht das Training, kippt im letzten Jahr die normale Rendite von +10,44% auf −9,02%. ADA Steigung 72h: Senkt den Drawdown, verschlechtert die letzte Jahresrendite aber von −18,45% auf −36,17%. NEAR CMO 0,40: Senkt die letzte normale Rendite von +113,83% auf +61,89% und verschlechtert den Stress-Drawdown. Die zusätzlichen Hybrid-Varianten bestanden die abschließende Gegenprüfung ebenfalls nicht. Deshalb werden diese Ansätze nicht als Verbesserung übernommen.

## Ausführung, Sicherheit und Nachweis

Kosten pro Seite: normal 10 Basispunkte Gebühr + 2 Spread + 3 Slippage; Stress 10 + 10 + 20. Gebühren und Handelsrundung sind im nativen Engine enthalten. Stops/Trailing reagieren auf abgeschlossene 1h-Kerzen und werden am nächsten Open simuliert; keine garantierten Intrastunden-Stoppreise. Der ausgewiesene Drawdown basiert auf Stundenschluss-Equity. Fehlende ältere USDC-Kerzen werden durch dokumentierte USDT-Kerzen ergänzt; heutige USDC-Regeln beweisen keine historische USDC-Liquidität.

Die bestehenden V6- und V8-Definitionen wurden nicht verändert. Es gab keinen Neustart, keine Schlüsseländerung, keine Testfreigabe und keine neue Liveaktivierung. Die Varianten sind ausführbare, versionierte Forschungsdefinitionen im Backtest-Code; kein Echtgeld- oder Paper-Freigabenachweis. A09/A11-Freigaben werden nicht behauptet.

Betroffene Tests und Ruff-Prüfung bestehen. Einzelne Kandidaten wurden mit dem fertig formatierten Forschungscode exakt reproduziert. Details in verification.json, policies-results.json, parameters-results.json, hybrid-results.json, candidate-recipes.json sowie den nativen HTML-Berichten unter reports/.

Reproduktion mit separaten marktbezogenen SQLite-Kopien:

```powershell
python scripts/research_coin_policies_20261011.py --family policies --data SNAPSHOT --out NEW_POLICY_DIR
python scripts/research_coin_policies_20261011.py --family parameters --data SNAPSHOT --out NEW_PARAMETER_DIR
python scripts/research_coin_policies_20261011.py --family hybrid --data SNAPSHOT --out NEW_HYBRID_DIR
python scripts/verify_coin_research_20261011.py --data SNAPSHOT --experiments NEW_POLICY_DIR/results.json NEW_PARAMETER_DIR/results.json --out NEW_VERIFICATION_DIR
```

Wichtig: Diese Skripte benötigen konsistente Kopien von hixton-usdc.sqlite3 und backtest-history.sqlite3 mit ausschließlich Marktdaten. Die Arbeit erfolgt auf diesen Kopien; der Loader lehnt fehlende Netzwerk-Ersatzdaten ab. Ergebnisse bleiben Forschung, bis zusätzliche unabhängige Prüfung und zukünftige Beobachtung vorliegen.
