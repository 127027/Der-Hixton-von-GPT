# Hixton Engineering Agents

## Current operating model

The repository is maintained by the deterministic eleven-role engineering swarm A01–A11 under agent_memory/swarm/. The active mission is agent_memory/swarm/taskboard.json. GitHub Actions is the authoritative execution path; the normal swarm requires neither an OpenAI API key nor Binance private credentials.

## Durable knowledge

Current durable knowledge is intentionally small:
- agent_memory/state.json — current product/agent checkpoint;
- agent_memory/architecture.md — current architecture;
- agent_memory/dataflows.md — current data and control flows;
- agent_memory/swarm/README.md — swarm overview;
- agent_memory/swarm/registry.json — exact A01–A11 registry;
- agent_memory/swarm/protocol.md — orchestration and evidence rules;
- agent_memory/swarm/taskboard.json — active/archived missions;
- agent_memory/swarm/agents/ — role contracts.

Do not recreate the superseded bootstrap inventory/security/storage/ui-map files unless a future mission explicitly needs a new durable artifact.

## Source-of-truth order

For current behavior:
1. current code and tests;
2. active taskboard mission and agent contracts;
3. current DMS;
4. README/backtests current journal;
5. Git history for obsolete behavior.

Historical Git content must not be interpreted as an active product requirement.

## Product invariants

- Product strategy: current V6 only.
- Canonical V6 source: src/hixton/domain/versions.py.
- Config stores only strategy.key = v6; no duplicated version/profile snapshot.
- Public Binance USDC market data; Paper plus guarded local Live execution with a separate controlled 1×50-USDC first roundtrip.
- Main acceptance model: one saved `max_capital_usdc`; `CAPITAL-V1-2X50PCT` derives two `ranked_repeat` tranches at 50% each (default 250 → 2×125).
- 10×250 is per-coin diagnostic research, not main account capital.
- No permanent portfolio drawdown halt; 5% UTC-day pause and technical safety gates remain.
- Cloud/agent runs may never send real/testnet orders. Local real-money execution remains fail-closed and starts only through the explicit controlled 1×50-USDC gate; automatic strategy activation/merge is prohibited.

## Agent workflow

A01 requirements/docs -> A02 research -> A03 Paper parity -> A04 UI freshness -> A05 runtime liveness -> A06 integration/regression -> A07 Binance/data -> A08 strategy/risk -> A10 routing/evidence -> A09 independent QA -> A11 governance.

A promotable optimizer artifact is new work, not an automatic release. A10 routes it through A02/A08 and the affected implementation specialists; downstream evidence is rerun. A09 and A11 must evaluate the exact latest commit.

## Repository hygiene

Keep only current product artifacts on the current branch. Do not park files with old/backup/final-copy names. Git is the archive. Obsolete product modes must not remain selectable merely for historical convenience.

## Safety

Never send real Binance orders from CI, agents or an automated optimization run. Never weaken validation or risk gates to improve a number. Never claim backtest performance as future profitability.
