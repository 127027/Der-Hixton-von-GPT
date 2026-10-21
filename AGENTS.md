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

### Latest owner selection rule — 2026-10-21

- Owner clarification (2026-10-21): a successfully reconciled, timely automatic 50-USDC signal roundtrip confers durable **technical execution-test eligibility**, bound to the tested API key and original journal evidence. Restarts and subsequent source/application/strategy releases do not erase that historical execution fact. It is not certification of future performance or real testing of a newly changed trading contract. Never rewrite the original test identities as current. An explicitly requested new trial revokes eligibility until a new valid roundtrip completes; archived tests cannot restore it. Full-source-on-disk, current product validation, account preflight/reconciliation, risk gates and separate explicit Live activation remain mandatory. Incompatible acceptance schema/semantics require an explicit acceptance-version migration, never an automatic bypass. See `docs/durable-trial-acceptance-20261021.md`.

- Rank technically eligible, validated candidates by highest net portfolio profit first; lower maximum drawdown is the second criterion. Do not silently replace this order with a profit/drawdown weighted score or choose a lower-profit candidate solely for lower drawdown.
- Compare candidates on the same frozen candle snapshots, reporting window, starting capital, reinvestment settings, market universe, exchange filters and costs. Old headline amounts from another rolling window are historical evidence, never a current winning configuration.
- Backtest, Paper, the next explicitly authorized 50-USDC trial and ordinary Live must use the same active versioned strategy, policy, allocator and risk rules. There is no separately optimized backtest strategy or hidden higher-return Live strategy. Preserve owned legacy exits under their frozen obligations; never relabel their old acceptance as current.
- Eligibility still requires existing validation, cost/stress review, execution parity, reconciliation and explicit trading activation. Higher historical profit never authorizes weakened gates, lookahead or a new real order. Report the best tested eligible candidate, never guaranteed future optimality or identical realized profits.
- The active local product is the `v8r` definition in `src/hixton/domain/versions.py`. V6 and older V8/V8r runs remain frozen historical/regression evidence; stale memory or mission descriptions cannot override current code and this latest owner instruction. See `docs/selection-policy-20261021.md`.

### Frozen anchors and unchanged safety invariants

- **V6 is the frozen ten-coin Core regression anchor.**
- **V8 is the original 15-market anchor; the active owner-selected product is v8r as defined in current code.**
- V8 reuses V6 Core indicator parameters and adds a separate five-Satellite research layer. Owner-authorized refinement on 2026-10-07: DOT adds slope_bars=24 to its original CMO threshold; other Core policies stay identical. V6 remains frozen.
- Owner-requested local trade-focus revision (2026-10-06): NEAR, AAVE and BCH are shared-active fillers; SUI and UNI remain research-only after negative shared contributions. The prior 205-trade snapshot is preserved at e40258260d3a77ab88d3216a6c029adbdb5bacf0. Historical SAT2 review artifacts describe the prior strategy and cannot certify this revision.
- V8 and V6 use the original ranked-repeat Core allocation. A lone Core candidate can use both X/2 tranches.
- Core has absolute priority: all fillers exit for eligible Core entries at the next executable open. Fillers only enter when no Core is active. Saved gap_fillers_enabled can disable filler entries, never Core priority.
- All five Satellite profiles retain their momentum/slope/ATR regime gates, retain their original per-coin holding horizons, and may re-enter an eligible UP trend at 00:00/12:00 UTC decision boundaries. Indicators never receive provisional/future candles.
- Only finalized 1h bars may steer decisions. Runtime must never use future/holdout information.
- `max_capital_usdc = X` is the manual capital input; automatic mode uses fresh available Binance Spot USDC under the current rules. `CAPITAL-V1-2X50PCT` is the frozen two-half anchor; current v8r uses its code-defined allocator/diversification. 250/125 and 1000/500 are examples, not fixed live budgets.
- The 1600-USDC result and the earlier rejection of a roughly 392-USDC reduction are historical research checkpoints, not current selection targets. Preserve their regression evidence and report net PnL, drawdown, costs, filler contribution and temporal results, including stress costs; never disable risk/exchange gates to raise trade counts.
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
