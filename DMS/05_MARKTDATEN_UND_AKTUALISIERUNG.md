# 05 – Marktdaten und Aktualisierung

## Datenumfang

Primärquelle und Handelsplatz sind Binance Spot. Historische Klines, laufende Kline-Streams, Serverzeit, Symbolstatus und Orderfilter werden über die offiziellen Binance-Schnittstellen bezogen. Ein späterer Providerwechsel ist eine versionierte Datenentscheidung und darf Serien nicht still mischen.

Pro aktivem Symbol und Trading-Timeframe werden gespeichert:

- Open-Time und Close-Time in UTC;
- Open, High, Low, Close;
- Basisvolumen und, sofern verfügbar, Quote-Volumen;
- Tradeanzahl (`optional`, providerabhängig);
- Kennzeichen `closed`/`provisional`;
- Datenquelle, Abrufzeit und Import-Batch-ID.

Preise und Mengen werden decimal-sicher gespeichert, nicht als unkontrollierte binäre Gleitkommazahl. Der verbindliche Signaltimeframe aller aktuellen Strategieversionen ist **1 Stunde (`1h`)**. Die UI-Zeiträume sind **keine** Trading-Timeframes.

## Historienanforderung

- Mindestens drei vollständige Jahre vor dem gewählten Backtest-Ende.
- Zusätzlich Warm-up-Bars vor dem Berichtsstart, sodass der erste berichtete Bar alle Indikatoren vollständig initialisiert hat.
- Wenn verfügbar, wird die gesamte konsistente Historie gespeichert und separat ausgewertet.
- Datenquelle (`binance_spot`) und Symbolmapping werden je Import festgehalten.
- Wechsel der Börse oder Datenquelle erzeugt einen neuen Datensatzstand; Serien werden nicht still gemischt.

## Startup-Sequenz

Bei jedem Start läuft vor der Strategieaktivierung:

1. Konfiguration und Schema validieren.
2. Systemuhr und UTC-Konvertierung prüfen.
3. Datenbankintegrität prüfen.
4. Börsenmetadaten für alle zehn Paare laden: Status, Tick Size, Step Size, Mindestmenge, Mindestnotional.
5. Pro Paar lokalen ersten/letzten Bar, erwartete Baranzahl, Duplikate, Lücken und OHLC-Konsistenz prüfen.
6. Fehlende Bereiche paginiert nachladen.
7. Neueste potenziell offene Kerze aktualisieren, aber als `provisional` markieren.
8. Nur vollständig geschlossene Bars freigeben.
9. Indikator-Warm-up und aktuellen Trendzustand neu berechnen bzw. mit Checkpoint vergleichen.
10. Im Paper-/Live-Modus Orders, Fills, Positionen und Salden synchronisieren.
11. Erst bei grünem Ergebnis Signalverarbeitung aktivieren; sonst `DEGRADED` oder `HALTED` melden.

Ein Startup darf keine historischen Signale als nachträgliche Live-Orders abspielen.

## Laufende Aktualisierung

- Stream/WebSocket liefert Live-Ticks oder Kline-Updates.
- Eine laufende Kerze darf in der UI aktualisiert werden, bleibt aber `provisional`.
- Nach offiziellem Kerzenschluss wird die Kerze per Primärquelle finalisiert.
- Bar-Close-Event wird genau einmal publiziert.
- Bei Streamabbruch startet exponentieller Reconnect mit Jitter.
- Nach Reconnect wird die Lücke per REST geschlossen, bevor neue Signale freigegeben werden.
- Ein Watchdog vergleicht erwartete und letzte Barzeit.
- Die aktuelle UTC-Stundengrenze ist das exklusive Ende der abgeschlossenen Daten. In den ersten zwei Minuten wird **keine zusätzliche Stunde abgezogen**. Der Watchdog prüft die erwartete letzte Kerze unabhängig vom Websocket-Close-Event; fehlende finale Daten oder das nächste Open führen zu Retry, nicht zu einer vorgerückten Paper-Checkpointzeit.
- Die neu begonnene Kerze wird separat geladen. Nur ihr unveränderliches Open dient als Paper-Ausführungsreferenz; High/Low/Close der offenen Kerze dürfen keine Strategieentscheidung beeinflussen.
- Mehr als 90 Sekunden ohne Streamupdate setzt den Feed auf `DEGRADED`.
- Fehlt die finale 1h-Kerze zwei Minuten nach ihrem planmäßigen UTC-Schluss, wird das Symbol pausiert und per REST repariert.

## Täglicher Mitternachtsjob

Verbindlicher Zeitpunkt: **00:05 UTC**. Der Puffer vermeidet die Verarbeitung einer noch nicht final bereitgestellten Tagesgrenze. In der UI wird zusätzlich die lokale Zeit Europe/Berlin angezeigt.

Der Job:

1. prüft alle zehn Paare;
2. lädt fehlende abgeschlossene Bars nach;
3. ersetzt ausschließlich vorläufige Bars durch finale Providerwerte;
4. prüft Duplikate, Zeitraster, OHLC-Regeln und Datenfrische;
5. aktualisiert Börsenfilter und Symbolstatus;
6. erstellt einen Datenqualitätsbericht;
7. markiert Backtestergebnisse als veraltet, falls zugrunde liegende historische Bars korrigiert wurden;
8. alarmiert bei Lücken oder Delisting, statt still ein Ersatzsymbol zu wählen.

## Datenqualitätsregeln

| Regel | Reaktion |
|---|---|
| doppelte `(exchange, symbol, timeframe, open_time)` | Import blockieren oder deterministisch identische Duplikate zusammenführen; Abweichung alarmieren |
| fehlender erwarteter Bar | nachladen; bis dahin Signalverarbeitung für Symbol pausieren |
| `high < max(open, close, low)` oder `low > min(open, close, high)` | Bar quarantänisieren |
| negatives Volumen | Bar quarantänisieren |
| Zeitstempel nicht auf Raster | Bar quarantänisieren |
| Kurs-/Volumensprung | nicht automatisch löschen; als Ausreißer markieren und Quelle gegenprüfen |
| Provider korrigiert alte Bar | neue Datenversion, Audit-Eintrag, abhängige Runs `STALE` |

Fehlende Bars werden nicht durch lineare Interpolation, Forward-Fill oder künstliche Nullvolumenkerzen ersetzt, außer eine Börsendokumentation bestätigt ausdrücklich eine handelsfreie Periode und die Entscheidung ist versioniert.

## Caching und UI-Auflösung

- Heute, 1W und 1M: native gespeicherte `1h`-Bars.
- 1J: standardmäßig deterministisch zu `4h` aggregiert.
- 3J: standardmäßig deterministisch zu `1d` aggregiert.
- Nutzer kann eine verfügbare Auflösung wählen; Strategieoverlay und Signalmarker bleiben Ergebnisse der nativen `1h`-Berechnung.
- Aggregation/Downsampling ist nur Darstellung und verändert keine Backtestdaten.
- Aggregierte OHLCV-Bars: Open = erstes Open, High = Maximum, Low = Minimum, Close = letztes Close, Volumen = Summe.
- Chart-Downsampling darf Signalmarker, lokale Extrema und Positionsevents nicht verfälschen.

## Zeitzonen

- Persistenz, Strategie, Scheduler-Referenz und APIs: UTC.
- UI: UTC und optional Europe/Berlin; Auswahl muss sichtbar sein.
- „Heute“ bedeutet 00:00 bis jetzt in der in der UI gewählten Zeitzone.
- Backtestgrenzen werden als exakte UTC-Zeitstempel gespeichert, nicht nur als Datumsstring.
