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
