# 18 – Backteststatus und Ergebnisformat

Status: CURRENT · 06.10.2026

Der aktuelle Produktnachweis wird frisch auf dem exakten Release-Commit erzeugt. Historische Ergebniswerte sind keine unveränderliche Zukunftsreferenz.

Aktuelle Modelle:
- **V6 Core:** eingefrorener Zehn-Coin-Regressionsanker;
- **V8 15×250 isoliert:** Forschungs-/Diagnoselabor, je Coin ein separates 250-USDC-Konto;
- **V8 Shared-Maximalbudget:** Produktmodell, ein gemeinsames Kapital X über `CAPITAL-V1-2X50PCT` = zwei Slots zu X/2;
- Shared Satellites: nur NEAR/BCH aktiv, ausschließlich in komplettem Core-Idle; SUI/UNI/AAVE research-only.

Jeder Produktlauf dokumentiert mindestens: Strategie-/Profilhash, Quellcommit, Datenfenster und Warmup, Datenprovenienz, Kostenmodell, Maximalbudget, abgeleitete Slotgröße, Endkapital/PnL, Positionszyklen, Slot-Trades, Drawdown, Idle-/Occupancy-Metriken und Core/Satellite-Beiträge.

Methodik:
- Reportende = letzte vollständig geschlossene UTC-Stunde;
- Reportstart = exakt drei Kalenderjahre davor;
- 400 1h-Bars davor dienen nur als Warmup;
- Signal-/Filter-/Exitentscheidung nur auf bereits geschlossenen Bars;
- Ausführung am nächsten verfügbaren Open;
- Training darf Kandidaten vorschlagen; Validation/Holdout darf ablehnen, aber darf Runtime-Entscheidungen nicht nachträglich steuern.

Simulationen sind ausdrücklich keine Binance-Ausführungs- oder Zukunftsnachweise. Releasefähig ist nur ein exakter Commit mit grüner Integration, UI-/Runtime-Parität, vollständiger Regression, A09 QA_PASS und A11 GOVERNANCE_PASS.
