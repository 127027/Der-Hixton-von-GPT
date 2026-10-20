# Wiederanlauf und ausdrücklicher 50-USDC-Wiederholungstest

Die abgeschlossenen Produkt-Handelsregeln und ihre Strategieversion bleiben
unverändert. Diese Korrektur betrifft Datenverfügbarkeit, konkurrierende Leser
und das erneute Starten eines vollständig abgeglichenen Einmaltests.

## Wiederanlauf nach längeren Ausfällen

Die Synchronisation zählt nur endgültige Kerzen als vorhandene abgeschlossene
Historie. Eine alte vorläufige Kerze wird daher auch außerhalb des üblichen
48-Stunden-Aktualisierungsfensters erneut beim Anbieter abgefragt. Die nächste
offene Kerze wird separat frisch bestätigt und bleibt außerhalb der Indikatoren.
Die vollständige Qualitätsprüfung bleibt unverändert streng; fehlende oder
vorläufige Providerdaten werden nicht erfunden und nicht als gültig gespeichert.

Reine Runtime-, Filter-, Settings-, Status-, Chart- und Paper-Lesezugriffe öffnen
die vorhandene Datenbank nur lesend. Dadurch benötigen diese Zugriffe keine
Migration und keine SQLite-Schreibsperre. Initialisierung und tatsächliche
Speicherung bleiben in den vorgesehenen Schreibpfaden. Bei fehlgeschlagenen
Migrationen wird die eigene Verbindung sofort geschlossen. Fehlende oder nicht
initialisierte Daten ergeben keine erfundene Bereitschaft.

## Erneuter Einmaltest

Ein abgeschlossener und abgeglichener Test kann auch bei identischer Quellversion
erneut ausdrücklich über den vorhandenen Testbutton gestartet werden. Die reine
Statusanzeige startet nichts. Dauer-Live muss deaktiviert sein; offene normale
Live-Positionen oder ungeklärte Orders verhindern den Wiederholungstest.

Beim Klick gelten weiterhin frische Binance-Vorprüfung, ein gültiger frischer
Kontosnapshot ohne offene Orders/gesperrte Guthaben und die atomaren Archivprüfungen:
bestätigter BUY und SELL, Fills beider Seiten, Abschlussdatum, Baseline und Rest null.
Der vorherige Bericht einschließlich seiner ursprünglichen Identitäten und Fills
bleibt archiviert. Erst anschließend erhält der neue Test eine eigene UUID und
wartet auf ein neues Signal. Ein erneuter Klick während eines laufenden Tests
erzeugt keinen zweiten Test. Normale Live-Historie und Paper werden nicht gelöscht.

Der neue Python-Fingerprint macht die bisherige Abnahme nicht automatisch zur
Abnahme des korrigierten Codes. Für diese Version ist der neue Roundtrip erforderlich.
Live-An-/Ausschalten bleibt eine separate ausdrückliche Benutzeraktion. Historische
Backtests bleiben erhalten und müssen die bestehende Versionsprüfung bestehen;
ein neuer Lauf verwendet weiterhin dieselben aktuellen Produktregeln.

## Grenzen des Befunds

Beim Aufholen werden historische Paper-Ereignisse simuliert. Reale verspätete
Ausstiege werden zum dann verfügbaren Kurs abgewickelt und als verspätet berichtet.
Internet-/Stromausfälle und eine bei Binance nicht freigegebene Ausgangs-IP lassen
sich durch diesen Datenfix nicht verhindern. Der Bot hält keine börsenseitigen
Schutzorders vor. Ein technischer Regressionstest oder abgeschlossener Einmaltest
garantiert weder unterbrechungsfreien Betrieb noch zukünftigen Gewinn.
