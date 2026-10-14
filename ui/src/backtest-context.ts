export interface RunComparison {
  status: "MATCHING" | "DIFFERENT" | "UNVERIFIED";
  reasons: string[];
  scope: string;
  window_note: string;
}

export function comparisonText(comparison?: RunComparison): string {
  if (!comparison) return "Abgleich mit aktivem Bot ungeprüft. Nach Aktualisierung neu laden.";
  const title = comparison.status === "MATCHING"
    ? "Handelsregeln und Rechenstand stimmen mit aktivem Bot überein. Testmodell siehe unten."
    : comparison.status === "DIFFERENT"
      ? "Historischer Vergleich: entspricht nicht dem aktiven Botstand."
      : "Übereinstimmung mit aktivem Bot nicht vollständig belegt.";
  return [title, ...comparison.reasons, comparison.scope, comparison.window_note].join(" ");
}

export function portfolioBlocksText(portfolio?: Record<string, unknown>): string {
  if (!portfolio) return "";
  const reasons = portfolio.blocked_reasons;
  if (!reasons || typeof reasons !== "object" || Array.isArray(reasons)) {
    return "Blockiergründe dieses historischen Laufs nicht verfügbar.";
  }
  const labels: Record<string, string> = {
    MAX_DRAWDOWN_20_PERCENT: "dauerhafter Konto-Risikohalt",
    DAILY_LOSS_5_PERCENT: "Tagesverlustpause",
    NO_FREE_SLOT: "alle Slots belegt",
    POLICY_CMO: "Momentum-Filter",
    POLICY_VIDYA_SLOPE: "Steigungsfilter",
    BELOW_EXCHANGE_MINIMUM: "unter Börsenminimum",
    INSUFFICIENT_CASH: "Guthaben reicht nicht",
  };
  const items = Object.entries(reasons).filter(([, count]) =>
    typeof count === "number" && Number.isInteger(count) && count > 0);
  items.sort((a, b) => Number(b[1]) - Number(a[1]));
  const maximum = portfolio.max_concurrent_positions;
  const capacity = typeof maximum === "number" ? `Maximal gleichzeitig belegt: ${maximum} Slots. ` : "";
  const metrics = portfolio.metrics;
  let tradeAccounting = "";
  if (metrics && typeof metrics === "object" && !Array.isArray(metrics)) {
    const typed = metrics as Record<string, unknown>;
    const cycles = typeof portfolio.completed_position_cycles === "number" ? portfolio.completed_position_cycles : typed.completed_trades;
    const slotTrades = typed.completed_slot_trades;
    if (typeof cycles === "number" && typeof slotTrades === "number") {
      const notional = Number(portfolio.target_notional);
      const tranche = Number.isFinite(notional) && notional > 0
        ? ` (${notional.toLocaleString("de-DE", {maximumFractionDigits: 2})}-USDC-Tranchen)` : "";
      tradeAccounting = typeof portfolio.partial_exit_count === "number"
        ? `Positionszyklen: ${cycles} · Teilverkäufe zur Diversifikation: ${portfolio.partial_exit_count}. `
        : `Positionszyklen: ${cycles} · Slot-Trades${tranche}: ${slotTrades}. `;
    }
  }
  return capacity + tradeAccounting + (items.length
    ? `Blockiergründe: ${items.map(([reason, count]) => `${count} × ${labels[reason] ?? reason}`).join(" · ")}.`
    : "Keine blockierten Signale in diesem Lauf.");
}


/** A running/failed calculation never turns a saved result into fresh evidence. */
export function savedRunNotice(hasRun: boolean, calculationStatus: string, comparison?: RunComparison): string {
  if (!hasRun) return calculationStatus === "RUNNING"
    ? "Neuer Backtest läuft. Noch kein abgeschlossenes Ergebnis verfügbar."
    : "Noch kein abgeschlossener Lauf für diese Auswahl. Backtest starten.";
  const state = calculationStatus === "RUNNING"
    ? "Neuer Backtest läuft; unten steht der letzte gespeicherte Lauf. "
    : calculationStatus === "FAILED"
      ? "Der neue Backtest ist fehlgeschlagen; unten steht der letzte gespeicherte Lauf. " : "";
  const match = comparison?.status === "MATCHING"
    ? "Dieser gespeicherte Lauf passt zu den aktuellen Handelsregeln und Einstellungen. Sein Zeitraum und Erstellungsdatum stehen oben."
    : comparison?.status === "DIFFERENT"
      ? "Historischer Lauf: anderer Botstand oder andere Einstellungen. Für den aktuellen Stand einen neuen Backtest starten."
      : "Gespeicherter Lauf: Übereinstimmung mit dem aktuellen Botstand nicht vollständig belegt.";
  return state + match;
}
