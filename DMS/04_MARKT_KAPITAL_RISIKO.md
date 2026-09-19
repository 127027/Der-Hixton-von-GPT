# 04 – Markt, Kapital und Risiko

Status: CURRENT · 19.09.2026

Quote-Asset im Betrieb ist USDC. Das Hauptmodell verwendet 250 USDC Startkapital und 3×80 USDC. ranked_repeat kann freie Slots auf denselben besten gültigen Kandidaten verteilen.

10×250 USDC sind reine Coin-Diagnose: zehn getrennte 250-USDC-Konten.

Aktive Risikoregeln:
- 5-%-UTC-Tagesverlustpause für neue Entries;
- Not-Aus/Einstiegspause;
- Cash-/Slotprüfung;
- Binance-MinQty/Step/Tick/MinNotional;
- Stale-/Gap-/Datenqualitätsgates;
- XRP-spezifischer Close-Stop gemäß Profil.

Es gibt **kein permanenter Portfolio-Drawdown-Halt**. High-Water-Mark und Drawdown werden weiterhin berechnet und berichtet.

Backtest-Drawdown und Rendite sind Simulationsmetriken, keine Garantie.
