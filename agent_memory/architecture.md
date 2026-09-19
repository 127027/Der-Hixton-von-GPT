# Hixton architecture — current V6 product

Status: CURRENT · 2026-09-19

## Product boundary
Hixton is currently a Paper/backtest product. Operational market data is public Binance USDC; orders and fills in Paper are simulated. Real-money and testnet order submission are outside the released product boundary.

## Single strategy source
`src/hixton/domain/versions.py` owns the canonical V6 ten-coin profile map and immutable digest. Runtime config stores only `strategy.key = v6`; it does not duplicate the digest or profiles.

The same V6 map feeds:
- runtime/Paper signal generation;
- isolated 10×250 research;
- shared 250-USDC / 3×80 `ranked_repeat` portfolio backtests;
- API/UI strategy profile display.

## Main components
- `src/hixton/data/`: public Binance candles, filters, quality and persistence.
- `src/hixton/domain/`: V6 parameters, policies, signal semantics.
- `src/hixton/backtest/`: single, isolated batch and shared portfolio engines.
- `src/hixton/paper/`: persistent simulated account, positions, events, checkpoints and strategy sessions.
- `src/hixton/runtime/`: startup recovery, market synchronization, stream/watchdog and backtest execution.
- `src/hixton/ui/` + `ui/`: local API and TypeScript product UI.
- `scripts/coin_optimization_cycle.py`: research-only Top-K train/validation/full/stress and marginal-3×80 optimization.
- `scripts/cloud_swarm_agent.py` + `scripts/swarm_core.py`: deterministic A01–A11 evidence and governance.
- `agent_memory/swarm/`: current agent registry, roles, protocol and mission state.

## Capital semantics
The authoritative main acceptance model is a shared 250-USDC account with three 80-USDC slots. `ranked_repeat` can assign more than one free slot to one ranked valid signal. These are capacity tranches of one position cycle.

The 10×250 batch is a diagnostic laboratory of ten separate 250-USDC accounts and is not a 2,500-USDC main account.

## Risk semantics
The old permanent 20% portfolio drawdown entry halt is not active V6 behavior. Drawdown remains measured. The 5% UTC-day loss pause, emergency stop, available cash, exchange filters and stale-data safety checks remain.

## Change/release path
Research -> frozen validation/full/stress -> marginal shared 3×80 -> combination gate -> canonical profile patch -> fresh preflight/E2E/regression -> A09 QA_PASS -> A11 GOVERNANCE_PASS -> explicit audited Paper strategy activation when the digest changes.

Automatic research is allowed. Automatic merge, unreviewed profile activation and real/testnet orders are not.
