# Auswahl und gemeinsamer aktueller Regelstand

Ausdrückliche Eigentümervorgabe vom 21.10.2026: Bei der Auswahl geprüfter,
technisch zulässiger Varianten steht der höchste Netto-Portfoliogewinn an erster
Stelle, der niedrigere maximale Drawdown an zweiter. Ein gewichteter Score darf
diese Reihenfolge nicht stillschweigend ersetzen. Einzelcoin-Diagnosen sind keine
zusätzlichen gemeinsamen Portfolios und bestimmen nicht isoliert den Gewinner.

Ein Vergleich friert für alle Kandidaten dieselben 15 Marktdaten-Snapshots,
denselben Zeitraum, dasselbe Startkapital, dieselbe Wiederanlage, Börsenfilter und
Kosten ein. Im automatischen Produkt-Portfolio stammt das Startkapital aus einem
frischen Binance-USDC-Snapshot. Ein höherer alter Endbetrag aus einem anderen
Zeitfenster belegt keine bessere aktuelle Einstellung. Beste geprüfte Variante
bedeutet keine garantierte optimale zukünftige Einstellung.

Backtest, Paper, neuer ausdrücklich gestarteter 50-USDC-Test und normales Live
verwenden denselben aktiven Strategie-, Policy-, Allocator- und Risikostand. Eine
Regeländerung muss in allen betroffenen Pfaden übernommen und mit Paritäts- und
Regressionsprüfungen belegt werden. Es darf keine nur für Backtests optimierte
oder nur für Live abweichende Gewinnvariante geben. Alte offene echte Positionen
behalten ihren ursprünglichen eingefrorenen Ausstiegsvertrag; dessen Bericht und
Abnahme werden nicht auf neue Regeln umgeschrieben.

Aktuelle Berichte sind an Quellfingerprint, Strategie, Einstellungen, Startkapital
und Testfenster gebunden. Abweichende oder unbelegte Berichte bleiben historische
Nachweise und dürfen nicht als aktueller Zustand angezeigt werden. Eine frische
historische Simulation startet in Cash und führt den aktuellen Regelstand kausal
durch die letzten drei Jahre; sie ist keine identische Wiedergabe des fortlaufenden
heutigen Kontos mitsamt seinen bestehenden Positionen oder Ausfällen.

Ausführungsqualität, Kosten-/Stressprüfungen, Datenqualität, Kontenabgleich und
ausdrückliche Aktivierung bleiben Voraussetzung. Gewinnpriorität erlaubt weder
Zukunftsdaten noch das Abschalten dieser Prüfungen. Gleichheit der Regeln bedeutet
keine garantierte Gleichheit realer Fillpreise, Latenzen, Gebühren oder Gewinne.
Eine historische Drawdown-Zahl ist keine fest zugesicherte Verlustobergrenze.

Diese Festlegung ändert keine ausführbare Handelsregel, aktiviert keinen Test und
kein Live und benötigt keinen Bot-Neustart. Der gültige aktive Stand bleibt aus
dem Code und den aktuellen, dazu passenden Berichten abzuleiten.
