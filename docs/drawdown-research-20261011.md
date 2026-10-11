# Drawdown investigation and defensive research candidate — 2026-10-11

## Result and operating state
Current V8 was reproduced exactly: shared starting cash 1092.05773944 USDC, period 2023-10-11 15:00 UTC through 2026-10-11 15:00 UTC, fifteen observed markets, two slots, compounding and quality filler screen ON. Current V8 remains the running default. The new `v8d` candidate is research-only (`paper_approved=False`); it was not installed into the owner's running bot, did not alter its frozen real-money test, and grants no Live release.

| Same three-year simulation | Ending USDC | Return | Maximum drawdown | Completed positions |
| --- | ---: | ---: | ---: | ---: |
| Current V8, full dynamic budget | 28,452.83 | 2505.43% | 47.63% | 153 |
| Defensive V8, 35% new-entry budget | 5,124.22 | 369.23% | 23.57% | 154 |
| Current V8, full dynamic budget, stress costs | 17,207.49 | 1475.69% | 60.76% | 155 |
| Defensive V8, 35% budget, stress costs | 4,378.98 | 300.98% | 26.57% | 156 |
| Reference only: current V8 without compounding | 7,182.23 | 557.68% | 17.81% | — |

The defensive candidate preserves the complete V8 coin profiles, entry filters, exits, Satellite rules, two-slot ranked-repeat allocation, and signal indicator parameters. Only the amount assigned to new entries changes: 35% of marked managed equity across the two slots, with the rest remaining simulated cash. With a fresh equity of 1092.05773944, total new-entry budget is approximately 382.22 USDC, about 191.11 per slot before fees/rounding. A sole Core entry can still consume both tranches. Profits and losses continue to change subsequent budgets. The cash reserve remains in equity and in the drawdown denominator; the reduction is not a display trick.

This is an entry-sizing rule, not a hard continuous 35% exposure cap. Positions can grow or shrink after entry; no constant rebalancing was added. Trading fees and exchange rounding affect the exact cash reserve. The independent explicit one-shot test remains a fixed 50-USDC execution test; this fraction does not shrink it into a 17.50-USDC test.

## Diagnosis
The historical worst decline runs from 2025-08-22 16:59:59.999 UTC to 2026-02-06 07:59:59.999 UTC: peak 34557.92928285, trough 18098.60436189, or 47.62821518%. The formula was verified directly against equity.csv. Current losses are measured against the previous peak, not the initial deposit.

During that interval, closed XRP, BNB and SOL trades contributed approximately -5642.79, -3447.43 and -2641.62 USDC respectively. These realized figures do not by themselves explain the entire peak-to-trough change: unrealized positions, cash, profitable exits and dust also contribute. 56 of the full run's 153 completed positions consumed both slots, so two slots often represented one concentrated asset exposure rather than diversification. Full reinvestment amplified the account path and absolute sums exposed after earlier gains. The 5% day-loss pause blocks new entries; it does not cap an existing position's loss or stop cumulative losses over many days.

## Experiments and selection
Twenty alternative configurations were tested in four explicitly recorded families, with one common baseline: close-only ATR exits; Core entry momentum/slope filters and routing; partial profit reinvestment; and smaller new-entry exposure. There were 68 historical replays in the initial families, plus four exact registered-candidate reproductions. Tests use the native portfolio engine and model costs, with no private account requests or orders.

Tighter stops and most extra filters were rejected because they increased drawdown or surrendered too much training profit. The partial-reinvestment winner without fillers looked attractive in the full period (25.74% DD) but **failed** the chronological final-year check (53.34% DD under current costs, worse than the incumbent's 37.50%). It must not be presented as accepted.

The first exit/entry/profit families required two profitable training years, at least 60% of incumbent training profit and at least 20% relative DD reduction. Those rules were not loosened to rescue their results. After those families failed, a separate, explicitly risk-prioritized exposure experiment was declared: both training years profitable, at least 20% of baseline training profit, DD at most 80% of baseline, select the lowest worst training DD. That experiment deliberately accepts a substantial return sacrifice. Exposure options were 75%, 50%, and 35%; training selected 35%. The final year was rejection-only, requiring at least 20% relative DD reduction and return no lower than min(0, incumbent return).

| Fresh last-year account, 2025-10-11 to 2026-10-11 | Return | Maximum drawdown |
| --- | ---: | ---: |
| Current V8, current costs | 3.32% | 37.50% |
| Defensive V8, current costs | 4.51% | 14.57% |
| Current V8, stress costs | -20.23% | 51.18% |
| Defensive V8, stress costs | -2.56% | 19.59% |

The candidate passed its declared historical risk check. This entire history had already been examined in earlier development, and later experiment families were motivated by earlier failures. Therefore this is **adaptive in-sample historical research with chronological rejection checks**, not pristine out-of-sample proof. No future test period has yet been observed. Chronological splitting avoids training on future observations when evaluating earlier data, as described in [scikit-learn's TimeSeriesSplit documentation](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html).

## Implementation and evidence
The shared immutable StrategyDefinition now contains a validated optional capital_exposure_fraction; the current V6/V8 payloads and profiles remain unchanged when the default is 1. Candidate v8d carries 0.35 and a separate strategy identity. Backtest, Paper and the Live controller take their sizing fraction from that definition; the Live pre-submit check enforces the same maximum. No UI auto-enablement or account migration was added. Rejected partial-reinvestment parameters remain explicit backtest research arguments, not runtime configuration.

The registered v8d candidate was rerun from the final implementation under current and stress costs, for the full period and last year. Ending equity and DD matched the selected experiment within 1e-20. Economic/data equality and restart persistence were additionally verified with deterministic Paper/backtest fixtures. Offline Live fixtures test both fixed and dynamic budgets and refusal of an excessive order, using a local fake exchange only.

Detailed machine-readable experiments and proof are in [drawdown-research-20261011](drawdown-research-20261011/). The immutable report manifests identify the modified Python source by SHA256; the Git commit field explicitly labels the research base and dirty source instead of pretending these are prior-commit QA results. VALID in a report means the historical calculation completed, not live acceptance.

The final source fingerprint is **7956f1b7c2ea1041c787313a14644da060ee3437eead077c49b163dfc42fe326**.

Current costs per side: 10 bps fee, 2 bps spread, 3 bps slippage. Stress: 10, 10 and 20 bps respectively. Older missing USDC history uses the disclosed USDT price proxy and present-day exchange rules; historical USDC liquidity is not proven. Binance explains that [market-order slippage can result from liquidity and price movement](https://www.binance.com/en/academy/glossary/slippage). Real fills are not asserted to equal the simulated next open.

Reproduce with the historical native/cache databases copied into an isolated directory:

```
python scripts/research_drawdown_20261011.py --family exposure --data ISOLATED_DATA --out exposure-results.json
python scripts/verify_defensive_candidate_20261011.py --data ISOLATED_DATA
```

Final affected regression: 168 tests passed, zero failures/errors. The 20 new/defensive tests were rerun after strengthening the oversized-order fixture and all passed. This is targeted regression evidence, not A09/A11 release approval.

Default strategies were preserved. Same-head governance/promotion and forward Paper observation remain separate release work; the candidate is not approved for normal runtime or real orders.
