# R2-S02-ABL-001 PREREGISTRATION — SINGLE-FACTOR COOLDOWN EFFECT

Registered 2026-11-04 **before** test outcome. Explicit research-only diagnostic ablation on rejected S01-A, not a new product candidate or backfitted strategy.

## Hypothesis and purpose
In S02-DIAG-002, current sealed S01-A forced exits (52 native fills) caused extensive portfolio divergence from frozen C0; 15 candidate BUY signals were blocked by the S01-specific post-fill 24-hour coin lock, one of which corresponded to a genuine C0 BUY fill with identical signal ID. Does post-S01 coin cooldown **causally** change native ending equity and subsequent portfolio activity **conditional on identical S01-A protection exits**? A one-factor experiment, not individual-trade 'missed gains' addition.

## Fixed source and finance input
- Frozen original product `f56d48536525830dd6ea50bf5bc174a6f9aeff8c`, normalized source SHA256 `5cf39658dc6b1ee827ec0daefd73b2384a9edd0ff116ba0203f9ab8bb7737797`, native `portfolio.py` SHA256 `06da08bf4e63613a5c655eaa34a3361d0b192645e1d128cf545e4075c0401dfd`.
- Original historic data ZIP SHA256 `d1d1cde8347665d74da71f9e44bb3876dc6662bfe4bfc9e34dcab1dfecd84308`, `original_32k/current`, frozen original normal costs, no sample/date/fee changes.
- Existing active native 24h S01-A source policy blob `b104854b95ecf1623dd6fcfbbba9d5303a8909fb`, runner read-only trace option source `fcf7f3c821b9fc13f3d1032a681a3d7a1122be6d`. Previous 24h output run `41889629161`, 52 exits, ending `10967.68139761524970000000`. C0 `33867.79699289748400000000`.

## Exact ONE intervention
For a **counterfactual S01-A-no-cooldown only**, skip both S01-specific BUY cooldown filters by overriding `S01Policy.entry_allowed(symbol,at)` to always return `True`. The policy's original S01 trigger, 5/6 EMA72, -4% net mark versus remaining native basis, original forced full native next-open exit, one-attempt-per-native-entry, original regular exit precedence, fee, slippage, dust, cash, slots, 400h warmup and all original native BUY/risk/quality gates stay **identical**. `cooldown_until` ledger fields may be still written after sale, but are deliberately not enforced; label these as inactive internal metadata, not an actual 24h lock.

Use same native frozen run/ledger verifier. A fixture asserts that in the modified research harness a coin that would have been blocked only by S01-specific cooldown is allowed, while all original S01 logic remains unchanged; the override only affects `entry_allowed`. Fail if the reference S01-A original run is not same exact prior end/52 fills.

## Outputs
- Existing C0 and S01-A exact terminal/economic references.
- New no-cooldown native original_32k/current end, real native S01 triggered and filled full exit count, native Fills/Trades/Cash/Fee/Basis/Dust/Slots audited.
- PAIRED S01-A-versus-no-cooldown *portfolio terminal delta* and native fills/trades/fees/slots.
- Difference interpreted as conditional total effect of removing the S01-specific lock **including all compounding and competing-trade interactions**, not dollar-by-dollar effects of the 15 blocked orders.
- Not sufficient to explain total C0-versus-S01 decrease or to claim future effectiveness. No additivity or holdout assertions; S01-A stays rejected.

## Post-outcome rules
No retuning of exit threshold, EMA72, cooldown duration or data windows based on result. One diagnostic question only; fail or adverse result records as-is. A later candidate needs a new preregistration, independent method QA, all 16 frozen contexts and separate untouched holdout provenance. No changes to product, live/paper, orders, credentials, or original f56.
