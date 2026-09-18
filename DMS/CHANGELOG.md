# CHANGELOG

## 18.09.2026 – Slotkapazität, Drawdown-Halt entfernt und Coin-Optimierungszyklus gestartet

- Aktive V6-Slotvergabe auf `ranked_repeat`: 3×80 ist reale Kapital-/Slotkapazität; Positionszyklen und Slot-Trades getrennt ausgewiesen.
- Permanenten 20-%-Portfolio-Drawdown-Halt aus aktiver V6-Paper-/Backtestausführung entfernt; Drawdown bleibt Telemetrie, 5-%-UTC-Tagespause und technische Sicherheitsgates bleiben.
- Reproduzierter Drei-Jahres-E2E: 3×80 von 250 auf 750,79 USDC, 111 Positionszyklen / 246 Slot-Trades, max. DD 31,97 %, kein Risikohalt; 10×250 insgesamt 492 Trades und 7.269,42 USDC Endsumme.
- Neuer Auftrag: alle zehn Coins einzeln diagnostizieren/optimieren, Auswahl train/validation-getrennt, danach ein gemeinsamer versionierter Zehn-Coin-Satz und zwingender frischer 3×80-Systemtest mit identischen Profilhashes.
- DMS-Gesamtprüfung gestartet und aktuelle USDT-/`one_per_symbol`-/20-%-Halt-Widersprüche in den normativen Dokumenten korrigiert; historische datierte Nachweise bleiben erhalten.

# DMS-Changelog

## 15.09.2026 – USDT-/USDC-Kontrollvergleich und Veröffentlichung

- Alte USDT-Portfolio- und Batch-Ergebnisse mit heutigem Code exakt reproduziert,
  jeweils Baseline/Stress; gleiche spätere Fenster für USDT/USDC neu gerechnet.
- Hauptunterschied auf späteren Neustart eingegrenzt, keine Änderung der
  Strategie oder Schutzgrenzen vorgenommen. Vollständiger Nachweis in DMS18
  und backtests/v8/reports/quote-migration-audit-20260915.json.
- Vor Veröffentlichung erneut 335 Python-Tests bestanden / ein Skip, 22 UI-
  Tests bestanden sowie Ruff, mypy und TypeScript ohne Fehler.

## 15.09.2026 – Portfolio-first V9

- Zehn feste Filter-/Exit-Kombinationen, Auswahl anhand zweier Portfolio-
  Stress-Trainingsfenster, danach spätere Prüfung und Einzeltests aller Coins.
- 28 Portfolio-/80 Einzelrechnungen plus vier klar getrennte Risiko-aus-
  Diagnosen. Bester Trainingskandidat Trailing4 verfehlt Freigabekriterien.
- Kein Parameter-, Konto- oder Risiko-Wechsel im laufenden Paperbetrieb.
- Bestehenden CLI-Forschungseinstieg erweitert; 335 Python-Tests / ein Skip,
  Ruff und mypy bestanden. Berichte vollständig unter backtests/v9.

## 15.09.2026 – Slot-Ursachenprüfung

- Zwölf Offline-Kontrollrechnungen für 1/3/6/9 Slots, Risiko-aus-Diagnose und
  ADA-only mit demselben Risikomodell; kein ungeklärter Kaufkandidat.
- Echter vollständiger USDC-Paper-Replay, durchgehend und mit Restart: exakt
  28 Fills und Endkapital wie Portfolio. Keine Ein-Slot-Fehlfunktion gefunden.
- Portfolio-UI ergänzt tatsächliche maximale Belegung und Blockierzähler;
  22 UI-Tests, TypeScript und Build bestanden. Keine Handelsregel geändert.
- Verluste bleiben offen; Risikoschutz nicht gelockert, kein Echtgeldauftrag.

## 15.09.2026 – gemeinsamer Istzustand und nachvollziehbare Backtests

- Eigentümerprinzip einer zentralen Strategie samt unterschiedlichen Kontomodellen
  in DMS 06 festgehalten; Einzelbudget bleibt ausdrücklich 250 USDC.
- UI-Abgleich gegen aktive Regeln, Code, Kosten und Portfolio-Budget ergänzt;
  alte Berichte bleiben historisch. Codepatch bei laufender Instanz erfordert
  vor einer neuen Berechnung Neustart statt falscher Quelltextbescheinigung.
- 20 direkte Coin-/Kosten-Paritätstests; insgesamt 333 Python-Tests / ein Skip,
  21 UI-Tests, Ruff, mypy, TypeScript und Produktionsbuild bestanden.
- Alten 733,31-USDT-Portfolio-Endwert mit identischen Daten reproduziert.
  Laptop sichtbar neu gestartet; regulärer Portfolio- und 10×250-Lauf fertig,
  jeweils Baseline/Stress. Ergebnisse und Grenzen in DMS 18.
