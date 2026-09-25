# 07 – Ausführung und Orders

Status: CURRENT · 25.09.2026

Paper und Backtest sind die Referenz für Strategie-/Allocator-Parität. Ein Signal entsteht auf einer geschlossenen 1h-Bar. Historische Ausführung nutzt das nächste verfügbare Bar-Open plus Kostenmodell; Paper-Fills sind keine Binance-Fills.

## Kontrollierter Echtgeldpfad

1. Binance API-Key/Secret liegen ausschließlich lokal im Windows-Anmeldedatenspeicher.
2. Die Kontovorprüfung verlangt Spot/USDC, sichere Rechte, freie Salden, keine fremden offenen Orders und gültige Marktfilter.
3. Der erste Echtgeldschritt ist **1 × 50 USDC**. Das Freigeben sendet nicht sofort eine Order, sondern wartet auf ein neues gültiges Signal.
4. Nach dem Entry darf nur der zugehörige reguläre Exit ausgeführt werden; danach müssen Orders/Fills/Salden vollständig reconciled sein.
5. Erst danach kann normaler Livebetrieb das gespeicherte **Maximalbudget** verwenden. Beim Standard 250 USDC leitet `CAPITAL-V1-2X50PCT` 2 × 125 USDC ranked_repeat ab.
6. Eine Änderung des Maximalbudgets ändert keinen bereits gebundenen Live-Plan stillschweigend; neue Einstiege werden gesperrt und eine sichere erneute Freigabe ist erforderlich.

Jede Order erhält vor dem Netzaufruf eine persistierte Client-/Intent-ID. Bei Timeout oder unbekanntem Ergebnis wird dieselbe ID abgefragt und **nicht blind erneut gesendet**. Restarts und wiederholte Scheduler-Ticks dürfen keine Doppelorder erzeugen.

BUY ist auf den persistent gebundenen Kapitalplan begrenzt. SELL darf höchstens den vom Bot persistent geführten Base-Bestand verkaufen. Konto-/Orderabweichungen, problematische Teilfills oder ungeklärte Zustände führen zu NEEDS_REVIEW und sperren neue Einstiege.

Live aus stoppt neue Einstiege, erzwingt keinen Sofortverkauf und storniert unbekannte Orders nicht blind.
