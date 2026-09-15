# Der Hixton Trading Bot

## Aktuell: Anwendung 0.4.9 / DMS 1.14.0

**Neuer Verbesserungsversuch [V9](backtests/v9/README.md):** Zehn gemeinsame
Portfolio-Varianten getestet, 28 Portfolio- und 80 Einzelrechnungen. Trailing4
erhöht Gesamt-Baseline auf 265,59 USDC / 123 Trades, verliert aber unter Stress
und im späteren Prüfzeitraum. Auch ohne Risikohalt keine Erholung auf 700.
Deshalb keine Aktivierung; V6-Paper unverändert. 335 Python-Tests / ein Skip,
Ruff und mypy bestanden. V9 ist ein Forschungsbericht, kein neuer UI-Handelsmodus.

**Slot-Nachprüfung:** 3×80 verarbeitet alle zehn Märkte; 431 von 473
Kaufkandidaten scheitern am historischen Risikohalt, nur vier an vollen Slots.
Auch 6×80 und 9×80 getestet. Ein Diagnoselauf ohne Halt liefert zwar 197 Trades,
aber Verlust und 54,28 % Drawdown: keine Aktivierung. Echter Paper-Replay mit
Restart ergibt exakt dieselben 28 Fills und 203,72 USDC wie der Portfolio-Test.
UI zeigt jetzt Slotbelegung und Blockiergründe. [Details in DMS 18](DMS/18_BACKTEST_STATUS_UND_ERGEBNISFORMAT.md).

**Prüfung 15.09.2026:** Eine zentrale Regelbasis für alle Prüfsichten in
[DMS 06](DMS/06_BACKTEST_UND_VALIDIERUNG.md) präzisiert. Gespeicherte Backtests
werden jetzt mit aktivem Code, Regeln, Kosten und Portfolio-Budget abgeglichen;
Codeänderungen erfordern vor neuen Läufen einen Neustart. Laptop neu gestartet,
Paper unverändert 3×80 USDC. Neue normale Läufe: Portfolio **203,72 USDC / 14
Abschlüsse / 20,83 % Drawdown**, isoliert 10×250 **4.004,18 USDC**; Fenster
24.03.2024–15.09.2026. Unterschiedliche Kontomodelle, nicht verschiedene
Coin-Strategien. Alter USDT-Portfolio-Endwert 733,31 exakt nachgerechnet.
333 Python-Tests / ein Skip, 21 UI-Tests und Build bestanden. Details und
Nachweisgrenzen: [DMS 18](DMS/18_BACKTEST_STATUS_UND_ERGEBNISFORMAT.md).
Kein Echtgeldstart, keine neue profitable Strategie behauptet.

**Forschung 14.09.2026:** [V8-Schwachstellenstudie](backtests/v8/README.md) mit
88 Einzel- und acht 3×80-Rechnungen abgeschlossen. Verbesserungen bei AVAX/DOT
reichen im späteren Prüfzeitraum und gemeinsamen Portfolio nicht zur Übernahme.
Aktiv bleibt V6; kein Echtgeldauftrag. 304 Python-Tests bestanden / ein Skip.

DEC-055: Eine gemeinsame Handelslogik bleibt das Ziel für Historie, Paper und echte Ausführung. Coin-Profile und `TradePolicyGate` sind gemeinsam; die Prioritätsfunktion ist jetzt ebenfalls zentral statt dreifach formuliert. Die getrennten Simulations-/Ausführungsabläufe sind noch keine vollständig einheitliche Engine. Kein Coin-Tuning, kein Kontoreset. Neue Berichte halten zusätzlich Python-Quelltext-Hash (auch für uncommittete Änderungen) und die Grenze „historische Simulation, keine Binance-Ausführungsabnahme“ fest. Ein Patch erfordert neue Tests; alte Gewinne werden weder überschrieben noch zu einer Zukunftsprognose.

Einmaltest-Laufzeit nun an den Supervisor angeschlossen (alle zwei Sekunden dieselben analysierten Punkte), ohne automatische Scharfschaltung. Ein eigener dauerhafter Ausgangsbestand und tatsächliche Fills ermöglichen einen exakten Saldovergleich einschließlich BNB-Gebühren und unveränderter Altbestände. Das ist **noch keine vollständige Fremdorder-/Restmengen-/Produktivabnahme**. Der 50-USDC-Endpunkt bleibt HTTP 409; der reale Versand ist zusätzlich direkt vor Submit gesperrt. Kein gestarteter Test, keine Livefreigabe. Die konkrete Restarbeit steht oben in [DMS 20](DMS/20_BETRIEBSRUNBOOK.md).

