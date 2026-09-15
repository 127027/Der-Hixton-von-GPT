# 16 – Entscheidungslog und offene Punkte

## DEC-055 – Ein Handelsregelwerk, getrennte Ausführungsnachweise, 09.09.2026

Eigentümer bestätigt: Historie simuliert die gewählten heutigen Regeln rückwirkend; Paper simuliert deren jetzige Ausführung; Live sendet echte Orders. Keine unabhängig erfundenen Coin-Regeln je Betriebsart. Ein Patch muss durch Strategie-/Policy-/Portfolio-/Ausführungstests geprüft werden. Ein historisches Ergebnis ist keine Vorhersage und kein Beweis funktionierender Binance-Rechte oder tatsächlicher Orderausführung. `VALID` bezeichnet ein valides Simulationsergebnis, nicht Produktfreigabe. Gewählte historische Versionen bleiben ausdrücklich historische Referenzen; aktuelle Coin-Parameter wurden in 0.4.9 nicht optimiert.

Einmaltest: nach manueller Benutzerfreigabe genau ein frisches qualifiziertes Signal aus zehn Coins, genau 50 USDC Kaufbudget, keine zweite Einstiegsberechtigung. Nach dem Kauf neue Einstiege aus; die eigene Position bleibt bis zum regulären Coin-Ausgang betreut. „Live aus“ meint Entry-aus, nicht Bot-Prozess aus. Die strengere Prozessabschaltung aus DEC-054 bleibt bestehen und wird nicht für heimliche Exit-Betreuung umgangen.

0.4.9 verbindet den dauerhaften Controller mit dem Supervisor, übernimmt dieselben analysierten Daten und zentralisiert die Rangfolge. Einmaliger Ausgangsbestand vor dem ersten Intent; Binance-Fills verändern nur die zugehörigen Mengen, Quote und Gebührenassets. Ein unveränderter Altbestand ist kein Bot-Eigentum. Fehlende Baseline, unklare Orders, offene Orders, eingefrorene Mengen, falsches Konto oder Saldoabweichung verhindern einen behaupteten Abschluss. Ein stabiler Saldovergleich allein beweist keine vollständige Historie zwischen zwei Abfragen: gegenläufige manuelle Trades sind damit nicht ausgeschlossen. Diese Grenze bleibt Teil der offenen produktiven Abnahme.

Produktiver Submit bleibt fail-closed gesperrt, ebenso Benutzerstart HTTP 409. Vor Freigabe: Live-Markt-/Preis-/Mengenprüfung, nicht handelbare vs. handelbare Reste, Fremdorderhistorie, externe Testnet-/Störfallabnahme und klare UI-Abnahmekette. Keine echte Order durch den Entwicklungsagenten. Nur ein späterer Benutzerklick darf die Einmalberechtigung erzeugen; Dauer-Live bleibt außerhalb dieser Freigabe.

## DEC-054 – Kein unsichtbarer Bot und kontrollierte Instanzablösung, 09.09.2026

VERBINDLICH auf Eigentümerauftrag: `Startbot.bat` bleibt der einzige Starter. Er führt den aktuell lokal installierten Code aus. Ein erneuter Start darf nicht eine zusätzliche Handelsinstanz erzeugen: bestehende Instanz anhand Installation, Instanz-ID und zufälligem lokalem Kontrolltoken identifizieren, Shutdown anfordern und tatsächliches Prozessende abwarten. Fremde/alte nicht authentifizierbare Server auf dem Port bleiben unangetastet und erzeugen eine verständliche Meldung. Einmaliges Deployment von 0.4.7 erfordert gezieltes Beenden der identifizierten alten Instanz, da diese das neue Protokoll noch nicht kennt.

Terminal geschlossen **oder** letzte Bot-Oberfläche geschlossen: neue Verarbeitung stoppen, Prozess beenden. Mehrere Tabs sind zulässig; erst das letzte Schließen startet die 5-Sekunden-Reload-Schonfrist. Minimierte Fenster und inaktive Tabs bleiben geöffnet; kein Timer auf Sichtfokus. WebSocket-Ping 10 Sekunden/Timeout 5 Sekunden zur Erkennung abgerissener Verbindungen. Keine Oberfläche nach 60 Sekunden: kein Handel und automatischer Stopp. Nach erkanntem Stopp maximal 15 Sekunden zum Prozessende, auch bei hängendem Download-Thread. Eigene unfertige SQLite-Transaktionen werden gegebenenfalls zurückgerollt; fremde Prozesse werden nie zwangsbeendet. Fehler der Terminalüberwachung führen ebenfalls zum Stopp.

Kein automatischer Verkauf bei Programmende. Bereits echte offene Positionen wären danach ohne Bot-Überwachung; das wird in Konsole und UI angezeigt. Ein späterer Live-Wiederanlauf muss reale Orders/Bestände abgleichen, darf keine neue Budgetfreigabe erfinden und bleibt bis zur getrennten Abnahme gesperrt. Diese Entscheidung ersetzt die Vorstellung eines unsichtbaren 24/7-Hintergrunddienstes, nicht die bisherigen Handels-/Kapitalregeln.

