# R2-S02-DIAG-001 — preregistered descriptive failure mechanism audit
Date: 2026-11-04. Registered after S01-A observed historical failure but **before** diagnostic extraction. Not a tradable strategy; all historical/synthetic worlds remain development data.

## Fixed evidence and source
- Frozen product f56d48536525830dd6ea50bf5bc174a6f9aeff8c, original historical archive SHA256 d1d1cde8347665d74da71f9e44bb3876dc6662bfe4bfc9e34dcab1dfecd84308.
- Current native S01-A run 41873929231, code SHA 3ec5635b367c610c647966d3892b282e56e106e4, artifact 13345118126. Independent native Fill/Trade accounting audit within this run passed, 52 confirmed native S01 sales, original_32k/current only.
- Original C0 path and costs taken exclusively from the frozen input contract and original native f56 Fills/Trades, not re-estimated.
- Confirmed terminal paired delta S01-A vs C0 -22900.1155952822343 USDC, i.e. a full pathwise result, **not the sum of attributable missed profits**.
- Both the 16/16 disabled-C0 identity and the old/current actual S01 outcome have already been calculated; **no new strategy financial replay in this diagnostic**.

## Question and exact measured fields (predeclare)
Can we establish that S01-A's loss of terminal equity reflects a changed native trade path rather than merely extra fee? First audit **observed** frequencies and money flows without causal attribution:
1. Count native confirmed forced full S01 exits, regular native exit takeovers, rejected or unresolved state, and event counts by symbol and UTC. Sum original S01 exit gross proceeds, sale fees, cash released and slot releases (flow, not end balance).
2. Count *recorded* symbol reentry cooldown blocks; events in the currently persisted S01 log are only those `filter_entries` records, so this is a **lower bound**, not an exhaustive signal-level count; additional next-pending blocks exist in the f56 blocked list but are not serialized in the event file.
3. Compare **candidate total native Fill fee** versus baseline total original f56 Fill fees directly extracted from original C0 `Fills.json`, and total modeled adverse-price slippage if fields are available. Incremental fee and slippage delta cannot on its own establish opportunity cost.
4. Compare native aggregate fill/trade counts, not individual attribution. Native C0 `Trades.json` permits chronology checks, but candidate result exports only first 25 sale details, not full candidate trade-by-trade or equity curve; consequently **do not claim** precise lost rebound PnL, competing-trade cash allocation, or four-way exact economic decomposition.
5. Record the **missing telemetry** required for a future causal matched-path event study: candidate and baseline hour-level ledger cash, position inventory, per-symbol entry/exit, all blocked entry signals, fee/slippage by fill and later closed-candle mark prices, matching same UTC. A later non-parameter diagnostic can add read-only outputs after new evidence and QA. Do not fit new thresholds to the 52 known S01 outcomes.

## Invariants and interpretation
- Explicit `NO_STRATEGY_PROMOTION` already follows from original_32k/current normal historical end below C0, independent of further synthetic contexts. No need to spend 15 more candidate backtests on a failed AND gate.
- Terminal wealth delta includes compounding, slot competition, reinvestment and subsequent trades; not additive to event 'missed profits'. Fees are measured costs but not sufficient explanation by themselves.
- A bounded retry-on-rejection policy is a separate S01-B potential hypothesis, not silently enabled.
- Keep product/paper/live/keys/orders unchanged and never claim original development histories are OOS.
