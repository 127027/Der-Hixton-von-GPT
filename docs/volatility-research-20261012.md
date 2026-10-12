# Weitere Verbesserung: schwankungsabhängige Positionsgrößen — 12.10.2026

**Ergebnis:** Eine Größenregel nach der Schwankung der jeweiligen Währung ist ein stärkerer Forschungsansatz als die bisherige LINK-Anpassung allein. Bei 0,75% ATR-Referenz steigt das historische Portfolio-Endkapital gegenüber dem laufenden V8 geringfügig und der Drawdown sinkt von 47,63% auf 41,81%. Unter höheren Kosten verbessert sich der Endwert deutlicher und der Drawdown fällt von 60,76% auf 50,75%. Das strenge Ziel von mindestens 20% relativer Drawdown-Reduktion wurde damit noch nicht erreicht. Kein neuer Ansatz wird als freigegebener Live-Ersatz dargestellt.

## Gemeinsamer Vergleich

Festes Forschungsfenster: 11.10.2023 19:00 UTC bis 11.10.2026 19:00 UTC, davor 400 Aufwärmkerzen. Startkapital 1.092,05773944 USDC. Alle Varianten nutzen dieselben Marktdaten, Handelsfilter, zwei Slots, Gewinn-/Verlust-Wiederanlage, Core-Priorität und Füllerregeln. Die LINK-Anpassung ist VIDYA 8 statt 6.

| Variante | Endkapital normal | Drawdown normal | Endkapital Stress | Drawdown Stress |
|---|---:|---:|---:|---:|
| Bisheriger V8 | 28.922,29 | 47,63% | 17.491,55 | 60,76% |
| LINK allein | 35.855,55 | 46,55% | 21.956,55 | 59,95% |
| LINK + ATR-Referenz 0,75% | 29.459,95 | 41,81% | 20.803,15 | 50,75% |
| LINK + ATR-Referenz 0,60% | 18.256,61 | 36,43% | 13.621,75 | 44,69% |

Die 0,75%-Variante gibt einen Teil des Mehrgewinns der reinen LINK-Variante für geringeres Risiko ab. Gegenüber dem tatsächlich laufenden V8 bleibt das historische normale Endkapital etwas höher. Die 0,60%-Variante reduziert den Drawdown stärker, opfert jedoch zu viel Gewinn und wurde nach den festgelegten Kriterien verworfen.

## Letztes Jahr als gesonderte Gegenprüfung

| Variante | Rendite normal | Drawdown normal | Rendite Stress | Drawdown Stress |
|---|---:|---:|---:|---:|
| Bisheriger V8 | 5,04% | 37,50% | -18,90% | 51,18% |
| ATR-Referenz 0,75% | 4,18% | 36,18% | -9,78% | 44,48% |
| ATR-Referenz 0,60% | 2,76% | 32,07% | -8,90% | 39,55% |

Das letzte Jahr bleibt unter Stresskosten negativ. Die Variante ist somit kein Nachweis dauerhafter Profitabilität. Alle betrachteten Jahre wurden bereits in früheren Arbeiten untersucht; die zeitliche Gegenprüfung ist kein unberührter Out-of-Sample-Test.

## Die neue Größenregel

Vor einem Kauf wird aus der abgeschlossenen Signalkerze ATR / Schlusskurs bestimmt. Bei einer ATR-Referenz von 0,75% gilt:

`Anteil der normalen Tranche = min(1, 0.0075 × Signal-Schlusskurs / Signal-ATR)`

Beispiel: Liegt ATR / Kurs bei 2%, werden 37,5% der normalen Tranche eingesetzt. Liegt die Schwankung unter 0,75%, bleibt die normale Tranche verfügbar. Höher als das ursprüngliche Budget wird niemals gekauft. Nicht eingesetztes Kapital bleibt USDC und zählt vollständig zur Equity und zum Drawdown.

Es handelt sich um die Größe neuer Einstiege. Bestehende Positionen werden nicht laufend umgeschichtet; die Ausstiegsregeln bleiben gleich. 0,75% ist eine Schwankungsreferenz, kein garantierter Höchstverlust und kein Stoppreis. Der separate Echtgeld-Einmaltest bleibt bei seinem 50-USDC-Kaufbudget.

Die Regel ist als optionale Eigenschaft der Strategie implementiert. Die normalen V6-/V8-Definitionen enthalten keine aktive ATR-Größenregel; ihre Parameter, Versionskennung und Config-Identität bleiben unverändert. Die aktuelle V8-Standardstrategie auf GitHub verwendet weiterhin die bisherigen Größen.

## Backtest, Paper, Live und Neustart

Die gemeinsame Funktion `entry_volatility_fraction` wird von Portfolio-Backtest, Paper und normaler Live-Ausführung verwendet. Sie erhält die ATR und den Schlusskurs des gespeicherten Signals, keine zukünftigen Kurse. Ein ausstehender Live-Kauf wird vor der Übermittlung erneut gegen das gespeicherte Signal und die frische Kontenprüfung geprüft. Ein Neustart mit später veränderter ATR darf das vorgemerkte Kaufbudget nicht erhöhen. Fehlende oder ungültige Eingaben sperren die risikobasierte Berechnung.

