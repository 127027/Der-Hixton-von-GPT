# 04 – Markt, Kapital und Risiko

Status: CURRENT · 25.09.2026

Quote-Asset ist USDC. Das Produkt besitzt ein gemeinsames Maximalbudget `max_capital_usdc`; Standard 250 USDC. Der zentrale Allocator `CAPITAL-V1-2X50PCT` leitet aktuell zwei ranked_repeat-Tranchen zu je 50 % ab. Bei 250 USDC sind das 2 × 125 USDC.

ranked_repeat kann freie Tranchen auf dasselbe aktuell stärkste gültige Signal verteilen. Kein Coin wird aufgrund vergangener Drei-Jahres-Performance dauerhaft bevorzugt.

10×250 USDC sind reine Coin-Diagnose/Forschung: zehn getrennte 250-USDC-Konten. Sie sind keine Live-Kapitalquelle.

Sicherheitsgates:
- Cash-/Slotprüfung;
- maximaler gebundener Betrag aus dem zentralen Kapitalplan;
- 5-%-UTC-Tagesverlustpause;
- Not-/Einstiegssperre;
- Daten- und Exchange-Filter;
- Konto-/Order-Reconciliation im Livebetrieb.

Für die aktive V6 gilt: **kein permanenter Portfolio-Drawdown-Halt**. Drawdown wird gemessen und in Backtests/Stressauswertung berichtet.
