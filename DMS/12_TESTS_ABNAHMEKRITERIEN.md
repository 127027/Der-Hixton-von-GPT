# 12 – Tests und Abnahmekriterien

## Prüfstand 0.4.9 / DEC-055

292 Python-Tests bestanden, ein opt-in Windows-Vault-Test übersprungen; 19 UI-Tests, Ruff, mypy (52 Quelldateien), TypeScript und Produktionsbuild bestanden. Zusätzliche 21 Tests: zehn Coin-Durchläufe vergleichen Paperentscheidungen mit Einmaltest und realem Adapterparser auf synthetischen Antworten; genau ein 50-USDC-Kauf und zugehöriger Verkauf trotz Entry-aus. Timeout-/Restart-Abgleich ohne zweiten Kauf; unveränderliche Baseline; kein Netzwerkzugriff beim inaktiven/gestoppten Lifecycle; Konto-/Saldo-/OpenOrder-/Stale-/Locked-Fehler; BNB-Gebühren ohne erfundenen Netto-PnL; veränderliche Kontosnapshots; Quelltext-Hash reagiert auf uncommittete Pythonänderungen. Die bestehende historische Portfolio-/Paper-Paritätsregression besteht weiterhin.

Die Start-API muss weiterhin HTTP 409 liefern, obwohl `runtime_connected=true` ist: Verbindung ist nicht Produktionsfreigabe. Keine echten oder Testnet-Orders in dieser Suite. Nur nachgewiesene Teile als bestanden markieren; tatsächlicher Vorversand-Guard, Restmengen/Fremdorderhistorie und externe Betriebsabnahme bleiben offen gemäß DMS 20. Alte Berichte bleiben unverändert; neue Manifeste und HTML-/UI-Hinweise trennen historische Berechnung ausdrücklich von Ausführungsabnahme und Zukunftsertrag.

Schnittstellenreferenz für lesenden Konto-/Orderabgleich: [Binance Account API](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/account), geprüft am 09.09.2026. Dokumentation ist kein Konto- oder Ausführungsnachweis.

## Prüfstand 0.4.8 / DEC-054

271 Python-Tests bestanden, ein optionaler Windows-Vault-Test übersprungen; 19 UI-Tests, Ruff, mypy (50 Quelldateien), TypeScript und Produktionsbuild bestanden. Neue Tests: kein Handel vor UI, abgewiesener Fremd-Origin/fehlendes oder veraltetes Shutdown-Token, Mehrtab-/Reload-Schonfrist, Terminalverlust und Fehler der Terminalüberwachung, expliziter Stop, Schutz fremder Portbenutzer und Metadaten einer Nachfolgeinstanz. UI prüft pagehide/BFCache, Stop ohne Auto-Reconnect, Reload bei Prozesswechsel und sichtbaren Verbindungsverlust. Kontovorprüfung unterscheidet false/unbekannt und benennt Fremdbestände, ohne Gates zu lockern. Realer Laptop-Start-/Stopp-Nachweis wird getrennt in DMS 18 geführt; kein Echtgeldauftrag gehört zu diesen Tests.

## Prüfstand 0.4.7 / DEC-053 – keine Echtgeld-Abnahme

Deployment-Nachtrag 09.09.2026 / DMS 1.12.1: Python-Suite auch im tatsächlichen Laptop-Projekt erfolgreich wiederholt, 262 bestanden und ein opt-in Windows-Vault-Test übersprungen. Laufender 0.4.7-USDC-Bot HEALTHY, zehn Märkte, 50/50 Chartkombinationen; Browserübersicht/Einstellungen/Chart geprüft, keine erfassten JavaScript-Warnungen/-Fehler. Erhaltene alte Paperdaten und lokale Schlüssel-/Passwortkonfiguration siehe DMS 18. Das ersetzt weder Binance-Ordertests noch einen abgenommenen echten Kontoreconciler.

Abschlussprüfung: **262 Python-Tests bestanden, 1 opt-in Windows-Vault-Test übersprungen; 16 UI-Tests bestanden; Ruff, Mypy (48 Quelldateien), TypeScript und Vite-Build bestanden.** Ein erster parallel zum Bundle-Build laufender Test wurde durch dessen temporär entfernten Assets-Ordner gestört; der vollständige sequenzielle Wiederholungslauf bestand. Kein Fehler wurde durch Entfernen eines Sicherheitstests umgangen.

