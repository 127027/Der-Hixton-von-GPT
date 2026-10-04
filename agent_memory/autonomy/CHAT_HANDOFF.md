# LIVE OVERRIDE — Core-first micro-filler mission after Run #74

This section supersedes older replacement-universe wording below.

- Protected ten-Core product remains the primary earnings engine and is not modified.
- Satellites exist only to monetize complete Core quiet periods. They are not a second primary strategy.
- Primary Satellite markets: SUIUSDC, NEARUSDC, UNIUSDC, AAVEUSDC, BCHUSDC. Extra USDC markets may be added later only as optional filler breadth.
- ANY executable Core entry has absolute priority. If a Satellite is open, it is closed at the next executable open and the Core entry receives the capital. No "materially stronger Core" threshold applies.
- Run #74 / 37202539649 completed SUCCESS but found zero robust training survivors from the old V1-style 4/8/12h replacement baseline. Reusing that same entry family on more coins is not the next path.
- Current stage target: SATELLITE_MICRO_FILLER_RESEARCH.
- New bounded family targets genuinely smaller/faster signals on the five primary Satellites with 2/6/12h maximum holds, strict idle-only entry, baseline+stress costs, training-only selection and Direct-USDC rejection-only holdout.
- Capital path: 50 USDC first real trial after full engineering validation; 250 USDC initial configured target; 1000 USDC only after a clean operating period and later scale validation.
- Success is one shared account: Core-only three-year result versus Core+Satellite on identical data/costs, with higher after-cost ending equity and materially shorter idle gaps.
- No Paper/Live auto-activation, private credentials or cloud orders.

## LIVE UPDATE — Run #70 replacement discovery

- Run #70 / `37198769433` / `736ee30f610f85044bb5476992ab81fd8606263c` completed SUCCESS.
- Ten new non-seed Binance Spot USDC markets passed point-in-time liquidity/history eligibility: ALGOUSDC, ZECUSDC, LTCUSDC, WLDUSDC, FETUSDC, SANDUSDC, RUNEUSDC, INJUSDC, HBARUSDC, ICPUSDC.
- No strategy or holdout outcome selected these markets; this is eligibility only.
- Next stage is `SATELLITE_V1_REPLACEMENT_BASELINE`: all ten are screened from unchanged V1/DMS_V1 entry semantics using training-selected short filler horizons in one shared C=250 free-slot model. Direct-USDC remains rejection-only.
- This free-capacity model may use a spare slot while Core is under-deployed; the point-in-time router may reclaim filler capital for a materially superior Core opportunity. Weak Core signals do not win solely by label.

# LIVE OVERRIDE — after Run #69 (2026-10-04)

This section supersedes older stage/status statements below when they conflict.

- Protected product remains `gpt/usdc-audit@f6497acf8d4d852aaac0b69878762fabb53155d4`.
- Research Run #69 / `37196821137` / head `9314df9baeae1c907d98472823d2e7ccd3e4eaa4` completed SUCCESS.
- The 2/4/6h V1 exact-full-Core-idle family produced no direct-USDC survivor. UNI selected 6h on TRAINING only but failed rejection-only Direct-USDC. SUI/NEAR/AAVE/BCH had no fully robust training horizon.
- The current strict-idle experiment is a conservative falsification layer, not the final capital router: it only allows Satellite entry when no Core position is open. The owner target is broader genuine free-capacity filling; spare shared-account capacity may be used when it does not displace Core, and materially superior Core opportunities must be able to reclaim filler capital.
- The original five are now seed candidates, not immutable final choices. After repeated bounded rejection, replacement Binance Spot USDC markets may be discovered using point-in-time tradability/liquidity/history eligibility. Holdout outcomes may not select replacements.
- Current stage: `SATELLITE_V1_REPLACEMENT_UNIVERSE_DISCOVERY`.
- Next action: run `scripts/satellite_universe_discovery.py`, inspect eligible USDC replacements, then build a V1/DMS_V1 training-only baseline/evolution for the active candidate set and validate it in one shared C=250 free-capacity replay.
- Do not weaken holdout/stress/future/red-team gates. Do not mutate the protected Core. No Paper/Live activation, credentials or orders.

# HIXTON CHAT HANDOFF — 2026-10-04 10:49 Europe/Berlin

## Purpose
This file is the durable cross-chat handoff for Andreas's Hixton project. A new ChatGPT chat must treat GitHub as the source of truth and re-fetch live state before acting. Do not rely on stale chat memory if repository evidence is newer.

## First actions in any new chat
1. Fetch `gpt/usdc-audit` HEAD.
2. Fetch `gpt/autonomous-research-v1` HEAD.
3. Fetch the latest `Hixton Autonomous Research Loop` runs/jobs/artifacts.
4. Read:
   - `agent_memory/autonomy/CHAT_HANDOFF.md`
   - `agent_memory/autonomy/current_mission.json`
   - `agent_memory/autonomy/roles.json`
   - `agent_memory/autonomy/policy.json`
   - `agent_memory/state.json`
   - GitHub Issue #3 newest comments.
