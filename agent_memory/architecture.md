# Architecture map — verified 2026-09-15

## Architectural invariant

Der Hixton has one trading application entry (`src/main.py`) and one normal Windows application starter (`Startbot.bat`). Backtest, Paper, local UI and deliberately blocked live preparation are modes/surfaces of the same application package. Research modules are invoked from the same CLI and are not independent trading programs.

The engineering-agent tooling (`StartAgent.bat`, `AgentChat.bat`, `scripts/*.ps1`, `agent_memory/`) is outside the trading execution path. It must never be allowed to become a second bot/runtime or a hidden live dispatcher.

## Top-level call graph

`Startbot.bat`
→ validate/create `.venv`
→ validate exact runtime dependency versions and built static UI
→ `python src/main.py start`
→ `hixton.cli.main()` / `command_start`
→ `hixton.ui.server.run_local_dashboard()`
→ local instance reservation / authenticated predecessor shutdown
→ FastAPI/Uvicorn + `VisibleSession`
→ trading supervisor starts only after first valid UI presence WebSocket
→ `RuntimeSupervisor.start()`
→ startup data/time/database/symbol sync
→ PaperStore/PaperEngine initialization or restart recovery
→ Binance 1h WebSocket + REST recovery + daily audit
→ API/UI reads snapshots and triggers allowed actions.

Closing the terminal or final UI tab requests orderly stop. There is no intended invisible trading process. No automatic position liquidation occurs when the process stops.

## Configuration / version ownership

`config/examples/config.example.json`
→ `hixton.config.load_config()` strict field validation
→ strategy key resolves through `hixton.domain.versions.strategy_definition()`
→ loader verifies quote, symbols, semantics, slot policy and exact strategy payload/profile definitions.

Active strategy definition is the single source for coin parameters and TradePolicy overlays. Paper, charts and canonical backtests receive this definition; research variants remain separately versioned and do not activate themselves.

Current active universe is ten ordered USDC Spot symbols. Current new-account model is 250 USDC shared Paper cash, default 3 slots × 80 USDC. Isolated canonical backtests use one 250-USDC simulated account per coin.

## Domain layer

`domain/models.py` owns typed immutable Candle/IndicatorPoint/Signal/StrategyParameters/semantics records.

`domain/strategy.py` owns deterministic VIDYA/CMO/ATR calculation, trend state, flip signals, stable signal IDs and centralized entry priority. It rejects provisional, invalid, non-contiguous or out-of-order candles.

`domain/trade_policy.py` layers explicit coin policies over the base flip signal (CMO/slope entry filters and close-based exits such as stop/trailing). It does not invent market data or exchange fills.

`domain/versions.py` owns StrategyDefinition/CoinProfile maps and release/research flags.

`domain/allocation.py` owns slot-assignment policy.

`domain/risk.py` owns pure shared-account state transition for 5% UTC-day entry pause and persistent 20% high-water drawdown halt. It is reused by Paper and shared portfolio simulation.

No network, database or UI dependencies belong in the strategy domain.

## Data layer

`data/binance.py` is public market-data/exchange-info access. Runtime may request server time, filters, historical 1h bars and stream data; no account order submit is here.

`data/quality.py` performs non-mutating strict validation. It reports rather than interpolates missing history.

`data/storage.py` owns candle/symbol-filter SQLite storage, revisions and deterministic snapshots. Read-only mode exists for research controls.

`data/sync.py` owns incremental fetch/paging/tail refresh and strict revalidation.

Provider state is not trusted merely because a request succeeded: candles are re-audited before strategy use.

## Runtime layer

`runtime/state.py` owns thread-safe observable status: application health/mode, market snapshots, event/log snippets, backtest state and stream information.

`runtime/analysis.py` derives strategy-analysis/common-window helpers without owning execution.

`runtime/supervisor.py` owns lifecycle orchestration:
- server-time drift check;
- SQLite integrity and historical sync;
- common available history/warm-up;
- exchange-rule snapshots;
- strategy/Paper startup or recovery;
- ten-market WebSocket and REST fallback;
- provisional/final bar updates;
- exactly-once Paper processing through PaperEngine;
- daily 00:05 UTC audit;
- stale/final-bar watchdog;
- backtest actions using current data/settings;
- Python source fingerprint/provenance.

RuntimeSupervisor is not allowed to silently bless code changed on disk while the old process remains loaded: source fingerprint changes require restart before a new backtest can be trusted as matching the running code.

## Paper layer

`paper/storage.py` owns account/settings/positions/events/checkpoints/dust/soak/audit persistence and atomic cycle commits. Ordinary initialize/restart is non-resetting and fail-closed on incompatible strategy/legacy state.

`paper/engine.py` receives aligned finalized market slices and actual next-bar opens. It:
- applies pending exits before entries;
- uses the same strategy/profile/policy source as backtests;
- uses central priority/allocation;
- applies shared risk state;
- applies saved slot/notional/emergency settings;
- simulates baseline costs;
- persists result/checkpoint/bar counters atomically.

Missing next-open data prevents the entire aligned slice from advancing, avoiding divergent execution reference times.

