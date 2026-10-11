# Hixton: operative Priorität Spot-only, 11.10.2026

Diese Entscheidung des Besitzers **ersetzt** die frühere Hebel-/Margin-Forschungspriorität in `VISION_AND_ACCEPTANCE_20261011.md`, ohne historische Untersuchungen oder Belege zu löschen.

## Jetzt verbindlich
- **Kein Hebel, keine Derivate, keine Margin-Kredite:** Normaler Binance **Spot-Long 1×** ist die alleinige Zielausführung. Entsprechende Hebel-/Margin-Arbeit wird **pausiert** (GitHub Issue #12). Keine gehebelten UI-Versprechen, API-Berechtigungen oder simulierten Renditen als Release-Kriterium.
- Der **bestehende, langlebige V8-Standardbot** soll **innerhalb von 15 beobachteten USDC-Coins** in Ertrag und Verlustfilterung verbessert werden. 15 ist ein Beobachtungsuniversum, keine Pflicht zu 15 parallel eröffneten Positionen.
- **Gesamtkapital zuerst ca. 1.000–1.100 USDC**, Gewinne und Verluste werden im selben gemeinsamen Portfolio reinvestiert: Equity 1.100 → 1.200 heißt 1.200 USDC **Gesamtbudget**, nicht 1.200 pro Position; 1–N Trades nur bis tatsächlich freie Quote reicht. Keine Überschreitung von 100 % Spot-Eigenkapital.
- **Aktive Platzfüller:** NEAR, AAVE, BCH; SUI/UNI nur Research. Alle Füller auf marginalen Nettoeffekt, Kostenstress, drawdown und maximalen **Abstand zwischen Einstiegen** prüfen. Profitabler Einzeltrade bedeutet nicht, dass der Füller im Portfolio nützt; rückblickender Verlust bedeutet nicht, dass alle künftigen Signale negativ werden.
- Der Nutzer bevorzugt **spürbar aktiven Handel**, erlaubt moderat geringere Einzeltrade-Erfolgsaussichten, verlangt aber positiven erwarteten Gesamtportfolioertrag. **Keine erzwungenen Trades** oder Garantie eines Mindestintervalls.
- Statt maximaler historischem Endwert allein: Robustheit gegen Overfitting, Negativjahr, tägliche Verluste, Fees, slippage, Worst Idle Gap, falsche Entry-Signale.
- Exakter Referenzzeitraum 2023-10-10 bis 2026-10-10 bereits mehrfach untersucht. Daher **nicht** als unberührte OOS-Periode ausgeben; neue strategische Änderungen benötigen Walk-Forward und echten neuen Forward-/Paper-Holdout.
- **Nicht im Live-Produkt aktiviert:** Das Flag `auto_budget_enabled` ist derzeit eine persistierte, fail-closed Forschungsvormerkung. Bestehende 50-USDC-Trial- und Live-Enable-Freigaben und aktuelle V8-Ausführung bleiben unverändert, bis Backtest/Paper/Live-Parität geprüft ist.

## Nachweise und nächste Forschung
- Reproduzierter 1100-USDC-Spot-Compound-Referenzlauf: https://github.com/127027/Der-Hixton-von-GPT/actions/runs/38127386550
- Filler-/Tradeaktivitätsablation inklusive 1000-USDC-Budget, Core-/Satellitenfilter, Normal-/Stresskosten: https://github.com/127027/Der-Hixton-von-GPT/actions/runs/38135412643
- Ziel/A01–A11-Governance: https://github.com/127027/Der-Hixton-von-GPT/issues/13
- Forschung bleibt auf getrennten Branches ohne automatische Promotion, Echtgeldorders oder Entsperrung des Live-Modus.
