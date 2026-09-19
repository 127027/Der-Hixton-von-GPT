# 06 – Backtest und Validierung

Status: CURRENT · 19.09.2026

## Aktueller Validierungsvertrag 19.09.2026
Alle produktiven Backtests verwenden die aktuelle V6 und dieselben Parameter-/Policy-Hashes wie Paper.

Modelle:
- single: ein Coin, 250 USDC;
- all: 10×250 USDC isoliert;
- portfolio: 250 USDC gemeinsam, 3×80, ranked_repeat.

Optimierung:
1. begrenzter Kandidatenraum;
2. Ranking nur auf Training A/B;
3. Top-K einfrieren;
4. Validation Baseline/Stress;
5. vollständige Drei-Jahres-Baseline/Stress;
6. robuste Kandidaten einzeln im 3×80;
7. nur portfolio-kompatible Kandidaten kombinieren;
8. jede Addition erneut gegen den aktuellen Kombinationsstand prüfen;
9. final 10×250 und 3×80 Baseline/Stress müssen nicht regressieren.

Aktueller Forschungscheckpoint: Run 35463131378, 10×250 8.217,01 USDC, 3×80 1.217,91 USDC; Details in DMS 18 und backtests/v6/current-evidence.json.

Validation ist ein Gate, kein zweiter Optimierungsdatensatz.
