# Unknowns and resolved questions — 2026-09-15

## Repository-understanding questions

None remain open after the inventory, architecture, dataflow, UI, storage, tests, security and final cross-check passes.

Important resolved points:
- Active runtime is V6-USDC with one shared strategy/profile source, not an independent USDC strategy fork.
- Old USDT 733.31 versus current ~203 is primarily a different start/account path; same later window USDT and USDC are ~201/204.
- Shared 3×80 low trade count is dominated by persistent drawdown halt, not a hidden one-slot limit.
- Isolated 10×250 and shared 3×80 are intentionally different account models.
- Paper and shared portfolio are separate implementations but share strategy/policy/risk and have explicit exact-fill/restart parity regression tests.
- Historical/research V4–V9 modules do not activate Paper automatically.
- Low-level live order code exists, but productive arming/submit remains intentionally hard-blocked and UI/CLI cannot release it.
- Normal startup never resets the Paper account; reset is explicit offline maintenance with archive verification.
- UI TypeScript source and tracked built static bundle are separate artifacts; UI source changes require rebuild.
- The previous laptop-bound `StartAgent.bat`, `AgentChat.bat`, `scripts/local_agent.ps1`, `scripts/agent_chat.ps1` and local swarm runner were removed. The authoritative engineering swarm now runs through GitHub Actions on GitHub-hosted virtual machines.
- Older DMS USDT/service/budget statements are historical and are superseded by newer owner decisions/current DMS headings/current implementation; historical evidence must not be globally rewritten.

## External/runtime unknowns — deliberately not solved by repository reading

These remain facts that require an external service, future market data or an explicitly authorized runtime acceptance test:
1. `OPENAI_API_KEY` must exist as a GitHub repository secret before the official Codex Action can execute cloud agents. A laptop ChatGPT/Codex login cannot be reused by GitHub-hosted runners.
2. Current real Binance account API permissions, IP restriction state, balances, current account-specific fees and real execution behavior.
3. Current Binance filters/status at a future order instant; repository stores/uses snapshots but exchange facts can change.
4. External Binance Spot Testnet/operational fault acceptance for the unreleased one-off live trial.
5. Full foreign/manual-order history/account isolation proof and final tradable-remainder/dust acceptance for live release.
6. Actual external encrypted backup target/retention/restore health on the operator machine.
7. Future profitability/robustness of any strategy or market regime.
8. Operator-machine sleep/power/network behavior beyond tested/simulated scenarios until observed in an actual soak.

## Rule for agents

Do not convert an external/runtime unknown into a guessed repository fact. A task that depends on one of these must either collect the authorized runtime evidence or report the limitation. The cloud swarm may use public market data and deterministic test fixtures, but it must never infer or request private Binance account state unless a future owner-authorized acceptance process explicitly provides it.
