# HIXTON R2 – CENTRAL RESEARCH JOURNAL / FIVE-DOT LEDGER
Last evidence refresh: 2026-11-04. Research only; production f56 and live/API orders unchanged.

## SINGLE VERSIONED REFERENCE
- Current coordinated research branch: `research/hixton-native-baseline-proof-20261103`.
- Preconsolidation executable code/tree reference: `2bbb46edadc4b1536f72d35c61d44c766f3126ca`. Research overlays are separate from frozen product `f56d48536525830dd6ea50bf5bc174a6f9aeff8c` (normalized fingerprint `5cf39658dc6b1ee827ec0daefd73b2384a9edd0ff116ba0203f9ab8bb7737797`).
- Historical original archive SHA256 `d1d1cde8347665d74da71f9e44bb3876dc6662bfe4bfc9e34dcab1dfecd84308`; synthetic original archive SHA256 `5262f12bef7182ae10e2c85fe5b790263404764e98e759196dbdfb7d0970d278`.
- The 16 contexts are original_32k/current_26oct/latest_long/cycles/winter/whipsaw/rotation/tail × current/stress cost. **Do not treat successful workflow status as independent external signoff.**

## COMPLETED GITHUB RUNS — EXACT SOURCE SHAs
1. `41860032713` PASS at `da81f30b609d07ee2adf005ec1321178cb2bf857` — S01 off; original_32k/current C0 native hourly money/metrics/fills/trades/signals exact.
2. `41862289840` PASS at **older** `75558adaa2968622e026283a1ac62633fdfa37e2` — **enabled** S01 original_32k/current: 69 S01 triggers, 52 genuine native S01 sells, 17 native regular exits taking precedence, 0 reported market rejections. Original C0 ending 33867.796992897484 USDC, S01 ending 10967.6813976152497 USDC, paired aggregate delta **-22900.1155952822343 USDC (~ -67.62% of C0 ending)**; 423 original native fills, 211 native trades, 1737.87067614658085 total modeled fees. That fee value is total candidate fills, **not incremental S01 fee versus C0**. Older active result is diagnostic, not current method PASS or independent causation.
3. `41862839373` PASS at `654f8e0b05fc981e6d0703ecfaccd3d5d68d8dad` — deterministic native fixtures and disabled C0 original_32k/current identity; additional separate native Fill/Trade audit is present in source but *not exercised in enabled candidate mode* in this run.
4. `41862977181` PASS at `38b3e39eca7f726a16adfc4a23528f9cd61e729e` — ALL 16 S01-disabled exact native C0 equivalences (metrics, signals, fills, trades, every hourly cash/equity row); both original archive SHA256 verified. This run uses same executable S01 source as `2bbb46e` (later commits documentation only), but only disabled behavior.
5. Superseded preflight runs `41862419692`, `41862448713`, `41862681659` failed on intermediate revisions. They are **not current pass evidence**; the later `41862710588` and `41862839373` successfully exercised their subsequent test fixes.
6. Prior C0 read-only observer `41848583275` PASS: 26304 completed hours; 21234 with genuine holdings, 4963 dust-only, 107 neither; 66 distinct C0 entries had hypothetical warning conditions. This is **not** 66 executed/redeemed S01 trades.
7. Previous R1 H1/H2/H3, HOLD001/002/003, 16-case each and control 200 quarterly cases were completed earlier; all proposed HOLD candidates rejected. Do not repeat as fresh tests.

## FIVE DOTS: RESPONSIBILITY, PROVEN DELIVERY, BLOCKER, NEXT NONDUPLICATE WORK
| Dot | Function | Newest verified delivery | Current status | Next exactly bounded action |
|---|---|---|---|---|
| 1 | Held-position protection and causal loss analysis | Native C0 observed real holdings and first warning; active S01 old negative delta and 52 sells now recorded | CAUSAL_ATTRIBUTION_OPEN | Matched native trade-trajectory study: separate premature exits, subsequent signal/cash/slot allocation, BUY cooldown, modeled costs; **no additive per-trade 'missed-profit' attribution**. |
| 2 | Native capital and books | 16/16 disabled-C0 ledger parity + original native Fill/Trade formulas; research additional audit module `native_ledger_independent_audit.py` committed | ACTIVE_LEDGER_AUDIT_NOT_EXECUTED | Run independent activated candidate ledger audit of native sale quantities, proportional basis, fees, net cash, dust, slot capacity; explicitly distinguish f56 synchronous fills from unsupported exchange order reservations. |
| 3 | Implement strategy | S01 native policy/runner in shared branch, plus independent S01 predicate fixture `3ba4f6104db13d99d18a6fa754cbbb01ba1ac57f` on `research/dot3-s01-method-fixtures-20261104` | ONE_ENGINE_RULE; AUX_TEST_BRANCH_AWAITING_RECONCILIATION | Reuse only truly additional test assertions (400h report warmup, partial-basis invariance, prefix-time invariance); **do not merge a second strategy/predicate as authority**. Verify coverage in shared fixtures. |
| 4 | Independent methodology QA | Reviewed older run SHAs and explicitly retained `METHOD_QA_PENDING` | **NO INDEPENDENT APPROVAL** | Reconstruct identical current source+data signature, run *enabled* S01 with separate Fill/Trade audit, verify rejection vs UNKNOWN fail-closed and next-open. Produce independent PASS or precise evidence-linked BLOCKED, not just green CI. |
| 5 | Coordination and provenance | This central ledger now corrects obsolete 'queued' statuses; sealed execution contract `2bbb46e` | JOURNAL UPDATED; HOLDOUT_UNPROVEN | Keep evidence-per-commit and owner gates synchronized. Audit all prior datasets before labelling any holdout untouched. |

