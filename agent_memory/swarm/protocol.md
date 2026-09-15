# Swarm protocol

## 1. Intake and preflight

Every owner request becomes a task with a unique ID, explicit objective, invariants, prohibited actions, affected areas, evidence requirements and acceptance conditions. A01 reviews the relevant documentation and current implementation before engineering starts. Contradictions are recorded, not silently resolved.

The authoritative dispatcher is GitHub Actions. It checks out `gpt/usdc-audit` into GitHub-hosted virtual machines, builds a fresh Python virtual environment and UI dependency tree, and uses only public/generated market data plus tracked repository evidence. The owner laptop is not part of the agent execution path.

## 2. Assignment

A10 coordinates diagnosis and implementation after the independent specialist reviews. Specialists may propose implementation in their domains but may not approve their own result. A11 verifies that the assignment covers every affected component and that A10 did not omit or ignore a required agent.

## 3. Heartbeats and anti-stall

A01-A08 execute as independent cloud jobs. GitHub job status, artifacts and timeouts are the heartbeat mechanism. A10 is considered stalled when it fails/times out, repeats an unsupported conclusion, produces no new evidence after repair feedback, or leaves a known blocker unaddressed. A11 audits the result and automatically forces one repair round when governance is not satisfied. A second unresolved failure is surfaced as a GitHub issue and failed workflow rather than being hidden as DONE.

## 4. Evidence discipline

Claims must point to code, tests, committed reports, deterministic command output or runtime observations. Historical profit alone is never proof of correctness. A result must distinguish: code defect, configuration mismatch, data difference, state/path dependency, intended behavior, research hypothesis and external-runtime unknown.

## 5. Patch discipline

Before a patch: capture the relevant golden/baseline behavior and expected intentional delta. After a patch: rerun the smallest focused tests first, then all affected cross-component tests, then the full applicable QA gate. Old reports remain immutable historical evidence.

A10 works only on an isolated `swarm/run-<GitHub run id>` branch. Protected workflow/governance and Live-submit paths are rejected by a deterministic path guard. Successful work opens a pull request; it is never auto-merged.

## 6. Mandatory cross-checks

A06 asks after every behavioral patch: what else could this have changed? It checks configuration, shared strategy/risk rules, data assumptions, Paper, Backtest, runtime, storage/restart, API/UI, generated assets and documentation as applicable. Quote/symbol migrations require explicit same-window old-vs-new comparisons and state-reset analysis.

## 7. QA gate

A09 runs after A10 on a fresh GitHub runner. Deterministic QA includes Python compile, Ruff, mypy, pytest, UI tests, TypeScript checking/build and application status. A09 then produces `QA_PASS` or `QA_FAIL`. It cannot alter production behavior to make tests pass. FAIL returns the task to the automatic repair loop. PASS alone is not DONE.

## 8. Governance gate

A11 runs after A09 on another read-only cloud job. It checks that all required agents actually ran, evidence is non-vacuous, no specialist self-approved, no unresolved task-scoped blocker was hidden, and the result still matches the owner's objective. Only `QA_PASS + GOVERNANCE_PASS` permits a pull request to be opened.

## 9. Repair loop

A failure is routed back to A10 together with A09/A11 evidence. A10 repairs only the concrete failure while preserving valid work. QA and governance are then invalidated and rerun from scratch. If the second governance pass still fails, the branch remains available for diagnosis and the workflow opens a GitHub issue instead of claiming completion.

## 10. Continuous cloud watch

The default-branch dispatcher runs manually or on schedule. Before spending model/API work, preflight checks whether the taskboard has actionable work and whether another swarm pull request is already open. If either condition says no work is needed, the swarm stays idle. A05 owns runtime/liveness analysis inside active missions; A10 keeps repair work moving; A11 detects skipped duties. Autonomous cloud checks never place real orders and receive no Binance credentials.

## 11. Research versus repair

A08 may propose strategy/risk changes; A02 may evaluate them. They must never relabel strategy optimization as bug repair. A06 and A09 enforce this distinction. A production activation requires explicit evidence and the applicable owner/release gates. A successful research candidate is not automatically activated by the cloud swarm.
