# 10 – Betrieb, Monitoring und Recovery

## Systemzustände

| Zustand | Bedeutung | Tradingverhalten |
|---|---|---|
| `STARTING` | Prüfungen laufen | keine neuen Orders |
| `HEALTHY` | alle kritischen Komponenten grün | gemäß aktivem Modus |
| `DEGRADED` | Teilfunktion gestört, Sichtbarkeit vorhanden | neue Entries standardmäßig pausiert |
| `HALTED` | Sicherheit/Zustand unklar oder Not-Aus | keine neuen Orders |
| `STOPPING` | geordnetes Herunterfahren | keine neuen Orders, Checkpoint |

Einzelne Symbole können separat pausiert sein, während andere gesund bleiben. Ein globaler Datenbank- oder Kontosyncfehler stoppt alle Live-Entries.

## Geplanter Betrieb

### Beim Prozessstart

- Startup-Sequenz aus Dokument 05;
- Scheduler-Jobs registrieren;
- überfällige Jobs erkennen;
- Stream verbinden;
- Bar-Close-Verarbeitung aktivieren;
- Paper-/Live-Reconciliation durchführen;
- Health-Report und Startup-Audit schreiben.

### Laufende Jobs

| Job | Takt |
|---|---|
| Livefeed/Bar-Finalisierung | kontinuierlich / je Bar-Close |
| Freshness-Watchdog | mindestens alle 30 Sekunden |
| Order-Reconciliation | ereignisgetrieben plus periodisch |
| Mitternachts-Datenaudit | täglich 00:05 UTC |
| Backup | täglich nach erfolgreichem Datenaudit |
| ausführlicher Datenintegritätscheck | wöchentlich |
| Backtest-Neulauf | manuell/freigegeben oder nach versionierter Daten-/Strategieänderung |

Das Papersystem ist für 24/7-Betrieb vorgesehen. Schlafmodus, Windows-Updates, Internet-/Stromausfall und Service-Autostart werden deshalb im Soak-Test ausdrücklich geprüft. Nach jedem Ausfall gilt Gap-Fill und Reconciliation vor neuer Signalverarbeitung.

Nach bestandener Paperfreigabe läuft der Bot als Windows-Service mit verzögertem Autostart und Restart-on-Failure. Ein Service-Restart überspringt niemals Startup-Prüfung oder Reconciliation.

Ein Backtest wird nicht ungeprüft jeden Tag automatisch zum Live-Entscheider. Neue Ergebnisse müssen gesichtet und freigegeben werden.

Nach einer bestätigten Websocket-Wiederverbindung wechselt der Feed zurück auf `WEBSOCKET`. Eine vom Streamloop selbst gesetzte Fehlermeldung wird dabei gelöscht und `DEGRADED` zu `HEALTHY` zurückgeführt. Stammt der aktuelle Fehler inzwischen aus Datenprüfung, Audit oder einer anderen Komponente, darf die Wiederverbindung ihn nicht löschen oder den Healthstatus gesund melden.

## Health Checks

Pflichtprüfungen:

- Prozess erreichbar;
- Datenbank les-/schreibbar und Migration aktuell;
- letzte geschlossene Kerze pro Symbol erwartungsgemäß;
- Stream verbunden oder Fallback aktiv;
- REST-/Providerzugriff;
- Scheduler letztes/nächstes Ausführungsdatum;
- keine überfällige Reconciliation;
- keine unbekannten Orders/Positionsdifferenzen;
- ausreichend Speicherplatz;
- Systemzeit innerhalb Toleranz;
- letzter Backupstatus;
- aktive Konfiguration gültig und unverändert.

## Logs und Metriken

Jedes Logevent enthält:

- UTC-Zeit;
- Level;
- Komponente;
- Eventcode;
- Korrelations-ID;
- Symbol/Timeframe, falls relevant;
- Modus;
- redigierte strukturierte Details.

Metriken umfassen mindestens Datenlatenz, letzte Barzeit, Lückenanzahl, Stream-Reconnects, API-Fehler, Rate-Limits, Signal-/Intent-/Orderzahlen, blockierte Intents, Filllatenz, Schedulerdauer und Backupalter.

## Alarmklassen

| Priorität | Beispiel | Erwartete Reaktion |
|---|---|---|
| P1 kritisch | unbekannte Live-Order, Kontodifferenz, Datenbankkorruption | Live halt, sofort sichtbar/alarmieren |
| P2 hoch | mehrere fehlende Bars, Stream dauerhaft aus, Backup fehlgeschlagen | Entries pausieren, zeitnah beheben |
| P3 mittel | einzelnes Symbol stale, Rate-Limit-Spitze | Symbol pausieren/überwachen |
| P4 info | täglicher Audit erfolgreich, Backtest fertig | protokollieren |

