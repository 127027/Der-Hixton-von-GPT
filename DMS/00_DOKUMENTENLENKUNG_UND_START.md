# 00 – Dokumentenlenkung und Start

## Aktuell: DMS 1.14.0 / Anwendung 0.4.9, DEC-055

Ein gemeinsamer Entscheidungsweg für Backtest/Paper/Live, unterschiedliche Daten- und Ausführungsschnittstellen. Zentrale Signalpriorität ergänzt die bereits gemeinsame Coin-Policy. Einmaltest-Laufzeit ist jetzt angeschlossen, Ausgangsbestand-/Fill-Saldovergleich implementiert; Produktion weiterhin direkt vor Orderversand gesperrt. Konkrete Abgrenzung: 292 Python-Tests/19 UI-Tests, zehn Offline-Durchläufe mit echtem Adapterparser und abgeglichenen Paperentscheidungen sind keine externe Binance-Abnahme. Markt-/Preis-/Mengenfreigaben, handelbare Restmengen, vollständige Fremdorderprüfung und Testnet/Betriebsnachweis bleiben offen. Neue Backtest-Manifeste protokollieren Python-Quelltext-Hash und Prüfbereich. DMS 20 enthält den aktuellen Arbeitsstand; ältere Aussagen „kein Runtime-Anschluss“ sind dadurch teilweise überholt, nicht die Echtgeldsperre.

## Historie: DMS 1.13.0 / Anwendung 0.4.8, DEC-054

Sichtbarer Betrieb ist Eigentümervorgabe: keine versteckte Dauerinstanz; neuer Start löst ausschließlich die authentifizierte alte Instanz derselben Installation ab und wartet auf deren Prozessende. Letzter Bot-Tab zu oder Terminal weg beendet den Bot. Kein Handel vor erster UI-Verbindung; Reload-Schonfrist 5 Sekunden, anschließend geordneter Stopp mit maximal 15 Sekunden Selbstbeendigungsfrist. Netzwerkabbrüche benötigen zusätzlich Erkennung durch WebSocket-Ping. Minimieren/Tabwechsel sind kein Schließen. Keine automatische Liquidation, offene Echtgeldpositionen wären nach Prozessende unbetreut. Historische 24/7-Aussagen gelten nur mit geöffneter Konsole/Oberfläche. Echtgeld bleibt technisch gesperrt; die Kontoprüfung erklärt konkrete Rechte und Fremdbestände, hebt aber keine Schutzregel auf. DMS 20 enthält Bedienung/Restarbeit, DMS 18 den tatsächlichen Laptopstand.

## Historie: DMS 1.12.1 / Anwendung 0.4.7, DEC-053

Der GitHub-USDC-Umbau wurde integriert und um Orderadapter-/Migrationsregressionen ergänzt. Am 09.09.2026 um 08:19 Berlin ist Code `bc0b121` tatsächlich im Laptop-Ordner installiert und dessen vorhandene `Startbot.bat` gestartet worden: HEALTHY, V6-USDC `d57f88ec2e5f`, zehn Märkte, 250-USDC-Modellkonto/3×80 in getrennter Datenbank. Altes USDT-Ledger und Zugangsdaten bleiben erhalten. Deploymentnachweis steht in DMS 18. Genau ein späterer 50-USDC-Test ist beauftragt, aber noch nicht ausführbar: produktiver Controller-Anschluss, Kontoreconciler, Mengen-/Preisgates und Testnet-/Betriebsabnahme fehlen. Keine Freigabe durch grüne Unit-Tests oder einen gesunden Paperbetrieb. DMS 20 enthält die konkrete Übergabe. Alle nachfolgenden datierten Stände sind Historie, keine heutige Aktivierungsbehauptung.

## Historie: DMS 1.11.0 / Anwendung 0.4.6, DEC-052

