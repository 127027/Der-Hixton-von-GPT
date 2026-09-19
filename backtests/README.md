# Backtests – current V6 research journal

Status: CURRENT · 2026-09-19

## Product model
- Main acceptance model: shared **250 USDC** account, **3×80 USDC**, `ranked_repeat`.
- Coin laboratory: **10×250 USDC isolated**, ten independent 250-USDC accounts.
- Same canonical V6 profile map in Paper, single coin, 10×250 and 3×80.
- Baseline and stress costs are both mandatory.
- There is no permanent portfolio drawdown entry halt. Drawdown is measured; the 5% UTC-day loss pause and technical safety gates remain.
- Historical same-base USDT candles may only be an explicitly labelled pre-listing research proxy.

## Current validated research checkpoint
Source: GitHub Actions run **35463131378**, artifact **10590881515**.
Window: **2023-09-19 19:00 UTC – 2026-09-19 19:00 UTC**.

| Model | Incumbent | Promotable candidate | Delta |
|---|---:|---:|---:|
| 10×250 baseline | 8,187.22 | **8,217.01** | +29.79 USDC |
| 10×250 stress | 7,659.23 | **7,692.51** | +33.28 USDC |
| 3×80 baseline | 1,212.98 | **1,217.91** | +4.92 USDC |
| 3×80 stress | 1,128.65 | **1,133.41** | +4.75 USDC |

Candidate 3×80 baseline: **94 position cycles**, **210 slot trades**, **24.10% max drawdown**.
Candidate 3×80 stress: **94 position cycles**, **210 slot trades**, **28.62% max drawdown**.
The aggregate gate reported `promotable=true`.

The final incremental change in that run is **BTC VIDYA 6 → 5**. It sits on top of the already validated/promoted ADA band 4.4, AVAX band 4.6 and DOGE momentum 18 profile changes.

## Current profile lessons
- **SOL** remains a protected strong incumbent; previous aggressive challengers materially harmed isolated performance.
- **BTC** improved with VIDYA 5 and passed isolated baseline/stress plus marginal shared-portfolio baseline/stress.
- **ADA** and **AVAX** materially improved through wider coin-specific bands and became portfolio-compatible only after Top-K + marginal 3×80 selection.
- **DOGE** benefits from momentum 18 in the accepted combination.
- **XRP** still deserves loss-cluster work: it contributes many trades and its portfolio PnL is sensitive under stress.
- **DOT/ETH/LINK** can be positive isolated sources yet negative shared-portfolio contributors because slot timing matters. Isolated improvement is never sufficient for promotion.

## Required research loop
1. Generate a bounded candidate neighbourhood from a causal trade/loss hypothesis.
2. Rank only on training A/B evidence.
3. Freeze Top-K.
4. Run validation baseline/stress and full-three-year baseline/stress.
5. Reject any finalist that fails the coin gate.
6. Test every robust finalist alone against the incumbent nine-coin map in shared 3×80 baseline/stress.
7. Combine only portfolio-compatible winners, re-testing each addition.
8. Require final 10×250 and 3×80 baseline/stress non-regression.
9. Record rejected candidates/lessons here.
10. Only then patch the canonical V6 map and rerun preflight, E2E, full regression and A01–A11.

## Evidence discipline
A higher backtest number is not a forecast. All results are simulations under documented cost/fill assumptions. Research artifacts do not activate Paper automatically. A changed V6 digest requires explicit audited Paper strategy activation without account reset.

Older V1–V5/V7–V9 directories were removed from the current product branch during the 2026-09-19 cleanup. Their useful lessons are retained here, in DMS CHANGELOG/decision history and Git history.