Zusätzlich echte lokal gespeicherte USDC-Kerzen geprüft: gemeinsamer Warm-up-Start 07.03.2024 08:00 UTC, Ende 08.09.2026 06:00 UTC, je Markt 21.958 Bars; zehn von zehn Qualitätsprüfungen und letzte Indikatorberechnungen gültig. Der Handelsbericht beginnt erst nach 400 Warm-up-Bars, am 24.03.2024 00:00 UTC. Dies ist kein aktueller Kontocheck, kein Echtgeldlauf und kein neuer Profitabilitätsbeleg. Das alte USDT-Ledger wird beim versehentlichen Öffnen mit dem neuen PaperStore vor einer Schemaänderung abgewiesen.

Neue Offline-Regressionen: exaktes 50-USDC-Quote-Budget, keine USDT-/Kontoverwechslung, echter Antwortparser einschließlich BNB-Fee und gerundetem `quoteQty`, verlorenes ACK mit Wiederanlauf ohne zweiten POST, fehlende Filldetails, falsche Fremdfills/NaN, signierter POST-Body, feste HTTPS-Hosts/Endpunkte, redigierte Fehler ohne Retry, Ledger-Schemaerhalt, terminale Ergebnisse gegen konkurrierende Fehler geschützt, alle zehn USDC-Coin-Controller-Rundläufe und nicht durch abgelaufene Entry-Freigabe blockierter Ausgang.

Migrationsregressionen prüfen gemeinsame verfügbare Historie/400-Warm-up, blockierte interne/Endlücken, erhaltenen Vault-Namespace und richtige Quote alter Reports ohne Umschreiben. Produktiver automatischer Bestandsabgleich, Restmengen-/Filterausführung, Runtime-Hydration und Binance-Testnet-Nachweis bleiben offen. Grüner Mock-Test ist keine Kontoprüfung und keine Startfreigabe.

## Historie: Abnahme 0.4.6 / DEC-052 – USDC-Prüfstand, keine Live-Abnahme

Abschließende Arbeitskopie: **224 Python-Tests bestanden**, ein opt-in Vault-Test übersprungen; **16 UI-Tests**, Ruff, mypy, TypeScript und Produktionsbuild erfolgreich. Auf dem laufenden Laptop zusätzlich **50/50 Chartkombinationen** (zehn Coins × fünf Zeiträume) mit nichtleeren Daten, zehn valide Marktkarten und zehn letzte Signalzeiten geprüft. Die vorher dokumentierten 222 Tests beziehen sich auf den Stand vor den zwei CLI-Größenregressionen.

Ergänzter Spiegelnachweis: 384/384 Fills der produktiven Paper-Engine gegen aktuellen Drei-Jahres-USDT-Backtest exakt gleich (Signal-ID, Zeit, Preis, Menge, Gebühr), Equity-Differenz null. Ab realem Paper-Neustart null Signale/Fills und identischer 250-Kontostand. Alter 739,52-Run im identischen Zeitraum exakt reproduziert. CLI-Regressionen für gespeichertes 4×45 statt Config 3×80 sowie Configfallback ohne initialisiertes Konto. Ergebnisse DMS 18.

Regressionen für getrennte USDT-/USDC-Universen, unveränderte V6-Identität und Coin-Profile, gemischte/falsche Märkte, spätere Listings, Lücken, fehlende letzte Bars, Duplikate, falsche OHLCV, vorläufige Kerzen und zu wenig Warm-up. Beide kanonischen Backtest-Engines mit USDC, tatsächlich erzeugten synthetischen Fills, nichtnegativem Cash und expliziter Quote im Manifest geprüft. Offline-Gesamtlauf einschließlich zeitraumgleichem USDT-Kontrolllauf; bestehendes Konto und Kontroll-Datenbank bleiben unverändert. SQLite-Nur-Lesen verhindert Änderungen und legt keine fehlenden Datenbanken an. UI-Regression unterscheidet letzten Trendwechsel von einem ausgeführten Trade.

Markt-/Backtestergebnisse separat in DMS 18/V7; erfolgreiche Softwaretests sind keine Profit- oder Echtgeldfreigabe. Produktive Runtime-Migration und Live-Order-/Reconciliation-Abnahme bleiben offen.

