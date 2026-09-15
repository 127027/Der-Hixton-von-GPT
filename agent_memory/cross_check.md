# Final repository cross-check — 2026-09-15

This pass is the bootstrap completion audit required by AGENTS.md. It asks specifically whether repository components are orphaned, duplicated, semantically divergent, unsafe or falsely presented as complete.

## 1. UI controls without valid backend path

### Normal dashboard/markets/charts/backtests/settings
Verified wired through `ui/src/main.ts`/helpers → `ui/api.py` → RuntimeState/CandleStore/PaperStore/RuntimeSupervisor/canonical backtests. No material read surface was found to be a decorative-only control.

### Live enable / one-off real-money test
These controls have backend routes, but the backend intentionally returns blocked/409 status because release gates remain closed. This is **not an orphan** and must not be 'fixed' by bypassing the gate. UI correctly renders the blocker and does not invent a green Live state.

### Bot stop
Frontend presence/stop path is wired to VisibleSession/instance control and runtime termination; it is not a kill-all-port shortcut.

### Emergency stop
Server/Paper state supports the safety latch. Current UI no longer exposes every historical stop control described in older DMS revisions. Absence of an old visible toggle is not release of the stored safety state; current UI decisions superseded older layouts.

Conclusion: no current UI action requiring a code repair was found solely because it lacks backend wiring. The intentionally unavailable live actions are correctly fail-closed.

## 2. Backend actions without ordinary UI caller

Expected/legitimate:
- CLI data sync/audit and explicit backtests;
- `paper-fresh-start` maintenance (intentionally CLI/offline, should not be a normal UI button);
- research V4/V5/V6/V8/V9 commands;
- low-level live exchange/order primitives (deliberately not directly callable from UI);
- CLI `live` placeholder deliberately blocked.

These are not orphan bugs. Exposing low-level order primitives directly in UI would be a security regression.

## 3. Duplicate strategy/execution implementations

There is one authoritative strategy/profile/policy definition source, but multiple execution perspectives:
- single/isolated backtest engine;
- shared portfolio backtest engine;
- PaperEngine;
- unreleased trial/live order controller.

This is intentional because account/transport models differ. It is the main semantic-drift risk. Existing controls:
- independent strategy golden oracle;
- single ↔ portfolio coin parity for same rules/budget;
- Paper ↔ shared portfolio exact fill/equity parity;
- Paper restart split replay;
- same central entry priority, CoinProfile, TradePolicy and shared portfolio-risk function.

A06 must treat edits to any execution path as cross-component and rerun relevant parity tests. The swarm should not try to mechanically collapse these engines into one without a separate architecture mission because doing so could mix historically simulated execution with real transport semantics.

## 4. Paper / Backtest / Live semantic divergence

### Strategy
Active coin parameters and TradePolicy source are shared; no separate hidden Paper strategy found.

### Account model
Isolated 10×250 intentionally differs from shared Paper/portfolio 250 with slots/risk. This difference is documented and surfaced. Comparing their total return as if same account is invalid, not an engine defect.

### Shared portfolio risk
Paper and shared portfolio use the same pure risk transition; parity tests cover representative replay.

### Fill transport
Backtest/Paper use modeled next-bar-open + documented costs. Live would use actual market orders/fills and must not claim identical execution prices. Current Live remains blocked. This difference is intended.

Conclusion: known divergences are explicit model boundaries, not hidden accidental strategy forks. Future patches can still create drift; A06/A09 enforce parity.

## 5. Persisted state across restart

Persisted where correctness requires it:
- market candles/rules/revisions;
- Paper account/settings/positions/events/checkpoints/dust/strategy session/soak;
- trial intents/order journal/fills and reconciliation baseline;
- explicit runtime instance metadata for safe predecessor control.

Intentionally process/browser transient:
- WebSocket connection;
- RuntimeState cache;
- local live-auth browser session;
- unsaved UI form draft;
- currently loaded Python code.

The transient items are reconstructable and do not own exchange/Paper economic truth. A source hash guard prevents new backtest proof after an on-disk patch while old code remains loaded.

No repository-inspection-answerable critical economic state was found to exist only in unpersisted memory.

## 6. Startup/reset hazards

Ordinary startup does not reset Paper. Explicit fresh start is isolated behind stopped-runtime + exact confirmation + known-schema + verified archive/integrity/hash.

Legacy USDT Paper state is rejected before USDC mutation rather than silently relabeled.

