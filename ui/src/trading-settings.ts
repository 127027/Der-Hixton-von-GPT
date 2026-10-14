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
        auto_budget_enabled: item<HTMLInputElement>("auto-budget-input").checked,
        autonomous_performance_enabled: item<HTMLInputElement>("performance-mode-input").checked,
      };
    }
    return { ...derivedDraft(
      item<HTMLInputElement>("auto-budget-input").checked && saved
        ? saved.max_capital_usdc : item<HTMLInputElement>("capital-input").value,
      item<HTMLInputElement>("entry-pause-input").checked,
      limits,
    ), gap_fillers_enabled: item<HTMLInputElement>("gap-fillers-input").checked,
       auto_budget_enabled: item<HTMLInputElement>("auto-budget-input").checked,
       autonomous_performance_enabled: item<HTMLInputElement>("performance-mode-input").checked,
       diversification_stages: saved?.diversification_stages };
  };

  const draw = (): void => {
    if (saved && draft.acceptsPolling)
      item<HTMLInputElement>("capital-input").value =
        String(Number(saved.max_capital_usdc));
    const value = read();
    for (const id of ["capital-input", "entry-pause-input", "gap-fillers-input", "auto-budget-input", "performance-mode-input", "settings-button"])
      item<HTMLInputElement | HTMLButtonElement>(id).disabled =
        draft.saving || !saved || !limits;
    const automatic = item<HTMLInputElement>("auto-budget-input").checked;
    const capital = item<HTMLInputElement>("capital-input");
    capital.disabled = capital.disabled || automatic;
    if (automatic && saved) capital.value = String(Number(saved.max_capital_usdc));
    capital.title = automatic ? "Im Automatikmodus inaktiv; kein zusätzliches Kapital-Limit." : "Aktives maximales Budget im manuellen Modus.";
    item("budget-mode-help").textContent = automatic
      ? "Automatik: verfügbare Binance-USDC sind maßgeblich. Der Betrag links ist inaktiv und nur für den manuellen Modus gespeichert."
      : "Manuell: Der Betrag links ist dein maximales Budget. Änderungen mit Übernehmen speichern.";
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
  item("auto-budget-input").addEventListener("change", () => {
    // One owner-facing checkbox controls both internal research policies.
    item<HTMLInputElement>("performance-mode-input").checked =
      item<HTMLInputElement>("auto-budget-input").checked;
    draft.edit(); failure = ""; draw();
  });
  item("performance-mode-input").addEventListener("change", () => {
    draft.edit(); failure = ""; draw();
  });
  item("gap-fillers-input").addEventListener("change", () => {
    draft.edit(); failure = ""; draw();
  });
  item("entry-pause-input").addEventListener("change", () => {
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
      if (saved && draft.acceptsPolling)
        item<HTMLInputElement>("entry-pause-input").checked = saved.emergency_stop;
      if (saved && draft.acceptsPolling)
        item<HTMLInputElement>("gap-fillers-input").checked = saved.gap_fillers_enabled !== false;
      if (saved && draft.acceptsPolling)
        item<HTMLInputElement>("auto-budget-input").checked =
          saved.auto_budget_enabled === true && saved.autonomous_performance_enabled === true;
      if (saved && draft.acceptsPolling)
        item<HTMLInputElement>("performance-mode-input").checked = saved.autonomous_performance_enabled === true;
      draw();
    },
    liveBlocker(mode: "live" | "trial" = "live"): string | null {
      return !saved || !limits
        ? "Maximalbudget nicht geladen."
        : draft.dirty || draft.saving
          ? "Zuerst das Maximalbudget mit Übernehmen speichern."
          : saved.emergency_stop
            ? "Bestehende technische Einstiegssperre aktiv. Nicht automatisch aufgehoben."
            : mode === "live" && ((saved.auto_budget_enabled && saved.auto_budget_live_available !== true)
              || (saved.autonomous_performance_enabled && saved.autonomous_performance_live_available !== true))
              ? "Dynamisches Budget ist nur vorgemerkt. Live bleibt bis zur Sicherheitsfreigabe gesperrt."
              : null;
    },
  };
}
