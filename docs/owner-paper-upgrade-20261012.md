# Lokale Aktivierung vom 12.10.2026

Der Eigentümer hat die Installation des letzten Forschungs-Patches und einen Neustart ausdrücklich angefordert. V8r (`HIXTON-V8-LINK8-ATR075-PAPER-1`) macht die untersuchte Kombination LINK VIDYA 8 / ATR-Ziel 0,0075 für Paper und Portfolio-Backtests auswählbar. Die bisherige V8-Definition bleibt unverändert. V8r ist eine manuell ausgewählte Paper-Variante, keine bestandene technische oder wirtschaftliche Live-Abnahme. Die Forschungs-Kriterien wurden nicht nachträglich geändert.

## Offener 50-USDC-Test

Bei einem bereits gekauften Test wird seine gespeicherte Strategie aus dem bekannten Definitionskatalog wiederhergestellt. Die Datenbasis enthält dieselben geprüften abgeschlossenen Kerzen wie der Hauptbot. Geänderte Profile (hier LINK) werden für den eingefrorenen Test mit den Originalparametern nachgerechnet. Identische Profile erhalten die ursprüngliche Versionskennung. Dieser Cache hat keine eigene Orderfreigabe und eröffnet keinen weiteren Test. Unbekannte eingefrorene Strategien benötigen weiterhin manuellen Abgleich. Eine noch nicht übermittelte alte Kaufberechtigung wird nicht als Besitz behandelt.

Die ursprüngliche Test-ID, Binance-Kauforder, Menge, Kontobaseline, Quellversion und Strategie werden nicht umgeschrieben. Der bestehende Test wird ausschließlich für seinen regulären Ausstieg und anschließenden Abgleich weitergeführt. Ein geänderter Python-Quellstand und eine andere Hauptstrategie bleiben im Ausführungsbericht sichtbar. Der alte Test kann die neue Version nicht für Dauer-Live freigeben. Die gesonderte Freigabe prüft nun explizit Quelle, Strategie, Anwendung und Allokator; die UI verwendet dieselbe Prüfung.

## Paper-Wechsel und Sicherung

Die vorhandene Funktion `activate_paper_strategy` protokolliert den Wechsel. Sie beendet alte simulierte Positionen zu modellierten Preisen, erhält die Historie und das Kontorisiko, setzt Checkpoints auf den letzten vollständig geprüften Kerzenschluss und beginnt eine neue Strategiereferenz mit dem verbleibenden simulierten Vermögen. Sie berührt weder Binance noch die Testdatenbank. Dies ist ein ausdrücklich dokumentierter Wechsel der Simulation, kein echtes Verkaufssignal.

Vor dem lokalen Austausch werden konsistente SQLite-Sicherungen, Quellcode und Konfiguration gespeichert. Der Bot wird geordnet beendet, der finale Testzustand nochmals gesichert, dann wird die neue Konfiguration aktiviert und derselbe Launcher neu gestartet. API-Schlüssel bleiben im bestehenden Windows-Anmeldedatenspeicher; der Installations- und Datenbankpfad bleiben erhalten.

## Offline-Prüfungen

Die Upgrade-Tests prüfen exakte Originalindikatoren nach dem Profilwechsel, Wiederaufnahme eines gekauften Tests, genau einen BUY und SELL im simulierten Journal, unveränderte ursprüngliche Identität und die Ablehnung alter Freigaben. Es werden keine echten/testnet Orders in diesen Prüfungen gesendet.

### Geprüfter Stand

- Python: 566 bestanden, 2 optionale Tests übersprungen.
- UI: TypeScript-Prüfung, 34 Tests und Produktionsbuild bestanden.
- Ruff: src/scripts/tests bestanden. MyPy: 67 Quellmodule bestanden.
- Probelauf auf einer Kopie des lokalen Zustands: alte Test-ID, Kauforder und 8,4 NEAR erhalten; keine Börsenanfragen; alte Ausstiegsregeln wiederhergestellt.

Dies sind lokale Regressionsergebnisse, keine behaupteten A09-/A11-Abnahmen und keine bestätigte Live-Ausführung der neuen Strategie.
