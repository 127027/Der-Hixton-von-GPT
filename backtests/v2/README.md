# HIXTON V2 – aktive Paperstrategie seit 02.09.2026

Status: `PAPER_ACTIVE`, `LIVE_BLOCKED`. Der Eigentümer hat V2 mit `DEC-037` ausdrücklich als bislang besten Paperstand freigegeben. Die unveränderliche Versionskennung enthält weiterhin `RESEARCH-CANDIDATE`; sie wird für historische Nachvollziehbarkeit nicht umbenannt. Dieser Ordner überschreibt weder V1 noch alte Runs.

## Ausgangspunkt und Fehlerbild von V1

Der echte V1-Dreijahreslauf `68e84b25-91f9-4faa-9a65-a6699b8bd7d5` endete in der Baseline bei 3.387,67 USDT aus 2.500 USDT (+35,51 %) und im Stress bei 1.681,85 USDT (−32,73 %) mit jeweils 1.724 abgeschlossenen Trades. ETH, LINK und DOT waren in der Baseline negativ.

Die Tradeanalyse zeigt das gemeinsame Muster: Bei allen zehn Coins verloren die in weniger als 72 Stunden geschlossenen Trades in Summe Geld; die Gewinne kamen aus den länger laufenden Trends. Die Jahre 2025 und 2026 waren für V1 breit schwach. Der Schluss daraus ist ausdrücklich nicht „beliebig mehr Trades“, sondern weniger kurze Fehlausbrüche bei weiterhin ausreichender Signalzahl.

## Referenz und geprüfter Suchraum

- Vom Eigentümer bereitgestellte Pine-v6-Quelle: `strategy/pine/Der_Hixton_Indikator_v6.pine`
- SHA-256: `8af8e9a1e6c73dc66307271b7fd1141eaae02bc1fe88e8ba97b96e7a861263dd`
- 1.280 gemeinsame Parametersätze im breiten Raster: VIDYA `6/10/14/20`, Momentum `10/20/30/50`, SMA `8/24/36/60`, ATR `60/120/200/320`, Band `2,0/2,6/3,2/3,8/4,4`
- 75 Spitzensätze anschließend über drei Marktfenster und beide Kostenmodelle verglichen
- 48 direkte Nachbarn um den besten Bereich als Sensitivitätsprüfung
- Screening mit Pine-v6-Signalmathematik; Finalisten erneut mit der Produktionsengine, Decimal-Geldfluss und Binance-Mengenrundung gerechnet
- Keine Coin-Auswahl nach Ergebnis: alle zehn festgelegten Märkte bleiben in jeder Wertung

Die drei beobachteten Fenster sind keine unangetastete finale Zukunftsstichprobe. Deshalb ist das Ergebnis ein Kandidat und keine Livefreigabe.

## Ausgewählter gemeinsamer Kandidat

| Parameter | Wert |
|---|---:|
| VIDYA | 6 |
| Momentum/CMO | 20 |
| Nachglättung SMA | 8 |
| ATR | 60 |
| Bandmultiplikator | 3,80 |
| Warm-up | 400 Bars |
| Signaltimeframe | 1h |
| Semantik | Pine v6 aus der Eigentümerquelle |

Der direkte Nachbar mit Band 3,75 erzeugte im aktuellen Fenster 574 statt 549 Trades, war aber sowohl im Kosten-Stress als auch in beiden älteren Segmenten schwächer. 3,80 bleibt deshalb der Hauptkandidat; 3,75 ist nur ein dokumentierter Challenger.

## Exakter aktueller Dreijahreslauf

Fenster: `[2023-09-01 12:00 UTC, 2026-09-01 12:00 UTC)`, zehn isolierte Konten à 250 USDT.

- Primär-Run: `8dbdeb5b-a4e8-4b56-b6dc-61c7f0d54e93`
- Wiederholungs-Run: `a7c96450-29f6-437d-af97-402d9d9c58cc`
- Ausführung über den einzigen Einstieg: `py -3 src/main.py backtest all --strategy v2 --end 2026-09-01T12:00:00Z --cost both`

| Szenario | Endkapital | Rendite | Trades | kombinierter Max-Drawdown |
|---|---:|---:|---:|---:|
| Baseline, 15 bps/Seite | 6.592,22 USDT | +163,69 % | 549 | 22,00 % |
| Stress, 40 bps/Seite | 5.843,73 USDT | +133,75 % | 549 | 28,40 % |

