# 08 – UI/UX-Spezifikation

Status: CURRENT · 19.09.2026

Die lokale deutsche UI zeigt:
- System-/Paperstatus und aktuelle V6-ID;
- zehn USDC-Marktkarten und aktuelle Coin-Profile;
- Charts/Signale/Paper-Fills;
- offene Paperpositionen und Ereignisse;
- Datenqualität;
- System-/Runtime-Logs;
- Backtests: gemeinsames Portfolio, 10×250 isoliert und Einzelcoin.

Backtests besitzen keine V1/V2/V3-Auswahl mehr. Nur aktuelle V6 ist auswählbar. Die Anzeige unterscheidet Positionszyklen und Slot-Trades.

Der Einstellungsbereich zeigt den lokalen Binance-Zugang sichtbar an: lokales Hixton-Passwort, API-Key/Secret, lokales Speichern im Windows-Anmeldedatenspeicher und eine read-only Kontovorprüfung. Produktiver Livehandel und der 50-USDC-Test bleiben über Serverflags deaktiviert, solange die jeweilige Freigabe fehlt. Ein gespeicherter Schlüssel allein kann keine Orderfreigabe erzeugen; das Backend bleibt fail-closed.

Dokumentationslinks zeigen auf 127027/Der-Hixton-von-GPT und den aktuellen Engineering-Branch.
