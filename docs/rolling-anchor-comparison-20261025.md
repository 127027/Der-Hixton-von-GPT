# Warum 32.469,39 und 21.558,10 USDC keine Fortsetzung desselben Kontos sind

Prüfung vom 24.–25.10.2026. Verglichen werden die tatsächlich gespeicherten
Berichte, keine neuen Prognosen und kein aktueller Binance-Kontostand. Aktives
Produkt bleibt `v8r`, Strategieversion
`HIXTON-V8-LINK8-ATR075-DOGE50-DD10-ETH8-DIV32-CLOSECAP-PAPER-6`.
Die Bezeichnung `current_v6` in internen Forschungsdateien bezeichnet diese
Version 6 von v8r, nicht den eingefrorenen V6-Zehncoin-Anker.

## Originalberichte reproduziert

| Bericht | Berichtsfenster UTC | Start USDC | Ende USDC | Max-DD |
| --- | --- | ---: | ---: | ---: |
| Früherer DOGE50-Anker | 11.10.2023 19:00 bis 11.10.2026 19:00 | 1.092,05773944 | 32.469,39 | 39,13 % |
| Gespeichertes aktuelles Produkt | 23.10.2023 13:00 bis 23.10.2026 13:00 | 1.039,26093944 | 21.558,10 | 38,21 % |

Beide Ergebnisse einschließlich des exakten Drawdowns wurden mit dem nativen
Portfolio-Motor reproduziert. Alle 15 Kerzenhashes jedes Originalmanifests stimmen
mit den rekonstruierten Eingangsdaten überein. Auf den gemeinsamen Zeitstempeln
sind OHLC, Volumen und Tradezahl aller 15 Märkte identisch; eine Revision dieser
Marktdaten erklärt die Differenz nicht. Die originale DOGE50-Kontrolle wurde
zusätzlich ohne Indikatorcache ausgeführt: alle Fills und Metriken sind gleich.
Die Original-Börsenfilter ergeben hier dieselbe Zahl wie die heutigen Filter.

Die verwendete historische USDT-Continuity für fehlende USDC-Historie bleibt
offengelegt. Die Ergebnisse beweisen keine historische USDC-Orderbuchliquidität.

## Vergleich mit identischem Startkapital und identischen Kosten

Je Fenster starten beide Definitionen ohne Positionen mit **1.039,26093944 USDC**,
allen 15 Marktdatenreihen, denselben Börsenfiltern, Wiederanlage und autonomen
Spot-Einstellungen. Normal je Seite: 10 bp Gebühr, 2 bp Spread, 3 bp Slippage;
Stress: 10/10/20 bp. Nur der versionierte Regelstand wird gewechselt.

| Fenster | Regelstand | Normal Ende | Normal DD | Stress Ende | Stress DD |
| --- | --- | ---: | ---: | ---: | ---: |
| 11.10.–11.10. | Früher DOGE50 | 30.901,33 | 39,13 % | 21.716,37 | 48,57 % |
| 11.10.–11.10. | Aktuelle v8r-Version 6 | **33.777,01** | **30,48 %** | **22.401,40** | **47,73 %** |
| 23.10.–23.10. | Früher DOGE50 | 20.957,56 | 39,14 % | 14.632,08 | 48,58 % |
| 23.10.–23.10. | Aktuelle v8r-Version 6 | **21.558,10** | **38,21 %** | **15.096,95** | **47,73 %** |

Die aktuelle Definition ist damit in beiden untersuchten Fenstern bei normalen
und erhöhten Kosten besser als DOGE50. Ein Rückbau auf die alten Regeln stellt
das alte 32k-Ergebnis im neueren Fenster nicht wieder her. Das ist ein Vergleich
zweier bereits bekannter Definitionen, keine neue Parametersuche oder Freigabe.

Nur das geringere Startbudget reduziert beim alten DOGE50-Lauf das Ende von
32.469,39 auf 30.901,33 USDC. Umgekehrt erzielt die aktuelle Definition im neueren
Fenster mit dem alten höheren Budget 22.655,77 statt 21.558,10 USDC. Der
Budgetunterschied erklärt daher einen Teil, aber nicht den Großteil des Sprungs.

## Startpunkt und Wiederanlage

Die Fenster sind um **11 Tage 18 Stunden** verschoben, nicht um mehrere Monate.
Dabei werden sowohl frühe Tage entfernt als auch neue späte Tage ergänzt.
Jeder neue historische Produktlauf startet in Cash und übernimmt keine vor
seinem Berichtsstart eröffneten Positionen.

