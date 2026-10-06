# Der Hixton

Der Hixton 0.5.0 ist ein lokaler deutschsprachiger Binance-Spot-Bot für 15 USDC-Märkte. Das aktuelle Produkt ist **V8**: der unveränderte, eingefrorene V6-Zehn-Coin-Core plus ein separater Satellite-Layer. Backtest, Paper und der guarded lokale Live-Pfad verwenden dieselbe StrategyDefinition, dieselbe Kapitalquelle und dieselben point-in-time Routingregeln.

## Produktvertrag

- Core: BTC, ETH, BNB, SOL, XRP, ADA, LINK, AVAX, DOT und DOGE gegen USDC.
- Satellite-Forschungsuniversum: SUI, NEAR, UNI, AAVE und BCH gegen USDC.
- Im Shared-Produkt aktiv: **NEARUSDC und BCHUSDC**. SUI/UNI/AAVE bleiben research-only und dürfen kein Shared-Kapital belegen.
- Satellites dürfen nur handeln, wenn der Core komplett idle ist. Ein ausführbares Core-Signal verdrängt benötigte Satellite-Positionen am nächsten ausführbaren Open.
- Zeitrahmen: 1h. Signal-/Filter-/Exitlogik verwendet nur vollständig geschlossene Kerzen; Fills werden am nächsten verfügbaren Open modelliert.
- Backtestfenster: exakt drei Kalenderjahre bis zur letzten vollständig geschlossenen UTC-Stunde plus 400 Warm-up-Bars davor.
- Kanonische Strategiequelle: `src/hixton/domain/versions.py`.
- **V6** bleibt der eingefrorene Zehn-Coin-Regressionsanker; **V8** ist das aktuelle Produkt.
- Kanonische Kapitalquelle: `max_capital_usdc`.
- Allocator: `CAPITAL-V1-2X50PCT` = zwei Tranchen zu je 50 % des konfigurierten Maximalbudgets. 250 → 2×125, 1.000 → 2×500. Diese Zahlen sind Beispiele; die Produktlogik skaliert aus X.
- Core nutzt `ranked_repeat`; aktive Satellites bekommen höchstens einen Slot pro Symbol.
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

Alle fünf Profile bleiben im isolierten 15×250-Labor sichtbar. Shared-Kapital erhalten derzeit nur NEAR und BCH.

| Coin | Shared | Kerneigenschaft |
|---|---|---|
| SUIUSDC | Research-only | isoliert profitabel, Shared-/Preemption-Kandidat derzeit nicht freigegeben |
| NEARUSDC | **Aktiv** | Gap-Filler, getesteter 48h Max-Hold/Value-Decay-Pfad |
| UNIUSDC | Research-only | Shared-/Short-Gap-Kandidat derzeit nicht freigegeben |
| AAVEUSDC | Research-only | Shared positiv in Teiltests, aber nicht robust genug für Aktivierung |
| BCHUSDC | **Aktiv** | Gap-Filler mit point-in-time ATR-Regimefilter |

## Backtests und Forschung

Es gibt zwei getrennte Sichtweisen:

1. **15×250 isoliert**: Laborvergleich mit einem separaten 250-USDC-Konto je Coin. Das ist kein 3.750-USDC-Hauptkonto.
2. **Shared-Maximalbudget**: das reale Produktmodell mit einem gemeinsamen Kapital X und zwei 50-%-Slots. Core hat absolute Priorität; validierte Satellites füllen nur echte Core-Leerlücken.

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
