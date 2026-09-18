# 02 – Verbindliche Anforderungen

Aktueller Vorrang: **DMS 1.12.0 / DEC-053 / Anwendung 0.4.7**. Der integrierte Code verwendet USDC (250 Modellstart, Standard 3×80; später genau ein 50-USDC-Test). Alte datierte USDT-Anforderungen/Ergebnisse sind Historie, keine umgerechneten USDC-Nachweise. Runtime- und Laptop-Deployment sind getrennt zu prüfen. Kein Echtgeldstart: technischer Restarbeitsplan in [DMS 20](20_BETRIEBSRUNBOOK.md), tatsächlicher Testnachweis in [DMS 12](12_TESTS_ABNAHMEKRITERIEN.md). Bestehende Live-Sicherheitsgates bleiben wirksam.

CAP-010 / OPS-010 (aktuell, VERBINDLICH): Nur ausdrücklich bestätigter Offline-Neuanfang darf nach geprüftem Vollarchiv das aktive Paperledger zurücksetzen. Kapitalbaseline 250 USDC, drei Slots à 80 USDC; kein Übertrag alter Gewinne/Verluste oder Soak-Tage. Normale Starts und Backtests dürfen keinen Reset auslösen.

Ergänzung STR-009 / CAP-009 (DEC-043/044, VERBINDLICH): Ein Coin-Profil besteht aus versionierten Hixton-Parametern und expliziten Zusatzregeln. Paper, Einzeltest, Batch und Portfolio müssen dieselbe ausgewählte Definition verwenden; Charts zeigen qualifizierte Signale getrennt von tatsächlichen Paper-Fills. Eine gemeinsame Einstellung darf je Coin beibehalten werden, wenn sie im begrenzten Vergleich besser belegt ist. Profilindividualisierung ist kein Gewinnnachweis. Schlechtere Portfolio-/Stress-/Altfenster werden berichtet, nicht durch mehr Trades oder gelockerte Risikogates verdeckt.

Die IDs bleiben über die Entwicklung stabil. Änderungen werden nicht durch Umnummerieren versteckt.

## Strategie

| ID | Anforderung | Status |
|---|---|---|
| STR-001 | Der Bot setzt ausschließlich die freigegebene Hixton-/VIDYA-/ATR-Signallogik um. | VERBINDLICH |
| STR-002 | Signalentscheidungen verwenden nur abgeschlossene Kerzen. | VERBINDLICH |
| STR-003 | Ein Trendwechsel auf `UP` erzeugt höchstens einen Kauf-Intent; Wiederholungen im selben Trend erzeugen keinen neuen Einstieg. | VERBINDLICH |
| STR-004 | Ein Trendwechsel auf `DOWN` schließt eine vorhandene Long-Position; Short-Einstieg ist verboten. | VERBINDLICH |
| STR-005 | Verbindliche V1-Referenz ist `HIXTON-SPEC-1.0` aus DMS 03: 1h, Close, VIDYA 10, CMO 20, SMA 15, Wilder-ATR 200, Band 2.0, Warm-up 400, Startzustand DOWN ohne Initialorder. | VERBINDLICH |
| STR-006 | Spezifikationsparität wird über Golden-Testvektoren für mindestens 1.000 aufeinanderfolgende Bars je Testmarkt belegt. | VERBINDLICH |
| STR-007 | Ein Signal wird mit Symbol, Kerzenzeit, Strategieversion, Parametern, Eingabewerten und Grund gespeichert. | VERBINDLICH |
| STR-008 | Die Eigentümer-Pine-Quelle ist die Formelreferenz für V2. V1, V2 und spätere Challenger besitzen getrennte Versionen, Backtestordner und Freigabestatus; ein Wechsel der aktiven Paperstrategie erfolgt nur explizit, atomar und auditierbar. | VERBINDLICH |

## Märkte und Kapital

