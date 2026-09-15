# 08 – UI-/UX-Spezifikation

Aktueller Vorrang: **DMS 1.12.0 / DEC-053 / Anwendung 0.4.7**. Der integrierte Code verwendet USDC (250 Modellstart, Standard 3×80; später genau ein 50-USDC-Test). Alte datierte USDT-Anforderungen/Ergebnisse sind Historie, keine umgerechneten USDC-Nachweise. Runtime- und Laptop-Deployment sind getrennt zu prüfen. Kein Echtgeldstart: technischer Restarbeitsplan in [DMS 20](20_BETRIEBSRUNBOOK.md), tatsächlicher Testnachweis in [DMS 12](12_TESTS_ABNAHMEKRITERIEN.md). Bestehende Live-Sicherheitsgates bleiben wirksam.

## Ergänzung 0.4.6 / DEC-052

Jede Marktkarte zeigt den letzten Indikator-Trendwechsel mit Kauf/Verkauf und Zeitpunkt in Europe/Berlin. Bei grünem Trend ohne Position erklären: alter Trend ist kein neuer Kauf; historische Signale werden nicht nachgehandelt. Kein Signal ist kein Fillnachweis. Ohne geladene Signalhistorie unbekannt/noch kein Wechsel anzeigen, nicht behaupten, es habe niemals einen gegeben.

USDC-V7 bleibt ein separater Validierungsstand außerhalb der aktiven Strategieauswahl. Bestehende V6-/USDT-Preis-, Konto- und Einstellungslabels nicht vor der tatsächlichen Ledger-/Runtime-Migration umetikettieren. Geplanter künftiger Einmaltest 50 USDC; bisheriger USDT-Livebereich bleibt bis zur vollständigen Umsetzung gesperrt. Layout und übrige Bedienung unverändert.

## Gültiger Einstellungsablauf ab 0.4.5 / DEC-051

1. **Handel:** maximal offene Trades (1–10), USDT je Trade (Schritt 1), ein Button „Übernehmen“. Gewähltes Positionsbudget = Slots × Betrag, keine feste 240-USDT-Grenze, kein redundanter Grenz-/Beispieltext. Kein Verwerfen, keine sichtbare Einstiegspause, keine getippte Bestätigung. Entwurf bleibt bei Polling und Fehler erhalten; erfolgreiche Serverantwort aktualisiert beide Anzeigen. Speichern erzeugt kein neues Guthaben.
2. **Binance verbinden:** echtes Formular mit Enter-Unterstützung; Passwort und Wiederholung nur bei erstmaliger Einrichtung. Fehler/Erfolg direkt daneben. Erfolg erst nach bestätigtem Sessioncookie; Key/Secret danach freigegeben und fokussiert. Key speichern, Verbindung prüfen. Schlüsselverwaltung einklappbar, Entfernen mit Ja/Abbrechen. Keine automatische Passwort-Recovery oder Sicherheitsumgehung.
3. **Livehandel:** gemeinsame gespeicherte Handelsgröße, Live an/aus, kompakte Rückmeldung. Nur bestätigtes Live-an wird grün; Live-aus markiert seinen eigenen Button (Text und aria-pressed). Unbekannter Status markiert keinen, Einmaltest separat. Einmaltest und technische Freigabegründe einklappbar. Ein ausdrücklich beschrifteter Button fordert genau einen 50-USDT-Echtgeldtrade an, keine zusätzliche Checkbox und kein Dauerbetrieb. Echtgeld bleibt wegen fehlender produktiver Anbindung gesperrt.

Auf Desktop zwei Formularspalten, darunter Live; schmale Fenster einspaltig. Bestehende Farben/Typografie außerhalb der Einstellungsseite unverändert. Seite wird mit Cache-Control no-store ausgeliefert; bereits geöffnete alte Tabs müssen einmal neu geladen werden. Nachfolgende 0.4.3-/0.4.2-UI-Beschreibungen sind Historie und durch diesen Ablauf ersetzt.

