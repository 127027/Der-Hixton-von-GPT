# Schutzregeln: Vergleich auf den letzten drei Jahren · 26.10.2026

**Entscheidung: NO_CHANGE. Keine neue Handelsregel übernommen.**

Acht vorab festgelegte Varianten des aktuellen Bots auf denselben15Marktreihen, demselben Zeitraum26.10.2023–26.10.2026 und gemeinsamem Vergleichsstartkapital1.085,77093944USDC mit Wiederanlage. NormaleKosten, Kostenstress und eine ausdrücklich unkalibrierte Liquiditätskosten-Sensitivität werden getrennt verglichen.

- [Entscheidung, Tradeoffs und Erklärung der neuen Baseline](Einordnung.md)
- [Alle Ergebnisse, Auswahl und Grenzen](Bericht.md)
- [Alle Vergleichswerte](Comparison.csv) und [Equity-/Drawdown-Diagramm](Vergleich.png)
- [Vorabvertrag](Study-Contract.json), [mechanische Auswahl](Selection.json), [Ergebnisübersicht](Summary.json)
- [Öffentliche abgeleitete Simulationsspezifikation](Simulation-Spezifikation.json)
- [Methodenquellen](Methoden-Code.zip), [ausdrücklicher nativer Researchdiff](Native-Overlay.diff), [Dateibindung](Public-Evidence.json)

Die Baseline wurde gegen den unveränderten nativen Engine vollständig identisch geprüft ([normal](Native-Parity-current.json), [Stress](Native-Parity-stress.json)). Forschungsregeln sind kein bereits eingebauter Livevertrag. Die5%-Schwelle ist keine garantierte Verlustobergrenze. Historische Proxykerzen, heutige Exchangefilter und fehlende historische Orderbücher begrenzen die Aussage. Der Startbetrag wurde ausdrücklich als zuletzt bestätigter Vergleichsseed gewählt, nicht als frischer Kontostand.

Originale große Marktdatensätze, Ausführungskurven und private Statusdaten bleiben lokal; ihre Originalhashes sind gebunden. Keine Schlüssel, Passwörter oder Live-/Neustartänderungen.