Alle Klassen erscheinen in UI und strukturiertem Log. P1/P2 müssen dort dauerhaft auffällig bleiben, bis sie quittiert oder behoben sind; P3 wird mindestens in der UI protokolliert, P4 bleibt UI/Log. Der Eigentümer hat regelmäßige manuelle Überwachung als Betriebsmodell bestätigt. Telegram ist weder Pflichtkanal noch Live-Gate. Ein später optional ergänzter externer Kanal darf die lokale Alarmierung nicht ersetzen und benötigt eine eigene Konfigurationsversion.

## Sicheres Herunterfahren

- neue Intents stoppen;
- laufende Persistenztransaktionen abschließen;
- offene Börsenorders nicht blind stornieren;
- letzten verarbeiteten Bar-/Event-Checkpoint speichern;
- Status der offenen Orders und Positionen sichern;
- Shutdown-Grund protokollieren.

## Backup

Backup umfasst:

- Datenbank;
- freigegebene Konfigurationen ohne Secrets;
- verschlüsselte/extern verwaltete Secret-Referenzen, nicht Klartext;
- Backtestmanifeste und Berichte;
- Strategiequellen/-hashes und DMS-Version;
- Migrationsstand.

Backups erhalten Prüfsumme, Erstellzeit, Version und Retention. Sie werden verschlüsselt außerhalb des öffentlichen Repositories und außerhalb der aktiven Datenbank abgelegt, bevorzugt in einem getrennten OneDrive-synchronisierten Ziel. Secrets werden nur in verschlüsselter Form bzw. als wiederherstellbare Secret-Referenz gesichert.

Verbindliche Retention:

- 7 tägliche Stände;
- 4 wöchentliche Stände;
- 12 monatliche Stände.

Das Zielverzeichnis ist eine deployment-spezifische Pflichtkonfiguration und darf nicht innerhalb des Git-Worktrees liegen. Ein fehlendes oder nicht beschreibbares Backupziel blockiert Live.

## Restore-Test

Mindestens vor Live-Freigabe und danach vierteljährlich:

1. neue isolierte Umgebung bereitstellen;
2. Backupintegrität prüfen;
3. wiederherstellen;
4. Schema/Hashes prüfen;
5. im `LIVE_DISABLED`-Modus starten;
6. Positionen/Orders nicht senden, sondern Reconciliation trocken prüfen;
7. einen bekannten Backtest reproduzieren;
8. Ergebnis und Dauer dokumentieren.

## Verbindlicher Paper-Soak vor Live

Alle Bedingungen müssen erfüllt sein:

- mindestens 30 zusammenhängende Kalendertage im 24/7-Paperbetrieb;
- mindestens 720 verarbeitete geschlossene 1h-Bars je aktivem Symbol;
- mindestens 20 vollständig abgeschlossene Papertrades portfolioübergreifend;
- keine ungeklärte Doppelorder, Kontodifferenz oder kritische Datenlücke;
- Restart-, Internet-/Streamausfall-, sichtbares P1/P2-Alarm- und Restore-Szenario bestanden.

Werden nach 30 Tagen weniger als 20 Trades erreicht, läuft Paper bis zum 20. Trade weiter, jedoch höchstens 90 Tage. Nach 90 Tagen ohne 20 Trades entscheidet der Eigentümer dokumentiert über Verlängerung oder Abbruch; es gibt keine automatische Live-Freigabe.

Der technische Nachweiszähler ist persistent: Der erste Paperstart setzt je Symbol einen Checkpoint, ohne historische Signale nachzuhandeln. Jeder tatsächlich verarbeitete neue Bar-Close erhöht den SQLite-Zähler des Symbols atomar mit Ledger, Events und Checkpoint. Ein späterer Neustart überschreibt diese Checkpoints nicht, sondern verarbeitet zwischenzeitlich geschlossene Bars exakt einmal nach. Die bestehende Systemkarte zeigt Kalendertage, den kleinsten Barzähler aller zehn Märkte, abgeschlossene Trades und `RUNNING`, `REVIEW_REQUIRED` oder `PASSED`. Ein Zählerstand allein ersetzt keinen Test der weiteren Bedingungen dieses Abschnitts.

## Typische Recovery-Szenarien

- Strom-/Prozessausfall während Orderübermittlung;
- Streamausfall über mehrere Bars;
- REST-API vorübergehend nicht erreichbar;
- lokale Datenbank gesperrt oder beschädigt;
- historische Kerzen nachträglich korrigiert;
- Börsenfilter geändert;
- Coin delistet/Trading pausiert;
- Systemuhr falsch;
- manuelle Kontobewegung oder Fremdorder;
- Speicherplatz knapp;
- Konfiguration unvollständig.

Für jedes Szenario gilt: Zustand zuerst eindeutig machen, dann fortsetzen. Ungewissheit wird nicht durch eine neue Order „behoben“.