**Aktuell 0.4.3 / DEC-049:** „Handelseinstellungen · Paper & Live“ enthält genau eine Slot-/Positionsgrößen-Eingabe und eine „Einstiegspause“. Nur ein persistenter Datensatz; keine unabhängige Live-Slotkopie. Die Live-Zusammenfassung außerhalb des gesperrten Key-Fieldsets wird aus demselben UI-Zustand aktualisiert: gültig gespeichert, ungespeicherter Entwurf oder Speichern läuft. Änderungen sind sofort sichtbar, aber erst nach erfolgreichem ANWENDEN wirksam. Live-Anforderung bei Entwurf/Speicherung/Einstiegspause blockieren. Ungültige 4-/5-Slot-Eingaben klar als außerhalb der derzeitigen Freigabe 3/240 kennzeichnen; nie stillen Rückfall als erfolgreiche Speicherung ausgeben. Grenzen kommen von der API.

Die redundante Einmaltest-Stopp-Schaltfläche entfällt: „Live aus · auch Einmaltest-Einstiege stoppen“ verwendet denselben Entry-Stopp, nie Liquidation. Gemeinsame Einstiegspause sperrt zusätzlich Paper-Einstiege; vorhandene Positionen dürfen regulär auslaufen. Entpausieren ist kein Live-Start und erneuert keine Einmalberechtigung. Der separate 1×50-Test bleibt eine absichtliche Budgetausnahme, keine zweite editierbare Konfiguration. Key-Felder weiter sichtbar; technische Freigabegründe einklappbar und doppelte Meldungen dedupliziert. Paper und Live nutzen Echtzeit, nur Backtests historische Zeit. Nachfolgende 0.4.2-Beschreibungen sind historische Teilstände; echte Orderausführung bleibt offen.

Implementierungsstand 0.4.2 / DEC-048: API-Key/Secret und Test-/Liveaktionen bleiben sichtbar in einem deaktivierten Fieldset; Entsperren hebt nur die Eingabesperre auf. Die alte Ausblendung entfällt. 50-USDT-Teststart benötigt lokale Session und ausdrückliche Bestätigung; Produktionsfreigabe fehlt, daher weiterhin 409 ohne Order. Einmaltest-Stopp und Live-aus unterscheiden Entry-Sperre von Liquidation; gespeicherte Paper-Slots werden als spätere Vorlage gezeigt. Keyänderung/-entfernung bei einem angeschlossenen unvollständig abgeglichenen Test gesperrt. Offen: produktiver Test-/Mehrslotbetrieb und echte Positionen/Charts/Abschlussberichte. Die folgende DEC-047-Spezifikation ist nicht allein durch diese UI fertig erfüllt.

DEC-047 (geplant, **nicht in 0.4.1 verfügbar**): gesonderte Aktion „Einmaltest · 50 USDT · Echtgeld“ mit ausdrücklicher Budget-/Gebühren-/Strategiebestätigung. Zustände: wartet auf neues Signal, Kauf ungeklärt/in Ausführung, Position offen, Ausstieg in Ausführung, beendet oder klärungsbedürftig. Ein laufender Echtgeldtest darf nicht durch den abgeschalteten 24/7-Livemodus verdeckt werden. Genau ein logischer Trade, danach keine neuen Entries; Restart/Doppelklick ändern das nicht. Im bestehenden Positions-/Orderbereich echte Fills mit Strategieprofil, Soll/Ist-Budget, Gebühren, Kontobewegungen und differenziertem Exitnachweis anzeigen. Nicht konfigurierte Stop-/Take-Profit-Regeln heißen „nicht konfiguriert“, nicht „bestanden“. Keine Behauptung, dass 1×50-Paper-Settings bereits einen echten Einmaltest starten. Vollständiger Vertrag DMS 20.

Browser-Abnahme 0.4.0: Bestätigungen erfolgen **in der Seite**, nicht über `window.prompt/confirm`. „ANWENDEN“ öffnet bei Bedarf ein beschriftetes Eingabefeld mit exakten Paperwerten; Wort eintippen und erneut bestätigen. Änderungen an Slots/Notional/Not-Aus verwerfen eine alte Bestätigung. Schlüsselaktionen benötigen entsprechend SPEICHERN oder ENTFERNEN im geschützten Bereich. Damit bleibt die Bedienung auch in Browserumgebungen ohne native JavaScript-Dialoge möglich.

Ergänzung 1.8.0 / Anwendung 0.4.0: Paper-Settings sind ein expliziter Entwurf. Automatische Statusantworten dürfen Felder während Bearbeitung, Bestätigungsdialog und Speicherung nicht überschreiben. Abbrechen/Fehler erhalten den Entwurf; Erfolg übernimmt die Serverantwort; „Verwerfen“ stellt den aktuellen Speicherstand wieder her. Ein separater Hinweis zeigt den tatsächlich aktiven Speicherstand. Verspätete Statusantworten werden verworfen. Not-Aus folgt derselben ausdrücklichen Speicherung. Änderungen gelten nur für neue Entries, nicht rückwirkend; Konto und Soak werden nicht zurückgesetzt.

