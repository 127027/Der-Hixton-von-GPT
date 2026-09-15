# Repository inventory — verified 2026-09-15

## Scope and baseline

The tracked application baseline was imported from `127027/Der-Hixton@codex/backtest-audit-20260915` into this GPT repository. Before swarm additions, the destination tree matched the source tree SHA `b09ba60f7a41b984f57a8b95ab2ac3722788e1f2`. Runtime/ignored files such as `.venv`, `data/`, backups, logs and raw local run directories are deliberately not tracked.

## Current top-level engineering tooling

- `.gitattributes` — line-ending stability for hashed sources.
- `.gitignore` — excludes runtime databases, data, runs, secrets and caches.
- `AGENTS.md` — persistent-agent safety/engineering contract.
- `README.md` — human project entry and current operational summary.
- `Startbot.bat` — sole tracked batch launcher for the actual trading application; delegates to `src/main.py start`.
- `pyproject.toml` — Python package/runtime/dev dependencies and pytest/ruff/mypy configuration.
- `scripts/__init__.py` — cloud engineering-helper package marker.
- `scripts/swarm_core.py` — pure cloud-swarm registry/mission/regression/protected-path contract; no trading/network side effects.
- `scripts/qa_gate.sh` — compile, Ruff, mypy, pytest, UI tests, TypeScript check and Vite build.
- `.github/workflows/hixton-cloud-swarm-reusable.yml` — A01–A11 cloud execution graph on the engineering branch.
- `.github/workflows/hixton-cloud-preflight.yml` — secret-free GitHub-hosted swarm validation.

Legacy laptop-bound engineering launchers/runners are absent. The secret-free preflight enforces that `Startbot.bat` is the only tracked `.bat` file and that no local PowerShell engineering runner exists under `scripts/`.

The default-branch dispatcher lives on `main` as `.github/workflows/hixton-cloud-swarm.yml`. It handles manual/scheduled cloud dispatch and stays safely idle if the cloud-agent credential is not configured.

## DMS and decision sources

The complete `DMS/` tree remains tracked and historically versioned. Current interpretation uses DMS 00 source precedence and the latest owner decisions rather than rewriting old evidence. Key responsibilities:
- 00 document precedence/current state;
- 01 product scope;
- 02 stable requirements;
- 03 strategy/Pine/V6 profiles;
- 04 capital/slots/risk;
- 05 market data/update rules;
- 06 backtest/validation model;
- 07 intent/order/fill/reconciliation target;
- 08 UI/UX contract;
- 09 architecture/data model;
- 10 operations/monitoring/recovery;
- 11 security/compliance;
- 12 test/evidence boundaries;
- 13 configuration/schema;
- 14 build plan/Definition of Done;
- 15 traceability;
- 16 owner decisions/open points;
- 17 glossary;
- 18 current backtest/runtime evidence;
- 19 risk register;
- 20 operating runbook/live blockers;
- 21 Git collaboration;
- 22 sources/Binance checks;
- 23 folder/entrypoint rules;
- changelog/templates remain supporting historical/operational artifacts.

## Strategy/configuration

- `strategy/pine/Der_Hixton_Indikator_v6.pine` — owner-provided Pine reference.
- `strategy/source_material/Der Hixton Indikator.md` — original analysis/source material.
- `config/examples/config.example.json` — strict active V6-USDC runtime config: ten USDC markets, 250 shared Paper cash, default 3×80, localhost UI, USDC DB.

## Python application

### Entry/config/domain
- `src/main.py` — sole technical application entry.
- `src/hixton/cli.py` — status/start/data/backtest/paper/maintenance/live/ui routing.
- `src/hixton/config.py`, `constants.py` — strict config/current market constants.
- `domain/models.py`, `strategy.py`, `trade_policy.py`, `versions.py`, `risk.py`, `allocation.py`, `markets.py` — deterministic strategy/profile/policy/risk/allocation/domain truth.

