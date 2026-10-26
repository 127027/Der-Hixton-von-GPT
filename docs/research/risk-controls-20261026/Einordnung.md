# Entscheidung und Einordnung · 26.10.2026

**Keine der geprüften Änderungen belegt hier mehr Sicherheit bei mindestens gleichem Endkapital unter allen drei vorab festgelegten Ausführungsannahmen. Die Handelsregeln bleiben unverändert.**

Der automatische Ausstieg nach 5 % Tagesverlust reduziert das normale Endkapital von 11.004,18 auf 3.642,60 USDC, der zusätzliche 24-Stunden-Abstand auf 3.446,47 USDC. Der maximale Schlusskurs-Drawdown sinkt dabei nur von 38,23 auf 37,25 bzw. 36,86 %. Das ist in diesem Zeitraum ein hoher Renditeverzicht für wenig Verbesserung dieses Risikomaßes. Eine Verkleinerung neuer Positionen bei steigendem Drawdown erreicht 7.155,98 USDC bei 30,36 % DD. Alle kombinierten Änderungen erreichen 3.155,48 USDC bei 32,40 % DD. Eine 5-%-Schwelle ist weiterhin kein garantierter Verlustdeckel.

## Kleine Mehrgewinne sind kein technischer Fehler

Die 24-Stunden-Pause eines Coins nach einem abgeschlossenen Verlusttrade erzielt etwas mehr Endkapital: normal +127,5345 USDC, unter Kostenstress +100,4173 USDC und unter der zusätzlichen Impact-Annahme +108,0069 USDC. Ihr Drawdown ist jedoch ebenfalls leicht größer: +0,000247751548, +0,002480847576 bzw. +0,012990351469 Prozentpunkte. In einer Tabelle mit nur zwei Nachkommastellen ist das teilweise nicht sichtbar.

Diese Variante ist nicht pauschal schlechter und nicht technisch fehlerhaft. Sie scheitert am **vor der ersten Ergebnisbeobachtung festgelegten, exakten Nichtregressionskriterium** der vorliegenden Schutzstudie. Es gibt keinen belegten kostenlosen Sicherheitsgewinn. Die Schwelle wird nach Kenntnis der Ergebnisse nicht nachträglich gelockert, und die kleine Differenz wird nicht zu einem großen Risiko umgedeutet. Die Gewinnpriorität bleibt die Rangfolge innerhalb der vorab festgelegten zulässigen Menge; die zusätzlichen Nichtregressionskriterien dieser Schutzstudie sind im Vertrag ausdrücklich ausgewiesen und kein allgemeiner neuer gewichteter Gewinn/DD-Score.

## Warum die neue Baseline 11.004 statt etwa 21.558 USDC beträgt

Die Differenz wurde mit **unveränderter nativer Strategie** in zusätzlichen eng begrenzten Baselinekontrollen zerlegt. Diese Kontrollen verändern weder Kandidaten noch Auswahl.

| Native Kontrolle | End-USDC | Änderung gegenüber vorheriger Zeile |
|---|---:|---:|
| Alter Stichtag 23.10.2026, alter Startbetrag 1.039,26093944 USDC | 21.558,10 | Referenz |
| Gleicher Zeitraum, gewählter Vergleichsstartbetrag 1.085,77093944 USDC | 22.526,13 | +968,02 |
| Zusätzlich heutige einheitliche Exchangefilter | 22.526,13 | 0,00 |
| Alter Start bleibt bestehen; Simulation läuft bis 26.10.2026 weiter | 21.793,40 | −732,73 |
| Neuer flacher Start am 26.10.2023 mit zugehörigem 400h-Vorlauf | 11.004,18 | −10.789,22 |

Alle **399.465 überlappenden Kerzen** stimmen in sämtlichen gespeicherten Feldern überein. Der alte Lauf wurde mit allen ursprünglichen Fills und Trades exakt reproduziert. Die bis zum alten Ende reichenden Kontokurven bleiben beim bloßen Weiterlaufen ebenfalls exakt gleich. Der Unterschied entsteht damit nicht durch veränderte historische Kurse oder eine heimlich ausgetauschte Strategie.

Ein konkreter früher Auslöser ist AVAX: Der alte Lauf kauft am **26.10.2023 um 08:00 UTC**, sechs Stunden vor dem neuen Berichtsbeginn, und verkauft am 18.01.2024 mit **+188,92 %** realisiertem Tradeergebnis. Die frisch zu ihrem eigenen Stichtag ohne Positionen gestartete Simulation besitzt diesen Kauf nicht. Zusätzlich verändert der verschobene 400-Stunden-Vorlauf die rekursive Indikator-/Trendinitialisierung: im alten Präfix entsteht dort ein frisches UP-Signal, im neuen Präfix besteht der UP-Trend bereits während des Vorlaufs. Der Bot erfindet beim neuen Berichtsstart keinen zurückliegenden Kauf.

Die **−10.789,22 USDC sind der gemeinsame Effekt des späteren flachen Starts samt neuer Initialisierung und anschließendem Kapitalpfad**, nicht der nachgewiesene isolierte Verlustbeitrag eines einzigen AVAX-Trades. Später werden dadurch auch identische Signale anders groß gehandelt. Beispielsweise realisiert derselbe AVAX-Zyklus vom 15.08. bis 08.10.2026 im alten Startpfad 8.016,50 und im neuen Startpfad 4.043,86 USDC.

**Das ist eine erhebliche Startempfindlichkeit des historischen Ergebnisses. Weder 11.000 noch 21.000 oder frühere 32.000 USDC sind dadurch eine belastbare zukünftige Gewinnerwartung.** Es handelt sich um unterschiedliche simulierte Kapitalpfade, nicht um einen entsprechenden tatsächlichen Geldverlust des Benutzers.

## Was fertig ist und was unverändert bleibt

- 24 vorab festgelegte Hauptfälle, zwei vollständige Original-vs-Overlay-Kontrollen und vier zusätzliche native Baselinekontrollen sind abgeschlossen.
- Die unabhängige Zahlenprüfung umfasst alle 631.296 gespeicherten Hauptfall-Stundenwerte, 8.498 Fills und 144 Artefakthashes. Die Geldrekonstruktion weicht um null ab. Vorab bestanden 47 A09-Grenzfälle und acht separate A11-Auswahl-/Freezefälle.
- Weil die unveränderte Baseline nach dem eingefrorenen Schutzstudienkriterium ausgewählt wurde, wird keine Ersatzvariante durch weitere Parametersuche oder bekannte Fünfjahrespfade gerettet. Es wurde keine neue profitable oder sicherere Strategie behauptet.
- Backtest, Paper, 50-USDC-Test und Live behalten ihren bisherigen gemeinsamen Vertrag. Keine Order, kein Neustart, keine Schlüsseländerung und keine Liveaktivierung durch diese Arbeit.
- Die zusätzlichen Impactkosten sind unkalibrierte Sensitivitätsannahmen. Historische USDT-Proxyumsätze ersetzen kein damaliges USDC-Orderbuch. Vollständige Ausfall-/Teilfillrisiken sind dadurch nicht nachträglich historisch simuliert.

Die eingefrorene Hauptfallauswahl steht in `Selection.json`; die ursprünglichen lokalen Zusatzbelege sind an `Rolling-Control-Evidence.json` gebunden. Private Kontostatusdaten und die großen Rohdatensätze bleiben lokal.
