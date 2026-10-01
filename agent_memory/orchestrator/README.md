# Hixton Master Orchestrator V1

This directory contains the **parallel, non-authoritative** master-orchestration layer introduced after the fully green Hixton 0.5.0 AVAX/DOGE promotion at commit `128b11ff92e07134f0fec88ebeacc27734df5d20`.

## Phase

V1 is intentionally **SHADOW_ONLY**.

It may read the active mission, registry and A01-A11 reports and produce a routing plan. It may not:

- alter the canonical strategy;
- alter Paper or Live runtime state;
- reset accounts or ledgers;
- place real or testnet Binance orders;
- use Binance private credentials;
- merge code;
- replace A09 or A11;
- spend Codex/Agents/Dot budget by default.

The current A01-A11 GitHub Actions swarm remains the authoritative engineering and release path.

## Cost model

The default AI budget is **zero calls per cycle**. Ordinary work remains deterministic:

- status and evidence inspection;
- missing-report routing;
- retry/rerun decisions;
- pytest, Ruff, mypy and compile checks;
- public Binance market checks;
- backtests and regression runs;
- A09 QA and A11 governance.

An intelligent-model escalation is only a *candidate* when an unknown/novel engineering problem remains after deterministic diagnosis. V1 never performs the model call itself. A future adapter may do so only with an explicit owner unlock and a positive per-cycle budget.

## Intended evolution

1. Shadow planning alongside A01-A11.
2. Compare routing decisions with A10/A11 evidence.
3. Permit deterministic dispatch only after parity is proven.
4. Add an optional low-volume Codex/Agents adapter for genuine unknown engineering work.
5. Add OpenAI Dot as a persistent supervisor when available, without removing GitHub as source of truth or A09/A11 independence.

## Security boundary

Cloud orchestration is key-free and order-free. The local protected Hixton runtime remains the only place that may use owner-supplied Binance Spot credentials for the controlled 1x50-USDC trial and later explicitly enabled Live operation.
