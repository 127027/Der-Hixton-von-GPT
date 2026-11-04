# R2-D3-S01 — pre-outcome execution semantics seal (2026-11-04)

**Research only / existing S01 candidate / not a new strategy / method QA pending.**

### Immutable references
- frozen product `f56d48536525830dd6ea50bf5bc174a6f9aeff8c`, source fingerprint `5cf39658dc6b1ee827ec0daefd73b2384a9edd0ff116ba0203f9ab8bb7737797`.
- historical original archive SHA256 `d1d1cde8347665d74da71f9e44bb3876dc6662bfe4bfc9e34dcab1dfecd84308`.
- synthetic original archive SHA256 `5262f12bef7182ae10e2c85fe5b790263404764e98e759196dbdfb7d0970d278`.
- S01 native source implementation at reviewed branch HEAD `56e97e905badaa25af6acbce82eb74bfa2d44791`. The preceding S01 source and audit module are in that commit's ancestry. For independent approval require same complete tree+source hashes and both exact input archive hashes, not an earlier successful action.

### Rejected exit vs confirmed exit vs unknown
- S01 trigger requests one native full-exit attempt per `(symbol, native original entry_signal_id)`. This set is consumed upon **request**, not upon confirmed sale.
- Original regular exit executes before S01, hence no duplicate sell. An original regular exit is not called an S01 sale and does not launch S01 cooldown.
- Exactly one genuine matching native Fill, plus native full regular-position removal and reconciled cash, fees, basis, dust and released slots: **confirmed S01 native exit**. Start coin-only 24-hour new-entry cooldown at the actual native fill time, expiring exactly after 24 completed hours.
- No matching Fill but an original native explicit filter rejection or dust-to-ledger event: **rejected / untradeable / dust**, not a success. Do not start cooldown, do not credit cash or released sale proceeds, do not automatically retry the same entry every hour.
- Neither Fill nor native rejection, or any conflicting fill/position accounting: **unresolved native execution**. Fail closed, record blocker, no financial pass and no success attribution.
- Frozen f56 is synchronous. It does not model delayed exchange acknowledgments or independent live partial fills. Those require separate later product QA.

### Important interpretation and separate future candidate
The no-hourly-retry rule does **not** logically forbid a later bounded retry policy. Current **S01-A** is strictly once-per-entry, including a rejected attempt. This is a deliberate conservative pre-outcome interpretation of the preregistered no-repeat requirement and may prevent later recovery after a temporary filter rejection. It must be reported as a possible lost protective exit, not patched after seeing financial results.

A prospective **S01-B** could specify a single deterministic retry after a newly confirmed valid market-order condition, with explicit maximum attempts, expiration and no overlapping pending order, but is **NOT registered, NOT enabled and NOT part of S01-A financial comparison**. It requires its own preregistration, separate method QA, candidate ID and all sixteen comparisons. Do not choose S01-B because of a known losing interval.

### Gates
- Prior run `41860032713` passed disabled C0 once on an older commit, NOT this sealed tree.
- Existing queued run `41862289840` tests an older activated version and is diagnostic only for newer source.
- Existing queued run `41862839373` tests an older preflight revision and is NOT independent signoff of current tree.
- Existing queued run `41862977181` intends all 16 disabled C0 controls at commit `38b3e39eca7f726a16adfc4a23528f9cd61e729e`, which differs from this seal by documentation only. Reuse only if all executable source, dependencies and original archives are provably identical; verify commit trees/file SHA, not merely run success.
- Do not launch any S01 candidate 16-case finance without real activated native S01 fill ledger reconciliation and **genuinely independent** reviewer METHOD_PASS tied to the exact frozen code and inputs. A green self-authored Actions job alone is not independent authorization.