## DEC-053 – GitHub-USDC-Umbau übernehmen, Echtgeld-Einmaltest weiter vorbereiten, 09.09.2026

Eigentümer verweist auf `codex/build-foundation-v1` (übernommen bis `ab4f83e`). Parameter/Policies werden nicht neu optimiert. Aktiver Code benutzt zehn USDC-Symbole, eine eigene `hixton-usdc.sqlite3` und eindeutige Quote im Strategie-Snapshot; alte USDT-Konten/Ergebnisse werden nicht umetikettiert. Die historische V6-USDT-ID `9734f240e873` unterscheidet sich von V6-USDC `d57f88ec2e5f`. Das ist keine neue Profitabilitätsfreigabe.

Nachgewiesene Integrationskorrekturen: gemeinsame verfügbare Historie statt unmöglicher drei Jahre für sieben USDC-Paare, weiterhin strenger Lücken-/Endbar-/400-Warm-up-Check; gleiche Warm-up-Startgrenze für Paper und Portfolio-Backtest; tatsächliche Quote alter Berichte anzeigen; Windows-Vault-Namespace bei Wechsel der Standarddatenbank erhalten. Kein Zugriff auf Klartextschlüssel und keine Kontobewegung für diese Tests.

Einmaltest-Ziel bleibt genau ein echter 50-USDC-Kauf nach neuem qualifiziertem Signal, danach zugehöriger regulärer Ausgang und überprüfter Abschluss. Paper läuft unabhängig weiter. Dauer-Live bleibt aus. Der neue HTTPS-Orderadapter ist offline geprüft, jedoch ausdrücklich noch nicht produktiv angeschlossen. Technische Abnahme-/Kontoreconciler-Gates bleiben wirksam; der Start-Endpunkt gibt HTTP 409 zurück. Nicht als fertigen Testbutton ausliefern oder dokumentieren.

## DEC-052 – USDC-Ziel, getrennte Migrationsprüfung, 08.09.2026

Eigentümer beauftragt die Vorbereitung auf seine USDC-Mittel und später genau einen signalgesteuerten 50-USDC-Echtgeldtrade. **Keine Aktivierung des 3×80-Echtgeld-Dauerbetriebs.** Alte USDT-Konten, Backtests, Einstellungen und Schlüssel bleiben erhalten; weder bestehende Zahlen umetikettieren noch 1:1-Umtausch/Fills behaupten. Hebel ist nicht Bestandteil dieser Spot-Migration.

V7 ist zunächst `HIXTON-V7-USDC-VALIDATION-1-9734f240e873`, nicht Paper-/Live-freigegeben. Übernahme der zehn V6-Coin-Parameter und Zusatzregeln ohne neue Optimierung, Prüfung ausschließlich auf echten USDC-1h-Kerzen. Gemeinsamer Zeitraum allein anhand Datenverfügbarkeit einschließlich 400 Warm-up-Bars; zusätzlich vorab festgelegte 365-/90-Tage-Fenster, Baseline und Stress, zehn Einzelkonten à 250 sowie 250 Startcash/3×80 gemeinsam. Nicht verfügbare drei Jahre nicht durch USDT-Kerzen oder künstliche Bars ergänzen. Ein USDT-Kontrolllauf verwendet dieselben Start-/Endzeitpunkte, um Zeitraum- und Quote-Effekte nicht zu verwechseln. Keine Behauptung unberührter Out-of-sample-Daten für bereits auf USDT erforschte Einstellungen.

Vor Echtgeld bleiben Runtime-/Ledger-Migration, echte kontospezifische USDC-Handelbarkeit/Filter/Gebühren, Orderadapter, genau-einmal-Versand, Timeout-/Teilfill-/Restart-Abgleich, Ausgänge und Abnahme offen. Ein positiver öffentlicher Marktcheck ist keine Kontofreigabe. Kein Sicherheitsgate zum Erzwingen von Trades entfernen. Die aktive UI zeigt weiterhin zutreffend USDT, bis die Runtime tatsächlich migriert ist. DMS 18 und `backtests/v7/README.md` halten Ergebnisse und nächste Schritte fest.

## DEC-051 – Betreiberbudget, eindeutiger Livestatus und Binance-Fehler, 08.09.2026

Eigentümer hebt die feste 240-USDT-Positionsbudgetgrenze ausdrücklich auf. Gewähltes Budget ergibt sich aus 1–10 Slots × Zielnotional; kein zusätzliches Budgetfeld. Beispiel 5×50 = 250 oder später 10×100 = 1000 ist speicherbar. Das Update setzt selbst keine dieser Größen. Baseline bleibt 3×80 bei anfänglich 250 USDT, keine Einzahlung oder Übernahme fremder Binance-Guthaben ins Paperkonto. Ausführung bleibt durch verfügbares Cash, Börsenfilter, Signale und Risikogates begrenzt; Settings gelten für neue Entries, offene Positionen laufen unverändert aus. Das Positionsbudget ist keine garantierte Verlustobergrenze.

