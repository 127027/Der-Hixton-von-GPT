# 08 – UI/UX-Spezifikation

Status: CURRENT · 21.09.2026

Die lokale deutsche UI zeigt:
- System-/Paperstatus und aktuelle V6-ID;
- zehn USDC-Marktkarten und aktuelle Coin-Profile;
- Charts/Signale/Paper-Fills;
- offene Paperpositionen und Ereignisse;
- Datenqualität;
- System-/Runtime-Logs;
- Backtests: gemeinsames Portfolio, 10×250 isoliert und Einzelcoin.

Backtests besitzen keine V1/V2/V3-Auswahl mehr. Nur aktuelle V6 ist auswählbar. Die Anzeige unterscheidet Positionszyklen und Slot-Trades.

Der Einstellungsbereich zeigt den lokalen Binance-Zugang sichtbar an: lokales Hixton-Passwort, API-Key/Secret, lokales Speichern im Windows-Anmeldedatenspeicher und eine private Kontovorprüfung. Ein gespeicherter Schlüssel allein erzeugt keine Orderfreigabe.

Der kontrollierte 1×50-USDC-Testbutton wird nur aktiv, wenn Schlüssel, frische Kontoprüfung und exakt 1×50-Einstellungen vorliegen. Seine Betätigung sendet nicht sofort eine Order; der Bot wartet auf das nächste neue gültige Signal. Die Runtime muss spätestens beim tatsächlichen Signal HEALTHY sein, andernfalls bleibt die Order gesperrt. Der 3×80-Livebutton wird erst nach abgeschlossenem/reconciliertem Test, Paper-Soak, frischer Kontoprüfung, mindestens 250 freien USDC und exakt 3×80 freigegeben. Beide Zustände stammen ausschließlich vom Server.

Dokumentationslinks zeigen auf 127027/Der-Hixton-von-GPT und den aktuellen Engineering-Branch.
