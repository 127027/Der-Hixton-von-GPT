/** Polling may update the saved state, never an unsaved or in-flight edit. */
export interface TradingSettings {
  slot_count: number;
  target_notional_usdc: string;
  emergency_stop: boolean;
}

export interface TradingLimits { max_slots: number }

export function settingsProblem(settings: TradingSettings, limits: TradingLimits): string | null {
  const amount = Number(settings.target_notional_usdc);
  if (!Number.isInteger(settings.slot_count) || settings.slot_count < 1 || settings.slot_count > limits.max_slots)
    return `Freigegeben sind 1 bis ${limits.max_slots} Slots. Dieser Entwurf kann nicht übernommen werden.`;
  if (!Number.isFinite(amount) || amount <= 0 || !Number.isFinite(settings.slot_count * amount))
    return "Positionsgröße muss eine positive, endliche USDC-Zahl sein.";
  return null;
}

function formatBudget(value: string | number): string {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? new Intl.NumberFormat("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(parsed) : "ungültig";
}

export function describeSettings(value: TradingSettings): string {
  return `${value.slot_count} × ${formatBudget(value.target_notional_usdc)} USDC = ${formatBudget(value.slot_count * Number(value.target_notional_usdc))} USDC${value.emergency_stop ? " · bestehende Einstiegssperre aktiv" : ""}`;
}

export function describeLivePlan(saved: TradingSettings | null, draft: TradingSettings, dirty: boolean, saving: boolean, limits: TradingLimits | null): string {
  if (!saved || !limits) return "Gemeinsame Einstellungen nicht verfügbar. Keine Live-Freigabe.";
  const active = `Gespeichert: ${describeSettings(saved)}.`;
  if (dirty || saving) return `${active} ${saving ? "Wird gespeichert" : "Noch nicht übernommen"}: ${describeSettings(draft)}. ${settingsProblem(draft, limits) ?? "Erst Übernehmen klicken, bevor Live angefordert wird."}`;
  return `${active} Gemeinsame Vorgabe für Paper und normalen Livebetrieb.`;
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
