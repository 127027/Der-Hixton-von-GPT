# Vorlage – Backtest Run Manifest

Status: CURRENT · 26.09.2026

Jeder aktuelle Run muss dokumentieren:
- Run-ID, Commit-SHA, Erstellzeit;
- strategy_key: v6 und abgeleitete Strategieversion;
- Profilhash je Symbol;
- Quote/Marktdatenprovenienz und Proxykennzeichnung;
- Report- und Warm-up-Fenster;
- Modell: single / 10×250 / shared max_capital_usdc;
- Startkapital: single/isoliert 250,00 USDC je Coin; shared gemäß gespeichertem `max_capital_usdc`; 
- shared Allocator-Version, `max_capital_usdc`, abgeleitete Slotzahl/Tranchengröße/Reserve und `ranked_repeat`; 
- Baseline-/Stresskosten;
- Endkapital, PnL, Rendite, Positionszyklen, Slot-Trades, Max-DD;
- Blockierungsgründe;
- Source-/Config-/Daten-Fingerprints;
- Status und Limitierungen.

Ein Run darf nicht als Zukunfts- oder realer Binance-Fillnachweis bezeichnet werden.
