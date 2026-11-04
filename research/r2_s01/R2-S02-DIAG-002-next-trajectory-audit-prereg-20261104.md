# R2-S02-DIAG-002 — NEXT CAUSAL RESEARCH QUESTION, PREREGISTRATION ONLY

Registered 2026-11-04 after DIAG-001 read-only outcome. **No new trading strategy or tuning authorized.**

## Observation motivating test
Frozen native f56 C0 original_32k/current ended 33867.796992897484 USDC vs S01-A 10967.6813976152497 (same result verified at current native method-policy hash, 52 S01 confirmed native full exits). DIAG-001 established *lower* aggregate modeled fees (-508.9910919897366 USDC) and modeled adverse execution (-254.4987370052 USDC), so simply saying costs caused the 22900.115595 terminal deterioration is contradicted. C0 and S01-A trades differ (361 vs 423 fills, 180 vs 211 closed trades). Neither DIAG-001 nor activated S01's serialized event list includes complete hour-by-hour candidate inventory and blocked next-pending coin entries.

## Frozen research question
**Which changes in position exposure, lost later coin-specific rebounds, prevented symbol-specific entries, and reuse of cash/slot capacity occurred *after* the 52 S01 full exits, and can they be independently traced using the original native hourly ledger without inventing additive per-trade profits?**

## Diagnostic contract before further computing
1. Operate read-only, instrument **the same original f56 native C0 and the same sealed S01-A policy**, source SHA fixed to `b104854b95ecf1623dd6fcfbbba9d5303a8909fb`, frozen original data files and checksum. No candidate parameter or market change.
2. At every completed native hour, record on BOTH matched paths: UTC, closed equity, cash, regular position quantities and *remaining native cost basis* per coin, dust value, slot occupancy/capacity, signals, any pending and blocked entries, S01 confirmation/cooldown state, and per-fill fee/adverse execution. No future-close data in any decision.
3. Demand exact re-reconciliation to existing C0/active native metrics, fills/trades, ending equity and hourly money where already available; reject changed path and report why. Existing C0 and S01-A outcomes cannot be silently changed.
4. Mark every forced S01 exit event and look up the original C0 position state at matching UTC. Observe each subsequent native strategy exit and time to next BUY; count blocked candidate signals at *both* signal generation and order queue, clearly differentiate ordinary position-already-open/slot/cash gates. Observe rebounds only as matched path price/exposure measurements, not independent 'missed-profit' claims.
5. Produce four **separate descriptive mechanism reports**: early loss-position exits and subsequent exposure; blocked 24h coin reentries; changed use of released cash and competing coin allocations; actual aggregate and time-matched trading expenses. Fully label the four as **non-additive**, because changing one creates nonlinear alternative paths via native execution and compounding.
6. Do not claim a waterfall decomposition of -22900.115595 USDC unless a separate frozen **native** factorial/ablation contract and independent QA explicitly define interaction terms. No retroactive 'choose better threshold on known crash'.
7. Stop if event-time causality, fee/cash/basis/dust conservation, or original signal ledger identity fails. Holdout provenance still unconfirmed, so no robustness/profit promotion.

## Success criteria for this diagnostic
- Two per-hour original native ledgers, deterministic SHA-bound source, zero time gaps and preserved exact old ending C0/S01 results; all 52 S01 full exits linked to matched C0 position/exposure snapshots.
- Complete counts (not lower bounds) of buy signals and orders prevented by S01 coin cooldown, with UTC and original reason; separate native rejections and unknown state.
- Observational differences in time invested, per-coin exposure and recovery, slot/cash allocation and fees with explicit fact/assumption separation.
- A bounded, **pre-results** testable future protective hypothesis *only after* these measurements. No new candidate itself in this diagnostic.

## Status
`PREREGISTERED_NOT_EXECUTED`. Original S01-A economically rejected because it violates a hard historical normal-return floor. Product, live, keys and orders unchanged.
