# 02 – Verbindliche Anforderungen

Status: CURRENT · 25.09.2026

- Universum: BTCUSDC, ETHUSDC, BNBUSDC, SOLUSDC, XRPUSDC, ADAUSDC, LINKUSDC, AVAXUSDC, DOTUSDC und DOGEUSDC.
- Normale Produktpfade verwenden ausschließlich die kanonische V6 aus `src/hixton/domain/versions.py`.
- Entscheidungen entstehen auf abgeschlossenen 1h-Kerzen; Warm-up: 400 Bars.
- Die einzige editierbare Kapitalvorgabe ist das **Maximalbudget** `max_capital_usdc`.
- Konfigurierbarer Produktbereich: 100 bis 1.000.000 USDC; Standard: 250 USDC. 1.000 USDC bleibt die bisherige historische Forschungsreferenz für die Kapitalhöhe; höhere Budgets sind keine Backtest-Liquiditätsgarantie.
- `CAPITAL-V1-2X50PCT` leitet daraus **2 × 50 %** ranked-repeat-Tranchen ab. 250 USDC ergeben 2 × 125 USDC.
- Slotzahl, Tranchengröße und Reserve sind abgeleitete Werte und keine zweite Benutzerkonfiguration.
- Portfolio-Backtest, Paper und normaler Livebetrieb müssen denselben `capital_plan(max_capital_usdc)` verwenden.
- 10×250 USDC isoliert ist ausschließlich Diagnose-/Coin-Optimierungsforschung.
- Coin-Forschung darf Kandidaten nicht direkt auf dem Portfolio optimieren; das kanonische Maximalbudget-Portfolio ist nur nachgelagertes Non-Regression-Gate.
- Es gibt keinen fest verdrahteten Gewinner-Coin. Freie Tranchen werden anhand der aktuellen gültigen Signale/ranked_repeat vergeben.
- Es gibt **keinen permanenten Drawdown-Halt**; Drawdown-/Verlustschutz wird über die 5-%-UTC-Tagesverlustpause und die übrigen Runtime-Gates umgesetzt.
- Die 5-%-UTC-Tagesverlustpause, Not-Aus, Daten-, Cash- und Exchange-Gates bleiben aktiv.
- Cloud/CI/A01–A11 bleiben key-free und senden keine Echtgeld-/Testnet-Orders.
- Erster lokaler Echtgeldschritt bleibt **1×50 USDC** als separater Einmaltest; das gespeicherte Maximalbudget wird dafür nicht auf 50 geändert.
- Dauer-Live ist erst nach vollständig reconciliertem und auf Binance als Kauf+Verkauf bestätigtem 1×50-Roundtrip zulässig. Danach genügt die separate ausdrückliche Livefreigabe mit automatischer Konten-/API-/Marktdatenprüfung; ein Paper-Soak ist kein zusätzliches Echtgeld-Gate.
- Live nutzt ausschließlich Binance Spot USDC; Withdrawal, Transfer, Margin, Futures und Optionen müssen deaktiviert sein.
- Vorbestehende freie Spot-Bestände dürfen vorhanden sein. Sie werden als Konto-Baseline überwacht, nicht als Bot-Eigentum übernommen und dürfen von Hixton nicht verkauft werden; manuelle Bestandsänderungen während eines scharfen Echtgeldlaufs müssen den Abgleich fail-closed sperren.
- Trial und Live müssen die aktive Anwendungs-, Source-, Strategie- und Allocator-Identität persistent binden und im 24/7-Bericht gegen die aktuell laufende Version prüfen. Ein Source-Wechsel darf keine neuen Einstiege unter einem alten Patch erzeugen.
- Für Trial und Live muss ein lokaler, secret-freier Diagnosebericht Binance-Fills/Terminalzustände, Signal-zu-Order-Verzögerungen, vollständige Roundtrips, offene/ungeklärte Orders und Paper-vs-Live-Abweichungen enthalten.
