# Repository inventory — verified 2026-09-15

## Scope and baseline

Inventory source is the recursively enumerated tracked Git tree imported from `127027/Der-Hixton@codex/backtest-audit-20260915`. Before swarm-memory additions, target tree SHA matched source exactly: `b09ba60f7a41b984f57a8b95ab2ac3722788e1f2`. Runtime/ignored files such as `.venv`, `data/`, backups, logs and raw local run directories are deliberately not part of the tracked inventory.

Status notation: **READ** = implementation/content inspected; **GROUPED** = generated/static/template content whose role is verified as a group; **HISTORICAL EVIDENCE** = immutable research/results, not active behavior.

## Root / engineering tooling

- `.gitattributes` — line-ending stability for hashed sources. GROUPED.
- `.gitignore` — excludes local runtime databases, data, runs, secrets/caches. READ role.
- `.github/workflows/codex-supervisor.yml` — validates committed agent-memory structure only on its configured agent branch; does not run the trading bot and uses no exchange secret. READ.
- `AGENTS.md` — authoritative persistent-agent bootstrap and safety contract. READ.
- `README.md` — current human entry, operational/current-result summary; newest headings override historical sections. READ.
- `Startbot.bat` — sole trading application Windows starter; environment/dependency/UI checks then `src/main.py start`. READ.
- `StartAgent.bat` — engineering-agent launcher; not trading starter. READ role.
- `AgentChat.bat` — interactive engineering-agent launcher. READ role.
- `pyproject.toml` — package metadata, pinned runtime dependencies, pytest/ruff/mypy configuration. READ.
- `scripts/local_agent.ps1` — current single Codex learning loop, disposable worktree, old hard-coded `agent/codex-supervisor-v1`, persists only `agent_memory` during bootstrap. READ.
- `scripts/agent_chat.ps1` — current interactive single-agent chat, same old branch hard-code and bootstrap boundary. READ.
- `scripts/qa_gate.sh` — compile, Ruff, mypy, pytest, UI tests, TypeScript and production-build gate. READ.

## DMS — normative/current plus historical context

Individually accounted and reviewed for current-vs-historical precedence:
- `DMS/00_DOKUMENTENLENKUNG_UND_START.md` — document precedence/current version history. READ.
- `DMS/01_PRODUKTVISION_SCOPE.md` — product scope; contains older USDT/service statements superseded by newer decisions. READ.
- `DMS/02_VERBINDLICHE_ANFORDERUNGEN.md` — stable requirement IDs, current USDC preamble plus historical text. READ.
- `DMS/03_STRATEGIE_HIXTON.md` — strategy/Pine semantics and V6 coin profiles; historical quote wording retained. READ.
- `DMS/04_MARKT_KAPITAL_RISIKO.md` — capital, slots, risk and portfolio semantics; latest preamble identifies current USDC state. READ.
- `DMS/05_MARKTDATEN_UND_AKTUALISIERUNG.md` — history, startup sync, stream/fallback, freshness/audit rules. READ.
- `DMS/06_BACKTEST_UND_VALIDIERUNG.md` — current single-rulebase doctrine and isolated-vs-portfolio model distinction. READ.
- `DMS/07_AUSFUEHRUNG_ORDERS.md` — intent/order/fill/reconciliation target and implemented Paper behavior; live limitations. READ.
- `DMS/08_UI_UX_SPEZIFIKATION.md` — current UI behavior plus historical states. READ.
- `DMS/09_SYSTEMARCHITEKTUR_DATENMODELL.md` — component/data model principles. READ.
- `DMS/10_BETRIEB_MONITORING_RECOVERY.md` — health/recovery/soak/backup target model; some service-era text superseded by DEC-054 visible operation. READ.
- `DMS/11_SICHERHEIT_COMPLIANCE.md` — credential/session/network and live-gate requirements. READ.
- `DMS/12_TESTS_ABNAHMEKRITERIEN.md` — chronological test evidence and strict distinction between offline tests and external execution proof. READ.
- `DMS/13_KONFIGURATION_UND_SCHEMATA.md` — current JSON contract and historical schema examples. READ.
- `DMS/14_BUILD_PLAN_UND_DEFINITION_OF_DONE.md` — implementation phases/release boundaries. READ.
- `DMS/15_TRACEABILITY_MATRIX.md` — requirement-to-component/test map; historical portions may lag latest code. READ.
- `DMS/16_ENTSCHEIDUNGSLOG_UND_OFFENE_PUNKTE.md` — owner decisions DEC-055 etc.; highest DMS authority after owner instruction. READ.
- `DMS/17_GLOSSAR.md` — terms; some USDT amounts historical. READ.
- `DMS/18_BACKTEST_STATUS_UND_ERGEBNISFORMAT.md` — current operational/backtest evidence incl. quote migration, V9, slot audit and Paper parity. READ relevant current sections and prior audit evidence.
- `DMS/19_RISIKOREGISTER.md` — engineering/trading/runtime risks and controls. READ.
- `DMS/20_BETRIEBSRUNBOOK.md` — current runtime/live-preparation state and concrete remaining work. READ current sections.
- `DMS/21_GITHUB_ZUSAMMENARBEIT.md` — Git collaboration/branch/history rules; old source repo/branch references are historical. READ.
- `DMS/22_QUELLEN_UND_BINANCE_PRUEFUNG.md` — external-source method and historical USDT universe check. READ.
- `DMS/23_ORDNERSTRUKTUR_UND_EINSTIEGSPUNKT.md` — single bot starter/technical entry and repository hygiene. READ.
- `DMS/CHANGELOG.md` — chronological DMS/application history; role verified, historical by definition. GROUPED/READ role.
- `DMS/VORLAGE_BACKTEST_RUN_MANIFEST.md` — report template, not runtime input. GROUPED.
- `DMS/VORLAGE_INCIDENT_REPORT.md` — incident template, not runtime input. GROUPED.

