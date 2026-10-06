# Hixton architecture — current V8 product

Status: CURRENT · 2026-10-06

## Product boundary

Hixton V8 is a 15-market USDC product composed of two deliberately separate layers:

1. **Frozen V6 Core** — ten proven Core profiles, retained as an exact regression anchor.
2. **V8 Satellite layer** — five researched Satellite profiles; only NEARUSDC and BCHUSDC are currently allowed to allocate Shared capital.

SUIUSDC, UNIUSDC and AAVEUSDC remain visible research profiles but are blocked from Shared entries.

## Strategy and routing

`src/hixton/domain/versions.py` owns immutable StrategyDefinitions. V6 must remain behaviorally identical to the prior ten-Coin product. V8 extends that profile map without mutating V6.

`src/hixton/domain/satellite_layer.py` owns the Satellite role list, active shared subset and frozen point-in-time entry/horizon rules.

At each closed 1h bar:
- Core and Satellite signals are calculated without future bars.
- fills are modeled/executed at the next available open;
- Core entries have absolute priority;
- Satellites may enter only when no Core position is active;
- an executable Core entry closes required active Satellites at that next open before allocating Core slots;
- NEAR/BCH get at most one slot per symbol.

## Capital semantics

The single authoritative input is `max_capital_usdc = X`. `CAPITAL-V1-2X50PCT` derives two equal 50-% slots. Examples: 250 → 2×125; 1.000 → 2×500. Product code must not hard-code those example amounts.

The Core allocator is `ranked_repeat`. Research showed that globally switching the Core to higher slot counts/5×50 increased activity but materially reduced robust profit, so 2×50 % remains the selected architecture.

## Backtest semantics

The primary product report window is exactly three calendar years ending at the last fully closed UTC hour. Four hundred 1h bars before the report start are warmup only. Same-base USDT history may be used as an explicitly labeled historical price proxy where a USDC listing is too young; it is never represented as historical USDC liquidity or fills.

The isolated 15×250 laboratory and the Shared-X portfolio are separate evidence products. Only Shared-X represents main-account capital use.

## Persistence and safety

Paper persists account, positions, events and per-market checkpoints atomically. Strategy version drift is fail-closed and requires audited activation; no silent reset/top-up is allowed.

Local Live execution remains separately gated by account reconciliation, source/strategy/allocator identity, emergency/risk gates and the controlled first 1×50 roundtrip. CI/swarm never has private Binance credentials and never sends orders.

## Release path

Research → causal train/validation/full/stress evidence → exact candidate implementation → Backtest/Paper/Live/UI parity → full regression → A10 synthesis → same-head A09 QA_PASS → same-head A11 GOVERNANCE_PASS → explicit code promotion → separate audited Paper activation/catch-up. Live remains disabled until explicit owner action.
