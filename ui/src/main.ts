import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  LineSeries,
  createChart,
  createSeriesMarkers,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import "./styles.css";
import type { TradingSettings, TradingLimits } from "./settings-draft";
import { initializeTradingSettings } from "./trading-settings";
import { initializeLivePreparation } from "./live-preparation";
import { marketSignalText } from "./market-signal";
import { initializeSessionLifetime } from "./session-lifetime";
import { portfolioBlocksText } from "./backtest-context";

const symbols = ["BTCUSDC", "ETHUSDC", "BNBUSDC", "SOLUSDC", "XRPUSDC", "ADAUSDC", "LINKUSDC", "AVAXUSDC", "DOTUSDC", "DOGEUSDC"] as const;
type SymbolName = (typeof symbols)[number];
type RangeKey = "today" | "1w" | "1m" | "1y" | "3y";

interface PaperPosition {
  symbol: string;
  quantity: string;
  average_price: string;
  cost_basis_usdc: string;
  entry_time_utc: string;
  market_value_usdc: string;
  strategy_version: string;
  slot_count: number;
}
interface PaperPayload {
  cash_usdc: string;
  equity_usdc: string;
  unrealized_pnl_usdc: string;
  drawdown_pct: string;
  strategy_session: {
    key: string;
    version: string;
    activated_at_utc: string;
    starting_equity_usdc: string;
    pnl_usdc: string;
  };
  settings: TradingSettings;
  soak: {
    started_at_utc: string;
    calendar_days: number;
    minimum_processed_closed_bars: number;
    completed_trades: number;
    minimum_days: number;
    minimum_closed_bars_per_symbol: number;
    minimum_completed_trades: number;
    maximum_days_when_trade_count_low: number;
    status: string;
    ready: boolean;
    blockers: string[];
    processed_closed_bars_by_symbol: Record<string, number>;
  };
  positions: PaperPosition[];
}
interface RuntimePayload {
  health: string;
  mode: string;
  live_state: string;
  message: string;
  last_sync_utc: string | null;
  last_stream_update_utc: string | null;
  feed_mode: string;
  stream_connected: boolean;
  next_daily_audit_utc: string | null;
  last_daily_audit_utc: string | null;
  last_error: string | null;
  sync_in_progress: boolean;
  backtest_status: string;
}
interface StatusResponse {
  application_version: string;
  strategy_version: string;
  strategy_key: string;
  runtime: RuntimePayload;
  paper: PaperPayload | null;
  trading_limits: TradingLimits;
  server_time_utc: string;
  ui_timezone: string;
}
interface Market {
  symbol: SymbolName;
  display_symbol: string;
  available: boolean;
  price: number | null;
  price_time_utc: string | null;
  trend: string;
  last_signal: { action: string; time_utc: string } | null;
  position_state: string;
  position: PaperPosition | null;
  strategy_profile: {
    parameters: { vidya_length: number; momentum_length: number; smoothing_length: number; atr_length: number; band_multiplier: number };
    trade_policy: { cmo_floor: number; slope_bars: number; stop_atr: number; trail_atr: number };
  };
  data: { candle_count: number; gap_count: number | null; valid: boolean; first_open_utc: string | null; last_open_utc: string | null };
}
interface ChartBar {
  provisional?: boolean;
  time: string;
  close_time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  vidya: number | null;
  upper: number | null;
  lower: number | null;
  trend: string;
}
interface ChartPayload {
  available: boolean;
  symbol: string;
  display_resolution: string;
  trading_timeframe: string;
  bars: ChartBar[];
  signals: Array<{ time: string; display_time: string; action: string; signal_id: string; price: number; strength: number | null; reason?: string | null }>;
  paper_events: Array<{ display_time: string; action: string; status: string; event_id: string }>;
}
interface BacktestScenario {
  batch?: Record<string, unknown>;
  portfolio?: { metrics?: Record<string, unknown>; [key: string]: unknown };
  per_symbol?: Record<string, Record<string, unknown>>;
}
interface BacktestRun {
  manifest: Record<string, unknown>;
  metrics: Record<string, BacktestScenario>;

}
interface RuntimeLogEntry {
  time_utc: string;
  level: string;
  component: string;
  event_code: string;
  correlation_id: string;
  message: string;
}