| ID | Anforderung | Status |
|---|---|---|
| MKT-001 | Genau zehn aktive USDC-Spot-Paare bilden das aktive Universum. Historische USDT-Kerzen dürfen nur als klar gekennzeichneter gleicher-Basisasset-Preisproxy für vor-USDC-Zeiträume dienen. | VERBINDLICH |
| MKT-002 | Aktives Universum: BTC, ETH, BNB, SOL, XRP, ADA, LINK, AVAX, DOT und DOGE gegen USDC. Handelbarkeit wird aktuell über Binance Spot geprüft; fehlende drei Jahre echte USDC-Historie werden nicht erfunden. | VERBINDLICH |
| MKT-003 | Die Coinliste wird nicht automatisch nach Performance ausgetauscht. Eine spätere Überprüfung ist versioniert, vorwärtsgerichtet und benötigt neue Backtests. | VERBINDLICH |
| CAP-001 | Paper-/späteres Live-Portfolio startet neu mit 250,00 USDC aus einem gemeinsamen Cashbestand: 3×80 USDC plus 10 USDC anfängliche Reserve. Bestehende Ledger werden nicht aufgefüllt. | VERBINDLICH |
| CAP-002 | Baseline 3×80 USDC. Aktive V6-Slotvergabe ist `ranked_repeat`: gültige Kandidaten erhalten nach Rangfolge zunächst je einen Slot, verbleibende freie Slots gehen erneut an den stärksten gültigen Kandidaten. Ein Coin kann damit bei nur einem gültigen Signal 3×80 USDC tragen. | VERBINDLICH |
| CAP-003 | Positionsgröße und Slotanzahl sind später in der UI änderbar; Änderungen gelten nur vorwärts, werden validiert, bestätigt und auditierbar versioniert. | VERBINDLICH |
| CAP-004 | 250→500 USDT und genannte Tradezahlen sind illustrative Beispiele, keine verpflichtenden Optimierungs- oder Freigabequoten. Jeder Backtest prüft zuerst korrekte Reaktion und berichtet danach die vollständige Nettoperformance. | VERBINDLICH |
| CAP-005 | Bei mehr Kaufkandidaten als freien Slots gewinnt der auf 12 Dezimalstellen Half-Even gerundete größte Wert `(close-upper)/ATR`; Gleichstand folgt der festen Coinreihenfolge aus DMS 03. | VERBINDLICH |
| CAP-006 | Primärziel der Portfolioauswahl ist maximaler Nettogewinn nach Kosten; hohe Tradezahl ist nur Sekundärziel. | VERBINDLICH |
| CAP-007 | Die bestbelegte zulässige Strategieverbesserung wird nach bestandenem Vergleich und ausdrücklicher Entscheidung vorwärtsgerichtet als Paperstandard übernommen. „Bestbelegt“ verlangt Reproduzierbarkeit, Kosten-Stress, Altfenster und den risikogleichen 3×80-Spiegel; ein höchster Einzelwert genügt nicht. Live bleibt ein separates Gate. | VERBINDLICH |
| CAP-008 | Mehrere Slots desselben Coin-Signals sind in der aktiven V6 als `ranked_repeat` ausdrücklich freigegeben. Sie bleiben ein gemeinsamer Signal-/Positionszyklus mit `slot_count` 1–3 und werden zusätzlich als Slot-Trades ausgewiesen. | VERBINDLICH |
| RSK-001 | Kein Leverage, keine Margin, keine Futures und keine API-Auszahlungsrechte. | VERBINDLICH |
| RSK-002 | Börsenfilter wie Mindestnotional, Schrittweite und Präzision werden vor jeder Order geprüft. | VERBINDLICH |
| RSK-003 | Tagesverlust ab 5 % der Start-of-Day-Equity pausiert neue Entries bis zum nächsten UTC-Tag. Portfolio-Drawdown wird vollständig gemessen und ausgewiesen, erzeugt aber keinen permanenten globalen Halt. `HALTED` bleibt technischen/operativen Sicherheitsfällen vorbehalten. | VERBINDLICH |
| RSK-004 | Es gibt kein automatisches Compounding; Zielnotional bleibt in der Baseline im Paper-/Portfolio-Modell 80 USDC je Slot und im isolierten Backtest 250 USDC bzw. wird bei unzureichendem Cash abwärts begrenzt. | VERBINDLICH |

## Daten

| ID | Anforderung | Status |
|---|---|---|
| DAT-001 | OHLCV-Daten werden je Symbol und Timeframe dauerhaft gespeichert. | VERBINDLICH |
| DAT-002 | Beim Start werden Schema, Zeitraum, Lücken, Duplikate, letzte geschlossene Kerze und Datenfrische für alle zehn Paare geprüft. | VERBINDLICH |
| DAT-003 | Fehlende Daten werden inkrementell nachgeladen, paginiert und anschließend erneut validiert. | VERBINDLICH |
| DAT-004 | Täglich um 00:05 UTC läuft ein vollständiger Aktualitäts- und Lückenaudit. | VERBINDLICH |
| DAT-005 | Laufende Kurse kommen aus einem Stream; ein Polling-/REST-Fallback verhindert dauerhafte Blindheit. | VERBINDLICH |
| DAT-006 | Offene Kerzen werden als vorläufig markiert und nie als abgeschlossene Signalbasis behandelt. | VERBINDLICH |
| DAT-007 | UI-Historie bis drei Jahre verwendet die lokal gespeicherten, qualitätsgeprüften Daten. | VERBINDLICH |

