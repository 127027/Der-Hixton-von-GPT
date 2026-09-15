# V7 – USDC-Migrationsprüfung

Status: **Validierung, nicht aktiviert; keine Echtgeldfreigabe.** Die zehn V6-Coin-Profile werden ohne Optimierung auf echten USDC-Kerzen geprüft. V6-Paper bleibt USDT; historische Zahlen und Konten werden nicht umbenannt. V7 gehört zunächst nicht in die normale aktive UI-Strategieauswahl.

## Festgelegtes Verfahren

- Binance Spot, zehn Coins, 1h, ausschließlich geschlossene Bars, 400 Warm-up-Bars, Signal am Schluss/Fill am nächsten Open.
- Eigene öffentliche USDC-Datenbank `data/usdc-validation.sqlite3`. Keine Schlüssel nötig, keine USDT-Kerzen als Ersatz, keine künstliche Lückenfüllung.
- Angefordert drei Jahre. Tatsächlich gemeinsamer zusammenhängender Zeitraum nach Warm-up aller zehn Coins; spätere Listings/Unterbrechungen werden ausgewiesen. Zusätzlich feste Fenster letzte 365 und 90 Tage, wenn verfügbar.
- Je Fenster zehn Einzeltests à 250 und gemeinsames 250-Portfolio mit 3×80, Baseline und Stress. Aktuelle Börsenfilter statt historisch rekonstruierter Filter; angenommene Kosten statt verifizierter Betreibergebühren.
- USDT-Kontrolle im exakt selben Zeitfenster mit gleicher Strategie und Kosten/Risikoregeln. Bestehende Kerzen ausschließlich lesend, keine Änderung des Paperkontos.
- Die auf USDT erforschten Parameter machen zeitgleiche USDC-Daten nicht zu einem unabhängigen Out-of-sample-Nachweis. Keine Rückoptimierung auf diese Ergebnisse.
- Kanonische unveränderliche Einzel-/Portfolio-Berichte unter `runs/<id>/<fenster>/...`; Kontrolle unter `usdt_same_window_control/`. Manifest nennt Quote, Strategie, Quell-Commit und Kerzenhashes. Gesamtbericht enthält zusätzliche Quellcode-Dateihashes, Datenabdeckung, offene Positionen und realisiertes Ergebnis abgeschlossener Trades.

Aufruf über bestehenden Einstieg: `python src/main.py backtest usdc-review --end 2026-09-08T06:00:00Z --usdt-control-db "PFAD ZUR USDT-DATENBANK"`.

## Ergebnis vom 08.09.2026

Kanonischer Lauf `385bc1f7-4dca-4dcd-a138-3c33bd9c7da8`, Code `81a8fb84cada14ea4172c908972df8997ea97711`. [Kuratierter maschinenlesbarer Nachweis](validation-20260908.json), SHA-256 `3c43934daf70654db667e74031f210683dc42849dfe687ef4a24ce4cc2cfc7de`. Vollständiger lokaler Run enthält zwölf Manifest-/Trade-/Equity-/HTML-Bündel: je drei Fenster × zwei Betriebsmodelle × zwei Quotewährungen, jeweils Baseline/Stress gemeinsam im Bündel. Vorläufiger Lauf `8453e5ee-be89-4346-b3c5-77de6412fbb3` ohne Commitnachweis bleibt lokale Historie, nicht Referenz.

Angefordert 08.09.2023 06:00 bis 08.09.2026 06:00 UTC. Gemeinsamer USDC-Zeitraum tatsächlich **24.03.2024 00:00 bis 08.09.2026 06:00 UTC**, also keine vollen drei Jahre. BTC/ETH/BNB haben im angeforderten Ausschnitt ausreichende Historie. SOL/XRP/ADA/AVAX/DOT beginnen darin erst am 28.12.2023 08:00 UTC, LINK am 24.01.2024 08:00, DOGE am 07.03.2024 08:00. DOGE bestimmt mit 400 Warm-up-Bars den gemeinsamen Start. Innerhalb der geladenen Ausschnitte keine weiteren Lücken. Ein früheres ursprüngliches Listing beweist keine durchgehend verfügbare Historie.

### Gemeinsames Portfolio – immer 250 Startcash, 3×80

| Fenster | USDC Baseline Ende | USDC Stress Ende | USDT Baseline Ende, gleiches Fenster | USDT Stress Ende |
| --- | ---: | ---: | ---: | ---: |
| Verfügbarer gemeinsamer Zeitraum | 203,83 | 203,44 | 201,24 | 198,15 |
| Letzte 365 Tage | 211,01 | 204,99 | 232,62 | 227,20 |
| Letzte 90 Tage | 263,83 | 257,19 | 259,24 | 248,94 |

Baseline je Seite 10 bps Gebühr + 2 Spread + 3 Slippage; Stress 10 + 10 + 20. Keine angewandte/verifizierte BNB-Ermäßigung. Die Quote steht jeweils in der Spalte; kein behaupteter 1:1-Umtausch.

