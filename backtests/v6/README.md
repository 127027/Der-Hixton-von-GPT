# Current V6 backtest evidence

This directory is the only current product backtest directory.

Canonical strategy source: `src/hixton/domain/versions.py`.
Runtime config contains only `strategy.key = v6`; it does not duplicate the profile map or digest.

## Current profile map
Parameter order below: VIDYA / momentum / smoothing / ATR / band.

| Coin | Parameters | Policy delta |
|---|---|---|
| BTCUSDC | 5 / 20 / 8 / 120 / 4.4 | CMO floor 0.2 |
| ETHUSDC | 6 / 20 / 8 / 60 / 3.8 | slope 24 |
| BNBUSDC | 10 / 20 / 8 / 120 / 5.0 | — |
| SOLUSDC | 6 / 20 / 15 / 60 / 3.8 | — |
| XRPUSDC | 6 / 20 / 8 / 120 / 3.2 | close stop 4 entry ATR |
| ADAUSDC | 6 / 20 / 8 / 60 / 4.4 | — |
| LINKUSDC | 6 / 20 / 8 / 60 / 3.8 | slope 24 |
| AVAXUSDC | 6 / 20 / 8 / 60 / 4.6 | — |
| DOTUSDC | 6 / 20 / 8 / 60 / 3.8 | — |
| DOGEUSDC | 6 / 18 / 15 / 120 / 4.4 | CMO floor 0.2 |

All profiles use 1h closed-bar signal semantics and 400 warm-up bars.

## Latest promotion evidence
Run 35463131378 / artifact 10590881515, window 2023-09-19T19:00:00Z to 2026-09-19T19:00:00Z:

- 10×250 baseline: **8217.00711069101365 USDC**
- 10×250 stress: **7692.5144402748462 USDC**
- shared 3×80 baseline: **1217.9057596598351 USDC**
- shared 3×80 stress: **1133.4052326050468 USDC**
- shared baseline max DD: **24.0971724645773%**
- shared stress max DD: **28.6189648936273%**
- position cycles / slot trades: **94 / 210**
- aggregate promotion gate: **PASS / promotable**

See `current-evidence.json` for the compact machine-readable checkpoint and `../README.md` for the continuing learning journal.

## Commands
```powershell
py -3 src/main.py backtest all --strategy v6
py -3 src/main.py backtest portfolio --strategy v6
py -3 src/main.py backtest single --strategy v6 --symbol BTCUSDC
```

Normal product UI/API/CLI expose only current V6. Backtests never activate Paper. Real/testnet trading remains outside the released product boundary.
