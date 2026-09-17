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
    const cycles = typed.completed_trades;
    const slotTrades = typed.completed_slot_trades;
    if (typeof cycles === "number" && typeof slotTrades === "number") {
      tradeAccounting = `Positionszyklen: ${cycles} · Slot-Trades (80-USDC-Kapazität): ${slotTrades}. `;
    }
  }
  return capacity + tradeAccounting + (items.length
    ? `Blockiergründe: ${items.map(([reason, count]) => `${count} × ${labels[reason] ?? reason}`).join(" · ")}.`
    : "Keine blockierten Signale in diesem Lauf.");
}
