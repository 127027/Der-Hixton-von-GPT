/** Private forms: inline feedback, verified sessions, no browser secret storage. */
interface LiveStatus {
  state: string;
  authenticated: boolean;
  password_configured: boolean;
  credentials: { configured: boolean };
  blockers: string[];
  account_check: { blockers: string[] } | null;
  trial?: {state: string; symbol?: string};
}

function element<T extends HTMLElement>(id: string): T {
  const item = document.getElementById(id);
  if (!item) throw new Error(`Missing control: ${id}`);
  return item as T;
}

export function initializeLivePreparation(sharedSettingsBlocker: () => string | null): {refresh: () => Promise<boolean>; dispose: () => void} {
  let last: LiveStatus | null = null;
  let generation = 0;
  let busy = false;
  let focusAfter: string | null = null;
  const privateButtons = ["live-save-key", "live-delete-key", "live-delete-confirm", "live-delete-cancel", "live-check", "live-request", "live-off", "live-lock", "live-trial-start"];
  const message = (id: string, value: string): void => { element(id).textContent = value; };
  const clearSecrets = (): void => {
    for (const id of ["live-password", "live-password-repeat", "live-api-key", "live-api-secret"])
      element<HTMLInputElement>(id).value = "";
    element("live-delete-panel").classList.add("hidden");
  };
  const updateControls = (): void => {
    element<HTMLButtonElement>("live-unlock").disabled = busy;
    element<HTMLFieldSetElement>("live-protected").disabled = busy || !last?.authenticated;
    for (const id of privateButtons) element<HTMLButtonElement>(id).disabled = busy || !last?.authenticated;
    // State comes only from the server, never from clicking an action button.
    const enabled = last?.state === "LIVE_ENABLED";
    const disabled = last?.state === "LIVE_DISABLED" || last?.state === "EXIT_ONLY";
    for (const [id, active] of [["live-request", enabled], ["live-off", disabled]] as const) {
      element(id).setAttribute("aria-pressed", String(active));
      element(id).classList.toggle("is-selected", active);
    }
    message("live-request", enabled ? "● Live ist an" : "Live an");
    message("live-off", disabled ? "● Live ist aus" : "Live aus");
  };
  const render = (status: LiveStatus): void => {
    if (last?.authenticated && !status.authenticated) {
      clearSecrets();
      message("live-auth-result", "Sitzung abgelaufen oder in einem anderen Fenster ersetzt. Bitte erneut entsperren.");
    }
    last = status;
    message("live-state", status.state === "LIVE_DISABLED" ? "Live aus · Echtgeld noch nicht freigegeben"
      : status.state === "LIVE_ENABLED" ? "Live an · echte Orders aktiv"
      : status.state === "EXIT_ONLY" ? "Live aus · offene Positionen laufen aus"
      : status.state.startsWith("TRIAL_") ? `Einmaltest: ${status.state.slice(6)}`
      : `Ungeklärter Live-Status: ${status.state}`);
    element("live-auth-panel").classList.toggle("hidden", status.authenticated);
    element("live-password-repeat-label").classList.toggle("hidden", status.password_configured);
    element<HTMLInputElement>("live-password-repeat").required = !status.password_configured;
    message("live-unlock", status.password_configured ? "Entsperren" : "Passwort speichern & entsperren");
    message("live-auth-help", status.password_configured
      ? "Passwort ist bereits eingerichtet. Verwende das damals gewählte Hixton-Passwort, nicht dein Binance-Passwort. Entsperrung gilt 15 Minuten."
      : "Eigenes lokales Passwort mit mindestens 12 Zeichen wählen und wiederholen. Nicht dein Binance-Passwort.");
    message("live-credentials-status", status.credentials.configured ? "Binance-Schlüssel gespeichert." : "Noch kein Binance-Schlüssel gespeichert.");
    message("live-trial-status", status.trial?.state && status.trial.state !== "NOT_STARTED" ? `Test: ${status.trial.state}${status.trial.symbol ? " · " + status.trial.symbol : ""}` : "Nicht gestartet. Echtgeldanbindung noch gesperrt.");
    const list = element("live-blockers");
    list.replaceChildren();
    for (const reason of new Set([...status.blockers, ...(status.account_check?.blockers ?? [])])) {
      const item = document.createElement("li"); item.textContent = reason; list.append(item);
    }
    updateControls();
  };
  const refresh = async (): Promise<boolean> => {
    const current = ++generation;
    try {
      const response = await fetch("/api/live/status", {cache:"no-store", credentials:"same-origin"});
      const result = await response.json();
      if (current !== generation) return false;
      if (!response.ok) throw new Error("Status nicht erreichbar.");
      render(result as LiveStatus);
      return result.authenticated === true;
    } catch {
      if (current === generation) {
        last = null; clearSecrets(); updateControls();
        element("live-auth-panel").classList.remove("hidden");
        message("live-auth-result", "Verbindung zum Bot fehlt. Bitte erneut versuchen; Zugang bleibt gesperrt.");
        message("live-state", "Status unbekannt · keine Echtgeldfreigabe");
      }
      return false;
    }
  };
  const request = async (path: string, body: Record<string, unknown>): Promise<Record<string, unknown>> => {
    const response = await fetch(`/api/live/${path}`, {
      method:"POST", cache:"no-store", credentials:"same-origin",
      headers:{"Content-Type":"application/json", "X-Hixton-Action":"local-ui-v1"}, body:JSON.stringify(body),
    });
    const result = await response.json() as Record<string, unknown>;
    if (response.status === 409 && (path === "enable" || path === "trial/start")) {
      render(result as unknown as LiveStatus);
      throw new Error("Noch nicht startbereit: Echtgeld-Runtime-Anschluss, Kontoabgleich und Ausführungsabnahme fehlen. Kein Echtgeldauftrag gesendet. Details unter „Technische Freigabe prüfen“.");
    }
    if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : `Aktion fehlgeschlagen (${response.status}).`);
    return result;
  };
  const requireAuth = (): void => {
    if (!last?.authenticated) throw new Error("Zuerst unter Binance verbinden entsperren.");
  };
  const bind = (id: string, event: "click" | "submit", feedback: string, run: () => Promise<void>): void => {
    element(id).addEventListener(event, async (e) => {
      e.preventDefault();
      if (busy) return;
      busy = true; ++generation; focusAfter = null; updateControls();
      message(feedback, "Bitte warten …");
      try { await run(); }
      catch (error) { message(feedback, error instanceof Error ? error.message : "Aktion fehlgeschlagen."); }
      finally {
        await refresh();
        busy = false; updateControls();
        if (focusAfter && last?.authenticated) element(focusAfter).focus();
      }
    });
  };
  bind("live-auth-panel", "submit", "live-auth-result", async () => {
    const password = element<HTMLInputElement>("live-password").value;
    const repeat = element<HTMLInputElement>("live-password-repeat").value;
    element<HTMLInputElement>("live-password").value = "";
    element<HTMLInputElement>("live-password-repeat").value = "";
    await request("unlock", {password, repeat});
    if (!await refresh()) throw new Error("Passwort angenommen, aber Sitzung nicht bestätigt. Cookies für diese lokale Adresse erlauben und erneut entsperren.");
    message("live-auth-result", "Entsperrt. API-Key und Secret können jetzt eingegeben werden.");
    focusAfter = "live-api-key";
  });
  bind("live-key-form", "submit", "live-key-result", async () => {
    requireAuth();
    const api_key = element<HTMLInputElement>("live-api-key").value;
    const secret_key = element<HTMLInputElement>("live-api-secret").value;
    try {
      await request("credentials", {api_key, secret_key, confirmation:"SCHLUESSEL SPEICHERN"});
      message("live-key-result", "Schlüssel sicher gespeichert. Jetzt Verbindung prüfen.");
    } finally {
      element<HTMLInputElement>("live-api-key").value = "";
      element<HTMLInputElement>("live-api-secret").value = "";
    }
  });
  bind("live-check", "click", "live-check-result", async () => {
    requireAuth();
    const result = await request("check", {});
    message("live-check-result", result.account_checks_passed ? "Kontovorprüfung bestanden. Echtgeld-Freigabe bleibt separat." : "Kontovorprüfung blockiert: " + ((result.blockers as string[] | undefined)?.join(" · ") || "Details unter technische Freigabe."));
  });
  bind("live-lock", "click", "live-auth-result", async () => {
    requireAuth(); await request("lock", {}); last = null; clearSecrets();
    message("live-auth-result", "Zugang gesperrt.");
  });
  element("live-delete-key").addEventListener("click", () => element("live-delete-panel").classList.remove("hidden"));
  element("live-delete-cancel").addEventListener("click", () => element("live-delete-panel").classList.add("hidden"));
  bind("live-delete-confirm", "click", "live-key-result", async () => {
    requireAuth();
    await request("credentials/delete", {confirmation:"SCHLUESSEL ENTFERNEN"});
    clearSecrets(); message("live-key-result", "Lokalen Schlüssel entfernt. Bei Binance nicht widerrufen.");
  });
  bind("live-request", "click", "live-result", async () => {
    requireAuth();
    const blocker = sharedSettingsBlocker(); if (blocker) throw new Error(blocker);
    if (!last?.credentials.configured) throw new Error("Zuerst API-Key und Secret speichern und Verbindung prüfen.");
    await request("enable", {});
  });
  bind("live-off", "click", "live-result", async () => {
    requireAuth();
    await request("disable", {});
    message("live-result", "Neue Echtgeld-Einstiege gestoppt, auch beim Einmaltest. Kein Sofortverkauf; Paper läuft weiter.");
  });
  bind("live-trial-start", "click", "live-trial-result", async () => {
    requireAuth();
    const blocker = sharedSettingsBlocker(); if (blocker) throw new Error(blocker);
    if (!last?.credentials.configured) throw new Error("Zuerst API-Key und Secret speichern und Verbindung prüfen.");
    await request("trial/start", {confirmation:"TEST 50 USDC", quote_asset:"USDC", notional_quote:"50.00"});
  });
  window.addEventListener("pagehide", clearSecrets);
  void refresh();
  const timer = window.setInterval(() => { if (!busy) void refresh(); }, 5_000);
  return {refresh, dispose: () => { window.clearInterval(timer); window.removeEventListener("pagehide", clearSecrets); clearSecrets(); }};
}
