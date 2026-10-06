# Hixton Engineering Agents

## Current operating model

The deterministic eleven-role swarm A01–A11 under `agent_memory/swarm/` is the authoritative engineering review chain. GitHub Actions is the execution path. Agents require neither an OpenAI API key nor Binance private credentials and may never send real/testnet orders.

## Source-of-truth order

1. current code and tests;
2. active taskboard/coordination mission;
3. current DMS and durable architecture/dataflow notes;
4. README/current backtest evidence;
5. Git history for obsolete behavior.

## Product invariants

- **V6 is the frozen ten-coin Core regression anchor.**
- **V8 is the current 15-market product.**
- V8 reuses the exact V6 Core profiles and adds a separate five-Satellite research layer.
- Active shared Satellites are only NEARUSDC and BCHUSDC. SUIUSDC, UNIUSDC and AAVEUSDC are research-only and may not allocate Shared capital.
- Core has absolute priority. Satellites may enter only while the Core is fully idle and yield required capital at the next executable open.
- Only finalized 1h bars may steer decisions. Runtime must never use future/holdout information.
- `max_capital_usdc = X` is the single capital input. `CAPITAL-V1-2X50PCT` derives two 50-% tranches; 250/125 and 1000/500 are examples, not fixed product constants.
- Shared/product trade count is secondary to robust net PnL, drawdown, costs, occupancy and validation.
- Live stays fail-closed until explicit local owner activation; code promotion alone never arms entries.

## Agent workflow

A01 requirements/methodology/docs → A02 backtest/research → A03 Paper parity → A04 UI → A05 runtime liveness → A06 full regression → A07 Binance/data/rules → A08 strategy/risk → A10 synthesis/repair routing → A09 independent QA → A11 governance.

Any patch invalidates downstream evidence for the prior commit. A09 and A11 must evaluate one exact latest commit. Promotion requires same-head QA_PASS and GOVERNANCE_PASS.

## Durable knowledge

- `agent_memory/state.json`
- `agent_memory/architecture.md`
- `agent_memory/dataflows.md`
- `agent_memory/swarm/README.md`
- `agent_memory/swarm/registry.json`
- `agent_memory/swarm/protocol.md`
- `agent_memory/swarm/taskboard.json`
- `agent_memory/swarm/coordination.json`
- `agent_memory/swarm/agents/`

## Safety

Never weaken validation/risk gates to improve a number. Never claim backtest performance as future profitability. Cloud jobs remain key-free, use public market data only and never place orders. Local owned Live positions may use EXIT_ONLY after a source patch; stale source identity may never open a new position.