## Backtest

| ID | Anforderung | Status |
|---|---|---|
| BKT-001 | Signalverifikation und Primärbericht nutzen exakt drei vollständige Jahre pro Paar; zusätzlich Bericht über die gesamte verfügbare qualitätsgeprüfte Historie. | VERBINDLICH |
| BKT-002 | Orders werden frühestens zum nächsten handelbaren Preis nach einem bestätigten Signal gefüllt. | VERBINDLICH |
| BKT-003 | Gebühren, Slippage, Tick-/Lot-Rundung und Mindestnotional sind Teil der Simulation. | VERBINDLICH |
| BKT-004 | Kein Look-ahead, Survivorship-Bias oder stilles Auffüllen synthetischer Preise. | VERBINDLICH |
| BKT-005 | Einzel- und Portfolioergebnisse enthalten PnL, Rendite, Drawdown, Trades, Kosten, Exposure und Benchmark. | VERBINDLICH |
| BKT-006 | Jeder Lauf erzeugt ein unveränderliches Run-Manifest und Datenqualitätsprotokoll. | VERBINDLICH |
| BKT-007 | Kapitalunabhängige Signalparität wird getrennt von PnL- und Portfoliosimulation ausgewiesen. | VERBINDLICH |
| BKT-008 | Standard-Batchlauf: zehn isolierte Coin-Backtests mit jeweils 250,00 USDC Startkapital. Dieser Modus dient zugleich der Coin-für-Coin-Diagnose und train/validation-getrennten Profilforschung. | VERBINDLICH |
| BKT-009 | Einzelmodus: ein frei wählbares Paar, zum Beispiel ETH/USDC, wird separat mit 250,00 USDC getestet. | VERBINDLICH |
| BKT-010 | Der gemeinsame Spiegellauf verwendet 250 USDC Startkapital und die aktuell gespeicherte Slot-/Notionalaufteilung (Baseline 3×80), dieselbe 5-%-UTC-Tagespause wie Paper und keinen permanenten Drawdown-Halt. Aufteilung und Slotpolicy im Manifest festhalten. | VERBINDLICH |
| BKT-012 | Jede akzeptierte Coin-Profiländerung wird ausschließlich in der kanonischen `StrategyDefinition` versioniert. Danach müssen 10×250, 3×80, Paper und UI exakt dieselben per-Coin-Parameter/Policies lesen; Parameterhash-Parität ist Abnahmekriterium. Eine isolierte Verbesserung allein ist keine Freigabe. | VERBINDLICH |
| BKT-011 | Baseline je Orderseite: 10 bps Gebühr + 2 bps Spread + 3 bps Slippage; Stress: 10 + 10 + 20 bps. Kosten wirken advers auf Kauf und Verkauf. | VERBINDLICH |
| BKT-012 | Strategieverbesserungen werden nur als neue Backtestversion angelegt. Suchraum, Auswahlregel, ältere Marktsegmente, Kosten-Stress, Nachbarparameter und verworfene Varianten werden dokumentiert; mehr Trades sind nur bei robuster Nettowirkung besser. | VERBINDLICH |

## Ausführung

| ID | Anforderung | Status |
|---|---|---|
| EXE-001 | Signal, Order-Intent, Börsenorder, Fill und Position sind getrennte Zustände. | VERBINDLICH |
| EXE-002 | Idempotency-Key verhindert Doppelorders je Symbol, Strategieversion und Signalkerze. | VERBINDLICH |
| EXE-003 | Beim Neustart wird zuerst mit Börsenorders, Fills und Kontostand abgeglichen; vorher keine neue Live-Order. | VERBINDLICH |
| EXE-004 | Teilfills, Ablehnung, Timeout, Rate-Limit und Netzwerkverlust besitzen dokumentierte Zustandsübergänge. | VERBINDLICH |
| EXE-005 | Not-Aus verhindert neue Einstiege. Ob vorhandene Positionen gehalten oder liquidiert werden, ist eine getrennte, bestätigungspflichtige Aktion. | VERBINDLICH |
| EXE-006 | Eine später freigegebene Liveversion verwendet Market-Orders mit 25-bps-Vorab-Preisabweichungsgrenze; nach 10 Sekunden ohne eindeutige Bestätigung wird `UNKNOWN` gesetzt und reconciled, nicht neu gesendet. | VERBINDLICH |