## Abnahme 0.4.5 / DEC-051

207 Python-Tests bestanden, ein opt-in Vault-Test übersprungen; 15 UI-Tests, Ruff, mypy (45 Quelldateien), TypeScript und Produktionsbuild erfolgreich. Neue Regressionen: vollständige simulierte Read-only-Prüfkette mit kompakter Zehn-Coin-Liste ohne Key im öffentlichen Request; phasen-/codespezifische Fehler ohne Secret-/Rohtextleak; 250-/1000-USDT-Aufteilungen über API/UI, Neustartpersistenz ohne Cashmutation; Engine überschreitet vorhandenes Cash auch bei größerem Plan nicht. Ungültige Slots/NaN/Infinity/negative Beträge weiter abweisen.

UI-Harness prüft Live-aus → verweigertes Live-an ohne falsches Grün, ausschließlich hypothetisch bestätigtes Live-an, Auslaufen, Testzustand und unbekannten Status ohne Auswahl. Ein expliziter Klick sendet ausschließlich die feste 50-USDT-Einmalanforderung, niemals normales Live-enable. Bestehende globale Einmal-, Exit-, Replay- und Neustarttests bleiben erhalten. Öffentlicher echter Markttest: alter Request HTTP 400/-1100, kompakter Request HTTP 200 mit zehn Symbolen. **Kein authentifizierter Betreiber-Accountnachweis, kein Binance-Ordertest und keine Echtgeldfreigabe.** Ältere Prüfstände unten sind Historie.

## Abnahme 0.4.4 / DEC-050

201 Python-Tests und 13 UI-Tests; ein opt-in Vault-Test im Standardsatz übersprungen. Neue API-/Persistenzfälle 4×45, 5×40, 10×24 nach Neustart ohne Kontoveränderung; Engine eröffnet in einem kontrollierten Fünf-Signal-Fall genau vier 45-USDT-Positionen und blockiert die fünfte. Passwort-Einrichtung, erneutes Entsperren nach Prozessrestart, Fehler, Key-Speicherung, Fake-Kontovorprüfung und weiterhin verweigerter Live-Start geprüft.

UI-Tests führen die produktiven Formularcontroller in einem isolierten DOM-/Fetch-Harness aus: Submit/Enter-Pfad, Passwortfehler direkt am Feld, verifizierte Entsperrung, Keyspeichern, Kontoprüfung, Sitzung/Cookiefehler, gleichzeitige Anmeldung, Lock, Löschbestätigung, Testcheckbox, fehlende Echtgeldfreigabe, einfacher Übernehmen-Submit, Doppelstartschutz und Fehler-/Polling-Erhalt. Keine realen Zugangsdaten und keine echte Börsenorder. Sichtprüfung/ausgelieferter Stand siehe DMS 18.

Aktuell 0.4.3: **196 Python-Tests / ein opt-in Test übersprungen, sieben UI-Tests**. Neue Nachweise: ein gemeinsamer Speicherweg und Live-Lesequelle nach 1×50-Speicherung sowie Neustart; keine Konto-/Positions-/Soak-Veränderung; klare Ablehnung 4×80/5×80/Überbudget ohne Rückfall; gemeinsame Pause bei wartendem/offenem Fake-Test ohne Kauf, Verkauf oder erneutes Starten. UI-Modell prüft unmittelbare Entwurfsanzeige, Erfolgs-/Fehler-/Verwerfzustände und serverseitige Grenzwerte; genau ein Echtgeld-aus-Bedienelement, kein konkurrierender Live-Preview-Schreiber. Dies ist weiterhin keine echte Binance-Ausführungsabnahme.

Prüfstand 0.4.2: 25 neue Controller-Tests plus sieben zusätzliche API-Fälle, insgesamt 190 Python-Tests bestanden und ein opt-in Vault-Test übersprungen; vier UI-Tests. Geprüft sind globale Einmalberechtigung bei Konkurrenz, zehn Signale/richtige Rangfolge, bestehende Coin-Filter und XRP-Stop, 500/NaN/etc. zurückweisen, Restart/Timeout, fehlende veraltete/offene Bars, Entry-Stopp bei offener Position, regulärer Exit, unvollständiger Abgleich/Restmengen und Gebühren. API bleibt auch mit Key/Bestätigung gesperrt; keine Mutation des Paperkontos. Kein produktiver Runtime-, Binance-Testnet-, manueller Fremdbestands- oder Echtgeldbeleg. Die nachfolgenden Live-Abnahmen bleiben insoweit offen.