const required = <T extends HTMLElement>(selector: string): T => {
  const element = document.querySelector<T>(selector);
  if (!element) throw new Error(`UI element fehlt: ${selector}`);
  return element;
};
const text = (selector: string, value: string): void => { required(selector).textContent = value; };
const formatNumber = (value: number | string | null | undefined, digits = 2): string => {
  if (value === null || value === undefined || value === "") return "—";
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "—";
  return new Intl.NumberFormat("de-DE", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(parsed);
};
const formatPrice = (value: number | null): string => {
  if (value === null) return "—";
  const digits = value >= 1000 ? 2 : value >= 1 ? 4 : 6;
  return new Intl.NumberFormat("de-DE", { maximumFractionDigits: digits }).format(value);
};
const formatDate = (value: string | null, withSeconds = false): string => value
  ? new Intl.DateTimeFormat("de-DE", { dateStyle: "short", timeStyle: withSeconds ? "medium" : "short", timeZone: "Europe/Berlin" }).format(new Date(value))
  : "—";
const formatUtc = (value: string | null): string => value
  ? `${new Intl.DateTimeFormat("de-DE", { dateStyle: "short", timeStyle: "medium", timeZone: "UTC" }).format(new Date(value))} UTC`
  : "—";
const timestamp = (value: string): UTCTimestamp => Math.floor(new Date(value).getTime() / 1000) as UTCTimestamp;
const escapeHtml = (value: unknown): string => String(value ?? "—").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]!));

