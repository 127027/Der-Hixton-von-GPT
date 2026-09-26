# 17 – Glossar

Status: CURRENT · 26.09.2026

- **V6:** einzige aktuelle Produktstrategie mit zehn Coin-Profilen.
- **USDC:** operative Quote der zehn Binance-Spot-Märkte.
- **max_capital_usdc:** einzige aktuelle Kapitalvorgabe für Portfolio-Backtest, Paper und normalen Livebetrieb.
- **CAPITAL-V1-2X50PCT:** aktueller Allocator; zwei `ranked_repeat`-Tranchen zu je 50 % des Maximalbudgets, standardmäßig 250 USDC → 2×125.
- **1×50-USDC-Test:** separater kontrollierter erster Echtgeld-Roundtrip; ändert `max_capital_usdc` nicht.
- **3×80:** historisches früheres Portfolio-/Forschungsmodell; keine aktuelle Produktkapitalquelle.
- **10×250:** zehn isolierte Diagnosekonten à 250 USDC.
- **ranked_repeat:** Slotregel; freie Slots können nach Ranking erneut an einen bereits ausgewählten gültigen Kandidaten gehen.
- **Positionszyklus:** ein Entry-bis-Exit-Lebenszyklus eines Coins; kann mehrere Slots tragen.
- **Slot-Trade:** belegte Kapitaltranche; nicht mit einem zusätzlichen Signal gleichzusetzen.
- **Baseline:** normales modelliertes Kostenprofil.
- **Stress:** ungünstigeres modelliertes Kostenprofil.
- **Top-K:** im Training eingefrorene Kandidatenliste.
- **Validation:** getrenntes Ablehnungsfenster, nicht zur Nachoptimierung.
- **Paper:** simuliertes Geld/Fills auf echten öffentlichen Marktpreisen.
- **Strategy activation:** expliziter auditierter Wechsel der persistenten Paper-Strategieversion ohne stillen Kontoreset.
- **QA_PASS / GOVERNANCE_PASS:** unabhängige A09-/A11-Freigaben für den geprüften Commit.
