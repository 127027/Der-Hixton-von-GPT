# Read-only diagnosis: USDC performance and Paper activity

## Follow-up: newly executed runtime backtests, 14 September 15:07–15:09 Berlin

Owner explicitly requested complete reruns. Used the existing local authenticated-
origin/action-header route `POST /api/backtests/run`, not a code/config change.
No production source, strategy, settings, Paper balance or process restart changed.
Initial POST omitted the action header and was rejected; corrected request used
the documented local-ui-v1 header. No bypass or application protection change.

Completed and retrieved fresh manifests/results:

- All ten isolated coins: `52172ca2-0cc5-47b2-8c70-e9beaf003775`.
- Shared 3x80 portfolio: `cb756729-d15f-4f84-b437-db5bdc7a59d0`.
- Separate ETH single mode: `9c34650f-53cd-4a93-a6e6-4ddeb174b315`.

All under `backtests/v6/runs/`, each with baseline and stress. Actual common window:
2024-03-24 00:00 UTC to 2026-09-14 13:00 UTC (end exclusive). This is NOT a full
three-year test. Active app remains 0.4.9 / V6-USDC d57f88ec2e5f. Python source
fingerprint `f5fc60b6ca9bd0d0d6eb1818330dd0ace226cb4ef062d0404aeb3cf9cec8459a`.

| Coin, initial 250 USDC each | Baseline end | Closed trades | Max drawdown % | Stress end |
| --- | ---: | ---: | ---: | ---: |
| ADA | 340.54 | 49 | 50.77 | 258.72 |
| AVAX | 182.09 | 36 | 54.10 | 148.12 |
| BNB | 264.91 | 37 | 44.62 | 219.40 |
| BTC | 349.24 | 35 | 28.29 | 300.53 |
| DOGE | 633.37 | 38 | 34.04 | 583.52 |
| DOT | 165.32 | 50 | 74.17 | 121.54 |
| ETH | 573.70 | 30 | 32.51 | 527.73 |
| LINK | 370.29 | 46 | 46.16 | 279.60 |
| SOL | 571.90 | 49 | 21.71 | 507.15 |
| XRP | 552.76 | 73 | 36.81 | 372.85 |

Shared portfolio starts with 250 USDC and configured 3x80 notional:
baseline end 203.712064581145 USDC, -18.515174167542%, 14 completed trades,
20.8315621291% maximum drawdown, halt 2024-05-01 19:59:59.999 UTC.
431 subsequent signals blocked by MAX_DRAWDOWN_20_PERCENT.
Stress end 203.3215552696084 USDC, -18.6713778922%, 11 completed trades,
20.3736971863% maximum drawdown, halt 2024-04-30 12:59:59.999 UTC.
More expensive costs lead to an earlier halt, so stress maximum drawdown need
not exceed baseline maximum drawdown. Halt is not an automatic liquidation.

ETH separate single mode matches its batch baseline and stress ending equities
exactly (573.7027296753955 / 527.733280895053), 30 trades each, matching source
hash. This tests the selected single/batch consistency, not all external Live
execution paths or a future-profit guarantee.

After all runs: `/api/status` HEALTHY, COMPLETE, no last_error; Paper still has
one open SOL position, completed XRP trade and unchanged 3x80 settings. Equity
at final check approximately 243.02 USDC (-6.98 from start), current drawdown
2.79%, not halted. Quotes fluctuate; these are snapshots, not closed profits.

`/api/markets` explains idle slots: BTC/ADA/LINK/AVAX/DOT last BUY flips predate
Paper activation, BNB/DOGE last flips DOWN, ETH's new BUY failed slope policy,
SOL owns a position, XRP was stopped and waits for a new flip. A current UP
trend is not a repeated entry trigger. This confirms reported last-signal
state, not a full historical replay of every intrabar/processing event.

Operational observation: two five-second GET status/market requests timed out
during the batch calculation; later requests succeeded, and all runs completed.
Do not claim a permanent crash. CPU/runtime responsiveness under backtest load
still merits separate investigation before unattended Live approval.

Remaining source/UI fixes are not implemented by these reruns. The explicit
current-settings/source freshness label and strategy robustness remain open.

