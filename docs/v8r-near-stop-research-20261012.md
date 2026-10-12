# V8r-Backtestprüfung und NEAR-Stop-Untersuchung — 12.10.2026

Ergebnis: Der V8r-Backtestpfad wurde korrigiert. Die registrierte neue Strategie muss denselben Produktpfad wie V8 verwenden: 15 Märkte, historische Datenkontinuität, gespeicherte Automatik-Einstellungen, aktuelles freies Binance-USDC als Startkapital beim Produkt-Portfolio-Test und gemeinsame Positionsgrößenregel. Zuvor fehlte die neue Kennung in mehreren Whitelists und Aufrufen.

Die vier zusätzlichen NEAR-Stopvarianten wurden nicht aktiviert. Der nach Trainingsjahren gewählte 6-ATR-Stop änderte keine Ausführung und verfehlte die Drawdown-Abnahme. Engere Varianten senkten teilweise den Drawdown des letzten Jahres, verschlechterten aber die Ergebnisse im vollständigen Zeitraum. Es wurde nicht nachträglich der hübscheste Endwert als Sieger gewählt.

Fester Vergleich: 11.10.2023 19:00 UTC bis 11.10.2026 19:00 UTC; Start 1.092,05773944 USDC; zwei Slots; Wiederanlage; identische Daten und Kosten je Vergleich. Historie bereits untersucht, kein unberührter Holdout. Ältere fehlende USDC-Daten verwenden dokumentierte USDT-Preisproxies; keine bewiesene historische USDC-Liquidität. Drawdown anhand stündlicher Schlusswerte.

| Variante | Ende normal | DD normal | Ende Stress | DD Stress |
|---|---:|---:|---:|---:|
| original_v8 | 28922.29 | 47.63% | 17491.55 | 60.76% |
| baseline | 29459.95 | 41.81% | 20803.15 | 50.75% |
| stop2 | 27651.77 | 42.14% | 19697.27 | 51.14% |
| stop3 | 28925.75 | 42.24% | 20372.99 | 50.72% |
| stop4 | 28938.15 | 42.46% | 19872.96 | 52.52% |
| stop6 | 29459.95 | 41.81% | 20803.15 | 50.75% |

Im letzten Jahr blieb V8r unter Stresskosten bei -9,78% Rendite. Auch Stop 2/3/4 blieb mit etwa -8,91%/-8,51%/-9,38% negativ. Dies ist kein Beleg dauerhafter Profitabilität.

Prüfung: 34 native Portfolio-Läufe (10 Trainingsläufe, 12 volle Läufe, 12 letzte-Jahr-Läufe). Auswahl vor den abschließenden Läufen gespeichert. Original V8 und aktive V8r reproduzieren ihre bisherigen normalen/stressbedingten Vollzeit-Kennzahlen. Kein privater API-Zugriff, keine echten/testnet Orders und keine Aktivierung der Varianten durch diese Forschung.

Codeprüfung: 584 Regressionstests bestanden, 2 optional übersprungen. Nach der abschließenden CLI-Auswahlkorrektur zusätzlich 23 gezielte Produkt-/CLI-Tests bestanden. Ruff und MyPy (69 Quellmodule) bestanden. Die tatsächliche registrierte V8r ist jetzt in Paper-/Backtest-Paritätsprüfungen mit und ohne Wiederanlage enthalten. Der offene alte Echtgeldtest bleibt unverändert unter seiner eingefrorenen V8; keine neue Live-Abnahme behauptet.
