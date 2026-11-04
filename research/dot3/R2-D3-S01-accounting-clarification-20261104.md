# Dot 3 – separation and missing accounting contract for distinct R2 ideas (04 Nov 2026)

Research only. No product, live, paper or original trading-profile changes. Original R1 H3 was fully tested (16/16) and rejected.

## Never combine these prototypes
- **R2-D3-001** (local prototype, NOT financially tested): proposed 50% partial regular-position reduction after three completed EMA72-below bars and ATR24 adverse deviation >=0.50. Its own fee/lot-basis contract and method gate are still pending.
- **R2-D3-S01** (GitHub preregistration in research/dot3/R2-S01-held-trend-deterioration-prereg-20261104.md, NOT financially tested): separate **100% native close** of one held regular coin if 5 of last 6 consecutive completed hourly closes are below EMA72 and that **remaining coin position's** marked return <=-4%, with separate 24-closed-hour buy cooldown for the same coin. Only this S01 definition is clarified below.

## Accounting additions for S01 – independent Dot4 method approval required before any economic test
1. Use immutable original f56 source and Input-Contract.json with the original working NPZ / GZIP loader and verified snapshots; no generic CSV header scanner as substitute.
2. **Open-position loss denominator** = the native remaining regular position's positive `cost_basis` after all earlier partial sales. A partial sale deducts the proportion `old_cost_basis * sold_quantity / old_quantity`; do not reuse the original full-buy cost basis for the residual lot. The native purchase fee is already reflected in the cost of the received net base quantity; do not subtract it again.
3. Proposed closed-bar *mark* return at time t = `(remaining_base_quantity * last_finalized_close - remaining_cost_basis) / remaining_cost_basis`. This is NOT yet the actual net exit PnL. Fees and adverse fill price on any eventual sale occur only at the **next executable open** and are separately included by the original f56 native `Fill`/`Trade` cost model. If the original word “net” must include estimated exit fees in the threshold, freeze that alternative definition and secure new Dot4 sign-off BEFORE seeing results; no ex-post switching.
4. Signals use only fully closed hourly candles and existing position state as of the same close. Decide at close t, request an exit for **the next native open t+1**, not the just-seen close. Native full EXIT, Core handoff and diversification priority win; do not duplicate or pre-empt a regular exit. Any failed market minimum/step rule leaves the position governed by the native engine; do not invent partial fills or bypass dust handling.
5. The 24-hour no-buy window starts only after a successfully recorded S01 exit fill. Count exactly 24 **subsequent completed hourly bars** for that symbol; native buys become eligible at the next executable opportunity following completion, subject to all unchanged native gates/slots; never place a forced re-entry.
6. No negative-quantity, duplicated fee, invisible free slot, future-bar indicator, or fabricated candle. Closed-bar EMA72 and ATR24 initialization/warmup must match a frozen written technical method before use. SUI and UNI remain research-only.
7. Document false exits, missed profitable native entries, changed fee/spread/slippage, 20 continuous quarters for each synthetic 5Y run, both separately worst absolute/% HWM loss episodes, and all 16 unchanged original context/fee pairs. No parameter search or blending with R2-D1-HOLD-001.

**Status:** Method clarifications proposed for Dot4; no economic calculation or independent QA acceptance for S01/001 yet.