Prüfstand: 292 Python-Tests bestanden, ein optionaler Vault-Test übersprungen; 19 UI-Tests, Ruff, mypy (52 Quelldateien), TypeScript und Produktionsbuild bestanden. Zehn Coin-Durchläufe vergleichen Paper-Entscheidungen mit dem echten Adaptercode an **synthetischen Binance-Antworten**: genau ein 50-USDC-BUY, danach SELL trotz Entry-aus, Abschluss erst nach exaktem Kontovergleich. Kein externer Binance-/Testnet-Auftrag ist damit behauptet.

### Weiter gültig: sichtbarer Betrieb seit 0.4.8 / DMS 1.13.0

**Sichtbarer Betrieb (DEC-054):** `Startbot.bat` startet den lokal installierten Stand in einer sichtbaren Konsole und öffnet die Oberfläche. Eine identifizierte frühere Instanz derselben Installation wird geordnet beendet; erst nach ihrem tatsächlichen Prozessende startet die neue. Kein automatischer GitHub-Download beim Start, kein Abschießen fremder Portbenutzer. **Terminal schließen oder letzten Bot-Tab schließen = Bot aus.** Ein Tab-Neuladen hat 5 Sekunden Schonfrist; bei Verbindungsabbrüchen kommt die WebSocket-Erkennungszeit hinzu. Nach erkannter Stoppanforderung endet der Prozess spätestens nach 15 Sekunden, nötigenfalls durch Selbstbeendigung. Vor der ersten UI-Verbindung startet kein Paper-Handel; ohne Oberfläche beendet sich der Starter nach 60 Sekunden. Minimieren/Tabwechsel allein stoppen nicht. `--no-browser` unterdrückt nur das automatische Öffnen, erlaubt keinen unsichtbaren Dauerbetrieb.

**Offene Binance-Positionen werden beim Beenden nicht verkauft und danach nicht mehr überwacht.** Ein späteres Livekonto benötigt deshalb weiterhin vollständige Neustart-/Order-Reconciliation. Diese Änderung gibt keinen Echtgeldtest frei. Die Kontovorprüfung zeigt jetzt deaktivierte/ungeklärte Rechte getrennt und nennt blockierende Altbestände; keine Bestände allein wegen einer Fehlermeldung verkaufen. Code-Abnahme 0.4.8: 271 Python-Tests, ein optionaler Vault-Test übersprungen; 19 UI-Tests, Ruff, mypy, TypeScript und Bundle-Build bestanden. Tatsächlicher Laptop-Prüfstand wird in DMS 18 separat festgehalten.

**Laptop-Abnahme 09.09.2026, 19:15–19:20 Europe/Berlin:** Code `a84f956` im tatsächlichen Desktop-Projekt installiert. Neustart ersetzt die alte eigene Instanz; Konsole beendet / letzter Bot-Tab geschlossen beendet den Server. Zwei Tabs und Reload geprüft. Danach Port 8765 frei, kein weiterlaufender Bot. Alle elf Paper-Tabellen identisch zum vorherigen Backup, keine Kontorücksetzung. Vor dem Abschalttest HEALTHY / PAPER / LIVE_DISABLED. Details und Grenzen in [DMS 18](DMS/18_BACKTEST_STATUS_UND_ERGEBNISFORMAT.md).

### Vorherige Laptop-Auslieferung 0.4.7

Am 09.09.2026 um 08:19 Europe/Berlin wurde **die tatsächliche Laptop-Installation** in `C:\Users\andre\OneDrive\Desktop\Der Hixton Indikator traiding BOT` auf Code `bc0b121` aktualisiert und über ihre vorhandene `Startbot.bat` neu gestartet. Geprüft: Anwendung 0.4.7, V6-USDC `d57f88ec2e5f`, HEALTHY, zehn USDC-Märkte, Binance-Stream verbunden, getrenntes Paperkonto mit 250 USDC und 3×80. Alle 50 Chartkombinationen liefern Daten. Historische USDT-Berichte und das vollständige alte Konto bleiben unverändert erhalten; sie sind keine USDC-Ergebnisse. Deployment-/Sicherungsnachweis: [DMS 18](DMS/18_BACKTEST_STATUS_UND_ERGEBNISFORMAT.md). Ergebnisse und Grenzen: [USDC-Prüfstand V7](backtests/v7/README.md).

Der geplante Einmaltest verwendet **50 USDC**, wartet nach dem Benutzerklick auf genau ein neues qualifiziertes Signal und soll dessen Coin-Regeln bis zum Ausstieg ausführen; Paper bleibt unabhängig aktiv. **Noch nicht startbereit:** Orderadapter/Controller sind offline geprüft, aber nicht mit einem produktiven Runtime-/Bestandsreconciler verbunden. Der Button prüft Voraussetzungen, HTTP 409 verhindert Echtgeld. Ein grüner Trend ist kein neuer Kaufauftrag. Kein echter Testtrade und keine 24/7-Livefreigabe. Verbindlicher Übergabe-/Restarbeitsstand: [Betriebsrunbook](DMS/20_BETRIEBSRUNBOOK.md).

## Weiterhin gültige Bedienung seit 0.4.5

Einstellungen: **Handel → Binance verbinden → Livehandel**. Slots von 1 bis 10 und USDC je Trade in 1-USDC-Schritten; das gewählte Positionsbudget ist Slots × Betrag, ohne feste 240-USDC-Grenze. Ein Klick auf „Übernehmen“ speichert. Kein Kontoreset, Guthabenauffüllen oder automatischer Echtgeldstart; verfügbare Mittel und Risikogates bleiben maßgeblich. Bestehende Positionen werden bei Änderungen nicht umgebucht.

Binance-Fehler `-1100` der Marktfilterabfrage korrigiert: Die Zehn-Coin-Liste wird ohne JSON-Leerzeichen gesendet. Öffentlich ohne Schlüssel reproduziert: vorher HTTP 400/-1100, korrigiert HTTP 200 mit zehn Symbolen. Live-Schalter markieren den bestätigten Serverzustand; der ausdrücklich beschriftete 50-USDC-Einmaltest braucht kein zusätzliches Häkchen und aktiviert keinen Dauerbetrieb.

Unter „Binance verbinden“ zuerst das bereits eingerichtete lokale Hixton-Passwort verwenden bzw. beim ersten Mal eines festlegen. Rückmeldung steht direkt am Passwortfeld. Erst nach bestätigter Sitzung werden API-Key/Secret freigegeben; speichern und Verbindung prüfen. Vorhandene Passwörter werden nicht zurückgesetzt. Details: [Betriebsrunbook](DMS/20_BETRIEBSRUNBOOK.md).

**Echtgeld noch nicht ausführbar:** Live-Steuerung und die Vorbereitung des einmaligen 50-USDC-Tests sind sichtbar. Der Orderadapter ist ab 0.4.9 an die gesperrte Laufzeit angebunden; vollständiger produktiver Vorversand-/Restmengen-/Kontoabgleich und externe Abnahme fehlen weiterhin. Sie werden nicht durch UI-Vereinfachung freigegeben. Paper nutzt echte Marktzeit und simuliertes Geld; gemeinsame Handelsparameter, getrennte Konten/Fills.

Ein normaler Doppelklick auf `Startbot.bat` setzt **nichts** zurück. Der nur ausdrücklich beauftragte Offline-Neuanfang ist unter [DMS 20](DMS/20_BETRIEBSRUNBOOK.md) dokumentiert. Nach einem frischen Start sind zunächst drei Slots frei: Es wird auf neue qualifizierte Signale gewartet, nicht in alte grüne Trends hineingekauft.

Der Hixton verwendet eine gemeinsame Strategieengine für Backtest und Paper. Der neue Code nutzt V6-USDC `HIXTON-V6-COIN-PAPER-1-d57f88ec2e5f`; die Parameter-/Policy-Sätze entsprechen dem historischen V6-USDT-Profil `9734f240e873`. Andere Handelspaare können andere Signale und Ergebnisse erzeugen. Echte Live-Orders bleiben technisch deaktiviert.

Zentrale Projektablage: `https://github.com/127027/Der-Hixton`

## Schnellstart unter Windows

Historischer Prüfstand 06.09.2026: V6 startete mit 250 **USDT**, drei 80-USDT-Slots und 10 USDT Anfangsreserve. Diese Geschichte wird nicht in USDC umetikettiert. Eine neue USDC-Installation führt ein getrenntes Modellkonto mit 250 USDC/3×80. Der [alte V6-Vergleich](backtests/v6/README.md) ist USDT-Evidenz. **Paper-Experiment, nicht nachgewiesen optimal und nicht live-reif.**

Im Repository existiert genau ein menschlicher Programmstarter:

```text
Startbot.bat
```

Ein Doppelklick erstellt bei Bedarf die lokale `.venv`, installiert ausschließlich die gepinnten Python-Laufzeitabhängigkeiten und startet Paper-Bot plus UI auf `http://127.0.0.1:8765/`. Die Anwendung besitzt intern weiterhin genau einen technischen Einstiegspunkt: `src/main.py`.

Der erste Start lädt bis zu drei Jahre verfügbare `1h`-Historie plus 400 Warm-up-Bars. Sieben USDC-Märkte besitzen im untersuchten Fenster weniger Historie; gemeinsamer Start und tatsächlicher Testzeitraum werden anhand realer Daten bestimmt, nicht aufgefüllt. Währenddessen bleibt die UI sichtbar und zeigt `STARTING` oder `DEGRADED`. Historische Signale werden beim Start niemals nachgekauft. `1m` in der Zeitraumwahl bedeutet **ein Monat**, nicht eine Minutenkerze.

## Was die Anwendung enthält

- Binance Spot für BTC, ETH, BNB, SOL, XRP, ADA, LINK, AVAX, DOT und DOGE gegen USDC; USDT-Archive bleiben getrennt.
- Versionierte V1- und V2-Strategien: VIDYA/CMO, SMA-Nachglättung, Wilder-ATR, Bänder und ausschließlich geschlossene `1h`-Bars.
- Vom Eigentümer bereitgestellte Pine-v6-Referenz mit eigenem Hash und Golden-Test; der kontrollierte V1→V2-Wechsel bewahrt das alte Ledger und startet einen neuen V2-Soak.
- Paper-Ledger mit 250 USDC für neue Konten (10 USDC Anfangsreserve), drei Slots à 80 USDC, Kostenmodell, Einstiegspause, Tagesverlustpause, Drawdown-Halt und restartfestem Soak. Bestehende USDT-Ledger bleiben unverändert.
- WebSocket-Livestream mit REST-Gap-Recovery, Startup-Prüfung und täglichem Audit um 00:05 UTC.
- Verpasste geschlossene Bars werden nach einem Neustart exakt einmal nachverarbeitet; Soak-Tage, Bars je Coin und abgeschlossene Trades werden dauerhaft in SQLite gezählt und in der bestehenden Systemkarte angezeigt.
- Lokale deutsche UI mit zehn Marktkarten, Positionen, Datenqualität und Candlestick-Charts für Heute, 1 Woche, 1 Monat, 1 Jahr und 3 Jahre.
- Kauf-/Verkaufsmarker aus der nativen `1h`-Strategie; 1 Jahr wird nur zur Anzeige auf `4h`, 3 Jahre auf `1d` aggregiert.
- Neue Backtests: gemeinsames 250-USDC-Spiegelportfolio mit gespeicherten Paper-Slots (Standard 3×80) und denselben 5-%-/20-%-Risikogates wie Paper; zehn isolierte Konten à 250 USDC oder ein einzelner Coin à 250 USDC, jeweils Baseline und Stress. Ältere USDT-Berichte behalten ihre Quote. Läufe ohne Portfolio-Gates heißen `strategy-only`.
- Backtest v2: dokumentierte Parametersuche, ältere Marktsegmente, Kosten-Stress und Nachbarprüfung; V2 ist für Paper freigegeben, wegen früher Risikohalts aber ausdrücklich nicht für Live.
- Backtest v3: der gewünschte Versuch, mehrere 80-USDC-Slots demselben Coin zu geben, ist getrennt dokumentiert und verworfen; die aktive V6 verteilt höchstens einen Slot je Coin.
- Backtest v4/v5: begrenzte Coin-Parametersuche, Verlustdiagnose, getrennte Trainings-/Prüffenster, Original-Pine-Kontrolle und explizit versionierte Forschungsregeln; keine automatische Paperumschaltung.
- V6: zehn explizite Coin-Profile, deterministische Zusatzfilter/Schlusskurs-Stops und Paper-/Backtest-/Restart-Parität; ausdrückliche Paper-Experimentfreigabe trotz dokumentierter Mehrfenster-Portfoliorückschritte.
- Ziel sind gute Signalquellen und effiziente Nutzung der eingestellten Slots innerhalb des gewählten Budgets und vorhandenen Cashs. 250→500 USDT und genannte Tradezahlen sind Beispiele, keine Optimierungsquoten; kein Overfitting und keine erzwungenen Trades.
- Unveränderliche Backtest-Runordner mit Manifest, Metriken, Trades, Equity und HTML-Bericht.
- Einstellungen: ungespeicherter Entwurf bleibt über Status-Polls erhalten, ein Übernehmen-Klick und Anzeige gespeicherter Werte; keine Kontoauffüllung oder Änderung bestehender Positionen.
- Live-Vorbereitung mit HMAC API-Key **und** Secret ausschließlich im Windows-Anmeldedatenspeicher des aktuellen Benutzers und PCs. Kein Export, keine Klartextdatei, kein lokaler Browserstorage. Separates Hixton-Passwort, 15-Minuten-Sitzung, genaue Origin-Prüfung, redigierte Fehler und eigener Vorbereitungs-Audit.
- Read-only Binance-Prüfung: Uhr, Rechte/IP-Freigabe, freie USDC/BNB, offene Orders, Fremdbestände und grundlegende Filter aller zehn Paare. Sie erzeugt keine Orders und ist kein Ausführungsnachweis. Erster geplanter Echtgeldversuch höchstens 1×50, spätere Erhöhungen separat.