The USDT→USDC audit proved that a new historical account starting later is a different path; it did not reveal hidden currency conversion/reset code.

Conclusion: no implicit startup reset path found.

## 7. Market-data hazards

- Provisional bars not eligible for signals.
- Gaps/duplicates/invalid OHLCV invalidate rather than interpolate.
- runtime uses REST recovery around WebSocket gaps.
- common backtest window is constrained by actual USDC availability + warm-up.
- current stored Binance filters are acknowledged as current, not historical point-in-time truth.

No synthetic history path used by canonical current runs was found.

## 8. Live/security false-positive completion

Important deliberate state:
- low-level live adapter/order journal exists;
- many fake/offline tests are green;
- runtime bridge exists;
- productive arming/submit still hard-blocked;
- UI start endpoint remains 409;
- external/Testnet/remainder/foreign-order/pre-send acceptance remains open.

This is exactly the AGENTS.md cross-check case “tests appear green while production path is intentionally disabled.” Repository docs correctly state the limitation. A09/A11 must preserve it.

## 9. Documentation contradictions/staleness

Older DMS portions mention USDT, earlier strategy IDs, 240 cash, 3-only slot limits, Windows service/24×7 operation and earlier Live architecture states. DMS 00 and decision log explicitly define chronological/source precedence; latest DEC-053/054/055/current headings plus current implementation supersede those historical statements.

No attempt should globally rewrite historical evidence to current USDC wording; that would destroy provenance. A01 should flag stale current-facing text only when it is actually presented as current, not historical.

## 10. Engineering-agent infrastructure

The former laptop-bound engineering path has been removed:
- `StartAgent.bat` removed;
- `AgentChat.bat` removed;
- `scripts/local_agent.ps1` removed;
- `scripts/agent_chat.ps1` removed;
- the local executable swarm runner removed;
- the old `codex-supervisor.yml` local-memory-only workflow removed.

The authoritative replacement is cloud-hosted GitHub Actions:
- default-branch `.github/workflows/hixton-cloud-swarm.yml` provides manual and scheduled dispatch;
- `gpt/usdc-audit/.github/workflows/hixton-cloud-swarm-reusable.yml` contains the 11-agent execution graph;
- A01-A08 run independently and read-only on GitHub-hosted runners;
- A10 works on an isolated `swarm/run-<run id>` branch;
- A09 executes deterministic QA plus independent release review;
- A11 performs final governance and triggers one automatic A10 repair loop if needed;
- successful work creates a pull request and is never auto-merged.

A GitHub-hosted runner cannot reuse the user's interactive laptop ChatGPT/Codex login. The official Codex Action therefore requires a repository secret named `OPENAI_API_KEY`. This is an external configuration requirement, not repository code.

## 11. Repository structure/orphans

All tracked application/source/test/config/workflow/documentation files are assigned in `inventory.md`. Generated UI static assets and lockfiles are grouped with clear ownership. Backtest version directories are historical/research evidence, not duplicate application entrypoints.

`Startbot.bat -> src/main.py` remains the only trading application start path. The cloud engineering swarm is CI tooling and does not create a second bot runtime entrypoint.

## 12. Test/evidence consistency

Repo-reported counts vary between historical DMS revisions (e.g. 292/19 vs later 335/22) because those sections describe different commits. Latest current README/DMS18 is the relevant historical evidence. Cloud missions must report actual fresh runner results rather than copy historical counts.

The default-branch dispatcher and reusable workflow were accepted by GitHub as a valid workflow graph: GitHub resolved the called workflow on `gpt/usdc-audit` and instantiated preflight/specialist/A10/A09/A11/repair jobs. The first validation run stopped before runner steps because the required cloud OpenAI secret was not available, leaving all downstream jobs correctly skipped rather than pretending to run agents.

## Cross-check verdict

No unresolved **repository-understanding** question remains. The remaining uncertainties are external/runtime facts:
- GitHub repository `OPENAI_API_KEY` must be configured before Codex cloud jobs can execute;
- current real Binance account permissions/filter/fee/live-order behavior;
- external Testnet/operational acceptance;
- actual operator-machine backup/restore status;
- future strategy profitability/market behavior.

The repository is structurally ready for laptop-independent swarm execution while preserving all trading/live safety boundaries. SWARM-002 is the first active engineering mission once the GitHub OpenAI secret is configured.
