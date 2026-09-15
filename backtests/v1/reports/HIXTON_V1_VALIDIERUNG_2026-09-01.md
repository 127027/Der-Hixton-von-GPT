# HIXTON V1 – kuratierter Backtestnachweis vom 01.09.2026

Dieser kleine Git-Nachweis verweist auf den lokal erhaltenen, unveränderlichen Run `68e84b25-91f9-4faa-9a65-a6699b8bd7d5`. Große Marktdaten-, Trade- und Equity-Dateien bleiben gemäß DMS außerhalb von Git.

## Manifest

- Code: `3472415ec683597301eaed8c8ce930edec8804e8`
- Strategie: `HIXTON-SPEC-1.0`
- Config: `b2d5caafab7f702cabcc872b7078d4bf199d45fd8e5c6dd25fcba52e428b5966`
- Binance-Spot-Fenster: `[2023-09-01 12:00 UTC, 2026-09-01 12:00 UTC)`
- Daten je Coin: 26.304 Auswertungsbars plus 400 Warm-up-Bars
- Kapital: zehn vollständig isolierte Konten à 250 USDT
- Baseline: 15 bps je Seite; Stress: 40 bps je Seite

## Resultat

| Szenario | Endkapital | Netto-PnL | Rendite | Trades | Max. Drawdown |
|---|---:|---:|---:|---:|---:|
| Baseline | 3.387,67 USDT | +887,67 USDT | +35,51 % | 1.724 | 45,48 % |
| Stress | 1.681,85 USDT | −818,15 USDT | −32,73 % | 1.724 | 68,06 % |

## Bytegleiche Wiederholung

Wiederholungs-Run: `5192d8fd-7e16-41d8-b0de-214593878a76`.

| Datei | SHA-256 in beiden Runs |
|---|---|
| `metrics.json` | `9BDE37DE072ACFC37B9799013EC48AF32730D02CCF0DF63E0040907296467A01` |
| `trades.csv` | `3CF6AD814D1DD73E35D4689A38870FC91DB4BF31D4C0A8CF98046837A4375CAB` |
| `equity.csv` | `8FADBD9B8A89796D37A301708A8FDAAC7DCCA32FED1B10781FDABC85972FED73` |

ETH-Einzeltest: Run `cb4d0b5e-b903-4bba-895f-c92a9da5c1d1`, 250 USDT Start, Baseline 178,27 USDT, Stress 73,92 USDT, jeweils 181 Trades.

## Warnung

Der Lauf beweist die deterministische Umsetzung der Projektspezifikation, nicht zukünftige Profitabilität oder Herstellerparität. Hohe Drawdowns und das negative Stressresultat schließen eine automatische Live-Freigabe ausdrücklich aus.
