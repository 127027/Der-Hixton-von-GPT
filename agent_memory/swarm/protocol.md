# Swarm protocol

## 1. Intake and preflight

Every owner request becomes a task with a unique ID, explicit objective, invariants, prohibited actions, affected areas, evidence requirements and acceptance conditions. A01 reviews the relevant documentation and current implementation before engineering starts. Contradictions are recorded, not silently resolved.

## 2. Assignment

A10 selects one primary specialist and all required secondary specialists. The primary specialist owns diagnosis and proposed implementation in its domain, but may not approve its own result. A11 verifies that the assignment covers every affected component and that A10 did not omit a required agent.

## 3. Heartbeats and anti-stall

Each active agent state must contain: task_id, status, current_question, last_evidence, next_action, blockers, last_heartbeat_utc, attempt and touched_domains. An agent is considered stalled when it repeats the same unsupported conclusion, produces no new evidence across two rounds, leaves a known blocker unassigned, or exceeds the configured heartbeat window once an actual dispatcher exists. A10 retries/reassigns stalled work. A11 audits the retry and can overrule a false DONE/WAITING state.

## 4. Evidence discipline

Claims must point to code, tests, committed reports, deterministic command output or runtime observations. Historical profit alone is never proof of correctness. A result must distinguish: code defect, configuration mismatch, data difference, state/path dependency, intended behavior, research hypothesis and external-runtime unknown.

## 5. Patch discipline

Before a patch: capture the relevant golden/baseline behavior and expected intentional delta. After a patch: rerun the smallest focused tests first, then all affected cross-component tests, then the full applicable QA gate. Old reports remain immutable historical evidence.

## 6. Mandatory cross-checks

A06 asks after every behavioral patch: what else could this have changed? It checks configuration, shared strategy/risk rules, data assumptions, Paper, Backtest, runtime, storage/restart, API/UI, generated assets and documentation as applicable. Quote/symbol migrations require explicit same-window old-vs-new comparisons and state-reset analysis.

## 7. QA gate

A09 produces PASS or FAIL with an acceptance matrix. It cannot alter production behavior to make tests pass. FAIL returns the task to REPAIR_LOOP. PASS alone is not DONE.

## 8. Governance gate

A11 checks that all required agents actually ran, evidence is non-vacuous, no specialist self-approved, no unresolved task-scoped blocker was hidden, and the result still matches the owner's objective. Only `QA_PASS + GOVERNANCE_PASS` permits DONE.

## 9. Repair loop

A failure is routed to the agent owning the root cause, not automatically to the agent that discovered it. When repaired, every downstream gate affected by that change is invalidated and rerun. A10 tracks this invalidation graph; A11 checks it.

## 10. Continuous runtime watch

When a real persistent dispatcher is wired, A05 performs periodic health iterations. It reports only meaningful changes/incidents, while A10 keeps recurring checks alive. A11 detects if recurring duties silently stop. Autonomous checks never place real orders.

## 11. Research versus repair

A08 may propose strategy/risk changes; A02 may evaluate them. They must never relabel strategy optimization as bug repair. A06 and A09 enforce this distinction. A production activation requires explicit evidence and the applicable owner/release gates.
