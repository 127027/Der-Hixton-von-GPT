# Shared trial state across browser windows

All pages connected to the same local installation read the same trading state.
Unlock cookies and immediate action acknowledgements remain local to each browser.
An armed trial therefore previously showed a click acknowledgement in one window,
but only `Test: WAITING_SIGNAL` and a disabled start button in another. This did
not demonstrate a second bot or a different trade; the status presentation was
ambiguous. Background browser timer throttling could also delay a status read.

The trial button now displays its server-confirmed stage, including armed/waiting,
pending purchase, open and pending exit. An active stage is visibly selected even
when activation is disabled or the browser is locked. Settings use the same plain
language trial description as the overview. Warmup is an execution block, not a
revocation of an already recorded authorization. Pending/unknown orders never
become confirmed purchases or successful completions in this presentation.

Focus, pageshow and return to a visible tab trigger a fresh read of trial state;
the overview refreshes account/market state and events on those transitions too.
These callbacks only read APIs. Existing server gates, explicit confirmations,
per-browser authentication and the five-second poll remain in place. Old local
action receipts are cleared on subsequent state changes. Failed reads clear the
old armed indicator and explicitly mark the current trial state as unknown.

This patch contains only TypeScript/CSS, generated UI assets, DOM tests and this
note. Python source, strategy, orders, trial identity and trading databases are
unchanged. Static assets can be installed without restarting the process or
canceling/rearming a waiting trial. Already loaded tabs must reload once to load
the new hashed bundle; a server response cannot replace JavaScript already
executing in another browser. Browsers may still differ in authentication or
unsaved form drafts, and suspended/disconnected pages cannot promise instantaneous
updates. No action in another window is simulated by the client.
