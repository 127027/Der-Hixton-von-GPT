# Hixton Agent Swarm

This directory defines the persistent multi-agent engineering swarm for Der Hixton.

The swarm contains eleven distinct roles. Agents do not self-declare a task complete. Every engineering task passes through documentation preflight, the responsible specialist(s), integration/regression review, QA release gating, and meta-orchestrator governance.

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

Agent 10 owns task sequencing, dependencies, retries and hand-offs. Agent 11 is deliberately separate: it audits Agent 10 and every specialist for inactivity, scope drift, unsupported conclusions, missing evidence, skipped checks and stalled loops. Agent 11 may reassign or re-open a task, but never bypass Agent 9's technical QA gate.

## Mandatory lifecycle

`NEW -> PREFLIGHT -> ASSIGNED -> IN_PROGRESS -> VERIFYING -> REGRESSION -> QA -> GOVERNANCE -> DONE`

Any failure moves the task to `REPAIR_LOOP` and returns it to the responsible specialist. After repair, all affected downstream checks run again. A task cannot be marked DONE unless Agent 9 reports PASS and Agent 11 reports GOVERNANCE_PASS.

## Core rule

A patch is not successful because its own unit test passes. Success means the intended behavior changed, unrelated behavior did not regress, Paper/Backtest/UI/runtime/data contracts remain consistent where applicable, documentation matches reality, and the complete affected acceptance matrix passes.

## Safety

- Never place a real Binance order from an autonomous agent, CI or Codex session.
- Never expose credentials or secrets.
- Live execution remains disabled unless the owner gives a separate explicit real-money release instruction and all existing product safety gates are satisfied.
- During repository bootstrap, AGENTS.md remains authoritative: only files under agent_memory/ may be modified.

See `registry.json`, `protocol.md`, `taskboard.json`, and `agents/` for the executable role contracts to be wired into the local dispatcher after bootstrap.