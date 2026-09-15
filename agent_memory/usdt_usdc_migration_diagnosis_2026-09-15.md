# USDT -> USDC Backtest-Diagnose, 2026-09-15

## Auftrag

Ursache fuer den starken Ergebnisunterschied zwischen dem historischen gemeinsamen
3x80-USDT-Portfolio (rund +193 %, 733.31 aus 250) und dem heutigen 3x80-USDC-
Portfolio (rund 203-204 aus 250) bestimmen. Produktionscode, Strategieparameter,
Risikolimits und Live-Verhalten bleiben unveraendert, solange kein technischer
Defekt belegt ist.

## Verifizierte Kernaussage

Der grosse Einbruch wird **nicht** durch die Quote-Migration USDT -> USDC erklaert.
Mit aktuellem V6-Rechenkern und identischem spaeteren Startzeitpunkt 2024-03-24
00:00 UTC ergeben sich:

| Lauf | Start | Ende | 3x80 Portfolio | Abschluesse | 10x250 isoliert |
| --- | --- | --- | ---: | ---: | ---: |
| USDT historisches Originalfenster | 2023-09-01 12:00 UTC | 2026-09-01 12:00 UTC | 733.31 | 187 | 7152.29 |
| USDT frischer spaeterer Neustart | 2024-03-24 00:00 UTC | 2026-09-01 12:00 UTC | 201.11 | 9 | 4118.70 |
| USDC gleicher spaeterer Neustart | 2024-03-24 00:00 UTC | 2026-09-01 12:00 UTC | 203.62 | 14 | 4007.26 |

Damit ist USDC im direkten 3x80-Gleichzeitraum sogar 2.51 Quote-Einheiten besser
als USDT. Beim 10x250-Batch liegt USDC 111.44 unter USDT; diese Differenz ist real,
aber viel zu klein, um den Absturz 733 -> 203 zu erklaeren.

## Hauptursache: anderer Kontopfad

Das historische USDT-Portfolio startet bereits 2023-09-01. Am ersten Stunden-
schluss des 2024-03-24 besitzt dieser durchgelaufene Kontopfad laut bestehendem
Migrationsaudit bereits 681.09 Equity einschliesslich offener Positionen.

Der spaetere USDT- und USDC-Kontrolllauf startet dagegen am 2024-03-24 komplett
neu mit 250. Dadurch unterscheiden sich ab diesem Zeitpunkt:

- Kontoequity und High-Water-Mark,
- offene Positionen und belegte Slots,
- Strategie-/Positionszustand,
- relative Verlustschwellen,
- Folge der akzeptierten und blockierten Signale.

Ein Neustart am Beginn der verfuegbaren gemeinsamen USDC-Historie ist deshalb
kein fairer Ersatz fuer den bereits seit September 2023 laufenden USDT-Kontopfad.

## Zweite Hauptursache: persistenter 20-%-Portfolio-Risikohalt

`run_shared_portfolio_backtest()` initialisiert `PortfolioRiskState` aus dem
jeweiligen `starting_cash`. `evaluate_portfolio_risk()` fuehrt eine dauerhafte
Sperre fuer neue Einstiege ein, sobald der Drawdown relativ zur High-Water-Equity
20 % erreicht. Die 5-%-Tagesverlustgrenze pausiert Einstiege fuer den UTC-Tag.

Im kontrollierten spaeteren Fenster:

- USDT-Halt: 2024-04-30,
- USDC-Halt: 2024-05-01.

Die Slot-Ursachenpruefung fuer das USDC-3x80-Portfolio zaehlt 473 Kaufkandidaten:

- 14 ausgefuehrte Kaeufe,
- 431 durch Risikohalt blockiert,
- 24 durch Coinfilter blockiert,
- nur 4 wegen voller Slots blockiert.

Damit ist weder eine versteckte Ein-Slot-Grenze noch eine primaere Slotknappheit
die Ursache des niedrigen Trade-Counts. Der dominante Unterdruecker ist der
fruehe Kontorisikohalt nach Verlusten im neuen Kontopfad.

