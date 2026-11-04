# Dot3 H-ECO-15 provenance and time-causality gate (2026-11-04)

Status: PRE-REGISTERED QA SPECIFICATION; NOT a completed original-data audit or candidate backtest.
Frozen product: f56d48536525830dd6ea50bf5bc174a6f9aeff8c.
Source release: research-data-20261103-five-dot-inputs.
Loss archive SHA256: d1d1cde8347665d74da71f9e44bb3876dc6662bfe4bfc9e34dcab1dfecd84308.
Synthetic original archive SHA256: 5262f12bef7182ae10e2c85fe5b790263404764e98e759196dbdfb7d0970d278.

## Exact reproducible runner handoff
Use the existing research GitHub Actions runner environment (ubuntu-24.04, Python 3.11, permissions contents:read, timeout-minutes:20), in a separate read-only job, never a product workflow. Download using:
```bash
set -euo pipefail
gh release download research-data-20261103-five-dot-inputs -R 127027/Der-Hixton-von-GPT -p Hixton-Loss-Handoff-20261102.zip -D data
echo 'd1d1cde8347665d74da71f9e44bb3876dc6662bfe4bfc9e34dcab1dfecd84308  data/Hixton-Loss-Handoff-20261102.zip' | sha256sum -c
python -m zipfile -l data/Hixton-Loss-Handoff-20261102.zip
```
This initial command verifies the input archive, NOT the presence of OHLC candles or their sufficiency. Inspect archive paths and manifest first. If no verifiable hourly OHLC is present, return BLOCKED_MISSING_OHLC with precise missing symbols, periods, paths and SHA256, without generating substitute candles.

## Event and feature gate
Extract ALL original_32k current/stress entry events without filtering on subsequent PnL. Preserve source event IDs and fill/position linkage; distinguish 1,040 dependent rows from 245 historical entry events. Count separately by cost mode, do not assert identical event sets. No arbitrary row split. For each coin, prove listing time and historical pair availability.

Use only original, verifiably timestamped, **fully closed** 1-hour OHLC candles. At entry decision time t, the latest allowed feature candle is t-1; enforce candle_close_utc <= decision_utc, and strictly earlier than the entry order creation timestamp. Reject ambiguity about candle timestamps and indicator warmup. Independently recompute EMA24, EMA72 from closes and ATR24 from true ranges; record EMA initialization, ATR smoothing convention (Wilder vs SMA/EMA), missing bars and warmup. These conventions require Dot4 signoff before interpreting Q. For each eligible event compute Q=abs(EMA24(t-1)-EMA72(t-1))/ATR24(t-1). ATR<=0, missing candles, unknown listing, or unverifiable source => NOT_EVALUABLE, never assumed PASS.

Prespecified decision Q>=0.50, neighbors 0.40 and 0.60 only for post-QA sensitivity. Save per event: case, cost, event_id, coin, decision_utc, last_closed_candle_utc, candle_path, candle_sha256, entry_allowed_050, q, EMA24, EMA72, ATR24, warmup_count, original_entry_size, original_later_realized_pnl (diagnostic only), and evaluation_status. Original later PnL is never an input feature. Report all 15 coins, with ADA/SOL/XRP/ETH/AVAX and NEAR explicit; quantify both avoided losers and foregone winners, never optimize threshold after viewing them.

## Acceptance and escalation
1. Every source file hash matches a frozen independently obtained manifest; a synthetic 64-zero hash MUST fail.
2. Recompute indicators from OHLC; reported Q values match within a predeclared numeric tolerance (propose 1e-10 in absolute Q, Dot4 to approve).
3. Event-set identity and duplicates are reconciled with the native Signals/Trades/Fills ledger, including missing events and both cost modes.
4. Verify a prefix-invariance test: appending future candles cannot alter past Q or classification.
5. Produce sha256sum for input archive, source candle files, code, CSV/JSON outputs, CLI, runner commit and Python/dependency versions. Return QA_PASS, QA_FAIL or BLOCKED with reason per context.
6. Before ANY financial candidate run, independent Dot4 signoff must cover indicator conventions, all original checks/execution_diagnostics, capacity/cost/cash and all pre-existing gates. No product change, merge, live/paper trading, or candidate score tuning.

Existing confirmed C0 and historical coin-attribution runs are NOT rerun merely to generate this audit. Historical HWM current drawdown 10,455.8636408961 USDC and realized closed-trade component -6,307.86072205409 USDC do not establish full coin-level equity attribution.