Live an/aus optisch nur gemäß bestätigtem Serverzustand markieren; bei unbekanntem Status keine Aktivbehauptung, bei Einmaltest eigenen Zustand anzeigen. Ein ausdrücklich als **genau ein Echtgeld-Testtrade · 50 USDT** beschrifteter Button ersetzt die zusätzliche Checkbox. Festes Einmalbudget und globale restartfeste Einmalberechtigung bleiben; kein Dauerbetrieb durch fehlendes Häkchen oder wiederholtes Klicken. Weiterhin kein produktiver Versand/Runtime-Reconciler, HTTP 409 statt vorgetäuschtem Start.

Defekt der Kontovorprüfung nachgewiesen: `json.dumps(SYMBOLS)` enthielt Leerzeichen. Öffentliche `exchangeInfo`-Anfrage ergab HTTP 400/-1100, kompakte Serialisierung am 08.09.2026 HTTP 200 mit zehn Symbolen. Fix und Transportregression enthalten. Fehlertexte nennen ausschließlich feste Prüfschritt-/Codeerklärungen, niemals Binance-Rohtext/URL/Signatur/Keys. Authentifizierte Kontovorprüfung muss der Betreiber nach dem Update erneut auslösen; öffentlicher Markttest ist kein Nachweis der eigenen Key-Rechte. Ersetzt Budgetgrenze und Checkbox aus DEC-050, nicht Sicherheits- und Echtgeldgates.

## DEC-050 – Vereinfachte Einstellungen und flexible Slotaufteilung, 07.09.2026

Eigentümer verlangt ausdrücklich höhere Slotzahlen (Beispiel 4×45), 1-USDT-Eingabeschritte und einen direkten Übernehmen-Button. Beschluss: 1–10 gleichzeitig offene Slots (zehn mögliche Coins), weiterhin höchstens 240 USDT Positionsbudget und getrennte Guthabenprüfung. Keine Freigabe von 4×80/400/750 USDT und kein Auffüllen des 250-USDT-Paperkontos. Baseline bleibt 3×80; neue Aufteilungen sind keine historischen 3×80-Ergebnisse.

Drei UI-Bereiche Handel / Binance verbinden / Livehandel. Normale Parameter speichert ein Klick; kein Wort ANWENDEN/SPEICHERN nötig. Entfernen eines Keys bleibt eine eindeutige Ja/Abbrechen-Aktion, der 50-USDT-Echtgeldtest erhält eine Checkbox. Sichtbaren Einstiegspause-Schalter entfernen, bestehende interne Risiko-/Sicherheitslatches aber nicht automatisch löschen. Live aus verhindert neue Echtgeldentries und liquidiert nicht. Vorhandenes Passwort beibehalten, Authentifizierungsfehler direkt anzeigen, Key-Felder erst bei verifizierter Sitzung freischalten. Kein Echtgeld-Gate umgehen. Ersetzt die UI-/Slotgrenzen von DEC-049, nicht dessen gemeinsame Konfigurationsquelle.

## DEC-049 – Gemeinsame Handelseinstellungen, 07.09.2026

Eigentümer verlangt eine zusammenhängende Paper-/Live-Konfiguration und das Entfernen irreführender Doppelungen. Slotanzahl, Positionsgröße, Coin-Profile und Einstiegspause bilden eine gemeinsame Vorgabe; Paper und künftiger normaler Livebetrieb dürfen keine still auseinanderlaufenden Kopien führen. Gleiche Echtzeit-Marktdaten und Handelslogik, getrennte simulierte/echte Konten und Fillnachweise; nur der Backtest verwendet historische Zeit. Gleiche Fills oder Gewinne sind damit nicht zugesagt.

Umsetzung 0.4.3: sofortige gemeinsame Entwurfsanzeige mit ausdrücklich getrenntem Speicherstand, klarer ANWENDEN-Schritt, Live-Anforderung bei ungespeichertem Entwurf blockiert, ein Echtgeld-aus-Button auch für Einmaltest. Entry-Pause und Live-aus liquidieren nicht. Der bestätigte 1×50-Einmaltest bleibt eine bewusste Ausnahme zum normalen Budget. Technische Echtgeldfreigabe bleibt offen.

Die genannten Beispiele 4×80/5×80 werfen eine gesonderte Budgeterweiterung auf. Bis zu deren ausdrücklicher Klärung bleiben 3 Slots / 240 USDT freigegeben; kein Hochsetzen des 250-USDT-Kontos. Die UI muss diesen Grund statt eines scheinbar erfolgreichen Rückfalls auf 3×80 nennen. Betroffen: DMS 08/12/13/20 und Tests; keine Änderung der Strategieprofile/Backtestmethodik.

## Neueste Eigentümerentscheidung – DMS 1.7