DEC-047, **noch offene Einmaltest-Abnahme**: genau ein globales 50-USDT-Einstiegsbudget bei zehn zeitgleichen Coin-Signalen; 500/80/NaN/Infinity/manipulierte Budgetwerte ablehnen; keine Erneuerung durch Doppelklick, konkurrierende Browser, Timeout, Restart, Teilfill, Nachkauf oder veränderte Paper-Settings. Nur nach Aktivierung entstandene frische qualifizierte Signale und tatsächliches eingefrorenes Coin-Profil verwenden. Vor dem Senden bestehende Preis-/Filter-/Saldo-/Risikoprüfungen bestehen; danach Original-Order/Fills/Gebühren gegen Binance und testzugehörige Bestände abgleichen. Ausstieg darf nur erhaltene verfügbare Testmenge verkaufen. Endzustand bleibt über Neustart beendet; fremde Bestände/Dust und unbewertete Gebühren nicht als vollständig abgeglichen ausgeben. V6-Exitregeln einschließlich XRP-Schlusskurs-Stop und fehlender fester TP-/Trailing-Regeln wahrheitsgemäß nachweisen. Positive Simulationstests allein und ein einzelner echter Trade ersetzen weder sämtliche Coin-/Störfalltests noch die normale 24/7-Livefreigabe.

Ergänzung Anwendung 0.4.1: `tests/test_live_orders.py` enthält 21 isolierte Tests des noch nicht angeschlossenen Orderjournal-Kerns: atomarer Doppelstartschutz, unklare Antwort/Neustart ohne erneutes Senden, Teilfill-Deduplizierung, Gebührenwährungen und unveränderliche Auftrags-/Endzustände. Vollständige produktive Eigentums-/Budget-/Preis-/Filterprüfung und Börsen-Reconciliation werden damit **nicht** als bestanden markiert. Keine Änderung der Live-Gates durch Fake-Börsentests.

0.4.0 / DEC-046: `tests/test_live_preparation.py` prüft 1×50-Speicherung samt Neustart ohne Ledger-/Soak-Reset, NaN/Infinity/ungültige Werte, Origin-Prefix-Angriffe, Passwort/Sitzungsablauf/Rate-Limit, Secret-Nichtecho und -Nichtpersistenz in Audit, geschützte Key-Rotation/-Entfernung, Read-only-Requestsignatur/Allowlist, redigierte HTTP-/Timeoutfehler, Rechte/Fremdbestände/USDC/offene Orders, Konto-Vorcheck-Frische und zwingende Live-Sperre selbst bei gesundem Runtime-/Soak-Status. Opt-in-Windows-Vault-Test erzeugt nur einen einzigartigen künstlichen Datensatz und entfernt ihn vollständig. `npm --prefix ui test` prüft Entwurfszustand bei Polling, Abbruch, Erfolg und Speicherkonkurrenz ohne temporären Test-Build. Das ersetzt **keinen** Echtgeld-Order-, Binance-Testnet- oder Reconciliation-Nachweis.

UI 0.3.2: `tests/test_ui_api.py` prüft getrennte Versions-/Modus-/Coinfilter, Manifestchronologie trotz abweichender Dateizeiten, mehr als 25 fremde Testarten vor dem Filter, ungültige Auswahl und Erhaltung aller Runordner. UI enthält keine hartcodierte V1-Aktivkennung oder Dokumentationslinks auf den abgelösten `main`-Stand. Bestehende Paper-/Backtestparität bleibt Pflicht.

DEC-045: `tests/test_paper_maintenance.py` prüft Vollarchiv/Hash/Integrität, ausschließlich gelöschte Paperdaten bei erhaltenen Marktdaten, neuen 250-USDT-Account, fehlende Bestätigung, belegten Port, vorhandenes/außerhalb liegendes Archiv, unbekanntes Schema, atomaren Rollback und unveränderte normale Neustarts. Unfreigegebene Profile bleiben weiterhin technisch gesperrt; V6 besitzt nur die Eigentümer-Paperfreigabe.