Die groessten realisierten Portfolioverlustbeitraege des Audits stammen von
LINK (-16.18), BNB (-10.33) und DOT (-7.31 USDC).

## Warum Risikoschutz abschalten keine Korrektur ist

Der diagnostische 3x80-Lauf ohne Kontorisikogates produziert zwar 197 Abschluesse,
endet unter Baseline aber nur bei 223.10 und unter Stress bei 156.23; der maximale
Drawdown steigt auf 54.28 %. Das Entfernen des Risikoschutzes stellt den alten
733er-Verlauf daher nicht wieder her und verschlechtert die Robustheit deutlich.

## Quote- und Strategiemigration

Der bestehende Migrationsaudit verifiziert:

- die zehn numerischen Coinprofile des alten USDT-Referenzlaufs,
- identische Hashes der urspruenglichen USDT-Kerzen,
- keine Regelabweichungen im kontrollierten Replay,
- unveraenderte TradePolicy / Kontorisikogrenzen gegen den V6-Aktivierungsstand.

USDT-Daten wurden fuer die Kontrollrechnung nicht als USDC-Preise ausgegeben.
Nur Symbolbezeichner wurden separat im Speicher an den heutigen Validator
angepasst; die wirtschaftliche Quote und Preise blieben USDT.

Echte USDC-Paare koennen wegen leicht anderer Kerzen einzelne Signale verschieben.
Der direkte Gleichzeitraum zeigt aber, dass dieser Quote-Effekt klein gegenueber
dem Kontopfad-/Startzeit-Effekt ist.

## Engine-/Regressionsevidenz

Der Portfolio-Code bewertet Signale chronologisch, verarbeitet Exits vor Entries,
sortiert Entries ueber die gemeinsame Prioritaetsfunktion und verwendet echte
Slotallokation. Der Risk-State wird aus Startkapital, laufender Equity und
High-Water-Mark fortgeschrieben.

Vorhandene Tests pruefen unter anderem:

- spaetere USDC-Listings verschieben das gemeinsame kontinuierliche Fenster;
- Datenluecken werden nicht synthetisch aufgefuellt;
- USDC bleibt ein echtes USDC-Marktuniversum;
- fuer alle zehn Coins und Baseline/Stress liefern Einzel- und Portfolio-Engine
  bei identischen Kapital-/Regelbedingungen identische Signale, Fills, Trades und
  Endwerte.

Der vorhandene direkte Paper-/Portfolio-Replay meldet 28/28 identische Fills und
203.718610797945 USDC Endequity; auch in zwei unterbrochenen Verarbeitungsschritten
bleibt das Ergebnis identisch.

## Diagnose

1. **Kein belegter USDT->USDC-Codefehler.**
2. **Primaere Ursache:** nicht vergleichbare Startzeit / Kontopfadabhaengigkeit.
3. **Dominanter Mechanismus im frischen 3x80-Pfad:** frueher 20-%-Drawdown-Halt,
   der den Grossteil spaeterer Entries blockiert.
4. **Sekundaer:** reale Candle-/Signalunterschiede USDT vs. USDC; im kontrollierten
   Gleichzeitraum jedoch klein.
5. **10x250 und 3x80 sind nicht dieselben Kapitalmodelle:** isolierte Coinlaeufe
   konkurrieren weder um gemeinsame Slots noch um einen gemeinsamen Portfolio-
   Risikostatus.

## Entscheidung zur Korrektur

Kein Produktionspatch vorgenommen. Einen Strategie-, Slot- oder Risikopatch nur
zum Wiedererreichen von 733 USDC vorzunehmen waere keine Fehlerkorrektur, sondern
eine neue Strategieoptimierung. Dafuer ist ein getrenntes, zeitlich validiertes
Forschungsmandat erforderlich.

Die derzeit korrekte Antwort auf die Kontrollfrage lautet:

> Wenn USDT und USDC im exakt gleichen spaeteren Zeitraum mit identischem
> Startkapital und denselben Regeln frisch starten, ist USDC im gemeinsamen
> 3x80-Portfolio **nicht wesentlich schlechter**; in der vorhandenen Kontrolle
> endet USDC bei 203.62 und USDT bei 201.11.
