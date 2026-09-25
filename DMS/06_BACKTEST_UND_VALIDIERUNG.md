# 06 – Backtest und Validierung

Status: CURRENT · 25.09.2026

Alle Produktbacktests verwenden die aktuelle V6, dieselben Coin-Profile und denselben zentralen Kapitalplan wie Paper/Live.

Modelle:
- single: ein Coin, 250 USDC Forschungs-/Diagnoselauf;
- all: 10×250 USDC isoliert, ausschließlich Coin-Forschung;
- portfolio: gespeichertes **Maximalbudget**, standardmäßig 250 USDC, über `CAPITAL-V1-2X50PCT` aktuell 2 × 125 USDC ranked_repeat.

Jeder aktuelle Produktbacktest deckt exakt drei Kalenderjahre rückwärts vom Endzeitpunkt ab; 400 1h-Warm-up-Bars liegen davor und zählen nicht zum Performancefenster. Fehlende Historie führt fail-closed zum Fehler statt zu einem verkürzten Fenster.

Coin-Optimierung:
1. Kandidatenraum nur isoliert 10×250;
2. Ranking ausschließlich Training A/B;
3. Top-K einfrieren;
4. unabhängige Validation;
5. vollständige Drei-Jahres-Baseline/Stress;
6. robuste Kandidaten einzeln gegen das kanonische Maximalbudget-Portfolio;
7. nur portfolio-kompatible Kandidaten kombinieren;
8. final müssen isolierte Forschung und kanonisches Portfolio Baseline/Stress nicht regressieren.

Validation ist Gate, kein zweiter Optimierungsdatensatz. Historische Simulationen sind keine Zukunfts- oder Fillgarantie.