DEC-043/044: `tests/test_coin_profiles.py` prüft vollständige Profile, strikte Config, tatsächliche Paper-/Portfolio-Fills und Equity einschließlich mehrerer Neustarts, Batch-/Einzel-/Chart-Parität, XRP-Stop am Folge-Open mit eingefrorenem Entry-ATR, vollständige API-Profilanzeige, Migrations-Dust-/Cash-/Risikohalt-Erhaltung und keine künstliche Auffüllung bestehender Konten. Technische Parität ersetzt weder Mehrfensterrobustheit noch Paper-Soak oder Live-Gate.

## Testebenen

1. Unit-Tests für Mathematik, Zustände, Rundung und Gebühren.
2. Golden-Tests gegen unabhängig berechnete Werte aus `HIXTON-SPEC-1.0` für V1 und gegen die gehashte Eigentümer-Pine-Semantik für V2;
3. Integrationsprüfungen für Datenprovider, DB und Börsenadapter.
4. Replay-/Backtests mit historischen Bars.
5. End-to-End-Tests der UI bis Ledger/Report.
6. Failure-Injection für Netzwerk, Restart, Teilfill und stale Daten.
7. Paper-Soak-Test über ausreichend viele reale Barwechsel.
8. Sicherheits-, Backup- und Restore-Tests.

## Kritische Strategieprüfungen

- identische VIDYA-/Bandwerte innerhalb definierter Toleranz;
- null Signalabweichungen gegen Spezifikations-Golden-Daten;
- Signal erst nach Bar-Close;
- kein Signal auf Warm-up-/`na`-Bars;
- genau ein Flip-Event pro tatsächlichem Zustandswechsel;
- kein Pyramiding bei wiederholtem Up-Zustand;
- Down-Flip schließt Long im Long-only-Modus;
- Batch und inkrementelles Replay ergeben identische Resultate;
- Neustart an beliebiger Bar ändert Folgesignale nicht.

## Kritische Datenprüfungen

- drei Jahre plus Warm-up für alle zehn Paare;
- Lücke wird erkannt und blockiert das betroffene Symbol;
- Duplikat mit abweichenden Werten wird nicht still akzeptiert;
- offene Kerze bleibt vorläufig;
- Reconnect lädt fehlende Bars nach;
- Mitternachtsjob ist idempotent;
- Datenrevision markiert abhängige Backtests als stale;
- Zeitumstellung Europe/Berlin verändert UTC-Strategie nicht;
- Heute/1W/1M/1J/3J liefern korrekte Grenzen.

## Backtestprüfungen

- Standard-Batch startet zehn isolierte Tests mit exakt 250 USDT je Coin;
- Einzelmodus startet genau den gewählten Coin, zum Beispiel ETH, mit 250 USDT;
- Batchvergleich summiert 2.500 USDT nur rechnerisch und vermischt die zehn Cashbestände nicht;
- Paper-/Live-Spiegellauf startet neu mit 250 USDT und höchstens drei Slots à 80 USDT;
- bei mehr Signalen als Slots ist die freigegebene Priorisierung deterministisch;
- Next-bar-Fill ohne Look-ahead;
- Gebühren/Slippage auf Ein- und Ausstieg korrekt;
- Tick-/Step-Rundung und Mindestnotional korrekt;
- offene Endposition wird klar mark-to-market bewertet und nicht als heimlicher Fill geschlossen;
- Metriken gegen kleine handgerechnete Fixtures;
- identischer Run erzeugt identische Hashes und Ergebnisse;
- schlechter Coin und Verlusttrade bleiben im Bericht;
- Zielstatus basiert auf Netto-, nicht Bruttoergebnis.

V5-Forschungsnachweise in `tests/test_trade_policy.py`: Identitätsregel verändert weder Einzel- noch Portfolioergebnis; gefilterte Käufe werden nicht auf späteren grünen Bars nachgeholt; Stops reagieren nur auf Schlusskurse, nicht auf Dochte; Steigung verwendet ausschließlich vergangene VIDYA-Werte; zukünftige Kerzen verändern keine vergangenen Fills; Float-Screen/Decimal-Finalist sowie Einzel-/Portfolioentscheidung stimmen auf kontrollierten Fixtures überein. Nichttriviale Forschungsregeln benötigen ausdrücklich eine `HIXTON-V5-…`-Kennung und dürfen sich nicht als aktive V2 ausgeben. Diese Tests ersetzen keinen Paper-Nachweis der Forschungsregeln.