Darunter bleibt die bisherige Optik für **Live-Vorbereitung** erhalten: eigenes lokales Passwort (nicht Binance-Login), 15-Minuten-Sitzung, maskierte API-Key-/Secret-Felder, Speichern/Ersetzen/Entfernen, rein lesende Kontoprüfung, Live-Anforderung und Live-aus. Passwort und Schlüssel werden nie im Browserstorage gehalten; nach Senden/Sperren werden die Eingaben geleert. Fehlender Key führt zur Eingabeaufforderung. Gespeicherter Key zeigt nur Status/Fingerprint/Datum im entsperrten Bereich. **Der Live-Knopf meldet 409 mit konkreten Blockern, solange Orderadapter/Abnahmen fehlen; kein grüner Fake-Live-Status.** Live-aus bestätigt in dieser Vorbereitungsstufe ausschließlich den bestehenden ausgeschalteten Zustand; es storniert/verkauft nichts. Späteres Exit-only/Flatten ist noch zu implementieren und separat zu testen.

Ergänzung 1.7.1 / Anwendung 0.3.2: Backtestliste und Ergebnistabelle filtern gemeinsam nach gewählter Strategie UND Testart (3×80, 10×250 oder exakt ein Coin). Standardmäßig erscheint nur der neueste passende Lauf; bis zu 24 weitere bleiben eingeklappt erreichbar. Sortierung nach Manifest-Erstellungszeit, nicht Datei-Kopierdatum; Filter vor Anzeigegrenze. Bei einem Auswahlwechsel werden alte Werte sofort entfernt und verspätete Antworten verworfen. Kein Löschen von Runartefakten. Karten nennen Testfenster, Erstellungszeit, ausdrücklich Baseline und historischen Risikohalt; dieser ist kein aktueller Paperstatus. Dokumentationskarte bezieht die tatsächliche Strategie aus der Status-API, GitHub-Verweise nutzen den aktuellen Projektbranch `codex/build-foundation-v1`, nicht den alten `main`-Stand. Optik bleibt erhalten; lange Metadaten umbrechen lesbar.

Ergänzung 06.09.2026: Optik und Navigation bleiben bestehen. Jede Marktkarte zeigt ihre tatsächlichen VIDYA-/Momentum-/SMA-/ATR-/Bandwerte und Zusatzfilter. Die Backtestauswahl wird beim Laden aus der aktiven Paperstrategie vorbelegt; ein manuell gewählter Vergleich verändert Paper nicht. V6 ist gemäß DEC-045 als Paper-Experiment aktiv, nicht durch Auswahl eines Backtests. Qualifizierte hypothetische Coin-Signale und echte Ledger-Fills sind getrennt: Slots, Cash und Risikogates können ein Signal blockieren; Stopmarker heißen STOP. Der grüne Trend allein ist keine erneute Kaufaufforderung.

## UI-Grundsätze

- Die UI zeigt Fakten und Status, keine Renditeversprechen.
- `BACKTEST`, `PAPER`, `LIVE_DISABLED` und `LIVE` sind permanent sichtbar.
- Datenzeit, letzte abgeschlossene Kerze und Live-/vorläufiger Status sind sichtbar.
- Kritische Aktionen benötigen Bestätigung; Lesen und Navigieren nicht.
- Rot/Grün wird zusätzlich durch Text/Icon ergänzt, damit Farbe nie allein Bedeutung trägt.
- Deutsche Oberfläche; technische IDs dürfen kopierbar sein.

## Visueller Freeze V1

Die am 01.09.2026 abgenommene Desktop- und Mobiloptik ist gemäß `DEC-033` eingefroren. Funktionale Ergänzungen dürfen Inhalte in den bestehenden Ansichten präzisieren, aber keine neue Designsprache, parallele Navigation, zusätzlichen Starter oder unverbundene Sonderseite einführen. Neue Statuswerte nutzen die vorhandenen Karten-, Tabellen-, Badge- und Typografieregeln.

