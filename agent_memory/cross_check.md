# Final repository cross-check — 2026-09-15

This is the completed repository-understanding and cloud-swarm safety audit.

## UI/backend wiring

Normal dashboard, markets, charts, backtests and settings are wired through TypeScript/API to RuntimeState, CandleStore, PaperStore, RuntimeSupervisor and canonical backtests. Live controls have backend routes but intentionally remain blocked; that is a safety property, not an orphan to be bypassed. Bot stop is wired through visible-session/instance control rather than a kill-all-port shortcut.

Expected backend-only actions include data sync/audit, explicit backtests, offline Paper fresh-start maintenance, research commands and unreleased low-level live primitives. Exposing those low-level primitives directly to UI would be a regression.

## Execution-model boundaries

There is one authoritative strategy/profile/policy source but several execution perspectives: isolated backtest, shared portfolio backtest, Paper, and unreleased trial/live execution. This separation is intentional because account/transport models differ. Semantic drift is controlled by golden, coin-engine parity, Paper/portfolio parity and restart replay tests.

Isolated 10×250 and shared 3×80 are intentionally different account models. Comparing their returns as though they were the same account is invalid. Backtest/Paper use modeled next-bar-open costs; future Live uses actual market fills and therefore must not promise identical fill prices.

## Persisted state and restart

Economic state that must survive restart is persisted: candles/rules/revisions, Paper account/settings/positions/events/checkpoints/dust/session/soak, and trial/order/reconciliation state. WebSocket connections, runtime caches, browser sessions and unsaved UI drafts are intentionally transient and reconstructable.

Ordinary startup never resets Paper. Fresh start is an explicit stopped-runtime maintenance action with confirmation and archive/integrity checks. Legacy USDT Paper state is rejected before USDC mutation rather than silently relabeled.

## Market-data boundary

Provisional bars cannot signal; gaps/duplicates/invalid OHLCV invalidate rather than interpolate; runtime has REST recovery; common backtest windows follow actual USDC availability plus warm-up. Current stored exchange filters are current snapshots, not invented historical point-in-time truth.

## Live/security boundary

Low-level live adapter/order-journal code exists and many fake/offline tests are green, but productive arming/submit remains hard-blocked, UI start remains blocked, and external/Testnet/remainder/foreign-order acceptance remains open. Cloud agents must never turn those gates on simply to complete a task.

## Documentation precedence

Older DMS portions contain historical USDT, budget, service and Live architecture states. DMS 00 plus the decision log define chronological/source precedence. Historical evidence must not be globally rewritten to current USDC wording.

## Engineering swarm architecture

The current engineering path is exclusively cloud-hosted. Legacy laptop-bound engineering launchers and local agent runners are absent from the working tree.

Current control plane:
- default-branch `.github/workflows/hixton-cloud-swarm.yml` provides manual and scheduled dispatch;
- `gpt/usdc-audit/.github/workflows/hixton-cloud-swarm-reusable.yml` contains the A01–A11 execution graph;
- `.github/workflows/hixton-cloud-preflight.yml` validates the swarm contract without model credentials;
- A01–A08 run independently/read-only;
- A10 works on an isolated mission branch;
- A09 runs deterministic QA plus independent release review;
- A11 performs final governance and can force one automatic A10 repair loop;
- successful work opens a PR and is never auto-merged.

The cloud preflight has executed successfully on GitHub Ubuntu 24.04 / Python 3.12 and ran 11/11 swarm-core tests green. It reported A01–A11, SWARM-002, the USDT/USDC regression case, `real_money_orders_allowed=False`, `automatic_merge_allowed=False`, and confirmed the repository has only the trading batch launcher plus no local PowerShell engineering runner.

The main scheduler now checks for the cloud-agent credential first. If the credential is absent, the workflow succeeds in a safe idle state and skips model jobs rather than producing repeated false failures.

GitHub-hosted model work still requires repository secret `OPENAI_API_KEY`; it cannot inherit an interactive laptop ChatGPT/Codex login.

## Repository structure

`Startbot.bat -> src/main.py` remains the only trading application start path. Cloud swarm tooling is CI engineering infrastructure, not a second trading runtime. Research/backtest directories are evidence and experiments, not alternate application entrypoints.

## Final verdict

No repository-understanding blocker remains. The repository is structurally ready for laptop-independent swarm execution while preserving trading/live safety. The remaining prerequisites/unknowns are external: cloud OpenAI credential, real Binance account/runtime facts, external execution acceptance, operator backup/restore state and future market behavior.