Verified 2026-09-14, local branch `agent/codex-supervisor-v1`, HEAD `e2d2931`.
Application responds at localhost:8765 as 0.4.9, strategy V6 USDC d57f88ec2e5f,
HEALTHY/PAPER/LIVE_DISABLED. No restart, settings change, order or backtest POST
was performed. Bootstrap is not complete; production changes await clarification.

## Actual Paper activity (authoritative running API)

`GET /api/paper/events`: 11 September 2026, Europe/Berlin:

- 16:00 SOLUSDC ENTER_LONG FILLED, target approximately 80 USDC.
- 16:00 XRPUSDC ENTER_LONG FILLED, target approximately 80 USDC.
- 21:00 XRPUSDC EXIT_LONG FILLED, POLICY_STOP_ATR, realized PnL
  -3.79758696356518018018018018 USDC.
- ETH entry at the same signal boundary rejected by POLICY_VIDYA_SLOPE.

`GET /api/status` at approximately 08:48 Berlin on 14 September:
one open SOL position, cash 166.212584896615 USDC, marked equity approximately
243.59 USDC (variable with live prices), initial equity 250 USDC. Three slots,
80 USDC per entry, no emergency stop, no permanent or daily loss halt.
120 processed closed hourly bars per coin since activation on 9 September.
Thus the assertion that no Paper trade occurred is contradicted by actual fills.
This does not prove every potential signal was processed correctly; a full
same-window Paper/backtest event replay remains required.

## Historical comparison

Old portfolio `56a34f10-58fa-4968-9b24-59e430196c6d`:
USDT, 2023-09-01 12:00 UTC to 2026-09-01 12:00 UTC.
New portfolio `ec2c28e3-1ee1-4d15-a195-f13a91bfb6e7`:
USDC, 2024-03-24 00:00 UTC to 2026-09-10 20:00 UTC.
250 initial, 3 slots, 80 notional; end 203.689604069145 USDC, 14 closed trades.
Risk halt 2024-05-01 19:59:59.999 UTC; 429 entries rejected by MAX_DRAWDOWN_20_PERCENT.
Historical halt does not set the current Paper account's halt flag.

Old single-coin table identified in `bcb8df12-d33e-4bc7-9642-d353db3b2759`;
new table in `3cf436d4-53d8-43c7-a627-0c3fa27648bb`. Actual start dates differ.
All parameter and trade_policy fields of all ten old USDT profiles were compared
field by field with running `/api/status.strategy_profiles`, mapping quote suffix
only: no changed values. JSON string-order comparison is not a valid comparison.

Existing frozen-profile transfer study (not a new run):
`backtests/v7/runs/385bc1f7-4dca-4dcd-a138-3c33bd9c7da8/summary.json`.

| Same-window portfolio baseline | USDC end | USDT end |
| --- | ---: | ---: |
| 2024-03-24 to 2026-09-08 | 203.83, 14 trades, halted | 201.24, 9 trades, halted |
| Last 365 days ending 2026-09-08 | 211.01, halted | 232.62, halted |
| Last 90 days ending 2026-09-08 | 263.83, no halt | 259.24, no halt |

Inference: the dramatic full-history discrepancy is not evidence that changing
the quote alone broke strategy parameters. Starting the strategy in another
market phase and the persistent risk halt are material. Robustness is poor in
several start windows even on USDT. No future profitability follows from these
results. Study limitations include research-selected profiles, current rather
than historical exchange filters, and modeled commissions.

USDC common history is constrained by DOGEUSDC first downloaded bar
2024-03-07 08:00 UTC plus 400 warmup hours. Seven pairs lack the full requested
three years. `RuntimeSupervisor._synchronous_backtest` derives a common actual
report start from the latest warmup requirement across all ten symbols.

## Confirmed display/freshness gap, not yet patched

