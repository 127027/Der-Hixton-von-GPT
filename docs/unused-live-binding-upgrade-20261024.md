# Upgrade an unused disabled Live binding without enabling trading

A user can have a saved disabled Live control from strategy 5, but no normal
Live order has ever been reserved or sent. Installing strategy 6 preserved that
control. Status could display `ready: true` after a passed 50-USDC test although
explicit activation would fail with `Live account/strategy cannot change in place`.

Startup now upgrades this narrowly defined unused control. It requires the exact
frozen strategy-5 configuration, the exact reviewed entry-capital-only strategy-6
configuration, a current on-disk source fingerprint, matching current credential,
control and baseline account fingerprints, `LIVE_DISABLED`, and entries disabled.
All Live intents, fills, order audits, request diagnostics, events, positions, dust,
diversification decisions and entry-risk decisions must be entirely empty.
Previously traded, uncertain, partially initialized, foreign-account or unknown
strategy ledgers are not eligible for this migration.

The full prior control is archived alongside the new configuration, application
version, source and UTC timestamp. Audit and control update share an IMMEDIATE
transaction. Only strategy/application/source binding changes; disabled state,
baseline, checkpoints, capital, daily risk and diversification latch remain intact.
Reopening an already migrated installation creates no additional migration.
If the vault cannot supply the current credential identity at startup, migration
is skipped. The explicit activation path can retry it once that identity is
available, under the same guards and before any baseline refresh.

Trial journals, original source/strategy identities and the durable execution-test
acceptance are never rewritten, deleted or rearmed. A source patch does not
invalidate a genuinely passed historical execution test. It also does not turn
that historical test into a real-world test of the new strategy implementation.

Startup never performs an exchange request or enables Live. The separate explicit
authenticated activation still requires the current source guard, healthy aligned
market data, fresh Binance permission/account checks, balance reconciliation and
all existing risk/order gates. Activation now also rejects a foreign/unknown
account or strategy *before* it can refresh an old baseline; it rechecks identity
inside its write transaction.

Offline tests cover explicit activation after the eligible migration, no automatic
orders, preserved acceptance/checkpoints/risk fields, current credential binding,
every history/exposure guard, rollback on write failure, repeated startup and
unchanged baselines after refused activations. No strategy parameters, signal
selection, entry sizing, exit rules or costs change in this patch.
