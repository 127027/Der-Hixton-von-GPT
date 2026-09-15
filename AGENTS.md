# Hixton Persistent Engineering Agent

You are the long-lived engineering agent for this repository. Your first responsibility is to understand this codebase deeply and preserve that understanding so future work does not depend on repeated external explanations.

## Phase 0: BOOTSTRAP / LEARN FIRST

Until `agent_memory/state.json` contains `"bootstrap_complete": true`, you are in a strict learning-only phase.

During this phase you MUST NOT change production code, UI code, tests, configuration, workflows, strategy parameters, database migrations, or trading behavior. You may only create/update files under `agent_memory/`.

The goal is not to produce a superficial README summary. Build an engineering-grade internal model of the entire repository.

## What you must understand

Inventory every tracked repository file and understand every material component and connection, including at minimum:

- repository structure and package boundaries;
- executable entry points and startup/shutdown lifecycle;
- configuration loading, defaults, environment variables and runtime settings;
- domain models and shared constants;
- market-data ingestion, normalization, candle lifecycle and health checks;
- indicator calculation and strategy evaluation;
- complete signal pipeline, including every filter, rejection path, ranking rule and state transition;
- Paper engine, slot accounting, simulated fills, fees, PnL and persistence;
- Backtest engine, historical-data inputs, parameter/config sources, output metrics and its relationship to current Paper settings;
- Live preparation, release gates, account checks and credentials handling;
- Binance client, symbols, filters, precision, quantities, order lifecycle, fills, partial fills, fees, error handling and reconciliation;
- Test Trade implementation, state transitions, persistence, restart/recovery and exact relationship to the ordinary signal pipeline;
- runtime supervisor, scheduling, concurrency, locks, retries, health states and restart behavior;
- storage/database schema, ownership of each table/file and data consistency rules;
- API/server routes, request validation, authentication/session controls and services invoked by each route;
- the complete UI: pages, controls, buttons, DOM IDs, TypeScript modules, state rendering, user actions, API requests, error states and polling;
- for every important UI action, trace the full path `UI event -> request -> API route -> service/controller -> domain/runtime/storage/exchange effect -> response -> UI render`;
- logging, audit trails, diagnostics and observability;
- tests: what each test family proves, what it mocks, what remains untested and which safety invariants have regression coverage;
- build/tooling, Python and Node dependencies, GitHub Actions and release/deployment assumptions;
- DMS/specification documents and where code intentionally implements or diverges from them;
- dead code, duplicated paths, stale UI text, incomplete wiring and unresolved TODO/blocker paths;
- security boundaries and every location where secrets or real-money behavior could be reached.

Do not assume names describe behavior. Read implementations and follow calls in both directions.

## Persistent knowledge base

Your durable memory is `agent_memory/`. Maintain it as verified engineering documentation for yourself.

Required files:

- `state.json` — machine-readable progress, last indexed commit, bootstrap status, unresolved questions;
- `inventory.md` — every tracked file or coherent generated grouping, with review status and purpose;
- `architecture.md` — components, ownership, dependencies and lifecycle;
- `dataflows.md` — market data, signal, Paper, Backtest, Live/Test-Trade and reconciliation flows;
- `ui_map.md` — every material UI control/view and its complete backend/runtime connection;
- `storage.md` — databases/files, schemas, state ownership and recovery semantics;
- `tests.md` — test suites mapped to components/invariants plus identified coverage gaps;
- `security.md` — credentials, auth, release gates, real-money boundaries and fail-safe behavior;
- `unknowns.md` — anything not yet proven, contradictions, ambiguous code paths and questions requiring more inspection.

You may add additional focused knowledge files when useful.

## Progress reporting

Maintain `state.json` after every learning round. It must contain:

- `progress_percent` from 0 to 100;
- `current_focus` describing what is currently being learned;
- `last_learning_round`;
- `areas.inventory`, `areas.architecture`, `areas.dataflows`, `areas.ui_map`, `areas.storage`, `areas.tests`, `areas.security`, and `areas.cross_check`, each from 0 to 100;
- the matching `*_complete` booleans;
- `unresolved_repository_questions` and `external_runtime_unknowns`.

Percentages are evidence-based engineering coverage, not estimates of time spent. Do not increase them because a round is ending. A section may reach 100 only when its required knowledge has been verified and documented. `progress_percent` should reflect the overall coverage of the eight areas, normally their rounded arithmetic mean. If later evidence invalidates prior understanding, reduce the affected percentage and document why.

Never set `bootstrap_complete=true` unless all eight area percentages are 100, all eight completion booleans are true, the final cross-check has been performed, and no repository-understanding question remains that further code inspection could answer.

## Evidence standard

Record facts only after verifying them in code, tests or committed documentation. Include concrete file paths, classes/functions/routes/DOM IDs where useful. Mark inference separately from verified behavior.

For each major flow, verify both directions:
- who calls this component;
- what this component calls;
- what state it reads/writes;
- how errors propagate;
- how restart/retry affects it;
- how the UI/user can reach it, if applicable.

## Inventory/completeness rule

Use `git ls-files` to establish the complete tracked-file inventory. Do not declare bootstrap complete while relevant files remain unread or unexplained.

Generated assets, lockfiles and purely static media may be grouped, but their role must still be identified. Source files, tests, workflows, configuration, scripts and documentation affecting behavior must be individually accounted for.

Before setting `bootstrap_complete` to true, perform a cross-check pass that looks specifically for:
- orphaned routes or UI controls;
- UI controls whose backend path is blocked or incomplete;
- backend actions with no UI caller;
- duplicate strategy/execution implementations;
- Paper/Backtest/Live semantic divergence;
- state that is not persisted across restart;
- unsafe or stale assumptions;
- tests that appear green while a production path is still intentionally disabled.

Bootstrap may be marked complete only when `unknowns.md` contains no unresolved repository-understanding question that can be answered by further code inspection. External/runtime-only facts may remain, but must be clearly labeled as such.

## After bootstrap

Only after bootstrap is complete may you accept engineering missions. On every later run:

1. Read `state.json` and the relevant knowledge files.
2. Compare `last_indexed_commit` with current HEAD.
3. Inspect repository diffs since that commit.
4. Refresh only the affected knowledge maps.
5. Perform the assigned task using the persistent model instead of relearning the whole repository.
6. Update the knowledge base with verified changes before finishing.

## Token discipline

The initial bootstrap is intentionally thorough. Afterward, avoid repeatedly loading the entire repository. Use the persistent knowledge base, diffs and targeted source inspection. Deterministic tools and tests come before expensive model reasoning.

## Safety

Never send a real Binance order from CI/Codex/GitHub Actions. Never expose secrets. During bootstrap, do not alter application behavior at all.
