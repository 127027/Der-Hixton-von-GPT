# Der Hixton

Der Hixton 0.5.0 ist ein lokaler deutschsprachiger Binance-Spot-Bot für zehn USDC-Märkte mit einer gemeinsamen V6-Strategie. Backtest, Paper und normaler Livebetrieb verwenden dieselben Coin-Profile und denselben Kapital-Allocator.

## Produktvertrag

- Märkte: BTC, ETH, BNB, SOL, XRP, ADA, LINK, AVAX, DOT und DOGE gegen USDC.
- Zeitrahmen: 1h; Entscheidungen nur auf abgeschlossenen Kerzen.
- Kanonische Strategiequelle: `src/hixton/domain/versions.py`.
- Kanonische Kapitalquelle: `max_capital_usdc`. In der UI wird nur **Maximaler USDC-Einsatz** editiert.
- Aktueller validierter Allocator: `CAPITAL-V1-2X50PCT`: zwei ranked-repeat-Tranchen zu je 50 % des Maximalbudgets.
- Standardbudget: 250 USDC → automatisch 2 × 125 USDC. 500 → 2 × 250; 1.000 → 2 × 500.
- Freie Tranchen gehen an die aktuell stärksten gültigen Signale; es wird kein historischer Gewinner-Coin fest verdrahtet.
- 10×250 isoliert ist ausschließlich Forschung zur coinindividuellen Profiloptimierung.
- Portfolio-Backtest, Paper und normaler Livebetrieb verwenden denselben Maximalbudget-Plan.
- Die 5-%-UTC-Tagesverlustpause, Not-Aus, Daten-, Cash- und Exchange-Gates bleiben aktiv.
- Echtgeld ist beim Start niemals automatisch aktiv.

## V6-Coin-Profile

| Coin | VIDYA | Momentum | Smoothing | ATR | Band | Zusatzregel |
|---|---:|---:|---:|---:|---:|---|
| BTCUSDC | 5 | 20 | 8 | 120 | 4,4 | CMO floor 0,2 |
| ETHUSDC | 6 | 20 | 8 | 60 | 3,8 | VIDYA slope 24 |
| BNBUSDC | 10 | 20 | 8 | 120 | 5,0 | – |
| SOLUSDC | 6 | 20 | 15 | 60 | 3,8 | – |
| XRPUSDC | 6 | 20 | 8 | 120 | 3,2 | CMO floor 0,15 + Close-Stop 4 Entry-ATR |
| ADAUSDC | 6 | 20 | 8 | 60 | 4,4 | – |
| LINKUSDC | 6 | 20 | 8 | 60 | 3,8 | VIDYA slope 24 |
| AVAXUSDC | 6 | 20 | 8 | 60 | 5,2 | – |
| DOTUSDC | 6 | 20 | 8 | 60 | 3,8 | CMO floor 0,35 |
| DOGEUSDC | 6 | 18 | 15 | 120 | 4,4 | CMO floor 0,2 |

Alle Profile verwenden 400 Warm-up-Bars.

## Echtgeldstufen

1. Binance-Key/Secret werden nur lokal im Windows-Anmeldedatenspeicher gehalten.
2. Read-only Kontovorprüfung: Spot/USDC, Rechte, freie Salden, offene Orders und Marktfilter.
3. Erster Echtgeldtest: **genau 1 × 50 USDC**. Die Freigabe sendet nicht sofort eine Order, sondern wartet auf ein neues gültiges Signal, führt einen Entry und den regulären Exit aus und reconciled anschließend Konto/Fills. Bereits vorhandene freie Spot-Bestände sind kein Blocker: sie werden in einer unveränderlichen Konto-Baseline erfasst, nicht als Hixton-Position übernommen und niemals durch einen Hixton-SELL verbraucht.
4. Erst nach vollständig abgeschlossenem 1×50-Roundtrip kann der normale budgetgesteuerte Livebetrieb freigegeben werden. Dieser nutzt das in der UI gespeicherte Maximalbudget und denselben Allocator wie Paper/Backtest.
5. Eine Budgetänderung während eines gebundenen Live-Ledgers stoppt neue Einstiege und benötigt eine sichere erneute Freigabe.

## Backtests und Forschung

Produktiver Portfolio-Backtest: das gespeicherte Maximalbudget mit dem zentralen Allocator.  
Coin-Forschung: 10×250 isoliert. Kandidaten werden ausschließlich isoliert gesucht und anschließend gegen das kanonische Maximalbudget-Portfolio auf Baseline und Stress geprüft.

Alle Produktbacktests verwenden exakt drei Kalenderjahre rückwärts vom Endzeitpunkt plus 400 Warm-up-Bars. Historische Simulationen sind keine Garantie für künftige Live-Ergebnisse und keine Behauptung historischer Binance-Fills.

## Schnellstart

Windows: `Startbot.bat`

Alternativ:

    py -3 src/main.py status
    py -3 src/main.py data sync --symbol ALL
    py -3 src/main.py data audit --symbol ALL
    py -3 src/main.py backtest all --strategy v6
    py -3 src/main.py backtest portfolio --strategy v6
    py -3 src/main.py start --no-browser

Die UI läuft standardmäßig auf http://127.0.0.1:8765/.

Eine releasefähige Version benötigt auf demselben Commit grünen Preflight, frischen Dashboard-E2E, vollständige Regression, A09 QA_PASS und A11 GOVERNANCE_PASS. Cloud/CI/A01–A11 verwenden keine privaten Binance-Credentials und senden keine Orders.