## Strategy source material

- `strategy/pine/Der_Hixton_Indikator_v6.pine` — owner-provided Pine reference used by Pine-v6 semantics/golden tests; immutable reference role verified.
- `strategy/pine/.gitkeep` — structural placeholder, inert. GROUPED.
- `strategy/source_material/Der Hixton Indikator.md` — original analysis/source material, non-executable. GROUPED/READ role.

## Configuration

- `config/examples/config.example.json` — strict active V6-USDC runtime config, 10 markets, 250/3×80 defaults, localhost UI, USDC DB. READ through config loader/current audit.

## Python application

### Entry/config/constants
- `src/main.py` — sole technical application entry, delegates to CLI. READ.
- `src/hixton/__init__.py` — package/version metadata, inert application boundary. GROUPED.
- `src/hixton/cli.py` — status/start/data/backtest/paper/maintenance/live/ui command routing. READ.
- `src/hixton/config.py` — strict JSON config loader and active strategy/config invariants. READ.
- `src/hixton/constants.py` — active USDC universe/timeframe/constants. READ.

### Domain
- `src/hixton/domain/__init__.py` — package exports. GROUPED.
- `src/hixton/domain/models.py` — Candle/indicator/signal/parameter/semantics records. READ.
- `src/hixton/domain/strategy.py` — deterministic Hixton indicator/signal state machine and centralized entry priority. READ.
- `src/hixton/domain/trade_policy.py` — coin policy filters/close-stop/trailing decision gate. READ.
- `src/hixton/domain/versions.py` — versioned StrategyDefinition/CoinProfile maps incl. active V6 and research definitions. READ.
- `src/hixton/domain/risk.py` — 5% UTC-day entry pause + persistent 20% high-water drawdown halt. READ.
- `src/hixton/domain/allocation.py` — slot-allocation policies. READ.
- `src/hixton/domain/markets.py` — quote/symbol parsing and fixed active-market validation. READ.

### Data
- `src/hixton/data/__init__.py` — exports. GROUPED.
- `src/hixton/data/binance.py` — public REST/WebSocket-adjacent market-data adapter, exchange metadata/filter parsing. READ.
- `src/hixton/data/quality.py` — non-mutating candle audits; gaps/duplicates/OHLC/provisional/freshness. READ.
- `src/hixton/data/storage.py` — SQLite CandleStore, WAL/revisions/symbol rules/read-only mode. READ.
- `src/hixton/data/sync.py` — incremental history synchronization and strict re-audit. READ.

