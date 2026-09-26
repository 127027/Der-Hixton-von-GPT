# Hixton Agent Swarm

This directory defines the persistent eleven-agent engineering swarm for Der Hixton.

The swarm is **cloud-first and laptop-independent**. The default A01-A11 verification path runs deterministically on GitHub-hosted virtual machines without OpenAI or Binance private API credentials. Legacy laptop-bound engineering launchers and local agent runners are intentionally absent.

The trading application itself remains separate: `Startbot.bat` is still the human Windows starter for the actual bot installation. The cloud swarm never uses a local laptop login and never receives Binance credentials.

## Hierarchy

1. Documentation & Requirements Auditor
2. Backtest & Research Agent
3. Paper Runtime Agent
4. UI/UX Freshness Agent
5. Runtime Watchdog Agent
6. Integration, Regression & Repair Agent
7. Market Data & Binance Agent
8. Strategy & Risk Agent
9. QA & Release Gate Agent
10. Workflow Supervisor & Dispatcher
11. Meta-Orchestrator & Agent Auditor

A10 owns task sequencing, dependencies, implementation and repair hand-offs. A11 is deliberately separate: it audits A10 and every specialist for inactivity, scope drift, unsupported conclusions, missing evidence, skipped checks and stalled loops. A11 may force a repair round, but never bypasses A09's technical QA gate.

## Cloud execution model

The default-branch dispatcher workflow calls the reusable workflow stored with the engineering branch. A cloud run:

1. checks out `gpt/usdc-audit` on a GitHub-hosted Ubuntu VM;
2. creates a Python virtual environment and installs the pinned application plus development tools;
3. installs the UI dependencies;
4. validates the 11-agent registry and the active taskboard mission;
5. best-effort synchronizes public USDC market data into a temporary ignored SQLite database;
6. runs A01-A08 independently in read-only Codex jobs;
7. runs A10 on a dedicated `swarm/run-<run_id>` branch with the specialist evidence;
8. executes deterministic Python/UI QA and then A09 as an independent read-only release gate;
9. runs A11 as the final governance gate;
10. if A11 rejects the result, automatically returns the branch to A10 for a repair round and repeats QA/governance;
11. only after `QA_PASS` and `GOVERNANCE_PASS` opens a pull request back to `gpt/usdc-audit`.

No swarm run automatically merges strategy, capital, risk or real-money changes. A pull request is the hand-off boundary for owner review.

## Mandatory lifecycle

`NEW -> PREFLIGHT -> ASSIGNED -> IN_PROGRESS -> VERIFYING -> REGRESSION -> QA -> GOVERNANCE -> DONE`

Any failure moves the work to `REPAIR_LOOP` and returns it to A10 with the responsible specialist/gate evidence. After repair, all affected downstream checks run again. A task cannot be treated as complete unless A09 reports `QA_PASS` and A11 reports `GOVERNANCE_PASS`.

## Core rule

A patch is not successful because its own unit test passes. Success means the intended behavior changed, unrelated behavior did not regress, Paper/Backtest/UI/runtime/data contracts remain consistent where applicable, documentation matches reality, and the complete affected acceptance matrix passes.

## Authentication and cost boundary

The mandatory A01-A11 verification workflow is key-free and must not depend on an `OPENAI_API_KEY` or Binance credentials. Any future optional model-assisted workflow would require a separate explicit configuration and must never become a hidden dependency of the release gate.

## Safety

- Never place a real Binance order from an autonomous agent, CI or Codex session.
- Never expose credentials or secrets.
- Cloud runs receive no Binance API key/secret.
- Ordinary swarm missions may not change the protected live-submit implementation or GitHub workflow governance files.
- Active strategy/risk activation requires a separate explicit owner decision even when research finds a better candidate.
- Public Binance market data may be downloaded into ephemeral/ignored runner storage for analysis and backtests.

See `registry.json`, `protocol.md`, `taskboard.json`, `agents/`, `scripts/swarm_core.py`, and `.github/workflows/hixton-cloud-swarm-reusable.yml` for the executable contracts.
## Current strategy truth

For active V6 engineering, `taskboard.json` and the current DMS contract are normative: one canonical ten-coin USDC strategy, one saved `max_capital_usdc` with `CAPITAL-V1-2X50PCT` (default 250 → 2×125 `ranked_repeat`), no permanent portfolio drawdown halt, a separate controlled 1×50-USDC local Live trial, and 10×250 only as per-coin diagnostic/optimization laboratory. Historical backtest READMEs may contain superseded USDT, `one_per_symbol` or 20-percent-halt evidence and must never be interpreted as active runtime requirements.
