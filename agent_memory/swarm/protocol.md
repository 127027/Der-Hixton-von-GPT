# Swarm protocol

## 1. Intake and preflight

Every owner request becomes a task with a unique ID, explicit objective, invariants, prohibited actions, affected areas, evidence requirements and acceptance conditions. A01 reviews the relevant documentation and current implementation before engineering starts. Contradictions are recorded, not silently resolved.

The authoritative dispatcher is GitHub Actions. It checks out `gpt/usdc-audit` into GitHub-hosted virtual machines and builds fresh Python virtual environments. The owner laptop is not part of the execution path. The default eleven-role swarm is deliberately **key-free**: it requires neither an OpenAI/API secret nor Binance private credentials.

## 2. What an agent means in key-free mode

A01-A11 are independent deterministic engineering roles. Each role owns executable inspections, regression tests or gates and emits a machine-readable evidence report. They can detect regressions, stale runtime state, missing evidence, Binance public-data failures, Paper-ledger problems, broken tests and governance violations without a language-model API.

Key-free roles do not pretend to invent arbitrary novel code patches. A10 may route and classify failures and may only perform explicitly implemented safe deterministic remediation. A new behavioral code solution still requires a reviewed engineering change; it is never fabricated from a green status check.

## 3. Assignment and independence

A01-A08 execute as independent cloud jobs. A10 consumes their reports and checks assignment coverage, missing work and repair routing. A09 then performs an independent full QA gate. A11 runs last and verifies that A10/A09 did not skip or misrepresent evidence. No role may approve itself.

## 4. Heartbeats and anti-stall

GitHub job status, artifacts and timeouts are the heartbeat mechanism. Missing JSON evidence, timeout, failed deterministic commands, stale Paper state or unavailable required public market data count as a failed duty. A10 marks the affected duty for repair/retry. A11 refuses governance until required evidence is complete.

## 5. Evidence discipline

Claims must point to code, tests, committed reports, deterministic command output or runtime observations. Historical profit alone is never proof of correctness. A result must distinguish code defect, configuration mismatch, data difference, state/path dependency, intended behavior, research hypothesis and external-runtime unknown.

Operational Paper evidence uses real public Binance USDC market data. Deterministic fixtures are permitted for unit/regression tests only.

## 6. Paper-only security boundary

The project phase is Paper-only. Cloud jobs receive no Binance private credentials and do not call authenticated order endpoints. Real and testnet orders are forbidden. The existing protected UI/vault area for a future owner-supplied Binance API key remains separate and is not needed by Paper or by the swarm.

The future presence of a Binance key must never change the default cloud swarm into a trading actor. Productive real-order release remains a separate explicit release problem.

## 7. Mandatory cross-checks

A06 asks after every behavioral patch: what else could this have changed? It checks configuration, shared strategy/risk rules, data assumptions, Paper, Backtest, runtime, storage/restart, API/UI, generated assets and documentation as applicable. Quote/symbol migrations require explicit same-window old-vs-new comparisons and state-reset analysis.

## 8. QA gate

A09 runs on a fresh GitHub runner after A10. Deterministic QA includes Python compilation, Ruff, mypy, full pytest and application status. A09 produces `QA_PASS` or `QA_FAIL`. It cannot alter production behavior to make tests pass. PASS alone is not DONE.

## 9. Governance gate

A11 runs after A09 on another isolated cloud job. It verifies that all required roles actually emitted evidence, every preceding role passed, A09 emitted `QA_PASS`, the Paper-only security boundary still holds, and no failure was hidden. Only then may A11 emit `GOVERNANCE_PASS`.

## 10. Repair loop

A failed specialist report is routed by A10 to the responsible area. Deterministic retry/remediation may be used only when it is explicitly encoded and cannot change strategy or release safety. Otherwise the workflow remains failed with evidence for the next engineering change. Downstream QA/governance never converts an unresolved failure into PASS.

## 11. Continuous cloud watch

The default-branch dispatcher runs the key-free swarm on schedule and on manual dispatch. A05 owns Paper runtime/liveness checks. A07 independently validates the official public Binance market-data-only endpoint. A10 keeps failed duties visible. A11 detects missing or contradictory evidence. None of these roles needs an API secret.

## 12. Research versus repair

A08 may identify strategy/risk hypotheses and A02 may evaluate them through existing research/backtest machinery. They must never relabel strategy optimization as bug repair. A successful research candidate is not automatically activated. Strategy/risk activation requires a separate explicit owner decision and applicable release evidence.