5. If repository state is newer than this handoff, use the newer evidence and update this handoff when a material stage changes.

## Protected product — DO NOT casually mutate
Repository: `127027/Der-Hixton-von-GPT`

Protected product branch:
- `gpt/usdc-audit`
- SHA: `f6497acf8d4d852aaac0b69878762fabb53155d4`
- Message: `candidate(v6): materialize robust autonomous coin-profile winner`

This is the validated ten-Core product and remains the primary engine. Satellite research must not degrade or silently replace it.

Core markets:
- BTCUSDC
- ETHUSDC
- BNBUSDC
- SOLUSDC
- XRPUSDC
- ADAUSDC
- LINKUSDC
- AVAXUSDC
- DOTUSDC
- DOGEUSDC

Product remains research/protection oriented: no automatic Paper/Live activation, no private Binance credentials in cloud, no real/testnet cloud orders.

## Owner goal
Andreas's practical observation is that the protected ten-Core/250-USDC bot is active only about 1/10 of the time. The five Satellites are meant to monetize as much as possible of the remaining ~9/10 Core-idle opportunity pool.

The ~90% idle number is an opportunity pool, NOT a quota. Never force trades, split orders to inflate frequency, or accept negative after-cost portfolio value merely to increase utilization.

Final intended capital semantics:
- one configured total account capital `C`, current research reference `C = 250 USDC`;
- ten protected Core markets remain primary;
- up to five Satellites may use genuinely free Core-idle capacity;
- final success is measured on one shared account, not 15 independent accounts;
- isolated per-market 250-USDC tests are diagnostics only.

## Clean strategy reset — canonical
The old Satellite line that copied V6/Core templates is invalid as the design starting point.

The five fixed Satellite markets are:
- SUIUSDC
- NEARUSDC
- UNIUSDC
- AAVEUSDC
- BCHUSDC

New canonical basis:
- `V1_STRATEGY`
- `StrategySemantics.DMS_V1`

The five Satellites must be developed independently from the original V1 basis. They may end with different parameters/exit behavior. Do NOT copy the ten-Core V6 coin profiles as default Satellite strategies.

Old V6-derived Step-4 profiles remain historical evidence only. They may be used to locate long-history proxy symbols, not as strategy seeds.

## Current live research state
Research branch:
- `gpt/autonomous-research-v1`
- current SHA at handoff: `12033e72260568aa81c427f83afa75006d968ca7`
- message: `coord(heartbeat): launch per-market V1 evolution`

### Run #64 — clean V1 baseline
- Run ID: `37187899661`
- HEAD: `8b94f5825c27bf82a95e94773aaea6f7859dec69`
- conclusion: SUCCESS
- artifact: `11297757671`
- artifact digest: `sha256:6db3663c7b2f784748077f960431118fa6398244146d282ccec3e5a34cf45cf3`
- stage: `SATELLITE_V1_BASELINE`
- unchanged V1/DMS_V1 was run on all five markets.
- three-year proxy + one-year direct-USDC rejection-only evidence was produced.
- five-market potential union active coverage from unchanged V1: `78.4861618004866%`.
- IMPORTANT: this 78.49% is potential Satellite activity across the whole calendar; it is NOT yet exact realized coverage of the protected Core's idle mask.

### Run #65 — per-market V1 evolution
- Run ID: `37189822138`
- HEAD: `12033e72260568aa81c427f83afa75006d968ca7`
- conclusion: SUCCESS
- artifact: `11298795927`
- artifact digest: `sha256:3ab10a6de0f5fac53aea0dbf7b895ff3326be4570cd1a0291174d5d340689ee2`
- stage: `SATELLITE_V1_PER_MARKET_EVOLUTION`

Training champions:
- SUIUSDC -> `AXIS_atr_length_72`
- NEARUSDC -> `AXIS_atr_length_72`
- UNIUSDC -> `BALANCED_B`
- AAVEUSDC -> `AXIS_momentum_length_12`
- BCHUSDC -> `AXIS_band_multiplier_2.8`

Rejection-only direct-USDC result:
- `accepted_for_shared_core_idle_replay = [UNIUSDC]`

This means only UNI currently survived the first bounded V1-derived training + direct-USDC holdout path. SUI, NEAR, AAVE and BCH are NOT final rejects yet; they require one further bounded causal V1-derived family each. Do not copy Core V6 to rescue them.

Run #65 explicitly reports:
- next stage: `SATELLITE_V1_SHARED_CORE_IDLE_REPLAY`

## Immediate technical blocker / next engineering bridge
At this handoff time, the repository contains:
- `scripts/satellite_v1_baseline_research.py`
- `scripts/satellite_v1_evolution_research.py`

