# Dot 4 independent-method review — R2-S01-A exact code/data decision

Date: 2026-11-04. Status **METHOD_BLOCKED**, not METHOD_PASS. Research only.

## Subject of review
Executable current research code at commit `87e32f0c6a3379849d9482e6756722be8f115d97` (the subsequent workflow creation commit adds a CI-only file). Key blob SHAs:
- policy `research/r2_s01/native_s01_policy.py`: `b104854b95ecf1623dd6fcfbbba9d5303a8909fb`.
- native runner `research/r2_s01/run_native_s01.py`: `3ce4d4696c6e061b5cf8c80aa14e37b59fcc71ab`.
- separate native Fill/Trade accounting auditor `research/r2_s01/native_ledger_independent_audit.py`: `817edd41523219b94d1c010980ff208341e45edb`.
- native fixture file after Dot3 gap/prefix merge was added in commit `87e32f0c6a3379849d9482e6756722be8f115d97`.
- Frozen f56 product commit `f56d48536525830dd6ea50bf5bc174a6f9aeff8c`, original archive hash `d1d1cde8347665d74da71f9e44bb3876dc6662bfe4bfc9e34dcab1dfecd84308`; synthetic archive hash `5262f12bef7182ae10e2c85fe5b790263404764e98e759196dbdfb7d0970d278`.

## Positive independent data checks (real GitHub actions evidence)
- `41862977181` PASS: all 16 identical frozen C0 metrics, signals, fills, trades and all-hour cash/equity when S01 disabled, at `38b3e39eca7f726a16adfc4a23528f9cd61e729e`. Current executable policy, native runner and separate audit module blobs are unchanged from that commit; Dot3's later changes add fixture assertions only.
- `41862839373` PASS: original_32k/current disabled C0 + original native fixture set at `654f8e0b05fc981e6d0703ecfaccd3d5d68d8dad`.
- `41873630590` PASS: additional actual native feature-builder 400-hour prefix consistency/missing closed candle and original deterministic fixture tests, plus disabled original_32k/current C0, at `87e32f0c6a3379849d9482e6756722be8f115d97`.
- `41862289840` PASS older active S01 at `75558adaa2968622e026283a1ac62633fdfa37e2`: 52 actual original native exits, 17 regular-exit takeovers, 69 triggers. Old active ending 10967.6813976152497 USDC against C0 33867.796992897484; delta -22900.1155952822343. This predates the *current* reject/unknown semantics, native cash/slot checks, and separate auditor.

## Concrete missing proof / BLOCKED (not generic 'waiting')
**A. No actual activated current-policy native trade audit has passed** at policy blob `b104854...`, runner `3ce4d4...` and auditor `817edd...`. The successful current-schema check `41873630590` tested disabled C0 only, and the only active run `41862289840` used old policy `6907d1...` without the separate native Fill/Trade auditor. Therefore not yet demonstrated on the present executable tree that all native S01 Fills/Trades, fee, sold units, realized proportional cost basis, net cash, residual dust and freed slots reconcile.

**B. Rejection and unknown execution negative tests use injected native callback mocks** and were run via actual code fixtures. Full actual engine market-filter rejection cannot be claimed independently covered merely from those mocks; no such event appeared in the 69 older active triggers.

**C. No separate, independently authorized Dot4 signoff has examined the exact current activated financial ledger**. This file is an evidence review prepared during coordination, not a claim that an autonomous Dot4 reviewer approved the code. The Dot4 scheduled task's last recorded verdict remains METHOD_QA_PENDING.

## Required next evidence, no extra regression duplication
- Run exactly one enabled current-code `original_32k/current` controlled S01-A original native replay with the embedded separate auditor; a dedicated workflow is committed at `.github/workflows/hixton-r2-s01-current-method-ledger-20261104.yml` (commit `3ec5635b367c610c647966d3892b282e56e106e4`), but its run was not present in GitHub Actions results at this review. Do not claim it has executed.
- Compare native S01 signal/fill/trade/equity against the older 52-exit run for exact equivalence; if final trading path is identical and same input cost/model hashes, reuse older negative original_32k evidence as one context. If not, investigate divergence before all-16 cases.
- Obtain a separately recorded reviewer judgment based on that actual result and all negative fixtures; only then mark METHOD_PASS. If negative, report which check failed and exact job logs/artifact SHA.
- After valid PASS, run remaining distinct activated 15 contexts with unchanged frozen control and 16-context paired economic gates; do not rerun the existing disabled 16/16 or previously rejected HOLD/R1 sets.

## Outcome and trading interpretation
Potential strategy economic failure is **not** technical method failure. S01-A's old -22900.115595 USDC paired historical terminal delta is strong evidence against promotion in original_32k/current, but current finance METHOD_PASS remains unproven. There is no claim that total loss equals independently summed missed trade profits; compounding/cash/slot/concurrent trades make the delta path-dependent. Reject S01-A if unchanged hard normal-historical non-regression gate fails after valid QA. Next diagnostic question is causal decomposition of premature exits vs coin cooldown vs portfolio reallocation vs incremental costs, using preregistered decision-time diagnostics, without tuning known crash episodes.

Live product, API keys, orders, paper and production source not modified.
