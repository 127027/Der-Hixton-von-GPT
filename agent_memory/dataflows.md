# Data-flow map — verified 2026-09-15

## 1. Application startup and visibility

`Startbot.bat`
→ local Python/dependency/static-UI checks
→ `src/main.py start`
→ CLI loads strict config
→ local instance reservation / predecessor coordination
→ FastAPI/Uvicorn starts on `127.0.0.1`
→ browser opens unless `--no-browser`
→ `VisibleSession` waits for valid same-origin presence WebSocket
→ only first valid UI presence calls `RuntimeSupervisor.start()`
→ if no UI appears by deadline or terminal is lost, runtime exits.

State read/written: runtime-session metadata only for instance ownership; no Paper reset and no order action at startup by default.

Failure propagation: unknown port occupant blocks; invalid config/dependency/UI build blocks; broken terminal/UI lease stops instead of permitting hidden processing.

## 2. Startup market-data synchronization

RuntimeSupervisor
→ Binance server-time check
→ SQLite integrity
→ per-symbol first available 1h candle discovery
→ derive requested up-to-3y history + 400 warm-up while respecting provider availability
→ `sync_symbol_history()`
→ public Binance kline fetch/paging/tail refresh
→ CandleStore put/revision tracking
→ `audit_candles(...).require_valid()`
→ exchangeInfo SymbolRules stored/loaded
→ common aligned analysis/report start derived.

No gap interpolation. Seven USDC markets in the audited period do not support a full common three-year report after warm-up; actual common start is reported instead of fabricated.

Failures: invalid/gapped/latest-missing/provisional-in-report data blocks the affected analysis and pushes health to DEGRADED/recovery; it does not synthesize bars or trade on stale history.

## 3. Live market-data path

Binance WebSocket ten `symbol@kline_1h`
→ provisional updates stored and exposed to UI only
→ closed event triggers REST-backed finalization/re-sync
→ aligned closed bars plus known next-open reference become eligible for Paper
→ strategy updates only on final closed bars.

If stream drops:
→ runtime records stream-owned error / DEGRADED
→ REST fallback maintains recoverable data path
→ exponential reconnect
→ after reconnect, REST closes any gap before normal signal processing
→ reconnect may clear only the stream-owned failure, never an unrelated database/data-quality error.

Watchdog also checks >90s stream staleness and >120s overdue final 1h candle.

## 4. Strategy signal path

Final Candle
→ `HixtonStrategy.update()` validates symbol/timeframe/continuity/finality/OHLCV
→ indicator state (CMO/VIDYA/ATR/bands)
→ warm-up/state update
→ base flip (`flip_up`/`flip_down`)
→ stable Signal candidate
→ `TradePolicyGate.decide()` applies coin-specific entry filters and allowed close-based exit overlays
→ qualified signal or explicit block reason.

No slot/cash/account decision belongs to base indicator calculation. A green/up trend without a new flip is not a fresh buy signal.

## 5. Paper chronological execution

Runtime gathers one aligned finalized slice for all ten markets and next-open execution references
→ `PaperEngine.process_*`
→ load persisted account/settings/positions/checkpoints/dust/strategy session
→ reject duplicate/already-processed slice
→ execute pending exits first at modeled adverse next-open price
→ update cash/position/dust/fees/PnL
→ evaluate new strategy/policy decisions on closed bars
→ update shared account equity
→ pure portfolio risk transition (daily pause / persistent drawdown halt)
→ rank simultaneous entries through centralized `entry_priority`
→ allocate slots using active strategy slot policy
→ apply emergency stop/risk/daily pause/full slot/cash/exchange-minimum blocks
→ simulate accepted entry at next-open baseline costs
→ atomically persist account + full positions + events + checkpoints + dust + soak counters + execution audit.

Restart:
→ load checkpoints and existing strategy/account/session
→ fill missed finalized slices exactly once
→ do not create a new account/top-up/reset
→ current positions/cash/high-water/risk state survive.

