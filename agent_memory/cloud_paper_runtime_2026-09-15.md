# Verified GitHub Cloud Paper runtime — 2026-09-15

## Owner operating contract

Current project operation is Paper-only:
- real public Binance USDC Spot market data;
- simulated Paper fills/orders only;
- one persistent Paper account across GitHub-hosted runner cycles;
- no real-money orders;
- no Testnet orders;
- no Binance private/account credentials in GitHub Actions or autonomous agents.

## Cloud execution model

GitHub-hosted jobs are ephemeral, so Hixton does not pretend that one VM is a permanent trading process. The default-branch scheduler invokes the reusable Paper workflow six times per hour. Each cycle:
1. checks out `gpt/usdc-audit`;
2. builds a fresh Python virtual environment;
3. restores `data/hixton-usdc.sqlite3` from the isolated `paper-runtime-state` branch;
4. validates SQLite integrity;
5. uses the existing `RuntimeSupervisor._sync_and_analyze(initial=True)` startup/recovery path;
6. fetches real Binance public market data through Binance's market-data-only REST host `https://data-api.binance.vision`;
7. catches up finalized native 1h candles exactly once from persisted Paper checkpoints;
8. uses the canonical strategy, TradePolicy, allocation, risk and PaperEngine logic, including modeled next-bar-open fills;
9. checkpoints WAL, validates the resulting database and Paper-only invariants;
10. replaces the machine-managed `paper-runtime-state` branch with the new compressed database plus a manifest.

This is continuous catch-up operation for the native 1h strategy, not a claim that a single GitHub VM remains alive forever. Scheduler delay does not invent or skip finalized 1h candles; the next successful cycle processes any missing closed bars from persisted checkpoints.

## Reset protection

The first successful cloud initialization publishes the durable tag `paper-cloud-initialized`. If that tag exists but the `paper-runtime-state` branch is missing, the workflow fails closed instead of silently creating another 250-USDC account.

Normal cycles never top up/reset the Paper account. A first-ever initialization starts at the latest eligible market point and does not backtrade historical signals.

## Verified live-data evidence

Initial successful cloud cycle: GitHub Actions run `35026894961`.
- Paper mode: `PAPER_ONLY`
- market data: `BINANCE_PUBLIC_USDC`
- endpoint: `https://data-api.binance.vision`
- starting/cash/high-water equity: 250.00 USDC
- settings: 3 slots × 80.00 USDC
- checkpoints: all 10 symbols
- open positions at initialization: none
- halted: false
- real-money orders allowed: false
- Testnet orders allowed: false
- state branch and initialization tag were persisted successfully.

Resume proof: GitHub Actions run `35027389418`.
- existing state restored and passed pre-cycle SQLite integrity;
- real Binance Paper recovery cycle passed;
- post-cycle SQLite/WAL integrity passed;
- state persisted again;
- manifest links `previous_workflow_run_id=35026894961`;
- same Paper account remains at 250.00 USDC because no new qualified trade had occurred between the two runs;
- source provenance correctly records engineering commit `baeec362e1b6627c6347eb3480768bbbf9b094bf`.

## Incident resolved during setup

The normal API host `https://api.binance.com` returned HTTP 451 from a GitHub-hosted Azure runner because that runner region was restricted by Binance. This was not treated as a bot defect and was not bypassed with synthetic data. Cloud Paper was moved only to Binance's official public market-data-only endpoint. The normal project configuration was not globally rewritten; the cloud wrapper overrides only the public data base URL.

## Agent rules

A01–A11 must treat this document and `agent_memory/swarm/taskboard.json` as current operating evidence. In particular:
- do not request private Binance credentials;
- do not replace operational market data with generated/synthetic candles;
- do not create a second Paper execution engine;
- do not reset the state branch/account to make research easier;
- deterministic fixtures remain appropriate for unit/regression tests;
- strategy/risk changes are research until separately approved for activation;
- A05 monitors cloud-cycle liveness/state freshness, not an imaginary permanent local process;
- A06/A09 must preserve Paper/backtest parity and state-resume behavior after relevant patches;
- A11 must reject any mission that weakens the Paper-only/no-real-order boundary.
