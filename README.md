# Der Hixton

Der Hixton 0.5.0 ist ein lokaler deutschsprachiger Binance-Spot-Bot für 15 USDC-Märkte. Das aktuelle Produkt ist **V8**: der unveränderte, eingefrorene V6-Zehn-Coin-Core plus ein separater Satellite-Layer. Backtest, Paper und der guarded lokale Live-Pfad verwenden dieselbe StrategyDefinition, dieselbe Kapitalquelle und dieselben point-in-time Routingregeln.

## Produktvertrag

- Core: BTC, ETH, BNB, SOL, XRP, ADA, LINK, AVAX, DOT und DOGE gegen USDC.
- Die fünf Zwischenfüller SUI, NEAR, UNI, AAVE und BCH gegen USDC sind gemeinsam aktiv.
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
| SUIUSDC | **Aktiv** | ATR-Regimefilter und Close-Stop |
| NEARUSDC | **Aktiv** | 48h Max-Hold |
| UNIUSDC | **Aktiv** | CMO- und VIDYA-Slope-Filter |
| AAVEUSDC | **Aktiv** | ATR-/Trend-Regimefilter und Close-Stop |
| BCHUSDC | **Aktiv** | point-in-time ATR-Regimefilter |

Die korrigierte lokale Revision vom 06.10.2026 stellt den ursprünglichen Core-Allocator wieder her. Auf denselben Kerzen (06.10.2023 19:00 UTC bis 06.10.2026 19:00 UTC) ergab der Vergleich 205 statt 132 abgeschlossene Trades und 1.606,89 statt 1.613,19 USDC Endwert. Die verworfene Variante mit halbiertem Core-Einsatz hatte nur rund 1.221 USDC erreicht. Bei Stresskosten sinkt der korrigierte Endwert auf rund 1.456,64 USDC; der Füllerbeitrag ist dann negativ. Das ist keine vollständige Release-/Zukunftsvalidierung. Live bleibt gesperrt bis zur expliziten lokalen Freigabe.

Der gespeicherte UI-Schalter „Zwischenfüller mit Core-Vorrang“ (`gap_fillers_enabled`) aktiviert oder deaktiviert zusätzliche Füller-Einstiege in Shared-Backtest, Paper und Live. Ausschalten lässt nur den Core neue Positionen eröffnen; bestehende Füller werden weiter betreut und müssen weiterhin für Core weichen. Der isolierte Backtest prüft stets alle 15 Profile einzeln.

## Backtests und Forschung

Es gibt zwei getrennte Sichtweisen:

1. **15×250 isoliert**: Laborvergleich mit einem separaten 250-USDC-Konto je Coin. Das ist kein 3.750-USDC-Hauptkonto.
2. **Shared-Maximalbudget**: das Produktmodell mit einem gemeinsamen Kapital X und zwei 50-%-Slots. Core hat absolute Priorität; die fünf Satellites füllen freie Kapazität.

UI und CLI verwenden für V8 denselben Backtest-Pfad. Beide lesen das gespeicherte
Maximalbudget X. `all` simuliert alle 15 Profile isoliert mit je X USDC
(standardmäßig 15×250); `portfolio` verwendet X einmal gemeinsam und wendet
die aktuellen Core-/Zwischenfüller-Regeln mit ursprünglicher Core-Kapitalverteilung an.
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
