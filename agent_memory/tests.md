# Test map and evidence boundaries — verified 2026-09-15

## Quality gate

`scripts/qa_gate.sh` is the baseline repository-wide static/test gate:
1. compile Python sources;
2. Ruff on `src` + `tests`;
3. mypy on `src`;
4. pytest;
5. UI Node tests;
6. TypeScript check;
7. production Vite build.

This is necessary but not sufficient evidence for a trading change. A09 must add affected-domain parity/runtime/provenance checks and A11 must verify they actually ran.

Current repo-reported latest audit evidence in README/DMS18 is roughly 335 Python tests + one optional skip and 22 UI tests with Ruff/mypy/TypeScript/build passing. These counts are historical committed evidence until rerun on the GPT branch; do not report them as newly executed by the swarm.

## Independent oracle / domain tests

- `tests/golden_reference.py` — independent deterministic strategy reference fixtures/oracles used to avoid merely comparing implementation to itself.
- `test_domain_models.py` — typed domain validation/record invariants.
- `test_strategy_golden.py` — 1200-bar parity on every market against independent reference; Pine-v6 reference; batch vs chronological replay equality; warm-up; stable signal IDs; reject provisional/invalid/gapped input; ranking rounding.
- `test_trade_policy.py` — TradePolicy entry/exit filters, causal behavior, version gates and single/portfolio parity of policies.
- `test_coin_profiles.py` — full versioned V6 per-coin profile propagation/invariants and version identity.
- `test_allocation.py` — one-per-symbol/ranked-repeat allocation rules.
- `test_risk.py` — 5% daily pause resets on next UTC day; 20% high-water drawdown halt remains persistent after recovery.

Proof boundary: these prove deterministic calculation/rules on tested fixtures, not market profitability or live execution.

## Data tests

- `test_binance_adapter.py` — public market-data/exchange-info parsing, request/response behavior and adapter boundaries.
- `test_data_quality.py` — gaps/duplicates/invalid/provisional/time-window quality checks.
- `test_storage.py` — CandleStore schema/roundtrip/read-only/revision/integrity behaviors.
- `test_usdc_review.py` — USDC universe; later listing/common-window selection; preserve gaps/no synthetic fill; invalid latest/provisional/warm-up fail closed; canonical engines use USDC; validation study isolated from runtime account.
- `test_usdc_runtime_migration.py` — actual common warm-up/report start logic, gap/tail failures, credential namespace continuity and legacy USDT Paper DB rejection before mutation.

Proof boundary: current exchange status/filters/account permissions remain runtime facts and must be rechecked live when relevant.

## Backtest tests

- `test_backtest_engine.py` — next-bar-open simulation, cost/cash/fill/state mechanics and backtest invariants.
- `test_backtest_reporting.py` — immutable report structure/manifest/provenance output.
- `test_backtest_comparison.py` — MATCHING/DIFFERENT/UNVERIFIED comparison against strategy/code/cost/portfolio settings.
- `test_cli_portfolio.py` — CLI portfolio setup, saved Paper settings vs config fallback and command behavior.
- `test_coin_engine_parity.py` — every active coin × baseline/stress: with equal budget/rules and portfolio-account risk disabled only to isolate execution equivalence, single engine and shared portfolio produce identical signals, fills, trades and ending equity.
- `test_portfolio_review.py` — portfolio-first research/report methodology helpers.
- `test_weak_coin_review.py` — bounded V8 weak-coin study selection/report behavior.

Proof boundary: isolated 10×250 and shared 3×80 are intentionally different account experiments. Equal signal rules do not imply equal PnL/trade count when account/slot/risk state differs.

## Paper tests

- `test_paper_engine.py` — first startup does not backtrade history; restart checkpoint exactly-once; deterministic priority/slots; exit-before-entry; settings cannot invent cash; explicit strategy activation; account/session/version guards; Paper-approved strategy enforcement; persistent soak behavior.
- `test_paper_maintenance.py` — explicit fresh-start confirmation, archive/hash/integrity, known-schema-only reset and preservation of market data/non-Paper state.
- `test_runtime_parity.py` — canonical Paper vs shared portfolio fill/equity parity on equal historical inputs; split/restart replay produces identical account/positions/dust/event identities; actual-next-open timing/execution-model metadata; live-candle expiration and migration/parity guards.

The committed actual-USDC replay evidence additionally records exact 28/28 fill parity and 203.718610797945 ending equity, including interrupted processing replay.

Proof boundary: tested historical replay does not prove every real-time outage/intrabar/live account state.

## Runtime/visible-session tests

- `test_visible_session.py` — no trading before UI; same-origin/shutdown token/instance checks; multi-tab/reload grace; explicit stop; missing/broken terminal stops safely; successor metadata; unknown port owner is never killed.
- Runtime-related portions of `test_runtime_parity.py`, `test_ui_api.py`, `test_binance_adapter.py` cover freshness/source/fallback-facing contracts.

Proof boundary: repository tests use controlled fixtures/mocks. A05 needs actual runtime observation to claim an operator instance is currently healthy.

