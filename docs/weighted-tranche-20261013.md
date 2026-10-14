# Owner-selected DD10 second-tranche allocation — 2026-10-13

The owner explicitly requested installation, restart and transfer of the newly armed
single 50-USDC test to the new source/strategy on 2026-10-13. This is a strategy change,
not a repair to V6 or original V8. Continuous Live is not automatically enabled.

Active optional v8r: HIXTON-V8-LINK8-ATR075-DOGE50-DD10-PAPER-3.
Allocator: CAPITAL-V2-HALVES-REST-DD10. Old DOGE50 and ATR075 trial contracts remain
registered for owned-position continuation. A flat waiting test cannot certify new code.

## Shared rule

Keep two primary halves. At a finalized strategy-reference drawdown of at least 10%,
use 50/25/25 only if at least three ranked, eligible, distinct fresh candidates exist.
If exactly one intact half remains, split the free half into 25/25 only with two valid
new alternatives. Otherwise preserve ranked-repeat allocation, including a lone Core
using both original halves. No position is resized or liquidated to change capacity.
Quarter exits release only their own capacity. ATR075 sizing and Binance filters still
apply after allocation. No new research-only market, news model, permanent four slots
or BNB cost scenario was added.

The twenty internal capacity units represent one whole budget, not twenty positions.
Paper and Live persist each entry's units. Live consumes the same immutable, version-
and closed-bar-bound Paper strategy reference for the DD trigger. Missing reference
waits without consuming the signal; exits and reconciliation stay available. The
original native cash/rounding sizer handles all budgets, with fractional reserve for
quarter-tranches. Legacy profiles retain their old configuration and constraints.

Automatic available-USDC budgeting and the quality filler flag are distinct persisted
settings. The new implementation supports both settings in the production adapter.
Their values are frozen in the Live capital contract; changing one requires re-enable.
The local authenticated Live button still requires the fully reconciled current-source,
current-strategy, current-allocator 50-USDC BUY/SELL roundtrip and fresh account preflight.
Source changes, uncertain orders, manual baseline changes and insufficient cash still
block new orders. Foreign holdings remain untouched. The one-shot test remains exactly
one 50-USDC buy followed by the normal strategy exit; it cannot alone demonstrate all
three concurrent positions, which are covered by independent fake-exchange tests.

## Historical evidence

Market-only frozen snapshot, 2023-10-11 19:00 UTC to 2026-10-11 19:00 UTC, 400 warmup
bars, seed 1092.05773944 USDC, disclosed USDT continuity where USDC history is absent.
Accepted predeclared candidate A_DD10, selected on two fresh-account stress training
periods before final-year/full evaluation; examined history is not an unseen holdout.

| Model | Normal end USDC | Normal max DD | Stress end USDC | Stress max DD |
| --- | ---: | ---: | ---: | ---: |
| DOGE50 incumbent | 32469.39 | 39.13% | 22817.49 | 48.57% |
| DD10 second half | 33188.15 | 38.22% | 23314.51 | 47.75% |

Only four full split decisions occur per cost scenario. This modest sample is not a
profitability forecast or a 10% maximum-loss guarantee. The last-year stress probe
still loses money relative to its fresh starting account despite improving on baseline.

The product replay equals the frozen research model's entire equity curve and fills.
The independent three-year Paper replay matches end equity and all 305 normal-cost
fills by symbol, side, time, quantity and execution price. The existing Paper/Backtest
forced-handoff audit namespaces differ for 32 exits; verification normalizes only those
IDs from the identical Core trigger and execution boundary, without changing decisions.
Normal signal IDs remain exact. Historical reports retain their original identities.

Local installation QA includes complete Python syntax/Ruff/mypy/pytest and UI tests,
TypeScript checking and a rebuilt bundle. Local results are not an A09/A11 cloud
certificate; no old QA/governance report is relabelled as approval for this patch.
The existing gpt/usdc-audit promotion chain is not bypassed.