### Backtest
- `src/hixton/backtest/__init__.py` — exports. GROUPED.
- `src/hixton/backtest/models.py` — immutable cost/execution/fill/trade/result records. READ.
- `src/hixton/backtest/metrics.py` — pure metrics/drawdown/monthly/ratios. READ.
- `src/hixton/backtest/engine.py` — canonical single/isolated batch next-bar-open simulation. READ.
- `src/hixton/backtest/portfolio.py` — shared-cash/slot/risk chronological portfolio simulation. READ.
- `src/hixton/backtest/reporting.py` — immutable run bundles/manifests/hashes. READ.
- `src/hixton/backtest/comparison.py` — stored-run provenance vs active strategy/code/cost/settings classification. READ.
- `src/hixton/backtest/research.py` — bounded historical research, no runtime activation. READ.
- `src/hixton/backtest/usdc_review.py` — real-USDC migration review/common continuous history/no synthetic fill. READ.
- `src/hixton/backtest/coin_review.py` — V5 loss attribution/frozen policy catalogue/validation. READ major behavior.
- `src/hixton/backtest/weak_coin_review.py` — V8 bounded weak-coin study; role/results verified from reports/docs/tests. READ role/historical evidence.
- `src/hixton/backtest/portfolio_review.py` — V9 portfolio-first/risk sensitivity research; role/results verified from reports/docs/tests. READ role/historical evidence.

### Paper
- `src/hixton/paper/__init__.py` — exports. GROUPED.
- `src/hixton/paper/models.py` — paper account/settings/position/event/session/soak records. READ.
- `src/hixton/paper/storage.py` — PaperStore schema/migrations/atomic persistence/legacy-USDT fail-closed behavior. READ.
- `src/hixton/paper/engine.py` — current simulated execution, next-open fills, slots/risk, exactly-once checkpoints/restart. READ.
- `src/hixton/paper/maintenance.py` — explicit offline archive+fresh-start operation. READ.

### Runtime
- `src/hixton/runtime/__init__.py` — exports. GROUPED.
- `src/hixton/runtime/state.py` — thread-safe runtime/health/event/backtest state. READ.
- `src/hixton/runtime/analysis.py` — common available report start/strategy analysis helpers. READ.
- `src/hixton/runtime/supervisor.py` — startup sync, health, stream/REST recovery, Paper loop, daily audit, backtest actions, source fingerprint. READ.

### Live preparation / intentionally unreleased execution
- `src/hixton/live/__init__.py` — package marker. GROUPED.
- `src/hixton/live/credentials.py` — Windows Credential Manager, local password/session. READ.
- `src/hixton/live/binance.py` — signed read-only account/preflight client and permission/market checks. READ.
- `src/hixton/live/exchange.py` — signed order transport/parser, only reachable behind higher-level release gates. READ.
- `src/hixton/live/orders.py` — persistent exactly-once trial order journal/executor/reconciliation primitives. READ.
- `src/hixton/live/reconciliation.py` — baseline/balance/fill ownership reconciliation. READ.
- `src/hixton/live/runtime.py` — trial lifecycle runtime bridge. READ.
- `src/hixton/live/trial.py` — single-entry 50-USDC trial state machine; still release-blocked. READ.
- `src/hixton/live/preparation.py` — live-preparation service; two independent false release gates keep order submit disabled. READ.

### UI/backend
- `src/hixton/ui/__init__.py` — package marker. GROUPED.
- `src/hixton/ui/api.py` — FastAPI routes/status/markets/charts/backtests/settings/session/live-preparation wiring and localhost mutation guard. READ.
- `src/hixton/ui/chart.py` — chart range/aggregation/native-signal preparation. READ.
- `src/hixton/ui/instance.py` — local singleton/control metadata/previous-instance replacement. READ.
- `src/hixton/ui/lifecycle.py` — visible browser/terminal lease and stop policy. READ.
- `src/hixton/ui/live.py` — credential/live-preparation route registration, fail-closed trial/live endpoints. READ.
- `src/hixton/ui/server.py` — localhost Uvicorn/dashboard launcher and lifecycle. READ.

### Built UI
- `src/hixton/ui/static/index.html` — committed production HTML bundle target. GROUPED; role/serving behavior verified.
- `src/hixton/ui/static/assets/index-B5XEI3_N.css` — generated production CSS. GROUPED.
- `src/hixton/ui/static/assets/index-Ch6KdkH5.js` — generated production JS. GROUPED.

## TypeScript UI source

