# Der Hixton

Der Hixton ist ein lokaler, deutschsprachiger **Paper-, Backtest- und gestuft freigebbarer Binance-Spot-Trading-Bot** für zehn Märkte gegen USDC. Der produktive Stand besitzt **eine** auswählbare Strategie: die aktuelle V6 mit coinindividuellen Profilen. Echtgeld ist beim Start niemals automatisch aktiv.

## Aktueller Produktvertrag

- Märkte: BTC, ETH, BNB, SOL, XRP, ADA, LINK, AVAX, DOT und DOGE gegen USDC.
- Signalzeitrahmen: 1h; Strategieentscheidungen nur auf abgeschlossenen Kerzen.
- Kanonische Strategiequelle: src/hixton/domain/versions.py.
- Runtime-Konfiguration speichert nur strategy.key = v6. Version und Profile werden nicht doppelt in Config-Dateien gepflegt.
- Haupt-Abnahmemodell: gemeinsames 250-USDC-Konto mit drei 80-USDC-Slots und ranked_repeat.
- Diagnose-/Optimierungslabor: zehn getrennte Konten à 250 USDC (10×250).
- Drawdown wird gemessen; der frühere permanente 20-%-Portfolio-Drawdown-Halt ist nicht Teil der aktiven V6.
- Die 5-%-UTC-Tagesverlustpause, Not-Aus, Cash-, Daten- und Exchange-Filter bleiben Sicherheitsgates.
- Paper nutzt echte öffentliche Binance-Marktdaten und simulierte Ausführung.
- Der lokale Echtgeldpfad ist gestuft: zuerst ein ausdrücklich freigegebener 1×50-USDC-Roundtrip; dauerhafter Livebetrieb erst danach mit exakt 3×80 USDC, erfolgreichem Kontoabgleich und allen Runtime-Gates.
- Cloud-/CI-/Agentenläufe bleiben key-free und dürfen weder Echtgeld- noch Testnet-Orders senden.

## Aktuelle V6-Profile

| Coin | VIDYA | Momentum | Smoothing | ATR | Band | Zusatzregel |
|---|---:|---:|---:|---:|---:|---|
| BTCUSDC | 5 | 20 | 8 | 120 | 4,4 | CMO floor 0,2 |
| ETHUSDC | 6 | 20 | 8 | 60 | 3,8 | VIDYA slope 24 |
| BNBUSDC | 10 | 20 | 8 | 120 | 5,0 | – |
| SOLUSDC | 6 | 20 | 15 | 60 | 3,8 | – |
| XRPUSDC | 6 | 20 | 8 | 120 | 3,2 | Close-Stop 4 Entry-ATR |
| ADAUSDC | 6 | 20 | 8 | 60 | 4,4 | – |
| LINKUSDC | 6 | 20 | 8 | 60 | 3,8 | VIDYA slope 24 |
| AVAXUSDC | 6 | 20 | 8 | 60 | 4,6 | – |
| DOTUSDC | 6 | 20 | 8 | 60 | 3,8 | – |
| DOGEUSDC | 6 | 18 | 15 | 120 | 4,4 | CMO floor 0,2 |

Alle Profile verwenden 400 Warm-up-Bars.

## Aktueller Forschungsnachweis

Quelle: Coin-Optimization Run 35463131378, Artifact 10590881515, Fenster 19.09.2023 19:00 UTC bis 19.09.2026 19:00 UTC.

| Modell | Aktuelles Endkapital |
|---|---:|
| 10×250 isoliert | **8.217,01 USDC** |
| 3×80 Portfolio | **1.217,91 USDC** |

3×80 aktuell: 94 Positionszyklen, 210 Slot-Trades, 24,10 % Max-Drawdown. Das sind historische Simulationen, keine Gewinnprognose. Interne Forschungsvarianten und Robustheitsprüfungen bleiben im Forschungsjournal und werden nicht als parallele Produktresultate dargestellt.

## Optimierungsprozess

Der Dauerzyklus sucht pro Coin die robust beste Methode. Aktive V6-Varianten und auch Buy-and-Hold dürfen intern als Kandidaten antreten. Auswahl erfolgt auf Training, danach folgen unabhängige Validierung, vollständiger Drei-Jahres-Test und der entscheidende gemeinsame 3×80-Portfolio-Gate. Pro Coin wird nur der robuste Gewinner kanonisch; die normale UI zeigt nur diesen aktiven Stand.

Der Workflow Hixton Coin Optimization Cycle läuft zusätzlich planmäßig alle sechs Stunden. Er darf neue Forschungsergebnisse erzeugen, aber weder automatisch mergen noch Paper oder Echtgeld aktivieren. A01–A11 prüfen die aktuelle Mission unabhängig und key-free.

## Schnellstart

Unter Windows:

    Startbot.bat

Alternativ:

    py -3 src/main.py status
    py -3 src/main.py data sync --symbol ALL
    py -3 src/main.py data audit --symbol ALL
    py -3 src/main.py backtest all --strategy v6
    py -3 src/main.py backtest portfolio --strategy v6
    py -3 src/main.py backtest single --strategy v6 --symbol BTCUSDC
    py -3 src/main.py start --no-browser

Die lokale Oberfläche läuft standardmäßig auf http://127.0.0.1:8765/. Normale UI/API/CLI bieten nur die aktuelle V6 an.

## Entwicklung und Abnahme

    py -3 -m pip install -e ".[dev]"
    py -3 -m pytest -q
    py -3 -m ruff check .
    py -3 -m mypy src
    cd ui
    npm.cmd ci
    npm.cmd run check
    npm.cmd run build

Eine releasefähige Version benötigt auf dem exakten Commit grünen Preflight, Dashboard-E2E, vollständige Regression, A09 QA_PASS und A11 GOVERNANCE_PASS. Die Codefreigabe des Livepfads ersetzt keinen echten Kontonachweis: der erste 1×50-USDC-Roundtrip muss lokal mit dem eigenen Binance-Konto durchgeführt und vollständig reconciled werden, bevor 3×80 überhaupt freigeschaltet werden kann.

Zentrale Dokumentation: DMS/00_DOKUMENTENLENKUNG_UND_START.md. Forschungsjournal: backtests/README.md.
