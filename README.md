# Der Hixton

**Telegram-Kontakt (Erweiterung 21.10.2026):** Einstellungen enthalten einen
separaten Kontaktbereich für bestätigte Echtgeld-Käufe, Teilverkäufe und
abgeglichene Abschlüsse. Keine Paper- oder Freigabemeldungen; Zugang im
Windows-Schlüsselspeicher, gespeicherte Versandwarteschlange und transparente
Gebühren nach Asset. [Einrichtung, Betrieb und Grenzen](docs/telegram-notifications.md).
Code-Verfügbarkeit aktiviert weder den Versand noch Echtgeld. Bei laufendem
freigegebenem Test wird die Installation wegen der Versionsbindung abgestimmt.

Technischer Stand 16.10.2026: bestätigte Orderkennungen werden vor Folgeabfragen
gespeichert; ungeklärte Testorders erscheinen als Fehler. Eine eng begrenzte,
ausdrücklich autorisierte Orderklärung prüft Börsenhistorie und unveränderliche
Kontobaseline. Die Strategie und normale Live-Freigabe bleiben separat.
[Details und Grenzen](docs/execution-recovery-20261016.md).

**Abschlussstand 14.10.2026:** Die technische Kaufprüfung nach Reservierung ist installiert.
Ein neuer Portfolio-Backtest wurde mit rollierenden drei Kalenderjahren, den gespeicherten
Automatik-Einstellungen und frisch gelesenen freien Binance-USDC geprüft. Er passt zur laufenden Quelle.
Aktuelle kontobezogene Beträge und Laufberichte bleiben lokal und werden nicht im Repository veröffentlicht.
[Technische Korrektur und lokale Abnahme](docs/technical-entry-guard-20261014.md).
Die aktive Stufenregel bleibt zwei Grundtranchen/DD10 und ab 32k höchstens drei verschiedene Coins; keine Vierer-Stufe.

## Aktueller lokaler Produktstand: 14.10.2026

Die aktuelle lokale Strategie ist **HIXTON-V8-LINK8-ATR075-DOGE50-DD10-ETH8-DIV32-PAPER-5**.
Backtest, Paper und der geschützte Live-Controller verwenden diesen gemeinsamen Vertrag.
Bis 32.000 USDC bleibt die ETH8/DD10-Aufteilung erhalten; ab der letzten geschlossenen
Portfolio-Bewertung von 32.000 USDC gilt dauerhaft höchstens eine Position je Coin und
höchstens drei verschiedene Coins. Das Kaufbudget beträgt maximal ein Drittel vor ATR-Anpassung.
Eine bestehende zu große Position wird beim Wechsel einmal teilweise reduziert.

Automatikbudget nutzt das verwaltete USDC-Kapital und reinvestiert dessen Gewinne/Verluste;
fremde Coin-Bestände und USDT werden nicht übernommen. Der vorgemerkte 50-USDC-Test bleibt
ein eigener einmaliger Modus. Normales Echtgeld bleibt separat freizugeben und verlangt
einen passenden vollständig abgeglichenen Test sowie frische Konto-/Versionsprüfungen.
Ein neuer Download enthält keine API-Schlüssel, Kontodaten oder Testfreigabe eines anderen Rechners.

[Ergebnisse, Kostenstress und Grenzen](docs/diversification-20261013.md) ·
[Quellidentität](docs/diversification-20261013/Product-Identity.json) ·
[Lokaler Paper-/Backtest-Abgleich](docs/diversification-20261013/Full-Parity.json)

Der historische Vergleich ergibt 32.727,15 USDC / 30,50 % DD statt 31.825,37 / 38,22 %.
Kostenstress: 22.399,56 USDC / 47,75 %; die Schwelle wird dabei nicht erreicht.
Es gibt keine garantierte zukünftige Rendite oder Drawdown-Grenze. Andere Startbudgets
und Zeiträume können schlechter abschneiden. Die Abnahme ist lokal, keine formale Cloud-Swarm-Zertifizierung.
Die folgenden älteren V6/V8- und Reparaturabschnitte dokumentieren historische Grundlagen;
bei abweichenden Kapital-/Strategieangaben gilt der hier genannte aktuelle V8r-Vertrag.


Der Hixton 0.5.0 ist ein lokaler deutschsprachiger Binance-Spot-Bot für 15 USDC-Märkte. Das aktuelle Produkt ist **V8**: der unveränderte, eingefrorene V6-Zehn-Coin-Core plus ein separater Satellite-Layer. Backtest, Paper und der guarded lokale Live-Pfad verwenden dieselbe StrategyDefinition, dieselbe Kapitalquelle und dieselben point-in-time Routingregeln.

## Lokale Reparatur vom 11.10.2026

