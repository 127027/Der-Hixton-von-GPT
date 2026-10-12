# Zuverlässigkeitskorrekturen vom 12.10.2026

Die Strategieparameter von V8r und die eingefrorene V8 des offenen Echtgeldtests bleiben unverändert. Der Patch ändert Betriebszuverlässigkeit und den ausdrücklich angeforderten Testablauf nach einem Versionswechsel.

## Prozessgebundener Schutz vor automatischem Leerlauf

Die sichtbare Bot-Sitzung registriert Windows PowerRequestSystemRequired und PowerRequestExecutionRequired mit einem deutschsprachigen Grund. Die Requests werden beim Beenden freigegeben; ein Prozessabbruch gibt die Windows-Handles ebenfalls frei. Der Energieplan wird nicht geändert und der Bildschirm wird nicht dauerhaft eingeschaltet. Die Konsole meldet einen fehlenden Schutz ausdrücklich, `/api/session/info` enthält den aktuellen Anforderungsstatus.

Der Schutz ist keine Zusage gegen manuell angeforderten Standby, Zuklappen oder Windows-Grenzen im Akkubetrieb. Microsoft dokumentiert auf Modern-Standby-Systemen mit Akku eine Begrenzung von System-/Execution-Requests nach Ablauf des Sleep-Timeouts. Für unbeaufsichtigten Betrieb ist weiterhin eine passende Stromversorgung und Energiepolitik erforderlich.

Quelle: https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-powersetrequest

## Dauerhaftes Abschaltprotokoll

`data/runtime-lifecycle.jsonl` hält Start, angeforderten Stopp und normales Prozessende fest, mit UTC-Zeit, PID, Instanz und Grund. Es enthält weder API-Schlüssel noch den lokalen Launcher-Token. Bei mehr als 256 KiB wird eine vorherige Datei erhalten. Ein Schreibfehler darf das Stoppen nicht verhindern; weitere Handelszyklen werden bereits vor dem Schreiben gesperrt. Ein fehlendes normales Prozessende ist ein Hinweis auf eine Unterbrechung, kein erfundener Beendigungsgrund.

## Neuer Test nach einer veralteten Abnahme

Ein abgeschlossener alter Test konnte bislang keine aktuelle Live-Freigabe erteilen, blockierte aber auch jeden neuen Test. Jetzt kann der Eigentümer nach vollständig abgeglichenem Abschluss einer veralteten Version erneut ausdrücklich den 1×50-USDC-Button betätigen. Vorher prüft der Bot das Konto neu. Offene Orders, ungeklärte Live-Intents oder offene Live-Positionen verhindern diesen Weg.

Die Archivierung verlangt COMPLETED, bestätigte BUY-/SELL-Fills, vollständige Kontobaseline und Restmenge null. Sie bewahrt Test, ursprüngliche Quell-/Strategieidentität, Orders, Fills, Baseline und Bericht atomar in `trial_archives`. Der alte Bericht wird zusätzlich unter `data/trial-reports/<trial_id>.json` gespeichert. Ein offener oder ungeklärter Test kann nicht archiviert werden. Die neue Baseline und Test-ID werden erst nach der ausdrücklichen Aktion erstellt; es wird kein Kauf beim Klick erzwungen. Der Bot wartet wieder auf ein frisches gültiges Signal. Die alte Historie wird nicht zu einer Abnahme der neuen Version umgedeutet.

## Validierung

Offline-Tests prüfen Archivierung, die vollständige Erhaltung des alten Berichts, atomaren Abbruch bei fehlenden Fills, gesperrte offene Tests, genau einen bestehenden Kauf/Verkauf und keine neue Order beim Vorbereiten des nächsten Tests. Die Windows-Anforderung wurde kurz in einem separaten Prüfprozess mit der echten Windows-API aktiviert und freigegeben. Echte/testnet Orders werden in diesen Prüfungen nicht gesendet.

Geprüft: 575 Python-Tests bestanden, 2 optionale Tests übersprungen; 34 UI-Tests, TypeScript-Prüfung und UI-Build bestanden; Ruff und MyPy (69 Quellmodule) bestanden. Diese Ergebnisse sind keine behauptete A09-/A11-Live-Abnahme.