| Coin | Baseline Ende | Baseline Rendite | Stress Rendite | Trades | Profit Factor | Max-DD |
|---|---:|---:|---:|---:|---:|---:|
| BTC | 414,47 | +65,79 % | +28,43 % | 71 | 1,26 | 34,11 % |
| ETH | 649,16 | +159,67 % | +128,46 % | 61 | 1,92 | 32,42 % |
| BNB | 388,69 | +55,48 % | +24,69 % | 60 | 1,31 | 36,05 % |
| SOL | 1.508,45 | +503,38 % | +478,72 % | 44 | 4,88 | 23,54 % |
| XRP | 557,38 | +122,95 % | +80,60 % | 55 | 1,35 | 53,15 % |
| ADA | 678,79 | +171,52 % | +142,97 % | 55 | 1,68 | 41,39 % |
| LINK | 612,46 | +144,98 % | +119,65 % | 49 | 1,48 | 37,72 % |
| AVAX | 526,69 | +110,68 % | +80,17 % | 60 | 1,47 | 35,81 % |
| DOT | 447,99 | +79,20 % | +56,70 % | 44 | 1,44 | 47,50 % |
| DOGE | 808,14 | +223,26 % | +197,11 % | 50 | 2,20 | 41,52 % |

Alle zehn Coins waren in diesem Fenster selbst im Stress positiv. Sieben von zehn überschritten 500 USDT; BTC, BNB und DOT erreichten das angestrebte Verdopplungsziel nicht. Es wird kein anderes Ergebnis behauptet.

Die Wiederholung erzeugte bytegleiche Kernartefakte:

| Artefakt | SHA-256 in beiden Runs |
|---|---|
| `metrics.json` | `1EAB7D6F9DB0D34C95CE513571CB6417FC37763F8214EFFF32EE15F31F7AAF45` |
| `trades.csv` | `E40EECBDF15674E69B77BC5F4F0D6E418BCE75ADC7CF8914BD05F9E2E34DF843` |
| `equity.csv` | `E90DD77892565E553CA8C8D04F5C07F010CD89247B2E1050DA430FEC8593FA7D` |

## Gemeinsames 3×80-USDT-Strategiereplay

Der isolierte 10×250-Lauf beantwortet nicht, was aus gemeinsam eingesetzten 240 USDT geworden wäre. Deshalb wurde Kandidat 1 zusätzlich mit dem Paper-Kapitalmodell gerechnet: ein Cashpool, maximal drei gleichzeitige Slots, höchstens 80 USDT je Einstieg, kein automatisches Compounding und dieselbe deterministische Slotpriorität. Dieser erste Stand enthielt noch nicht die operativen 5-/20-%-Risikogates und wird deshalb klar als `strategy-only` bezeichnet.

- Primär-Run: `4aa4d135-b077-4c29-a839-fa141952113b`
- Wiederholungs-Run: `060745da-5e9f-4445-a768-0b2c2da63851`
- Ausführung: `py -3 src/main.py backtest portfolio --strategy v2 --end 2026-09-01T12:00:00Z --cost both`

| Szenario | Endkapital | Rendite | Trades | Gewinnquote | Profit Factor | Max-DD | Buy & Hold Ende |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 528,38 USDT | +120,16 % | 227 | 37,44 % | 1,37 | 34,10 % | 490,90 USDT |
| Stress | 436,31 USDT | +81,79 % | 227 | 35,68 % | 1,22 | 43,33 % | 489,68 USDT |

Die Baseline verdoppelte das gemeinsame Startkapital historisch und übertraf die gleichgewichtete Buy-and-Hold-Benchmark. Unter Stress blieb das Ergebnis positiv, aber unter 480 USDT und unter Buy-and-Hold. Von 781 Order-Signalen wurden 456 ausgeführt; 325 Einstiegssignale wurden ausschließlich als `NO_FREE_SLOT` protokolliert. Am Ende waren BTC und SOL noch offen und zum letzten Schlusskurs enthalten. Damit wird insbesondere nicht behauptet, die isolierten 6.592,22 USDT seien mit realen 240 USDT erreichbar gewesen.

Die Wiederholung erzeugte erneut bytegleiche Kernartefakte:

| Artefakt | SHA-256 in beiden Runs |
|---|---|
| `metrics.json` | `62BE829B0B57354AB2EBD5F824C576ECEE86B6B9829ABA33382272C8820B0119` |
| `trades.csv` | `47D6063FE662E0223D0A4FB3E6C27613D765E6C0C98A606DB6A47D707BB74AA0` |
| `equity.csv` | `5B8994F48EC7B2756CC73B58839B7AF521F7D3A6E6FD2FAE34F3A5A15AE43E48` |

## Paper-/Live-Risikospiegel nach Paritätskorrektur

Vor einer Livefreigabe wurde die fehlende Risikoparität geschlossen. Der Modus `backtest portfolio` nutzt nun zusätzlich dieselbe 5-%-Tagesverlustpause und denselben persistenten 20-%-Drawdown-Halt wie das Paperledger.

- Primär-Run: `83b38ab1-cf26-4ab2-a4b1-6e1e290822ea`
- Wiederholungs-Run: `c908cf2f-5910-4dfe-97b0-e6c40465205d`
- Ausführung: `py -3 src/main.py backtest portfolio --strategy v2 --end 2026-09-01T12:00:00Z --cost both`

