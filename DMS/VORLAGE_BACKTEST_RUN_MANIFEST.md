# Vorlage – Backtest-Run-Manifest

## Identität

- Run-ID:
- Erzeugt UTC:
- Status: `VALID / INVALID / FAILED / STALE`
- Verantwortlich:

## Versionen und Hashes

- Code/Build:
- Strategieversion: `HIXTON-SPEC-1.0`
- normative Strategiequelle: `DMS/03_STRATEGIE_HIXTON.md`
- Eigentümer-Pine-SHA-256: für V2 verpflichtend, für historische V1-Runs `null`
- Konfigurations-SHA-256:
- Daten-Snapshot-SHA-256:
- Dependency-Lock-SHA-256:
- DMS-Version:

## Daten

- Börse/Provider:
- Symbole:
- Timeframe: `1h`
- Warm-up Start UTC:
- Bericht Start UTC:
- Bericht Ende UTC:
- Bars erwartet/vorhanden:
- Lücken/Ausnahmen:
- Datenqualitätsbericht:

## Handelsannahmen

- Startkapital je Symbol: 250,00 USDT
- Zielnotional je isoliertem Einstieg: 250,00 USDT bzw. kleinerer verfügbarer Cashbetrag
- Run-Modus: `all_ten_isolated / single_symbol / paper_live_mirror`
- Einzeltest-Symbol (falls zutreffend):
- Spiegelportfolio: 250,00 USDT (historische 240,00-USDT-Läufe explizit kennzeichnen) / 3 Slots / 80,00 USDT Zielnotional
- Positionsgröße:
- Compounding: `false`
- Fillmodell: `next_bar_open`
- Ordertyp: simulierte Market-Order
- Gebühren: Baseline/Stress jeweils 10 bp je Seite, kein BNB-/VIP-Rabatt
- Slippage/Spread: Baseline 3/2 bp je Seite; Stress 20/10 bp je Seite
- Tick-/Step-/Mindestnotional-Stand:
- offene Position am Testende:

## Validierung

- Spezifikationsparität:
- Replay = Batch:
- Reproduktionslauf:
- Holdout-/Optimierungsstatus:
- bekannte Einschränkungen:

## Artefakte

- Einzelmetriken:
- Portfoliometriken:
- Trades:
- Equity/Drawdown:
- Benchmark:
- Laufprotokoll:
