/** Private forms: inline feedback, verified sessions, no browser secret storage. */
interface LiveStatus {
  state: string;
  trading_settings?: {second_tranche_split_dd_pct?: string | null};
  authenticated: boolean;
  password_configured: boolean;
  credentials: { configured: boolean };
  blockers: string[];
  ready: boolean;
  restart_required?: boolean;
  order_dispatch_available: boolean;
  trial_dispatch_available: boolean;
  trial_retryable_before_submit?: boolean;
  trial_retest_available?: boolean;
  trial_acceptance?: {
    eligible: boolean;
    state: "ACCEPTED" | "RETEST_REQUIRED" | "NOT_VERIFIED" | "ACCOUNT_MISMATCH";
    trial_id: string | null;
    accepted_at_utc: string | null;
    reason: string | null;
  };
  trial_blockers?: string[];
  runtime_health?: string;
  trial_order_execution_blocked_by_health?: boolean;
  account_check: {
    blockers: string[];
    warnings?: string[];
    account_checks_passed?: boolean;
    quote_asset?: string;
    free_quote?: string;
    free_usdc?: string | null;
    free_bnb?: string;
    open_order_count?: number;
  } | null;
  trial?: {state: string; symbol?: string; reason?: string | null; has_unresolved_orders?: boolean; buy?: {state: string} | null; sell?: {state: string} | null};
  trial_continuation?: {exit_only: boolean; frozen_strategy_version: string | null};
  live?: {state: string; used_slots: number; free_slots: number; slot_count?: number; allocation_capacity_units?: number | null; used_allocation_units?: number; open_position_count?: number; diversification_count?: number};
}

function element<T extends HTMLElement>(id: string): T {
  const item = document.getElementById(id);
  if (!item) throw new Error(`Missing control: ${id}`);
  return item as T;
}

