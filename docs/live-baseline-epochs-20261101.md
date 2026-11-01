# Reconciliation after an explicitly disabled, settled Live session

A completed profitable or losing position changes the account balance. Previously,
explicitly enabling a settled session again captured that current balance as the
baseline while reconciliation still added every historical fill. A 1,000-USDC
account that completed a trade at 1,050 USDC therefore incorrectly expected 1,100
USDC after re-enable. The rejected activation also left the refreshed baseline
persisted.

Each explicit baseline refresh now records both the actual account balances and
the stable `(account, symbol, trade_id)` identities already represented in them.
Subsequent reconciliation adds only movements not in that captured set. Original
fills, order identities, fees, trade history and the original 50-USDC acceptance
are retained. Implicit SQLite row numbers are not used: storage maintenance must
not change which exchange fills a baseline includes.

The balances and inclusion set are written in one transaction. Refresh requires
the same account, disabled entries, no owned positions, no unresolved intents and
no order event awaiting application. A snapshot preceding recorded order history
is rejected before either the baseline or inclusion set changes. Account checks
read the baseline, inclusion set, subsequent movements and unresolved intents from
one coherent database snapshot.

An existing installation initially receives an empty inclusion table. Its original
baseline therefore continues to reconcile against all original fills. A restart,
source update or restored Internet connection does not refresh a baseline. Only
the existing explicit, settled re-enable path may begin another epoch. Deposits,
withdrawals or changes to unrelated holdings while fully disabled can still be
captured during that explicit action; changes during an active session remain
reconciliation failures.

This is an account-bookkeeping correction. It does not change signals, portfolio
allocation, fees, backtest results, strategy versions or the requirement for
separate authenticated Live activation. It introduces no new API-key access or
exchange submission route.