DEC-045 – BESCHLOSSEN (06.09.2026): Auf ausdrücklichen Eigentümerwunsch wird V6 `HIXTON-V6-COIN-PAPER-1-9734f240e873` als **Paper-Experiment** aktiviert. Der frische Modellaccount startet mit 250 USDT, drei 80-USDT-Slots und 10 USDT Anfangsreserve. Alte Paperpositionen, Ereignisse, Dust und Soak bleiben ausschließlich im geprüften lokalen Vollarchiv; sie werden weder als neue Trades noch als Gewinn übernommen. Normale Neustarts erhalten das Konto weiterhin. Die schwächeren jüngsten/älteren Ergebnisse bleiben bestehen; dies ist keine Robustheits-, Optimalitäts- oder Livefreigabe.

Dies ist die ausdrücklich angeordnete Ausnahme zu DEC-043/044 für diesen frischen Paper-Versuch, keine allgemeine automatische Gewinnerübernahme und keine Lockerung von Risikogates. Wiederholte Resets erfordern jeweils einen neuen ausdrücklichen Auftrag. Historische V2/V6-Backtestergebnisse, Git-Versionen und heruntergeladene Kerzen werden nicht gelöscht.

## Ergänzungen 06.09.2026

- **DEC-043 – BESCHLOSSEN:** Eigentümer präzisiert den Zweck: robuste einzelne Coin-Signalquellen und effiziente Nutzung von höchstens 3×80 USDT; keine Tradequoten, keine Renditegarantie, kein Overfitting. Individuelle Profile müssen durch Paper und sämtliche Backtestmodi identisch weitergegeben werden. Der vorbereitete V6-Mix ist retrospektiv kalibriert und scheitert derzeit an einer durchgängigen Portfolioverbesserung. Technische Parität allein ist keine Übernahmefreigabe; ein abweichender Paper-Experimentwechsel müsste ausdrücklich mit diesen Rückschritten bestätigt werden.
- **DEC-044 – BESCHLOSSEN:** Eigentümer bestätigt 250 USDT für neue gemeinsame Modellkonten: 240 USDT Positionsbudgets und 10 USDT anfängliche Reserve. Kein Auffüllen/Reset des laufenden Ledgers. Isolierte Einzeltests bleiben 250 USDT pro Coin. Vergleiche nennen Startkapital; V2-Kontrolle des V6-Versuchs startet ebenfalls mit 250, alte 240-USDT-Artefakte bleiben unverändert.


Dieses Dokument ist die einzige Sammelstelle für fachliche Entscheidungen. „Default des Frameworks“ ist keine Entscheidung. Für DMS V1.3 sind alle implementierungsrelevanten P0-/P1-Entscheidungen geschlossen. Noch fehlende Zugangsdaten, Testresultate und Betriebsnachweise sind **Nachweise**, keine offenen Produktentscheidungen.

Beschlussstand: **02.09.2026, Europe/Berlin**. Änderungen nach dem DMS-Freeze benötigen eine Entscheidungs-ID, Begründung und passende Versionsanhebung.

## P0 – Strategie, Markt und Backtest

