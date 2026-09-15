# 20 – Betriebsrunbook

## Arbeitsstand 0.4.9 / DEC-055 – Einmaltest angeschlossen, noch nicht freigegeben

Neu fertig: Supervisor-Lifecycle alle zwei Sekunden, getrennt vom Stunden-Signal und unabhängig vom Paper-Ledger; dauerhaft geladener Einmaltest/Orderjournalzustand; keine Schlüssel-/Kontozugriffe bei nicht gestartetem Test. Der Service bindet den Binance-Adapter verzögert an den gespeicherten Schlüssel, doch **Arming und produktiver Submit sind weiterhin gesperrt**. Kein abgeschalteter Dauer-Live-Status wird als aktive Testausführung ausgegeben; Fehler erscheinen als TRIAL_NEEDS_REVIEW und werden redigiert protokolliert.

Neu fertig: unveränderlicher Ausgangsbestand in `trial_account_baseline` innerhalb der bereits vorhandenen lokalen `live-preparation.sqlite3`; Erfassung nur vor Order-Intents und ohne offene Orders/gesperrte Guthaben. Doppelte Kontoabfrage um openOrders verwirft veränderliche Snapshots. Erwarteter Saldo = Ausgangsbestand + bestätigte eigene Fills − tatsächliche Gebühren je Asset. Kein Import von Altbeständen ins Paperkonto oder Verkauf als Bot-Eigentum. Der Abschluss ruft die interne Bestätigung erst bei stimmigen Salden, keinen offenen/unklaren Orders und exakt null eigener Restmenge auf; kein UI-Boolean als Ersatz. Für den inaktiven Betreiber-Test wurde noch keine Baseline erfasst.

**Nächste Arbeit, bevor HTTP 409 aufgehoben werden darf:**

1. Technische Entry-/Exit-Freigabe unmittelbar vor Versand anschließen: frische Binance-Filter (einschließlich MARKET_LOT_SIZE), Preis-/Spread-/Slippagegrenzen, tatsächlich verfügbarer eigener Bestand und freie Quote/Reserve. Die derzeitigen `False`-Freigaben niemals lediglich durch `True` oder einen UI-Schalter ersetzen.
2. Restmengenmodell erweitern: derzeit führen nicht exakt vollständig verkaufte Mengen zu NEEDS_REVIEW. Handelbare Restmengen und nicht handelbarer Dust müssen vor automatischer Freigabe sauber quantisiert, getrennt gebucht und im Bericht ausgewiesen werden; keine stillschweigende Vollverkaufsbehauptung.
3. Vollständige Fremdorder-/Kontohistorie bzw. abgenommene Kontoisolierung: Saldoerhaltung ist notwendig, erkennt aber keine zwischenzeitlichen gegenläufigen manuellen Trades. Aktuelle strenge Fremdbestandsblockade bleibt bestehen. Keine Benutzerbestände ohne Auftrag verkaufen.
4. Externe Testnet-Ausführung und Störfälle abnehmen; API-Rechte/IP-Freigabe am Betreiberkonto müssen zusätzlich stimmen. Synthetische Antworten, ein öffentlicher Marktcheck oder ein profitabler Backtest ersetzen keinen solchen Nachweis. Danach Benutzerbutton einmalig scharfstellbar machen, Kauf/Exit/Fills/Restmenge in UI/Chart vollständig abnehmen; 3×80-Dauer-Live weiterhin nicht automatisch aktivieren.

Nachgewiesen offline: alle zehn Coin-Policies treffen gleiche Paper-/Einmaltest-Entscheidungen an denselben synthetischen Punkten. Tatsächlicher Adapterparser verarbeitet je Test einen BUY(50.00) und SELL; Entry-aus nach BUY verhindert nicht SELL. Verlorene Antwort nach Kauf und Neustart erzeugen keinen zweiten BUY. Abweichende Konten/Salden, offene Orders, alte Snapshots, gebundene Mittel und BNB-Gebühren sind getestet. Dies ist kein Gewinnnachweis; die Beispielsummen sind künstliche Testwerte.

## Bedienung ab 0.4.8 / DEC-054 – kein versteckter Dauerbetrieb

1. Einmal `Startbot.bat` öffnen. Konsole und Bot-Seite offen lassen. Die Konsole benennt die Stoppregel, die UI zeigt eine dauerhafte Verbindungs-/Abschaltzeile und „Bot beenden“.
2. Erneuter Start ersetzt die identifizierte frühere Instanz **derselben Installation** geordnet. Der Starter wartet auf Prozessende, nicht nur auf einen kurzfristig freien Port. Unbekannter Portbenutzer: verständlicher Abbruch, kein pauschales `taskkill` und keine zweite Handelsinstanz. Der Starter lädt keinen ungeprüften GitHub-Code automatisch herunter.
3. Terminal schließen, letzten Bot-Tab schließen oder „Bot beenden“: Bot stoppt. Reload innerhalb 5 Sekunden bleibt möglich; mehrere Tabs zählen getrennt. Browser-/Verbindungsabbruch kann zusätzlich die Ping-Erkennungszeit benötigen. Nach erkanntem Stopp endet der Prozess binnen 15 Sekunden; ein hängender eigener Download-Thread verhindert das nicht dauerhaft.
4. Ohne erste Bot-Oberfläche startet der Handel nicht; der Starter beendet sich nach 60 Sekunden. `Startbot.bat --no-browser` ist nur für manuelles Öffnen/Testen, kein Headless-Modus. Minimieren/Tabwechsel stoppen den Bot nicht. Windows-Konsole/zugehörige Shell werden überwacht; ein Überwachungsfehler stoppt sicher.
5. **Offene Positionen werden nicht zwangsverkauft.** Nach Botende werden echte Binance-Positionen nicht mehr vom Bot überwacht. Vor echtem Betrieb bleibt ein vollständig abgenommener Konto-/Order-/Restmengen-Wiederanlauf zwingend. Bisheriger Einmaltest weiterhin nicht produktiv angeschlossen.
6. Bei Binance-Vorprüfung unterscheiden die Meldungen jetzt „deaktiviert“ und „nicht eindeutig gemeldet“. Blockierende Altbestände werden namentlich angezeigt, nicht pauschal als Staub ignoriert oder als Bot-Eigentum übernommen. Betreiber richtet vertrauenswürdige öffentliche Ausgangs-IP und Spot-Les-/Handelsrechte selbst ein und speichert bei Binance. Keine Auszahlungs-/Transfer-/Futuresrechte hinzufügen. Danach lokal entsperren und neu „Verbindung prüfen“. Ein grüner Kontocheck allein ist keine Testtrade-Freigabe.

