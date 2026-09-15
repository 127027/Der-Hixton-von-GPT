# 14 – Build-Plan und Definition of Done

DMS 1.7 / Anwendung 0.3.1: DEC-045 ergänzt ausdrücklich autorisierte V6-Paperaktivierung und gesicherten Offline-Neuanfang; kein neuer Indikator, kein neuer Optimierungslauf. Die Aussage „alle zehn robust / optimal / live-reif“ bleibt NICHT ERFÜLLT. Aktueller Betriebsnachweis: DMS 18.

Ergänzung DMS 1.6 / Anwendung 0.3.0: Coin-Profilweitergabe durch alle bestehenden Engines, restartfeste Zusatzregeln, sichtbare Profilwerte und 250-USDT-Startmodell sind implementiert. V6 ist im Einzeltest technisch konsistent, aber in jüngstem/älterem gemeinsamen Portfolio schlechter als V2. Deshalb ist die Produktaussage „alle zehn robust / optimal / live-reif“ weiterhin **NICHT ERFÜLLT**. Aktueller Aktivierungs- und Laptopnachweis steht in DMS 18; die Tabelle vom 02.09. bleibt historische Abnahme.

Dieses Dokument beschreibt Reihenfolge und tatsächlichen Nachweisstand. Der Eigentümer hat nach dem DMS-Freeze die Implementierung ausdrücklich beauftragt.

## Implementierungsstand am 02.09.2026

| Phase | Technischer Stand | Freigabestatus |
|---|---|---|
| 0 – Spezifikation | DMS V1/`HIXTON-SPEC-1.0` eingefroren | **BESTANDEN** |
| 1 – Strategie-Domain | eine Engine, V1- und Eigentümer-Pine-v6-Golden-/Replay-/Zustandstests | **BESTANDEN**; V2 ist aktives Paper, V1 bleibt Historie |
| 2 – Datenplattform | Binance REST/WebSocket, SQLite-WAL, Revisionen, 00:05-UTC-Scheduler, 10×3 Jahre + Warm-up geprüft | **TECHNISCH BESTANDEN**; echter nächster Mitternachtslauf bleibt Betriebsnachweis |
| 3 – Backtest | 10×250, Einzeltest und gemeinsames 3×80-Portfolio einschließlich Paper-Risikogates, Baseline/Stress, immutable lokale Runs, Reproduktionsvergleich | **BESTANDEN**; V2 als bisher bestbelegter Paperstand gewählt, V3-Mehrfachslot verworfen |
| 4 – UI-Lesemodus | zehn Märkte, fünf Zeiträume, Overlays, Signal-/Fillmarker, Tabellen, Qualität, Logs und sichtbarer Risikohalt | **BESTANDEN** in lokaler Browser-Abnahme mit 50/50 Chartkombinationen |
| 5 – Paper Execution | persistenter versionierter 240-USDT-/3×80-Ledger, atomarer Strategiewechsel, Slotpriorität, Kosten, Guards, Restart-Recovery und Soak-Zähler | **IMPLEMENTIERT**, V2-Soak/Gate C noch nicht bestanden |
| 6 – Live-Adapter | kein privater Orderversand; UI und CLI zeigen `LIVE_DISABLED` | **ABSICHTLICH GESPERRT** |
| 7 – Live-Freigabe | nicht begonnen | **NICHT FREIGEGEBEN** |

## Phase 0 – Spezifikation schließen

- `HIXTON-SPEC-1.0` mit Formeln, Parametern, `1h`-Timeframe, Warm-up und Zustandslogik festlegen;
- Börse, eigener Bot-Account/Subaccount, zehn Paare und Kapitalmodell festlegen;
- Trading-/Ordermodus, Kosten, Risikogrenzen und Betriebsregeln festlegen;
- alle P0-/P1-Entscheidungen schließen und Traceability synchronisieren;
- DMS V1 einfrieren, changeloggen und taggen.

Ergebnis: **mit DMS V1 erreicht**; Implementierung kann ohne Strategieerfindung beginnen, sobald der Eigentümer die nächste Phase beauftragt.

## Phase 1 – Reproduzierbare Strategie-Domain

- Candle-/Decimal-/Zeitmodell;
- VIDYA, ATR, Bänder, Trendzustand;
- Golden-Spezifikationsparität für V1 und Eigentümer-Pine-Parität für V2;
- Signal-IDs, Parameterhashes und Unit-Tests;
- Pine-v6-Semantik mit eigener Versionskennung; V1-/V2-Signale dürfen nicht kollidieren.