| Szenario | Endkapital | Rendite | Trades | Profit Factor | Max-DD | Risikohalt |
|---|---:|---:|---:|---:|---:|---|
| Baseline | 542,49 USDT | +126,04 % | 108 | 2,04 | 22,77 % | 06.02.2025 |
| Stress | 406,29 USDT | +69,29 % | 30 | 3,52 | 20,13 % | 05.02.2024 |

Das Ergebnis ist positiv, aber der Bot hätte nicht drei Jahre durchgehend weitergehandelt. Der Baseline-Halt blockierte danach 307 Einstiege, der Stress-Halt 487. Die älteren Risikospiegel endeten mit Verlust: 227,42/223,32 USDT im ersten und 207,24/201,90 USDT im zweiten Segment. Deshalb ist V2 als Paper-Forward-Test vertretbar, aber weiterhin nicht live-reif.

Der mit exakt gleichem Fenster und Risikomodell nachgerechnete V1-Run `70089491-f5b6-4388-a420-b2c7f4641225` endete bei 383,89 USDT Baseline und 343,47 USDT Stress. V2 lag im direkten Vergleich um 158,60 beziehungsweise 62,82 USDT höher und ist deshalb nach Eigentümerentscheidung der aktive Paperstand.

| Artefakt | SHA-256 in beiden korrigierten Runs |
|---|---|
| `metrics.json` | `DBF2F599F533A2B8BED40DB71835DA2B197E3D9F306E12D22B6FA3D09BE5446C` |
| `trades.csv` | `FFD91869C4FD3F4D24AA41F00B2758D2FE70B05FF9215D8B95FA14E1016B15D8` |
| `equity.csv` | `3914FC1FDC11C24DCAD94F95D65EA29842678E3BDA25A9CB414338DE70DBCB6C` |

## Fokussierter Band-4,0-Challenger verworfen

Band 4,0 wirkte im aktuellen gemeinsamen Portfolio mit 776,56 USDT Baseline und 684,84 USDT Stress zunächst deutlich besser als 3,8. Im älteren Segment 16.10.2021–24.03.2023 fiel es jedoch auf 230,07 USDT Baseline und 178,58 USDT Stress, während Band 3,8 dort 291,76 beziehungsweise 208,73 USDT erreichte. Band 4,0 wird deshalb als jüngst überangepasst verworfen und nicht aktiviert.

## Ältere Marktsegmente

Wegen echter Binance-Wartungslücken wurden keine Kerzen erfunden. Statt eines künstlich geschlossenen Dreijahresfensters wurden zwei nach Datenprüfung lückenlose Segmente verwendet.

| Segment | Szenario | Aggregierte Rendite | Trades | kombinierter Max-DD |
|---|---|---:|---:|---:|
| 16.10.2021 01:00 – 24.03.2023 13:00 UTC | Baseline | +4,26 % | 252 | 32,29 % |
| gleiches Segment | Stress | −7,82 % | 252 | 34,54 % |
| 10.04.2023 06:00 – 01.09.2024 12:00 UTC | Baseline | +77,69 % | 238 | 18,50 % |
| gleiches Segment | Stress | +64,32 % | 238 | 20,12 % |

Über alle drei Fenster waren 24 von 30 Coin-Fenstern in der Baseline und 21 von 30 im Stress positiv. Das schwächere ältere Segment enthält deutliche Einzelverluste, unter anderem bei SOL und XRP. Diese Grenzen bleiben sichtbar und verhindern eine Livefreigabe; die Paperaktivierung ist ein kontrollierter Forward-/Soak-Test, keine Renditezusage.

## Abgelehnte Richtungen

- Ein Setup mit 1.837 Trades erreichte zwar +71,07 % Baseline, fiel im Stress aber auf −14,28 %. Mehr Trades allein wurden deshalb verworfen.
- Ein zusätzlicher Langfrist-Regimefilter reduzierte die Signale stark und beschädigte insbesondere XRP; er wurde nicht übernommen.
- Coin-spezifische Parameter lieferten schönere Einzelwerte, erhöhen aber Overfitting und Betriebsaufwand. V2 bleibt vorerst ein gemeinsamer Parametersatz für alle zehn Märkte.

## Nächster Freigabeschritt

1. Pine-Golden-Tests und bytegleichen V2-Reproduktionslauf dauerhaft grün halten.
2. Den neu gestarteten V2-Paper-Soak mindestens 30 Tage, 720 Bars je Coin und 20 abgeschlossene Trades beobachten; bei zu wenigen Trades höchstens bis 90 Tage verlängern.
3. Nettoperformance, Drawdown, Fehlerfreiheit, blockierte Signale und tatsächliche Tradezahl gegen den historischen V1-Abschnitt auswerten.
4. Live erst nach sämtlichen Gate-D-Nachweisen und einer neuen ausdrücklichen Eigentümerentscheidung erwägen.

Das Ziel „250 USDT möglichst in drei Jahren auf 500 USDT je Coin“ bleibt eine Optimierungsrichtung, keine Zusage und kein Grund, Verlustfenster zu verstecken.