## Sichere Grenzen

- `LIVE_DISABLED` ist permanent sichtbar. Es existiert noch kein freigeschalteter privater Binance-Orderadapter.
- Ein positiver Backtest ist keine Gewinngarantie.
- Live benötigt unter anderem 30 bis höchstens 90 Tage Paper-Soak gemäß DMS, mindestens 720 neue Bars je Coin, 20 abgeschlossene Papertrades, sichtbare lokale P1/P2-Alarme, Backup/Restore, einen dedizierten Bot-Account und schriftliche Eigentümerfreigabe. Telegram ist nicht erforderlich.
- Secrets, Datenbanken, automatisch geladene `1h`-Marktdaten, Logs, `.venv` und `node_modules` werden nicht in Git gespeichert.

## Kommandozeile

Alle Befehle laufen über denselben Einstieg:

```powershell
py -3 src/main.py status
py -3 src/main.py data sync --symbol ALL
py -3 src/main.py data audit --symbol ALL
py -3 src/main.py backtest all
py -3 src/main.py backtest single --symbol ETHUSDC
py -3 src/main.py backtest portfolio
py -3 src/main.py backtest all --strategy v2
py -3 src/main.py backtest single --strategy v2 --symbol ETHUSDC
py -3 src/main.py backtest portfolio --strategy v2
py -3 src/main.py backtest portfolio --strategy v3
py -3 src/main.py backtest research --output backtests/v4/runs/mein-neuer-review/research.json
py -3 src/main.py backtest research --study v5 --output backtests/v5/runs/mein-neuer-review/research.json
py -3 src/main.py backtest all --strategy v6
py -3 src/main.py backtest portfolio --strategy v6
py -3 src/main.py backtest research --study v6 --output backtests/v6/runs/mein-neuer-review/research.json
py -3 src/main.py start --no-browser
py -3 src/main.py live
```

Ohne `--strategy` verwendet ein Backtest automatisch die konfigurierte aktive Paperstrategie V6. V1 und V3 müssen für historische beziehungsweise verworfene Vergleichsläufe ausdrücklich gewählt werden.

`live` beendet sich absichtlich mit einer Sperrmeldung.