## Execution-/Recovery-Prüfungen

- Retry nach Timeout erzeugt keine Doppelorder;
- unbekannter Submit-Status führt zu Reconciliation;
- Teilfills ergeben korrekte Position/Gebühr;
- Restart zwischen Submit und Response wird sicher aufgelöst;
- Fremdorder/Saldoabweichung stoppt Live-Entries;
- Not-Aus verhindert neue Entries;
- manuelles „alle schließen“ kann nicht versehentlich durch eine einfache Navigation ausgelöst werden;
- Rate-Limit wird eingehalten;
- stale Feed stoppt Entry.

## UI-Abnahme

- alle zehn Karten sichtbar und korrekt zuordenbar;
- Modus und Health permanent sichtbar;
- Chartzeiträume entsprechen definierter Semantik;
- vorläufige Kerze klar markiert;
- Signal- und Fillmarker sind unterscheidbar;
- Backtest zeigt Zeitraum, Kosten und Hashes;
- „unbekannt“ wird nicht als 0 dargestellt;
- Fehlerzustände bieten klare nächste Schritte;
- Einstellungen zeigen Diff und erzeugen Audit;
- Tastaturbedienung, Kontrast und responsive Kernansicht werden geprüft.

## Nichtfunktionale Kriterien

Verbindliche Grenzwerte auf der dokumentierten Referenzinstallation mit zehn Märkten:

- UI-/Lese-API p95 höchstens 2 Sekunden; sie darf den Tradingloop nie synchron blockieren;
- Verarbeitung eines 1h-Bar-Close für alle zehn Märkte einschließlich Persistenz höchstens 60 Sekunden;
- ein kontrollierter Abbruch von Backtest/Datenimport wird spätestens nach 5 Sekunden quittiert und hinterlässt einen eindeutigen Status;
- 3-Jahres-Chart p95 höchstens 3 Sekunden nach verfügbarer lokaler Historie und serverseitiger Aggregation;
- Retention hält normale Betriebslogs bei höchstens 90 Tagen, ohne Audit-/Trade-/Backtestnachweise zu löschen;
- Restore ist in einer sauberen Umgebung reproduzierbar und wird vor Live sowie vierteljährlich nachgewiesen.

## Automatisierter Nachweisstand vom 02.09.2026

- `pytest`: 68 von 68 Tests bestanden, einschließlich versionierter Ledger-Migration, Fail-closed-Strategiekonflikt, Mehrfachslot-Allokation, Aktivierungssperre der verworfenen V3 und Websocket-Health-Recovery ohne Verdecken fremder Fehler;
- Ruff: keine Lint-/Sauberkeitsabweichung;
- mypy: keine Typfehler in 34 Source-Dateien;
- TypeScript: `tsc --noEmit` bestanden;
- npm Audit: 0 bekannte Schwachstellen in 67 Abhängigkeiten;
- Datenqualität: zehn von zehn Märkten mit drei Jahren plus 400 Warm-up-Bars ohne Lücke;
- Backtest: 10×250-USDT-Batch, ETH-Einzelmodus und gemeinsames 3×80-USDT-Portfolio einschließlich risikogleichem Paper-/Live-Spiegel ausgeführt;
- Reproduktion: Metrik-, Trade- und Equity-Dateien bytegleich;
- Browsermatrix: 10 Coins × 5 Zeiträume ohne fehlgeschlagene Chartabfrage geprüft;
- responsive Kernansicht, System-/Log-, Backtest-, Qualitäts-, Einstellungs- und Dokumentationsseite lokal abgenommen.

Diese Nachweise schließen Gate A und Gate B für V1 und V2. Restart-Checkpoint, Nachverarbeitung verpasster Bars, kontrollierter V1→V2-Wechsel, Strategiekonflikt-Sperre und persistente Soak-Zähler sind automatisiert geprüft. Sie ersetzen nicht die noch offenen Gate-C-Nachweise für Backup/Restore, vollständige Failure-Injection und den real ablaufenden V2-Paper-Soak. V3 ist nach dem negativen Mehrfachslot-Risikospiegel verworfen.

## Freigabegates

### Gate A – DMS/Strategie eingefroren

