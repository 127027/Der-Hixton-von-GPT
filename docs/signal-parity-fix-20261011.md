# Signalverarbeitung und Einmaltest – 11.10.2026

Ursache: Der freigegebene Test wartete seit 17:56:37 UTC. Die 17:59:59.999-UTC-Kerzen wurden erst nach 109,9 Sekunden veröffentlicht; das 90-Sekunden-Einstiegsfenster war abgelaufen. Paper buchte LINK am nächsten modellierten Open. Keine reale Testorder wurde erzeugt.

Korrektur: Historischer 48-Stunden-Abgleich und nächste offene Kerze werden gemeinsam abgerufen. Acht öffentliche Marktleser statt vier; kürzere begrenzte Netzversuche, Fehler bleiben geschlossen und werden durch die bestehende Recovery behandelt. Frische REST-Bestätigung der nächsten Öffnung bleibt Pflicht; ein bereits gespeicherter vorläufiger Datensatz reicht nicht. Vollständige Qualitätsprüfung, 15-Markt-Barriere, Quellenbindung, Kontenabgleich und 90-Sekunden-Fenster bleiben bestehen.

Einmaltest: Gleicher gespeicherter Zusatzfilter für Satellites wie in Paper/Portfolio/Live. Core-Vorrang beendet auch eine Satellite-Testposition, ohne einen zweiten echten Trade zu starten. Reguläre und maximale Haltedauer-Ausstiege bleiben bei fehlenden fremden Core-Daten ausführbar. Abgelaufene Einstiegssignale werden als ENTRY_WINDOW_EXPIRED angezeigt; keine verspätete Order wird nachgeholt.

Prüfung: 127 Python-Tests (gemeinsame Signalregeln, Paper-/Portfolio-Parität, normaler Livecontroller mit Fake-Binance, Einmaltest, Risiko und Startbedingungen); anschließend 51 betroffene Tests nach der letzten Korrektur. 34 UI-Tests, TypeScript-Prüfung und Build erfolgreich. Öffentliche Binance-Synchronisation auf temporärer Kursdatenkopie: 15 gültige Märkte in 56,1 Sekunden. Diese Einzelmessung garantiert keine Netzlatenz. Keine privaten API-Orders in Tests. Historische Modellpreise und reale Fills werden nicht als identisch zertifiziert.

Aktivierung: Python-Patch benötigt Neustart. Alte, noch ungehandelte Testfreigabe wird wegen Quellenwechsel ungültig; explizite neue Freigabe im UI erforderlich. Keine automatische Freigabeübertragung, kein Nachholen des LINK-Kaufs. Gespeicherte Schlüssel und Konten bleiben bestehen. Keine Änderung der Strategieparameter oder des Budgets.
