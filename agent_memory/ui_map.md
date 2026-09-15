# UI/API map — verified 2026-09-15

## Serving/lifecycle

`Startbot.bat -> src/main.py start -> ui/server.py` serves committed static assets on localhost. `ui/instance.py` prevents unsafe duplicate instances and only replaces an authenticated predecessor from the same installation. `ui/lifecycle.py` owns browser-presence and terminal lifetime. No first UI presence means no trading start; final UI loss/terminal loss stops the runtime.

API responses are `no-store`; FastAPI uses localhost trusted hosts and security headers. Mutating local-browser requests require exact local Origin and `X-Hixton-Action: local-ui-v1`.

## Frontend controller ownership

`ui/src/main.ts`
- initial page bootstrap and navigation;
- periodic polling of status, markets, logs/events and backtest metadata;
- chart selection and rendering orchestration;
- Paper/trading settings form;
- system/backtest/market/Paper rendering;
- stale-response generation counters so late requests cannot overwrite a newer selection.

`ui/src/trading-settings.ts`
- client settings model/bounds/payload composition; server remains authoritative.

`ui/src/settings-draft.ts`
- separates saved settings from current unsaved draft and prevents periodic status polling from clobbering the user's edit.

`ui/src/live-preparation.ts`
- local-password unlock/key management/preflight/live/trial preparation UI states;
- never treats a client-side click as server-confirmed live state;
- HTTP 409 release blockers stay visible.

`ui/src/backtest-context.ts`
- renders stored-run provenance as MATCHING/DIFFERENT/UNVERIFIED;
- explicitly states isolated versus shared-account scope;
- maps portfolio blocked reasons and maximum slot use.

`ui/src/market-signal.ts`
- market-card last-signal semantics. A current UP trend is not represented as a new buy/fill.

`ui/src/session-lifetime.ts`
- presence WebSocket/stop/reload handling consistent with visible-session backend.

`ui/src/styles.css` and source `ui/index.html` are presentation shell/style; no trading decision logic.

Production bundle is `src/hixton/ui/static/index.html` plus hashed CSS/JS assets. Any UI-source patch requires tests, TypeScript check and production build so tracked bundle matches source.

## Backend API surface and full action paths

### Status / dashboard
Browser poll
→ status endpoint in `ui/api.py`
→ RuntimeState snapshot + PaperStore/PaperEngine state + strategy/config metadata
→ UI header/system/Paper/settings render.

Shows PAPER/LIVE_DISABLED truth, health, feed, strategy version, Paper account/settings/soak/risk. Live is not inferred from existence of adapter code.

### Markets
Browser poll
→ markets endpoint
→ RuntimeState current market analysis + active StrategyDefinition CoinProfile + freshness/data-quality state + Paper positions
→ ten market cards.

Cards expose current profile parameters/filters, trend/latest price/latest signal, position/fill distinction. Missing historical signal context is not represented as "never happened".

### Chart
Coin/range/resolution selection
→ chart endpoint
→ CandleStore native 1h + strategy analysis/markers + optional provisional live candle
→ `ui/chart.py` display aggregation
→ frontend candlestick/overlay/markers.

Today/1w/1m default 1h; 1y default 4h display aggregation; 3y default 1d display aggregation. Signals always derive from native 1h. Provisional candle may render but cannot produce confirmed signal marker.

### Positions/events/logs
Browser poll
→ PaperStore/RuntimeState/API summaries
→ position/order/event/system tables/cards.

Paper fills and strategy signals are separate objects; the UI does not treat every qualified signal as a fill because slots/cash/risk can block it.

### Backtest list/results
Browser filters by strategy/test type/coin
→ API enumerates immutable manifest/report folders
→ filter before display cap and sort by manifest created time
→ infer historical quote from run evidence, not current config
→ `compare_run()` against active strategy/source hash/cost/settings
→ UI clears prior selection immediately, discards late responses, renders metrics/provenance/block reasons.

Backtest selection never activates Paper strategy. Historical risk halt is displayed as historical-run context, not current Paper state.

### Backtest trigger
Local protected action
→ API/runtime backtest request
→ RuntimeSupervisor validates currently loaded code fingerprint against disk
→ canonical engine(s)
→ immutable report bundle
→ UI refreshes status/list.

If Python files changed after runtime start, new trusted backtest is blocked until restart.

### Trading/Paper settings
User edits draft
→ frontend validates basic representation but keeps draft
→ POST `/api/trading/settings` (legacy Paper alias targets same handler)
→ origin/action guard
→ server validates 1–10 slots, finite positive target and current constraints
→ one PaperStore settings row updated
→ future entries use settings
→ response updates saved UI state.

No cash top-up, account reset, retroactive position resizing or Live activation. Emergency stop remains server state even if not currently exposed as a primary user control.

### Bot stop
User clicks stop / final tab disappears / terminal fails
→ session-lifetime/presence backend
→ local instance control token/ID verification
→ RuntimeSupervisor stop
→ server termination.

No automatic liquidation. A stopped future real position would be unmonitored, which is explicitly visible/documented.

### Local live-preparation authentication
Password setup/unlock
→ protected live route
→ `live/credentials.py`
→ Windows Credential Manager local verifier/session
→ HttpOnly SameSite=Strict session cookie.

API key/secret save/remove
→ unlocked session + same-origin/action guard
→ exact credential-vault target
→ no secret response/browser storage.

### Binance account preflight
Unlocked user clicks connection check
→ UI live-preparation route
→ signed read-only client
→ account permissions, Spot capability, IP restriction status, open orders/locked funds/foreign balances/free USDC + market checks
→ redacted result/fingerprint/freshness shown.

A green preflight is not order release.

### Live enable
User clicks Live
→ `/api/live/enable`
→ current server blockers/release state
→ HTTP 409 while unreleased
→ UI renders block reason and does not show fake green Live state.

CLI Live is also deliberately disabled.

### 50-USDC trial start
User clicks explicitly labeled one-trial action
→ protected route/preflight/release blockers
→ currently HTTP 409; no order.

Internal trial/exchange components are present for offline tests, but productive arming and submit have independent hard-false checks. Frontend cannot override them.

### Key removal / live-disable semantics
Removing credentials or disabling entries is distinct from liquidation. Open/uncertain trial state can block credential mutation. "Live aus" / entry stop does not automatically sell positions.

## UI freshness invariants for A04

After any patch touching strategy/version/quote/settings/Paper/risk/data/backtest/report/runtime/API:
1. Verify server payload changed or intentionally did not change.
2. Verify every visible label/unit/quote/version reflects server truth, not hardcoded history.
3. Verify old async result cannot overwrite a new selection/draft.
4. Verify Paper signal versus fill distinction remains explicit.
5. Verify Backtest provenance remains MATCHING/DIFFERENT/UNVERIFIED rather than stale-current.
6. Verify unreleased Live controls remain visibly blocked and no green state is client-invented.
7. If TypeScript changed, rebuild committed static assets and test them.

## Known historical/stale documentation UI statements

Older DMS sections reference USDT, Windows-service/24×7 operation, older budget limits and prior button wording. Current owner decisions/README/current DMS preambles plus actual API/UI code take precedence. A04 must never restore older text merely because it still occurs in a historical section.