`paper/maintenance.py` is the only explicit fresh-start path: bot stopped, exact confirmation, verified non-overwriting archive, integrity/hash, known schema only. It is not called by ordinary startup/backtest.

## Backtest layer

`backtest/engine.py` is the canonical isolated/single-coin simulation path: confirmed signal at bar close, fill next bar open, Decimal cash/quantity/cost model, exchange-rule constraints, no compounding beyond available cash.

`backtest/portfolio.py` is a separate shared-account execution implementation because it must model synchronized markets, common cash, slot competition, central priority and account-level risk. It uses the same strategy/policy/risk definitions but is not literally the PaperEngine. Therefore parity tests are essential.

`backtest/reporting.py` owns immutable run bundles and provenance; `comparison.py` compares stored evidence to active strategy/code/cost/portfolio settings.

Research modules (`research.py`, `coin_review.py`, `weak_coin_review.py`, `portfolio_review.py`, `usdc_review.py`) consume canonical engines and write research evidence. They must not mutate the active Paper account or activate a strategy.

## UI / API layer

`ui/server.py` starts the localhost server and visible-session lifecycle.

`ui/instance.py` provides safe singleton/predecessor handling; unknown port occupants are not killed.

`ui/lifecycle.py` requires a real visible browser lease plus terminal presence. Trading does not start before UI presence.

`ui/api.py` exposes status, markets, chart data, backtest data/actions, settings and session actions. Local mutating calls require exact localhost Origin plus action header. Responses are no-store and security headers restrict browser use.

`ui/live.py` registers credential/account-check/trial/live-preparation routes. Live/real-order start remains fail-closed.

`ui/chart.py` aggregates only for display; native 1h strategy outputs remain the source of signals.

TypeScript source under `ui/src/` renders API truth. Production assets under `src/hixton/ui/static/` are generated build output and must be rebuilt/verified after source UI changes.

## Live preparation/security layer

This layer is deliberately separate from Paper and is not production-released.

`live/credentials.py` — Windows Credential Manager + local-password/session protection.

`live/binance.py` — signed read-only account/permission/market preflight; no order submit.

`live/exchange.py` — low-level signed order transport/parser exists, but is not sufficient authorization.

`live/orders.py` — persistent idempotent order intent/journal/exactly-once primitives; ambiguity reconciles instead of blind retry.

`live/trial.py` — exactly-one-entry 50-USDC trial controller and exit lifecycle.

`live/reconciliation.py` — establishes immutable account baseline and reconciles known bot fills/balances.

`live/runtime.py` — supervisor-to-trial lifecycle bridge.

`live/preparation.py` — composition/root service. Productive submit/arming are held behind independent hard-false release gates and documented blockers. UI/CLI cannot turn these gates on. Development agents/CI must never replace those gates with `True` merely to make a flow pass.

## Persistence ownership

- Market data and exchange-filter snapshots: CandleStore SQLite (active DB path currently USDC DB).
- Paper ledger/settings/checkpoints/soak/audit: PaperStore tables in active database.
- Live-preparation security/audit and trial order/baseline state: separate live-preparation store/Windows Credential Manager as implemented; not a second Paper account.
- Runtime instance token/metadata: ignored local runtime-session file, no Binance secret.
- Backtest/research reports: immutable directories/manifests under versioned backtest roots; large raw runs may be ignored locally.
- Generated UI assets: tracked static build output.

## Concurrency and failure boundaries

- Runtime state guarded by locks; Paper processing is serialized/aligned and persisted atomically.
- WebSocket failure switches to REST fallback and DEGRADED; successful reconnect only clears stream-owned failure, not unrelated health errors.
- Paper restart uses persisted checkpoints and replays missing finalized bars exactly once.
- Live order ambiguity is never resolved by resubmitting blindly.
- Visible-session/terminal failure stops runtime; it does not force-liquidate positions.
- Backtest/report artifacts are immutable; a repeat creates a new run ID.

## Deliberate duplications versus defects

There are separate execution loops for isolated backtest, shared portfolio backtest and Paper. This is intentional because account models differ, but they share strategy/profile/policy and (for shared models) risk semantics. The risk is semantic drift; `test_coin_engine_parity.py` and `test_runtime_parity.py` are the primary regression controls. A06 must treat changes to any one execution path as potentially affecting parity assumptions.

Research engines/screens may contain simplified screening logic before exact finalists. Their outputs are research-only and exact candidate confirmation uses canonical Decimal engines. They are not alternate production execution paths.

## Agent tooling architecture (current, pre-swarm-runner)

`StartAgent.bat`/`AgentChat.bat` call PowerShell tooling. Existing `local_agent.ps1` and `agent_chat.ps1` are single-agent mechanisms and hard-code an obsolete `agent/codex-supervisor-v1` branch. They use disposable worktrees and normal Codex/ChatGPT login, then persist allowed memory changes.

The new 11-role definitions under `agent_memory/swarm/` are governance contracts, not yet 11 running processes. After bootstrap, the existing engineering-agent entry should be upgraded rather than adding a competing bot starter. A10 will schedule role executions; A11 will audit A10 and the specialists. Patching agents must use isolated worktrees/branches or serialized ownership to avoid conflicting writes.