- Keine Coinprofile, Risiko-Limits, Paperbestände oder Livefreigaben geändert.

## 14.09.2026 – Forschungsnachtrag V8, Anwendung weiterhin 0.4.9

- Getrennte, ausdrücklich erlaubte Schwachstellenstudie für DOT/AVAX/BNB über
  den bestehenden CLI-Einstieg ergänzt; read-only Datenbank und feste Auswahlregeln.
- 88 Einzel- und acht Portfolioausführungen abgeschlossen; alle zehn bestehenden
  Profile kontrolliert. Keine Variante besteht die Übernahmebedingungen.
- 304 Python-Tests / ein Skip, Ruff und mypy bestanden. Keine aktive Strategie,
  UI, Konto- oder Liveänderung. Vollständiger Nachweis in `backtests/v8` und DMS 18.

## 1.12.0 – 09.09.2026 / Anwendung 0.4.7

- GitHub-USDC-Migration bis `ab4f83e` mit dem neuen, nicht produktiv angeschlossenen Orderadapter zusammengeführt; keine Echtgeldaktivierung.
- USDC-Startprüfung für tatsächlich verfügbare Historie repariert, gemeinsame Paper-/Backtest-Warm-up-Grenze, historische Ergebnisquote und Standard-Vault-Zuordnung korrigiert.
- Quote-eindeutiges Order-/Fill-Journal, Binance-cashgenaues `quoteQty`, UNKNOWN ohne Wiederkauf, terminale Antwort gegen konkurrierende Fehler und bestehende Ausgänge gegen Entry-Freigabeablauf abgesichert.
- DMS 20 nennt konkrete noch fehlende Runtime-/Kontoreconciler-/Restmengen-/Testnet-Arbeiten. Laptop-Deployment und Code-Stand werden ausdrücklich getrennt; der Testbutton bleibt eine gesperrte Vorprüfung.

## 1.11.0 – 08.09.2026 / Anwendung 0.4.6

- Auf Rückfrage direkter USDT-Spiegelnachweis: alter 739,52-Run exakt reproduziert; aktuelle drei Jahre 742,60, 384/384 produktive Paper-Engine-Fills identisch. Replay ab echtem Paperstart ebenfalls null Signale/Fills. Separate CLI-Defaultabweichung korrigiert: Portfolio nutzt wie UI gespeicherte Handelsgrößen, Regression 4×45 vs. Config 3×80. Kein Reset oder erzwungener Entry.
- DEC-052: USDC-Ziel und geplanter 50-USDC-Einmaltest ausdrücklich von noch aktiver V6-USDT-Runtime getrennt. Keine Konto-/Key-/Profiländerung, kein Echtgeldstart.
- V7-Validierung mit echten USDC-Kerzen, Datenverfügbarkeitsprüfung, unveränderten Coin-Profilen, Baseline/Stress, Einzel-/Portfoliofenstern und optionalem zeitraumgleichen USDT-Kontrolllauf. Quote im Manifest, Quellcodehashes, kein Umetikettieren oder Auffüllen fehlender Historie. Nur-lesender Zugriff auf Kontrollkerzen.
- Marktübersicht zeigt letzten Hixton-Trendwechsel und erklärt alte grüne Trends ohne nachträglichen Kauf. Veraltete 240-USDT-Zielgrenze und Anwenden/Verwerfen-Beschreibung im Haupt-README korrigiert.
- Ergebnisse und Auslieferungsnachweise in DMS 18 und `backtests/v7/README.md`. Positive Softwaretests ersetzen keine Robustheits-/Livefreigabe; weitere Runtime-/Ledger-/Adapter-Arbeit bleibt offen.

## 1.10.1 – 08.09.2026 / Anwendung 0.4.5

- DEC-051: feste 240-USDT-Grenze aufgehoben, Positionsbudget aus Slots × Betrag; keine automatische Änderung gespeicherter Settings oder Guthaben. UI ohne redundante Grenz-/Beispieltexte.
- Binance-Marktfilterfehler -1100 öffentlich ohne Schlüssel reproduziert und durch kompakte JSON-Coinliste korrigiert. Fehlerphase/Code mit sicheren festen Meldungen statt pauschalem Key-Rechtehinweis.
- Live-Markierung folgt ausschließlich dem Serverzustand, unbekannte Zustände nicht als aktiv anzeigen. Ein ausdrücklicher 50-USDT-Einmaltestbutton ohne Checkbox; globale Einmalbegrenzung und noch fehlende Echtgeldfreigabe unverändert.
- 207 Python-Tests bestanden, ein opt-in Vault-Test übersprungen; 15 UI-Tests, Ruff, mypy, TypeScript und Produktionsbuild erfolgreich. Kein echter Auftrag, keine Schlüsseländerung, kein neuer Backtest oder Profitnachweis. Auslieferungsnachweis DMS 18.

