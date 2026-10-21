/** Local Telegram contact settings. Saving never sends a message or enables trading. */
interface NotificationStatus {
  authenticated: boolean;
  configured: boolean;
  enabled: boolean;
  recipient?: string;
  secret_configured?: boolean;
  pending?: number;
  last_sent_at?: string | null;
  last_error?: string | null;
}

function control<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) throw new Error(`Missing notification control: ${id}`);
  return node as T;
}

export function initializeNotifications(): {refresh: () => Promise<void>; dispose: () => void} {
  let last: NotificationStatus | null = null;
  let generation = 0;
  let accessEpoch = 0;
  let busy = false;
  let dirty = false;
  let disposed = false;
  let suspended = false;
  const text = (id: string, value: string): void => { control(id).textContent = value; };
  const clearSecret = (): void => { control<HTMLInputElement>("notification-secret").value = ""; };
  const redactPrivate = (): void => {
    ++accessEpoch;
    clearSecret(); dirty = false;
    control<HTMLInputElement>("notification-recipient").value = "";
    control<HTMLSelectElement>("notification-chat-choice").replaceChildren();
    control<HTMLSelectElement>("notification-chat-choice").value = "";
    control("notification-chat-choice-wrap").classList.add("hidden");
  };
  const actionCurrent = (epoch: number): boolean =>
    !disposed && !suspended && epoch === accessEpoch && last?.authenticated === true;
  const updateControls = (): void => {
    control<HTMLFieldSetElement>("notification-protected").disabled = busy || !last?.authenticated;
    for (const id of ["notification-save", "notification-token-save", "notification-discover"])
      control<HTMLButtonElement>(id).disabled = busy || !last?.authenticated;
    control("notification-token-save").classList.toggle("hidden", last?.configured === true);
    control<HTMLButtonElement>("notification-test").disabled = busy || dirty || !last?.authenticated || !last.configured;
    control<HTMLButtonElement>("notification-delete").disabled = busy || !last?.authenticated || !(last.configured || last.secret_configured);
    text("notification-edit-state", dirty ? "Änderungen noch nicht gespeichert. Erst speichern, dann eine Testmeldung senden." : "Speichern sendet keine Testmeldung und keine früheren Handelsmeldungen.");
  };
  const render = (status: NotificationStatus): void => {
    last = status;
    if (!status.authenticated) {
      redactPrivate();
      last = {authenticated:false, configured:status.configured, enabled:status.enabled};
      text("notification-secret-help", "Tokenstatus nach dem Entsperren prüfen. Das Token bleibt ausschließlich lokal gespeichert.");
      if (busy) text("notification-feedback", "Sitzung abgelaufen. Späte Kontaktantworten werden nicht angezeigt.");
      text("notification-status", status.configured
        ? `Telegram-Kontakt gespeichert · ${status.enabled ? "Meldungen aktiviert" : "Meldungen aus"}. Zum Bearbeiten oben entsperren.`
        : "Noch kein Telegram-Kontakt. Zum Einrichten oben entsperren.");
    } else {
      text("notification-secret-help", status.secret_configured
        ? "Token gespeichert (erneute Eingabe nicht nötig). Nur zum Ersetzen ein neues Token eintragen."
        : "Noch kein Token gespeichert. BotFather-Token eintragen und mit Schritt 1 sicher speichern.");
      if (!dirty) {
        control<HTMLInputElement>("notification-enabled").checked = status.enabled;
        control<HTMLInputElement>("notification-recipient").value = status.recipient ?? "";
      }
      const pending = status.pending ? ` · ${status.pending} Meldung(en) warten` : "";
      const sent = status.last_sent_at
        ? ` · zuletzt vom Versanddienst angenommen: ${new Intl.DateTimeFormat("de-DE", {dateStyle:"short", timeStyle:"short", timeZone:"Europe/Berlin"}).format(new Date(status.last_sent_at))}` : "";
      text("notification-status", status.configured
        ? `Telegram ${status.enabled ? "aktiviert" : "aus"}${pending}${sent}${status.last_error ? ` · ${status.last_error}` : ""}`
        : status.secret_configured
          ? "Token sicher gespeichert · Chat-ID fehlt. Jetzt privaten Chat finden."
          : "Noch kein Telegram-Kontakt und kein Token gespeichert.");
    }
    updateControls();
  };
  const refresh = async (): Promise<void> => {
    if (disposed || suspended) return;
    const current = ++generation;
    try {
      const response = await fetch("/api/live/notifications", {cache:"no-store", credentials:"same-origin"});
      if (!response.ok) throw new Error("Kontaktstatus nicht erreichbar.");
      const status = await response.json() as NotificationStatus;
      if (current === generation && !disposed && !suspended) render(status);
    } catch {
      if (current !== generation) return;
      last = null; redactPrivate(); updateControls();
      text("notification-status", "Kontaktstatus nicht erreichbar. Keine Versandbestätigung verfügbar.");
    }
  };
  const request = async (suffix: string, body: Record<string, unknown>, epoch: number): Promise<Record<string, unknown>> => {
    const response = await fetch(`/api/live/notifications${suffix}`, {
      method:"POST", credentials:"same-origin", cache:"no-store",
      headers:{"Content-Type":"application/json", "X-Hixton-Action":"local-ui-v1"}, body:JSON.stringify(body),
    });
    const result = await response.json() as Record<string, unknown>;
    if (!actionCurrent(epoch)) throw new Error("Kontaktaktion gehört zu einer abgelaufenen Sitzung.");
    if (response.status === 401) {
      ++generation; last = null; redactPrivate(); updateControls();
      text("notification-feedback", "Kontaktbereich gesperrt. Zum Fortfahren oben erneut entsperren.");
      throw new Error("Kontaktaktion gehört zu einer abgelaufenen Sitzung.");
    }
    if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : `Aktion fehlgeschlagen (${response.status}).`);
    return result;
  };
  const act = async (run: (epoch: number) => Promise<void>): Promise<void> => {
    if (busy || disposed || suspended) return;
    if (!last?.authenticated) { clearSecret(); text("notification-feedback", "Zuerst oben mit deinem lokalen Hixton-Passwort entsperren."); return; }
    busy = true; ++generation; updateControls(); text("notification-feedback", "Bitte warten …");
    const epoch = accessEpoch;
    try { await run(epoch); }
    catch (error) {
      if (actionCurrent(epoch)) text("notification-feedback", error instanceof Error ? error.message : "Aktion fehlgeschlagen.");
    }
    finally { if (actionCurrent(epoch)) await refresh(); busy = false; updateControls(); }
  };
  const edited = (): void => { dirty = true; updateControls(); };
  for (const id of ["notification-enabled", "notification-recipient", "notification-secret"])
    for (const event of ["input", "change"]) control(id).addEventListener(event, edited);
  control("notification-form").addEventListener("submit", event => {
    event.preventDefault();
    return act(async epoch => {
      const recipient = control<HTMLInputElement>("notification-recipient").value.trim();
      if (!/^[1-9][0-9]{0,19}$/.test(recipient))
        throw new Error("Die private Chat-ID muss eine positive Zahl sein, kein Bot-Link oder Benutzername. Bitte „Privaten Chat finden“ wählen und deinen Chat auswählen.");
      if (!control<HTMLInputElement>("notification-secret").value.trim() && !last?.secret_configured)
        throw new Error("Noch kein Bot-Token gespeichert. Zuerst bei Schritt 1 das BotFather-Token eintragen und speichern.");
      try {
        await request("", {
          channel:"telegram", enabled:control<HTMLInputElement>("notification-enabled").checked,
          recipient,
          secret:control<HTMLInputElement>("notification-secret").value.trim(),
        }, epoch);
        if (!actionCurrent(epoch)) return;
        dirty = false;
        text("notification-feedback", "Kontakt gespeichert. Es wurde keine Nachricht versendet.");
      } finally { clearSecret(); }
    });
  });
  control("notification-token-save").addEventListener("click", () => act(async epoch => {
    if (last?.configured) throw new Error("Kontakt ist bereits eingerichtet. Tokenänderungen mit dem vollständigen Kontakt speichern.");
    const secret = control<HTMLInputElement>("notification-secret").value.trim();
    if (!secret && !last?.secret_configured)
      throw new Error("Noch kein Bot-Token gespeichert. Bitte das BotFather-Token oben eintragen und Schritt 1 erneut wählen.");
    try {
      await request("", {channel:"telegram", secret, recipient:"", enabled:false}, epoch);
      if (!actionCurrent(epoch)) return;
      control<HTMLInputElement>("notification-recipient").value = "";
      control<HTMLInputElement>("notification-enabled").checked = false;
      dirty = false;
      text("notification-feedback", "Token sicher gespeichert. Jetzt privaten Chat finden.");
    } finally { clearSecret(); }
  }));
  control("notification-discover").addEventListener("click", () => act(async epoch => {
    const secret = control<HTMLInputElement>("notification-secret").value.trim();
    if (!secret && !last?.secret_configured)
      throw new Error("Noch kein Bot-Token vorhanden. Bitte zuerst bei Schritt 1 das Token eintragen und speichern.");
    const result = await request("/discover", {secret}, epoch);
    if (!actionCurrent(epoch)) return;
    const chats = Array.isArray(result.chats) ? result.chats : [];
    const choices = control<HTMLSelectElement>("notification-chat-choice");
    choices.replaceChildren();
    const placeholder = document.createElement("option"); placeholder.value = ""; placeholder.textContent = "Chat auswählen …"; choices.append(placeholder);
    let count = 0;
    for (const raw of chats) {
      if (!raw || typeof raw !== "object") continue;
      const chat = raw as Record<string, unknown>;
      if (typeof chat.id !== "string" || typeof chat.label !== "string") continue;
      const option = document.createElement("option"); option.value = chat.id; option.textContent = `${chat.label} · ${chat.id}`; choices.append(option); count++;
    }
    choices.value = "";
    control("notification-chat-choice-wrap").classList.toggle("hidden", count === 0);
    text("notification-feedback", count
      ? "Private Chats gefunden. Deinen Chat auswählen und den Kontakt speichern. Es wurde keine Nachricht versendet."
      : "Noch kein privater Chat gefunden. Deinen eigenen Bot in Telegram öffnen, /start senden und erneut suchen.");
  }));
  control("notification-chat-choice").addEventListener("change", () => {
    const id = control<HTMLSelectElement>("notification-chat-choice").value;
    if (id) { control<HTMLInputElement>("notification-recipient").value = id; edited(); }
  });
  control("notification-test").addEventListener("click", () => act(async epoch => {
    if (dirty || !last?.configured) throw new Error("Kontaktänderungen zuerst speichern.");
    const result = await request("/test", {}, epoch);
    if (!actionCurrent(epoch)) return;
    if (result.accepted !== true) throw new Error("Versandannahme nicht bestätigt. Status prüfen, bevor du erneut sendest.");
    text("notification-feedback", "Testmeldung vom Versanddienst angenommen. Zustellung und Lesen bitte in Telegram prüfen.");
  }));
  control("notification-delete").addEventListener("click", () => act(async epoch => {
    await request("/delete", {}, epoch);
    if (!actionCurrent(epoch)) return;
    clearSecret(); dirty = false;
    control<HTMLSelectElement>("notification-chat-choice").replaceChildren();
    control("notification-chat-choice-wrap").classList.add("hidden");
    text("notification-feedback", "Kontakt und lokal gespeichertes Bot-Token entfernt. Der Handelszustand bleibt unverändert.");
  }));
  const locked = (): void => {
    ++generation; last = null; redactPrivate(); updateControls();
    text("notification-status", "Kontaktbereich gesperrt. Zum Bearbeiten oben erneut entsperren.");
    text("notification-feedback", "Kontaktbereich gesperrt. Späte Antworten werden nicht angezeigt.");
  };
  const pagehide = (): void => { suspended = true; locked(); };
  const pageshow = (): void => { suspended = false; void refresh(); };
  control("live-lock").addEventListener("click", locked);
  window.addEventListener("pagehide", pagehide);
  window.addEventListener("pageshow", pageshow);
  void refresh();
  const timer = window.setInterval(() => { if (!busy) void refresh(); }, 5_000);
  return {refresh, dispose: () => {
    disposed = true; ++generation; redactPrivate();
    window.clearInterval(timer);
    window.removeEventListener("pagehide", pagehide); window.removeEventListener("pageshow", pageshow);
    control("live-lock").removeEventListener("click", locked);
  }};
}