## UI

| ID | Anforderung | Status |
|---|---|---|
| UI-001 | Dashboard zeigt zehn Märkte, Trend, Position, Datenfrische, Preis, unrealisierten PnL und letzte Aktion. | VERBINDLICH |
| UI-002 | Chartbereiche: Heute, 1W, 1M, 1J und 3J. | VERBINDLICH |
| UI-003 | Chart zeigt Kerzen, VIDYA/Trendlinie, ATR-Bänder, Kauf-/Verkaufsmarker und offene Position. | VERBINDLICH |
| UI-004 | Live-/vorläufige Kerze ist visuell eindeutig von geschlossenen Kerzen getrennt. | VERBINDLICH |
| UI-005 | Jede Zahl zeigt Einheit, Bezugszeitraum und bei Zeitwerten die Zeitzone. | VERBINDLICH |
| UI-006 | Paper und Live sind farblich/textlich deutlich; Live-Aktivierung verlangt eine explizite Bestätigung. | VERBINDLICH |
| UI-007 | Backtestseite zeigt Annahmen und Kosten direkt neben Ergebnissen. | VERBINDLICH |
| UI-008 | Standardbereich ist 1M; Heute/1W/1M zeigen standardmäßig 1h, 1J 4h und 3J 1d. Signale bleiben immer 1h-basiert. | VERBINDLICH |

## Betrieb, Sicherheit und Qualität

| ID | Anforderung | Status |
|---|---|---|
| OPS-001 | Health-Status umfasst Datenfeed, Scheduler, Datenbank, Börsenverbindung, letzte Kerze und letzte erfolgreiche Synchronisation. | VERBINDLICH |
| OPS-002 | Strukturierte Logs haben UTC-Zeit, Korrelations-ID, Schweregrad und redigieren Geheimnisse. | VERBINDLICH |
| OPS-003 | Backups und Restore werden automatisiert erstellt bzw. regelmäßig getestet. | VERBINDLICH |
| OPS-004 | Paper-Soak dauert mindestens 30 Tage und 720 geschlossene 1h-Bars je aktivem Symbol; bei weniger als 20 abgeschlossenen Trades wird bis 20 Trades, höchstens 90 Tage, verlängert. | VERBINDLICH |
| OPS-005 | Manuelles Trading auf demselben Binance-Konto ist verboten; Live nutzt einen eigenen Bot-Subaccount bzw. ein ausschließlich dem Bot zugeordnetes Spot-Konto. | VERBINDLICH |
| OPS-006 | P1/P2-Ereignisse müssen dauerhaft und auffällig in lokaler UI sowie strukturierten Logs erscheinen. Der Eigentümer überwacht den Bot regelmäßig manuell; Telegram ist kein Pflichtkanal und kein Live-Gate. | VERBINDLICH |
| OPS-007 | Verschlüsselte Backups außerhalb Git/aktiver DB: 7 täglich, 4 wöchentlich, 12 monatlich; Restore vor Live und vierteljährlich. | VERBINDLICH |
| OPS-008 | Die UI bindet nur an localhost; nach Paperfreigabe läuft der Bot als Windows-Service mit Reconciliation bei jedem Start. | VERBINDLICH |
| SEC-001 | Secrets stehen nie in Quellcode, DMS, Logs oder UI-Exporten. | VERBINDLICH |
| SEC-002 | API-Key erhält nur Lesen und Spot-Handel; Auszahlung ist verboten. | VERBINDLICH |
| SEC-003 | Live wird nur nach Strategieparität, Backtest, Paper-Soak-Test und Restore-Test freigeschaltet. | VERBINDLICH |
| QLT-001 | Kritische Anforderungen sind in der Traceability-Matrix mit mindestens einem Test verknüpft. | VERBINDLICH |
| COL-001 | Zentrale Projektablage ist `https://github.com/127027/Der-Hixton`. Geprüfte Arbeitsstände werden fortlaufend committed und gepusht; 99-%-Freigabe wird separat als Release/Tag markiert. Secrets sind immer verboten. | VERBINDLICH |
| COL-002 | Das Repository ist öffentlich. Die am 01.09.2026 vom Eigentümer zur Projektverwendung bereitgestellte Pine-Datei darf versioniert veröffentlicht werden; fremde Quellen ohne Rechte und Secrets bleiben verboten. Eine Open-Source-Lizenz wird ohne eigene `LICENSE` nicht unterstellt. | VERBINDLICH |
