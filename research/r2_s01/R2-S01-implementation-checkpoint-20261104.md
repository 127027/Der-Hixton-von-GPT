# R2-S01 implementation checkpoint – 2026-11-04

**Research only; not a product or live-trading approval.**

## Proven evidence
- Frozen f56 source `f56d48536525830dd6ea50bf5bc174a6f9aeff8c`; input fingerprint `5cf39658dc6b1ee827ec0daefd73b2384a9edd0ff116ba0203f9ab8bb7737797`. Original archive `Hixton-Loss-Handoff-20261102.zip`, SHA256 `d1d1cde8347665d74da71f9e44bb3876dc6662bfe4bfc9e34dcab1dfecd84308`.
- Previous completed original-C0 real position observer: run `41848583275`. 26,304 closed hours; 21,234 with native regular holdings; 4,963 only nontradable dust; 107 without balances; 66 distinct original C0 entry identifiers with hypothetical S01 warnings. **No S01 protective trade was executed by this diagnostic.**
- Isolated research policy: `research/r2_s01/native_s01_policy.py`. It injects S01 calls into a SHA-verified original f56 portfolio **in memory**, and calls the **original** `execute_exit` closure; neither a new Fill/Trade engine nor product source edits. Native position is keyed by coin, with one aggregated trade and native cost_basis; the original order path refuses buying a coin that already has an open position. Concurrent independent same-coin lots are not represented by this frozen engine and must NOT be asserted as tested.
- Research runner: `research/r2_s01/run_native_s01.py`, supporting unchanged original 3 historical / 5 synthetic windows at current and stress costs. It asserts native source/input hash, original data snapshots, native ledger validity and disabled-mode original C0 identity. Not yet an independently approved S01 financial comparison.
- Pre-economic fixtures `research/r2_s01/native_method_fixtures.py` and repaired original predicate `s01_predicate_prefix_fixtures.py`. These check prefix invariance, known-position prerequisites, net-loss basis, native source order, fake rejected fill/no cooldown, verified callback-created full fill/cooldown, 23h/24h boundary and coin-specific entries.
- **Verified PASS:** GitHub Actions run `41860032713` at commit `da81f30b609d07ee2adf005ec1321178cb2bf857`: original archive hash, all invoked method fixtures and exact original C0 native financial ledger/equity identity with S01 disabled (`original_32k__current`). Artifact `13338634602`. This is a **preflight** result, not an independent Dot4 Method-PASS.
- S01 code's once-per-native-entry guard ensures a rejected attempt cannot generate infinite hourly duplicate exit requests.

## Explicit missing proofs and statuses
1. **Dot3 implementation**: `IMPLEMENTED_RESEARCH_ONLY`, baseline-disabled original ledger parity passed once. The enabled S01 native candidate has not yet undergone full independent method QA.
2. **Dot2 finance/reconciliation**: static proportional native basis verified by original code; real cash/position/dust accounting belongs to frozen native execute_exit; full independent state and slot reconstruction across stress/cost contexts remains open. Original engine models the quote cash as `cash` and pending signals as not-yet-filled; no separate held order-cash reserve has been proved. Original f56 does **not** simulate arbitrary asynchronous exchange partial-fill states; do not claim that live behavior is tested.
3. **Dot4 independent signoff**: `METHOD_QA_PENDING`. Prove enabled mode against native actual fills, cancellation/market-rule failures, time causality, slot/basis conservation, cooldown, and original C0 identity. If failing, repair and rerun **targeted** tests, not the rejected R1/HOLD experiments.
4. **16-context economic A/B**: `NOT_STARTED`. Must remain after documented independent method PASS, followed by independent result QA and immutable owner success gates.
5. **Dot1 original causal exposure**: At first 10% DD held BTC/SOL were profitable, both S01-negative; at first 15% DD held SOL profitable, S01-negative; at first 30% DD AVAX was ~-7.20% net with 6 below EMA, S01-positive, ADA/ETH negative. An observed warning is NOT a proven avoided loss, and no known crash can become a bespoke parameter rule.
6. **Dot5 holdout**: suggested UTC 2020-10-11 to 2023-10-11 unverified for exhaustive overlap against ALL previous research, unverified authentic listing/data/warmup. `HOLDOUT_PROVENANCE_UNCONFIRMED`; prepare independently, do not block development financial A/B solely because holdout is unready.

## Native S01 specifics frozen
- At each completed closed-hour event, EMA72 seeded by mean of first 72 genuine bars, 5 of 6 below EMA and estimated remaining native position liquidation net return <= -4%.
- One S01 attempt per native entry identity; next available native open only; original regular exits and native capacity handoffs take priority; S01 attempts are before any new buys.
- No new engine-defined extra loss-booking or fabricated gains. Filled S01 sale uses original full `execute_exit` including original price, spread, fee, fill, trade, basis, dust and position deletion.
- 24 completed hourly intervals from actual confirmed native full exit; coin-specific entry prohibition. A rejected market order or dust-only event must not start a successful-fill cooldown.
- Future-bar prices excluded from signal decision; inactive profile markets remain inactive, 15 observed markets != 15 enabled.
- All capital, HWM, positions, slots, and rules persist continuously across five-year scenarios; quarter reports are observations, not restarts.
- Synthetic whipsaw is not a forecast or proof of 1,000,000 USDC. Promotion only after original unchanged hard profitability/stress/winter/tail and independent holdout plus owner approval.

## Next strictly concrete step
Obtain independent Dot4 **activated S01** native method signoff including true actual full-exit execution and failed order/slot/cost-basis negative fixtures. Then execute exactly one 16-case frozen native paired comparison with independent economic QA. No changes to product, paper, live, API secrets or orders.