But it does NOT yet contain a dedicated V1 shared-Core-idle replay script/stage, and the workflow currently recognizes only:
- `SATELLITE_V1_BASELINE`
- `SATELLITE_V1_PER_MARKET_EVOLUTION`

Therefore the immediate next controller task is:
1. do NOT rerun Run #65 unchanged;
2. build the deterministic `SATELLITE_V1_SHARED_CORE_IDLE_REPLAY` bridge;
3. replay the currently accepted UNI V1 candidate only in the exact protected-Core idle mask, using one shared C=250 account, baseline and stress costs;
4. measure exact Core idle hours, Satellite hours monetized, Core-idle fill %, after-cost incremental PnL, shared ending equity, Core displacement, holding duration and profit/occupied-hour;
5. in parallel/next bounded rounds, evolve SUI/NEAR/AAVE/BCH one causal V1-derived family at a time because their first champions failed holdout;
6. only after candidates are robust should the final five/up-to-five set be frozen.

Do not interpret only-one-survivor as permission to weaken holdout gates.

## Required research discipline
- Per-market selection/tuning: training only.
- Direct-USDC holdout: rejection only.
- Shifted full-three-year robustness: required later.
- Sealed future-readiness: rejection only.
- Independent red-team: required.
- No future realized PnL/MFE/MAE as decision inputs.
- No raw trade-count gaming.
- Fees, spread and slippage modeled.
- Prefer short profitable capital occupancy and high profit per occupied hour.
- A market may ultimately be rejected if no robust gap-filler strategy exists.
- Core performance may not be sacrificed merely for activity.

## Promotion path
After Satellite strategy and shared-idle evidence:
1. robustness / shifted windows / future-readiness / red-team;
2. deterministic Satellite/Core state-machine and restart/duplicate/state-transition tests;
3. dynamic `max_capital_usdc=C` scale-invariance for 50/250/1000/5000/20000+;
4. Backtest/UI/Paper/Trial/Live semantic parity;
5. D14 Satellite architecture candidate;
6. exact-head A01-A11;
7. A09 must report `QA_PASS`;
8. A11 must report `GOVERNANCE_PASS`;
9. only then fast-forward protected product branch and call it DOWNLOAD READY.

## Agent roles — all aligned to this mission
A01 requirements/evidence contract
A02 deterministic V1 backtests/shared replay
A03 semantic/parity
A04 UI/API truthfulness
A05 idle-time/per-market weakness diagnosis
A06 regression/determinism/no leakage
A07 Binance public data/filter validity
A08 strategy/risk/cost challenge
A09 independent QA gate
A10 next evidence-led task dispatcher
A11 governance/promotion gate

D12 V1 Hypothesis Architect
D13 Event Intelligence (later optional; do not distract baseline/evolution)
D14 Engineering Promotion
D15 Universe frozen to selected five during this mission
D16 original V1 signal mining for the five
D17 forward/future rejection-only evidence
D18 protected Core baseline guard
D19 lead Satellite-V1 research
D20 alignment/continuity/stall prevention

## Active ChatGPT scheduled controllers at handoff
The available task slots are used for:
- Hixton V1 Hourly Controller — sole normal writer/controller
- Hixton V1 Hypothesis Dot (D12)
- Hixton V1 Baseline Guard (D18)
- Hixton V1 Satellite Dot (D19)
- Hixton V1 Forward Dot (D17)

Old Master and obsolete V6/Step5B watches remain paused to prevent conflicting writers.

ChatGPT task scheduling supports hourly as the highest recurring frequency. Do not claim a 15-minute ChatGPT automation exists. Issue #3 may contain `WATCHDOG 15M` checkpoint comments from direct watchdog checks, but durable recurring ChatGPT scheduling must be treated as hourly unless a separate repository-side GitHub mechanism is explicitly built and verified.

## Historical orchestration failure to never repeat
On the night of Oct 3/4, Run #61 finished around 00:11 Europe/Berlin and research then stalled for ~8 hours despite hourly task executions. Only one required checkpoint had persisted. The morning recovery fixed workflow routing, but this proved that an automation's last-run timestamp is not evidence of useful work.

Every controller check must therefore verify concrete GitHub progress:
- branch HEAD delta,
- workflow run/stage delta,
- job/step state,
- artifact/evidence delta,
- Issue #3 persistence.

If a completed stage has no next run/bridge, classify it as HANDOFF_STALL and build/fix the next bridge rather than waiting for Andreas to ask.

## Cross-chat communication rule
Chats do not directly message one another. Cross-chat continuity is implemented through GitHub:
- this `CHAT_HANDOFF.md`;
- `current_mission.json`, `roles.json`, `policy.json`, `state.json`;
- workflow runs/artifacts;
- GitHub Issue #3.

Any new chat must re-read these sources before modifying research. Any material stage change should update this handoff or post a new canonical Issue #3 handoff comment.

No Microsoft Teams connection is required or desired for this project.