Der heruntergeladene Test-ZIP ließ versehentlich `src/hixton/data` aus. Die fehlenden Module sind ergänzt; der Start prüft die vollständigen Imports vor einem Instanzwechsel. Die Paket-Workflows schließen Laufzeitdaten aus, behalten aber Quellmodule.

Der optionale Automatikmodus reinvestiert im **Paper-Modell und gemeinsamen Portfolio-Backtest** die Gewinne/Verluste des einen verwalteten Kontos und verwendet dieselben neuen NEAR/BCH-Filter. Der gemeinsame Backtest speichert diese Auswahl im Manifest; anders konfigurierte oder alte, nicht belegte Berichte gelten nicht als passend. Der isolierte Coin-Test bleibt eine separate Diagnose und kein gemeinsames Portfolio.

**Handelswährung ist USDC.** USDT-Bestände werden nicht als USDC behandelt oder automatisch umgetauscht. Die Demo beginnt mit virtuellem Kapital von 1.100 USDC, ohne Nachweis eines tatsächlichen Binance-Guthabens. Zwei Slots bleiben erhalten; ein einzelner Core-Kandidat kann beide erhalten und damit das ganze verfügbare Kapital einsetzen. Das ist keine automatische Verteilung auf beliebig viele kleinere Positionen.

**Echtgeld-Automatik bleibt gesperrt.** Vor einer Freigabe müssen der 50-USDC-Test und der echte Live-Pfad nachweisbar diesen neuen Modus prüfen. Die bestehenden alten Testpfade und historischen Zahlen zertifizieren ihn nicht. Gleiche Entscheidungsregeln garantieren keine identischen Börsenkurse, Gebühren oder Netzwerklaufzeiten.

## Produktvertrag

- Core: BTC, ETH, BNB, SOL, XRP, ADA, LINK, AVAX, DOT und DOGE gegen USDC.
- NEAR, AAVE und BCH gegen USDC sind gemeinsam aktive Zwischenfüller. SUI und UNI bleiben im isolierten Forschungstest und in den Charts, erhalten aber keinen gemeinsamen Einsatz.
- Zwischenfüller dürfen nur einsteigen, wenn kein Core-Coin aktiv ist. Bei einem zulässigen Core-Einstieg müssen alle Zwischenfüller am nächsten ausführbaren Open aussteigen.
- Zeitrahmen: 1h. Signal-/Filter-/Exitlogik verwendet nur vollständig geschlossene Kerzen; Fills werden am nächsten verfügbaren Open modelliert.
- Backtestfenster: exakt drei Kalenderjahre bis zur letzten vollständig geschlossenen UTC-Stunde plus 400 Warm-up-Bars davor.
- Kanonische Strategiequelle: `src/hixton/domain/versions.py`.
- **V6** bleibt der eingefrorene Zehn-Coin-Regressionsanker; **V8** ist das aktuelle Produkt.
- Kanonische Kapitalquelle: `max_capital_usdc`.
- Allocator: `CAPITAL-V1-2X50PCT` = zwei Tranchen zu je 50 % des konfigurierten Maximalbudgets. 250 → 2×125, 1.000 → 2×500. Diese Zahlen sind Beispiele; die Produktlogik skaliert aus X.
- V8 und V6 nutzen die ursprüngliche Core-Verteilung `ranked_repeat`: Ein einzelner Core-Kandidat kann beide Tranchen erhalten. Zwischenfüller erhalten höchstens eine Tranche je Coin. Kapitalgrenze, zwei Slots und Tagesverlustschutz bleiben erhalten.
- Echtgeld ist beim Start niemals automatisch aktiv. Cloud/CI/Agenten senden weder Real- noch Testnet-Orders.

## Eingefrorener V6-Core

| Coin | VIDYA | Momentum | Smoothing | ATR | Band | Zusatzregel |
|---|---:|---:|---:|---:|---:|---|
| BTCUSDC | 5 | 20 | 8 | 120 | 4,4 | CMO floor 0,2 |
| ETHUSDC | 6 | 20 | 8 | 60 | 3,8 | VIDYA slope 24 |
| BNBUSDC | 10 | 20 | 8 | 120 | 5,0 | – |
| SOLUSDC | 6 | 20 | 15 | 60 | 3,8 | – |
| XRPUSDC | 6 | 20 | 8 | 120 | 3,2 | CMO floor 0,15 + Close-Stop 4 Entry-ATR |
| ADAUSDC | 8 | 20 | 8 | 60 | 4,4 | – |
| LINKUSDC | 6 | 20 | 8 | 60 | 3,8 | VIDYA slope 24 |
| AVAXUSDC | 6 | 20 | 8 | 90 | 5,5 | – |
| DOTUSDC | 6 | 20 | 8 | 120 | 3,8 | CMO floor 0,35 |
| DOGEUSDC | 6 | 16 | 14 | 120 | 4,3 | CMO floor 0,2 |