USDC ist das vom Eigentümer gewünschte Ziel für den späteren 50-USDC-Einmaltest und Spotbetrieb. Der technische Stand ist ausdrücklich **Validierung, nicht vollzogene Migration**: V6-Paper/Config/Ledger bleiben USDT, V7 ist ein nicht aktivierbarer Forschungsstand mit unveränderten Coin-Profilen auf echten USDC-Kerzen. Datenverfügbarkeit, Kosten-Stress und gemeinsame 3×80-Tests werden getrennt ausgewiesen. Kein Echtgeldstart, keine neue Livefreigabe, keine Umbenennung alter Zahlen. Maßgeblicher Ergebnisnachweis: `backtests/v7/README.md` und DMS 18. Offene Umsetzung: währungseindeutiges Runtime-/Ledger-/UI-/Kontoprüfmodell sowie produktiver Orderadapter und Reconciliation. Sämtliche älteren datierten Stände unten sind Historie, auch wenn sie damals als aktuell bezeichnet wurden.

## Historie: DMS 1.10.1 / Anwendung 0.4.5, DEC-051

Eigentümer wählt Positionsbudget über 1–10 Slots × USDT je Trade ohne feste 240-USDT-Obergrenze. Keine automatische Änderung der gespeicherten Werte oder Kontoguthaben. Live-Anzeige folgt dem Serverzustand, Einmaltest genau ein 50-USDT-Trade ohne Zusatzhäkchen. Binance-Marktfilterabfrage von JSON-Leerzeichen befreit; Fehlerphase und Codes sicher unterscheidbar. Echtgeld bleibt ohne produktiven Adapter/Abgleich gesperrt. Konten, Passwort und Schlüssel bleiben erhalten. Ältere datierte Grenzen/Checkbox-Anleitungen unten sind Historie und durch DEC-051 ersetzt.

Neuester Stand **DMS 1.9.1 / Anwendung 0.4.3, DEC-049**: eine gemeinsame Handelskonfiguration, direkte Entwurfs-/Speicherstandsanzeige auch bei Live, eindeutig benannte Einstiegspause und ein gemeinsamer Echtgeld-aus-Button. Bestehende Grenze 3 Slots / 240 USDT bleibt bis zur ausdrücklichen Erweiterung bestehen. Paper läuft in echter Marktzeit, nur Geld/Fills werden simuliert. Keine Echtgeldfreigabe, kein Kontoreset und keine Strategieänderung. Nachfolgende datierte Teilstände bleiben Historie.

Aktueller Stand **DMS 1.9.0 / Anwendung 0.4.2, DEC-048**: Sichtbare, bis zur lokalen Entsperrung deaktivierte API-Key-/Secret-Felder und getrennte Test-/Live-Steuerung eingebaut. Signal-Einmaltest-Controller mit globaler 50-USDT-Einstiegsberechtigung, regulärem Coin-Ausgang, Abschluss-/Restmengenprüfung und Fortführung offener Positionen bei Entry-Stopp ausschließlich mit Fake-Börse getestet. Produktiver Adapter, Runtime-Anschluss, echter automatischer Bestandsabgleich und Live-Abnahme fehlen weiterhin; Startanforderungen bleiben HTTP 409, **kein Echtgeldstart**. Paperkonto/Settings/Profile unverändert. Ältere datierte Stände darunter sind Historie, keine aktuelle Freigabe.

## Zweck

Aktueller Ergänzungsstand: **DMS 1.7.1, 06.09.2026 / Anwendung 0.3.2**. DEC-045 (06.09.2026): Auf ausdrücklichen Eigentümerwunsch wird V6 `HIXTON-V6-COIN-PAPER-1-9734f240e873` als **Paper-Experiment** aktiviert. Der frische Modellaccount startet mit 250 USDT, drei 80-USDT-Slots und 10 USDT Anfangsreserve. Alte Paperpositionen, Ereignisse, Dust und Soak bleiben ausschließlich im geprüften lokalen Vollarchiv; sie werden weder als neue Trades noch als Gewinn übernommen. Normale Neustarts erhalten das Konto weiterhin. Die schwächeren jüngsten/älteren Ergebnisse bleiben bestehen; dies ist keine Robustheits-, Optimalitäts- oder Livefreigabe. Historische Abnahmen unten bleiben datierte Nachweise.

