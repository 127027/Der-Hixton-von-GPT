# Promotion brief — 2026-10-01

## Approved winners
Promote exactly these two research winners from COORD-2026-10-01-PROFITOPP-006:

- AVAXUSDC: VIDYA 6, momentum 20, smoothing 8, ATR 150, band 5.2, warmup 400; unchanged zeroed trade-policy extras.
- DOGEUSDC: VIDYA 6, momentum 16, smoothing 14, ATR 120, band 4.3, warmup 400; CMO floor 0.20, other trade-policy extras unchanged.

All eight other production coin profiles remain unchanged. CAPITAL-V1-2X50PCT / 2x125 ranked_repeat remains unchanged.

## Expected identity
The exact promoted V6 digest is c78c8cabf980, therefore the canonical strategy version must be:
HIXTON-V6-COIN-PAPER-1-c78c8cabf980

Any current-state evidence that still identifies b271d7952d15 is stale and cannot support release.

## Validation contract
Run fresh Preflight, exact-three-year Dashboard E2E, coin optimization/recheck and A01-A11 on the exact promotion commit. A09 must emit QA_PASS and A11 GOVERNANCE_PASS. Persistent Paper state may transition only through the exact owner-authorized b271d7952d15 -> c78c8cabf980 path, preserving history with no reset and no real/testnet orders.

## Distribution
The final user ZIP must be pinned to the exact validated commit SHA, not a moving branch reference.
