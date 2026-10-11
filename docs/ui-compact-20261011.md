# Kompakte Oberfläche – 11.10.2026
Alle acht Ansichten überarbeitet: Übersicht, Chart & Signale, Positionen & Orders, Backtests, Datenqualität, System & Logs, Einstellungen und Dokumentation.

Kompaktere Typografie, Abstände, Kennzahlen und Chart-Höhe. In der Übersicht bleiben echtes USDC-Guthaben und der tatsächliche Einmalteststatus sichtbar. Das separat bezeichnete Paper-Konto ist aufklappbar. Lange Betriebs-, Konto- und Marktparameter stehen in Details. Markt-Karten kennzeichnen offene Positionen explizit als Paper. Aufgeklappte Marktparameter bleiben bei Hintergrundaktualisierungen geöffnet; ihr Klick öffnet nicht versehentlich den Chart.

Der Header übernimmt den tatsächlichen Echtgeldzustand statt eines fest codierten LIVE_DISABLED. Bei Guthabenfehlern oder Verbindungsausfall bleibt die fehlende Bestätigung sichtbar. Unbelegte alte statische Systembehauptungen wurden entfernt. Die Logliste bleibt vollständig zugänglich, scrollt jedoch innerhalb eines begrenzten Bereichs.

Budgetmodi, API-Schlüsselverwaltung und Echtgeldfreigaben bleiben erhalten. Lange Regeln und technische Berichte sind einklappbar. Bei fehlenden Zugangsschlüsseln öffnet sich das Eingabeformular; gespeicherte Schlüssel erfordern keine erneute Eingabe. Dokumentlinks verweisen auf den aktuellen Projektbranch und wurden gegen vorhandene Dateien geprüft.

Validierung: 33 UI-Tests bestanden, TypeScript und Produktionsbuild erfolgreich. Alle acht Seiten offline bei 1440 und 390 Pixeln mit fiktiven Kontodaten geprüft: keine JavaScript-Fehler, doppelten IDs oder überlaufenden Seiten. Desktop-Vorschaubilder visuell geprüft; Aufklappen und Navigation geprüft.

Nur Oberfläche geändert. Keine Änderung des Python-Quellfingerabdrucks, der Strategie, Schlüssel, Kontodaten oder Freigaben. Kein Neustart, keine Order und kein neuer Echtgeldtest. Die Browserseite lädt die Änderung durch Strg+F5.