Der alte Lauf kaufte BTC und SOL am **16.10.2023 06:00 UTC**. SOL blieb bis zum
26.12.2023 im Portfolio; der ausgewiesene Trade gewann etwa **367,56 %** bzw.
**1.995,14 USDC**. Am neuen Startpunkt 23.10.2023 war das alte laufende Konto
bereits investiert und rund 1.308,20 USDC wert. Ein neuer, leer startender Lauf
befindet sich in einem anderen Zustand und kann diesen bestehenden Trade nicht
einfach übernehmen. Die Kapitalbasis, spätere Allokationen, Signalkonkurrenz und
gegebenenfalls erreichte Diversifikationsschwellen verändern den gesamten
anschließenden Wiederanlagepfad. Der gesamte Endwertunterschied darf nicht allein
diesem einen Trade oder den letzten hinzugekommenen Tagen zugerechnet werden.

Eine zusätzliche native Fortsetzung isoliert die Endtage: gleicher alter
Startpunkt, gleiche aktuelle Definition und gleicher Vergleichsseed, aber
Fortführung bis zum neuen Ende. Dieser ausdrücklich als Diagnose gekennzeichnete
Lauf ist **drei Jahre plus 282 Stunden** lang, kein Produkt-Dreijahresbericht.
Sein Wert am alten Endpunkt ist exakt 33.777,01368032555 USDC und am neuen
Endpunkt 31.363,63446002421 USDC.

Damit ergibt sich für diese festgelegte Vergleichsreihenfolge:

| Schritt | End-USDC | Änderung zum vorigen Schritt |
| --- | ---: | ---: |
| Original DOGE50, alter Seed, altes Fenster | 32.469,39 | — |
| Gleiche alte Regeln mit gemeinsamem kleinerem Seed | 30.901,33 | −1.568,05 |
| Aktuelle Regeln, gleiches altes Fenster/Seed | 33.777,01 | +2.875,68 |
| Fortsetzung dieses Kontos bis zum neuen Enddatum | 31.363,63 | −2.413,38 |
| Neuer leerer Start am neuen Dreijahresbeginn | 21.558,10 | −9.805,53 |

Die zusätzliche jüngste Marktphase kostet auf dieser fortgeführten Kurve also
etwa 2.413 USDC. Die rund 9.806 USDC danach entstehen durch den anderen
Start-/Indikator-/Positions- und Wiederanlagepfad, nicht als realisierter
zusätzlicher Monatsverlust desselben Kontos. Das ist eine deterministische
Zerlegung entlang dieser Reihenfolge, keine eindeutige allgemeine Zuschreibung
interagierender Strategieeffekte. Im neueren Produktlauf liegt das simulierte
Maximum bei 28.331,75 USDC, unter 32.000. Die dauerhafte Dreicoin-Stufe wird
dort nicht erreicht; bis zu drei Positionen stammen aus der DD10-Aufteilung.

## Die aktuellen Paper-Verluste

Unveränderliche Journalprüfung vom 24.10.2026 19:30 UTC, am 25.10.2026 07:40 UTC
lesend auf unveränderte 14 Fills und null offene Paper-Positionen geprüft:

- Sieben geschlossene Zyklen, alle negativ. Einer ist ein ausdrücklich
  erzwungener alter Strategiewechsel; sechs sind reguläre Strategiezyklen.
- Alle 13 regulären Fills haben die nativ erneut berechneten Original-Signal-IDs,
  nächsten Kerzen-Open und modellierten Kosten. Alle sechs regulären Ausstiege
  liegen am ersten gültigen Strategie-Ausstieg; kein früher ignoriertes
  reguläres Exit-Signal wurde gefunden.
- Die regulären Verluste betreffen dreimal NEAR, zweimal BCH und einmal XRP.
  Die Einstiege stammen aus älteren erhaltenen Versionen. Ein separater kausaler
  Diagnose-Replay mit der aktuellen Definition seit dem 14.10. erzeugt ebenfalls
  sechs Verlustzyklen und etwa **−8,42 %**. Seine Endbewertung unterscheidet sich
  zum gleichen geschlossenen Preisstand nur um rund **0,034 USDC** vom laufenden
  Konto. Das ist ein Segmenttest mit fortgesetztem Indikatorpräfix, kein neuer
  unveränderter Drei-Jahres-Produktbericht.
- Paper-Equity am 25.10. 07:40 UTC: rund **972,36 USDC** gegenüber ursprünglich
  1.092,06 USDC. Sie umfasst verbleibenden Dust; freier Cash ist rund 971,04 USDC.
  Der Gesamtverlust von rund 10,96 % enthält den alten Strategiewechsel.