Lokal ignoriert: `data/runtime-session.json` enthält den zufälligen Instanz-Kontrolltoken, **keinen Binance-Schlüssel**; nicht veröffentlichen. Er wird bei regulärem Ende nur vom passenden Besitzer entfernt. Veraltete Metadaten nach Rechnerabsturz werden bei freiem Port sicher ersetzt; sie rechtfertigen niemals blindes Beenden einer PID. Schlüssel/Passwort und Paperkonto werden durch Start/Stopp nicht gelöscht oder zurückgesetzt.

## Historie 0.4.7 / DEC-053 – damaliges Deployment; Echtgeld-Restarbeit weiterhin offen

GitHub-Stand `ab4f83e` und lokaler Orderadapter wurden zusammengeführt. Der Laptop wurde am 09.09.2026 ausdrücklich aktualisiert: Fast-forward `f976d6f` → `bc0b121` im tatsächlichen Desktop-Projekt, vorhandene `Startbot.bat` um 08:19 Berlin gestartet. Seit 08:19:54 HEALTHY, V6-USDC, 250 USDC Modellkapital, drei 80-USDC-Slots, keine Position/abgeschlossenen Trades, LIVE_DISABLED, Test NOT_STARTED. Alle zehn USDC-Märkte und 50 Chartkombinationen geprüft. Altes USDT-Ledger bleibt unangetastet und zusätzlich gesichert; Passwort/Schlüssel weiterhin als eingerichtet erkannt. Vollständiger Nachweis in DMS 18.

**Weiter gültig:** Ausschließlich dieselbe `Startbot.bat` im Desktop-Projekt verwenden. Die Oberfläche liegt auf `http://127.0.0.1:8765/`; zeigt eine bereits offene Browserseite noch USDT, einmal Strg+F5. Aktiver Header muss V6-ID `d57f88ec2e5f`, Marktkarte BTC/USDC und Kapital USDC zeigen. Die damalige 0.4.7 konnte alte Prozesse nicht automatisch ersetzen; **ab 0.4.8 gilt stattdessen die oben beschriebene authentifizierte Ablösung**. Bei Updates Installation und tatsächlich laufende Version prüfen, nicht nur GitHub. Keine zweite Startdatei/kein automatischer Kontoreset hinzugefügt.

Neu implementiert: `live/exchange.py` mit explizitem Binance-/Spot-Testnet-Host, HTTPS ohne Redirect/Proxy/automatischen Retry, signiertem MARKET-Kauf mit `quoteOrderQty=50.00`, SELL mit ausdrücklich vorgegebener eigener Menge, stabiler Client-ID, ACK→Orderstatus→paginierten tatsächlichen Fills. Unklare Antworten bleiben UNKNOWN und werden nur abgefragt. Exakte Binance-Quote-Mengen/Gebührenwährungen werden gebucht; USDT/USDC sind getrennt. Späte Fehler überschreiben keinen terminalen Erfolg. Entry-Freigabeablauf verhindert keinen schon fälligen Exit; dessen eigene Sicherheitsprüfung bleibt zwingend. Alles bisher ausschließlich mit Fake-HTTP/Fake-Börse geprüft.

Migration korrigiert: sieben Märkte haben keine vollständigen drei Jahre. Start fragt erste verfügbare reale Kerze ab, synchronisiert streng bis zur letzten geschlossenen Bar und verwendet einen gemeinsamen Warm-up-Start. Portfolio und CLI-Berichte geben den tatsächlich verfügbaren Zeitraum aus; keine aufgefüllten Kerzen. Alte Berichte erhalten beim Lesen ihre tatsächliche Quote, ohne Dateiumschreiben. `hixton-usdc.sqlite3` verwendet denselben Vault-Namespace wie die bisherige Standarddatenbank, ohne Schlüsselkopie/-Reset.

**Restarbeit vor dem Benutzerklick, in dieser Reihenfolge:**

1. Gemeinsames USDC-Paper-/Einmaltest-Runtime-Lifecycle anschließen. Controller muss nach Neustart alle offenen/ungeklärten Testzustände hydratisieren und Exits betreuen; Paper unabhängig weiterführen. Keine Übernahme von alten USDT-Paperpositionen als reale Bestände. Bestehendes USDT-Ledger unverändert archiviert lassen.
2. Vor jedem echten BUY Kontofingerprint, explizite globale Einmalberechtigung, frisches Signal, Markt-/LOT_SIZE-/MARKET_LOT_SIZE-/Notionalfilter, freie USDC, BNB-Reserve und Preis-/Risikolimits prüfen. Kein direkter UI-Aufruf des Low-Level-Adapters. SELL nur testzugehörige verfügbare Menge; Filterschritte, Teilfills, Dust und eventuelle Restverkaufsaufträge dauerhaft modellieren, nicht still runden oder als fertig abhaken.
3. Vertrauenswürdigen Kontoreconciler anschließen: Startbestand, Binance-Orders und vollständige Fills, Gebühren je Asset, heutige Bestände, Fremdorders/manueller Handel und Restmengen abgleichen. `confirm_reconciled` nicht durch einen UI-Boolean oder ungeprüftes True ersetzen. Bei BNB-Gebühren ohne Bewertung kein erfundener Netto-PnL.
4. Ablauf in UI/Positionsboard/Chart sichtbar machen und Testnet-/Timeout-/Teilausführungs-/Restart-/Entry-aus-/Netzausfallfälle nachweisen. Erst nach bestandener technischer Abnahme darf der Benutzerbutton einen Test scharfstellen. Keine Ausführung durch den Entwicklungsagenten, keine Aktivierung des 3×80-Dauer-Live-Modus.

Bis dahin ist HTTP 409 korrekt. Der Button heißt ausdrücklich „1 × 50 USDC · Startvoraussetzungen prüfen“. Die Kontovorprüfung verwendet USDC, ist aber kein Fill-/Exit-/Profitabilitätsnachweis. Das normale Live-Soak-Gate ist nicht entfernt. Ein echter Test hat noch nicht stattgefunden.

Adapterreferenz: [Binance Spot Trade API](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/trade) und [Account/Order/MyTrades API](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/account), geprüft am 09.09.2026. Die API-Dokumentation ersetzt nicht die noch ausstehenden Tests am tatsächlich verwendeten Konto.

## Historie: USDC-Prüfung – 0.4.6 / DEC-052, kein Echtgeldstart

Zum Spiegelverständnis: „Backtest aktuelle Einstellungen“ bedeutet dieselben Regeln mit einem frischen historischen Startkonto über das gewählte Zeitfenster. Es bedeutet nicht Übernahme historischer Gewinne/Positionen in ein heute neu gestartetes Paperkonto. Der direkte Drei-Jahres-Paper-Engine-Abgleich ist in DMS 18 dokumentiert. Portfolio über UI **und CLI** verwendet gespeicherte Slotzahl/Betrag; ohne initialisierte Settings dienen die Configwerte als ausdrücklich gewählte Defaults. Ein 4×45-Lauf ist entsprechend kein 3×80-Referenzlauf. Einzeltests bleiben 1×250.