| ID | Beschluss | Status/Auswirkung |
|---|---|---|
| DEC-001 | Historischer V1-Beschluss: normative und implementierbare Referenz bleibt `HIXTON-SPEC-1.0`. Die später bereitgestellte Eigentümer-Pine-Quelle erzeugt V2 und verändert V1 nicht. | **BESCHLOSSEN**; durch DEC-034 für V2 ergänzt. |
| DEC-002 | Source `close`; VIDYA-Länge 10; Momentum/CMO 20; Nachglättung SMA 15; ATR als Wilder-RMA 200; Bandmultiplikator 2,0. Formeln und Rundungsregeln stehen normativ in DMS 03. | **BESCHLOSSEN** |
| DEC-003 | Signallogik auf Binance-Spot-Kerzen mit festem Timeframe `1h`. UI-Zeiträume sind davon unabhängig. | **BESCHLOSSEN** |
| DEC-004 | Handelsplatz und Datenquelle: Binance Spot, Quote-Asset USDT. Paper nutzt dieselben Marktdaten; Live benötigt einen eigenen Bot-Account oder Subaccount. | **BESCHLOSSEN** |
| DEC-005 | BTC, ETH, BNB, SOL, XRP, ADA, LINK, AVAX, DOT und DOGE, jeweils `/USDT`; keine automatische Ersetzung. | **BESCHLOSSEN** |
| DEC-006 | 250→500 USDT je Coin und genannte Tradezahlen sind illustrative Beispiele, keine festen Optimierungsquoten und kein Gewinnversprechen (DEC-043). Ergebnisse werden netto und vollständig berichtet; Primärziel ist robuste Nettowirkung, nicht maximale Tradezahl allein. | **BESCHLOSSEN, präzisiert 01.09.2026** |
| DEC-007 | Spot long-only; Kauf öffnet Long, Verkauf schließt Long; kein Short, Margin, Futures oder Leverage. Die aktive V2 nutzt höchstens einen Slot je Coin; abweichende Mehrfachslotmodelle benötigen eine eigene Version. | **BESCHLOSSEN; Mehrfachslot-Forschung durch DEC-039 präzisiert** |
| DEC-008 | Backtest: zehn isolierte Läufe à 250 USDT sowie Einzelmodus à 250 USDT; verpflichtender 250-USDT-Spiegellauf mit denselben Risikogates wie Paper. Neue Paperkonten: gemeinsamer Cashpool 250 USDT gemäß DEC-044, drei Slots à 80 USDT. | **BESCHLOSSEN** |
| DEC-009 | Die erste später freigegebene Liveversion verwendet Market-Orders mit den Guards aus DMS 07. | **BESCHLOSSEN** |
| DEC-010 | Kosten je Seite: Baseline 10 bp Gebühr + 2 bp Spread + 3 bp Slippage = 15 bp; Stress 10 + 10 + 20 = 40 bp. Kein BNB-/VIP-Rabatt. | **BESCHLOSSEN** |
| DEC-011 | Nur geschlossene Bars; Warm-up 400 Bars; Initialzustand nach Bar 399 `DOWN`, ohne Startorder; Cross- und Fill-Regeln exakt nach DMS 03/06. | **BESCHLOSSEN** |
| DEC-029 | Bei mehr Kaufkandidaten als freien Slots gewinnt der größte normalisierte Ausbruch `(close-upper)/ATR`; Tie-Break: BTC, ETH, BNB, SOL, XRP, ADA, LINK, AVAX, DOT, DOGE. | **BESCHLOSSEN** |
| DEC-030 | Ein Paper-/Live-Slot bleibt 80 USDT, bis der Betreiber ihn bewusst und auditierbar für künftige Entries ändert. Der isolierte Backtest nutzt fest 250 USDT Zielbudget bzw. den kleineren verfügbaren Cashbestand. Gewinne erhöhen keine der Zielgrößen automatisch. | **BESCHLOSSEN** |

## P1 – Paper-, Live- und Betriebsregeln