Internetbedingte Verarbeitungsverzögerungen werden separat dokumentiert. Sie
werden hier nicht erneut als falsche Strategie-Ausstiegsformel gezählt. Eine
nachträglich zum historischen Open fortgesetzte Paper-Simulation beweist trotzdem
keine rückwirkend zu diesem Preis mögliche reale Binance-Ausführung.

Auch im positiven Drei-Jahresbericht sind **81 von 154 Zyklen negativ** und
**16 von 37 berichteten Kalendermonaten** negativ; Randmonate sind teilweise.
Der Gesamtgewinn entsteht durch größere Gewinner, nicht durch fast durchgehend
positive Trades. Die starke Abhängigkeit von Einstiegsepisoden bleibt ein
Robustheitsrisiko. Der alte Betrag ist kein verlässliches Drei-Jahres-Ziel und
ein historischer Drawdown keine feste zukünftige Verlustgrenze.

## Gemeinsamer Vertrag und gezielte Reparaturen

Regulärer Auto-Backtest, Paper und normales Live verwenden dieselben zentralen
Indikator-, Filter-, Ranking-, Kapital-, Allokations- und Risikoregeln. Gleichheit
der Regeln setzt für gleiche Entscheidungen auch gleiche Eingangs- und
Kontozustände voraus. Unterschiedliche Anfangspositionen, Gebühren, verfügbare
Mittel und echte Teilausführungen können unterschiedliche Kontoverläufe erzeugen.
Der 50-USDC-Test ist ein einzelner technischer Signal-/Roundtriptest mit festem
Budget und eigenem Positionsbuch; er belegt nicht allein die volle spätere
Portfolioallokation. Alte echte Positionen behalten ihren eingefrorenen Vertrag.

Ein echter bedingter Unterschied wurde im **manuellen** Budgetmodus gefunden:
Nach einem Verlust kann Paper/Backtest den verbliebenen Cash statt einer vollen
Tranche investieren. Live reservierte bisher die volle Tranche und blockierte
sie erst bei der Kontoprüfung. Die Reparatur begrenzt bereits die Reservierung
auf verfügbaren Cash. Das eingefrorene Signalbudget, dessen Maximalgrenze,
Börsenfilter und frischer Kontenabgleich bleiben verbindlich. Ein unabhängiger
Drei-Modi-Test prüft den Fall 500-USDC-Tranche, Verkaufserlös 485, neuer Kauf 485
auch über Controller-Neustarts. Manipulierte Budgets bleiben gesperrt.

Dieser Fehler ist im aktuell verwendeten Automatikmodus inaktiv und erklärt
die 32k/21k-Differenz nicht. Die ausführbaren Strategieparameter bleiben unverändert.
Neue Berichte speichern außerdem Kapitalbewertungsbasis, DD10-Aufteilung und
Diversifikationsplan vollständig aus dem gemeinsamen Konfigurationsvertrag.
Bestehende Originalberichte werden nicht umgeschrieben.

## Reproduktionsnachweise

Private lokale, nicht veröffentlichte Rohdaten liegen unter
`research/anchor-comparison-20261024/`: Originalmanifeste/-metriken,
`Anchor-Retrieval.json`, zwei komprimierte Kerzensnapshots,
`Snapshot-Overlap.json`, `Comparison-Contract.json`, `Comparison-Results.json`
und alle Fills/Trades je Kontrolllauf. Die Paper- und Echtgeld-Einzelaudits liegen
separat unter `research/trade-parity-audit-20261024/`.
Schlüssel, Kontojournale und private Einstellungen gehören nicht ins Git-Archiv.

Der Forschungsstart bindet den Gesamtquellfingerprint
`4a5858480c93f066e18e88c452db9f16fd272bbdce8ff6835f5ac8394b3b4318`
von Commit `e474c46`. Während der Forschung wurden die hier beschriebenen
Manual-Live-/Reportingreparaturen geschrieben; deshalb schlug die abschließende
globale Unverändertheitsassertion erwartungsgemäß fehl. Die Teilresultate werden
nicht als unveränderter Gesamt-Head-Test ausgegeben. Die maßgeblichen nativen
Backtest-/Domain-Dateien sind separat gegen den Startcommit hashgebunden und
unverändert; `Source-Binding-Limitation.json` dokumentiert diese Abgrenzung.
Die Regression und unabhängigen Reviews des Reparaturcommits sind davon getrennt.
