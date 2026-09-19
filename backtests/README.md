# Backtests – zentrales Forschungs- und Lernjournal

## Status und Zweck

**Aktuelles Forschungsjournal.** Diese Datei bündelt den nachvollziehbaren Wissensstand aus
Backtests über alle zehn aktiven Kryptowährungen. Sie ersetzt keine normative DMS-Anforderung:
bei Widersprüchen gelten die aktuellen DMS-Dokumente und die aktive kanonische Strategiedefinition.

Ziel ist, dass spätere Entwickler und die A01–A11-Agenten nicht dieselben Versuche wiederholen,
Verlustmuster nicht vergessen und akzeptierte Verbesserungen immer als Teil **eines einzigen
Hixton-Systems** behandeln.

## Verbindliches Testmodell

- Hauptsystem: **250 USDC gemeinsames Konto, 3×80 USDC, ranked_repeat**.
- Diagnose: **10×250 USDC isoliert**, je ein separates 250-USDC-Konto pro Coin.
- Aktive Märkte: ADA, AVAX, BNB, BTC, DOGE, DOT, ETH, LINK, SOL und XRP gegen USDC.
- Der 10×250-Lauf dient dazu, jeden Coin unabhängig zu verstehen und zu verbessern.
- Der 3×80-Lauf ist der entscheidende Integrations-/Portfolio-Gate.
- Beide Modi müssen dieselbe kanonische Profilmap, dieselben Signalregeln und dieselben
  modellierten Kosten verwenden.
- Mehrere 80-USDC-Slots auf demselben Signal sind mehrere Kapitaltranchen desselben
  Positionszyklus; deshalb werden Positionszyklen und Slot-Trades getrennt gezählt.
- Es gibt **keinen permanenten Portfolio-Drawdown-Halt**. Drawdown bleibt Mess- und
  Optimierungsgröße; die 5-%-UTC-Tagespause sowie technische Sicherheitsgates bleiben getrennt.
- Historische Proxy-Kerzen gleicher Basisassets müssen als Proxy gekennzeichnet bleiben und sind
  kein Nachweis historischer USDC-Liquidität oder realer Fills.

## Letzter vollständig nachgewiesener Drei-Jahres-Baseline-Stand

Quelle: realer Dashboard-E2E vom 18.09.2026, Fenster
**18.09.2023 18:00 UTC bis 18.09.2026 18:00 UTC**.

### Gemeinsames 3×80-Portfolio

- Start: **250,00 USDC**
- Ende: **750,79 USDC**
- Rendite: **+200,32 %**
- **111 Positionszyklen**
- **246 Slot-Trades**
- Maximaler Drawdown: **31,97 %**
- Permanenter Drawdown-Halt: **nein**
- Blockierungen durch `MAX_DRAWDOWN_20_PERCENT`: **0**
- Weitere Blockierungen: 390 × `NO_FREE_SLOT`, 26 × VIDYA-Slope, 4 × CMO.

### 10×250 – Coin für Coin

Jeder Coin startet isoliert mit 250 USDC. Die Tabelle ist eine **Baseline-Diagnose**, keine
Empfehlung und keine Aussage, dass der Hauptbot 2.500 USDC besitzt.

| Coin | Trades | Ende USDC | PnL USDC | Rendite | Max. DD | Erster Forschungsfokus |
|---|---:|---:|---:|---:|---:|---|
| ADA | 54 | 695,16 | +445,16 | +178,06 % | 41,41 % | hohe Verlusttiefe trotz positiver Gesamtrendite; Verlustcluster und Exit/Stop prüfen |
| AVAX | 38 | 744,34 | +494,34 | +197,74 % | 38,62 % | wenige Trades, hoher DD; Entryqualität und lange Verlustphasen prüfen |
| BNB | 42 | 439,96 | +189,96 | +75,98 % | 32,58 % | niedrigste Rendite der aktuellen Baseline; schlechte Entries/Exits priorisieren |
| BTC | 44 | 568,06 | +318,06 | +127,22 % | 20,49 % | Referenz für relativ kontrollierten DD; nicht blind als Vorlage für andere Coins verwenden |
| DOGE | 47 | 874,88 | +624,88 | +249,95 % | 32,19 % | starke Rendite, aber DD noch relevant; Gewinnerstruktur bewahren |
| DOT | 43 | 499,51 | +249,51 | +99,80 % | 47,01 % | höchste aktuelle DD-Priorität; Verlusttrades, Stops und Regimewechsel untersuchen |
| ETH | 36 | 734,92 | +484,92 | +193,97 % | 25,03 % | starke Baseline bei moderatem DD; nur evidenzbasierte Änderungen |
| LINK | 50 | 604,27 | +354,27 | +141,71 % | 37,72 % | Verlustcluster/Entryfilter und Exitverhalten detailliert prüfen |
| SOL | 57 | 1.524,32 | +1.274,32 | +509,73 % | 23,81 % | stärkste Baseline; Verbesserung nur ohne Beschädigung der robusten Gewinnerstruktur |
| XRP | 81 | 584,00 | +334,00 | +133,60 % | 41,33 % | höchste Tradefrequenz bei hohem DD; Overtrading-/Signalqualitätsmuster prüfen |

10×250 gesamt: Startsumme **2.500 USDC**, Ende **7.269,42 USDC**, 492 abgeschlossene
Positionszyklen. Die Summe ist nur ein Diagnoseaggregat über zehn getrennte Konten.

## Arbeitsmethode für den nächsten Optimierungszyklus

**Alle zehn Coins werden untersucht, nicht nur die schwächsten.** Für jeden Coin wird der gleiche
Ablauf verwendet:

1. aktuelle Baseline aus unveränderlichen `manifest.json`, `metrics.json`, `trades.csv` und
   `equity.csv` sichern;
2. größte Verlusttrades und Verlustserien nach Entry-Zeitpunkt, Haltedauer, Trend-/VIDYA-/CMO-
   Kontext, Stop-/Exitgrund, Volatilität und Kosten untersuchen;
3. konkrete kausale Hypothese formulieren, z. B. schlechter Entry in Seitwärtsphase, zu später
   Exit oder ungeeigneter Stop-Abstand;
4. nur einen begrenzten, dokumentierten Kandidatenkatalog aus dieser Hypothese erzeugen;
5. Auswahl ausschließlich auf Trainingsdaten;
6. ausgewählten Kandidaten unverändert auf Validierung und Kostenstress testen;
7. vollständigen Drei-Jahres-10×250-Vergleich gegen den bisherigen Coin-Incumbent durchführen;
8. akzeptierte Coin-Kandidaten einmal zu einer neuen Zehn-Coin-Profilmap zusammensetzen;
9. mit **genau denselben Profilhashes** 10×250 und gemeinsames 3×80 neu rechnen;
10. nur übernehmen, wenn das gemeinsame 3×80 unter Baseline **und** Stress nicht schlechter wird.

Eine isolierte Verbesserung ist damit noch keine Botverbesserung. Slotkonkurrenz und zeitliche
Überlappung können dazu führen, dass ein isoliert besserer Coin das gemeinsame Portfolio
verschlechtert. Dann bleibt der Kandidat als Forschungsergebnis dokumentiert, wird aber nicht aktiv.

## Was jeder neue Forschungsabschnitt dokumentieren muss

Für **jeden Coin**:

- Datum, Strategie-/Profilversion und Datenfenster;
- Baseline: Trades, Gewinner/Verlierer, PnL, Rendite, Max-DD, Haltedauer;
- auffällige Verlusttrades bzw. Verlustcluster;
- vermutete Ursache und überprüfbare Hypothese;
- exakte Parameter-/Policy-Änderung des Kandidaten;
- Trainingsergebnis;
- Validationsergebnis;
- Stresskosten-Ergebnis;
- vollständiger Drei-Jahres-Incumbent-vs.-Challenger-Vergleich;
- Entscheidung **ACCEPT / REJECT / UNRESOLVED** mit Begründung;
- anschließend Auswirkung der zusammengesetzten Profilmap auf das gemeinsame 3×80;
- Pfade/Run-IDs der unveränderlichen Evidenz.

Fehlgeschlagene Kandidaten werden **nicht gelöscht**. Sie sind Lernmaterial und verhindern,
dass spätere Agenten denselben schlechten Versuch erneut als neue Idee behandeln.

## Bekannte Forschungsgrenzen und bereits gelernte Punkte

- Historische ältere Läufe mit permanentem 20-%-Portfoliohalt erklären nicht das aktuelle
  Betriebsverhalten und bleiben nur historische Evidenz.
- Mehr Slots allein lösen schlechte Entries nicht; sie erhöhen nur verfügbare Kapazität.
- BTC-Parameter dürfen nicht pauschal auf andere Coins übertragen werden.
- Ein Kandidat, der einen Coin isoliert verbessert, kann wegen Slotkonkurrenz das 3×80-Portfolio
  verschlechtern.
- Ein am 19.09.2026 untersuchter zusammengesetzter Kandidat verschlechterte den gemeinsamen
  3×80-Endwert ungefähr von **750,58 auf 594,60 USDC** und wurde deshalb verworfen.
- Ein untersuchter SOL-Challenger verschlechterte die isolierte Drei-Jahres-Baseline ungefähr
  von **1.521,88 auf 1.007,40 USDC** und wurde ebenfalls verworfen. SOL bleibt damit beim
  Incumbent, bis ein besser belegter Kandidat vorliegt.

Diese abgelehnten Varianten sind Forschungsevidenz, keine aktive Strategie.

## Pflegepflicht für A01–A11

- **A01:** prüft, dass README, DMS und aktive Strategie nicht widersprüchlich werden.
- **A02:** pflegt nach jedem materiellen Backtest den Coin-für-Coin-Forschungsstand und verifiziert
  Kennzahlen gegen rohe Trades/Equity.
- **A03:** beweist, dass isolierter Test, 3×80, Paper und UI dieselbe kanonische Profilmap lesen.
- **A04:** prüft verständliche Darstellung von Positionszyklen, Slot-Trades und Datenprovenienz.
- **A06:** reproduziert Kennzahlen aus Rohartefakten und lässt fehlgeschlagene Kandidaten sichtbar.
- **A08:** prüft Parameterherkunft und verhindert hindsight-only Regeln.
- **A09/A10/A11:** akzeptieren eine Optimierungsrunde erst, wenn Evidenz, Regression,
  10×250→3×80-Parität und Dokumentation vollständig sind.

## Nächster offener Zyklus

Der nächste Zyklus untersucht die zehn Coins einzeln auf Verlustursachen und mögliche
Verbesserungen. Schwerpunkt sind zunächst DOT, ADA, XRP, LINK, AVAX und BNB wegen
Drawdown bzw. relativ schwächerer Baseline; BTC, DOGE, ETH und SOL werden trotzdem vollständig
mitgeprüft, damit keine Verbesserung oder Regression übersehen wird.

Neue lokale 3×80- und 10×250-Ergebnisse des Eigentümers werden mit dem Cloud-Nachweis
abgeglichen, sobald sie vorliegen. Abweichende Fenster, Versionen oder Profilhashes werden zuerst
geklärt, bevor Ergebnisse miteinander bewertet werden.
