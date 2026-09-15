# Security and real-money boundary — verified 2026-09-15

## Core safety invariant

The repository contains live-preparation/order infrastructure but **real order release is intentionally not product-enabled**. Repository agents, CI and the autonomous swarm have no authority to weaken this boundary. A green backtest, Paper replay, UI state or fake-exchange test never implies live readiness.

## Local network/UI boundary

- UI binds to `127.0.0.1`, not a remote interface.
- FastAPI TrustedHost/security headers restrict use.
- Mutating browser actions require exact local Origin and explicit local-action header; no broad CORS trust.
- Sensitive API responses are `Cache-Control: no-store`.
- Visible browser presence and terminal are part of runtime lifetime; there is no intended hidden daemon mode.
- Instance shutdown requires matching local installation/session metadata and random control token; an unknown process on the port is not killed.

## Credential boundary

`live/credentials.py` uses Windows Credential Manager Generic Credentials scoped to exact Hixton target names. There is no plaintext config/env/file fallback for the live-preparation key/secret.

The local Hixton password is not the Binance password. It stores an scrypt verifier (not cleartext) and gates a short-lived browser session. Browser cookie is HttpOnly/SameSite=Strict and server-side token state is process-local. Restart invalidates session. Failed authentication is rate-limited/temporarily locked.

UI never receives stored key/secret values. Inputs are bounded/cleared and credentials are not put in browser storage or repository artifacts. Error handling deliberately avoids reflecting signed URLs, headers, provider raw text, secrets or full account identifiers.

Known limitation: malware/admin/same-user process memory or browser compromise is outside what an application-level local password can fully prevent; OS account/BitLocker/update/IP controls remain operator responsibilities.

## Binance permission/preflight boundary

Read-only authenticated preflight client uses fixed official HTTPS host/endpoints, no redirect/proxy/automatic retry and no order/withdraw/transfer operation.

Preflight checks include:
- account can trade Spot;
- read and Spot-trade key permissions;
- dangerous withdrawal/transfer/margin/futures permissions must not be enabled/unclear;
- IP restriction expectations;
- open orders / locked balances;
- unexpected foreign balances;
- sufficient free USDC for the planned one-off test;
- all active USDC markets and current exchange rules.

A successful preflight is short-lived runtime evidence only and still does not release an order.

## Order-send defense in depth

Low-level signed order transport exists in `live/exchange.py`, but higher-level composition in `live/preparation.py` remains blocked by multiple independent release conditions. Current productive trial arming/submit is deliberately supplied hard-false gates; `/api/live/enable` and trial-start route respond 409 while release blockers remain. CLI `live` is also disabled.

Therefore deleting a blocker message, changing a UI button, or obtaining a valid Binance key is insufficient to send an order.

A06/A09/A11 must treat any diff that changes these gates as security-critical. A patch that merely turns `False` to `True`, bypasses release_check, directly exposes low-level exchange submit, or makes UI call the adapter directly is automatically unacceptable without a separately explicit owner real-money release mission and complete current live acceptance evidence.

## Future trial execution safety model

If separately released later, the intended one-off scope is exactly one new qualified 50-USDC BUY entitlement across all ten coins, followed by management of only that bot-owned position until the regular strategy exit.

Required invariants already represented in architecture/tests:
- fresh signal and frozen active profile;
- global exactly-once entry entitlement;
- immutable intent/client order ID;
- persist submit claim before network send;
- price/filter/free-cash/ownership/risk gates immediately before send;
- no blind retry after timeout/unknown response;
- query/reconcile ambiguous state;
- partial fills booked individually;
- fee kept in actual asset;
- SELL quantity no greater than bot-owned received base;
- account baseline/known-fill reconciliation before declaring completion;
- user/foreign holdings are never silently adopted/sold.

Still-open product evidence from DMS20: full pre-send live market/filter gate incl. MARKET_LOT_SIZE, clean tradable remainder/dust behavior, complete foreign-order/account isolation proof and external Testnet/operational fault acceptance. These are external/runtime release blockers, not repository-understanding gaps.