## UI/backend tests

- `test_ui_api.py` — status/markets/backtest filters, chronology, strategy/test-type selection, settings API, route/response security and live-preparation fail-closed behavior as covered by current suite.
- `test_ui_chart.py` — chart range/aggregation/native-signal semantics, provisional handling.

Node/UI tests:
- `ui/tests/dom-harness.mjs` — lightweight DOM/fetch harness.
- `backtest-context.test.mjs` — provenance/model-scope/block-reason rendering.
- `market-signal.test.mjs` — last-trend/signal wording semantics.
- `session-lifetime.test.mjs` — browser presence/stop/reload/process-change behavior.
- `settings-draft.test.mjs` — draft survives polling/error; success adopts server state.
- `settings-flows.test.mjs` — end-to-end front-end settings/auth/live-preparation state transitions using mocked transport.

Proof boundary: UI harness tests do not prove a real browser/operator machine or Binance account. TypeScript source changes additionally require production bundle rebuild.

## Live preparation / unreleased execution tests

- `test_live_exchange.py` — signed transport/request parser/host/response semantics with fake HTTP; no external order.
- `test_live_orders.py` — immutable intent/client ID, concurrent submit claim exactly once, release gate blocks submit, timeout/restart no rebuy, partial-fill dedup, missing fill details, terminal-state monotonicity, fee asset correctness, exit only received base, quote precision and legacy migration.
- `test_live_preparation.py` — local password/session/vault boundaries, read-only account checks, fail-closed live/trial API, settings persistence/no account reset, runtime adapter/preflight constraints.
- `test_live_reconciliation_runtime.py` — baseline/balance/known-fill ownership/restart/runtime bridge scenarios and mismatch handling.
- `test_live_trial.py` — one-entry 50-USDC trial controller, candidate ranking/policy parity, restart/entry-stop/exit state machine and blocking rules.

Proof boundary — critical: all productive live-order tests use fake/synthetic exchange responses. Current start endpoint remains 409 and productive submit remains hard-blocked. These tests are not Binance Testnet/account/order acceptance and must never be described as real-money readiness.

## Configuration/package tests

- `test_config.py` — strict config keys/types/current active strategy payload and invalid configuration rejection.
- package/build configuration is additionally validated by static tools and startup dependency checks.

## Regression incidents already encoded

Existing tests/reports cover the classes the swarm must preserve:
- strategy batch/replay drift;
- Paper/backtest drift;
- Paper restart duplicate processing;
- missing next-open reference;
- stale/provisional/gapped candles;
- slot priority/cash over-allocation;
- quote migration/history truncation/legacy-account confusion;
- source-code provenance changed while runtime still loaded;
- stale UI/backtest context;
- duplicate live submit after timeout/restart;
- unsafe hidden runtime/duplicate instance;
- fake live state despite blocked release.

The USDT→USDC incident is now an explicit swarm system regression: same-window quote comparison + start-state/path analysis must prevent diagnosing `733 -> 203` as a currency-conversion bug.

## Coverage gaps / evidence that tests intentionally do not prove

1. No complete real Binance/Testnet pre-send/fill/remainder/foreign-order operational acceptance.
2. No full operator-machine external backup/restore gate evidence in repository alone.
3. Not all possible long-running network/power/sleep/outage sequences are covered by one historical Paper replay.
4. Current exact Binance filters/account fees/permissions are time-varying runtime facts.
5. Historical research has been inspected repeatedly; many periods are not untouched holdouts.
6. Strategy profitability/optimality is never guaranteed by green code tests.
7. Separate Paper/shared/isolated execution implementations can drift in future; parity suites must be rerun after relevant patches.
8. Current single-agent engineering scripts have no test for 11-agent orchestration yet; SWARM-001 must add such tests after bootstrap.

## Required A09 selection by change type

- Domain/strategy/policy/risk: golden + policy + risk + coin-profile + single/portfolio parity + Paper/portfolio parity + backtests affected.
- Market data/storage: data-quality + storage + Binance adapter + runtime migration + affected backtests/Paper startup.
- Paper/storage: Paper engine + maintenance if relevant + runtime parity + restart split replay.
- Backtest/reporting: engine/reporting/comparison/CLI + strategy/parity controls.
- Runtime/lifecycle: visible-session + runtime parity + UI API + startup/recovery scenario.
- UI/API: UI API/chart + Node tests + TypeScript + production build; backend regressions based on changed contracts.
- Live preparation: all relevant live_* tests plus explicit confirmation productive release gates remain closed unless the owner separately commissions/reviews that work.
- Agent infrastructure: pure orchestration state-machine tests, isolated-worktree safety, branch selection, heartbeat/stall/reopen/QA/governance scenarios; never use real trading execution as the agent-runner test.

## Anti-vacuity rule

A09 must reject a passing test that does not exercise the claimed path. Examples: zero-signal fixture used to claim fill parity; fake exchange used to claim Binance acceptance; historical run with a different start state used to claim quote regression; UI text test used to claim backend state. Tests must include a positive event where necessary and verify the relevant identity/economics, not merely no exception.