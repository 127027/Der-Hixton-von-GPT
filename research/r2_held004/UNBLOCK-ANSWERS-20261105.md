# Concrete unblock answers — owner request 2026-11-05
Deadline: 2026-11-06 16:00 Europe/Berlin. Research only. No product/trading access.

## D3: corrected fixtures and exact-source evidence now available
Tests corrected and committed at e799010ac94d72de0c9f57e87c74b63f544f2f70.
Evidence: research/r2_held004/evidence/CODEX-EXACT-ADAPTER-FIXTURES-20261105.json.
Codex downloaded the exact GitHub core/adapter (Git object IDs verified), not a reconstructed implementation. Original fixtures:6PASS/5FAIL. Corrected positives and two additional negative controls:13PASS/0FAIL under Python3.11.4.
This is ONLY pure adapter QA, not native METHOD_PASS, disabled-C0 parity, or a profitable strategy. Do not repeat unchanged old15fixtures.

## D3: the missing original bundle already exists publicly
Repository:127027/Der-Hixton-von-GPT.
Release:research-data-20261103-five-dot-inputs.
Historical asset704760402:Hixton-Loss-Handoff-20261102.zip,191666867bytes.
SHA256:d1d1cde8347665d74da71f9e44bb3876dc6662bfe4bfc9e34dcab1dfecd84308.
Synthetic asset704760404:Hixton-Five-Synthetic-Worlds-20261103.zip,185238985bytes.
SHA256:5262f12bef7182ae10e2c85fe5b790263404764e98e759196dbdfb7d0970d278.
Release contains frozen f56 engine, Input-Contract.json, original data and original C0 reference ledgers. Historical archive root is Hixton-Loss-Handoff-20261102/; engine/src/hixton/backtest/portfolio.py is below it. Synthetic root is separate. Do not merge contracts.

The existing regular Actions workflow .github/workflows/hixton-r2-hold003-16-native-20261104.yml already demonstrates verified downloading and extraction. Reuse only its setup/download pattern for HELD004 methodology; DO NOT rerun its obsolete HOLD003 candidate or whole16financial series.

Example within a regular existing Actions runner with normal GitHub access:
```bash
mkdir -p bundle extracted
gh release download research-data-20261103-five-dot-inputs -R "$GH_REPO" -p Hixton-Loss-Handoff-20261102.zip -D bundle
echo "d1d1cde8347665d74da71f9e44bb3876dc6662bfe4bfc9e34dcab1dfecd84308  bundle/Hixton-Loss-Handoff-20261102.zip" | sha256sum -c
```
Then validate ZIP members remain below extraction root before extracting (the existing workflow provides that code), verify contract/source hashes, use --bundle extracted/Hixton-Loss-Handoff-20261102. No need to locate Codex's private local directories. If the chat runtime cannot download, use the regular Actions runner; report exact denied capability if it cannot be dispatched. No security bypass.

## D1/D2: actual5year native financial/state outputs are genuinely missing publicly
The newer market-only release is not a financial ledger. Do not label that absence solved by the historical3window bundle.
Use release research-data-20261105-fiveyear-market-only, asset714334556,23369957bytes,SHA256 ad7adb901a56ae974c85f787ff0a4789efb6666f12663877903886f469cb047e.
Input-Contract.json binds15market snapshots,1000USDC synthetic research seed,costs,frozen reference filters and provenance.
Assign ONE existing development owner to produce ONE shared normal-cost continuous C0 research baseline and outputs for D1/D2, only after checking no equivalent1000seed run already exists or is active. This is a new prerequisite, not a broad parameter/backtest series. D1/D2 must not each start their own copy.
The exact f56 strict loader does not automatically support this5year market contract: later SUI history and the shared2023-03-24 13UTC outage require the documented5year compatibility handling from UI branch codex/hixton-backtest-years-20261105,commit8964151000c6ef4c48cfc871de9951e879b9a81a. It preserves strategy behavior in the already-verified overlap, but this5year context is EXPLORATORY_DATA_GAPS, not historical execution parity.
Do not change strategy rules or pretend this is the old frozen16context contract. Do not invent candles/orders or capital resets. Use1000USDC, not account-derived balances. Native source differences and compatibility wrapper must be explicitly bound in evidence.
Export fills/trades/signals and hourly cash/positions/equity. D1 starts attribution with fields actually present; D2 reconstructs states from actual fills where possible and lists missing fields precisely. Do not make a perfect expanded trace a prerequisite for every independent attribution step.
All privacy-sensitive previous account-based5year results remain local and must not be uploaded.

## Coordination answer
No pending ownership decision or keys are needed for these offline steps.
D3's existing HELD004 integration continues independently of the new5year C0 prerequisite. D4 can inspect this corrected exact-source fixture evidence but cannot issue native METHOD_PASS yet.
When input retrieval itself is denied, show the precise tool error. Do not substitute repeated inventory or an invented PASS.
CAP remains archived, unchanged economic gates apply, no additional broad series, no new redundant automation.