Der bisherige Bot läuft unverändert als V6-USDT-Paperkonto. Nicht versuchen, den USDT-Testbutton mit USDC-Guthaben als fertig migrierten Ablauf zu verwenden. V7 ist nur ein Prüfstand; weder `paper-activate` noch normale Backtest-/UI-Auswahl geben ihn frei. Einmaltest und Dauer-Live bleiben gesperrt.

Ein technischer Einstieg bleibt `src/main.py`: `python src/main.py backtest usdc-review --end 2026-09-08T06:00:00Z`. Optional `--usdt-control-db "ABSOLUTER PFAD ZUR BESTEHENDEN DATENBANK"` für den zeitraumgleichen USDT-Kontrolllauf. Dieser liest nur Kerzen mittels SQLite `mode=ro`, führt keine Migration aus und schreibt keine Kontotabellen. Öffentliche USDC-Kerzen werden ausschließlich in `data/usdc-validation.sqlite3` gespeichert, nicht im aktiven Ledger. Jeder Bericht landet unveränderlich unter `backtests/v7/runs/<id>/`; kompakte kuratierte Nachweise stehen eine Ebene darüber. Keine zusätzliche Startdatei, keine großen Kerzendaten auf GitHub.

Bei „keine Papertrades“ zuerst Gesundheit, letzte geschlossene Bar, letzten Trendwechsel, Aktivierungszeit, vorhandene Positionen und Risiko-/Cashblocker prüfen. Grün allein ist kein neuer Entry. Marktkarten zeigen ab 0.4.6 den letzten Indikatorwechsel; das ist ausdrücklich kein Fillnachweis. Alte Signale werden nicht nachgekauft und der Risikohalt nicht wegen geringer Tradezahl gelöscht.

## Einstellungen bedienen – gültig ab 0.4.5 / DEC-051

- Browser einmal neu laden (bei alter Ansicht Strg+F5). Unter Handel gewünschte Slots und USDT pro Trade einstellen, dann **Übernehmen**. Positionsbudget ist deren Produkt, keine feste 240-USDT-Grenze. 5×50 ergibt 250; 10×100 ergibt 1000, aber kein neues Kontoguthaben. Keine neuen Positionen allein durch Speichern; Auslieferung setzt selbst keine Betreiberwerte um.
- Unter Binance verbinden das **bereits eingerichtete Hixton-Passwort** eingeben und Entsperren oder Enter drücken. Nur bei erster Einrichtung Passwort wiederholen. Nicht das Binance-Passwort verwenden. Fehlermeldung steht direkt darunter, z. B. falsches Passwort oder 60 Sekunden Wartezeit nach zu vielen Versuchen. Kein Passwortreset durch das Update; Zugang nicht durch Umgehen der Prüfung freischalten.
- Bei bestätigter Sitzung erscheint „Entsperrt“ und API-Key/Secret sind editierbar. Beide eingeben, Schlüssel speichern, Verbindung prüfen. Jede Aktion hat eine eigene sichtbare Rückmeldung. Ablage bleibt Windows Credential Manager; keine echten Schlüssel in Chat, Projekt oder GitHub.
- Die Verbindungskontrolle liest nur Konto/Rechte. **Live an und 50-USDT-Test sind noch nicht ausführbar**, solange Orderadapter/Abgleich fehlen. Live aus sperrt neue echte Entries, auch für einen angeschlossenen Test; keine Zwangsliquidation, Paper bleibt aktiv. Bot muss für reguläre Ausstiege laufen bleiben.
- Einmaltest optional aufklappen, ausdrücklich beschrifteten Button für genau einen 50-USDT-Echtgeldtrade verwenden. Keine Checkbox oder Wortbestätigung, kein Dauerbetrieb; aktueller fehlender Echtgeldanschluss verhindert den Start weiterhin. Live an/aus markiert den Serverzustand, nicht den zuletzt angeklickten Button. Normales Live soll die gemeinsamen Werte verwenden. Schlüsselverwaltung/Sicherheitsdetails sind einklappbar; Entfernen eines Schlüssels wird separat mit Ja bestätigt.

Fehlerbehebung 08.09.2026: `-1100` bei Marktfiltern war durch Leerzeichen in der vom Bot gesendeten Zehn-Coin-Liste reproduzierbar. In 0.4.5 korrigiert; hierfür keinen neuen Schlüssel erzeugen. Nach Update erneut entsperren und **Verbindung prüfen**. Ein danach genannter anderer Prüfschritt/Code ist getrennt zu untersuchen. Systemzeit, Parameterformat und Key-/IP-Rechte werden nicht mehr mit derselben pauschalen Empfehlung verwechselt. Keine Secrets in Chat, Logs oder Projektdateien schreiben.

Die bisherigen Anleitungen mit Einstiegspause, Verwerfen und getipptem ANWENDEN sind historische Teilstände, durch den obigen Ablauf ersetzt. Interne Risikoabschaltungen bleiben wirksam.

## Gemeinsame Einstellungen ab 0.4.3

1. Unter „Handelseinstellungen · Paper & Live“ Slots und Positionsgröße einmal eingeben. Die Live-Zusammenfassung zeigt sofort den **Entwurf** neben dem weiterhin geltenden Speicherstand. Bei 4/5 Slots erscheint die bestehende Freigabegrenze 3/240 ausdrücklich; kein stiller Standard-Rückfall.
2. ANWENDEN bestätigen. Erst eine erfolgreiche Serverantwort ersetzt den gespeicherten Stand überall; Fehler lassen den Entwurf stehen, „Verwerfen“ stellt den Speicherstand wieder her. Kein Kontoreset, keine Kapitalzufuhr. Ein gemeinsamer Datensatz, keine zweite Live-Eingabe. Mit ungespeicherten Änderungen kein Live-Start.
3. „Einstiegspause“ verhindert nach dem Speichern neue Käufe in Paper und stoppt neue Entries eines angeschlossenen Testcontrollers. Keine Liquidation; Entpausieren ist kein Live-Start. „Live aus · auch Einmaltest-Einstiege stoppen“ betrifft nur neue Echtgeld-Einstiege und lässt Paper laufen. Die frühere separate Einmaltest-Stopp-Schaltfläche entfällt. Ein laufender Bot bleibt für Ausstieg/Überwachung nötig.
4. Der 1×50-Einmaltest bleibt getrennt vom normalen Budget. API-Key/Secret sind sichtbar und werden erst lokal entsperrt. Echtgeld bleibt wegen fehlendem produktivem Adapter/Abgleich gesperrt; keine Freigabe durch diese UI-Änderung. Technische Gründe sind einklappbar.

