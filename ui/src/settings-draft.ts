/** Polling may update the saved state, never an unsaved or in-flight edit. */
export interface TradingSettings {
  max_capital_usdc: string;
  slot_count: number;
  target_notional_usdc: string;
  reserve_usdc: string;
  allocation_policy: string;
  allocator_version: string;
  emergency_stop: boolean;
}

export interface TradingLimits {
  min_capital_usdc: string;
  max_capital_usdc: string;
  research_reference_max_usdc?: string;
  allocator_version: string;
}

function formatBudget(value: string | number): string {
  const parsed = Number(value);
  return Number.isFinite(parsed)
    ? new Intl.NumberFormat("de-DE", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(parsed)
    : "ungültig";
}

export function settingsProblem(
  settings: TradingSettings,
  limits: TradingLimits,
): string | null {
  const amount = Number(settings.max_capital_usdc);
  const minimum = Number(limits.min_capital_usdc);
  const maximum = Number(limits.max_capital_usdc);
  if (!Number.isFinite(amount) || !Number.isFinite(minimum) || !Number.isFinite(maximum))
    return "Maximalbudget muss eine gültige USDC-Zahl sein.";
  if (amount < minimum || amount > maximum)
    return "Konfigurierbar sind " + formatBudget(minimum) + " bis "
      + formatBudget(maximum) + " USDC.";
  return null;
}

export function derivedDraft(
  maxCapital: string,
  emergencyStop: boolean,
  limits: TradingLimits,
): TradingSettings {
  const parsed = Number(maxCapital);
  const tranche = Math.floor((parsed / 2) * 100) / 100;
  const reserve = parsed - tranche * 2;
  return {
    max_capital_usdc: maxCapital,
    slot_count: 2,
    target_notional_usdc: Number.isFinite(tranche) ? tranche.toFixed(2) : "NaN",
    reserve_usdc: Number.isFinite(reserve) ? Math.max(0, reserve).toFixed(2) : "NaN",
    allocation_policy: "ranked_repeat",
    allocator_version: limits.allocator_version,
    emergency_stop: emergencyStop,
  };
}

export function describeSettings(value: TradingSettings): string {
  const reserve = Number(value.reserve_usdc);
  const reserveText = Number.isFinite(reserve) && reserve > 0
    ? " · Reserve " + formatBudget(reserve) + " USDC"
    : "";
  return "Max. " + formatBudget(value.max_capital_usdc) + " USDC → automatisch "
    + value.slot_count + " × " + formatBudget(value.target_notional_usdc)
    + " USDC · " + value.allocation_policy + reserveText
    + (value.emergency_stop ? " · Einstiegssperre aktiv" : "");
}

export function describeLivePlan(
  saved: TradingSettings | null,
  draft: TradingSettings,
  dirty: boolean,
  saving: boolean,
  limits: TradingLimits | null,
): string {
  if (!saved || !limits)
    return "Gemeinsames Maximalbudget nicht verfügbar. Keine Live-Freigabe.";
  const active = "Gespeichert: " + describeSettings(saved) + ".";
  if (dirty || saving)
    return active + " " + (saving ? "Wird gespeichert" : "Noch nicht übernommen")
      + ": " + describeSettings(draft) + ". "
      + (settingsProblem(draft, limits)
        ?? "Erst Übernehmen klicken, bevor Live angefordert wird.");
  const reference = Number(limits.research_reference_max_usdc ?? "NaN");
  const selected = Number(saved.max_capital_usdc);
  const scaleNote = Number.isFinite(reference) && Number.isFinite(selected) && selected > reference
    ? " Hinweis: Die Kapitalhöhe liegt über der historischen Forschungsreferenz von "
      + formatBudget(reference) + " USDC; echte Marktliquidität und Slippage werden beim "
      + "Echtbetrieb nicht durch den Backtest garantiert."
    : "";
  return active
    + " Dasselbe Budget und derselbe Allocator gelten für Portfolio-Backtest, Paper und normalen Livebetrieb."
    + scaleNote;
}

export class SettingsDraft {
  dirty = false;
  saving = false;

  edit(): void { this.dirty = true; }
  get acceptsPolling(): boolean { return !this.dirty && !this.saving; }
  beginSave(): boolean {
    if (this.saving) return false;
    this.saving = true;
    return true;
  }
  finishSave(success: boolean): void {
    this.saving = false;
    if (success) this.dirty = false;
  }
  discard(): void { if (!this.saving) this.dirty = false; }
}