## 1.10.0 – 07.09.2026 / Anwendung 0.4.4

- DEC-050: Einstellungsseite vollständig in Handel, Binance verbinden und Livehandel gegliedert. Ein Übernehmen-Klick statt getippter Bestätigung, 1-USDT-Schritte, Slotzahl bis zehn bei unverändertem 240-USDT-Positionsbudget.
- Keine sichtbare Einstiegspause oder Verwerfen-Aktion; bestehende interne Stopplatches bleiben erhalten. Key-Entfernen per Ja/Abbrechen, 50-USDT-Test per Checkbox.
- Passwort-/Key-/Verbindungsfehler direkt an der jeweiligen Aktion, Submit/Enter-Unterstützung, erfolgreiche Entsperrung erst nach Sitzungsverifikation, Key-Fokus, Schutz gegen parallele Anmeldungen. Vorhandenes Betreiberpasswort nicht verändert. HTML nicht zwischenspeichern.
- 201 Python- und 13 UI-Tests; Runtime-Engine mit vier Positionen und komplette isolierte Formular-/Accountvorcheck-Kette geprüft. Keine Echtgeldfreigabe, kein Reset und keine neuen Profitbehauptungen.

## 1.9.1 – 07.09.2026 / Anwendung 0.4.3

- DEC-049: gemeinsame Handelseinstellungen statt getrennter Paper-/Live-Budgetdarstellung. Live-Zusammenfassung aktualisiert sich sofort bei Bearbeitung, erfolgreichem Speichern und Verwerfen; Entwurf ist ausdrücklich nicht aktiv. Keine Live-Anforderung mit ungespeicherten Werten.
- Ein persistenter Speicherweg `/api/trading/settings`, alter Paper-Pfad kompatibel. Live-Status liest denselben Datensatz einschließlich Einstiegspause. Freigabegrenzen serverseitig zentral; größere Slot-/Budgetentwürfe werden verständlich abgewiesen. Bisherige 3/240-Freigabe nicht still erweitert.
- „Not-Aus“ eindeutig als Einstiegspause beschriftet; ein Echtgeld-aus-Button auch für Einmaltest. Keine Zwangsverkäufe, keine Erneuerung des Einmaltests durch Entpausieren. Technische Blocker einklappbar/dedupliziert. Echte Marktzeit in Paper und Live erläutert; simulierte versus echte Ausführung klar getrennt.
- 196 Python-Tests und sieben UI-Tests bestanden, ein opt-in Vault-Test übersprungen. Keine Änderung der aktiven Coin-Profile, kein neuer Backtest, kein Paper-Reset und keine Echtgeldfreigabe.

## 1.9.0 – 07.09.2026 / Anwendung 0.4.2

- Laptop-Abnahme ergänzt in DMS 18: Neustart über den bestehenden Starter, elf Paper-Tabellen unverändert, 190 Python-Tests auch im Laptop-Projekt, 50/50 Chartabfragen und sichtbare gesperrte Key-/Test-/Live-Bereiche geprüft. Keine Echtgeldfreigabe.
- DEC-048 umgesetzt als weiterer Teilstand: Binance-Key-/Secret-Felder immer sichtbar, bis zur lokalen Entsperrung deaktiviert. Erklärung des dreistufigen Ablaufs; kein neues Design oder neuer Starter. Bei Statusfehler/Sitzungsende Eingaben leeren und sperren.
- Getrennte 50-USDT-Test-/Stopp- und Live-an/aus-Bedienelemente; tatsächliche gespeicherte Paper-Slots als spätere Live-Vorlage anzeigen. Authentifizierte Testanforderung validiert genau 50 und die Bestätigung, lehnt zusätzliche/manipulierte Felder ab und bleibt ohne produktive Anbindung 409. Kein automatischer Start nach Key-Eingabe/Kontoprüfung.
- `live/trial.py`: persistente globale Einmalberechtigung, frische gleichzeitige Zehn-Coin-Auswahl nach bestehender Rangfolge, echte Wiederverwendung von `TradePolicyGate`, eingefrorener Profilsnapshot, Restart ohne Neukauf, Exit nach Entry-Stopp, keine Freigabe eines weiteren Tests nach Abschluss. Unbekannte Orders werden weiter abgefragt, verpasste Ausstiegssignale nicht als historische Modellfills verbucht.
- Bericht enthält Order-/Trade-IDs, Original-Fillmengen und Gebühren. Offene Restmengen brauchen Klärung; Abschluss erst nach separater vertrauenswürdiger Reconciliation. Nicht bewertete BNB-Gebühren verhindern erfundene Nettozahlen. Schlüsselwechsel/-entfernung bei angeschlossenem offenen Test verhindert; UI/API verbergen dessen Status nicht als `LIVE_DISABLED`.
- **Alles zur Handelsausführung weiterhin Offline-/Fake-Börsen-Nachweis.** Produktionsadapter, dauerhafter Runtime-/Konto-Reconciler, echte Tradeanzeige und normaler Mehrslot-Livebetrieb sind nicht fertig. Kein Echtgeldauftrag oder Paper-Reset. 190 Python-Tests bestanden, ein opt-in Vault-Test übersprungen; vier UI-Tests, Ruff, mypy, TypeScript und Build erfolgreich. Fortsetzung DMS 20.