Alle Profile verwenden 400 Warm-up-Bars. Der V6-Core-Hash bleibt ein harter Regressionstest.

## V8-Satellite-Layer

Alle fünf Profile verwenden dieselben Regeln im Einzeltest und im Shared-/Paper-/Live-Pfad. Die ursprünglichen Haltehorizonte bleiben erhalten: NEAR 48 Stunden, AAVE 120 Stunden, sonst Trend-/Policy-Exit. Alle Zwischenfüller müssen unabhängig davon für Core aussteigen. Neben dem ursprünglichen Trendwechsel dürfen sie bei bestätigtem UP-Trend zu den geschlossenen Stundenkerzen vor 00:00/12:00 UTC erneut einsteigen. Momentum-, Slope-, Stop- und ATR-Regimefilter gelten weiterhin; ein freier Slot und gültige Exchange-/Risiko-Gates sind erforderlich.

| Coin | Shared | Kerneigenschaft |
|---|---|---|
| SUIUSDC | **Research** | ATR-Regimefilter und Close-Stop |
| NEARUSDC | **Aktiv** | 48h Max-Hold |
| UNIUSDC | **Research** | CMO- und VIDYA-Slope-Filter |
| AAVEUSDC | **Aktiv** | ATR-/Trend-Regimefilter und Close-Stop |
| BCHUSDC | **Aktiv** | point-in-time ATR-Regimefilter |

Der Stand mit 205 Trades und 1.606,89 USDC wurde vor der Folgekorrektur lokal gesichert und als Commit e40258260d3a77ab88d3216a6c029adbdb5bacf0 auf gpt/usdc-audit gespeichert. Er bleibt als nachvollziehbarer Vergleich erhalten.

Der identische Core-Allein-Test ergab 84 Trades und 1.582,30 USDC. Die frühere Variante mit 132 Trades hatte bereits 48 NEAR-/BCH-Füller-Trades und kam auf 1.613,19 USDC. Der 205er-Stand enthält 121 Füller-Trades; seine SUI-/UNI-Trades realisieren zusammen rund -40,21 USDC. Alle 84 abgeschlossenen Core-Trades waren in den verglichenen Varianten identisch. Der Core war 72,64 % der Zeit investiert; Handelsanzahl ist keine Leerlaufmessung.

Die Folgekorrektur aktiviert NEAR, AAVE und BCH gemeinsam und belässt SUI/UNI in der Forschung. Auf demselben Fenster (06.10.2023 19:00 UTC bis 06.10.2026 19:00 UTC) ergeben sich 186 Trades und 1.637,36 USDC. Bei Stresskosten: 1.523,00 USDC gegenüber 1.496,65 USDC Core allein. Damit unterstützen die drei Füller den Core in beiden Kostenmodellen des betrachteten Gesamtfensters; einzelne Trades/Teilzeiträume können weiterhin negativ sein. Die Auswahl erfolgte anhand bereits betrachteter historischer Daten und ist kein unabhängiger Zukunftstest. 1.600 USDC sind keine garantierte Untergrenze. Live bleibt gesperrt bis zur expliziten lokalen Freigabe.

Der gespeicherte UI-Schalter „Zwischenfüller mit Core-Vorrang“ (`gap_fillers_enabled`) aktiviert oder deaktiviert zusätzliche Füller-Einstiege in Shared-Backtest, Paper und Live. Ausschalten lässt nur den Core neue Positionen eröffnen; bestehende Füller werden weiter betreut und müssen weiterhin für Core weichen. Der isolierte Backtest prüft stets alle 15 Profile einzeln.

## Backtests und Forschung

Es gibt zwei getrennte Sichtweisen:

1. **15×250 isoliert**: Laborvergleich mit einem separaten 250-USDC-Konto je Coin. Das ist kein 3.750-USDC-Hauptkonto.
2. **Shared-Maximalbudget**: das Produktmodell mit einem gemeinsamen Kapital X und zwei 50-%-Slots. Core hat absolute Priorität; die drei aktiven Satellites füllen vollständig freie Core-Phasen.

