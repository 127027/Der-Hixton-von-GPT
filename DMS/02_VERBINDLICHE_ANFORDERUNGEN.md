# 02 – Verbindliche Anforderungen

Status: CURRENT · 21.09.2026

- Das aktive Universum umfasst BTCUSDC, ETHUSDC, BNBUSDC, SOLUSDC, XRPUSDC, ADAUSDC, LINKUSDC, AVAXUSDC, DOTUSDC und DOGEUSDC.
- Normale Produktpfade unterstützen ausschließlich die aktuelle V6.
- Die kanonische StrategyDefinition in src/hixton/domain/versions.py ist die einzige Quelle für V6-Version und Coin-Profile.
- Config darf die Profilmap oder den Digest nicht duplizieren.
- Strategiezeitrahmen ist 1h; Signale entstehen nur aus abgeschlossenen Kerzen.
- Das Hauptportfolio startet mit 250 USDC, drei 80-USDC-Slots und ranked_repeat.
- 10×250 USDC sind zehn isolierte Diagnosekonten.
- Mehrere Slots desselben Signals sind Kapitaltranchen eines Positionszyklus.
- Es gibt keinen permanenten Drawdown-Halt auf Portfolioebene.
- Die 5-%-UTC-Tagesverlustpause und technische Safety-Gates bleiben aktiv.
- Paper, Backtest und UI müssen dieselben Coin-Profile verwenden.
- Änderungen müssen Baseline und Stress bestehen; isolierte Coin-Verbesserung allein genügt nicht.
- Cloud, CI und A01–A11 bleiben key-free; dort sind Echtgeld- und Testnet-Orders strikt gesperrt.
- Der lokale Echtgeldpfad ist gestuft und fail-closed: erster Test ausschließlich 1×50 USDC nach expliziter Freigabe; keine sofortige Order, sondern Warten auf ein neues gültiges Signal.
- Dauer-Live ist ausschließlich das Hauptmodell 250 USDC / maximal drei 80-USDC-Slots / ranked_repeat und setzt einen vollständig abgeschlossenen und reconcilierten 1×50-Roundtrip voraus.
- Live nutzt Binance Spot USDC בלבד: keine Margin-, Futures-, Transfer-, Options- oder Withdrawal-Rechte.
