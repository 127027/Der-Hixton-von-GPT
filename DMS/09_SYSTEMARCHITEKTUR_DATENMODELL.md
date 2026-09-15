# 09 – Systemarchitektur und Datenmodell

V6-Erweiterung ohne zweite Engine: `StrategyDefinition` hält eine vollständige unveränderliche Map aus zehn `CoinProfile`-Einträgen. Jeder enthält `StrategyParameters` und `TradePolicy`. Analyse, Paper, Einzel-/Batch-/Portfoliobacktest und Chart lesen diese Quelle. SQLite-Positionen erhalten `entry_atr_text` und `highest_close_text` mit Legacy-Default 0; alte Zeilen werden nicht gelöscht. V6-Positionen ohne persistierten Entry-ATR stoppen die Verarbeitung sicher. Strategie-ID enthält den Profilhash.

## Architekturprinzipien

- Strategie-Domain bleibt unabhängig von Börse, UI und Speicher.
- Backtest, Paper und Live verwenden dieselbe Signalengine.
- Alle externen Systeme liegen hinter Adaptern.
- Zustandsänderungen sind persistent, auditierbar und idempotent.
- UTC und Decimal sind fachliche Standards.
- Sichere Degradierung: Unsicherheit stoppt neue Orders, nicht die Transparenz.

## Zwei Systeme, ein gemeinsamer Strategiekern

1. **Backtest-Labor:** historische Replay-/Batchläufe, standardmäßig 10×250 USDT oder ein frei gewählter Einzeltest mit 250 USDT; niemals Börsenorders.
2. **24/7 Paper-/Live-System:** laufende Binance-Daten, anfangs 250 USDT gemeinsamer Cashpool (10 USDT Startreserve) und drei Slots à 80 USDT; Paper ist Pflichtvorstufe für Live.

Die Systeme sind getrennte Laufmodi und Ledgers, aber keine getrennten Kopien der Hixton-Formel. Beide verwenden dieselbe versionierte Indicator-/Strategy-Engine. Dadurch wird verhindert, dass der Backtest „richtig“ und Paper/Live anders reagiert.

## Logische Komponenten

| Komponente | Verantwortung |
|---|---|
| Config & Versioning | Schema, Defaults, Freigaben, Hashes |
| Market Data Adapter | Historie, Stream, Metadaten, Rate-Limits |
| Data Quality Service | Lücken, Duplikate, Quarantäne, Freshness |
| Indicator Engine | VIDYA/ATR/Trend deterministisch berechnen |
| Strategy Engine | Flip und Position-Intent erzeugen |
| Risk/Guard Service | Health, Kapital, Filter, Modus und Not-Aus prüfen |
| Execution Adapter | Paper oder Börsenorder und Fills |
| Portfolio Ledger | Cash, Positionen, Gebühren, realisierter/unrealisierter PnL |
| Backtest Engine | historische Eventsimulation und Benchmarks |
| Scheduler | Startup, Bar-Close, 00:05-UTC-Audit, Backup |
| API | lesende/steuernde UI-Schnittstelle mit Rechteprüfung |
| UI | Dashboard, Chart, Reports, Einstellungen |
| Observability | Logs, Metriken, Health und Alerts |

## Verbindlicher Referenzstack

- Python-3-Service für Domain, Backtest und Adapter;
- lokale relationale Datenbank, initial SQLite im WAL-Modus; Migration auf PostgreSQL möglich;
- lokale Web-API;
- TypeScript-Web-UI mit einer Candlestick-fähigen Chartbibliothek;
- schema-validierte YAML/JSON-Konfiguration plus Secret-Store/Umgebungsvariablen;
- ein Prozessmanager/Windows-Service für Autostart.

Framework- und Paketversionen werden beim Implementierungsstart in Lockfiles festgeschrieben. Ein Stackwechsel benötigt Architekturentscheidung und Migrationstest; er darf Strategie-, Decimal-, UTC-, Ledger- oder Auditsemantik nicht verändern.

## Kernobjekte

### `candle`

Schlüssel: `exchange`, `symbol`, `timeframe`, `open_time_utc`.

Felder: OHLCV, close time, final/provisional, source, import batch, revision, quality status, created/updated time.

### `indicator_value`

Schlüssel: Strategieversion, Parameterhash, Symbol, Timeframe, Barzeit.

Felder: VIDYA, upper/lower, Trendzustand, flip flags, Warm-up/valid flag.

### `signal`

Signal-ID, Symbol, Barzeit, Typ, Strategieversion, Parameterhash, Indikator-Snapshot, created time, origin (`BACKTEST/PAPER/LIVE`).

### `order_intent`

Intent-ID, Idempotency-Key, Signal-ID, Aktion, gewünschte Menge/Notional, Guards, Status, Grund, Konfigurationsversion.

### `exchange_order` und `fill`

Provider-ID/Client-ID, Zustand, Menge, Limit/Typ, Preise, Gebühren, Zeitstempel und Rohantwort-Referenz. Secrets werden nie persistiert.

### `ledger_entry`

Doppelte Buchführung bzw. unveränderliche Bewegungszeile für Cash, Asset, Gebühren, realisierten PnL und Korrekturen. Ableitbare Kontostände werden nicht ohne Herkunft überschrieben.

### `position_snapshot`

Symbol, Menge, Durchschnittspreis, Marktwert, PnL, Source und Zeit. Snapshot ersetzt nicht das Ledger.

### `backtest_run`

Run-ID, Status, Zeitfenster, Strategie-/Config-/Daten-/Codehash, Kostenmodell, Seed, Umgebung, Ergebnisse und Artefaktpfade.

### `audit_event`

Zeit, Actor, Aktion, Objekt, vorher/nachher bzw. Referenz, Korrelations-ID und redigierte Details.

## Zustandskonsistenz

- Persistenz eines Bar-Close-Events und seiner Verarbeitung muss idempotent sein.
- Eine Signal-ID ist für denselben Input stabil.
- Ledger-Einträge werden nicht gelöscht; Korrekturen erfolgen durch Gegenbuchung.
- Schemaänderungen laufen über versionierte Migrationen.
- Backtestdaten sind immutable je Datenversion.
- UI-Abfragen dürfen laufende Handelsverarbeitung nicht blockieren.

## API-Grenzen

Mindestens benötigt:

- Health/Systemstatus;
- Märkte und aktuelle Snapshots;
- Chartdaten nach Symbol, Zeitraum und Auflösung;
- Signale, Intents, Orders, Fills und Positionen;
- Backtestläufe, Ergebnisse und Artefakte;
- Datenqualitätsberichte;
- Konfigurationsversionen und Diffs;
- kontrollierte Aktionen wie Audit, Not-Aus und Moduswechsel.

Schreibaktionen benötigen Authentisierung, Berechtigung, CSRF-/Origin-Schutz bei Browserbetrieb und Audit.

## Kapazitätsannahme

Zehn Paare über drei Jahre sind für eine lokale relationale Datenbank überschaubar. Kapazität wird dennoch anhand Timeframe, Indikator-Snapshots, Logs und Backtestversionen gemessen. Retention darf keine für Reproduzierbarkeit benötigten Daten löschen.
