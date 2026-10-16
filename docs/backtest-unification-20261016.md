# Aktuelle Regeln in allen Produkt-Backtests

Portfolio, Coin-Diagnose, Paper, Einmaltest und normales Live verwenden dieselbe
aktive Strategie und deren gemeinsame Policy-/Allocator-/Risiko-Komponenten.
Die Coin-Diagnose verwendet jetzt ebenfalls die gemeinsame Backtest-Handelsengine,
anstatt die ältere nicht reinvestierende Einzelcoin-Engine aufzurufen. Die alte
Engine bleibt als eingefrorener Regression-/Forschungsanker erhalten.

- Gemeinsames Portfolio: ein Konto, aktuelle gespeicherte Handelsregeln,
  Reinvestition gemäß Einstellung, gemeinsame Kapital- und Slotkonkurrenz.
  Im Automatikmodus wird genau ein frischer Snapshot des tatsächlich freien
  Binance-Spot-USDC als Startkapital verwendet. Historische Gewinne und Verluste
  verändern danach ausschließlich das simulierte Konto.
- Ohne gespeicherten API-Schlüssel: für den automatischen Portfolio-Backtest
  ausdrücklich 1.000 simulierte USDC, als `SIMULATED_NO_API_KEY` gekennzeichnet.
  Fehler vorhandener Schlüssel oder der Kontoabfrage bleiben Fehler; kein Fallback.
- Einzel-/15er-Diagnose: je Coin ein eigenes Konto mit 250 USDC, unabhängig vom
  eingestellten Livebudget und ohne private Kontoabfrage. Alle 15 unveränderten
  Markthistorien steuern weiter Indikatoren, Core-Vorrang und Filter. Nach diesen
  Filtern darf die Kapitalverteilung ausschließlich den jeweiligen Coin kaufen.
  ATR-Größen, Tagespause, Reinvestition und Diversifikationsregeln bleiben aktiv.
  SUI/UNI erhalten als Research-only-Coins keinen künstlichen Handelszugang.

Eine Coin-Diagnose entfernt konkurrierende Käufe, nicht die Marktdaten. Ihre
Trades können daher von denen des gemeinsamen Portfolios abweichen. Die Summe
der 15 Konten ist keine Simulation eines gemeinsamen 3.750-USDC-Kontos.

Alle neuen Berichte binden Quellfingerprint, aktive Strategie, Einstellungen,
Startkapital und Zeitraum. Coin-Berichte speichern zusätzlich Hashes des gesamten
15-Markt-Kontexts. Alte Einzeltests ohne Nachweis der gemeinsamen Engine werden
nicht mehr als passend bezeichnet. Historische Berichte werden nicht überschrieben.
Die Oberfläche zeigt einen simulierten 1.000-USDC-Start ausdrücklich als Simulation.

Der Backtest nutzt abgeschlossene Stundenkerzen kausal und modellierte Folgekurse,
Kosten und Börsenfilter. Er bestätigt keine tatsächlichen Binance-Ausführungen.
Der echte 50-USDC-Roundtrip mit Kontoabgleich bleibt dafür erforderlich. Identische
Regeln garantieren keine identischen Fillpreise, Latenzen oder zukünftigen Gewinne.

Die Binance-Assetprüfung akzeptiert jetzt auch unveränderte alphanumerische
Unicode-Namen (z.B. chinesische Assetnamen). Mengen, doppelte Namen, gesperrte
Guthaben und die vollständige unveränderliche Kontobaseline bleiben strikt geprüft;
es findet keine Normalisierung oder Zusammenfassung verschiedener Namen statt.