- `HIXTON-SPEC-1.0` ist als normative Referenz vorhanden;
- Formeln, Parameter, `1h`-Timeframe, Warm-up, Initialzustand, Cross- und Fillregeln sind verbindlich;
- Kosten-, Kapital-, Slot- und Long-only-Regeln sind synchron dokumentiert;
- keine kritische Strategieentscheidung steht auf `OFFEN`;
- DMS-Version/Tag und Changelog sind gesetzt.

V1 bleibt durch seine eigene eingefrorene Spezifikation reproduzierbar. Die später vom Eigentümer bereitgestellte Pine-v6-Datei wird zusätzlich für V2 gehasht und per unabhängiger Golden-Implementierung geprüft; sie deutet V1 nicht rückwirkend um.

### Gate B – Backtest valide

- Strategy Engine besteht Golden- und Zustandsmaschinentests ohne Abweichung zur Spezifikation;
- alle zehn Einzeltests und Portfolio beendet;
- Daten/Kosten/Manifest vollständig;
- Reproduktionslauf identisch;
- Ergebnisse fachlich geprüft, einschließlich Verfehlungen.

### Gate C – Paper bereit

- alle Integrations-, UI- und Failure-Tests grün;
- keine kritischen offenen Defekte;
- Monitoring in UI/strukturierten Logs und Backups aktiv;
- dedizierter Bot-Account/Subaccount ohne manuellen Handel vorbereitet.

### Gate D – Live bereit

- mindestens 30 Kalendertage, 720 geschlossene 1h-Bars je Symbol und 20 abgeschlossene Papertrades; bei zu wenigen Trades Verlängerung bis höchstens 90 Tage gemäß DEC-018;
- Börse/Account/Keys bestätigt;
- Reconciliation-, Not-Aus- und Restore-Test bestanden;
- Live-Risikolimits bestätigt;
- schriftliche Freigabe des Eigentümers.

## Definition „99 % dokumentiert“

Ergänzung 05.09.2026: 74 Python-Tests sowie Ruff, mypy (35 Quelldateien), TypeScript und UI-Produktionsbuild bestanden. `tests/test_runtime_parity.py` vergleicht echte Produktionsengines einschließlich Kurslücken, Mengenrundung/Dust, verschiedener Close-Millisekunden und geteilter Restart-Verarbeitung. Zusätzlich geprüft: fehlendes Folge-Open schreibt keinen Checkpoint, die UTC-Grenze innerhalb der ersten zwei Minuten, Fill-/Chart-Zeitraster, vorläufige Kerze ohne neues Signal, Preisfrische und einmaliger Soak-Neustart ohne Positions-/Cash-/Ledgerverlust. Die frühere API-/Browserabnahme hatte die Ausführungslücke nicht erkannt; sie wird nicht als umfassender Paritätsnachweis weiterverwendet. Gate D bleibt offen.

Der Wert ist kein mathematisch exakter Qualitätsbeweis. Für dieses Projekt bedeutet er:

- 100 % der kritischen Anforderungen haben Owner, Status und Test;
- keine kritische Entscheidung steht auf `OFFEN`;
- normative Strategiequelle und Börse sind bestätigt;
- alle Annahmen sind bestätigt oder verworfen;
- Traceability besitzt keine kritische Lücke;
- ein unabhängiger Leser kann ohne Strategieerfindung implementieren.

Dieser Dokumentationszustand ist mit DMS V1.3 erreicht: Die Strategien lassen sich ohne Erfindung implementieren und Dokument 16 enthält keine offene kritische Produktentscheidung. Stand 02.09.2026 bestehen 68 automatisierte Strategie-/Daten-/Backtest-/Paper-/Portfolio-Risiko-/Migration-/Restart-/Recovery-/API-/Charttests, der echte Drei-Jahres-Datenaudit und reproduzierte Backtests. Nach der V2-Aktivierung bestanden alle 50 Coin-/Zeitraumkombinationen die lokale API-Prüfung; Übersicht, Chartbedienung, Signalhistorie, Paper-Ledger und Status wurden zusätzlich im gerenderten Browser geprüft, die Konsole meldete keine Warnung und keinen Fehler. Gate C bleibt bis zu externem Backup-/vollständigen Failure-Nachweisen und dem vorgeschriebenen realen V2-Paper-Soak offen; Gate D bleibt vollständig offen und `LIVE_DISABLED`.