Dieses DMS ist die maßgebliche Produktspezifikation für den **Hixton-Indikator Trading Bot**. Es beschreibt, was gebaut, getestet, angezeigt und betrieben wird. Der aktuelle Implementierungs- und Nachweisstand steht ergänzend in Dokument 14 und 18; auch ein valider historischer Test ist kein Nachweis zukünftiger Profitabilität.

## Geltungsbereich

Die Dokumentation deckt ab:

- die exakt abzugleichende Hixton-/VIDYA-/ATR-Signallogik;
- zehn Kryptowährungspaare auf Binance Spot;
- Einzel- und Portfoliobacktests mit klaren Annahmen;
- Marktdatenbeschaffung, Lückenprüfung und tägliche Aktualisierung;
- Order-, Kapital- und Sicherheitsregeln;
- Live-UI mit Chartzeiträumen Heute, 1 Woche, 1 Monat, 1 Jahr und 3 Jahre;
- Architektur, Datenmodell, Betrieb, Wiederanlauf, Monitoring und Recovery;
- Tests, Abnahme, Nachvollziehbarkeit und einen schrittweisen Build-Plan.

## Rangfolge der Quellen

Bei einem Widerspruch gilt diese Reihenfolge:

1. schriftlich vom Eigentümer freigegebene Entscheidung im Entscheidungslog;
2. für den aktiven Paperbetrieb die in `DEC-045` ausdrücklich gewählte V6 samt Profilen in Dokument 03 und `backtests/v6/candidate.json`;
3. diese DMS-Dokumente mit Status `VERBINDLICH`;
4. die am 01.09.2026 vom Eigentümer bereitgestellte Pine-v6-Quelle samt Hash; sie überschreibt historische V1-Nachweise nicht;
5. vorhandene Analyse `Der Hixton Indikator.md`;
6. Kommentare, Beispiele, UI-Mockups und sonstige Hinweise.

Eine spätere Implementierung darf nicht stillschweigend von einer höher priorisierten Quelle abweichen.

## Dokumentstatus

| Status | Bedeutung |
|---|---|
| VERBINDLICH | Freigegebene Soll-Vorgabe |
| ANNAHME | Arbeitsannahme, die bestätigt oder ersetzt werden muss |
| OFFEN | Entscheidung oder Quelldatei fehlt |
| NACHWEIS AUSSTEHEND | Vorgabe ist definiert, aber noch nicht durch Test/Artefakt belegt |
| VERWORFEN | Darf nicht implementiert werden |

Aktueller Paketstatus: **DMS V1.7; V6 aktives Paper-Experiment, V2 vorherige Referenz, V1 historisch, V3 verworfen, V4/V5 historische Forschung.** V6-Paper-Soak, externes Backup/Restore, dedizierter Live-Account und Livefreigabe bleiben `NACHWEIS AUSSTEHEND`; `LIVE_DISABLED` bleibt technisch erzwungen. Telegram ist kein Pflichtkanal.

## Arbeitsübergabe vom 02.09.2026

