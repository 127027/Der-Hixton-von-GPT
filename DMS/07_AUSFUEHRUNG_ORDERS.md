# 07 – Ausführung und Orders

Status: CURRENT · 21.09.2026

Paper und Backtest bleiben die Referenz für Strategie- und Portfolio-Parität. Ein Signal entsteht auf einer geschlossenen 1h-Bar; historische Ausführung verwendet das nächste verfügbare Bar-Open plus Kostenmodell. Paper-Fills sind keine Binance-Fills.

## Lokaler kontrollierter Echtgeldpfad

1. Binance API-Key/Secret werden ausschließlich lokal im Windows-Anmeldedatenspeicher gehalten.
2. Eine private Kontovorprüfung muss Spot/USDC, erlaubte Rechte, freien Saldo, offene Orders und die zehn Märkte bestätigen.
3. Der erste Echtgeldschritt ist ausdrücklich **1 × 50 USDC**. Das Freigeben sendet keine Order nachträglich oder sofort, sondern setzt einen einmaligen Anspruch und wartet auf ein neues gültiges V6-Signal.
4. Nach dem Kauf darf nur der zugehörige reguläre Exit ausgeführt werden. Danach müssen Orderhistorie/Fills und Kontosalden vollständig reconciled sein.
5. Dauerbetrieb ist erst danach mit exakt **3 × 80 USDC** erlaubt. 10×250 bleibt reines Forschungslabor.

## Order-Sicherheit

Jede Order erhält vor dem Netzaufruf eine persistierte eindeutige Intent-/Client-Order-ID. Bei Timeout oder unbekanntem Ergebnis wird dieselbe Order-ID ausschließlich abgefragt; sie wird nicht blind erneut gesendet. Parallelzugriffe, Restarts und wiederholte Scheduler-Ticks dürfen denselben Intent nicht duplizieren.

BUY ist auf die freigegebene Quote-Budgetgröße begrenzt; im 3×80-Betrieb sind maximal 240 USDC gleichzeitig gebunden. SELL darf höchstens den persistent als Bot-Bestand geführten Base-Bestand verkaufen. Abweichende Salden, fremde Orders, partielle/problematische Restmengen oder ungeklärte Zustände führen zu NEEDS_REVIEW und sperren neue Einstiege.

Live aus stoppt neue Einstiege, storniert keine unbekannte Order blind und erzwingt keinen Sofortverkauf. Bereits eigene offene Positionen dürfen weiterhin regulär aussteigen.

Cloud-/CI-/Agentenpfade besitzen keine Binance-Secrets und senden niemals Echtgeld- oder Testnet-Orders.