Definition of Done: Null Signalabweichungen in Golden-Daten, Batch = Replay, keine externe API nötig.

## Phase 2 – Datenplattform

- Provideradapter und Börsenmetadaten;
- historische Downloads für zehn Paare;
- Datenbank, Revisionen und Qualitätsprüfungen;
- Startup-Sync, Stream, Reconnect, täglicher Audit;
- Datenqualitäts-UI/API.

Definition of Done: drei Jahre plus Warm-up pro Paar, Lücken/Fehler nachweislich erkannt, reproduzierbarer Snapshot.

## Phase 3 – Backtest und Reporting

- Eventengine und Next-bar-Fills;
- Gebühren, Slippage, Rundung;
- isolierte 250-USDT-Ledger;
- Standard-Batch 10×250 USDT und frei wählbarer Einzeltest;
- 240-USDT-Spiegellauf mit drei 80-USDT-Slots;
- Metriken/Benchmarks;
- Manifest und Reports;
- Sensitivität und Holdoutprozess.

Definition of Done: alle zehn Einzeltests und Aggregation exakt reproduzierbar; keine erfundenen Ergebnisse.

V2-Zusatzstand: Parametersuche, Mehrfenstervergleich und Sensitivität sind unter `backtests/v2` dokumentiert. Nach ausdrücklicher Eigentümerentscheidung wurde V2 kontrolliert als Paperstandard übernommen. Dies ist ein Forward-/Soak-Test unter echten Marktdaten, keine Live-Freigabe.

Der geordnete V3-Versuch einer Mehrfachbelegung desselben Coins ist unter `backtests/v3` dokumentiert und wegen sofortigem Konzentrations-/Risikohalt verworfen. Ein weiterer Challenger erhält die nächste freie Version und muss kurze Fehlausbrüche untersuchen, lange Gewinntrends erhalten sowie Kosten-, Altfenster-, Nachbar- und Risikogate-Prüfungen bestehen. V2 wird nicht überschrieben; eine Parameter- oder Risikolockerung allein zur Zielrendite ist ausgeschlossen.

## Phase 4 – UI-Lesemodus

- Dashboard mit zehn Karten;
- Chart mit Heute/1W/1M/1J/3J;
- Indikator, Signale, Datenstatus;
- Backtestberichte und Logs;
- klare Empty/Error/Stale-Zustände.

Definition of Done: UI-Abnahmetests bestanden, keine Trading-Schreibfunktion.

## Phase 5 – Paper Execution

- Intent-/Order-/Fill-Zustände;
- Paperadapter und realistisches Fillmodell;
- Positionen/Ledger;
- Not-Aus, Audit, Reconciliation-Simulation;
- Failure-Injection und Soak-Test;
- 24/7-Servicebetrieb mit Binance-Stream, Startup-Recovery und 240-USDT-/3×80-Slotmodell.
- persistente Zählung der Kalendertage, verarbeiteten Bars je Symbol und abgeschlossenen Trades mit sichtbarem Gate-Status.

Definition of Done: keine Doppelorders in Restart-/Timeouttests; längerer Paperbetrieb ohne kritische Abweichung.

## Phase 6 – Live-Adapter, weiterhin gesperrt

- geringberechtigter Börsenkey;
- Live-Metadaten, Ordermapping und Reconciliation;
- Teilfills, Rate-Limits und Unknown-State;
- Security-, Backup- und Restore-Test;
- Betriebsrunbook und Benachrichtigungen.

Definition of Done: Gate D technisch prüfbar, `live_enabled=false` bleibt Default.

## Phase 7 – kontrollierte Live-Freigabe

- explizite schriftliche Entscheidung;
- kleinster freigegebener Umfang;
- enges Monitoring;
- täglicher Abgleich;
- Review nach festgelegter Beobachtungsphase.

Live-Freigabe ist ein eigener Eigentümerentscheid, nicht automatische Folge eines positiven Backtests.

## Definition of Done für das Gesamtprodukt

- alle P0/P1-Anforderungen implementiert und getestet;
- keine kritischen offenen Entscheidungen;
- Strategieparität belegt;
- Daten für zehn Paare vollständig und aktuell;
- Backtests reproduzierbar;
- UI vollständig gemäß Dokument 08;
- Paper-Soak bestanden;
- Sicherheit, Audit, Not-Aus, Reconciliation, Backup/Restore bestanden;
- Benutzer-/Betriebsdokumentation aktuell;
- bekannte Restrisiken dokumentiert;
- Live bleibt deaktiviert, bis separate Freigabe erfolgt.
