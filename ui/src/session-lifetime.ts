/** An open UI connection, not polling or tab focus, grants the visible session lease. */
export function initializeSessionLifetime(): void {
  const notice = document.createElement("aside");
  notice.className = "session-notice";
  notice.setAttribute("role", "status");
  const label = document.createElement("span");
  label.textContent = "Bot-Verbindung wird hergestellt …";
  const stop = document.createElement("button");
  stop.type = "button";
  stop.textContent = "Bot beenden";
  notice.append(label, stop);
  document.querySelector("main")?.prepend(notice);
  let socket: WebSocket | null = null;
  let instance: string | null = null;
  let pageGone = false;
  let explicitlyStopped = false;
  let retry: ReturnType<typeof setTimeout> | undefined;
  stop.addEventListener("click", () => {
    explicitlyStopped = true;
    if (socket?.readyState === WebSocket.OPEN) socket.send("stop");
    socket?.close();
    label.textContent = "Beenden angefordert – offene Binance-Positionen werden nicht verkauft.";
    stop.disabled = true;
  });
  function connect(): void {
    if (pageGone || explicitlyStopped) return;
    socket = new WebSocket(`ws://${window.location.host}/api/session/presence`);
    socket.addEventListener("message", (event) => {
      const message = JSON.parse(String(event.data)) as {instance: string; stopping: boolean};
      if (instance !== null && instance !== message.instance) {
        window.location.reload(); // A new process must load its current UI bundle.
        return;
      }
      instance = message.instance;
      notice.classList.remove("disconnected");
      label.textContent = "Bot verbunden · Terminal oder letzten Bot-Tab schließen = AUS (5 s Schonfrist). Offene Binance-Positionen bleiben dann unbetreut.";
    });
    socket.addEventListener("close", () => {
      notice.classList.add("disconnected");
      label.textContent = "Bot-Verbindung beendet – keine laufende Überwachung bestätigt. Startbot.bat für einen neuen Start öffnen. Offene Binance-Positionen separat prüfen.";
      if (!pageGone && !explicitlyStopped) retry = setTimeout(connect, 1000);
    });
  }
  window.addEventListener("pagehide", () => {
    pageGone = true;
    clearTimeout(retry);
    socket?.close();
  });
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) {
      pageGone = false;
      connect();
    }
  });
  connect();
}
