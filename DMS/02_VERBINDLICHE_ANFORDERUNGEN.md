# 02 – Verbindliche Anforderungen

Status: CURRENT · 25.09.2026

- Universum: BTCUSDC, ETHUSDC, BNBUSDC, SOLUSDC, XRPUSDC, ADAUSDC, LINKUSDC, AVAXUSDC, DOTUSDC und DOGEUSDC.
- Normale Produktpfade verwenden ausschließlich die kanonische V6 aus `src/hixton/domain/versions.py`.
- Entscheidungen entstehen auf abgeschlossenen 1h-Kerzen; Warm-up: 400 Bars.
- Die einzige editierbare Kapitalvorgabe ist das **Maximalbudget** `max_capital_usdc`.
- Aktuell validierter Bereich: 100 bis 1.000 USDC; Standard: 250 USDC.
- `CAPITAL-V1-2X50PCT` leitet daraus **2 × 50 %** ranked-repeat-Tranchen ab. 250 USDC ergeben 2 × 125 USDC.
- Slotzahl, Tranchengröße und Reserve sind abgeleitete Werte und keine zweite Benutzerkonfiguration.
- Portfolio-Backtest, Paper und normaler Livebetrieb müssen denselben `capital_plan(max_capital_usdc)` verwenden.
- 10×250 USDC isoliert ist ausschließlich Diagnose-/Coin-Optimierungsforschung.
- Coin-Forschung darf Kandidaten nicht direkt auf dem Portfolio optimieren; das kanonische Maximalbudget-Portfolio ist nur nachgelagertes Non-Regression-Gate.
- Es gibt keinen fest verdrahteten Gewinner-Coin. Freie Tranchen werden anhand der aktuellen gültigen Signale/ranked_repeat vergeben.
- Die 5-%-UTC-Tagesverlustpause, Not-Aus, Daten-, Cash- und Exchange-Gates bleiben aktiv.
- Cloud/CI/A01–A11 bleiben key-free und senden keine Echtgeld-/Testnet-Orders.
- Erster lokaler Echtgeldschritt bleibt **1×50 USDC** als separater Einmaltest; das gespeicherte Maximalbudget wird dafür nicht auf 50 geändert.
- Dauer-Live ist erst nach vollständig reconciliertem 1×50-Roundtrip und allen Runtime-Gates zulässig und verwendet anschließend das gespeicherte Maximalbudget.
- Live nutzt ausschließlich Binance Spot USDC; Withdrawal, Transfer, Margin, Futures und Optionen müssen deaktiviert sein.