| ID | Beschluss | Status/Auswirkung |
|---|---|---|
| DEC-012 | Täglicher Datenaudit und Update um 00:05 UTC; UI zeigt zusätzlich Europe/Berlin. | **BESCHLOSSEN** |
| DEC-013 | 90 Sekunden ohne Streamupdate → `DEGRADED`; finale 1h-Bar mehr als 120 Sekunden verspätet → Symbol pausieren und REST-Recovery. | **BESCHLOSSEN** |
| DEC-014 | Vor Live-Submit maximal 25 bp Abweichung zwischen aktuellem Referenzpreis und geplantem Preis; darüber Intent blockieren und neu bewerten. | **BESCHLOSSEN** |
| DEC-015 | Netto-Tagesverlust von 5 % der Equity zu 00:00 UTC pausiert neue Entries bis zum nächsten UTC-Tag. 20 % Drawdown vom globalen Equity-High-Water-Mark setzt `HALTED`; keine automatische Notliquidation. | **BESCHLOSSEN** |
| DEC-016 | Ohne bestätigten Börsenstatus nach 10 Sekunden Zustand `UNKNOWN` und Reconciliation, niemals blinde Ersatzorder. Nach 30 Sekunden verbleibenden stornierbaren Teilfill-Rest stornieren; keine automatische Neuorder. | **BESCHLOSSEN** |
| DEC-017 | Offene Position am Backtestende separat mark-to-market bewerten; keinen künstlichen Exit erfinden. | **BESCHLOSSEN** |
| DEC-018 | Live-Gate: mindestens 30 Kalendertage, 720 geschlossene 1h-Bars und 20 abgeschlossene Papertrades. Sind nach 30 Tagen weniger als 20 Trades erreicht, bis 20 Trades verlängern, höchstens auf 90 Tage; danach Eigentümerentscheidung statt automatischer Live-Freigabe. | **BESCHLOSSEN** |
| DEC-019 | UI und strukturierte Logs sind die Pflichtkanäle. Der Eigentümer überwacht den Bot regelmäßig; Telegram wird ausdrücklich nicht benötigt und blockiert weder Paper noch Live. | **BESCHLOSSEN, ersetzt 01.09.2026** |
| DEC-020 | Verschlüsselte Backups außerhalb des öffentlichen Repos und außerhalb der aktiven Datenbank, bevorzugt in einem separaten OneDrive-Ziel. Retention: 7 tägliche, 4 wöchentliche, 12 monatliche Stände; Restore-Test vor Live und danach vierteljährlich. | **BESCHLOSSEN** |
| DEC-021 | Manueller Handel auf demselben Binance-Account/Subaccount ist verboten. Fremdorders oder unerklärte Salden setzen Live-Entries aus. | **BESCHLOSSEN** |
| DEC-022 | Die UI bindet ausschließlich an localhost. Netzwerkfreigabe ist eine spätere Sicherheitsentscheidung. | **BESCHLOSSEN** |
| DEC-023 | Nach bestandener Paperfreigabe Betrieb als Windows-Service mit verzögertem Autostart und Restart-on-Failure; jede Wiederaufnahme beginnt mit Startup-Reconciliation. | **BESCHLOSSEN** |
| DEC-031 | Repository `127027/Der-Hixton` ist öffentlich. DMS und eigene Projektspezifikation dürfen hinein; Secrets nie. Die vom Eigentümer ausdrücklich für das Projekt übermittelte Pine-Quelle darf eingecheckt werden; fremder Code ohne Rechte bleibt verboten. | **BESCHLOSSEN, präzisiert 01.09.2026** |
| DEC-034 | Der am 01.09.2026 übermittelte Pine-v6-Code wird einmalig unter `strategy/pine/` gespeichert und per SHA-256 fixiert. Seine Semantik ist V2-Referenz; V1 bleibt historische Wahrheit für vorhandene Runs und Paperereignisse. | **BESCHLOSSEN** |
| DEC-035 | Strategieverbesserungen werden iterativ in `backtests/v2`, `v3` usw. untersucht. Mehr Trades sind erwünscht, wenn Kosten-Stress und ältere Fenster nicht dadurch verschlechtert werden. Keine Version wird überschrieben. | **BESCHLOSSEN** |
| DEC-036 | V2-Kandidat 1 nutzt 1h, VIDYA 6, Momentum 20, SMA 8, ATR 60, Band 3,8 und 400 Warm-up-Bars. Seine unveränderliche Versionskennung bleibt `HIXTON-V2-RESEARCH-CANDIDATE-1`, auch nachdem der Status durch DEC-037 geändert wurde. | **BESCHLOSSEN; Paperstatus durch DEC-037 ersetzt** |
| DEC-037 | Der Eigentümer hat am 02.09.2026 ausdrücklich verlangt, den bislang besten Stand V2 im Paperbot zu verwenden. Der Wechsel gilt nur für Paper, erfolgt einmalig und vorwärtsgerichtet, schließt vorhandene V1-Paperpositionen kontrolliert nach Baselinekosten, bewahrt alle versionierten Ereignisse und startet den V2-Soak neu. | **BESCHLOSSEN; V2 PAPER_APPROVED, Live bleibt gesperrt** |
| DEC-038 | Grundprinzip für Verbesserungen: Der bestbelegte zulässige Kandidat wird nach dokumentiertem Vergleich und ausdrücklicher Entscheidung für Paper übernommen. Bestbelegt bedeutet nicht höchster Einzelwert, sondern Reproduzierbarkeit, Baseline/Stress, ältere Fenster, Nachbarstabilität und risikogleicher 3×80-Spiegel. Risikogrenzen werden nicht zum Schönen des Ergebnisses gelockert; Live bleibt ein eigener Entscheid. | **BESCHLOSSEN** |
| DEC-039 | Mehrere 80-USDT-Slots im selben Coin sind ein zulässiges Forschungsziel. V3 `ranked_repeat` vergab zuerst je gleichzeitigem Kandidaten einen Slot und danach Restslots an den stärksten. Der aktuelle Risikospiegel stoppte bereits am 12.10.2023 bei 287,85/282,16 USDT; V3 ist verworfen. Aktive V2 bleibt `one_per_symbol`, bis eine neue Version sie im vollständigen Prüfprogramm übertrifft. | **BESCHLOSSEN; V3 VERWORFEN** |

## P2 – Bedienung und Aufbewahrung

Ergänzende technische Entscheidungen vom 05.09.2026 im Auftrag der Fehlerkorrektur:

- **DEC-040 – VERBINDLICH:** Paper-Modell `NEXT_BAR_OPEN_V1`, tatsächliches Folge-Open, getrennte Modell-/Verarbeitungszeit, UTC-Zeitscheiben, Dust-Erhalt und einmaliger technischer Soak-Neustart. Kein Umschreiben alter Fills und keine Liquidation beim technischen Upgrade. Strategieparameter und Risikolimits unverändert.
- **DEC-041 – FORSCHUNG ABGESCHLOSSEN, NICHT AKTIVIEREN:** V4 prüft 24 Parameterkombinationen je Coin mit chronologischer Auswahl und separat bestätigte Nachkäufe. Der coinindividuelle Kandidat verbessert das volle historische Portfolio, verschlechtert aber das jüngste Neustartfenster; Nachkäufe verschlechtern acht von zehn vereinfachten Einzeltests. Keine Paperübernahme und keine Livefreigabe. Der Forschungsbericht ist kein weiterer Programmstarter und keine aktivierbare V4-Strategie.
- **DEC-042 – FORSCHUNG ABGESCHLOSSEN, NICHT AKTIVIEREN:** Im Auftrag der Einzelcoin-Verbesserung prüft V5 348 Hixton-Parameter-/Filter-/Stopkombinationen mit zwei getrennten Trainingsjahren und festgehaltener Auswahl. Alle zehn Verlustdiagnosen bleiben sichtbar. ETH verbessert das jüngste Stressjahr, hat aber einen älteren Rückschritt. XRP verbessert alle sechs Einzel-Endwerte, verschlechtert allein im gemeinsamen Konto jedoch das jüngste Jahr; sein 500-USDT-Ziel ist nicht nachbarstabil. Das vollständige Kandidatenportfolio erhöht den historischen Dreijahresendwert, verschlechtert jüngstes und älteres Neustartfenster. Gemäß DEC-038 keine Übernahme, keine Anpassung der Risikolimits, kein Paper-/Soak-Reset. Zusatzregeln bleiben explizite Forschung mit eigener Versionskennung, nicht Teil der Original-Pine- oder aktiven V2-Logik.

