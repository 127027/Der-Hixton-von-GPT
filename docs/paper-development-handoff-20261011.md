# Paper development handoff — 2026-10-11

Use this branch for further Paper development. V8 is the current strategy; preserve common signal rules across Paper, portfolio backtest, and Live. V6 remains the frozen regression anchor. Read AGENTS.md before changing strategy or acceptance criteria.

The owner requested a clean local Paper start. Its verified seed was 1092.05773944 USDC, copied from the then-current confirmed available Binance USDC balance. Paper positions and history were archived locally and reset; checkpoints were preserved to prevent replay of old entries. Local runtime was HEALTHY, with two free Paper slots and zero initial drawdown.

This repository contains code, not the owner's private runtime database, API keys, passwords, or Binance holdings. A fresh clone does not inherit that local Paper account or any real-money entitlement. Without credentials, show “API-Key nicht vorhanden.” instead of real-account cards. Never invent a Binance balance. The seed above is a dated simulation reference, not a live balance feed.

Paper cash and equity evolve independently through simulated fills and costs; do not overwrite them every 30 seconds with Binance cash, because that would erase simulated gains/losses and corrupt open-position accounting. Fresh Binance data requires a locally configured key. Initialize a requested fresh simulation from a confirmed account snapshot, then keep simulated accounting separate.

At handoff, the local 50-USDC test was WAITING_SIGNAL and regular Live was disabled. This is local state only and must never be armed automatically from repository files. Improve and verify in Paper/public data only; do not submit orders, enable Live, change keys or restart the owner's bot as part of external development.

Validation of the preceding strategy/runtime fixes: 131 Python tests; 34 UI tests; TypeScript and UI build. Actual warm synchronization after restart was 37.8 seconds; cold startup 152.8 seconds. The real 50-USDC roundtrip was not yet complete, so no Live acceptance is implied.
