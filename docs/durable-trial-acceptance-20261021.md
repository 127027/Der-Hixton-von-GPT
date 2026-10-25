# Durable technical execution-test eligibility

The owner requires one correctly completed automatic 50-USDC test, followed by
durable eligibility to explicitly activate ordinary Live. Restarting or installing
a later release must not require repeating the historical execution test. Starting
another test explicitly suspends eligibility until that test also passes. Live is
never enabled automatically by completion, migration, installation or restart.

Previously `LivePreparation` required the completed test's entire Python-source
fingerprint, application version, allocator and strategy to equal the running
release. Even notification-only changes consequently disabled the Live button.

`SIGNAL-ROUNDTRIP-ACCEPTANCE-1` separates historical execution evidence from current
runtime identity. `trial_acceptance` persists a digest bound to the latest trial
and tested API-key fingerprint (not a verified Binance account ID). The proof
requires two distinct confirmed FILLED orders, full finite positive fill totals,
50-USDC BUY budget, automatic strategy signals, each submission within the existing
90-second signal window, zero remaining owned quantity, account/baseline identity
and a completed balance-reconciliation audit after the fills. Profit is not a
requirement. Fees in other assets remain separately reported.

Certificate issuance shares the completion transaction. Startup can derive a
certificate from an existing genuine, qualifying current journal. Status reads
never migrate or write. The proof is rechecked against the original current
journal on each eligibility read. Original source/strategy/allocator identities
are never changed. Archived trials never grant eligibility. Archive/rearm deletes
the current certificate transactionally, including across crashes, failed or
canceled subsequent tests. An unsuccessful preflight before archiving preserves
the previous completed test and certificate.

The historical audit is a local runtime record, not a signed exchange document or
a fresh Binance lookup. The certificate is not tamper-proof against a malicious
local database writer. It neither promises Backtest/Paper/Live fills at identical
prices nor certifies performance or a later trading implementation. A replacement
API key cannot silently inherit the old key's proof. Incompatible acceptance
contracts require an explicitly reviewed acceptance-version migration.

Live still requires explicit local authentication/activation, the current
on-disk source guard, healthy current market data, saved budget and entry settings,
fresh Binance permission/account preflight, reconciliation and existing order/risk
gates. Missing/corrupt proofs and any new unsettled test remain closed. Ordinary
strategy logic, Backtest and Paper calculations are unchanged by this patch.

Offline coverage exercises real order-adapter parsing, journal fills and account
reconciliation against a fake exchange; restart/release persistence; optional
retest invalidation; wrong keys; incomplete/foreign/non-finite fills; manual or
late historical tests; startup-only migration and reads overlapping a writer.


## Source update versus saved eligibility — 2026-10-25

A stopped server, an expired local unlock session, or source files changed while
an older process is running cannot accept trading actions. None of these deletes
a valid execution certificate. The UI exposes the concrete action blocker next
to each button and keeps historical acceptance separate. If an update requires a
restart, it says that no new 50-USDC test is needed. After restart the existing
journal/key proof remains eligible; warmup, local unlock and fresh account checks
still apply before a user explicitly enables Live. The optional retest requires
ordinary Live to be completely off and warns that it replaces eligibility.

The source guard applies to arming the first trial as well as voluntary retests.
A mismatch cannot masquerade solely as "already COMPLETED" or arm a stale-source
first trial. Backend and UI regressions cover an empty install before/after fake
key setup, genuine fake-exchange BUY/SELL/reconciliation, source-update blockage,
reopening/restarting against the same journal and restored technical readiness.
No restart, GET refresh or certificate migration automatically enables Live or
starts another test. A separate new installation never imports another machine's
private key or execution certificate from the public download.