- Der Eigentümer hat V2 ausdrücklich für Paper freigegeben. Aktiver Laufzeitstand ist **V2 `HIXTON-V2-RESEARCH-CANDIDATE-1`**; die unveränderliche Kennung wird trotz neuem Status nicht umbenannt. V1-Ledger und V1-Runs bleiben erhalten. Live ist nicht freigegeben.
- Der V2-10×250-Test war im aktuellen Dreijahresfenster stark. Der echte 3×80-Paper-/Live-Risikospiegel hielt jedoch im aktuellen Fenster und in beiden älteren Prüfsegmenten wegen der verbindlichen Risikogrenzen vorzeitig an. Er belegt deshalb keinen kontinuierlichen Dreijahresbetrieb und keine tägliche Gewinnerwartung.
- Band 4,0 wurde trotz besserem aktuellen Fenster wegen schwacher älterer Segmente verworfen. Der nächste Bearbeiter darf diesen Challenger nicht ohne neue robuste Nachweise reaktivieren und die 5-%-Tagesverlustpause oder den 20-%-Drawdown-Halt nicht zur Ergebnisverbesserung lockern.
- Der erste V3-Versuch erlaubte die vom Eigentümer gewünschte Mehrfachbelegung eines Coins: zuerst je gleichzeitigem Kandidaten ein Slot, danach alle freien Slots an den stärksten Kandidaten. Er endete schon am 12.10.2023 im Risikohalt bei 287,85 USDT Baseline bzw. 282,16 USDT Stress und ist verworfen. Aktive V2 bleibt bei höchstens einem Slot je Coin.
- Grundprinzip: Die bestbelegte zulässige Version wird nach explizitem, protokolliertem Wechsel für Paper übernommen. Ein einzelner Spitzenwert genügt nicht; Kosten-Stress, Altfenster, Risikospiegel und Reproduzierbarkeit bleiben Pflicht. Live benötigt immer eine eigene Freigabe.
- Abgenommener Stand nach dem Betriebswechsel: 68 grüne Python-Tests, Ruff, mypy, TypeScript und Produktionsbuild bestanden. Die lokale V2-UI wurde nach dem Neustart sichtbar geprüft; alle 50 Kombinationen aus zehn Coins und fünf Chartzeiträumen lieferten Daten, Coin-/Zeitraumwechsel und Signal-/Paper-Fill-Daten funktionierten und die Browserkonsole blieb ohne Warnung oder Fehler.
- Die kontrollierte Migration am 02.09.2026 schloss genau die offene V1-DOT-Position zu Baselinekosten mit `-2,55367424142 USDT`, bewahrte beide Ledger-Ereignisse und startete V2 bei `237,44632575858 USDT`. Seit V2-Aktivierung sind noch keine V2-Trades abgeschlossen; der V2-Session-PnL ist deshalb `0 USDT` und darf nicht mit dem historischen V1-Verlust vermischt werden.
- Vor der Migration wurde `backups/hixton-before-v2-20260902-1533.sqlite3` erstellt und byte-/hashgleich zur Quelldatenbank geprüft (`SHA-256 EE5F0D278F5A184BFE0D8AFEADF8FB89220FD7AECE9B66EAFE19D40BDB42428E`). Dieses lokale Backup ist bewusst nicht Teil von Git.
- Marktdaten sind lokale, automatisch nachgeladene `1h`-Kerzen. UI-Kürzel `1m` bedeutet einen Monat. Datenbank, Marktdaten, Logs und große reproduzierbare Run-Artefakte bleiben durch `.gitignore` lokal.
- Gemeinsamer Übergabestand liegt im Branch `codex/build-foundation-v1` und Pull Request 2. Der nach der Browserabnahme ergänzte Recovery-Fix `3deea9e` verhindert einen dauerhaft falschen `DEGRADED`-Status nach erfolgreicher Websocket-Wiederverbindung, ohne unabhängige Fehler zu verdecken. Dokument 18 und `backtests/v2/README.md` enthalten die belastbaren Run-IDs, Hashes, Ergebnisse und Grenzen.

## Eingangsbestand vom 31.08.2026

| Datei | Umfang | SHA-256 | Bewertung |
|---|---:|---|---|
| `Der Hixton Indikator.md` | 7.226 Bytes / 27 Zeilen | `3577700EAFA4738D8941769F8275024BEDE86B6D8CB344C7B1EA8E60E7E4E117` | Analyse/Beschreibung, kein Pine-Quellcode |
| `Der_Hixton_Indikator_v6.pine` | Eigentümerquelle vom 01.09.2026 | `8AF8E9A1E6C73DC66307271B7FD1141EAAE02BC1FE88E8BA97B96E7A861263DD` | verbindliche Formelreferenz von V2 und V6, nicht rückwirkend für V1 |

Die ursprüngliche Markdown-Analyse bleibt als unverändertes Eingangsmaterial erhalten. Der später vom Eigentümer vollständig übermittelte Pine-v6-Code liegt einmalig unter `strategy/pine/` und ist die Referenz für V2. Die selbstständige V1-Projektdefinition in Dokument 03 und sämtliche V1-Runs bleiben unverändert erhalten.

