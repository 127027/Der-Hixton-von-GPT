# Hixton data flows — current V6 product

Status: CURRENT · 2026-09-26

## Market data
Public Binance USDC candles and exchange filters -> data quality -> SQLite candle store -> indicator analysis. Only finalized 1h candles enter signal logic; the next bar open may be used as the execution model reference.

Where a three-year research window predates a USDC listing, a same-base Binance USDT price path may be used only as an explicitly labelled research proxy. It is never stored or described as historical USDC liquidity/fills.

## Paper
Canonical V6 profile map -> indicators/signals -> risk/slot gate -> simulated fill -> position -> strategy exit -> realized PnL -> atomic SQLite persistence of account, positions, events and checkpoints.

Restart restores the same account and replays missed finalized bars exactly once. A canonical V6 digest change is fail-closed until explicit audited `paper-activate`; no silent reset is permitted.

## Backtest
The same canonical V6 map and execution semantics feed:
1. single 250-USDC coin tests;
2. isolated 10×250 diagnostics;
3. shared max-budget `CAPITAL-V1-2X50PCT` / `ranked_repeat` portfolio tests.

Baseline and stress cost models are separate. Position-cycle count and slot-trade count are separate metrics.

## Optimization
Per coin: bounded candidate catalog -> training A/B ranking -> frozen Top-K -> validation baseline/stress -> full-three-year baseline/stress -> robust finalists.

Each robust finalist then changes only one coin in the canonical max-budget portfolio map. Only non-regressive baseline+stress candidates may enter combination assembly. Every addition is re-tested against the already assembled portfolio. Final promotion additionally requires isolated 10×250 baseline/stress non-regression.

The optimizer emits research evidence only; it does not automatically activate a strategy.

## UI/API
Runtime state, market profiles, Paper portfolio/events, data quality and current V6 backtests -> local API -> TypeScript UI. Normal product UI/API/CLI expose only current V6; historical/research strategies are not selectable.

## Agent flow
GitHub Actions -> lifecycle/preflight -> A01–A08 specialist evidence -> A10 evidence/repair audit -> A09 independent QA -> A11 governance. Current role execution is deterministic and requires no OpenAI key or Binance private credential.
