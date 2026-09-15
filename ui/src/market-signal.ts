/** Indicator flips are not execution confirmations or a promise of another entry. */
export function marketSignalText(
  signal: { action: string; time_utc: string } | null,
  formatDate: (value: string) => string,
): string {
  if (!signal) return "Noch kein Trendwechsel in den geladenen Daten";
  const action = signal.action === "ENTER_LONG" ? "Kauf" : signal.action === "EXIT_LONG" ? "Verkauf" : "Unbekannt";
  return `Letzter Trendwechsel: ${action} · ${formatDate(signal.time_utc)}`;
}