These Dots are scheduled tasks with completed individual turns; **five independent concurrently running compute workers are not demonstrated**.

## EXPERIMENT S01-A – EXECUTION SEMANTICS SEALED BEFORE FINANCIAL PROMOTION
- EMA72 SMA seed first 72 closed bars, >=5 of last 6 completed closes below relevant prefix EMA, remaining native estimated net cost-basis return <= -4%; genuine regular-held positions only.
- One exit **attempt** per (symbol, original native entry signal_id), including rejected attempt; no automatic hourly retry. Original regular sales take priority; original synchronous f56 `execute_exit` is authoritative for Fill/Trade/cash/dust/slot mechanics.
- Matching real confirmed S01 sale starts coin-specific 24 finished hours BUY gate from actual fill, not warning/rejection. Explicit native rejection converts neither imaginary cash nor cooldown. Unknown/no Fill/no block reason fails closed.
- Bounded retry after rejection is conceivable as **separately preregistered S01-B**, never inserted into S01-A after results are seen.
- f56 does not model external exchange async partial fills or multiple independently tracked same-coin lots; they remain future product review.

## CURRENT QA GATE / ECONOMIC REUSE DECISION
- **METHOD_QA_STATUS = PENDING**, not approved. Current active enabled replay with `native_ledger_independent_audit.py` has NOT been proven by the named passes. No separate autonomous Dot4 approval of this exact code/data state.
- Executable policy code materially differs from old active `75558ada` by fill/rejection/unknown classification, fail-closed book assertions, original slot and cash reconciliation, and external ledger audit. **Signal thresholds and intended sale/cooldown choices are unchanged.**
- Because old active run reports 52 fills + 17 native exits with no rejected/no-fill statuses, its **historical economic negative signal is highly relevant**, but without a same-code replay and passing audit no bitwise identity of actual current trade schedule can be claimed. Comparing old active ending capital to current C0 is diagnostic only.
- 16/16 disabled C0 identity is complete. **16/16 activated S01 economic comparison is not yet executed or method-authorized.**
- Holdout 2020-10-11 to 2023-10-11 is only a proposed window; independent unusedness, listing provenance and 400h warmup are not established.

## FIRST MECHANISM ANALYSIS — NON-ADDITIVE
Observation: 52 forced full S01 exits on old historical original_32k/current were followed by a portfolio terminal equity 22900.115595 USDC below C0. That is a paired **pathwise** equity delta; one cannot allocate it to individual missed coin profits without counterfactual replay because sale proceeds alter cash, later entries, slot contention, cost basis, fee frequency and compounding. 17 trigger events were superseded by native regular exits; they were not S01 sales. Costs: 1737.870676 USDC is candidate total fees, not attributable excess fees.
Separate follow-up questions (not asserted answers): (1) which S01 exits were followed by rising coin prices or rebound before C0 exit; (2) whether 24h symbol lock actually excluded eligible next-native buys; (3) how liberated cash/slots changed competing trades and later exposure; (4) change in native fee/slippage paths vs identical C0 timestamps. Attribution must compare comparable paths, never sum independent missed-profit estimates.

## NEXT PREREGISTERED RESEARCH QUESTION (CONDITIONAL)
If all hard gates are missed on a method-verified S01-A, reject S01-A. Investigate **HYPOTHESIS R2-S02-PRELIMINARY**: sustained weak *held* positions can display adverse continuation versus transient technical pullbacks; before any new parameter choice, classify the existing 52 S01 events by strictly decision-time-available trend/volatility state and independently measure later rebound opportunity cost using counterfactual native trajectories. This is diagnostic only, not an approved parameter tweak or new trade policy. Predeclare rule, control, failure gates and untouched evaluation partition **before** running future economic candidate tests. No bespoke known-crash exceptions.

Product/Paper/Live orders, API credentials and releases unchanged.