`backtest research` verwendet standardmäßig den unveränderten V4-Versuch mit 24 Parametervarianten je Coin. `--study v5` untersucht bis zu 36 Kombinationen je Coin aus drei Hixton-Parameterbasen und zwölf klar beschriebenen Filtern/Stops. Auswahl ausschließlich im Training, danach exakte Einzel-/Portfoliovergleiche. V5 benötigt zusätzlich den im Bericht angegebenen älteren lokalen Datensatz. Beide Studien ändern weder Paperstrategie noch Kontostand; vorhandene Ergebnisdateien werden nicht überschrieben. Bereits betrachtete Prüfdaten werden ausdrücklich nicht als unangetasteter Holdout bezeichnet.

Paper verwendet seit der Ausführungskorrektur `NEXT_BAR_OPEN_V1`: Signal ausschließlich auf geschlossener Kerze, modellierter Fill mit dem tatsächlichen nächsten Kerzen-Open plus Kosten. Der echte Verarbeitungszeitpunkt wird zusätzlich gespeichert. Das ist ein deterministischer Ausführungssimulator, noch kein Nachweis realer Binance-Fills oder realistisch gemessener Orderlatenz. Alte Ereignisse bleiben als Legacy erhalten; der technische Soak startet einmalig neu, Cash und Positionen bleiben bestehen.

Die Backtestseite besitzt die eindeutige Auswahl `V6 · Paper-Experiment / Coin-Mix`, `V2 · vorherige Referenz`, `V1 · Historie` oder `V3 · Mehrfachslot verworfen`, `Gemeinsames 3×80-Portfolio`, `10×250 isoliert` und jeden Einzelcoin. Version und Testart filtern gemeinsam: Nur der neueste passende Run steht direkt sichtbar, ältere Läufe sind eingeklappt. Diese Auswahl ändert niemals die aktive Paperstrategie.

## Entwicklung und Prüfung

```powershell
py -3 -m pip install -e ".[dev]"
py -3 -m pytest -q
py -3 -m ruff check .
py -3 -m mypy src
cd ui
npm.cmd ci
npm.cmd run check
npm.cmd run build
```

UI-Abhängigkeiten sind in `ui/package-lock.json` festgeschrieben. Der gebaute, vom Python-Service ausgelieferte Stand liegt ausschließlich unter `src/hixton/ui/static/`.

## Sauberkeitsregeln

Ordnung und kleine, eindeutige Verantwortungsbereiche sind verbindliche Produktanforderungen:

- Im Hauptordner liegen nur Projektsteuerdateien, `README.md` und die eine `Startbot.bat`.
- Keine Kopien wie `bot_final.py`, `bot_neu.py`, `start_2.bat` oder Coin-spezifische Starter.
- Eine fachliche Backteständerung erhält `backtests/v2`, `v3` usw.; Wiederholungen derselben Methodik erhalten nur eine neue Run-ID unter `backtests/v1/runs/`.
- Laufzeitdaten gehören ausschließlich in ignorierte Ordner wie `data/`, `runtime/`, `logs/` und `backups/`.
- Generierte UI-Dateien liegen nur im vorgesehenen Buildziel; `node_modules` und temporäre Buildreste werden nie eingecheckt.
- Veraltete Dateien werden nicht als `alt`, `old` oder `backup` im Repository geparkt. Git bewahrt die Historie.
- Jede neue Datei benötigt genau eine Verantwortung, den richtigen Zielordner und einen Test oder eine dokumentierte Begründung.
- Vor jedem Commit laufen Python-Tests, Ruff, Mypy, TypeScript-Check und UI-Build.

## Maßgebliche Dokumentation

1. [`DMS/00_DOKUMENTENLENKUNG_UND_START.md`](DMS/00_DOKUMENTENLENKUNG_UND_START.md)
2. [`DMS/03_STRATEGIE_HIXTON.md`](DMS/03_STRATEGIE_HIXTON.md)
3. [`DMS/12_TESTS_ABNAHMEKRITERIEN.md`](DMS/12_TESTS_ABNAHMEKRITERIEN.md)
4. [`DMS/14_BUILD_PLAN_UND_DEFINITION_OF_DONE.md`](DMS/14_BUILD_PLAN_UND_DEFINITION_OF_DONE.md)
5. [`DMS/20_BETRIEBSRUNBOOK.md`](DMS/20_BETRIEBSRUNBOOK.md)
6. [`DMS/23_ORDNERSTRUKTUR_UND_EINSTIEGSPUNKT.md`](DMS/23_ORDNERSTRUKTUR_UND_EINSTIEGSPUNKT.md)