## 1.8.2 – 07.09.2026 / Anwendung unverändert 0.4.1

- DEC-047: Eigentümer entscheidet die bisher offene Testform. Genau ein Echtgeldtrade nach einem neuen qualifizierten Hixton-Signal aus zehn Coins, 50 USDT Kaufnotional mit separat ausgewiesenen Gebühren, regulärer Coin-Strategieausstieg, danach keine weiteren Einstiege und kein automatischer 3×80-Livestart.
- DMS 07/08/12/13/15/16/20 synchronisiert: globale restart-/konkurrenzfeste Einmalbegrenzung statt 50 je beliebiger Order; echter Soll/Ist-/Fill-/Gebühren-/Strategie-/Exitbericht als Abnahmeanforderung. Fehlender oder nicht ausgelöster Stop/TP wird nicht als bestanden ausgegeben.
- Aktueller Code und Runtime erneut gelesen: alle zehn V6-Profile ohne festen Take-Profit und aktiviertes ATR-Trailing; nur XRP mit zusätzlichem lokalem 1h-Schlusskurs-ATR-Stop, kein Binance-Schutzauftrag. Keine stillen Strategieergänzungen. Ein Trade kann nicht alle zehn Profile/Fehlerpfade oder Profitabilität belegen.
- **Nur Dokumentationsentscheidung, kein ausführbarer Einmaltest und keine neue Abnahme.** Kein Echtgeldauftrag, keine API-Key-Eingabe, kein Paper-Settingwechsel und kein Prozessneustart.

## 1.8.1 – 07.09.2026 / Anwendung 0.4.1

- Browser-Abnahme fand nicht unterstützte native Dialoge im eingebetteten Browser: Anwenden sowie Schlüssel-Speichern/-Entfernen verwenden jetzt Inline-Bestätigungen. Neue Text-/Passwortfelder verwenden die bestehende Optik. Kein vorzeitiges Speichern beim Öffnen der Bestätigung.
- Isolierter Orderjournal-Kern: unveränderliche 50-USDT-Kaufintents, atomare Sendebeanspruchung vor Netzwerkzugriff, nach unklarem Ausgang ausschließlich Statusabfrage, kein blinder Neuversand. Teilfills, Gebührenwährung, unveränderliche Endzustände und numerisch identische Duplikate geprüft.
- **Nur Fake-Börse, nicht an Binance oder UI angeschlossen.** Globale Testbudget-/Bestandsfreigabe, frischer Ordervorcheck, tatsächlicher Adapter und Live-/Testfreigabe bleiben offen. Ein Modulname oder ein grüner Unit-Test ist kein Echtgeldnachweis.
- 158 Python-Tests bestanden, ein Windows-Vault-Integrationstest im Standardlauf bewusst übersprungen; dieser wurde zuvor separat mit künstlichem, anschließend entferntem Eintrag bestanden. Drei UI-Tests, TypeScript, Ruff und mypy erfolgreich. Deployment-/Betriebsnachweis in DMS 18.
- Aktives V6-Paperkonto, Parameter, Risikogates und Soak bleiben erhalten. Keine Strategieoptimierung oder neue Backtestergebnisse in dieser Lieferung.

## 1.8.0 – 06.09.2026 / Anwendung 0.4.0

- DEC-046: Paper-Formular vor überschreibenden 5-Sekunden-Polls geschützt, Entwurf/Speicherstand getrennt, Anwenden/Verwerfen und Fehlererhaltung. Ganze Slots und endliche positive Beträge serverseitig validiert; 1×50 ohne Konto-/Soak-Reset geprüft.
- Live-Vorbereitung, **keine Live-Fertigstellung**: Windows Credential Manager, separates lokales Passwort, kurzlebige Sitzung, genaue Origin-/Host-Prüfung, begrenzte Secret-Eingaben, kein Cache/Secret-Echo, redigierte Netzwerkfehler.
- Getrenntes Vorbereitungs-Audit; ausschließlich allowlistbasierte GET-Abfragen an `https://api.binance.com`, keine Proxy-/Redirect-Weiterleitung und keine Ordermethode. Erlaubnis-, Guthaben-, Fremdorder-/Bestands- und grundlegende Filterprüfung; Rate-Limit und Frischegrenze.
- Live-Anforderung zeigt reale Blocker und bleibt `LIVE_DISABLED`, auch bei bestandenem Konto-Vorcheck. Echtgeld-Dispatcher, Fill-Ledger, Reconciliation, Testnet-Ausführungsprüfung und DMS-Freigabe sind weiterhin offen. Kein Übertragen von Paperpositionen, keine automatische Budgeterhöhung oder Lockerung der Risikogates.