Paper arbeitet bereits mit echten Binance-Marktdaten in Echtzeit, aber simuliert Geld und Ausführungen. Live soll dieselben Coin-Regeln und gespeicherten Handelsgrößen verwenden, führt aber eigene echte Positionen; historische Paper-Käufe werden nicht in Binance nachgekauft. Tatsächliche Preise, Gebühren und Fills können vom Modell abweichen. Der Backtest ist die historische Simulation. Die nachfolgende 0.4.2-Anleitung bleibt als datierter Teilstand erhalten.

## Live-Vorbereitung ab Anwendung 0.4.0

### Bedienung und tatsächlicher Teilstand 0.4.2

Unter **Einstellungen → Binance Live-Vorbereitung** sind API-Key und Secret nicht mehr hinter einer ausgeblendeten Fläche versteckt. Beide Felder bleiben sichtbar, aber gesperrt, bis der Betreiber sein lokales Hixton-Passwort eingerichtet bzw. eingegeben hat. Danach dort **Binance API-Key (HMAC)** und das zugehörige **Binance Secret-Key** eingeben, SPEICHERN bestätigen und „Binance-Konto prüfen — keine Orders“ wählen. Diese Kontoprüfung liest Binance; sie ist kein Ordertest und keine automatische Echtgeldfreigabe.

Darunter stehen jetzt „Test-Trade · 50 USDT · Freigabe prüfen“, „Einmaltest: neue Einstiege stoppen“ und getrennt „Live an · Freigabe prüfen“ / „Live aus · nur neue Einstiege sperren“. Die tatsächlichen gespeicherten Paper-Slots werden als spätere Live-Vorlage angezeigt, nicht blind 3×80 behauptet. TEST 50 USDT bestätigt den beabsichtigten einmaligen Umfang. **In 0.4.2 bleibt Start trotzdem gesperrt**, weil der getestete Controller noch keinen produktiven Exchange-/Runtime-/Reconciliation-Anschluss hat. Die UI sagt ausdrücklich „nicht gestartet“ und nennt die fehlenden Schritte. Wiederholtes Klicken, Schlüssel-Eingabe oder ein positives Kontoergebnis umgehen diese Sperre nicht.

Implementierter Code: `src/hixton/live/trial.py`, 25 Fake-Börsen-Tests in `tests/test_live_trial.py`, vorhandenes Orderjournal und abgesicherte UI-Routen. `SignalTrial` verwendet dieselbe `TradePolicyGate` und Rangfolge wie Paper, reserviert genau einen Einstieg im SQLite-Ledger und bewahrt die Identität über Neustarts. Entry-Stopp lässt eine bereits offene Position offen und lässt den Strategieausstieg im Controller weiter zu. Eine volle Verkaufsmeldung allein ist kein Abschluss: `AWAITING_RECONCILIATION` benötigt einen separat vertrauenswürdig erzeugten Kontonachweis, nicht eine Behauptung aus der UI. Handelbare Restmengen bleiben `NEEDS_REVIEW`. Historische verpasste Exit-Signale verwenden einen aktuellen Ausführungsreferenzpreis statt erfundener vergangener Fills. Zusätzliche Menge wird nie nachgekauft. Ausstiegsberichte benennen konfigurierten Stop, fehlenden TP/Trailing, Fills/IDs/Gebühren; ohne Bewertung von Gebühren in dritter Währung bleibt Netto offen.

**Fortsetzung, noch zu implementieren/abzunehmen:** Produktions-Binance-Submit/Query/gezieltes Storno mit vollständigen aktuellen Filtern/Saldo-/Preis-/Rechte-/Risikogates; realer Konto-/Fremdorder-/manueller-Handel-/BNB-Reconciler und sichere Restmengenbehandlung; dauerhafter Supervisor mit Startup-Hydration, Entry-Sperre und fortlaufender Exitbetreuung; tatsächliche Echtgeldpositionen/-orders/-trades in Positionsboard/Chart/Audit; individuelle Betreiber-/Testnet-/Störfallabnahme. Der normale 3×80- bzw. konfigurierbare Live-Mehrslotbetrieb ist noch nicht implementiert. Bestehende Papertrades bleiben hiervon unabhängig. API-Clients oder boolesche Test-Fixture-Freigaben nicht als produktive Freigabe missbrauchen. Start-/Stoppknöpfe in dieser Version sind kein Nachweis eines mehrere Wochen autonom betreuten Binance-Kontos.

**Status: Vorbereitung nutzbar, Echtgeld-Orderversand NICHT implementiert/freigegeben.** Der Paper-Test läuft weiter. Der neue Bereich ist kein Schalter, der trotz fehlender Prüfungen echte Orders auslösen darf.

1. Unter Einstellungen Paper-Slots/Notional bearbeiten, z. B. 1 und 50. Der Entwurf bleibt trotz Polling erhalten. „ANWENDEN“ mit genau diesem Wort bestätigen. Gespeicherten Stand kontrollieren. „Verwerfen“ lädt den aktuellen Speicherstand zurück. Keine Kontoauffüllung, keine Schließung/Vergrößerung bestehender Positionen. Ein Einstellungswechsel segmentiert die spätere Auswertung über den vorhandenen Audit, ohne Soak-/Kontohistorie zu löschen.
2. Im getrennten Live-Bereich ein **eigenes lokales Hixton-Passwort** mit mindestens zwölf Zeichen festlegen und wiederholen. Es ist nicht das Binance-Passwort. Bei späterer Nutzung damit entsperren. Sitzung gilt höchstens 15 Minuten und endet nach Bot-Neustart/Abmelden.
3. Einen eigenen HMAC API-Key samt Secret für einen dedizierten Binance-Bot-Account/Subaccount **nur in der lokalen UI** eintragen. Lesen/Spot erlauben; Auszahlung, interne/universelle Transfers, Margin, Futures, Optionen und sonstige Handelszugriffe deaktivieren; IP-Beschränkung setzen. Fehlende oder unbekannte Rechte bleiben blockiert. Keine Keys in Chat, Git, Terminal oder Markdown.
4. Sicher speichern/Ersetzen ausdrücklich bestätigen. Ablage erfolgt im Windows-Anmeldedatenspeicher des aktuellen Benutzers/PCs, nicht in OneDrive. Beide Eingabefelder werden geleert. Sichtbar bleiben nur Status/Fingerprint/Datum im entsperrten Bereich.
5. „Binance-Konto prüfen — keine Orders“ liest Uhr, Rechte, Spotkonto, offene Orders und Filter aller zehn Märkte. Erster geplanter Echtgeld-Test: **1×50 USDT**, mindestens 60 freie USDT inkl. anfänglichem Gebühren-/Cashpuffer. BNB-Guthaben wird separat angezeigt, kein Rabatt allein daraus unterstellt. USDC zählt nicht als USDT. Fremdbestände/offene Orders werden nicht automatisch verkauft, importiert oder storniert. Eine positive Kontoprüfung ersetzt keine Ausführungsprüfung.
6. „Live anfordern / Freigabe prüfen“ zeigt fehlende Schritte. **Aktuell immer `LIVE_DISABLED`**, auch mit gültigem Key und bestandenem Kontovorcheck. Kein automatischer Folgeauftrag nach Schlüsseleingabe. Kontoprüfung verfällt nach 60 Sekunden, Restart oder Schlüsseländerung; frühestens nach 30 Sekunden erneut anfordern, Provider-Rate-Limits können länger sperren.
7. „Live aus“ bestätigt in dieser Stufe den ausgeschalteten Zustand. „Schlüssel entfernen“ entfernt nur den lokalen Key/Secret, nicht das lokale Passwort und nicht den Binance-Key auf der Börse. Widerruf bei Binance ist eine gesonderte Betreiberaktion. „Sperren“ beendet die geschützte UI-Sitzung.