- `ui/package.json`, `ui/package-lock.json`, `ui/tsconfig.json`, `ui/vite.config.ts` — build/test/tooling lock/config. READ role.
- `ui/index.html` — source HTML shell. GROUPED/read role.
- `ui/src/main.ts` — primary dashboard controller/polling/render/settings/backtests/charts. READ.
- `ui/src/trading-settings.ts` — settings bounds/payload/UI model. READ.
- `ui/src/settings-draft.ts` — preserves unsaved draft against polling/concurrency. READ.
- `ui/src/live-preparation.ts` — credential/live-preparation UI state/actions; server truth/fail-closed. READ.
- `ui/src/backtest-context.ts` — MATCHING/DIFFERENT/UNVERIFIED and portfolio block-reason display. READ.
- `ui/src/market-signal.ts` — last-signal/trend presentation helper; role verified through UI tests/docs. READ role.
- `ui/src/session-lifetime.ts` — presence/stop/reconnect browser session controller; role verified through UI tests/runtime. READ role.
- `ui/src/styles.css` — visual layer; no trading semantics. GROUPED.

## Tests

Every tracked Python test file is mapped in `agent_memory/tests.md`:
- `tests/__init__.py`, `tests/golden_reference.py`
- `tests/test_allocation.py`
- `tests/test_backtest_comparison.py`
- `tests/test_backtest_engine.py`
- `tests/test_backtest_reporting.py`
- `tests/test_binance_adapter.py`
- `tests/test_cli_portfolio.py`
- `tests/test_coin_engine_parity.py`
- `tests/test_coin_profiles.py`
- `tests/test_config.py`
- `tests/test_data_quality.py`
- `tests/test_domain_models.py`
- `tests/test_live_exchange.py`
- `tests/test_live_orders.py`
- `tests/test_live_preparation.py`
- `tests/test_live_reconciliation_runtime.py`
- `tests/test_live_trial.py`
- `tests/test_paper_engine.py`
- `tests/test_paper_maintenance.py`
- `tests/test_portfolio_review.py`
- `tests/test_risk.py`
- `tests/test_runtime_parity.py`
- `tests/test_storage.py`
- `tests/test_strategy_golden.py`
- `tests/test_trade_policy.py`
- `tests/test_ui_api.py`
- `tests/test_ui_chart.py`
- `tests/test_usdc_review.py`
- `tests/test_usdc_runtime_migration.py`
- `tests/test_visible_session.py`
- `tests/test_weak_coin_review.py`

UI test files:
- `ui/tests/dom-harness.mjs` — isolated DOM/fetch harness.
- `ui/tests/backtest-context.test.mjs`
- `ui/tests/market-signal.test.mjs`
- `ui/tests/session-lifetime.test.mjs`
- `ui/tests/settings-draft.test.mjs`
- `ui/tests/settings-flows.test.mjs`

## Backtest evidence directories

Historical/research artifacts are not application entry points:
- `backtests/v1/manifest-template.yaml`, report and `.gitkeep` structure — historical V1 evidence/template.
- `backtests/v2/README.md`, `candidate.json`, ignored-run placeholder — historical V2 research/reference.
- `backtests/v3/README.md`, `candidate.json`, ignored-run placeholder — rejected multi-slot challenger.
- `backtests/v4/README.md`, `reports/review-20260905.json` — coin-parameter research.
- `backtests/v5/README.md`, `reports/coin-review-20260905.json` — loss attribution/policy research.
- `backtests/v6/README.md`, `candidate.json`, `reports/profile-review-20260906.json` — historical V6 profile selection/reference.
- `backtests/v7/README.md`, `validation-20260908.json` — USDC validation/migration evidence.
- `backtests/v8/README.md`, `reports/weak-coin-review-20260914.json`, `quote-migration-audit-20260915.json`, `slot-capacity-audit-20260915.json`, `portfolio-reference-replay-20260914.json`, `paper-portfolio-parity-20260915.json` — bounded weak-coin, quote-migration, slot and parity evidence.
- `backtests/v9/README.md`, `reports/portfolio-first-20260915.json`, `risk-sensitivity-20260915.json` — rejected portfolio-first/risk research.

## Agent-memory additions on GPT working branch

- `agent_memory/state.json` — bootstrap progress/control.
- `agent_memory/diagnosis_2026-09-14.md` — prior agent diagnosis.
- `agent_memory/usdt_usdc_migration_diagnosis_2026-09-15.md` — verified quote/start-path diagnosis.
- `agent_memory/swarm/README.md`, `registry.json`, `protocol.md`, `taskboard.json` — 11-agent governance model.
- `agent_memory/swarm/agents/A01...A11*.md` — role contracts.
- this inventory and the remaining required knowledge maps.

## Inventory conclusion

No tracked trading application file is unassigned to a component above. Runtime-only/ignored files are intentionally external to Git and must be inspected only on the operator machine when a task explicitly requires runtime evidence; their absence from this repository is not a code-understanding gap.