export function initializeLivePreparation(sharedSettingsBlocker: (mode?: "live" | "trial") => string | null): {refresh: () => Promise<boolean>; dispose: () => void} {
  let last: LiveStatus | null = null;
  let generation = 0;
  let busy = false;
  let focusAfter: string | null = null;
  let checkError: string | null = null;
  const credentialButtons = [
    "live-save-key",
    "live-delete-key",
    "live-delete-confirm",
    "live-delete-cancel",
    "live-check",
    "live-off",
    "live-lock",
    "live-report-refresh",
    "live-report-download",
  ];
  const message = (id: string, value: string): void => { element(id).textContent = value; };
  const clearSecrets = (): void => {
    for (const id of ["live-password", "live-password-repeat", "live-api-key", "live-api-secret"])
      element<HTMLInputElement>(id).value = "";
    element("live-delete-panel").classList.add("hidden");
  };
  const updateControls = (): void => {
    element<HTMLButtonElement>("live-unlock").disabled = busy;
    element<HTMLFieldSetElement>("live-protected").disabled = busy || !last?.authenticated;
    for (const id of credentialButtons) {
      element<HTMLButtonElement>(id).disabled = busy || !last?.authenticated;
    }
    element<HTMLButtonElement>("live-request").disabled =
      busy || !last?.authenticated || last.restart_required === true || !last.ready || !last.order_dispatch_available;
    element<HTMLButtonElement>("live-trial-start").disabled =
      busy || !last?.authenticated || last.restart_required === true || !last.trial_dispatch_available;
    // State comes only from the server, never from clicking an action button.
    const enabled = last?.state === "LIVE_ENABLED";
    const disabled = last?.state === "LIVE_DISABLED" || last?.state === "EXIT_ONLY";
    for (const [id, active] of [["live-request", enabled], ["live-off", disabled]] as const) {
      element(id).setAttribute("aria-pressed", String(active));
      element(id).classList.toggle("is-selected", active);
    }
    message("live-request", enabled ? "● Live ist an" : "Live an");
    message("live-off", "Echtgeld-Einstiege stoppen");
    const trialState = last?.trial?.state;
    const trialActive = ["WAITING_SIGNAL", "ENTRY_PENDING", "OPEN", "EXIT_PENDING"].includes(trialState ?? "");
    const trialButton = element<HTMLButtonElement>("live-trial-start");
    trialButton.setAttribute("aria-pressed", String(trialActive));
    trialButton.classList.toggle("is-selected", trialActive);
    message("live-trial-start", trialState === "WAITING_SIGNAL" ? "● 50-USDC-Test scharf · wartet auf Signal"
      : trialState === "ENTRY_PENDING" ? "50-USDC-Test · Kauf wird abgeglichen"
      : trialState === "OPEN" ? "● 50-USDC-Test offen"
      : trialState === "EXIT_PENDING" ? "50-USDC-Test · Ausstieg wird abgeglichen"
      : "1 × 50 USDC · Test freigeben");
  };
  const render = (status: LiveStatus): void => {
    if (!busy && last?.trial?.state !== status.trial?.state) message("live-trial-result", "");
    if (!busy && (last?.state !== status.state || last?.restart_required !== status.restart_required)) message("live-result", "");
    if (!busy && last?.restart_required !== status.restart_required) message("live-trial-result", "");
    if (last?.authenticated && !status.authenticated) {
      clearSecrets();
      message("live-auth-result", "Sitzung abgelaufen oder in einem anderen Fenster ersetzt. Bitte erneut entsperren.");
    }
    last = status;
    message("live-state", status.state === "LIVE_DISABLED" ? "Live aus · keine neuen Echtgeld-Einstiege"
      : status.state === "LIVE_ENABLED" ? "Live an · echte Orders aktiv"
      : status.state === "EXIT_ONLY" ? "Live aus · offene Positionen laufen aus"
      : status.state.startsWith("TRIAL_") ? `Einmaltest: ${status.state.slice(6)}`
      : `Ungeklärter Live-Status: ${status.state}`);
    const acceptance = status.trial_acceptance;
    const accepted = acceptance?.state === "ACCEPTED" && acceptance.eligible === true;
    message("live-trial-acceptance", accepted
      ? "50-USDC-Test bestanden · Nachweis dauerhaft gespeichert; "
        + (status.restart_required === true
          ? "Kein neuer Test nötig. Vor einer neuen Freigabe den Bot neu starten."
          : status.state === "LIVE_ENABLED" ? "Live ist eingeschaltet."
            : "Live separat einschalten, sobald die aktuellen Startvoraussetzungen erfüllt sind.")
      : acceptance?.state === "RETEST_REQUIRED"
        ? "Neuer 50-USDC-Test noch nicht bestanden · Live gesperrt."
        : acceptance?.state === "ACCOUNT_MISMATCH"
          ? "50-USDC-Nachweis passt nicht zum aktuellen Binance-Zugang · Live gesperrt."
          : "50-USDC-Nachweis noch nicht bestätigt · Live gesperrt.");
    element("live-auth-panel").classList.toggle("hidden", status.authenticated);
    element("live-password-repeat-label").classList.toggle("hidden", status.password_configured);
    element<HTMLInputElement>("live-password-repeat").required = !status.password_configured;
    message("live-unlock", status.password_configured ? "Entsperren" : "Passwort speichern & entsperren");
    message("live-auth-help", status.password_configured
      ? "Passwort ist bereits eingerichtet. Verwende das damals gewählte Hixton-Passwort, nicht dein Binance-Passwort. Entsperrung gilt 15 Minuten."
      : "Eigenes lokales Passwort mit mindestens 12 Zeichen wählen und wiederholen. Nicht dein Binance-Passwort.");
    message(
      "live-credentials-status",
      status.credentials.configured
        ? "Binance-Zugangsschlüssel lokal gespeichert."
        : "Noch kein Binance-Zugangsschlüssel gespeichert.",
    );
    element("binance-key-missing").classList.toggle("hidden", status.credentials.configured);
    element("binance-account-content").classList.toggle("hidden", !status.credentials.configured);
    const trialState = status.trial?.state ?? "NOT_STARTED";
    const unresolvedTrial = status.trial?.has_unresolved_orders
      || status.trial?.reason === "ORDER_UNKNOWN"
      || [status.trial?.buy?.state, status.trial?.sell?.state].some(state =>
        ["UNKNOWN", "SUBMITTING", "FILL_DETAILS_PENDING"].includes(state ?? ""));
    const unresolvedNotice = "Order ungeklärt · Binance-Abgleich nötig. Kauf/Verkauf nicht bestätigt; keinen weiteren Test starten und Live nicht freigeben.";
    const trialLabels: Record<string, string> = {
      NOT_STARTED: "Nicht freigegeben; noch kein Test-Kauf.",
      WAITING_SIGNAL: "Scharf · wartet auf ein neues Signal; noch kein Test-Kauf.",
      ENTRY_PENDING: "Kauf in Übermittlung oder Abgleich; Ausführung noch nicht bestätigt.",
      OPEN: "Offen · Kauf bestätigt; wartet auf den regulären Strategie-Ausstieg.",
      EXIT_PENDING: status.trial?.sell?.state === "CREATED" || !status.trial?.sell
        ? "Strategie-Ausstieg erkannt · Verkauf vorbereitet, noch nicht an Binance gesendet; Abschluss noch nicht bestätigt."
        : "Verkauf in Übermittlung oder Abgleich; Abschluss noch nicht bestätigt.",
      COMPLETED: "Abgeschlossen; Kauf/Verkauf und Kontenabgleich im Bericht prüfen.",
      CANCELED: "Abgebrochen; kein bestandener regulärer Testabschluss.",
      NEEDS_REVIEW: "Ungeklärt · Bericht prüfen; keine weiteren Einstiege freigeben.",
    };
    const continuation = status.trial_continuation?.exit_only
      ? ` · Bestehender Test läuft mit seiner eingefrorenen Strategie weiter (${status.trial_continuation.frozen_strategy_version}). Keine neuen Test-Käufe.` : "";
    const trialDescription = unresolvedTrial ? unresolvedNotice : trialLabels[trialState] ?? trialState;
    message("real-trial-status", `50-USDC-Einmaltest: ${trialDescription}${status.trial?.symbol ? " · " + status.trial.symbol : ""}${continuation}`);
    message("position-real-status", `50-USDC-Einmaltest: ${trialDescription}${status.trial?.symbol ? " · " + status.trial.symbol : ""}`);
    const live = status.live;
    const weighted = Boolean(live?.allocation_capacity_units || status.trading_settings?.second_tranche_split_dd_pct);
    const distinct = (live?.diversification_count ?? 2) > 2;
    const capacityHidden = weighted && !live?.allocation_capacity_units && !distinct;
    message("real-live-slots", capacityHidden ? "—" : distinct && live ? String(live.free_slots) : live?.allocation_capacity_units
      ? `${Math.max(0, live.allocation_capacity_units - (live.used_allocation_units ?? 0)) * 5} %`
      : live ? String(live.free_slots) : "—");
    const capacityTitle = element("real-live-slots").previousElementSibling;
    if (capacityTitle) capacityTitle.textContent = weighted && !distinct
      ? "Freie Dauer-Live-Kapazität" : "Slots für Dauer-Live";
    message("real-live-slots-detail", live
      ? `${capacityHidden ? "Für genaue Kapazität entsperren" : distinct ? `von ${live.slot_count} · verschiedene Coins` : live.allocation_capacity_units
          ? `${live.open_position_count ?? 0} normale Live-Positionen`
          : `von ${live.slot_count ?? live.used_slots + live.free_slots}`} · ${live.state === "LIVE_DISABLED" ? "Dauer-Live aus" : live.state}. Einmaltest separat.`
      : "Dauer-Live-Kapazität noch nicht bestätigt.");
    if (!status.credentials.configured) element<HTMLDetailsElement>("key-editor").open = true;
    const trialReason = (status.trial_blockers ?? []).join(" · ");
    const signalWait = status.trial?.reason === "ENTRY_WINDOW_EXPIRED"
      ? " Letztes Einstiegssignal verpasst: Marktdaten kamen nach dem 90-Sekunden-Fenster. Keine Order nachgeholt; wartet auf ein neues Signal."
      : "";
    const healthWait = status.trial_order_execution_blocked_by_health
      ? " Order-Ausführung derzeit blockiert: Warmup/Marktdaten sind noch nicht HEALTHY. "
        + "Es wird keine Binance-Order gesendet, bis der Bot HEALTHY meldet."
      : "";
    message(
      "live-trial-status",
      unresolvedTrial ? unresolvedNotice : status.trial?.state && status.trial.state !== "NOT_STARTED"
        ? status.trial_retest_available && status.trial_dispatch_available && status.restart_required !== true
          ? "Vorheriger Test abgeschlossen und abgeglichen. Ein freiwilliger neuer 1×50-USDC-Test sperrt Live bis zum erneuten erfolgreichen Abschluss. Der bisherige Bericht bleibt gespeichert. Noch kein neuer Test freigegeben."
          : status.trial_retryable_before_submit && status.trial_dispatch_available && status.restart_required !== true
          ? `Vor einer Binance-Order beendet (${status.trial.state}) · sicher erneut startbar.`
          : `50-USDC-Einmaltest: ${trialDescription}${status.trial.symbol ? " · " + status.trial.symbol : ""}${healthWait}${signalWait}`
            + (trialState === "COMPLETED" && !status.trial_dispatch_available && trialReason
              ? ` Neue Testfreigabe gesperrt: ${trialReason}.${accepted ? " Kein neuer Test nötig; der bestandene Nachweis bleibt gespeichert." : ""}` : "")
        : status.trial_dispatch_available
          ? `Noch nicht gestartet: Test freigeben, um auf das nächste gültige Signal zu warten.${healthWait}${signalWait}`
          : trialReason
            ? `Noch gesperrt: ${trialReason}`
            : "Nicht gestartet. Voraussetzungen siehe technische Freigabe.",
    );
    const unlockHint = "zuerst oben mit deinem lokalen Hixton-Passwort entsperren";
    const liveReason = status.blockers.join(" · ");
    const liveReadiness = status.state === "LIVE_ENABLED"
      ? `Live ist eingeschaltet · ${status.authenticated ? "echte Orders nach den aktuellen Bot-Regeln." : `für Änderungen ${unlockHint}.`}`
      : !status.authenticated
        ? `Live-Freigabe gesperrt · ${unlockHint}.`
        : status.restart_required === true
          ? `Live-Freigabe gesperrt · ${liveReason || "Bot vor einer neuen Freigabe neu starten."}`
          : status.ready && status.order_dispatch_available
            ? "Bereit: Live separat einschalten. Das Binance-Konto wird beim Klick frisch geprüft."
            : `Live-Freigabe gesperrt · ${liveReason || "Aktuelle Startvoraussetzungen noch nicht bestätigt."}`;
    const trialReadiness = !status.authenticated
      ? `Neue Testfreigabe gesperrt · ${unlockHint}.`
      : status.restart_required === true
        ? `Neue Testfreigabe gesperrt · ${trialReason || "Bot vor einer neuen Freigabe neu starten."}${accepted ? " Kein neuer Test nötig." : ""}`
        : ["WAITING_SIGNAL", "ENTRY_PENDING", "OPEN", "EXIT_PENDING"].includes(trialState)
          ? "Test bereits aktiv · keinen weiteren Test starten. Zustand siehe unten."
          : status.trial_dispatch_available
            ? status.trial_retest_available
              ? "Optional: neuer 50-USDC-Test. Er sperrt Live bis zu seinem erneuten erfolgreichen Abschluss."
              : "Bereit: 50-USDC-Test ausdrücklich freigeben. Kein Sofortkauf; wartet danach auf ein neues gültiges Signal."
            : `Neue Testfreigabe gesperrt · ${trialReason || "Aktuelle Testvoraussetzungen noch nicht bestätigt."}`;
    message("live-readiness", liveReadiness);
    message("live-trial-readiness", trialReadiness);
    element<HTMLButtonElement>("live-request").title = liveReadiness;
    element<HTMLButtonElement>("live-trial-start").title = trialState === "WAITING_SIGNAL"
      ? `Bereits freigegeben; nicht erneut starten. Wartet auf ein neues gültiges Signal, noch kein Test-Kauf.${healthWait}${signalWait}${!status.authenticated ? ` Für Änderungen ${unlockHint}.` : ""}`
      : ["ENTRY_PENDING", "OPEN", "EXIT_PENDING"].includes(trialState)
        ? `50-USDC-Einmaltest: ${trialDescription}${healthWait}${!status.authenticated ? ` Für Änderungen ${unlockHint}.` : ""}`
        : trialReadiness;
    if (status.authenticated && status.credentials.configured && !status.account_check) {
      message(
        "live-check-result",
        checkError ?? (trialState === "EXIT_PENDING"
          ? "Kein frischer Diagnose-Check gespeichert. Der bestehende Test wartet auf Verkauf und Kontenabgleich; keinen neuen Test starten."
          : "Kein frischer Diagnose-Check gespeichert. Das ist kein Startblocker: "
            + "50-USDC-Test und Live prüfen das Binance-Konto beim Klick automatisch neu."),
      );
    }
    const list = element("live-blockers");
    list.replaceChildren();
    for (const reason of new Set([...status.blockers, ...(status.account_check?.blockers ?? [])])) {
      const item = document.createElement("li"); item.textContent = reason; list.append(item);
    }
    for (const warning of new Set(status.account_check?.warnings ?? [])) {
      const item = document.createElement("li");
      item.textContent = `Hinweis (kein Blocker): ${warning}`;
      list.append(item);
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
        message("live-readiness", "Live-Startvoraussetzungen unbekannt · Verbindung zum Bot fehlt.");
        message("live-trial-readiness", "Test-Startvoraussetzungen unbekannt · Verbindung zum Bot fehlt; nicht erneut freigeben.");
        message("live-result", "");
        message("live-check-result", "Binance-Diagnose derzeit nicht bestätigt · Verbindung zum Bot fehlt.");
        element("live-request").title = "Live-Startvoraussetzungen unbekannt · Verbindung zum Bot fehlt.";
        message("live-trial-acceptance", "50-USDC-Nachweis derzeit nicht bestätigt · Verbindung zum Bot fehlt.");
        message("real-trial-status", "Echtgeldtest: Verbindung unterbrochen; Zustand nicht bestätigt.");
        message("real-live-slots", "—");
        message("position-real-status", "Verbindung unterbrochen; Echtgeld-Teststatus nicht bestätigt.");
        message("real-live-slots-detail", "Live-Zustand nicht bestätigt.");
        message("live-trial-status", "Teststatus unbekannt · Verbindung zum Bot fehlt. Nicht erneut freigeben, bis der aktuelle Zustand bestätigt ist.");
        message("live-trial-result", "");
        element("live-trial-start").title = "Teststatus derzeit nicht bestätigt · Verbindung zum Bot fehlt.";
      }
      return false;
    }
  };
  const refreshReport = async (): Promise<void> => {
    requireAuth();
    const report = await request("report", {});
    const summary = report.summary as Record<string, unknown> | undefined;
    const trial = report.trial as Record<string, unknown> | undefined;
    const live = report.live as Record<string, unknown> | undefined;
    message(
      "live-report-summary",
      "Status: " + String(summary?.status ?? "UNBEKANNT")
        + " · Fehler: " + String(summary?.error_count ?? 0)
        + " · Warnungen: " + String(summary?.warning_count ?? 0)
        + " · 50-USDC-Roundtrip Binance-komplett: "
        + String(summary?.trial_binance_roundtrip_complete ?? false)
        + " · Live: " + String(live?.state ?? "LIVE_DISABLED")
        + " · Trial: " + String(trial?.state ?? "NOT_STARTED"),
    );
    element("live-report-output").textContent = JSON.stringify(report, null, 2);
  };

  const request = async (path: string, body: Record<string, unknown>): Promise<Record<string, unknown>> => {
    const response = await fetch(`/api/live/${path}`, {
      method:"POST", cache:"no-store", credentials:"same-origin",
      headers:{"Content-Type":"application/json", "X-Hixton-Action":"local-ui-v1"}, body:JSON.stringify(body),
    });
    const result = await response.json() as Record<string, unknown>;
    if (response.status === 409 && (path === "enable" || path === "trial/start")) {
      if ("state" in result && "blockers" in result) render(result as unknown as LiveStatus);
      throw new Error(
        typeof result.detail === "string"
          ? result.detail
          : "Freigabe sicher abgelehnt. Es wurde keine neue Order ausgelöst.",
      );
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
      catch (error) {
        const detail = error instanceof Error ? error.message : "Aktion fehlgeschlagen.";
        if (id === "live-check") checkError = detail;
        message(feedback, detail);
      }
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
      checkError = null;
      message(
        "live-key-result",
        "Schlüssel sicher gespeichert. Du kannst den 50-USDC-Test direkt starten; "
          + "„Binance-Verbindung prüfen“ ist optional zur Diagnose.",
      );
    } finally {
      element<HTMLInputElement>("live-api-key").value = "";
      element<HTMLInputElement>("live-api-secret").value = "";
    }
  });
  bind("live-check", "click", "live-check-result", async () => {
    requireAuth();
    const result = await request("check", {});
    checkError = null;
    const freeUsdc = typeof result.free_usdc === "string" ? ` · frei: ${result.free_usdc} USDC` : "";
    const warnings = Array.isArray(result.warnings)
      ? result.warnings.filter((item): item is string => typeof item === "string")
      : [];
    const warningText = warnings.length ? ` Hinweis (kein Blocker): ${warnings.join(" · ")}` : "";
    message(
      "live-check-result",
      result.account_checks_passed
        ? `Binance-Verbindung und Kontovorprüfung bestanden${freeUsdc}. Echtgeld-Freigabe bleibt separat.${warningText}`
        : "Kontovorprüfung blockiert: "
          + ((result.blockers as string[] | undefined)?.join(" · ")
            || "Details unter technische Freigabe."),
    );
  });
  bind("live-report-refresh", "click", "live-report-summary", async () => {
    await refreshReport();
  });
  bind("live-report-download", "click", "live-report-summary", async () => {
    requireAuth();
    // POST supplies the browser Origin and the explicit local-action header.
    // Errors stay on this page, preserving the bot's presence connection.
    const response = await fetch("/api/live/report/download", {
      method:"POST", cache:"no-store", credentials:"same-origin",
      headers:{"Content-Type":"application/json", "X-Hixton-Action":"local-ui-v1"}, body:"{}",
    });
    if (!response.ok) {
      const result = await response.json() as Record<string, unknown>;
      throw new Error(typeof result.detail === "string" ? result.detail : "Bericht konnte nicht heruntergeladen werden.");
    }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = "Hixton-Live-Bericht.json";
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    message("live-report-summary", "JSON-Bericht heruntergeladen. Der Bot läuft weiter.");
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
    checkError = null;
    clearSecrets(); message("live-key-result", "Lokalen Schlüssel entfernt. Bei Binance nicht widerrufen.");
  });
  bind("live-request", "click", "live-result", async () => {
    requireAuth();
    if (last?.restart_required === true || !last?.ready || !last.order_dispatch_available) {
      throw new Error("Produktiver Livehandel ist serverseitig noch nicht freigegeben.");
    }
    const blocker = sharedSettingsBlocker(); if (blocker) throw new Error(blocker);
    if (!last.credentials.configured) {
      throw new Error("Zuerst API-Key und Secret lokal speichern.");
    }
    await request("enable", {confirmation:"LIVE MAXIMALBUDGET AKTIVIEREN"});
    message(
      "live-result",
      "Budgetgesteuerter Livebetrieb aktiviert. Es wird keine Order nachgeholt; der Bot wartet auf neue gültige Signale und nutzt das gespeicherte Maximalbudget.",
    );
  });
  bind("live-off", "click", "live-result", async () => {
    requireAuth();
    await request("disable", {});
    message("live-result", "Neue Echtgeld-Einstiege gestoppt. Ein wartender 50-USDC-Test ist abgebrochen; bereits gekaufte Positionen bleiben bis zum regulären Ausstieg überwacht. Kein Sofortverkauf; Paper läuft weiter.");
  });
  bind("live-trial-start", "click", "live-trial-result", async () => {
    requireAuth();
    if (last?.restart_required === true || !last?.trial_dispatch_available) {
      throw new Error("Der 50-USDC-Testtrade ist serverseitig noch nicht freigegeben.");
    }
    const blocker = sharedSettingsBlocker("trial"); if (blocker) throw new Error(blocker);
    if (!last.credentials.configured) {
      throw new Error("Zuerst API-Key und Secret lokal speichern.");
    }
    await request("trial/start", {
      confirmation:"TEST 50 USDC",
      quote_asset:"USDC",
      notional_quote:"50.00",
    });
    message(
      "live-trial-result",
      "1×50-Echtgeldtest scharf. Kontoprüfung und Baseline sind bestanden. "
        + "Noch keine Order wurde sofort gesendet; der Bot wartet auf ein neues gültiges Signal.",
    );
  });
  window.addEventListener("pagehide", clearSecrets);
  const foreground = async (): Promise<void> => { if (!busy) await refresh(); };
  const visible = async (): Promise<void> => {
    if (document.visibilityState === "visible") await foreground();
  };
  window.addEventListener("focus", foreground);
  window.addEventListener("pageshow", foreground);
  document.addEventListener("visibilitychange", visible);
  void refresh();
  const timer = window.setInterval(() => { if (!busy) void refresh(); }, 5_000);
  return {refresh, dispose: () => {
    ++generation;
    window.clearInterval(timer);
    window.removeEventListener("pagehide", clearSecrets);
    window.removeEventListener("focus", foreground);
    window.removeEventListener("pageshow", foreground);
    document.removeEventListener("visibilitychange", visible);
    clearSecrets();
  }};
}