### Verbindliches Ziel: ein signalgesteuerter 50-USDT-Einmaltest (DEC-047)

Am 07.09.2026 hat der Eigentümer die Rückfrage entschieden: **kein sofortiger Kauf-/Verkaufs-Rundlauf**, sondern genau ein vollständiger Echtgeldtrade nach der aktiven coinindividuellen Hixton-Strategie. Dies ist eine beschlossene Anforderung, **keine in Anwendung 0.4.1 bereits verfügbare Startfunktion**. Paper-Settings 1×50 oder der vorhandene Vorbereitungsbereich starten keinen Echtgeldtest.

Geplanter Ablauf nach technischer Implementierung und gesonderter Testfreigabe:

1. Betreiber entsperrt den lokalen Bereich, hinterlegt Key/Secret selbst und lässt Rechte, Konto, Filter, Datenfrische und reale freie Mittel prüfen. Bestätigungsansicht zeigt ausdrücklich **EINMALTEST · ECHTGELD · ein Einstieg · 50 USDT Kaufnotional · Gebühren separat**. Das bezeichnet USDT, nicht Euro. Normales 24/7-Live bleibt gesondert gesperrt; ein laufender Echtgeldtest darf in der UI nicht als bloßes `LIVE_DISABLED` versteckt werden.
2. Nach ausdrücklichem Start durch den Betreiber wartet der Test auf das nächste **neue qualifizierte** Signal aus den zehn bestehenden Coins. Kein sofortiger Kauf, kein Nachholen alter Paperfills und kein Einstieg allein wegen grünem Trend. Bei gleichzeitigen geeigneten Signalen gelten dieselbe normalisierte Rangfolge und feste Tie-Break-Reihenfolge wie im Paperbetrieb. Aktive Strategieversion und vollständige Coin-Profile werden für den Test eingefroren; spätere UI-/Profiländerungen dürfen ihn nicht still verändern.
3. Genau eine Einstiegsberechtigung für den gesamten Test, nicht eine pro Coin oder HTTP-Aufruf. Der Server begrenzt den BUY auf 50 USDT Quote-Budget, unabhängig von Paper-Settings, Kontoguthaben oder manipuliertem Browserwert. Gebühren werden zusätzlich und in ihrer tatsächlichen Währung ausgewiesen; der bestehende 60-USDT-Vorcheck schafft Puffer, aber keine Erlaubnis, diesen mit zu investieren. Mengenfilter/Teilfüllungen können zu einem tatsächlich kleineren Kauf führen; nie durch Nachkäufe auf 50 auffüllen. Auch die separaten Paper-Slots lösen keine weiteren Echtgeldkäufe aus.
4. Die tatsächlich erhaltene Menge wird separat geführt und ausschließlich nach dem ausgewählten Coin-Profil verwaltet. Ausstieg durch reguläres Hixton-Verkaufssignal oder eine tatsächlich konfigurierte zusätzliche Stopregel. Kein erfundener Take-Profit, kein erzwungener Verkauf am nächsten Morgen. Teilfills sind Teile desselben logischen Trades, keine weiteren Einstiege. Es dürfen nur testzugehörige verfügbare Mengen verkauft werden, keine fremden Bestände oder vorgelagerte BNB-Gebührenreserve.
5. Nach Ausstieg und erfolgreichem Börsenabgleich ist der Test dauerhaft beendet: **keine automatische Wiederbewaffnung, kein zweiter Einstieg und keine Freigabe für 3×80**. Doppelklick, mehrere Browser, neues Signal oder Neustart dürfen das Einmalbudget nicht erneuern. Unklare Orders bleiben klärungsbedürftig; kein neuer Kauf als vermeintliche Wiederholung. Bei Restmengen werden handelbare Reste bzw. Dust ausdrücklich ausgewiesen; kein verschwiegener Bestand bei einer Erfolgsmeldung. Abbruch vor dem Kauf beendet die Wartephase; nach möglichem Kauf stoppt er nicht still die Überwachung realer Bestände.

**Tatsächliche V6-Ausstiege:** Alle zehn Profile haben derzeit keinen festen Take-Profit und keinen aktivierten ATR-Trailing-Stop. Nur XRP hat zusätzlich den lokalen Schlusskurs-Stop `close <= entry_fill - 4 * entry_ATR`; die übrigen neun Coins steigen per Hixton-Verkaufssignal aus. Der XRP-Stop wird an geschlossenen `1h`-Bars beurteilt, ist kein bei Binance hinterlegter dauerhafter Schutzauftrag und garantiert keinen Verkauf zum Stoppreis. Ausfall des Laptops/Feeds kann einen lokal ausgelösten Ausstieg verzögern. Ein zusätzlicher harter Börsen-Stop oder fester Take-Profit wäre eine eigene Strategie-/Ausführungsänderung mit neuen Tests, nicht eine unbemerkte Ergänzung dieses Spiegeltests.

Der Bericht erscheint als **EINMALTEST · ECHTGELD**, getrennt von Paper und Backtest, im bestehenden Positions-/Orderbereich und enthält:

- Test-ID, ausgewählter Coin, Strategieversion, vollständige Parameter/Regeln und zugehörige Ein-/Ausstiegssignale samt Indikatorwerten;
- angefordertes Kaufbudget, von Binance bestätigtes Kaufnotional, Menge, Preis, Teilfills, Order-/Trade-IDs, Signal-/Sende-/Ausführungszeiten und Abweichungen; Soll/Ist ausdrücklich getrennt;
- reale USDT-Abgänge/-Zugänge und Gebühren in USDT, BNB oder Basisasset; getrennte Netto-Mengenrechnung und Bestandsabgleich, kein modellierter Paperpreis als Echtgeldbeleg;
- Ausstiegsgrund mit Unterscheidung **nicht konfiguriert / konfiguriert, nicht ausgelöst / ausgelöst, Ausführung bestätigt / fehlgeschlagen oder ungeklärt** für Stop-Loss, Take-Profit und Trailing;
- Dauer, Brutto-/Nettoergebnis, Restbestände und jede Abweichung. Unbewertete Fremdwährungsgebühren oder fehlende Fills verhindern eine endgültige Netto-Erfolgsaussage.

