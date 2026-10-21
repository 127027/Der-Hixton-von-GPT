# Concise Telegram trade messages

Owner request: describe confirmed real-money entries and closes at a glance, with
actual size, per-trade result, cumulative bot result and the current Binance USDC
balance. Paper and arming remain silent. Sending a preview never places an order.

The original detailed execution message stays in `detail_body` locally. Structured
facts produce the compact outgoing title/body. Order/trade IDs and signal diagnostics
are not included in the compact message. Quote amounts display rounded cents;
full exact quantities, quotes and fees remain in the execution journal/details.

`Bot abgeschlossen (N)` sums each distinct fully reconciled automatic zero-residual
roundtrip once, separately per API-key fingerprint and quote currency. It includes
automatic one-shot tests and normal Live cycles, incorporates partial exits only
at final completion, and excludes Paper, manual operator tests, deposits and cycles
with unvalued residual holdings. Quote-denominated fees are deducted. Unvalued BNB
or other third-asset fees are explicitly labelled `vor BNB`/asset; no net-USDC
valuation is invented. Fees for the reported trade are displayed separately.
This is realized bot PnL for the retained journal, not all Binance account income
or the unrealized result of still-open positions.

The cumulative result is frozen with its execution event when enqueued. Retries
cannot replace an old event's total with later profits. Delivery deduplication,
private chat binding, opt-in epochs and password/origin controls remain intact.

Each trade delivery uses a dedicated signed read-only Spot-USDC snapshot reader
after execution, bypassing the UI success cache. Successful reads are not cached;
failed reads retain the existing 60-second retry cooldown and remain unavailable,
never stale successful balances. The tested key must match the
current saved key under the credential lock. The message labels total/free USDC
and the observation time; these figures exclude coin holdings and are not a
calculation of the trade's profit. Missing, stale, pre-execution or invalid data
produce an explicit unavailable warning while the confirmed trade is still sent.
Delivery/account lookup never holds a transaction on the trading ledger and never
changes entries, exits, approvals or risk settings. The precise attempted outgoing
body is retained in `last_payload` before transmission, including retry snapshots.
Shutdown guards prevent a new Telegram call after a slow balance lookup returns
to a stopping worker; the same pending event remains deliverable after restart.

These are notification-only changes, but the existing full-source guard still
applies before a new trial BUY. A waiting test is not silently rebound or re-armed
after installation; its owner must explicitly re-authorize the test after the
source update. Already-owned exits retain their original obligations. Completed
technical acceptance remains governed by the durable acceptance policy.
