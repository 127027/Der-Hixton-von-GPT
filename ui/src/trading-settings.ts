import {SettingsDraft, describeLivePlan, describeSettings, settingsProblem, type TradingSettings, type TradingLimits} from "./settings-draft";

const item = <T extends HTMLElement>(id: string): T => {
  const found = document.getElementById(id);
  if (!found) throw new Error(`Missing control: ${id}`);
  return found as T;
};

/** One settings form; a click is consent to save, not consent to start real trading. */
export function initializeTradingSettings(save: (value: TradingSettings) => Promise<TradingSettings>, onSaved: (value: TradingSettings) => void) {
  const draft = new SettingsDraft();
  let saved: TradingSettings | null = null;
  let limits: TradingLimits | null = null;
  let failure = "";
  const read = (): TradingSettings => ({
    slot_count: Number(item<HTMLInputElement>("slot-input").value),
    target_notional_usdc: item<HTMLInputElement>("notional-input").value,
    // Preserve a legacy safety latch; removing its UI must not silently clear it.
    emergency_stop: saved?.emergency_stop ?? false,
  });
  const draw = (): void => {
    if (saved && draft.acceptsPolling) {
      item<HTMLInputElement>("slot-input").value = String(saved.slot_count);
      item<HTMLInputElement>("notional-input").value = String(Number(saved.target_notional_usdc));
    }
    const value = read();
    for (const id of ["slot-input", "notional-input", "settings-button"])
      item<HTMLInputElement | HTMLButtonElement>(id).disabled = draft.saving || !saved || !limits;
    item("settings-button").textContent = draft.saving ? "Wird übernommen …" : "Übernehmen";
    item("settings-saved").textContent = saved ? `Gespeichert: ${describeSettings(saved)}` : "Einstellungen nicht verfügbar.";
    item("settings-validation").textContent = failure || (draft.dirty && limits ? settingsProblem(value, limits) ?? "" : "");
    item("settings-edit-state").textContent = draft.dirty ? "Änderungen sind noch nicht übernommen." : "";
    item("live-plan").textContent = describeLivePlan(saved, value, draft.dirty, draft.saving, limits);
    if (limits) {
      item<HTMLInputElement>("slot-input").max = String(limits.max_slots);
    }
  };
  for (const id of ["slot-input", "notional-input"])
    item(id).addEventListener("input", () => { draft.edit(); failure = ""; draw(); });
  item("trading-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (draft.saving || !saved || !limits) return;
    if (!item<HTMLInputElement>("slot-input").reportValidity() || !item<HTMLInputElement>("notional-input").reportValidity()) return;
    const value = read();
    failure = settingsProblem(value, limits) ?? "";
    if (failure) { draw(); return; }
    if (!draft.beginSave()) return;
    draw();
    try {
      saved = await save(value);
      draft.finishSave(true);
      onSaved(saved);
    } catch (error) {
      draft.finishSave(false);
      failure = error instanceof Error ? error.message : "Speichern fehlgeschlagen. Entwurf bleibt erhalten.";
    }
    draw();
  });
  draw();
  return {
    render(value: TradingSettings | null, boundaries: TradingLimits | null): void { saved = value; limits = boundaries; draw(); },
    liveBlocker(): string | null {
      return !saved || !limits ? "Handelseinstellungen nicht geladen." : draft.dirty || draft.saving
        ? "Zuerst die Handelseinstellungen mit Übernehmen speichern."
        : saved.emergency_stop ? "Bestehende technische Einstiegssperre aktiv. Nicht automatisch aufgehoben." : null;
    },
  };
}
