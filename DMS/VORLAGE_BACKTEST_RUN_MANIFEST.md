# Vorlage – Backtest Run Manifest

Status: CURRENT · 19.09.2026

Jeder aktuelle Run muss dokumentieren:
- Run-ID, Commit-SHA, Erstellzeit;
- strategy_key: v6 und abgeleitete Strategieversion;
- Profilhash je Symbol;
- Quote/Marktdatenprovenienz und Proxykennzeichnung;
- Report- und Warm-up-Fenster;
- Modell: single / 10×250 / shared 3×80;
- Startkapital: single/isoliert 250,00 USDC je Coin; shared 250,00 USDC;
- shared slot_count 3, target 80,00 USDC, ranked_repeat;
- Baseline-/Stresskosten;
- Endkapital, PnL, Rendite, Positionszyklen, Slot-Trades, Max-DD;
- Blockierungsgründe;
- Source-/Config-/Daten-Fingerprints;
- Status und Limitierungen.

Ein Run darf nicht als Zukunfts- oder realer Binance-Fillnachweis bezeichnet werden.
