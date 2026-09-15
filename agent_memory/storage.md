# Storage and recovery map — verified 2026-09-15

## Market-data SQLite ownership

`hixton.data.storage.CandleStore` owns persistent candle and symbol-rule state. Active config points to a USDC database path (`data/hixton-usdc.sqlite3`). SQLite uses WAL, foreign keys and synchronous FULL. The database directory is created only in writable mode; research controls can open read-only without schema mutation.

Candle identity is symbol/time/open-time. Closed historical replacements are revisioned/auditable rather than silently destroying provenance. Provisional/current rows may update as provider information changes. Stored SymbolRules capture current exchange filter snapshots; these are not claimed to be historical point-in-time filters.

CandleStore is also the source for deterministic candle snapshot hashing used in reports. Data-quality code does not repair data by interpolation.

## PaperStore ownership

`hixton.paper.storage.PaperStore` owns the simulated shared account and its operational history within the active database:
- Paper account/cash/start equity/high-water/day-start/risk-halt state;
- one shared Paper settings row (slot count, target notional, emergency/entry control as implemented);
- positions including entry basis/version/entry ATR/highest close/slot use;
- events/fills/audit-style records;
- per-symbol processing checkpoints;
- dust quantities;
- strategy session/activation metadata;
- soak epoch/counters and execution-model audit.

PaperStore initialization is idempotent/non-resetting. Existing accounts are never topped up simply because config defaults differ. Strategy mismatch is fail-closed and requires explicit controlled activation. A legacy USDT Paper checkpoint/database presented to the USDC runtime is rejected before destructive schema/state mutation.

Each processed aligned Paper cycle is persisted atomically: account, complete position set, generated events, checkpoints, dust and counters advance together. A process crash before commit rolls back the SQLite transaction; restart reads the prior coherent checkpoint.

## Paper recovery

On normal restart RuntimeSupervisor/PaperEngine load existing account/settings/positions/checkpoints. Missing closed bars after checkpoint are replayed chronologically exactly once, using actual next-open references. Existing cash, high-water, daily reference, positions, dust and halt state survive restart.

First-ever initialization intentionally starts at the latest synchronized position rather than creating historical Paper fills. That prevents a startup sync from becoming delayed real-time trades.

## Explicit fresh-start maintenance

`paper/maintenance.py` and CLI `paper-fresh-start` are intentionally exceptional. Preconditions include stopped runtime/port, exact confirmation and approved baseline. It verifies expected known Paper schema, creates a non-overwriting SQLite backup using SQLite backup facilities, checks integrity and hash, then clears only the known Paper tables and initializes a fresh account/session. Market data remains.

Normal `Startbot.bat`, backtests, UI reloads, configuration save and strategy research do not call this path. Repeated resets require a new explicit owner instruction.

## Runtime instance metadata

The visible local instance uses ignored runtime metadata (`data/runtime-session.json` per runbook) containing an instance/control token for safe predecessor shutdown. It contains no Binance API secret. Ownership/token checks prevent killing arbitrary processes on the port. Stale metadata at a free port can be replaced safely.

## Live-preparation persistence

Live preparation uses separate local security/audit state (`data/live-preparation.sqlite3` in current design) plus Windows Credential Manager.

This store is not a second Paper trading account. It holds preparation/trial/audit/reconciliation state such as immutable trial account baseline and order-journal state where composed. It must not import old Paper balances as bot-owned live assets.

`live/orders.py` OrderJournal persists immutable TrialIntent identity before submit, submission claim/state and deduplicated fills. Important properties:
- exactly one claimant can transition an intent to sending;
- terminal exchange result cannot be erased by a late failure;
- duplicate fill trade identity with conflicting economics fails instead of overwriting;
- timeout/unknown submit is reconciled/query-only, never blindly re-submitted;
- fill fees retain their actual fee asset.

`live/reconciliation.py` establishes a clean immutable account baseline and derives expected changes only from known bot fills. Completion does not rely on a UI Boolean.

## Credential storage

`live/credentials.py` uses exact namespaced Windows Credential Manager entries. Stored objects include local password verifier material and Binance API key/secret. No plaintext file/env fallback is implemented for these live-preparation credentials. Session tokens are process-local hashed state plus short-lived HttpOnly browser cookie; they expire across restart.

The USDC database migration deliberately retains the previous installation credential namespace rather than copying or exposing secret values.

## Backtest and research artifact storage

`backtest/reporting.py` writes each run to a new unique directory and refuses overwrite. Manifests/results carry code/config/strategy/data/cost/window/model provenance. Historical reports remain immutable evidence even when active code later changes.

Large raw run artifacts and market data can be ignored locally; small curated READMEs/candidate/reports are tracked under `backtests/vN/`. A stored report is never automatically active strategy state.

## UI build storage

Editable source is `ui/`. Production-served built assets are committed under `src/hixton/ui/static/`. The normal application start requires the built `index.html`. A UI source change without rebuilding static output is therefore an incomplete change and must fail A04/A09 review.

## Configuration persistence

The shipped strict baseline config is tracked JSON under `config/examples`. Operator Paper settings are not a second config file; they persist in PaperStore and take precedence for forward Paper slot/notional behavior. Saving settings cannot mutate account cash or existing positions.

Secrets and live-enable flags are deliberately absent from tracked config.

## State that is intentionally not persisted

- Current in-memory RuntimeState snapshots/events beyond their persisted underlying sources.
- Browser live-auth session token across process restart.
- Transient WebSocket connection state.
- Unsaved UI settings draft (browser view state only).
- Research screening process memory after immutable result writing.

These are safe to reconstruct. Persistent ownership-critical state (Paper checkpoints/account, trial intents/fills/baseline) is stored before effects that require restart safety.

## Backup/restore boundary

DMS specifies external encrypted backup/retention/restore requirements for eventual live operation; full automated external backup/quarterly restore is not proven by this repository snapshot. The explicit Paper fresh-start archive is implemented and tested but is not a substitute for the full future live backup gate.

Runtime-local databases/backups are intentionally outside Git. Therefore repository agents can verify storage semantics and tests but cannot truthfully assert a particular operator database/backup is healthy without runtime access.

## Recovery failure rules

- Corrupt/incompatible DB: fail closed; do not create a replacement account silently.
- Missing/gapped candles: repair from provider then re-audit before signal processing.
- Paper process crash: resume checkpoint, no duplicate cycle.
- Live ambiguous submit: UNKNOWN/query/reconcile, no replacement submit.
- Unknown manual/foreign live state: block completion/live entry; do not claim or sell user assets.
- Bot process stop: no auto-liquidation; later live restart would require reconciliation before new order.

## Agent requirements

A03 owns Paper persistence/restart correctness; A07 owns market-data persistence/revisions; A05 owns runtime recovery observation; A06 checks schema/state regressions; A09 requires migration/restart tests for storage changes; A11 must reject any patch that 'fixes' a mismatch by silently resetting or deleting persistent state.