Die nächste Analyse prüft damit den konkreten realen Ablauf, nicht nur eine grüne UI-Meldung. Ein einziger abgeschlossener Trade belegt weder alle zehn Coin-Pfade noch alle Stop-/Fehlerfälle oder zukünftige Profitabilität. Ein Abschluss bis zum nächsten Morgen und ein Gewinn werden nicht versprochen. Bisher wurde kein echter Test gestartet.

### Noch vor einem tatsächlichen 1×50-Liveversuch zu bauen und abzunehmen

Bereits offline implementiert: `src/hixton/live/orders.py` mit dauerhaftem Auftrag, atomarer Sendebeanspruchung, Abgleich nach unklarer Antwort/Neustart und idempotenten Teilfills. `tests/test_live_orders.py` prüft 21 Fälle mit einer künstlichen Börse, einschließlich Kauf/Verkauf nur der netto erhaltenen Menge. **Nicht angeschlossen und kein vollständiges Livekonto.** Jeder separat angelegte Intent benötigt später eine gemeinsame wirksame Einmal-/Budget-/Besitzprüfung; „50 pro Intent“ allein begrenzt nicht die Gesamtausgaben. Das Orderjournal wird im normalen Botstart nicht angelegt. Die nachfolgenden produktiven Arbeiten bleiben offen.

- Gemeinsame frische Order-Intents für Paper/Live, aber getrennte Konten, Positions-/Order-/Fill-Ledger und Checkpoints. Kein Weiterleiten historischer Paper-Replay-Fills; kein spontaner Kauf beim Moduswechsel.
- Binance-Submit mit persistenter Client-ID **vor** Netzwerkzugriff, echte Teilfills/Gebühren (einschließlich BNB), Filter-/Saldo-/Slippagekontrolle, UNKNOWN-Behandlung und Neustart-Reconciliation ohne Doppelorder. Getestete Fremdorder-/Saldoerkennung und BNB-Gebührenreserve dürfen keine fremden Assets vereinnahmen.
- Geprüfte Live-aus-Semantik: keine neuen Entries, reale offene Positionen sichtbar weiter überwachen/regelkonform aussteigen lassen; vollständiges Schließen nur separat bestätigt. Kein stiller Wechsel ins Paperkonto bei noch existierenden Echtgeldpositionen. Neustart beginnt gesperrt und verlangt Reconciliation.
- Separate wirksame Budgetfreigabe: zunächst maximal 1×50. Erst spätere ausdrücklich bestätigte und getestete Erhöhungen auf 3×80, 750 USDT oder mehr. Keine selbsttätige Erhöhung durch Kontoguthaben, Gewinne oder Beispielwerte in der UI.
- Binance-Testnet-/Failure-Injection-Nachweis und vergleichbare Paper-/Live-Ausführung, vollständiger Paper-Soak, Sicherheit/Recovery/Backup/Incident-Abnahme nach DMS 12 sowie gesonderte Eigentümerfreigabe. Auch danach sind identische Fillpreise oder Gewinne nicht garantiert.

Das sind offene Implementierungs-/Nachweisarbeiten, keine bereits vorhandene Funktion. Ein fest gespeichertes `live=true` oder allein eine abgeänderte Statusanzeige wäre keine zulässige Umsetzung. Die größere Echtgeldfunktion darf nicht aus dem Vorbereitungs-UI als fertig abgeleitet werden.

### Schlüssel-/Passwort-Recovery und Installation

Windows-Speicherziele heißen `DerHixton/<Installationshash>/binance-hmac` und `/ui-password`; der Hash bezieht sich auf den exakten Datenbankpfad. Ein anderes Windows-Konto, ein anderer PC oder verschobener Projektpfad benötigt eine neue Einrichtung. Das ist keine Mehrbenutzer-Webplattform. Ein vergessenes lokales Passwort wird nicht über eine unauthentifizierte HTTP-Resetfunktion zurückgesetzt. In dieser noch orderlosen Version: Bot stoppen, Betreiber entfernt ausschließlich die **beiden exakt zugehörigen** Hixton-Einträge über Windows-Anmeldeinformationsverwaltung, anschließend neu einrichten; bei Unsicherheit zuerst den Binance-Key widerrufen. Vor künftigem Livebetrieb ist Recovery mit offenen Orders gesondert abzusichern.

Audit liegt separat unter `data/live-preparation.sqlite3` und enthält Zeit/Aktion sowie gegebenenfalls Fingerprint/Prüferfolg, keine Secretwerte oder kompletten Binance-Antworten. Nach einem erfolgten Schlüsselschreibvorgang, aber fehlgeschlagener Audit-Endmeldung bleibt Live weiterhin gesperrt; Speicherstatus lokal prüfen, nicht von einer Erfolgsmeldung ausgehen. Normale Projektbackups enthalten keine Windows-Secrets. Gegen Schadsoftware mit denselben Windows-Rechten oder Administratoren gibt es keinen absoluten Schutz.

UI-Stand 0.3.2: Nach einem UI-Update die vorhandene Browserseite einmal neu laden (bei altem Bundle `Strg+F5`). Kein Kontoreset nötig. Unter Backtests zuerst Version und Testart wählen; nur der neueste passende Lauf steht direkt sichtbar, frühere Läufe lassen sich aufklappen. Ein historischer RISIKOHALT ist nicht der aktuelle Paper-Healthstatus. Abnahme und unverändert erhaltener V6-Soak: DMS 18.

## Aktuell: V6-Paperexperiment und ausdrücklicher Neuanfang (DEC-045)

DEC-045 (06.09.2026): Auf ausdrücklichen Eigentümerwunsch wird V6 `HIXTON-V6-COIN-PAPER-1-9734f240e873` als **Paper-Experiment** aktiviert. Der frische Modellaccount startet mit 250 USDT, drei 80-USDT-Slots und 10 USDT Anfangsreserve. Alte Paperpositionen, Ereignisse, Dust und Soak bleiben ausschließlich im geprüften lokalen Vollarchiv; sie werden weder als neue Trades noch als Gewinn übernommen. Normale Neustarts erhalten das Konto weiterhin. Die schwächeren jüngsten/älteren Ergebnisse bleiben bestehen; dies ist keine Robustheits-, Optimalitäts- oder Livefreigabe.

### Genau ein Starter, kein automatischer Reset

Normal starten: `Startbot.bat`. Backtestauswahl verändert Paper nicht. Neues Paperkonto nur auf ausdrücklichen Auftrag:

1. `backtests/v6/README.md` einschließlich Verlustfenstern und Risikohalts lesen.
2. Den identifizierten einzelnen Hixton-Prozess stoppen; Port 8765 muss frei sein. Während der Wartung nicht parallel starten.
3. Geprüften Code und V6-Config installieren. Über denselben technischen Einstieg einmalig ausführen:

```powershell
py -3 src/main.py paper-fresh-start --archive backups/paper-v2-archive-20260906/hixton.sqlite3 --confirmation NEUSTART
```

4. Befehl reserviert den UI-Port, sperrt SQLite-Schreibzugriffe, erzeugt ein nicht überschreibbares Vollarchiv, prüft Integrität und SHA-256 und setzt ausschließlich bekannte `paper_*`-Tabellen in einer Transaktion zurück. Ein Fehler beim Reset rollt vollständig zurück; vorhandene Archive werden nie überschrieben. Fehlgeschlagene Archivversuche können eine unvollständige Datei hinterlassen: nicht als gültiges Backup verwenden.
5. Neues Konto: 250 USDT Cash/Startbasis/High-Water-Mark, 3×80, keine Positionen, Trades oder Dust. Audit `PAPER_FRESH_START` enthält Zeitpunkt, Archivpfad/-hash und alte Zeilenzahlen. Das ist keine simulierte Liquidation und keine Gewinnbuchung.
6. `Startbot.bat` starten und Startup-Sync für alle zehn Märkte abwarten. Neue Checkpoints auf letzte geschlossene Bars; Soak startet neu. Alte Signale werden nicht nachgehandelt.
7. `HEALTHY / PAPER / LIVE_DISABLED`, V6-Version, zehn tatsächliche Profile, 250 USDT, drei freie Slots, null alte Paperfills und fünf Chartzeiträume prüfen. Historische Indikatorsignale bleiben für Charts vorhanden.
8. Pfad/Hash/Zeit und Prüfungen in DMS 18 festhalten. Das Archiv bleibt unter ignoriertem `backups/`; Marktdaten bleiben in `data/hixton.sqlite3`.

Für einen späteren Strategiewechsel **ohne** Kontoneuanfang bleibt `paper-activate --strategy v6 --confirmation AKTIVIEREN` ein anderer Wartungsvorgang: Er bewahrt Ledger, Cash und Risikohistorie und modelliert gegebenenfalls alte Positionsschließungen. Nicht mit dem Reset verwechseln.

Historische Abnahme der Anwendung 0.3.0 (`f633f38`) mit unverändertem V2-Konto steht in DMS 18; sie wurde erst durch den neuen ausdrücklichen DEC-045-Auftrag abgelöst.

## Historischer Übergabestand 05.09.2026

Anwendung 0.2.1 läuft auf dem Laptop über die einzige `Startbot.bat`; Strategie bleibt V2, drei Slots à 80 USDT, Live gesperrt. DMS 18 enthält Backup, Neustartnachweis und die beiden frisch aus der UI gestarteten Run-IDs. Der technische Soak startete wegen der Ausführungskorrektur einmalig neu. Alte Positionen und Trades dürfen dafür **nicht** gelöscht oder zu besseren Kursen umgebucht werden.

Neuester Forschungsstand DMS 1.5: V5 untersucht alle zehn Coins einzeln. Zuerst `backtests/v5/README.md` einschließlich Rückschritten und realisiertem/offenem PnL lesen; nicht nur den hohen Dreijahres-Portfolioendwert übernehmen. Forschung über `backtest research --study v5` ändert keine Einstellungen und ist keine neue UI-Strategieauswahl. Keine riskanten Kontoresets oder Soak-Neustarts allein für einen Forschungsbericht. Für eine Fortsetzung durch GPT/Codex sind Versuchskatalog, Rohbericht-Hash, Quell-/Datenhashes und nächste fachliche Schritte im V5-Nachweis festgehalten.

Bei „handelt zu wenig“ zuerst freie Slots, offene Positionen, letzten **neuen** Trendwechsel und den Blockierungsgrund unter Positionen/Orders prüfen. Ein grüner Dauertrend ist kein erneuter Entry; mehrere Slots im selben Coin sind weiterhin nicht freigegeben. Zum Zeitpunkt des Updates waren ADA, DOGE und ETH gleichzeitig offen.

Für eine Verzögerungsprüfung tatsächlichen Verarbeitungszeitpunkt (`/api/paper/events`: `processed_at_utc`) und modellierte Fillzeit (`occurred_at_utc`) getrennt lesen. `LEGACY_CLOSE_OR_MIGRATION` besitzt keinen neuen Latenznachweis. Datenqualität muss die gerade abgeschlossene Stunde zeigen; nach zwei Minuten fehlende Kerzen sind ein Recoveryfall. Modellexits alter Einstiege zählen nicht als vollständige neue Soak-Trades. Der private Orderadapter, Reconciliation und ein realistischer Ausführungs-/Restore-/Störungsnachweis bleiben vor Echtgeld offen.

## Vor jedem ersten Start

1. Modus `BACKTEST` oder `PAPER`; `LIVE` aus.
2. freigegebene DMS-, Strategie- und Konfigurationsversion prüfen.
3. zehn Coins, Börse, Timeframe und Kostenmodell prüfen.
4. Secret-Referenzen testen; keine Werte anzeigen oder kopieren.
5. lokalen Speicherplatz, Systemzeit und Backupziel prüfen.
6. Start auslösen und Startup-Report vollständig abwarten.
7. Nur bei `HEALTHY` Paper-Signalverarbeitung freigeben.

## Täglicher Betreibercheck

- Modus und globaler Healthstatus;
- letzte geschlossene Kerze für alle zehn Coins;
- letzte erfolgreiche 00:05-UTC-Synchronisation;
- offene/ungeklärte Orders;
- Reconciliation- und Saldodifferenzen;
- Datenlücken/Quarantäne;
- Backupstatus;
- P1/P2-Alarme;
- Speicherplatz und Scheduler.

Dieser Check wird im Livebetrieb protokolliert. „Keine Warnung gesehen“ ist kein Ersatz für einen Healthnachweis.

## Geplanter Neustart

1. neue Entries pausieren;
2. offene Orders/Positionen ansehen;
3. Bot geordnet stoppen; Börsenorders nicht blind stornieren;
4. Wartung durchführen;
5. im `LIVE_DISABLED`-/Paper-Zustand starten;
6. Startup-Sync und Reconciliation prüfen;
7. Versionen/Config-Diff kontrollieren;
8. erst danach vorherigen Modus explizit wieder freigeben.

## Kontrollierter Paper-Strategiewechsel

Ein Strategiewechsel ist kein normaler Neustart und erfolgt nie über die Backtestauswahl.