`ui/src/main.ts::refreshBacktests` renders `response.runs[0]` as latest metrics.
`ui/api.py::_list_backtests` filters test mode/symbol and preserves original quote,
but does not compare the manifest's current strategy/settings/source hash with
the running bot. Old USDT results must remain USDT, but must not be presented as
current USDC evidence. Existing manifest hashes are available for a freshness
classification. Future patch: explicitly current-settings match/stale/unknown,
actual dates and quote beside headline metrics; old runs retained as archive.
New runs must use current settings; changing code must not rewrite historical
reports or falsely mark previous results current. Full replay/regression tests
are still needed before declaring simulation/runtime parity.

## Authorized follow-up completed: V8 research

Owner explicitly approved isolated weak-coin research despite learning-only
bootstrap on 14 September; the exception was announced before editing. This
does not authorize real orders or completion of the bootstrap flag.
Implemented `backtest research --study v8` through existing CLI, with a read-only
consistent SQLite snapshot, six predeclared candidates each for DOT/AVAX/BNB,
training-only selection and unchanged canonical single/portfolio engines.
88 single computations and eight portfolios completed; full report and rules
under `backtests/v8`. All three selected stop4 candidates fail acceptance;
the combined portfolio fails too. No Paper setting/profile/account or live
change. 304 tests passed, one skipped; Ruff and mypy pass. Source fingerprint
is recorded in the curated report. Actual runtime remains 0.4.9/V6/HEALTHY/PAPER,
one SOL position, one closed XRP trade. No restart was necessary for research.