## 1.7.1 – 06.09.2026 / Anwendung 0.3.2

- Eigentümerwunsch UI-Bereinigung: Strategie, 3×80-/10×250-/Einzeltest gemeinsam filtern; neuester passender Lauf sichtbar, ältere Nachweise eingeklappt, nichts gelöscht.
- Run-Reihenfolge nach Manifestzeit statt Kopierdatum; Testfenster und Erstellungszeit getrennt, Baseline und historischer Risikohalt eindeutig bezeichnet; lange Kartenmetadaten umbrechen.
- Veraltete V1-Festtexte auf Dokumentationsseite durch tatsächliche Runtimeversion ersetzt, GitHub-DMS-Links auf aktuellen Projektbranch korrigiert, 250/240/10-Kapitaltrennung erläutert.
- Reines UI-/Listenupdate: V6-Profile, Kosten, Slots, Risikogates und das neue Paperkonto samt Soak unverändert.

## 1.7.0 – 06.09.2026 / Anwendung 0.3.1

- DEC-045: Eigentümer verlangt V6-Aktivierung und ausdrücklich einen frischen Paperstart mit 250 USDT / 3×80; als Paper-Experiment trotz unverändert dokumentierter schlechterer Verlustfenster.
- V6-Profilmap unverändert; Config, Backtest-Vorauswahl und UI-Beschriftung synchronisiert. Kein UI-Redesign, keine Lockerung von Risiken, Live gesperrt.
- Gesicherter Offline-Befehl `paper-fresh-start`: exklusives Vollarchiv mit Integritäts-/Hashprüfung, atomarer Paperreset, Marktdaten erhalten; normales Startverhalten weiter ohne Reset.
- Tests für Sicherheitsbedingungen, Rollback und Wiederanlauf ergänzt; konkrete Laptop-Abnahme und Archivnachweis in DMS 18.

## 1.6.0 – 06.09.2026

- Auslieferungsabnahme ergänzt: Anwendung 0.3.0 über Startbot.bat gestartet, 98 Tests auf beiden Kopien, 50 Chart-API-Kombinationen, sichtbarer ETH-Chart-/Paper-Fill, Browserkonsole fehlerfrei. Backup geprüft; Konto, drei Positionen, sechs Ledgerereignisse und Soak erhalten. V2 aktiv, V6 nicht freigegeben.
- Produktions-Batch und -Portfolio mit vollständigem Commitnachweis reproduziert; Metrik-, Trade- und Equitydateien bytegleich. Erste unvollständige Metadatenläufe ausdrücklich gekennzeichnet, nicht umgeschrieben.

- Zielpräzisierung: Signalqualität und robuste Slotnutzung statt Trade-/Gewinnquoten; neue Konten 250 USDT einschließlich 10 USDT Anfangsreserve, laufende Konten unverändert.
- Vollständige hashgebundene V6-Coin-Profile durch Analyse, Paper, Einzel-/Batch-/Portfolioengine und Charts geführt; Entry-ATR/High-Close restartfest gespeichert.
- Technische Parität und Migrations-Restmengen-/Risikohalterhaltung geprüft; Profilwerte in vorhandener UI, aktive Strategie als Backtest-Vorauswahl.
- V6 gegen V2 in drei Fenstern mit Baseline/Stress und gleichem gemeinsamen 250-USDT-Kapital geprüft. Retrospektive Auswahl offen gelegt; schlechtere jüngste/ältere gemeinsame Ergebnisse verhindern eine allgemeine Robustheitsfreigabe.
- Startpfad und Ordnerdisziplin unverändert; Live weiterhin deaktiviert.

## 1.5.0 – 05.09.2026

- V5: alle zehn Coins mit unveränderter Pine-Referenz, aktiver V2 und 348 begrenzten Hixton-Parameter-/Filter-/Stopkombinationen geprüft; Auswahl nur im Training.
- Gemeinsame Forschungs-Regelentscheidung für Einzel-/Portfolioengine ergänzt, mit expliziter V5-Versionssperre, Schlusskurs-/Next-Open-Ausführung und unverändertem Identitätsverhalten der aktiven Strategie.
- Verlustdiagnose je Coin, Haltedauern, Kursrückgaben, Konzentration auf wenige Gewinner, realisierter/offener PnL und ältere Rückschritte dokumentiert.
- Vollständiges Kandidatenportfolio und zusätzlich nur XRP im 3×80-Konto geprüft; XRP-Nachbarsensitivität transparent als nachträgliche Diagnose gekennzeichnet. Keine Aktivierung wegen fehlender Mehrfenster-/Portfolioverbesserung.
- 86 Tests bestanden; Ruff/mypy ohne Befund. Die Hauptmesswerte wurden zweimal identisch erzeugt. Keine UI-/Pine-/Config-/Paper-Ledgeränderung.
- Ergebnisse ausschließlich unter `backtests/v5`, große Rohberichte weiter ignoriert; ein Starter und bestehende DMS-Struktur beibehalten. DEC-042 und Übergabehinweise für GPT/Codex nachgezogen.

