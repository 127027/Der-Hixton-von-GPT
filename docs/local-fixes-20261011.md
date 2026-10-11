# Lokale Hixton-Reparaturen vom 11.10.2026

Diese Version enthält die reparierte Startprüfung, vollständige Datenmodule, den gemeinsamen Portfolio-Backtest mit frischem Binance-USDC-Startkapital und die echte Guthabenanzeige in der Übersicht. Beim Automatik-Portfolio-Test ist ein gespeicherter lokaler API-Schlüssel nötig; eine fehlgeschlagene Kontoabfrage verwendet kein Ersatzbudget. Der historische Lauf simuliert anschließend sein eigenes Konto einschließlich Wiederanlage.

Die Übersicht fragt nur Spot-USDC lesend ab: gesamtes USDC-Guthaben und davon frei verfügbar, mit Zeitstempel und automatischer Aktualisierung alle 30 Sekunden. Abfragefehler oder fehlende Schlüssel zeigen keinen simulierten Ersatzbetrag. Paper-Werte bleiben separat gekennzeichnet. Bestehende Coins und USDT werden nicht übernommen oder verkauft.

Die Checkbox-Darstellung und Beschreibungen wurden korrigiert. Der Kapitalplan behält zwei Slots. Python-Änderungen erfordern einen regulären Neustart im selben Botordner. Dort vorhandene Windows-Schlüssel und Datenbanken bleiben erhalten. Ein neuer Ordner ist ein eigener lokaler Daten-/Schlüsselbereich.

Validierung: gezielte Konto-, Backtest- und API-Tests; TypeScript-Prüfung, 30 UI-Tests, Produktionsbuild und Offline-Browserprüfung. Ein lokaler historischer Portfolio-Lauf wurde ausgeführt; private Kontosnapshots und Berichte sind nicht Bestandteil dieses Uploads. Die historische Simulation verwendet für fehlende ältere USDC-Historie USDT-Preiskerzen und belegt keine damalige USDC-Liquidität.

Echtes autonomes Live bleibt gesperrt. Keine Behauptung einer vollständigen Gleichheit von Simulation und echten Binance-Fills, keine zukünftige Gewinnzusage und keine QA-/Governance-Freigabe allein durch diesen Upload. Alte Quellversionsnachweise werden nicht auf diese Version umetikettiert.