First-ever initialization arms at latest current point rather than backtrading old historical signals.

## 6. Isolated single/batch backtest

Historical audited candles + stored execution rules + one strategy definition
→ `run_single_backtest()` per symbol
→ warm-up same strategy
→ previous close-generated signal becomes pending
→ fill earliest at following bar open with chosen CostModel
→ no account-level 20% portfolio halt
→ target 250 per coin bounded downward by available cash; no automatic target compounding
→ final open position marked to market
→ metrics and data snapshot hash.

`run_isolated_batch()` repeats for ten independent 250-unit accounts and aggregates numerically. The 2500 total is a diagnostic sum, not the Paper shared cashpool.

## 7. Shared portfolio backtest

Ten aligned audited historical series
→ `run_shared_portfolio_backtest()`
→ same per-coin StrategyDefinition and TradePolicyGate
→ shared starting cash (normally 250)
→ next-bar-open exits before entries
→ centralized priority and slot allocation
→ same pure shared risk function used by Paper
→ shared cash/positions/equity/path dependency
→ persistent halt blocks future entries but does not force-liquidate existing positions
→ metrics/block reasons/max concurrent slots/halt time/hashes.

Important path rule: a fresh backtest starts a new cash account. It does not inherit today's Paper positions or the equity/high-water of a longer historical run. This is the root distinction exposed by the USDT→USDC audit.

## 8. Paper ↔ portfolio parity validation

Same deterministic candle fixture/actual historical window + same profiles + same starting account/slot/target/rules
→ process through PaperEngine
and
→ process through shared portfolio backtest
→ compare signal IDs, fill time, reference/fill price, quantity, fee and final equity.

Current audited reference: 28/28 fills and 203.718610797945 ending USDC matched; split/restart replay also matched. This proves the tested historical path, not every future failure/live/intrabar condition.

## 9. Backtest report/provenance path

Completed result(s)
→ `write_report_bundle()`
→ new unique output directory only
→ manifest with strategy/profile/config/code/data/cost/window/model metadata
→ metrics/trade/report artifacts
→ never overwrite prior run.

API/UI reader
→ loads manifest/metrics
→ `compare_run()` compares stored strategy/quote/Python hash/costs and, for portfolio, current starting capital/slots/notional/risk proof
→ classifies `MATCHING`, `DIFFERENT`, or `UNVERIFIED`
→ UI presents scope and window limitations rather than silently calling old evidence current.

## 10. Research flow

Owner/research mission
→ fixed hypothesis/search space and training/validation windows
→ simplified screening where explicitly documented
→ freeze candidate before validation where methodology requires it
→ exact finalists through canonical Decimal engines
→ baseline/stress and shared-portfolio checks
→ immutable research report
→ no automatic Paper activation.

A positive individual result is insufficient; failures/regression windows are retained. V8/V9 are current examples of rejected research despite local improvements.

## 11. Quote migration review

USDT historical evidence remains economically USDT.
USDC review downloads/uses actual USDC candles.
→ common continuous suffix selected only from real data availability plus warm-up
→ same-window USDT control when available
→ compare rules/profiles/windows/account starting state separately
→ no symbol rename used as fake USDC history.

Verified incident result: old long-running USDT 733.31 vs fresh later USDT 201.11 and fresh same-window USDC 203.62. Main delta is account path/start state, not currency conversion code.

## 12. Chart/UI data path

Browser selection (symbol/range/resolution)
→ GET chart API
→ locally stored native 1h candles + strategy overlays
→ optional deterministic display aggregation (1y→4h, 3y→1d defaults)
→ signal markers remain native-1h derived
→ current provisional candle may be displayed but never emits a confirmed signal marker
→ generation counters discard late responses after UI selection changes.

Market cards/status poll current runtime/Paper snapshots, including freshness and actual current profiles. Paper fills are separate from hypothetical qualified strategy markers.