Der Header und die Systemkarte zeigen immer die tatsächlich konfigurierte Paperstrategie samt Aktivierungszeit und PnL seit diesem Strategiewechsel. Seit `DEC-045` ist V6 aktiv; die Backtestauswahl nennt sie `V6 · Paper-Experiment / Coin-Mix` und V2 die vorherige Referenz. Die Backtestauswahl kennzeichnet V1 als Historie und V3 als verworfenen Versuch; eine Backtestauswahl schaltet Paper niemals um.

## Hauptnavigation

1. Übersicht
2. Chart & Signale
3. Positionen & Orders
4. Backtests
5. Datenqualität
6. System & Logs
7. Einstellungen
8. Dokumentation/Versionen

## Übersicht

Kopfbereich:

- Botname und Version;
- Modus;
- Gesamtstatus `HEALTHY/DEGRADED/HALTED`;
- Börsen-/Datenverbindung;
- letzte Synchronisation;
- aktuelle UI-Zeitzone;
- Not-Aus.

Zehn Marktkarten zeigen:

- Symbol;
- aktuellen/letzten Preis mit Zeit;
- Trend `UP/DOWN/UNINITIALIZED`;
- letztes Signal und Signalkerzenzeit;
- Position `FLAT/LONG/UNKNOWN`;
- Positionsmenge, Einstieg, Marktwert;
- unrealisierten PnL;
- isoliertes Cash und Equity;
- Datenfrische und Lückenstatus;
- offene/ungeklärte Order.

## Chart & Signale

Pflichtsteuerungen:

- Coin-Auswahl;
- Zeitraum: **Heute**, **1 Woche**, **1 Monat**, **1 Jahr**, **3 Jahre**;
- sichtbarer Daten-/Trading-Timeframe;
- Zeitzone;
- Overlays ein/aus.

Pflichtdarstellung:

- Candlesticks;
- VIDYA-Trendlinie gemäß `HIXTON-SPEC-1.0`;
- obere und untere ATR-Bänder;
- farbige Trendsegmente/Füllung;
- Kauf- und Verkaufssignalmarker;
- Einstieg/Ausstieg/Fills;
- offene Position;
- Volumen (`optional sichtbar`, Daten werden dennoch gespeichert);
- Lücken oder nicht verfügbare Bereiche.

Die laufende Kerze erhält z. B. gestrichelte Kontur und Label „vorläufig“. Auf ihr darf kein bestätigter Signalmarker stehen.

### Zeitraumverhalten

| Auswahl | Semantik |
|---|---|
| Heute | 00:00 bis jetzt in gewählter UI-Zeitzone |
| 1 Woche | rollierende letzte 7 × 24 Stunden |
| 1 Monat | rollierende letzte 30 Tage |
| 1 Jahr | rollierende letzte 365 Tage |
| 3 Jahre | rollierende letzte 3 Kalenderjahre bis jetzt |

Standardauswahl ist **1 Monat**. Heute/1W/1M verwenden native `1h`-Bars; 1J wird standardmäßig zu `4h`, 3J zu `1d` aggregiert. Eine verfügbare Auflösung darf manuell gewählt werden. Indikatorwerte und Signalmarker stammen stets aus der nativen `1h`-Strategie; die UI berechnet aus aggregierten Bars keine neuen Signale. Kalenderwoche/-monat sind ausdrücklich keine Signal- oder Datenaggregationssemantik.

## Positionen & Orders

Tabellen für:

- aktuelle Positionen;
- offene Orders;
- abgeschlossene Orders/Fills;
- blockierte Intents;
- Reconciliation-Differenzen.

Drill-down von jedem Eintrag zu Signal, Signalkerze, Parametern, Börsenantwort und Logs. Statusfilter und CSV-/JSON-Export sind vorgesehen; Exporte enthalten keine Geheimnisse.

## Backtestseite

Startmaske:

- `Alle 10 Coins`: zehn isolierte Läufe mit je 250 USDT;
- `Einzeltest`: genau ein auswählbares Paar, etwa ETH/USDT, mit 250 USDT;
- `Gemeinsames 3×80-Portfolio`: 250 USDT gemeinsamer Cashpool (10 USDT Startreserve) mit höchstens drei festen 80-USDT-Slots;
- Zeitraum, Timeframe, Kostenmodell und Strategieversion vor Start sichtbar;
- Backteststart löst niemals eine Börsenorder aus.

Kopf des Reports:

- Run-ID, Status und Erstellzeit;
- Strategie-/Konfigurations-/Datenhash;
- Zeitraum und Warm-up;
- Börse/Datenquelle;
- Gebühren-, Slippage- und Fillmodell;
- zehn Coins und Startkapital;
- Warnung, falls Ergebnis veraltet oder nicht reproduzierbar ist.

Darstellung:

- Kennzahlkarten;
- Equity-/Drawdown-Chart;
- Vergleich mit Buy-and-Hold;
- Monatsrendite-Tabelle;
- Trades und Kosten;
- je Coin Ampel „netto positiv/netto negativ/nicht bewertbar“ ohne Gewinnversprechen;
- Portfolioaggregation ohne schlechte Coins auszublenden.
- Spiegelportfolio als eigene Ergebniszeile mit Start, Ende, Rendite, Trades, Drawdown und gleichgewichtetem Buy-and-Hold; es darf nicht als 10×250-Batch beschriftet werden.

## Datenqualität

Pro Coin:

- verfügbare Zeitspanne;
- letzte geschlossene Kerze;
- erwartete/vorhandene Bars;
- Lücken, Duplikate, Quarantänefälle;
- letzter erfolgreicher Startup-/Mitternachtsaudit;
- Datenversion;
- Button für sicheren erneuten Audit, nicht für willkürliche Datenmanipulation.

## System & Logs

- Komponentenstatus;
- Scheduler mit nächstem/letztem Lauf;
- Stream-/REST-Status;
- Datenbank/Backup;
- Warnungen und Incidents;
- filterbare strukturierte Logs;
- Korrelations-ID kopierbar;
- klare Hilfetexte für `DEGRADED` und `HALTED`.

## Einstellungen

- Strategieparameter im Livebetrieb standardmäßig schreibgeschützt;
- jede Änderung erzeugt neue Konfigurationsversion und invalidiert betroffene Backtests;
- Secrets werden nur gesetzt/ersetzt, nie im Klartext zurückgelesen;
- Live-Aktivierung erfordert alle Freigabegates, Bestätigung und optional eine Bestätigungsphrase;
- Änderungen zeigen Diff, Zeitpunkt, Benutzer und Begründung.
- Paper-/Live-Positionsgröße startet bei 80 USDT, Slotanzahl bei drei; beide sind später änderbar.
- UI validiert `Slotanzahl × Zielnotional` gegen verfügbares/konfiguriertes Gesamtkapital und aktuelle Binance-Mindestwerte.
- Änderungen wirken nur auf künftige Entries; bestehende Positionen werden nicht automatisch angepasst.
- Einstellungen zeigen die unveränderlichen Risikobaselines: 5 % Tagesverlustpause, 20 % Max-Drawdown-Halt, 25 bp maximale Preisabweichung, 10 Sekunden bis `UNKNOWN` und 30 Sekunden Teilfill-Restfrist.

## Zustände ohne Daten

Die UI muss Loading, leer, stale, teilweise verfügbar, Fehler und Berechtigungsproblem unterscheiden. `0` darf nicht als Ersatz für „unbekannt“ erscheinen.

## Akzeptanz für Chartperformance

Präzisierung 05.09.: Der Zähler heißt **Freie Slots** (0 von 3 bedeutet drei belegte Slots). Marktkarten unterscheiden „Position läuft“ von „Wartet auf neuen Kauf“; ein alter grüner Trend ist kein neuer Kaufauftrag. Frische Streamkerzen aktualisieren Preise und den sichtbaren Chart, sind als „letzte Kerze live/offen“ gekennzeichnet und erzeugen keine Signale. Nach 90 Sekunden ohne frisches Symbolupdate fällt die Anzeige auf bestätigte Daten zurück. Paper-Fills werden nach ihrer gespeicherten Fillzeit auf die jeweilige Anzeigenkerze gerastert. Automatische Aktualisierung erhält den Zoom und verwendet dieselbe Markerinstanz. Farben, Layout und Navigation bleiben unverändert.

- Wechsel zwischen Zeiträumen blockiert die Bedienung nicht dauerhaft.
- Drei Jahre werden downsampled dargestellt, ohne die gespeicherten Backtestdaten zu verändern.
- Marker bleiben zeitlich korrekt.
- Tooltip zeigt OHLCV, Indikatorwerte, Trend, Barstatus und Zeitzone.