## Paper/live separation

Paper uses real public market timing/data but simulated fills/cash. It does not access live credentials to trade. Paper position/account state is not a claim of Binance asset ownership.

The active USDC Paper DB is separate from historical USDT account history. Migration did not rename old economic quote or import old Paper holdings into live state.

Paper settings may be reused conceptually by future normal live mode, but saving slots/notional does not enable live and does not create Binance cash.

## Backtest/research safety

Backtest/research code has no exchange order side effect. USDC review public market downloads write a dedicated validation cache, and same-window control DB access can be read-only. Reports are immutable evidence and are explicitly labeled historical simulation rather than Binance execution proof.

Research modules cannot activate Paper by themselves. Positive historical performance must not be used to bypass soak/security/live gates.

## Data/integrity safety

- strategy/config/data/source hashes in reports detect stale/mismatched evidence;
- Python source fingerprint blocks trustworthy new runtime backtest after on-disk source patch until process restart;
- Candle revisions retained rather than silently overwriting historical evidence;
- invalid/gapped/provisional candles fail closed;
- Paper cycle persistence is atomic/idempotent;
- live order journal is append/idempotency oriented and conflicting duplicate fills fail closed;
- old incompatible Paper DB is rejected rather than silently migrated into a new quote account.

## Secret/public-repository hygiene

Never commit or print:
- Binance key/secret;
- local authentication secrets/session tokens;
- runtime DB/account dumps with identifying data;
- credential-vault bytes;
- backup archives;
- signed URLs/headers.

Tracked example config is secret-free. Runtime data/backups/logs are ignored. If a real key is accidentally published, removing it from Git is not enough; operator must revoke/rotate it.

## Agent-swarm security contract

1. A10 may orchestrate code/test/research work but gets no live-release capability.
2. A05 can observe runtime health but cannot auto-place/recover an exchange order.
3. A07 may query public/existing authorized diagnostic data only when task/environment permits; never dump credentials.
4. A08 cannot relax risk/live safety simply to improve returns.
5. A06 must flag any expansion of authenticated/real-order reach as a cross-component security change.
6. A09 requires explicit security acceptance for live-bound changes and verifies hard gates stay closed for ordinary engineering missions.
7. A11 audits that no specialist bypasses A09 or reclassifies a blocked live feature as complete.
8. Agent/CI tests use mocks/Testnet only when explicitly authorized; **never real-money orders**.
9. Agent orchestration should use isolated Git worktrees/branches and clean-tree checks; it must not read ignored operator data by default.
10. Any future live-release mission must be explicit, separately scoped and cannot be inferred from a generic request to improve the bot.

## Threat/control map

- Look-ahead/repainting → closed-bar rules + independent golden/replay tests.
- Data gap/stale feed → strict audit, pause/recovery, no synthetic bars.
- Dependency/patch regression → pinned runtime deps, QA gate, A06 regression matrix.
- Duplicate order → immutable ID, claim-before-send, reconciliation/no blind retry.
- Foreign/manual order → dedicated account expectation + reconciliation/live halt.
- Secret disclosure → OS vault, redacted errors, no tracked secret config.
- Paper/Live confusion → permanent mode truth + 409 gates + separate fills/accounts.
- UI stale state → server-source provenance + no-store + A04 checks.
- DB corruption/reset → integrity checks, atomic transactions, explicit archive-only reset.
- Hidden bot instance → visible session/terminal lifetime + authenticated singleton replacement.
- Agent scope drift → A10 assignment + A11 independent governance.

## Security conclusion

Repository understanding of the live/security boundaries is complete enough for engineering work. What remains intentionally unknown is external operational truth (actual current operator key permissions, current exchange conditions, Testnet/real-account acceptance, external backups). Those facts must remain labeled external/runtime unknowns and cannot be solved by reading more repository code.