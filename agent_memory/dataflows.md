# Hixton data flows — current V8 product

Status: CURRENT · 2026-10-06

## Market data

Public Binance USDC candles/exchange filters → quality audit → SQLite candle store → per-market indicator state. Only finalized 1h candles enter strategy logic. The next candle open is the execution reference; its future high/low/close are not available to the decision.

For old history that predates a USDC listing, same-base Binance USDT candles may be used only as an explicitly labeled price-history proxy in research/backtest evidence.

## Strategy

Frozen V6 Core profiles + V8 Satellite profiles → indicator/policy decisions.

Core symbols: BTC, ETH, BNB, SOL, XRP, ADA, LINK, AVAX, DOT, DOGE.  
Satellite research symbols: SUI, NEAR, UNI, AAVE, BCH.  
Shared-active Satellites: NEAR, BCH only.

Inactive Satellites may be calculated/displayed for research but are blocked before capital allocation.

## Shared portfolio

Closed-bar decisions → natural exits → Core-entry check → strict Core handoff of Satellite positions at next open → two-slot Core allocation. If no Core position/signal owns capacity, valid NEAR/BCH entries may use free slots one per symbol.

`max_capital_usdc = X` → `CAPITAL-V1-2X50PCT` → two slots of X/2. The same derived plan is used by Shared backtest, Paper and guarded Live.

## Paper

V8 market analysis → point-in-time routing/risk/slot gates → next-open simulated fill → persistent position/event/account/checkpoint transaction. Restart restores the ledger and replays only missing finalized bars. A V6→V8 change requires explicit audited strategy activation; no reset is allowed.

## Backtest

Two evidence views remain distinct:
1. isolated 15×250 diagnostics/research;
2. one Shared-X product portfolio.

Baseline and stress cost models are separate. Position-cycle count and slot-trade count are separate. Historical outcome is evidence, not future knowledge available to runtime.

## UI/API

Runtime state + all 15 market profiles + explicit CORE/SATELLITE role + `shared_active` flag + Paper portfolio/events + data quality + current V8 backtest evidence → local API → TypeScript UI. The normal product selector exposes current V8 only; V6 remains a code/test regression anchor, not a selectable current product.

## Agent flow

GitHub Actions → exact-head lifecycle/preflight → A01–A08 specialist evidence → A10 synthesis/repair routing → A09 independent QA → A11 governance. Any code patch invalidates affected downstream evidence.
