# Binance-Diagnose: Fehler sichtbar erhalten

Die Statusaktualisierung nach einem fehlgeschlagenen Verbindungstest ersetzte
die konkrete Fehlermeldung sofort durch den Hinweis auf einen fehlenden frischen
Diagnose-Check. Die Schaltfläche erreichte den Server, aber die Oberfläche
verdeckte dessen Antwort.

Die Oberfläche erhält jetzt den letzten Diagnosefehler über Statusaktualisierungen
hinweg. Eine erfolgreiche erneute Prüfung oder eine erfolgreich gespeicherte
Schlüsseländerung entfernt ihn. Abgelaufene erfolgreiche Prüfungen werden weiterhin
nicht als frisch bestätigt angezeigt. Fehler werden nur im Arbeitsspeicher der
aktuellen Seite gehalten; kein Browser-Speicher und keine Schlüssel werden ergänzt.

Ein Testverkauf im Journalzustand CREATED wird ausdrücklich als vorbereitet und
noch nicht gesendet angezeigt. Ungeklärte Übermittlungen bleiben ungeklärt. Ein
laufender Test benötigt keine Aktivierung von Dauer-Live für seinen Ausstieg.

Diese Änderung betrifft ausschließlich TypeScript und gebaute statische Dateien.
Python-Quellfingerprint, Handelsregeln, Testidentität, gespeicherte Schlüssel,
Orders und Freigaben ändern sich nicht. Die statischen Dateien können bei laufendem
Bot aktualisiert werden: zuerst das neue Bundle, anschließend die neue HTML-Datei.
Alte Bundles bleiben in der Installation für bereits geladene Seiten erhalten.
Die aktuelle Seite muss danach neu geladen werden; kein Bot-Neustart notwendig.

Validierung: TypeScript-Prüfung, 41 UI-Tests einschließlich Diagnosefehler über
Aktionsabschluss und wiederholte Statusabfragen, erfolgreiche Wiederholung,
Frischeablauf sowie vorbereiteter gegenüber ungeklärtem Verkauf; Vite-Produktbuild.
Ein Darstellungsfix hebt keine Binance-Ablehnung und keine Handelsprüfung auf.