| ID | Beschluss | Status/Auswirkung |
|---|---|---|
| DEC-024 | Exporte: CSV und JSON; druckbarer HTML-Bericht. PDF ist optional und darf aus HTML erzeugt werden. | **BESCHLOSSEN** |
| DEC-025 | UI-Standardzeitraum: 1 Monat. | **BESCHLOSSEN** |
| DEC-026 | Chart: Heute/1W/1M nativ `1h`, 1J deterministisch `4h`, 3J deterministisch `1d`; Nutzer darf eine verfügbare Auflösung wählen. Strategie und Signale werden immer auf `1h` berechnet, nie auf aggregierten UI-Bars. | **BESCHLOSSEN** |
| DEC-027 | Markt-/Backtestdaten und Trade-/Audit-Ledger bleiben für Reproduzierbarkeit dauerhaft. Betriebslogs 90 Tage online, danach löschbar; Incidentberichte und Release-Nachweise dauerhaft. | **BESCHLOSSEN** |
| DEC-028 | Oberfläche Deutsch; technische IDs, API-Felder und Symbole bleiben unverändert/kopierbar. | **BESCHLOSSEN** |
| DEC-032 | Es gibt genau eine `Startbot.bat` für Windows. Sie enthält keine Fachlogik und delegiert an den einzigen technischen Einstieg `src/main.py start`. Weitere Starterdateien sind verboten. | **BESCHLOSSEN** |
| DEC-033 | Die am 01.09.2026 browsergeprüfte V1-Optik ist vom Eigentümer freigegeben und visuell eingefroren. Neue Betriebsinformationen verwenden die vorhandenen Karten, Tabellen, Farben, Abstände und Navigation; ein Redesign erfolgt nur nach neuer ausdrücklicher Freigabe. | **BESCHLOSSEN** |

## Vom Nutzer verbindlich vorgegeben

**DEC-048 – BEAUFTRAGT / TEILIMPLEMENTIERUNG 0.4.2, 07.09.2026:** Eigentümer verlangt auffindbare API-Key-Eingabe mit Konto-/Rechteprüfung, separaten 50-USDT-Einmaltest und späteren Live-an/aus-Betrieb nach bestätigten Paper-Slots. Paper bleibt als unabhängige Informationsquelle aktiv. „Aus“ blockiert neue Einstiege, darf offene Paper-/Echtgeldpositionen weder zwangsverkaufen noch ausblenden; deren regulärer Ausstieg und Abgleich bleiben erforderlich. Manueller Eingriff bei Binance muss später erkannt werden, nicht automatische Neukäufe/Doppelverkäufe verursachen. Implementiert: sichtbare gesperrte Key-Felder, Steuerungsoberfläche, validierte gesperrte Startanforderung, separat fake-getesteter Einmalcontroller und Entry-Stopp. Produktiver Adapter/Supervisor/Reconciler und Mehrslot-Live bleiben offen (DMS 20). Kein echter Test wurde gestartet, keine neue Schlüssel-/Kontofreigabe durch den Entwicklungsagenten.

**DEC-047 – TESTABLAUF BESCHLOSSEN, NOCH NICHT IMPLEMENTIERT/FREIGEGEBEN, 07.09.2026:** Eigentümer bestätigt genau einen vollständigen Echtgeldtrade: nach Betreiberstart auf ein neues gültiges Hixton-Signal aus zehn Coins warten, höchstens 50 USDT Kaufnotional mit dem tatsächlichen Coin-Profil einsetzen, regulären Strategieausstieg abwarten und danach dauerhaft keine neuen Entries. Kein sofortiger technischer Rundlauf und kein automatischer Übergang zu 3×80. Reale Binance-Fills, Gebühren, Kontobewegungen, Regel-/Signalnachweis und Exitgrund getrennt von Paper dokumentieren; nicht konfigurierte Stop-/Take-Profit-Regeln nicht als bestanden ausgeben. Einmalbudget muss auch über konkurrierende Anfragen, Teilfills und Neustarts gelten. Die Rückfrage aus DEC-046 ist damit geklärt. Die Normierung von 50 USDT als Kaufnotional mit separat ausgewiesenen Gebühren folgt dem bestehenden Notional-Modell; keine 500-USDT-Order und keine dynamische Budgeterhöhung. Implementierung, Testfreigabe und tatsächlicher Start durch den Betreiber bleiben getrennte Schritte. Vollständiger Ablauf/Nachweis sowie bestehende V6-Stop-/Take-Profit-Grenzen: DMS 20.