USDC-Gesamtfenster: **−18,47 %**, 14 abgeschlossene Trades (2 Gewinner / 12 Verlierer), maximaler Drawdown **20,83 %**, Entry-Risikohalt am **01.05.2024 19:59:59.999 UTC**. USDT-Kontrolle erreicht ebenfalls früh den Halt. Im 365-Tage-Fenster beträgt der USDC-Drawdown **27,49 %**, trotz 20-%-Entry-Halt: dieser ist keine garantierte Verlustbegrenzung und schließt Positionen nicht zwangsweise.

90 Tage USDC: 14 abgeschlossene Trades (4 Gewinner / 10 Verlierer), deren realisiertes Ergebnis zusammen **−23,51 USDC**. Am Ende sind BTC/BNB/ADA noch offen; Cash **12,88**, Positions-/Restmengenwert **250,96**, Equity **263,83 USDC**. Das positive Endkapital enthält somit offene Bewertungen und ist kein vollständig realisierter Gewinn. Im langen angehaltenen Lauf sind keine regulären Positionen mehr offen, aber bewertete Restmengen von **3,40 USDC** verbleiben neben **200,43 Cash**. Dust ist weder frei verfügbares Cash noch eine laufende Strategieposition.

### Zehn Einzeltests – je Coin 250 Startkapital

Endkapital in USDC; isolierte Strategieprüfung, nicht das spätere gemeinsame Risikomodell.

| Coin | Gesamtfenster Baseline | Gesamtfenster Stress | Letzte 365 Tage Baseline | Letzte 90 Tage Baseline |
| --- | ---: | ---: | ---: | ---: |
| BTC | 352,92 | 303,98 | 244,71 | 302,29 |
| ETH | 573,66 | 527,69 | 287,96 | 327,46 |
| BNB | 274,74 | 228,09 | 252,58 | 285,63 |
| SOL | 594,14 | 530,76 | 225,34 | 325,78 |
| XRP | 564,63 | 385,90 | 288,93 | 342,03 |
| ADA | 351,06 | 269,22 | 121,71 | 263,98 |
| LINK | 410,42 | 312,63 | 210,91 | 353,03 |
| AVAX | 196,96 | 160,22 | 196,13 | 234,60 |
| DOT | 175,47 | 129,00 | 122,54 | 226,65 |
| DOGE | 647,84 | 598,69 | 205,35 | 241,68 |

**Urteil: keine Robustheits-/Livefreigabe.** AVAX und DOT verlieren in allen drei gezeigten Fenstern. BNB kippt im langen Kostenstress ins Minus; ADA/DOT verlieren im letzten Jahr ungefähr die Hälfte des Einzelkapitals. Acht profitable Einzelkurven machen das gemeinsame Portfolio nicht automatisch profitabel. Der zeitraumgleiche USDT-Kontrolllauf widerlegt eine Erklärung allein durch USDC: Startzustand, Marktphase, Konkurrenz um Slots und früher dauerhafter Risikohalt sind wesentlich. Der alte ungefähr 739-USDT-Lauf ist weder ein USDC-Ergebnis noch ein Nachweis für beliebige Startzeitpunkte.

Zur Abgrenzung: Der alte USDT-739,52-Lauf wurde mit identischen Start-/Endzeiten exakt reproduziert. Der aktuelle volle Drei-Jahres-USDT-Lauf endet bei 742,60. Die produktive Paper-Engine erzeugt über dieselben Kerzen 384 identische Fills und exakt dasselbe Endkapital. Ab dem tatsächlichen Paper-Neustart am 06.09.2026 entstehen hingegen keine neuen Signale und keine Fills. Details und Run-IDs in [DMS 18](../../DMS/18_BACKTEST_STATUS_UND_ERGEBNISFORMAT.md). Der negative kürzere Vergleich ist keine Behauptung, der aktive Paperbot benutze eine andere Strategie.

Nächste Strategiearbeit muss diese Start-/Marktphasenabhängigkeit mit vorab festgelegten mehreren Startfenstern, Kosten und Parameter-Nachbarn prüfen. Nicht den Startpunkt nach Profit auswählen, schlechte Coins still entfernen oder Risikohalts löschen. Eine Verbesserung bleibt Kandidat, bis sie risikogleich im gemeinsamen Portfolio und außerhalb ihres Auswahlfensters standhält. Der aktuelle negative Befund wird nicht durch nachträgliches Tuning überschrieben.

## Noch offen

Währungseindeutige Migration von Runtime, Ledger, UI und Binance-Kontoprüfung; sichere Trennung alter USDT-Historie. Produktiver Orderadapter samt Teilfills/Timeouts/Dust/Restart-Reconciliation und genau einem 50-USDC-Entry. Kontospezifische Handelbarkeit, tatsächliche Gebühren und vollständiger Ein-/Ausstiegsnachweis. Kein automatischer Wechsel auf 3×80 Live.