1. ausdrückliche Eigentümerentscheidung und Zielversion im Entscheidungslog prüfen;
2. laufenden Paperprozess geordnet stoppen und lokale SQLite-Datei sichern;
3. Code, Konfiguration, DMS, Golden-Tests und Ziel-Backtests auf denselben Commit bringen;
4. Daten für alle zehn Märkte vollständig synchronisieren und auditieren;
5. einmalig über den einzigen Einstieg `py -3 src/main.py paper-activate --strategy v2 --confirmation AKTIVIEREN` migrieren;
6. kontrollierte Schließungen alter Paperpositionen, Auditdatensatz, neue Strategie-Session, Start-Equity und zurückgesetzten Soak prüfen;
7. Bot ausschließlich in Paper starten; ein Versionskonflikt muss den Start blockieren;
8. Header, Systemkarte, Ledger, zehn Märkte und alle Chartzeiträume prüfen;
9. `LIVE_DISABLED` muss unverändert sichtbar und technisch erzwungen sein.

Die Migration löscht keine alten Ereignisse. Eine Wiederholung auf dieselbe aktive Version ist idempotent. Ein Wechsel zurück benötigt eine neue ausdrückliche Entscheidung; keine Datenbankdatei wird manuell umgeschrieben.

## Stream oder Datenfeed stale

Auslöser: 90 Sekunden ohne Streamupdate oder finale 1h-Bar mehr als 120 Sekunden nach geplantem Schluss nicht verfügbar.

1. betroffene Symbole/Zeitraum feststellen;
2. neue Entries für betroffene Symbole pausiert lassen;
3. REST-/Providerstatus und Systemzeit prüfen;
4. Reconnect abwarten bzw. sicheren Audit starten;
5. fehlende Bars nachladen und Datenqualität erneut prüfen;
6. aktuellen Trendzustand rekonstruieren;
7. keine alten Signale als Live-Order nachholen;
8. bei längerem/mehrfachem Ausfall Incident eröffnen.

## Orderstatus `UNKNOWN`

Auslöser: zehn Sekunden nach Submit keine eindeutige Börsenbestätigung.

1. **keine Ersatzorder senden**;
2. Client-Order-ID bei Börse abfragen;
3. offene/geschlossene Orders und Trades seit Signalzeit prüfen;
4. freie/gesperrte Salden abgleichen;
5. Fills ins Ledger übernehmen, falls eindeutig;
6. bei Restunsicherheit `HALTED` lassen und Incident eskalieren;
7. nur nach dokumentierter Reconciliation entsperren.

Ein nach 30 Sekunden verbleibender Teilfill-Rest wird nach Statusklärung storniert, sofern die Börse ihn als stornierbar meldet. Kein automatischer Ersatzsubmit. Ein Rest unter Börsenminimum bleibt sichtbar als `DUST`.

## Tagesverlust oder Drawdown-Grenze

- Bei 5 % Nettoverlust gegenüber der Equity um 00:00 UTC werden neue Entries bis zum nächsten UTC-Tag pausiert; Exits und Überwachung bleiben aktiv.
- Bei 20 % Drawdown vom globalen Equity-High-Water-Mark wechselt das System auf `HALTED`.
- Keine der beiden Grenzen liquidiert Positionen automatisch.
- Vor manueller Wiederaufnahme nach Drawdown: Ursachen-, Ledger-, Daten- und Konfigurationsprüfung, Incidentabschluss und ausdrückliche Eigentümerfreigabe.

## Lokale Alarmanzeige oder Log gestört

1. Botstatus direkt über die lokale Status-API und Datenbank nur lesend prüfen;
2. bei Ausfall der UI **oder** des strukturierten Logs `DEGRADED` setzen und neue Entries pausieren;
3. Ursache in API, Dateisystem, Datenbank und Browserkonsole prüfen;
4. P1-Testereignis auslösen und Sichtbarkeit in UI sowie Log bestätigen;
5. erst danach Entries wieder freigeben.

Telegram ist kein Pflichtbestandteil. Ein später optionaler externer Alarmkanal wird als Zusatz behandelt und darf die lokalen Pflichtnachweise nicht ersetzen.

## Positions-/Saldodifferenz

1. Live-Entries global pausieren;
2. lokale Fills/Ledger mit Börsentrades vergleichen;
3. manuelle Orders, Gebührenassets, Transfers und Rundungsreste prüfen;
4. keine lokalen Werte ohne Gegenbuchung überschreiben;
5. Ursache und Korrektur auditieren;
6. Reconciliation-Test wiederholen;
7. Eigentümerfreigabe bei Kapitalauswirkung.

## Not-Aus

1. Not-Aus aktivieren; dies verhindert neue Entries.
2. offene Orders und Positionen getrennt beurteilen.
3. Not-Aus darf Positionen nicht still automatisch liquidieren.
4. Falls Schließen nötig: Symbol, Menge, erwartete Kosten und Preisabweichung prüfen; separate Aktion bestätigen.
5. Grund/Actor/Zeit auditieren.
6. Reaktivierung erst nach Ursachenklärung und Reconciliation.

## Delisting/Handelspause

1. Symbol auf `HALTED` setzen;
2. Börsenstatus und bestehende Position prüfen;
3. keine automatische Ersatzkryptowährung wählen;
4. Ausstiegs-/Transferoptionen durch Eigentümer entscheiden;
5. Universumsänderung als neue Strategie-/Konfigurationsversion behandeln;
6. betroffene Backtests neu ausführen.

## Fehlgeschlagener Mitternachtsjob

1. Fehlerursache und betroffene Coins aus Jobbericht lesen;
2. Datenfrische und letzte geschlossene Bar prüfen;
3. sicheren manuellen Audit erneut starten;
4. Idempotenzbericht prüfen;
5. bei historischen Änderungen Backtests `STALE` belassen;
6. bei Wiederholung P2/P1-Incident eröffnen.

## Speicher knapp oder Datenbankfehler

1. Trading auf `HALTED`/Entries pausieren;
2. keine Datenbankdatei im laufenden Betrieb manuell löschen/verschieben;
3. Backup- und Integritystatus prüfen;
4. Logs gemäß dokumentierter Retention rotieren, nicht Audit-/Runartefakte entfernen;
5. bei Korruption Restore-Prozess in isolierter Umgebung ausführen;
6. vor Wiederaufnahme Backtest-Reproduktion und Reconciliation durchführen.

## Restore

1. Zielumgebung isolieren und `LIVE_DISABLED` erzwingen.
2. Backuphash prüfen.
3. DB, Migrationen, Config und Artefakte wiederherstellen.
4. Secrets separat und least-privilege einrichten.
5. Startup-Datenprüfung ausführen.
6. bekannten Backtest reproduzieren.
7. Börsen-Reconciliation trocken durchführen.
8. Restore-Bericht prüfen und schriftlich freigeben.

## Incidentabschluss

- Ursache verstanden;
- Kapital-/Orderauswirkung vollständig abgeglichen;
- Daten/Backtests bei Bedarf neu versioniert;
- dauerhafte Korrektur getestet;
- Monitoring/Test ergänzt;
- Runbook/DMS aktualisiert;
- Owner schließt Incident nachvollziehbar.
