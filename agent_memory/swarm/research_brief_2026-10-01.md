# Research brief — 2026-10-01 profit and capital velocity

## Owner goal
Move Hixton 0.5.0 closer to higher reproducible net profit from the same 250-USDC total budget, with faster productive reuse of capital. Drawdown, stress and holdout integrity remain hard gates, not the primary optimization direction.

## Runtime first
The preserved Paper account is stale because it is still bound to HIXTON-V6-COIN-PAPER-1-fbd1b842f4f9 while the current canonical V6 profile map is HIXTON-V6-COIN-PAPER-1-b271d7952d15. Recover it only through the exact Paper-only authorization. Preserve history; do not reset; never enable real/testnet orders.

## Research findings to act on
- Do not rerun the latest parameter grids unchanged.
- ETH momentum19 is the priority diagnostic case: isolated alpha can still harm the shared 250-USDC portfolio through slot timing/opportunity cost.
- Measure added, removed and shifted trades; extra/freed occupied slot-hours; simultaneous competing signals; displaced-coin counterfactual PnL.
- A candidate must improve both isolated and canonical shared-portfolio evidence under baseline and stress before promotion.
- ADA and DOT remain production-frozen; shadow research is allowed.
- BTC/BNB: focus on capital binding/timing and stall/progress behavior.
- SOL/LINK/AVAX: focus on capturing more high-quality opportunities and timing/volatility response.
- XRP: focus on entry timing rather than repeating stop/CMO/band search.
- DOGE: focus on ATR/volatility response rather than repeating momentum/smoother/CMO.
- Keep coin-profile experiments separate from portfolio allocator/ranking experiments.

## Portfolio research after coin freeze
Use the same exact three-year window, costs, risk and 250-USDC total budget. Compare the 2x125 baseline against already-required equal-budget alternatives and opportunity-cost ranking. Do not alter coin profiles in the same experiment. Preemption, if studied at all, comes only after ranking/allocation evidence.

## Required gates
No promotion without exact-head reproducibility, training-only candidate selection, holdout/stress integrity, isolated base/stress, shared-portfolio base/stress, and positive portfolio marginal contribution. A09 and A11 remain independent gates.