### Data
- `data/binance.py` — public market data/exchange metadata.
- `data/quality.py` — strict candle validation.
- `data/storage.py` — CandleStore SQLite/revisions/read-only support.
- `data/sync.py` — incremental history synchronization and re-audit.

### Backtest/research
- `backtest/models.py`, `metrics.py`, `engine.py`, `portfolio.py`, `reporting.py`, `comparison.py` — canonical simulation/reporting/provenance.
- `research.py`, `usdc_review.py`, `coin_review.py`, `weak_coin_review.py`, `portfolio_review.py` — versioned research/diagnosis only; no automatic Paper activation.

### Paper/runtime
- `paper/models.py`, `storage.py`, `engine.py`, `maintenance.py` — persistent Paper account/settings/positions/events/checkpoints/dust/session/soak and explicit fresh-start maintenance.
- `runtime/state.py`, `analysis.py`, `supervisor.py` — observable state, analysis/common windows, startup/sync/stream/fallback/Paper/audit/backtest orchestration.

### Live preparation — intentionally unreleased
- `live/credentials.py`, `binance.py`, `exchange.py`, `orders.py`, `reconciliation.py`, `runtime.py`, `trial.py`, `preparation.py` — credential/preflight/order primitives/trial/reconciliation, with productive release still fail-closed.
- `ui/live.py` — live-preparation route surface; also protected from autonomous swarm patches.

### UI/backend
- `ui/api.py`, `chart.py`, `instance.py`, `lifecycle.py`, `server.py` — localhost API/chart/single-instance/visible-session/server lifecycle.
- `src/hixton/ui/static/` — generated production UI bundle.
- `ui/src/` — TypeScript source for dashboard/settings/live-preparation/backtest provenance/session lifetime/styles.
- `ui/tests/` — front-end DOM/fetch harness and behavior tests.

## Tests

Python tests cover allocation, strategy golden/reference parity, trade policy, coin profiles, risk, market adapter/data quality/storage, USDC migration/review, backtest engine/reporting/comparison/CLI, Paper engine/maintenance/runtime parity, runtime visible-session, UI API/chart, live preparation/order/reconciliation/trial, research reviews, configuration, and the cloud swarm contract.

`tests/test_swarm_core.py` specifically verifies:
- exact A01–A11 registry;
- SWARM-002 active mission;
- mandatory USDT/USDC regression requirements;
- `real_money_orders_allowed=False` and `automatic_merge_allowed=False`;
- protection of workflow/governance/Live-submit paths from autonomous patches.

The secret-free GitHub preflight executed these swarm tests successfully (11/11) in an Ubuntu 24.04 / Python 3.12 virtual environment.

## Backtest evidence

Versioned evidence remains under `backtests/v1` through `v9`. Historical/research artifacts are not application entrypoints. V7/V8/V9 contain the quote-migration, slot-capacity, Paper parity and later research evidence used by SWARM-002. Large reproducible raw runs remain ignored where designed.

## Persistent agent knowledge

- `agent_memory/state.json` — current engineering/cloud state.
- `agent_memory/diagnosis_2026-09-14.md` — prior diagnosis.
- `agent_memory/usdt_usdc_migration_diagnosis_2026-09-15.md` — verified quote/start-path diagnosis.
- `agent_memory/swarm/README.md`, `registry.json`, `protocol.md`, `taskboard.json` — 11-agent cloud governance and active mission.
- `agent_memory/swarm/agents/A01...A11*.md` — specialist contracts.
- `inventory.md`, `architecture.md`, `dataflows.md`, `ui_map.md`, `storage.md`, `tests.md`, `security.md`, `unknowns.md`, `cross_check.md` — durable verified engineering knowledge.

## Inventory conclusion

No tracked trading application file is unassigned. Public market data may be generated ephemerally by GitHub Actions. Private operator credentials/account state are never autonomous swarm inputs. `Startbot.bat -> src/main.py` remains the only trading application start path; the engineering swarm is GitHub CI tooling, not a second bot runtime.