**DEC-046 – BEAUFTRAGT, TEILUMSETZUNG 06.09.2026 / Anwendung 0.4.0:** Eigentümer verlangt dauerhaft bedienbare Paper-Settings und Vorbereitung eines späteren Live-An/Aus-Ablaufs mit sicher eingegebenem Binance-Key/Secret. Erster beabsichtigter Echtgeldversuch 1×50, spätere Erhöhung auf 3×80 und dann insgesamt 750 USDT nur ausdrücklich, nicht automatisch. Implementiert: Entwurfs-/Polling-Fix, validierte persistente Paperänderung ohne Reset, Windows-Schlüsselablage mit lokalem Passwort/Session, read-only Binance-Vorcheck, transparente gesperrte Live-Anforderung. **Nicht implementiert/freigegeben:** Echtgeld-Dispatcher, echte Fill-/Positionsbuchung, Recovery/Reconciliation und vollständige Live-Abnahme. Der Auftrag erteilt keine Erlaubnis zum Auslösen realer Testorders durch den Entwicklungsagenten und hebt die bestehenden DMS-Gates nicht stillschweigend auf. V6-Profile, bestehende Paper-Settings und Konto bleiben bei Auslieferung unverändert. Die im UI sichtbare höhere Ausbauperspektive hebt die 240-USDT-Papergrenze nicht vorzeitig auf. Offene Arbeiten und Schlüsselsicherheit stehen in DMS 20/11.

- Die reine Dokumentationsphase wurde nach dem DMS-Freeze beendet; anschließend wurde der Bau ausdrücklich beauftragt.
- Zehn Kryptowährungen auf Binance Spot/USDT.
- Backtest-Batch: zehn isolierte Tests à 250 USDT; Einzeltest für einen wählbaren Coin ebenfalls 250 USDT.
- 24/7-Paperbetrieb als Pflichtvorbereitung für Live.
- Neuer Paperstart: 250 USDT als drei Positionsbudgets à 80 USDT plus 10 USDT Anfangsreserve; Echtgeldfreigabe separat.
- Dreijähriger Primärbacktest und lokale Historie.
- UI-Charts Heute, 1 Woche, 1 Monat, 1 Jahr und 3 Jahre.
- Startup-Vollprüfung aller zehn Coins und tägliches Nachziehen.
- Die Strategie basiert ausschließlich auf der dokumentierten Hixton-Logik; aktive Paperparameter sind die V6-Coin-Profile, V2 und V1 bleiben historische Referenzen.
- Die bestbelegte geprüfte Verbesserung soll im Paperbetrieb übernommen werden; eine Backtestwahl oder ein einzelner Spitzenwert schaltet nie automatisch um.
- Mehrere Slots im selben Coin dürfen erforscht werden, bleiben aber gesperrt, solange sie den risikogleichen Vergleich nicht gewinnen.
- GitHub ist die zentrale Projektablage; übersichtliche Struktur, ein technischer Einstiegspunkt, Backtestversionen in getrennten Versionsordnern.
- Eine einzige `Startbot.bat` startet Paper-Bot und UI; Ordnung, laufendes Aufräumen und dokumentierte Sauberkeitsregeln sind verbindlich.

## Umgang mit der Eigentümer-Pine-Quelle

Die Quelle liegt seit 01.09.2026 vor. Sie ist gehasht, versioniert und über eine unabhängige Testimplementierung gegen die Python-Engine abgesichert. Sie ersetzt weder V1-Artefakte noch bereits verbuchte Paperereignisse. Jede Parameteränderung erzeugt einen neuen Snapshot und Backtestordner; eine spätere Aktivierung gilt nur vorwärts.

## Änderungsformat nach dem Freeze

```text
Entscheidung: DEC-xxx
Datum/Zeitzone:
Entschieden von:
Beschluss:
Begründung:
Betroffene Anforderungen/Dokumente:
Neue Strategie-/Konfigurationsversion:
Erforderliche neue Tests/Backtests:
```

## Restarbeiten sind Nachweise, keine Entscheidungen

Vor Implementierung fehlen keine kritischen fachlichen Festlegungen. Vor Backtest, Paper oder Live müssen jedoch die jeweiligen Nachweise erzeugt werden: Code-/Config-/Pine-Hashes, Golden-Fixtures, echte Binance-Daten, Backtestergebnisse, API-Key-Berechtigungsprüfung, sichtbare P1/P2-Alarme, Backup-Restore und Paper-Soak. Diese Artefakte dürfen nicht vorgetäuscht werden und werden in DMS 12 über Freigabegates kontrolliert.