## Dokumentenkarte

| Datei | Inhalt |
|---|---|
| `01_PRODUKTVISION_SCOPE.md` | Ziel, Grenzen und Nutzerrollen |
| `02_VERBINDLICHE_ANFORDERUNGEN.md` | funktionale und nichtfunktionale Anforderungen |
| `03_STRATEGIE_HIXTON.md` | normative Signal- und Zustandslogik |
| `04_MARKT_KAPITAL_RISIKO.md` | zehn Märkte, 3×80-USDT-Modell und Schutzregeln |
| `05_MARKTDATEN_UND_AKTUALISIERUNG.md` | Download, Lücken, Startup und Mitternachtsjob |
| `06_BACKTEST_UND_VALIDIERUNG.md` | 3-Jahres-Test, Kosten, Metriken und Anti-Overfitting |
| `07_AUSFUEHRUNG_ORDERS.md` | Signal-zu-Order-Lebenszyklus |
| `08_UI_UX_SPEZIFIKATION.md` | Screens, Charts, Status und Bedienregeln |
| `09_SYSTEMARCHITEKTUR_DATENMODELL.md` | Komponenten, Zustände und persistente Daten |
| `10_BETRIEB_MONITORING_RECOVERY.md` | Start, Scheduler, Logs, Backup und Störungen |
| `11_SICHERHEIT_COMPLIANCE.md` | Schlüssel, Rechte, Audit und Haftungshinweise |
| `12_TESTS_ABNAHMEKRITERIEN.md` | Testpyramide und Freigabegates |
| `13_KONFIGURATION_UND_SCHEMATA.md` | Konfigurationsfelder und Validierung |
| `14_BUILD_PLAN_UND_DEFINITION_OF_DONE.md` | spätere Umsetzungsreihenfolge |
| `15_TRACEABILITY_MATRIX.md` | Anforderung → Test → UI/Artefakt |
| `16_ENTSCHEIDUNGSLOG_UND_OFFENE_PUNKTE.md` | zentrale Unklarheiten und Beschlüsse |
| `17_GLOSSAR.md` | eindeutige Begriffe |
| `18_BACKTEST_STATUS_UND_ERGEBNISFORMAT.md` | wahrheitsgemäßer Ist-Stand und Ergebnisformat |
| `19_RISIKOREGISTER.md` | fachliche, technische und betriebliche Restrisiken |
| `20_BETRIEBSRUNBOOK.md` | konkrete Bedien- und Störungsabläufe |
| `21_GITHUB_ZUSAMMENARBEIT.md` | Repository, Branches, Reviews und späterer Upload |
| `22_QUELLEN_UND_BINANCE_PRUEFUNG.md` | offizielle Schnittstellen und geprüfter Marktstatus |
| `23_ORDNERSTRUKTUR_UND_EINSTIEGSPUNKT.md` | ein Projektstart, ein technischer Einstieg und Backtestversionen |

## Änderungsprozess

1. Jede fachliche Änderung erhält eine Entscheidungs-ID (`DEC-xxx`).
2. Betroffene Anforderungen und Tests werden aktualisiert.
3. Änderungen an der Strategie erhöhen die Strategieversion und machen bestehende Backtestergebnisse ungültig.
4. Eine Backtestausgabe nennt immer Git-/Build-Version, Strategiehash, Konfigurationshash, Datenhash und Kostenmodell.
5. Nur als `VERBINDLICH` markierte Entscheidungen dürfen gebaut werden.

## Nichtverhandelbare Wahrheitsregeln

- Keine erfundenen Backtestwerte.
- Keine Ergebnisgarantie oder Renditezusage.
- Kein Look-ahead, kein Repainting, keine Verwendung einer noch offenen Kerze zur Orderentscheidung.
- Keine heimliche Optimierung auf die Zielrendite.
- Keine Änderung der Strategie durch UI, Datenbereinigung oder Risikocode ohne dokumentierte Entscheidung.
- Ein blockierter Trade muss mit Ursache protokolliert werden; er darf nicht still verschwinden.