## 1.4.0 – 05.09.2026

- Permanente Stundenverzögerung der Closed-Bar-Synchronisierung beseitigt; Watchdog repariert fehlende Stunden unabhängig vom Close-Event.
- Paper auf tatsächliches Folge-Open umgestellt, Modellzeit und Verarbeitungszeit getrennt, UTC-Zeitscheiben synchronisiert, Dust dauerhaft bewertet. Alte Paperereignisse bleiben unverändert; technischer Soak wird einmalig neu begonnen, Positionen bleiben erhalten.
- Paper-/Portfolio-Produktionsparität mit Kurslücken, Mengenrundung und Restart geprüft; nicht ausführbare Kandidaten belegen keinen Slot. UI-Portfolio verwendet aktuelle Slot-/Notionaleinstellungen und ein datenbasiertes Testende.
- Bestehende UI ohne Redesign verbessert: Freie Slots, verständlicher Wartezustand, frische offene Kerzen, korrekt gerasterte Paper-Fills und wiederverwendete Marker.
- Begrenzte coinindividuelle V4-Untersuchung und echte sukzessive Nachkaufhypothese gerechnet; keine Aktivierung wegen schwacher jüngster Periode. Positive Dreijahreswerte bleiben von kontinuierlicher Profitabilität getrennt.
- Prüfstand 74 Tests; Ruff, mypy, TypeScript und UI-Build bestanden. Live bleibt deaktiviert.
- Laptop-Abnahme 0.2.1 abgeschlossen: Startbot.bat, geprüftes SQLite-Backup, unveränderte drei Positionen/sechs Ledgerereignisse, 50 Chart-API-Prüfungen, sichtbare Chart-/Fill-/Backtestabnahme und zwei neue UI-Backtests. Details und Hashes in DMS 18.

## 1.3.1 – 02.09.2026

- Kontrollierte V1→V2-Paperaktivierung mit Sicherungshash, DOT-Migrationsschluss, V2-Start-Equity, getrenntem Session-PnL und neu gestartetem Soak dokumentiert.
- V2-Betriebsabnahme abgeschlossen: zehn valide Märkte, 50/50 Coin-/Zeitraumcharts, sichtbare Signal-/Paper-Fill-Daten, korrekte Strategie-/Ledgeranzeige und leere Browser-Fehlerkonsole.
- Dauerhaft falschen `DEGRADED`-Status nach erfolgreichem Websocket-Reconnect behoben; fremde Daten-/Auditfehler bleiben erhalten.
- Prüfstand auf 68 grüne Python-Tests angehoben; Ruff und mypy weiterhin ohne Befund. Live bleibt `LIVE_DISABLED`.

## 1.3.0 – 02.09.2026

- V2 nach ausdrücklicher Eigentümerentscheidung `DEC-037` vom Forschungskandidaten zur aktiven Paperstrategie erhoben; Live bleibt `LIVE_DISABLED`.
- Exakten V1/V2-240-USDT-Vergleich mit identischem 3×80-Risikomodell dokumentiert: V2 übertraf V1 im aktuellen Fenster normal und unter Stress.
- Persistente Paper-Strategie-Session, versionierte Positionen/Ereignisse, atomare V1→V2-Migration, Soak-Neustart und Fail-closed-Konfliktprüfung ergänzt.
- Grundprinzip `DEC-038` festgelegt: bestbelegte zulässige Verbesserung nach vollständigem Vergleich und expliziter Entscheidung übernehmen; kein automatisches Umschalten und keine Live-Freigabe durch Backtest.
- Gewünschte Mehrfachbelegung desselben Coins als V3 `ranked_repeat` getestet und wegen frühem Konzentrations-/Risikohalt verworfen; aktive V2 bleibt `one_per_symbol`.
- UI ohne Redesign um aktive Strategie, Strategie-Session, PnL seit Wechsel sowie Positionsversion/Slotzahl ergänzt.
- Konfiguration auf aktive V2 synchronisiert; Backtest-UI kennzeichnet V2 aktiv, V1 historisch und V3 verworfen.
- Prüfstand auf 67 grüne Python-Tests sowie 34 mypy-geprüfte Source-Dateien angehoben; TypeScript und Produktionsbuild bestanden, Betriebsabnahme folgt nach lokalem V2-Neustart.