Offline-Tests bestätigen identische Paper-/Backtest-Fills und Equity sowohl mit Wiederanlage als auch mit festem Budget und aufgeteilt über einen Neustart. Live-Tests verwenden ausschließlich eine simulierte Börse und prüfen das eingefrorene Budget nach einem Neustart. Echte Binance-Preise, Gebühren und Ausführungszeiten können vom simulierten nächsten Open abweichen; identische Echtgeld-Fills wurden damit nicht behauptet.

## Auswahl, NEAR und Ablehnung

Die breite Größenfamilie testete ATR-Referenzen 0,5%, 0,75%, 1%, 1,5%, 2% zusätzlich zu V8 und LINK allein. Zwei getrennte Trainingsjahre bei Stresskosten mussten profitabel bleiben, mindestens 75% der bisherigen Rendite halten und den Drawdown jeweils um 20% senken. Nach Trainings-Rendite/Drawdown wurde 0,75% eingefroren. Die abschließende Vollzeit-Prüfung verfehlte die verlangte Drawdown-Reduktion.

Eine offen dokumentierte adaptive Verfeinerung prüfte 0,6%, 0,625% und 0,65% und priorisierte den geringsten schlechtesten Trainings-Drawdown. Der vor der erneuten Gegenprüfung eingefrorene Gewinner 0,6% verlor im gesamten Zeitraum sowie im letzten normalen Jahr zu viel Rendite. Die Kriterien wurden nicht nachträglich gelockert.

NEAR wurde im gemeinsamen Portfolio separat untersucht: abschalten sowie CMO-Schwellen 0,30 / 0,40 / 0,50. Vergleich war die LINK-Variante. Keine dieser Möglichkeiten bestand beide Trainingsjahre mit nicht höherem Drawdown. Weniger kurze Trades allein rechtfertigen daher noch keinen Umbau. NEAR bleibt im laufenden Bot unverändert.

## Softwarequalität und Umfang

72 Forschungs-Portfolio-Läufe und 36 zusätzliche exakte Reproduktionsläufe; die abschließenden zwölf Fälle stimmen mit den gespeicherten Kennzahlen überein. Der finale Python-Quellfingerprint lautet:

`6ec3882f47f58344004e70fb9d0e495926b3c45ad15fe4df1bbb66db319f018f`

Gesamttests: 560 bestanden, 2 übersprungen, keine Fehler. Die übersprungenen Tests benötigen ausdrücklich den echten Windows-Vault bzw. den Browser-E2E-Lauf; beide wurden nicht durch Fake-Ergebnisse ersetzt. Ruff besteht für `src scripts tests`; Mypy prüft alle 66 Quelldateien fehlerfrei.

Der erste umfassende Lauf deckte zwei alte Testprobleme auf: Der eingeschränkte Windows-Testbenutzer konnte den Git-Commit des anders besitzenden Forschungsordners nicht lesen; der abschließende Lauf erfolgte unter dessen Besitzer ohne globale Git-Sicherheitsausnahme. Eine alte öffentliche Daten-Testquelle lieferte bei der zusammengelegten Kerzenabfrage keinen nächsten Öffnungskurs. Die Fixture wurde korrigiert und prüft zusätzlich, dass diese vorläufige Kerze niemals in Indikatoren eingeht. Ältere Typ-, Import- und Formatfehler wurden im Entwicklungsstand bereinigt; Handelsfilter wurden dafür nicht abgeschaltet.

## Betriebszustand und Grenzen

In `C:\Users\andre\OneDrive\Desktop\Neuer Ordner` wurden ausschließlich die neuen Prüfberichte gespeichert. Python-Dateien, API-Schlüssel, Einstellungen, Paper-Ledger, Echtgeldtest und laufender Prozess wurden nicht verändert. Kein Neustart, keine Orders, kein Livewechsel. Auf GitHub liegen Entwicklungscode und Forschungsbelege; keine Variante ist für den laufenden Bot aktiviert. A09-/A11-Promotionsfreigaben werden nicht behauptet.

Kosten pro Seite: normal 10 Basispunkte Gebühr + 2 Spread + 3 Slippage, Stress 10 + 10 + 20. Fehlende ältere USDC-Kerzen werden offen durch USDT-Kerzen ergänzt, mit den gespeicherten aktuellen USDC-Handelsfiltern. Keine historische USDC-Liquiditätsgarantie. Der Drawdown wird auf Stunden-Schlusswerten gemessen und kann stärkere zwischenzeitliche Rückgänge nicht vollständig abbilden.

## Reproduktion

Mit marktbezogenen Kopien der beiden SQLite-Dateien in einem separaten Ordner, ohne private Tabellen:

```powershell
$env:PYTHONPATH = "$PWD\src"
python scripts/research_volatility_budget_20261012.py --family volatility --data SNAPSHOT --out NEW_BROAD_DIR
python scripts/research_volatility_budget_20261012.py --family volatility_risk --data SNAPSHOT --out NEW_RISK_DIR
python scripts/research_volatility_budget_20261012.py --family fillers --data SNAPSHOT --out NEW_FILLER_DIR
python scripts/verify_volatility_budget_20261012.py --data SNAPSHOT --broad NEW_BROAD_DIR/results.json --refined NEW_RISK_DIR/results.json --out NEW_PROOF_DIR
```

Die Snapshot-Loader lehnen fehlende Netzwerk-Ersatzdaten ab. Ergebnisse, Auswahlkataloge, Ablehnungen, Source-Bindung und native HTML-Berichte liegen unter `docs/volatility-research-20261012/`.