UI und CLI verwenden für V8 denselben Backtest-Pfad und dieselbe aktuelle
Portfolio-Handelsengine. `all` und `single` starten unabhängige Konten mit jeweils
250 USDC, unabhängig vom gespeicherten Maximalbudget. Alle 15 echten Preiswege
bleiben als Marktkontext erhalten; nur der ausgewählte Coin darf gekauft werden.
Reinvestition, Größenberechnung, Core-Vorrang und Risikoprüfungen folgen den
aktuellen Einstellungen. Research-only-Coins können deshalb null Trades haben.
`portfolio` verwendet das gespeicherte Budget einmal gemeinsam; im Automatikmodus
stammt sein Startkapital aus einer frischen Abfrage des freien Binance-USDC.
Nur ohne API-Schlüssel wird dafür ein ausdrücklich simuliertes 1.000-USDC-Budget
verwendet. Ein vorhandener, fehlerhafter Schlüssel führt zu einem Fehler und niemals
zu einem stillen Ersatzbudget. Einzelkonten bilden keine gemeinsame Slotkonkurrenz
ab und haben deshalb trotz gleicher Handelsregeln nicht dieselben Trades.
Beide Berichte umfassen exakt drei Kalenderjahre plus 400 Warm-up-Stunden.
Vorhandene echte USDC-Kerzen haben Vorrang. Nur der fehlende ältere Anfang wird mit
öffentlichen Kerzen des entsprechenden USDT-Basismarktes ergänzt. Der Bericht und
sein Manifest weisen diese Näherung je Markt aus; sie belegt keine historische
USDC-Liquidität. Der separate Cache `data/backtest-history.sqlite3` gelangt niemals
in Paper-/Live-Marktdaten. Backtests verändern weder das Budget noch das Paper-Konto.

Slotzahl und Coinprofile werden kausal getrennt erforscht. Mehr Trades allein sind kein Akzeptanzkriterium. Kandidaten müssen Baseline/Stress, Drawdown, Kosten, Occupancy, point-in-time Semantik und Out-of-Sample-/Validation-Gates bestehen. Historische Simulationen garantieren keine zukünftigen Ergebnisse.

## Echtgeldstufen

1. Binance-Key/Secret bleiben ausschließlich lokal.
2. Read-only Kontovorprüfung.
3. Erster Echtgeldtest: genau 1×50 USDC, nur nach expliziter lokaler Freigabe und neuem gültigem Signal.
4. Erst nach vollständig reconciled Roundtrip kann normaler Livebetrieb mit dem gespeicherten Maximalbudget freigegeben werden.
5. Eine Strategie-/Source-/Budgetabweichung bleibt fail-closed; bestehende eigene Positionen dürfen nur im überwachten EXIT_ONLY-Pfad verwaltet werden.

## Schnellstart

Windows: `Startbot.bat`

Alternativ:

    py -3 src/main.py status
    py -3 src/main.py data sync --symbol ALL
    py -3 src/main.py data audit --symbol ALL
    py -3 src/main.py backtest all --strategy v8
    py -3 src/main.py backtest portfolio --strategy v8
    py -3 src/main.py start --no-browser

Die UI läuft standardmäßig auf http://127.0.0.1:8765/.

Eine releasefähige Version benötigt auf demselben exakten Commit grüne Integration, reproduzierbaren UI-Build, vollständige Regression, A09 QA_PASS und A11 GOVERNANCE_PASS. Code-Promotion aktiviert weder Live noch Echtgeld automatisch.

## Aktivitätsnachweis und Vergleich vom 7. Oktober 2026

Die Statusanzeige prüft frische Marktdaten und vollständige Paper-Checkpoints für
alle 15 Märkte. Sie zeigt die zuletzt verarbeitete abgeschlossene Kerze sowie den
Grund für Warten, Positionsüberwachung oder Pause. Paper-Start aktiviert keinen
Echtgeldtest.

Auf dem unveränderten Vergleichsfenster 6.10.2023 19:00 UTC bis 6.10.2026 19:00 UTC
erreicht Core10 plus NEAR/AAVE/BCH bei 250 USDC 186 abgeschlossene Trades und
1.637,36 USDC Endwert; Core allein 84 und 1.582,30. Alle 84 abgeschlossenen
Core-Trades bleiben identisch. Jahresgewinne des gemeinsamen Portfolios:
640,98 / 721,86 / 24,51 USDC. Bei erhöhten Handelskosten ist das dritte Jahr
mit -30,73 USDC negativ. Der separate 1.000-USDC-Modelltest endet bei 6.561,61
USDC; er verändert das gespeicherte Budget nicht. Maximaler Rückgang rund 40 %.
Die auf diesem Zeitraum gewählte Konfiguration ist keine unabhängige
Out-of-Sample-Validierung und garantiert keine künftigen Jahresgewinne.

## Laptop-Paket und DOT-Feinjustierung vom 7. Oktober 2026

Der aktuelle V8-Stand ergänzt bei DOT die steigende 24-Stunden-VIDYA als
Einstiegsfilter. Alle anderen Profile und die Kapitalverteilung bleiben gleich;
V6 bleibt der unveränderte Regressionstest. Gemeinsamer Dreijahrestest bei
250 USDC: 185 Trades, 1.654,36 USDC Endwert; Stresskosten: 188 Trades,
1.539,92 USDC. Das ist eine historische Verbesserung, keine Gewinnwahrscheinlichkeit
oder Zukunftsgarantie. Die vorherigen 186er/205er-Snapshots bleiben erhalten.
Start auf einem weiteren Rechner: LAPTOP_START_HIER.md.