## 1.2.0 – 01.–02.09.2026

- Vollständigen, vom Eigentümer übermittelten Pine-v6-Code einmalig unter `strategy/pine/` aufgenommen, gehasht und als V2-Referenz dokumentiert; V1 bleibt unverändert.
- Pine-v6-Semantik in der Strategieengine getrennt ergänzt und mit einer unabhängigen Golden-Implementierung getestet.
- V1-Verlustursache analysiert: kurze Trades unter 72 Stunden verloren über alle zehn Coins in Summe; mehr Trades allein deshalb verworfen.
- V2-Forschung sauber unter `backtests/v2` angelegt: 1.280 breite Kandidaten, 75 Mehrfenster-Finalisten und 48 Nachbarvarianten dokumentiert.
- Gemeinsamen Kandidaten 6/20/SMA8/ATR60/Band3,8 als `RESEARCH_ONLY` ausgewählt; aktuelles Fenster stark, ältere Verlustfenster ausdrücklich festgehalten, keine Paperumschaltung.
- 250→500 USDT je Coin als gewünschtes, aber nicht garantiertes Optimierungsziel präzisiert; höhere Tradezahl bleibt der Robustheit nach Kosten untergeordnet.
- Telegram auf ausdrücklichen Eigentümerwunsch aus Pflicht- und Live-Gates entfernt; lokale UI und strukturierte Logs sind die verbindlichen Überwachungskanäle.
- Kombinierte Backtest-Drawdown-Aggregation gegen abweichende Provider-Close-Millisekunden korrigiert und per Regressionstest gesichert.
- V1/V2 über denselben CLI-Einstieg und in der bestehenden Backtest-UI getrennt auswählbar gemacht; V2-Manifeste enthalten Parameter, Pine-Referenz, Semantik und `paper_approved: false`.
- Vollständigen V2-10er-Batch bytegleich wiederholt und Kernartefakt-Hashes im V2-Bericht fixiert; damaliger Prüfstand 56 grüne Python-Tests.
- Gemeinsamen 240-USDT-Spiegellauf mit drei festen 80-USDT-Slots als eigenen CLI-/UI-Modus implementiert, zweimal bytegleich reproduziert und ehrlich gegen das gleichgewichtete Buy-and-Hold-Portfolio ausgewiesen; damaliger Prüfstand 59 grüne Python-Tests.
- Vor-Live-Prüfung fand und schloss die fehlende 5-%-Tagesverlust-/20-%-Drawdown-Parität zwischen Paperledger und Portfolio-Backtest; korrigierte Risikospiegel und frühe Halts in älteren Segmenten dokumentiert.
- Backtest-UI bindet Detailtabelle nun an denselben neuesten Run wie die Karte, kennzeichnet Portfolio/Batch/Einzeltest sowie `RISIKOHALT` sichtbar und behält die abgenommene Optik bei.
- Band-4,0-Challenger trotz starkem aktuellem Fenster wegen klarer älterer Verluste verworfen; aktueller Prüfstand 61 grüne Python-Tests.
- Zentrale Arbeitsübergabe für Codex/GPT ergänzt, den 3×80-Risikospiegel verbindlich statt optional benannt und `1m = ein Monat` eindeutig von den lokal automatisch geladenen `1h`-Kerzen getrennt.

## 1.1.0 – 01.09.2026

- Dokumentationsfreeze nach ausdrücklichem Bauauftrag in die Implementierungsphase überführt.
- Genau eine `Startbot.bat` als Windows-Komfortstarter beschlossen; einziger technischer Einstieg bleibt `src/main.py`.
- README und Ordnerregel um verbindliche Sauberkeits-, Build- und Aufräumregeln ergänzt.
- Implementierter V1-Stand für Strategie, Binance-Daten, SQLite, Backtest, 24/7-Paper-Runtime und lokale TypeScript-UI dokumentiert.
- Finaler Drei-Jahres-Batch `68e84b25-91f9-4faa-9a65-a6699b8bd7d5`, bytegleicher Reproduktionslauf und ETH-Einzeltest mit echten Binance-Spot-Daten dokumentiert.
- Gate B mit 51 automatisierten Tests, zehn vollständigen Datenaudits und reproduzierbaren Ergebnis-Hashes geschlossen; positive Baseline, negativer Stressfall und hohe Drawdowns ausdrücklich festgehalten.
- Windows-Kaltstart um eine fest gepinnte IANA-Zeitzonendatenbank ergänzt; schnelle Coin-/Zeitraumwechsel gegen veraltete Chartantworten abgesichert.
- Vom Eigentümer freigegebene V1-Optik als `DEC-033` eingefroren; weitere Betriebsfunktionen müssen das bestehende Erscheinungsbild unverändert weiterverwenden.
- Paper-Checkpoints gegen Überschreiben beim Neustart gehärtet; verpasste Bar-Closes werden nachgeholt und der 30-/720-/20-Soak-Fortschritt wird persistent und ohne Layoutänderung angezeigt.
- Live-Ausführung bleibt bis zu Paper-Soak, Telegram-, Backup-/Restore-, Account- und Eigentümerfreigabe technisch gesperrt.

