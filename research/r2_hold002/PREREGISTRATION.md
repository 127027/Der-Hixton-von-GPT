# R2-D1-HOLD-002 – predeclared one-variable ablation of buy shutdown

Research preregistration dated 2026-11-04 **before economic simulation of HOLD-002**. R1 H1/H2/H3 remain discarded. Frozen native financial source: `f56d48536525830dd6ea50bf5bc174a6f9aeff8c`.

## Grounded reason for new hypothesis

The completed 16-context HOLD-001 native financial run 41830599331 and separate financial QA 41831765786 show a large historical growth penalty. Across 16 cases, there were 20 defensive triggers, but only 12 actual trim fills across seven cases; in nine cases no regular-position partial trim occurred. HOLD-001 also blocks new native entries during defense, so the observed C0-vs-HOLD-001 equity difference does not isolate benefits or costs from partial liquidation.

## Frozen new hypothesis (only changed dimension from HOLD-001)

- Keep the existing 15%-from-global-HWM threshold, **72 consecutive finalized 1h closes**, *one trigger per episode*, 25% of each regular held coin's close-frozen base quantity, native full EXIT/handoff first, next-open execution at unchanged f56 native fee/slippage/exchange filters, unchanged regular position slots/units, no repeated hourly liquidation.
- Keep original re-arm after 168 consecutive finalized hourly closes with global HWM drawdown strictly below 10%, with no forced purchases.
- **Remove only HOLD-001's new-entry suspension**. In HOLD-002 all original f56 eligibility, capital/risk gates and buy signals remain unchanged throughout both the defensive and rearm states. At a trigger with no sellable held position, the episode is still recorded, but nothing is sold and native buys remain eligible. This avoids inventing a new sell opportunity or retrospectively postponing a trigger.
- No change in thresholds, coin universe, selection, warmup, price time, cost model, cash/reservation/slot semantics, win/loss scoring, stop policies, or original historical/synthetic worlds.

## Ex ante test plan and no look-ahead

Independently preflight HOLD-002 with a negative test proving that defensive mode cannot block a native new entry, while original HOLD-001 did. Prove native engine identity when the research hooks are disabled, preserved causal next-open settlement, original min order and fee handling, rearm/nonrepeat and regular-exit precedence. Only after pre-economic QA, calculate 3 overlapping historical windows + 5 invented 5Y worlds, each current/stress = **16 complete original-context A/B cases**. Keep uninterrupted reinvestment and 20 anchored 3mo segments in five-year worlds; never use selected bad quarter to modify parameters.

## Selection gates and interpretation

Reuse all old R1 profit-first gates unchanged: original normal ending-equity floor in both old 3Y historical windows and in latest-long, mean three paired historical stress return changes >=0, winter and tail ending equity not below C0 and maximum DD strictly below C0 under BOTH cost models, plus financial/source/causal QA. Drawdown reduction does not excuse failing profit floors. Document mean and worst monthly/quarter returns, max absolute/% HWM episodes with recovery, costs, and opportunity cost from missed profits. Treat synthetic outcomes as exploratory, not true independent holdout; no automatic product promotion.

No product/Live/Paper/Order/API key changes, and no Codex implementation until independently audited evidence and separate owner authorization.