Do not retroactively select a different candidate from the inspected validation
window and present it as untouched validation. A next study could inspect losing
entry regimes (including ADA's weak recent window) and prospective validation.
Prior staging commit d3d68f3 (0.4.10) is not installed here; preserve this branch
and its Agent files. UI freshness and full runtime/adapter parity remain open.

## 15 September: authorized provenance/parity patch and actual laptop runs

UI freshness issue above is now addressed by `backtest/comparison.py`,
`ui/api.py` and `ui/src/backtest-context.ts`: compare active profiles/semantics,
quote, Python hash, explicit costs; portfolio also slots/notional/start cash.
Missing proof is UNVERIFIED, differences DIFFERENT. Old reports unchanged.
Supervisor captures source fingerprint on construction and rejects backtests
after disk Python changes until restart; reporting accepts that loaded hash.
UI clears old comparison on selection/loading failure, rather than retaining
an unrelated affirmative message.

`tests/test_coin_engine_parity.py`: 20 controlled actual-engine comparisons,
ten coins times two cost models. Equal synthetic data, one active coin, cash,
notional and aligned account limits yield identical signals/fills/trades/equity.
Risk disabled only in this test to align isolated account semantics. Not a
claim of full Paper/Live/restart parity. 333 Python passed / one skip, 21 UI,
Ruff/mypy/TypeScript/build pass. Bootstrap remains incomplete.

Old USDT reference 56a34f10 reconstructed from matching original candle hashes:
733.30648172557635 baseline/187 trades, 564.8193836271619 stress/25. Diagnostic
in-memory symbol adapter for current USDC validator; prices/economic quote
unchanged USDT, never a real USDC report. Curated proof in backtests/v8/reports.

Actual Startbot started visibly 15 September 08:39:57 Berlin, connected visible
UI kept open. HEALTHY/PAPER/LIVE_DISABLED, V6 and 3x80 unchanged, one SOL open
and one XRP closed, no resets/orders. Source hash
343d2ef7a43e770c78dd70ec8a2faec94c858932192c0f21e66a1af437cef19f.
Normal API portfolio run 8b9018d0-3914-4af2-831b-a8904c3ea64a and batch run
e5729c9f-b72d-465d-8fee-58739096f581 complete, both MATCHING, baseline/stress.
Window March24,2024 to September15,2026 08:00 Berlin. Portfolio203.72/14/DD20.83%
with May1,2024 halt; batch4004.18/443, not same capital or risk model. DMS18
contains full per-coin values and next-work limits. No V8 promotion. No commit
or push performed in this work yet; preserve current branch and uncommitted patch.

## Slot-capacity follow-up 15 September

Twelve offline controls on the exact 8b9018d0 window/data: 1/3/6/9 slots,
3-slot risk-off attribution and ADA-only with portfolio risk, baseline/stress.
V6 unchanged. Report: backtests/v8/reports/slot-capacity-audit-20260915.json.
3x80: 473 BUY candidates = 14 fills + 431 risk blocks + 24 policy + 4 capacity;
no missing/unaccounted BUY. Slots reach 3/6/9 in respective baselines.
Risk-off: 197 completed,223.10 equity,54.28% DD; stress184/156.23/63.69%.
Not authorized for promotion. Largest realized losses LINK/BNB/DOT.

Actual V6 Paper replay on full same historical USDC window: exact 28 fills
(IDs/prices/quantities) and equity203.718610797945; same after splits at candle
indices900 and1800 (connections reopened). Temporary accounts only. Evidence
paper-portfolio-parity-20260915.json. Scope does not include live/reconciliation
or intrabar monitoring. No lost-slot implementation bug found in this path.

UI now renders max concurrent and block counters via portfolioBlocksText;
clears on selection/error. 22 UI tests/TypeScript/build pass, visually verified
in running HEALTHY/PAPER/LIVE_DISABLED instance. No Python trading edits, no
restart needed. DMS06/18/README/CHANGELOG synchronized. Next research should
target losing entry regimes/overlap; profitability remains unresolved. Keep
bootstrap incomplete and preserve all prior changes. No commit/push this turn.

## V9 portfolio-first follow-up

Owner requested iterations toward old USDT gains. Added bounded ten-policy
study through existing CLI, portfolio_review.py; common profiles untouched.
28 portfolios /80 singles complete; stress-training-only selection trail4.
Full baseline265.59/123 trades improves, full stress218.45 and later baseline
208.99/33 trades loses vs current220.72/15. Gate false; no promotion/reselection.
Four separately declared risk-off sensitivity runs: full262.03/313/DD35.61%,
stress165.18/290/DD52.19%; later206.86/165.92. No recovery-to700 evidence.
Complete reports/protocol under backtests/v9. During first run only typed
parameter construction/log formatting changed; original starting hash retained.
335 Python pass/one skip (336 collected), Ruff/mypy55 pass. No UI source edit
this turn. Owner's profit target NOT achieved; don't claim project complete.

Visible Startbot restart15:58:38 Berlin, HEALTHY/PAPER/LIVE_DISABLED. Normal
portfolio e549a5d0 and batch b975692b complete/MATCHING through16:00 Berlin:
203.70/14 vs3994.68/443. Current source fingerprint a2eced48a11bbf6ddf678244b37bfe21f9501649ae91ff8a3e04eaa9295a3c9b.
Existing accounts/positions and V6 unchanged. Future work requires a genuinely
new justified hypothesis/prospective validation, not reselecting on already
seen validation to obtain a desired terminal balance. No commit/push this turn.

## Fresh quote-migration audit and owner-requested push, 15 September

Current source a2eced48 reproduces original USDT portfolio733.30648172557635
and isolated7152.2937084475909 exactly; baseline/stress terminal values and
trade counts all match both original reports. Profiles and candle hashes match;
current pair execution filters equal. Six portfolios plus60 singles completed.
Same end Sep1,2026 12UTC; Mar24,2024 restart: USDT201.11/batch4118.70 vs
USDC203.62/batch4007.26. Original portfolio already681.09 at first Mar24 close.
Symbol adapter used only in memory for current market validator, prices retain
USDT economic meaning. Engines select identical400-bar warmup per report start.
Original commit unknown; code diff against226be5b shows no numeric profile,
cost or risk changes, trade_policy unchanged. No blanket live-parity claim.
Curated report and DMS18 preserve evidence. Full tests335pass/1skip, UI22pass,
Ruff/mypy/TypeScript pass. Owner explicitly requested publishing all pending
code/docs/reports to existing GitHub branch; never include local data/secrets.

Fetch discovered origin/agent/codex-supervisor-v1 advanced to0cc1966 with
separate live/testnet changes and another agent's bootstrap completion record.
Do NOT overwrite or merge unvalidated execution changes into running laptop.
Publish this tested e2d2931-based work to codex/backtest-audit-20260915 instead;
integration with that remote work remains separate. Local bootstrap record
reflects this audit's limited inspection, not a denial of remote agent work.
