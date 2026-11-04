# DOT3-R2-S01 — held-position deterioration exit (pre-registration, NOT APPROVED)
Date 2026-11-04. Status: HYPOTHESIS / AWAITING DOT4 METHODOLOGY QA. Research-only; no production or trading changes.

## Motivation and scope
R1 H1/H2/H3 are completed, rejected and must not be rerun. The already verified R1 HWM attribution is complete. This proposal acts on **already held positions**, unlike rejected entry-only H3. It applies only to existing approved trading profiles; the 15 monitored markets are not 15 enabled profiles (SUI/UNI research-only).

## Frozen candidate S01
At each hourly decision time t, using ONLY bars whose close timestamp is <= t-1 and the position's actual fill ledger as of t-1:
- For each open long coin c compute 72-bar EMA of closes and 24-bar ATR (Wilder smoothing, true range uses preceding close), on the native engine's already-normalized hourly candles; seed/warmup must be fixed from the native baseline contract, not fitted.
- Calculate adverse trend persistence P(c,t): count of the last **six completed hourly closes** strictly below their contemporaneous EMA72. No new signals during incomplete warmup or unavailable original bars.
- If P>=5 and unrealized position net return since weighted-average acquisition cost <= -0.04, request exit of **100% of that coin's existing long position** at the next native executable opportunity; fees, spread, slippage, lot rounding, dust, partial fills and order cash must be handled by the unchanged f56 execution engine. The signal does not retroactively fill at t-1 close.
- After a triggered exit, block NEW entries in that same coin for **24 completed hourly bars**, without changing other coin gates or global slots. Existing unrelated positions unchanged. If the native engine cannot represent this cooldown without altering baseline semantics, report BLOCKED_ENGINE_SEMANTICS to Dot4 rather than approximate.
- Compare predeclared direct neighbors P>=4 of 6 and P=6 of 6 **only after** primary S01 is independently QA-approved; same -4% loss trigger and 24h cooldown. No parameter search beyond these three.

## Required causality/negative tests BEFORE any financial backtest
1. Verify real Input-Contract.json candle members and exact native f56 loader/UTC convention; don't treat ZIP header-only schema scan as missing candles.
2. Strict prefix-invariance: adding future candles cannot alter any previous indicator/decision. Inject a future price spike and assert all prior decisions unchanged.
3. Verify entry/exit chronology, no t-bar close execution using t-bar indicator, and no hindsight labels from PnL attribution.
4. Check held-position accounting, weighted cost basis after partial buys/sells, missing-bar fail-closed behavior, 24h cooldown, listing availability, 15-market/active-profile separation, and no duplicate fees.
5. Dot4 signs methodology, original profit floors, stress/winter/tail gates, and 20-quarter plus independent holdout plan BEFORE A/B.

## Financial test contract (not yet authorized)
Once Dot4 approves, compare unmodified C0 vs S01 across 3 original-length historical windows and 5 original synthetic 5Y scenarios, each current/stress = 16 contexts. Same inputs, seeds, costs, f56 product SHA f56d48536525830dd6ea50bf5bc174a6f9aeff8c; uninterrupted equity and all native fills. Report total/coin exit counts, avoided drawdown, false exits, missed large winners/reentry delay, fees/slippage, absolute and relative HWM episodes and recovery, monthly dispersion and 20 continuous quarters per synthetic path. Report Pareto pairs without automatic promotion. Historical and synthetic development worlds are NOT independent holdout.

## Provenance anchors
Owner-verified handoff ZIP SHA256 7008224237a81422acce03186cbcf27b10991fb8f8b10aa216b32ccb8822f57a (not locally opened in this run). Historical original SHA256 d1d1cde8347665d74da71f9e44bb3876dc6662bfe4bfc9e34dcab1dfecd84308. Synthetic original SHA256 5262f12bef7182ae10e2c85fe5b790263404764e98e759196dbdfb7d0970d278. R2 20-quarter QA run 41801720710. No claim of a new executed simulation.