async function api<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...options, headers: { "Content-Type": "application/json", "X-Hixton-Action": "local-ui-v1", ...(options?.headers ?? {}) } });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText })) as { detail?: string };
    throw new Error(detail.detail ?? `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

let selectedSymbol: SymbolName = "BTCUSDC";
let selectedRange: RangeKey = "1m";
let lastStatus: StatusResponse | null = null;
let coreLoadGeneration = 0;
let chart: IChartApi | null = null;
let candleSeries: ISeriesApi<"Candlestick"> | null = null;
let vidyaSeries: ISeriesApi<"Line"> | null = null;
let upperSeries: ISeriesApi<"Line"> | null = null;
let lowerSeries: ISeriesApi<"Line"> | null = null;
let chartLoadGeneration = 0;
let backtestLoadGeneration = 0;
let backtestViewKey = "";
let chartMarkers: ISeriesMarkersPluginApi<Time> | null = null;

function showToast(message: string, error = false): void {
  const toast = required<HTMLDivElement>("#toast");
  toast.textContent = message;
  toast.style.borderColor = error ? "#fb7185" : "#2dd4a8";
  toast.classList.remove("hidden");
  window.setTimeout(() => toast.classList.add("hidden"), 4200);
}

function setPage(target: string, title: string): void {
  document.querySelectorAll(".page").forEach((page) => page.classList.toggle("active", page.id === target));
  document.querySelectorAll<HTMLButtonElement>(".nav-item").forEach((button) => button.classList.toggle("active", button.dataset.target === target));
  text("#page-title", title);
  if (target === "chart-panel") window.setTimeout(() => chart?.timeScale().fitContent(), 80);
}

function renderStatus(status: StatusResponse): void {
  if (!lastStatus) {
    required<HTMLSelectElement>("#backtest-strategy").value = status.strategy_key;
    void refreshBacktests();
  }
  lastStatus = status;
  const health = status.runtime.health.toLowerCase();
  const healthPill = required("#health-pill");
  healthPill.textContent = status.runtime.health;
  healthPill.className = `health-pill ${health}`;
  text("#runtime-message", status.runtime.message);
  text("#runtime-detail", status.runtime.last_error ?? `Letzte Synchronisation: ${formatDate(status.runtime.last_sync_utc, true)}`);
  const banner = required("#runtime-banner");
  banner.className = `runtime-banner ${status.runtime.health === "HEALTHY" ? "healthy" : status.runtime.health === "HALTED" ? "error" : "loading"}`;
  const dot = required("#connection-dot");
  dot.className = `status-dot ${status.runtime.health === "HEALTHY" ? "online" : status.runtime.health === "HALTED" ? "error" : ""}`;
  text("#connection-label", status.runtime.stream_connected ? "Binance Stream" : status.runtime.feed_mode);
  text("#active-strategy-label", `BINANCE SPOT · 1H · ${status.strategy_version}`);
  text("#app-version-badge", `HIXTON v${status.application_version}`);
  text("#doc-app-version", status.application_version);
  text("#doc-strategy-version", status.strategy_version);
  if (!status.paper) { tradingSettings.render(null, status.trading_limits); return; }
  text("#metric-equity", formatNumber(status.paper.equity_usdc));
  text("#metric-cash", formatNumber(status.paper.cash_usdc));
  const usedSlots = status.paper.positions.reduce((sum, position) => sum + position.slot_count, 0);
  text("#metric-slots", String(Math.max(0, status.paper.settings.slot_count - usedSlots)));
  required("#metric-slots").nextElementSibling!.textContent = `von ${status.paper.settings.slot_count}`;
  text("#metric-drawdown", `${formatNumber(status.paper.drawdown_pct)} %`);
  tradingSettings.render(status.paper.settings, status.trading_limits);
  renderPositions(status.paper.positions);
  renderSystem(status);
}

function marketCard(market: Market): string {
  const trendClass = market.trend.toLowerCase();
  const signal = market.position_state === "LONG" ? "Position läuft" : "Wartet auf neuen Kauf";
  const p = market.strategy_profile.parameters;
  const rule = market.strategy_profile.trade_policy;
  const extras = [rule.cmo_floor ? `CMO ≥ ${rule.cmo_floor}` : "", rule.slope_bars ? `VIDYA-Steigung ${rule.slope_bars}h` : "", rule.stop_atr ? `Stop ${rule.stop_atr} ATR am Schlusskurs` : "", rule.trail_atr ? `Trail ${rule.trail_atr} ATR` : ""].filter(Boolean).join(" · ");
  return `<article class="market-card" data-symbol="${market.symbol}" tabindex="0">
    <div class="market-top"><strong>${market.display_symbol}</strong><span class="trend-tag ${trendClass}">${market.trend}</span></div>
    <div class="market-price">${formatPrice(market.price)} <small>USDC</small></div>
    <div class="market-meta"><span>${formatDate(market.price_time_utc)}</span><span class="${market.data.valid ? "good" : "warning"}">${market.data.valid ? "DATEN OK" : "PRÜFUNG"}</span></div>
    <div class="market-meta"><span>VIDYA ${p.vidya_length} · MOM ${p.momentum_length} · SMA ${p.smoothing_length} · ATR ${p.atr_length} · Band ${p.band_multiplier}${extras ? `<br>${extras}` : ""}</span></div>
    <div class="market-meta"><span>${escapeHtml(marketSignalText(market.last_signal, formatDate))}${market.trend === "UP" && market.position_state !== "LONG" ? "<br>Grüner Trend ≠ neuer Kauf. Alte Signale werden nicht nachgehandelt." : ""}</span></div>
    <div class="market-foot"><span>${signal}</span><span class="${market.position_state === "LONG" ? "good" : ""}">${market.position_state}</span></div>
  </article>`;
}

function renderMarkets(markets: Market[]): void {
  const grid = required("#market-grid");
  grid.innerHTML = markets.map(marketCard).join("");
  grid.querySelectorAll<HTMLElement>(".market-card").forEach((card) => {
    const open = (): void => {
      selectedSymbol = card.dataset.symbol as SymbolName;
      required<HTMLSelectElement>("#coin-select").value = selectedSymbol;
      setPage("chart-panel", "Chart & Signale");
      void loadChart();
    };
    card.addEventListener("click", open);
    card.addEventListener("keydown", (event) => { if (event.key === "Enter") open(); });
  });
  renderQuality(markets);
}

function renderPositions(positions: PaperPosition[]): void {
  const container = required("#position-cards");
  container.innerHTML = positions.length ? positions.map((position) => `<article class="position-card"><strong>${position.symbol.replace("USDC", "/USDC")} · ${position.slot_count} Slot${position.slot_count === 1 ? "" : "s"}</strong><span>Menge ${formatNumber(position.quantity, 6)}</span><br><span>Einstieg ${formatPrice(Number(position.average_price))}</span><br><span>Marktwert ${formatNumber(position.market_value_usdc)} USDC</span><br><span>${position.strategy_version}</span></article>`).join("") : `<article class="position-card"><strong>Keine offene Position</strong><span>Paper startet in Cash. Alte Signale werden nicht nachgehandelt.</span></article>`;
}

function renderQuality(markets: Market[]): void {
  required("#quality-body").innerHTML = markets.map((market) => `<tr><td class="mono">${market.display_symbol}</td><td class="${market.data.valid ? "good" : "warning"}">${market.data.valid ? "OK" : "PRÜFUNG"}</td><td>${market.data.candle_count.toLocaleString("de-DE")}</td><td>${formatDate(market.data.first_open_utc)}</td><td>${formatDate(market.data.last_open_utc)}</td><td>${market.data.gap_count ?? "—"}</td></tr>`).join("");
}

function renderSystem(status: StatusResponse): void {
  const soak = status.paper?.soak;
  const soakLabel = soak
    ? `${soak.calendar_days}/${soak.minimum_days} Tage · ${soak.minimum_processed_closed_bars}/${soak.minimum_closed_bars_per_symbol} Bars je Coin · ${soak.completed_trades}/${soak.minimum_completed_trades} Trades · ${soak.status}`
    : "Noch nicht gestartet";
  const items: Array<[string, string]> = [
    ["Aktive Paperstrategie", `${status.strategy_version} · seit ${formatDate(status.paper?.strategy_session.activated_at_utc ?? null, true)}`],
    ["Ergebnis dieser Strategie", status.paper ? `${formatNumber(status.paper.strategy_session.pnl_usdc)} USDC seit ${formatNumber(status.paper.strategy_session.starting_equity_usdc)} USDC Start` : "—"],
    ["Datenfeed", `${status.runtime.feed_mode} · ${status.runtime.stream_connected ? "verbunden" : "Fallback"}`],
    ["Letzte Synchronisation", formatDate(status.runtime.last_sync_utc, true)],
    ["Nächster 00:05-UTC-Audit", `${formatUtc(status.runtime.next_daily_audit_utc)} / ${formatDate(status.runtime.next_daily_audit_utc, true)} Europe/Berlin`],
    ["Letzter Tagesaudit", status.runtime.last_daily_audit_utc ? `${formatUtc(status.runtime.last_daily_audit_utc)} / ${formatDate(status.runtime.last_daily_audit_utc, true)} Europe/Berlin` : "—"],
    ["Datenbank", status.runtime.sync_in_progress ? "Synchronisierung läuft" : "WAL · bereit"],
    ["Live-Ausführung", "Sicher deaktiviert"],
    ["Betriebsüberwachung", "UI & strukturierte Logs · manuell bestätigt"],
    ["Backup-/Restore-Gate", "Nicht konfiguriert · blockiert Live"],
    ["Paper-Soak", soakLabel],
  ];
  required("#system-grid").innerHTML = items.map(([label, value]) => `<article class="details-card"><strong>${label}</strong><span>${value}</span></article>`).join("");
}

function ensureChart(): void {
  if (chart) return;
  const container = required<HTMLDivElement>("#chart");
  chart = createChart(container, {
    autoSize: true,
    layout: { background: { type: ColorType.Solid, color: "#0d131c" }, textColor: "#8190a5", attributionLogo: true },
    grid: { vertLines: { color: "#182230" }, horzLines: { color: "#182230" } },
    crosshair: { mode: CrosshairMode.Normal },
    rightPriceScale: { borderColor: "#243040" },
    timeScale: { borderColor: "#243040", timeVisible: true, secondsVisible: false, rightOffset: 4 },
  });
  candleSeries = chart.addSeries(CandlestickSeries, { upColor: "#2dd4a8", downColor: "#fb7185", borderVisible: false, wickUpColor: "#2dd4a8", wickDownColor: "#fb7185" });
  vidyaSeries = chart.addSeries(LineSeries, { color: "#2dd4a8", lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
  upperSeries = chart.addSeries(LineSeries, { color: "rgba(110,168,254,.7)", lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
  lowerSeries = chart.addSeries(LineSeries, { color: "rgba(110,168,254,.7)", lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
  chart.subscribeCrosshairMove((param) => {
    if (!param.time || !candleSeries) return required("#chart-tooltip").classList.add("hidden");
    const item = param.seriesData.get(candleSeries) as CandlestickData<Time> | undefined;
    if (!item || !("open" in item)) return;
    const tooltip = required("#chart-tooltip");
    tooltip.innerHTML = `O ${formatPrice(item.open)} · H ${formatPrice(item.high)} · L ${formatPrice(item.low)} · C ${formatPrice(item.close)}`;
    tooltip.classList.remove("hidden");
  });
}

async function loadChart(background = false): Promise<void> {
  const generation = ++chartLoadGeneration;
  const requestedSymbol = selectedSymbol;
  const requestedRange = selectedRange;
  const timezone = required<HTMLSelectElement>("#timezone-select").value;
  ensureChart();
  if (!background) required("#chart-loading").classList.remove("hidden");
  text("#chart-symbol", requestedSymbol.replace("USDC", "/USDC"));
  try {
    const payload = await api<ChartPayload>(`/api/chart?symbol=${requestedSymbol}&range=${requestedRange}&timezone=${encodeURIComponent(timezone)}`);
    if (generation !== chartLoadGeneration) return;
    text("#resolution-label", `Trading ${payload.trading_timeframe} · Anzeige ${payload.display_resolution}${payload.bars.some((bar) => bar.provisional) ? " · letzte Kerze live/offen" : " · geschlossene Kerzen"}`);
    const candles = payload.bars.map((bar) => ({ time: timestamp(bar.time), open: bar.open, high: bar.high, low: bar.low, close: bar.close }));
    candleSeries!.setData(candles);
    vidyaSeries!.setData(payload.bars.filter((bar) => bar.vidya !== null).map((bar) => ({ time: timestamp(bar.time), value: bar.vidya! })));
    upperSeries!.setData(payload.bars.filter((bar) => bar.upper !== null).map((bar) => ({ time: timestamp(bar.time), value: bar.upper! })));
    lowerSeries!.setData(payload.bars.filter((bar) => bar.lower !== null).map((bar) => ({ time: timestamp(bar.time), value: bar.lower! })));
    const validTimes = new Set(candles.map((bar) => bar.time));
    const compactMarkers = requestedRange === "1y" || requestedRange === "3y";
    const markers: SeriesMarker<Time>[] = payload.signals
      .filter((signal) => validTimes.has(timestamp(signal.display_time)))
      .map((signal) => ({
        time: timestamp(signal.display_time),
        position: signal.action === "ENTER_LONG" ? "belowBar" : "aboveBar",
        color: signal.action === "ENTER_LONG" ? "#2dd4a8" : "#fb7185",
        shape: signal.action === "ENTER_LONG" ? "arrowUp" : "arrowDown",
        text: compactMarkers ? undefined : signal.action === "ENTER_LONG" ? "KAUF" : signal.reason ? "STOP" : "VERKAUF",
        size: compactMarkers ? 0.5 : 1,
      }));
    for (const event of payload.paper_events.filter((item) => item.status === "FILLED" && validTimes.has(timestamp(item.display_time)))) {
      markers.push({ time: timestamp(event.display_time), position: "inBar", color: "#d8b4fe", shape: "circle", text: "PAPER FILL" });
    }
    markers.sort((a, b) => Number(a.time) - Number(b.time));
    if (chartMarkers) chartMarkers.setMarkers(markers);
    else chartMarkers = createSeriesMarkers(candleSeries!, markers, { autoScale: true });
    text("#chart-signal-count", `${payload.signals.length.toLocaleString("de-DE")} Signale`);
    required("#chart-signals-body").innerHTML = payload.signals.length
      ? [...payload.signals].reverse().slice(0, 50).map((signal) => `<tr><td>${formatDate(signal.time, true)}</td><td class="${signal.action === "ENTER_LONG" ? "good" : "negative"}">${signal.action === "ENTER_LONG" ? "KAUF" : "VERKAUF"}</td><td>${formatPrice(signal.price)}</td><td>${signal.strength === null ? "—" : formatNumber(signal.strength, 6)}</td><td class="mono" title="${signal.signal_id}">${signal.signal_id.slice(0, 14)}…</td></tr>`).join("")
      : `<tr><td colspan="5">In diesem Zeitraum liegt kein bestätigtes Signal.</td></tr>`;
    if (!background) chart!.timeScale().fitContent();
    if (!payload.available) showToast("Für diesen Zeitraum sind noch keine lokalen Daten vorhanden.", true);
  } catch (error) {
    if (generation === chartLoadGeneration) {
      showToast(error instanceof Error ? error.message : String(error), true);
    }
  } finally {
    if (generation === chartLoadGeneration) {
      required("#chart-loading").classList.add("hidden");
    }
  }
}

async function refreshCore(): Promise<void> {
  const generation = ++coreLoadGeneration;
  try {
    const [status, markets] = await Promise.all([api<StatusResponse>("/api/status"), api<{ markets: Market[] }>("/api/markets")]);
    if (generation !== coreLoadGeneration) return;
    renderStatus(status);
    renderMarkets(markets.markets);
    if (required("#chart-panel").classList.contains("active")) void loadChart(true);
  } catch (error) {
    if (generation !== coreLoadGeneration) return;
    required("#connection-dot").className = "status-dot error";
    text("#connection-label", "UI-API getrennt");
    showToast(error instanceof Error ? error.message : String(error), true);
  }
}

async function refreshEvents(): Promise<void> {
  try {
    const response = await api<{ events: Array<Record<string, string | null>> }>("/api/paper/events?limit=250");
    required("#events-body").innerHTML = response.events.length ? response.events.map((event) => `<tr><td>${formatDate(event.occurred_at_utc ?? null, true)}</td><td class="mono">${event.symbol}</td><td>${event.action}</td><td class="${event.status === "FILLED" ? "good" : "warning"}">${event.status}</td><td>${formatPrice(event.execution_price ? Number(event.execution_price) : event.reference_price ? Number(event.reference_price) : null)}</td><td>${event.reason ?? (event.realized_pnl_usdc ? `PnL ${formatNumber(event.realized_pnl_usdc)} USDC` : "—")}</td></tr>`).join("") : `<tr><td colspan="6">Noch keine Paper-Ereignisse. Der Bot handelt keine historischen Signale nach.</td></tr>`;
  } catch { /* Startup can precede ledger initialization. */ }
}

async function refreshBacktests(): Promise<void> {
  const generation = ++backtestLoadGeneration;
  try {
    const strategy = required<HTMLSelectElement>("#backtest-strategy").value;
    const selection = required<HTMLSelectElement>("#backtest-symbol").value;
    const mode = selection === "PORTFOLIO" ? "portfolio" : selection === "ALL" ? "all" : "single";
    const viewKey = `${strategy}:${selection}`;
    const history = required<HTMLDetailsElement>("#backtest-history");
    if (backtestViewKey !== viewKey) {
      backtestViewKey = viewKey;
      required("#backtest-runs").textContent = "Passende Läufe werden geladen …";
      required("#backtest-detail-body").innerHTML = `<tr><td colspan="7">Auswahl wird geladen …</td></tr>`;
      text("#backtest-detail-title", "Ausgewählter Test · Ergebnis");

      text("#backtest-blocks", "");
      history.open = false;
      history.classList.add("hidden");
    }
    const query = new URLSearchParams({ strategy, mode });
    if (mode === "single") query.set("symbol", selection);
    const response = await api<{ runs: BacktestRun[]; status: string }>(`/api/backtests?${query}`);
    if (generation !== backtestLoadGeneration || required<HTMLSelectElement>("#backtest-strategy").value !== strategy || required<HTMLSelectElement>("#backtest-symbol").value !== selection) return;
    text("#backtest-eyebrow", `BACKTEST ${strategy.toUpperCase()}`);
    text("#backtest-title", "Aktuelle V6 · 3×80, 10×250 oder Einzelcoin");
    const button = required<HTMLButtonElement>("#backtest-button");
    button.disabled = response.status === "RUNNING";
    button.textContent = response.status === "RUNNING" ? "Backtest läuft …" : "Backtest starten";
    const cards = response.runs.map((run) => {
      const manifest = run.manifest;
      const current = run.metrics.current ?? run.metrics.baseline;
      const firstMetric = current ? Object.values(current.per_symbol ?? {})[0] : undefined;
      const summary = current?.portfolio?.metrics ?? current?.batch ?? firstMetric;
      const quote = manifest.quote_asset === "USDC" || manifest.quote_asset === "USDT" ? manifest.quote_asset : "Quote ungeklärt";
      const result = summary
        ? `${formatNumber(summary.ending_equity as string)} ${quote} · ${formatNumber(summary.return_pct as string)} %`
        : "Kennzahlen nicht verfügbar";
      const version = (manifest.strategy as Record<string, unknown> | undefined)?.version ?? strategy.toUpperCase();
      const runMode = current?.portfolio ? "Portfolio" : current?.batch ? "10×250 isoliert" : `Einzeltest ${Object.keys(current?.per_symbol ?? {}).join(", ")}`;
      const riskHalt = current?.portfolio?.risk_halted_at_utc;
      const riskLabel = riskHalt ? `<strong class="negative">RISIKOHALT im Test · ${formatDate(String(riskHalt), true)}</strong>` : "";
      const window = manifest.data as Record<string, unknown> | undefined;
      const runId = String(manifest.run_id ?? "—");
      return `<article class="run-card"><div><strong title="${escapeHtml(runId)}">${escapeHtml(runMode)} · Run ${escapeHtml(runId.slice(0, 8))}</strong><small>${escapeHtml(version)}</small><small>Testfenster: ${formatDate(window?.report_start_utc ? String(window.report_start_utc) : null)} – ${formatDate(window?.report_end_utc ? String(window.report_end_utc) : null)} (Ende exklusiv)</small><small>Erstellt: ${formatDate(manifest.created_at_utc ? String(manifest.created_at_utc) : null, true)} · ${escapeHtml(manifest.status)}</small></div><span>Ergebnis: ${result}${riskLabel}</span></article>`;
    });
    required("#backtest-runs").innerHTML = cards[0] ?? `<article class="run-card"><div><strong>Noch kein Backtest für diese Auswahl</strong><small>Version und Testart sind getrennt. Einen passenden Lauf hier starten.</small></div></article>`;
    required("#backtest-history-runs").innerHTML = "";
    text("#backtest-history-label", "Frühere Läufe sind im aktuellen Produkt ausgeblendet");
    history.classList.add("hidden");
    const latestRun = response.runs[0];

    const latestScenario = latestRun?.metrics.current ?? latestRun?.metrics.baseline;
    text("#backtest-blocks", portfolioBlocksText(latestScenario?.portfolio));
    const perSymbol = latestScenario?.per_symbol ?? {};
    const portfolioMetric = latestScenario?.portfolio?.metrics;
    text("#backtest-detail-title", portfolioMetric ? "Aktueller V6-Lauf · Portfolio" : "Aktueller V6-Lauf · isolierte Coin-Diagnose");
    const metricRow = (label: string, metric: Record<string, unknown>, halted = false) =>
      `<tr><td class="mono">${label}${halted ? " · HALTED" : ""}</td><td>${formatNumber(metric.starting_equity as string)}</td><td>${formatNumber(metric.ending_equity as string)}</td><td class="${Number(metric.return_pct) >= 0 ? "good" : "negative"}">${formatNumber(metric.return_pct as string)} %</td><td>${String(metric.completed_trades ?? "—")}</td><td>${formatNumber(metric.max_drawdown_pct as string)} %</td></tr>`;
    required("#backtest-detail-body").innerHTML = portfolioMetric
      ? metricRow("PORTFOLIO", portfolioMetric, Boolean(latestScenario?.portfolio?.risk_halted_at_utc))
      : Object.keys(perSymbol).length
      ? Object.entries(perSymbol).map(([symbol, metric]) => metricRow(symbol, metric)).join("")
      : `<tr><td colspan="7">Noch kein auswertbarer Run vorhanden.</td></tr>`;
  } catch {
    if (generation === backtestLoadGeneration) {
      required("#backtest-runs").textContent = "Backtestliste derzeit nicht erreichbar. Anzeige wird erneut geladen.";

      text("#backtest-blocks", "");
      required("#backtest-history").classList.add("hidden");
      required("#backtest-detail-body").innerHTML = `<tr><td colspan="7">Keine aktuelle Antwort für diese Auswahl.</td></tr>`;
    }
  }
}

async function refreshRuntimeLogs(): Promise<void> {
  try {
    const response = await api<{ logs: RuntimeLogEntry[] }>("/api/logs?limit=250");
    required("#runtime-logs-body").innerHTML = response.logs.length
      ? response.logs.map((entry) => `<tr><td>${formatUtc(entry.time_utc)}</td><td class="${entry.level === "ERROR" ? "negative" : entry.level === "WARNING" ? "warning" : "good"}">${entry.level}</td><td>${entry.component}</td><td class="mono">${entry.event_code}</td><td>${entry.message}</td><td class="mono" title="${entry.correlation_id}">${entry.correlation_id.slice(0, 12)}…</td></tr>`).join("")
      : `<tr><td colspan="6">Noch keine Laufzeitereignisse.</td></tr>`;
  } catch { /* A restarting server can briefly make logs unavailable. */ }
}

function initializeControls(): void {
  const coinOptions = symbols.map((symbol) => `<option value="${symbol}">${symbol.replace("USDC", "/USDC")}</option>`).join("");
  required<HTMLSelectElement>("#coin-select").innerHTML = coinOptions;
  required<HTMLSelectElement>("#backtest-symbol").insertAdjacentHTML("beforeend", coinOptions);
  document.querySelectorAll<HTMLButtonElement>(".nav-item").forEach((button) => button.addEventListener("click", () => setPage(button.dataset.target!, button.textContent ?? "Der Hixton")));
  document.querySelectorAll<HTMLButtonElement>("[data-range]").forEach((button) => button.addEventListener("click", () => {
    selectedRange = button.dataset.range as RangeKey;
    document.querySelectorAll("[data-range]").forEach((item) => item.classList.toggle("active", item === button));
    void loadChart();
  }));
  required<HTMLSelectElement>("#coin-select").addEventListener("change", (event) => { selectedSymbol = (event.target as HTMLSelectElement).value as SymbolName; void loadChart(); });
  required<HTMLSelectElement>("#backtest-strategy").addEventListener("change", () => void refreshBacktests());
  required<HTMLSelectElement>("#backtest-symbol").addEventListener("change", () => void refreshBacktests());
  required<HTMLSelectElement>("#timezone-select").addEventListener("change", () => void loadChart());
  required<HTMLInputElement>("#overlay-toggle").addEventListener("change", (event) => {
    const visible = (event.target as HTMLInputElement).checked;
    for (const series of [vidyaSeries, upperSeries, lowerSeries]) series?.applyOptions({ visible });
  });
  required<HTMLButtonElement>("#sync-button").addEventListener("click", async () => {
    const button = required<HTMLButtonElement>("#sync-button"); button.disabled = true;
    try { await api("/api/data/sync", { method: "POST", body: "{}" }); showToast("Datenprüfung abgeschlossen."); await refreshCore(); }
    catch (error) { showToast(error instanceof Error ? error.message : String(error), true); }
    finally { button.disabled = false; }
  });
  required<HTMLButtonElement>("#backtest-button").addEventListener("click", async () => {
    const symbol = required<HTMLSelectElement>("#backtest-symbol").value;
    const strategy = required<HTMLSelectElement>("#backtest-strategy").value;
    const mode = symbol === "PORTFOLIO" ? "portfolio" : symbol === "ALL" ? "all" : "single";
    try { await api("/api/backtests/run", { method: "POST", body: JSON.stringify({ mode, symbol, strategy }) }); showToast("V6-Backtest wurde gestartet."); await refreshBacktests(); }
    catch (error) { showToast(error instanceof Error ? error.message : String(error), true); }
  });
}

const tradingSettings = initializeTradingSettings(async (settings) => {
  const result = await api<{settings: TradingSettings}>("/api/trading/settings", {
    method: "POST", body: JSON.stringify({confirmation: "ANWENDEN", ...settings}),
  });
  ++coreLoadGeneration;
  return result.settings;
}, (settings) => {
  if (lastStatus?.paper) lastStatus.paper.settings = settings;
  void refreshCore();
});
initializeControls();
initializeSessionLifetime();
initializeLivePreparation(() => tradingSettings.liveBlocker());
ensureChart();
void Promise.all([refreshCore(), refreshEvents(), refreshBacktests(), refreshRuntimeLogs()]).then(() => loadChart());
window.setInterval(() => void refreshCore(), 5_000);
window.setInterval(() => void refreshEvents(), 15_000);
window.setInterval(() => void refreshBacktests(), 10_000);
window.setInterval(() => void refreshRuntimeLogs(), 10_000);
