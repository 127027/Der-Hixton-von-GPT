import {
  SettingsDraft,
  derivedDraft,
  describeLivePlan,
  describeSettings,
  settingsProblem,
  type TradingSettings,
  type TradingLimits,
} from "./settings-draft";

const item = <T extends HTMLElement>(id: string): T => {
  const found = document.getElementById(id);
  if (!found) throw new Error("Missing control: " + id);
  return found as T;
};

/** One budget form; saving changes Paper immediately and never starts real trading. */
export function initializeTradingSettings(
  save: (value: TradingSettings) => Promise<TradingSettings>,
  onSaved: (value: TradingSettings) => void,
) {
  const draft = new SettingsDraft();
  let saved: TradingSettings | null = null;
  let limits: TradingLimits | null = null;
  let failure = "";

  const read = (): TradingSettings => {
    if (!limits) {
      return saved ?? {
        max_capital_usdc: item<HTMLInputElement>("capital-input").value,
        slot_count: 2,
        target_notional_usdc: "0",
        reserve_usdc: "0",
        allocation_policy: "ranked_repeat",
        allocator_version: "",
        emergency_stop: false,
      };
    }
    return derivedDraft(
      item<HTMLInputElement>("capital-input").value,
      saved?.emergency_stop ?? false,
      limits,
    );
  };

  const draw = (): void => {
    if (saved && draft.acceptsPolling)
      item<HTMLInputElement>("capital-input").value =
        String(Number(saved.max_capital_usdc));
    const value = read();
    for (const id of ["capital-input", "settings-button"])
      item<HTMLInputElement | HTMLButtonElement>(id).disabled =
        draft.saving || !saved || !limits;
    item("settings-button").textContent =
      draft.saving ? "Wird übernommen …" : "Übernehmen";
    item("settings-saved").textContent = saved
      ? "Gespeichert: " + describeSettings(saved)
      : "Einstellungen nicht verfügbar.";
    item("settings-validation").textContent =
      failure || (draft.dirty && limits ? settingsProblem(value, limits) ?? "" : "");
    item("settings-edit-state").textContent =
      draft.dirty ? "Änderungen sind noch nicht übernommen." : "";
    item("live-plan").textContent =
      describeLivePlan(saved, value, draft.dirty, draft.saving, limits);
    if (limits) {
      const input = item<HTMLInputElement>("capital-input");
      input.min = limits.min_capital_usdc;
      input.max = limits.max_capital_usdc;
    }
  };

  item("capital-input").addEventListener("input", () => {
    draft.edit();
    failure = "";
    draw();
  });

  item("trading-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (draft.saving || !saved || !limits) return;
    if (!item<HTMLInputElement>("capital-input").reportValidity()) return;
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
      failure = error instanceof Error
        ? error.message
        : "Speichern fehlgeschlagen. Entwurf bleibt erhalten.";
    }
    draw();
  });

  draw();
  return {
    render(value: TradingSettings | null, boundaries: TradingLimits | null): void {
      saved = value;
      limits = boundaries;
      draw();
    },
    liveBlocker(): string | null {
      return !saved || !limits
        ? "Maximalbudget nicht geladen."
        : draft.dirty || draft.saving
          ? "Zuerst das Maximalbudget mit Übernehmen speichern."
          : saved.emergency_stop
            ? "Bestehende technische Einstiegssperre aktiv. Nicht automatisch aufgehoben."
            : null;
    },
  };
}