## 13. Settings path

UI draft
→ preserves unsaved user input against polling
→ POST local action with same-origin/action-header protection
→ API validates 1–10 slots and positive finite target notional
→ PaperStore persists one common settings row
→ server response becomes active UI state.

Saving settings never invents cash, resets account/soak, retroactively resizes positions or enables live trading. New settings affect future entries.

## 14. Visible-session shutdown path

Browser presence leaves / stop action / terminal probe fails
→ VisibleSession sets stopping
→ RuntimeSupervisor stop requested
→ no new processing/entries
→ process exits after orderly window/self-termination bound
→ matching runtime control metadata removed.

Unknown browser origin/token/instance cannot stop another instance; unknown port process is never killed.

## 15. Live-preparation credential path

Local UI password/session action
→ exact localhost Origin/action checks
→ `credentials.py` verifies/creates local scrypt verifier in Windows Credential Manager
→ HttpOnly SameSite=Strict temporary session cookie
→ key/secret operations access only exact Hixton vault targets
→ UI never receives secret values back; fields are cleared after use.

Account preflight
→ signed read-only Binance requests only
→ permissions/Spot status/IP restriction/open orders/locked funds/foreign balances/free USDC/10-market filters
→ redacted structured result stored with freshness limit
→ still does not enable order submit.

## 16. Trial/live order preparation path — currently blocked before real submit

User-visible trial start request
→ API checks auth/preflight/release blockers
→ currently HTTP 409
→ no real order.

Internal unreleased architecture:
qualified fresh signal
→ Trial controller global one-entry entitlement / fixed 50 USDC
→ intended pre-send market/account/risk gates
→ OrderJournal persists intent and atomically claims submit
→ release check must pass
→ Exchange adapter signed submit
→ fill/order parser
→ journal/reconciliation
→ position remains managed for its normal exit even after new-entry entitlement is consumed.

Current composition deliberately provides hard-false productive release gates. Therefore no development agent, CI job or UI action may reach a real submit. Timeout/unknown responses reconcile/query instead of blind re-send.

## 17. Live reconciliation path

Before a permitted future trial intent, an immutable clean account baseline is required.
Known exchange fills update expected balances by actual quantity/quote/fee asset.
Current balances/open orders/unresolved order state are compared.
Completion requires no unresolved order, no unexplained balance difference and no owned remainder falsely claimed sold.

Limit: balance snapshots alone cannot prove no offsetting manual trades occurred between observations. Full foreign-order/account isolation remains a documented live blocker.

## 18. Offline Paper fresh-start path

Explicit CLI maintenance command only
→ require bot stopped + exact confirmation `NEUSTART`
→ require approved strategy and expected baseline model
→ require archive path under backups and non-existing
→ lock DB / verify exact known Paper schema
→ byte-consistent SQLite backup + integrity check + SHA256
→ delete only known Paper tables' rows
→ initialize new 250/3×80 account/session/audit
→ market candles and unrelated state retained.

No ordinary startup/backtest/UI action calls this reset.

## 19. Engineering-agent flow — current and target

Current:
`StartAgent.bat` / `AgentChat.bat`
→ single PowerShell Codex agent
→ requires clean working tree and obsolete fixed branch
→ disposable worktree
→ during bootstrap only agent_memory copied back/committed.

Target after bootstrap:
existing engineering-agent entry
→ A10 task graph/role scheduler
→ A01 mandatory preflight
→ assigned specialist role(s) in isolated worktrees or serialized write ownership
→ A06 integration/regression
→ A09 independent QA
→ A11 independent governance audit
→ failures route to root-cause agent and invalidate downstream evidence
→ DONE only with `QA_PASS + GOVERNANCE_PASS`.

A05 recurring health observations may be scheduled only while an actual bot/runtime is available; absence of runtime must be reported, never fabricated as healthy. Agent automation receives no real-order release authority.