## 1.0.0 – 31.08.2026

- `HIXTON-SPEC-1.0` als vollständige normative V1-Strategie festgelegt: Formel, `1h`-Timeframe, Parameter, 400-Bar-Warm-up, Initialzustand, Cross-, Bar-Close- und Next-bar-Regeln.
- Sauber getrennt: implementierbare Projektspezifikation ja, unbelegte Identität mit proprietärem Hersteller-Pine nein.
- Backtestkosten verbindlich auf 15 bp je Seite in der Baseline und 40 bp je Seite im Stressfall festgelegt.
- Long-only, 3×80-USDT-Slots ohne automatisches Compounding und deterministische Slotpriorisierung in Anforderungen, Config und Traceability synchronisiert.
- Stale-Data-, Preisabweichungs-, Tagesverlust-, Drawdown-, Order-Timeout- und Teilfill-Grenzen geschlossen.
- Paper-Soak, Telegram-Alarmierung, dedizierter Bot-Account, localhost-UI, Windows-Service und Backup-/Restore-Retention festgelegt.
- Öffentliches GitHub-Repository bestätigt; fremder Pine-Source ohne Rechte ausgeschlossen, keine Open-Source-Lizenz stillschweigend angenommen.
- Entscheidungslog ohne kritische P0-/P1-Lücke geschlossen und DMS-Freigabegates von späteren Implementierungs-/Testnachweisen getrennt.
- Keine Botimplementierung und keine Backtestergebnisse erzeugt.

## 0.3.1 – 31.08.2026

- GitHub ausdrücklich als zentrale versionierte Projektablage festgeschrieben; OneDrive ist die lokale Arbeitskopie.
- Frühere Formulierung „Upload erst bei Freigabereife“ entfernt; 99 % bleibt ein separates Releasegate.
- `DEC-029` bestätigt: Slotvergabe nach stärkstem normalisiertem Hixton-Ausbruch mit festem Tie-Break.
- `DEC-030` bestätigt: 80 USDT je Slot bleiben fest bis zu einer bewussten UI-Änderung; kein automatisches Compounding.
- Verbleibende Kernblocker auf Pine-Referenz, Trading-Timeframe und Kostenmodell verdichtet.

## 0.3.0 – 31.08.2026

- `README.md` als einzige zentrale Startdatei festgelegt.
- Einziger späterer technischer Einstieg `src/main.py`; Backtest, Paper, Live und UI werden Modi statt getrennte Startprogramme.
- Reale Repository-Struktur ergänzt.
- Backtests verbindlich unter `backtests/v1`, danach `v2`, `v3`; neue Runs innerhalb einer Methodik überschreiben keine alten Ergebnisse.
- Secret-, Runtime- und Datenpfade über `.gitignore` abgesichert.

## 0.2.0 – 31.08.2026

- Binance Spot als Börse/Datenquelle festgelegt.
- Initiales Universum auf BTC, ETH, BNB, SOL, XRP, ADA, LINK, AVAX, DOT und DOGE gegen USDT festgelegt und aktuelle Binance-Handelbarkeit/Historienlänge geprüft.
- Zwei Systeme getrennt: 24/7 Paper-/Live-Vorbereitung mit 240 USDT und 3×80-USDT-Slots; Backtest-Labor mit 10×250-USDT-Batch und frei wählbarem 250-USDT-Einzeltest.
- Festes 250-/500-USDT-Performanceziel entfernt; Signalparität und ehrliche Nettoperformance getrennt.
- Maximale Nettoperformance als Primärziel, Tradezahl als Sekundärziel dokumentiert.
- GitHub-Repository, Agenten-Branches, Review-, Secret- und späteres Uploadgate dokumentiert.

## 0.1.0 – 31.08.2026

- Eingangsdatei inventarisiert und gehasht.
- Vollständige DMS-Struktur für Scope, Strategie, Märkte, Kapital, Daten, Backtest, Execution, UI, Architektur, Betrieb, Sicherheit, Tests und Konfiguration angelegt.
- Nutzeranforderungen zu zehn Coins, 250-USDT-Einzeltests, drei Jahren, Chartzeiträumen, Startup-Sync und täglichem Update abgebildet.
- Kritische fehlende Quellen und Entscheidungen zentral dokumentiert.
- Risikoregister und konkretes Betriebs-/Recovery-Runbook ergänzt.
- Keine Botimplementierung und keine erfundenen Backtestergebnisse erstellt.
