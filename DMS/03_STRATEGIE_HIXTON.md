# 03 – Hixton-Strategie: aktive V6-Coin-Profile, V2-Referenz und V1-Historie

DEC-045 (06.09.2026): Auf ausdrücklichen Eigentümerwunsch wird V6 `HIXTON-V6-COIN-PAPER-1-9734f240e873` als **Paper-Experiment** aktiviert. Der frische Modellaccount startet mit 250 USDT, drei 80-USDT-Slots und 10 USDT Anfangsreserve. Alte Paperpositionen, Ereignisse, Dust und Soak bleiben ausschließlich im geprüften lokalen Vollarchiv; sie werden weder als neue Trades noch als Gewinn übernommen. Normale Neustarts erhalten das Konto weiterhin. Die schwächeren jüngsten/älteren Ergebnisse bleiben bestehen; dies ist keine Robustheits-, Optimalitäts- oder Livefreigabe.

Status: `VERBINDLICH` für Strategieversion `HIXTON-SPEC-1.0`.

## Referenz und Abgrenzung

Dieses Dokument ist die vollständige mathematische Referenz für die spätere Botimplementierung. Ein Entwickler darf keine fehlenden Werte ergänzen, keine Bibliotheksdefaults übernehmen und keine ähnliche Internetstrategie an die Stelle dieser Definition setzen.

Für V1 heißt „Hixton“ ausschließlich die nachfolgend eingefrorene VIDYA-/CMO-/ATR-Spezifikation. Am 01.09.2026 hat der Eigentümer zusätzlich den vollständigen Pine-v6-Code zur Projektverwendung übermittelt. Er liegt einmal unter `strategy/pine/Der_Hixton_Indikator_v6.pine` (SHA-256 `8af8e9a1e6c73dc66307271b7fd1141eaae02bc1fe88e8ba97b96e7a861263dd`) und ist die Referenz für V2. V1 wird dadurch nicht rückwirkend verändert; beide Versionen behalten getrennte Tests, Runs und Freigabestatus.

## Status der Strategieversionen

| Version | Formelreferenz | Parameter | Betriebsstatus |
|---|---|---|---|
| `HIXTON-SPEC-1.0` | normative V1-Definition in diesem Dokument | 10/20/SMA15/ATR200/Band2,0 | historische Paperstrategie und reproduzierbare Referenz |
| `HIXTON-V2-RESEARCH-CANDIDATE-1` | Eigentümer-Pine v6 | 6/20/SMA8/ATR60/Band3,8 | vorherige Paperreferenz (`DEC-037`); nicht Live |
| `HIXTON-V3-SLOT-CANDIDATE-1` | V2-Signalparameter plus `ranked_repeat` | wie V2, aber Mehrfachslots je Coin | `VERWORFEN`; nicht Paper/Live |

## V6 – vollständige Coin-Profile (aktives Paper-Experiment)

Version `HIXTON-V6-COIN-PAPER-1-9734f240e873`; maßgeblich ist `backtests/v6/candidate.json`, geprüft gegen die eine Definition in `src/hixton/domain/versions.py`. Nicht als Original-Pine-Default oder V2 ausgeben. Zahlenfolge VIDYA / Momentum / SMA / ATR / Band:

| Coin | Parameter | Zusatzregel |
|---|---|---|
| BTC | 6/20/8/120/4,4 | abs(CMO) ≥ 0,2 |
| ETH | 6/20/8/60/3,8 | aktuelle VIDYA > VIDYA 24 geschlossene Bars zuvor |
| BNB | 10/20/8/60/4,4 | keine |
| SOL | 6/20/15/60/3,8 | keine |
| XRP | 6/20/8/120/3,2 | Schlusskurs-Stop 4 Entry-ATR |
| ADA | 6/20/8/60/3,8 | keine; V2 beibehalten |
| LINK | 6/20/8/60/3,8 | keine; V2 beibehalten |
| AVAX | 6/20/8/60/4,4 | keine |
| DOT | 6/20/8/60/3,8 | keine; V2 beibehalten |
| DOGE | 6/20/15/120/4,4 | abs(CMO) ≥ 0,2 |

Alle zehn: Pine-v6-Formelsemantik, Quelle close, 1h, 400 Warm-up-Bars, initial DOWN ohne Order. Ein frischer Flip-Up wird nur bei bestandenen Coin-Filtern zum qualifizierten BUY. Abgewiesene Flips werden nicht nachgeholt. Ein echter Hixton-Flip-Down schließt Long; sonst darf XRP bei `close <= entry_fill_price - 4 * entry_ATR` aussteigen. Entry-ATR stammt vom BUY-Signal und bleibt in der Position gespeichert. Ausführung am nächsten echten Open plus Modellkosten, niemals intrabar oder garantiert zum Stopwert. Nach Stop kein Nachkauf ohne neuen Flip. Kein Trail in diesem Snapshot.

Paper, alle Backtestmodi und Chartmarker verwenden dieselbe Profilquelle und `TradePolicyGate`. Filter erzeugen keine zusätzlichen Flips. Charts zeigen qualifizierte hypothetische Coin-Trades, tatsächliche Slots/Cash/Risikogates sind nur in echten Paper-Fillmarkern abgebildet. Profilauswahl und schlechte Marktphasen sind ausdrücklich retrospektiv dokumentiert; keine Allzeitoptimalität. V6 ist durch DEC-045 ausdrücklich als Paper-Experiment freigegeben; die fehlende Mehrfensterrobustheit bleibt offen.

## Verbindliche Defaultparameter

| Parameter | V1-Wert |
|---|---:|
| Strategie-ID | `hixton_vidya_atr` |
| Strategieversion | `HIXTON-SPEC-1.0` |
| Markt | Binance Spot, USDT-Paare |
| Signaltimeframe | `1h` |
| Preisquelle | `close` |
| VIDYA-Länge `L` | `10` |
| Momentum-/CMO-Länge `M` | `20` |
| Nachglättung | SMA `15` |
| ATR-Variante | True Range + Wilder RMA |
| ATR-Länge `A` | `200` |
| Bandmultiplikator `K` | `2.0` |
| Warm-up vor erster handelbarer Auswertung | `400` geschlossene 1h-Bars |
| Signalauswertung | ausschließlich nach endgültigem Kerzenschluss |
| Positionierung | Spot, Long-only, höchstens eine Position je Symbol |
| Pyramiding | `0` |

UI-Zeiträume Heute/1W/1M/1J/3J ändern den Signaltimeframe nicht. Ein später anderer Signaltimeframe ist eine neue Strategie-/Konfigurationsversion und benötigt neue Backtests.

## Eingabekerzen

Je Symbol wird eine lückenlose, streng aufsteigend nach UTC sortierte Folge endgültig geschlossener Binance-1h-Kerzen verwendet:

```text
Candle[t] = (open_time_utc, open, high, low, close, volume, closed=true)
```

Duplikate, Lücken, nicht positive Preise, negative Volumina oder vorläufige Kerzen sperren die Auswertung des Symbols. Es werden keine synthetischen Kerzen interpoliert. Die Kerzenindizes sind nullbasiert und ohne Lücke; `[a..b]` schließt beide Grenzen ein.

## VIDYA-/CMO-Berechnung

Index `t = 0` bezeichnet die erste Warm-up-Kerze. Indikatorrechnungen verwenden IEEE-754 Binary64 ohne Zwischenrundung; Vergleiche arbeiten auf den ungerundeten Werten. Geld, Gebühren und Ordermengen verwenden Decimal und werden erst nach der Indikatorentscheidung gemäß Binance-Filtern gerundet.

### 1. Momentum

```text
momentum[t] = close[t] - close[t-1]       für t >= 1
positive[t] = max(momentum[t], 0)
negative[t] = max(-momentum[t], 0)
```

Für `t = 0` sind `positive[0] = 0` und `negative[0] = 0`.

### 2. Absoluter CMO-Faktor

Über die letzten höchstens `M = 20` Momentumwerte einschließlich `t`:

```text
lo[t]      = max(1, t - M + 1)
pos_sum[t] = Sum(positive[i], i = lo[t]..t)  für t >= 1; sonst 0
neg_sum[t] = Sum(negative[i], i = lo[t]..t)  für t >= 1; sonst 0
denom[t]   = pos_sum[t] + neg_sum[t]

wenn denom[t] = 0:
    abs_cmo[t] = 0
sonst:
    abs_cmo[t] = abs((pos_sum[t] - neg_sum[t]) / denom[t])
```

`abs_cmo` liegt im Bereich `[0, 1]`. Es wird nicht erneut durch 100 geteilt.

### 3. Adaptive VIDYA

```text
alpha = 2 / (L + 1) = 2 / 11
effective_alpha[t] = alpha * abs_cmo[t]

vidya_raw[0] = close[0]
vidya_raw[t] = effective_alpha[t] * close[t]
             + (1 - effective_alpha[t]) * vidya_raw[t-1]
```

### 4. Nachglättung

```text
vidya[t] = Sum(vidya_raw[i], i = t-14..t) / 15    für t >= 14
```

`vidya[t]` ist erst gültig, wenn 15 Rohwerte vorhanden sind.

## ATR-Berechnung

### 1. True Range

```text
TR[0] = high[0] - low[0]

TR[t] = max(
    high[t] - low[t],
    abs(high[t] - close[t-1]),
    abs(low[t]  - close[t-1])
) für t >= 1
```

### 2. Wilder RMA mit Länge 200

Der erste ATR-Wert ist der Mittelwert der ersten 200 True-Range-Werte:

```text
ATR[199] = SMA(TR[0..199])
ATR[t]   = ((ATR[t-1] * 199) + TR[t]) / 200    für t >= 200
```

Vor Index 199 ist ATR ungültig.

## Bänder

Sobald VIDYA und ATR gültig sind:

```text
upper[t] = vidya[t] + ATR[t] * 2.0
lower[t] = vidya[t] - ATR[t] * 2.0
```

Die aktuelle Kerze darf in `vidya[t]` und `ATR[t]` eingehen, aber erst nachdem sie von Binance als geschlossen bestätigt wurde.

## Warm-up und Startzustand

- Pro Symbol müssen mindestens 400 lückenlose geschlossene 1h-Kerzen vorliegen.
- Bars `0..398` erzeugen niemals Signale oder Orders.
- Nach Abschluss von Bar `399` wird der Trendzustand auf `DOWN` initialisiert.
- Die Initialisierung erzeugt kein Verkaufssignal und keine Order.
- Das erste handelbare Ereignis kann frühestens ein späterer bestätigter Wechsel von `DOWN` nach `UP` sein.

Der 400-Bar-Warm-up liegt bewusst über den mathematisch mindestens benötigten 200 ATR-Bars und reduziert Seed-Einflüsse. Ein anderer Warm-up ist eine Strategieänderung.

## Exakte Cross- und Trendregel

Auswertung beginnt für `t >= 400` nach Kerzenschluss:

```text
flip_up[t] = close[t] > upper[t]
          AND close[t-1] <= upper[t-1]

flip_down[t] = close[t] < lower[t]
            AND close[t-1] >= lower[t-1]
```

Zustandsübergänge:

```text
wenn flip_up[t]:
    trend[t] = UP
sonst wenn flip_down[t]:
    trend[t] = DOWN
sonst:
    trend[t] = trend[t-1]
```

Falls aufgrund ungültiger Daten beide Bedingungen nicht eindeutig auswertbar sind, wird kein Zustand fortgeschrieben; das Symbol wird pausiert. Bei gültigen Bändern können `flip_up` und `flip_down` auf derselben Kerze nicht gleichzeitig wahr sein.

## Signal- und Positionsabbildung

| Ereignis | Position vorher | Aktion |
|---|---|---|
| `flip_up` | flat | Kaufkandidat `ENTER_LONG` |
| `flip_up` | long | keine Order, als bereits positioniert protokollieren |
| `flip_down` | long | vollständiger Long-Exit `EXIT_LONG` |
| `flip_down` | flat | keine Order |
| kein Flip | beliebig | keine Order |

Ein Verkaufssignal eröffnet niemals eine Short-Position. Es gibt keinen Stop-Loss, Take-Profit, Trailing Stop, DCA oder zusätzliches Entry-Signal in V1.

## Drei-Slot-Priorisierung für Paper/Live

Wenn mehr Kaufkandidaten als freie Slots auf derselben Kerzenzeit existieren, wird je Kandidat berechnet:

```text
breakout_strength[t] = (close[t] - upper[t]) / ATR[t]
```

Nur Werte größer als `0` sind zulässig. Sortierung:

1. Für das Ranking wird `breakout_strength` auf 12 Dezimalstellen mit Round-Half-Even gerundet; dieser `rank_strength` wird absteigend sortiert.
2. Bei gleichem `rank_strength` gilt diese feste Reihenfolge:
   `BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, ADAUSDT, LINKUSDT, AVAXUSDT, DOTUSDT, DOGEUSDT`.

Die aktive V6 vergibt höchstens einen Slot an jeden Kandidaten. Es werden nur so viele Kandidaten angenommen, wie freie Slots vorhanden sind. Abgewiesene Kandidaten werden als `NO_FREE_SLOT` gespeichert und nicht mitten im laufenden Uptrend nachgeholt.

V3 testete zusätzlich: jeder gleichzeitige Kandidat erhält zunächst einen Slot; verbleibende Slots gehen an den stärksten Kandidaten. Damit ergaben ein Kandidat `3×80` und zwei Kandidaten `2×80 + 1×80`. Diese Konzentration erhöhte nicht die Zahl unabhängiger Signale und führte bereits im ersten aktuellen Dreijahres-Risikospiegel zu einem frühen Halt. Sie bleibt deshalb in `backtests/v3` dokumentiert, aber in Paper gesperrt.

## Zeitpunkt von Signal und Fill

- Signalzeit ist die UTC-Close-Time der Signalkerze.
- Backtestorder wird frühestens am Open der folgenden 1h-Kerze gefüllt.
- Paper-/Live-Intent entsteht erst nach finalem Binance-Bar-Close.
- Historisch nachgeladene Signale werden nicht als verspätete Live-Orders gesendet.
- Gebühren, Spread, Slippage und Binance-Rundung werden nach Dokument 06 angewendet.

## Kein Repainting – Definition

V1 gilt als nicht repaintend, wenn:

- ausschließlich endgültig geschlossene Bars ausgewertet werden;
- kein zukünftiger Index verwendet wird;
- Batchberechnung und chronologisches Bar-für-Bar-Replay exakt dieselben Signal-IDs liefern;
- ein bereits gespeichertes Signal durch spätere Bars nicht geändert wird;
- Providerrevisionen eine neue Datenversion erzeugen, statt alte Resultate still zu überschreiben.

## Verbindliche Testvektoren

Vor Botcode-Freigabe werden handgerechnete Mini-Fixtures und später mindestens 1.000 aufeinanderfolgende 1h-Bars je Referenzmarkt geprüft. Pflichtfelder je Bar: OHLCV, `abs_cmo`, `vidya_raw`, `vidya`, `TR`, `ATR`, `upper`, `lower`, Trend, `flip_up`, `flip_down` und ggf. `breakout_strength`.

Für Golden-Tests gilt je numerischem Indikatorwert: bestanden, wenn absolute Abweichung höchstens `1e-10` **oder** relative Abweichung höchstens `1e-9` beträgt. Cross-Vergleiche verwenden trotzdem ungerundete Produktionswerte; Signal-, Trend- und Slotentscheidungen dürfen keine Abweichung haben.

## Versionsregel

Änderungen an Formel, Seed, Parameter, Timeframe, Warm-up, Cross, Positionsabbildung oder Slotranking erzeugen mindestens `HIXTON-SPEC-2.0` und `backtests/v2`. V1-Ergebnisse werden nicht überschrieben.

## Pine-v6-Semantik und V2-Kandidat

Die V2-Engine bildet die Eigentümerquelle ausdrücklich ab:

- `math.sum` wird erst bei vollständigem Momentumfenster gültig;
- das lokale persistente `var float v` startet mit `na` und folgt der Pine-Historiensemantik;
- die Nachglättung entspricht `ta.sma` mit der jeweils versionierten Länge;
- ATR entspricht `ta.atr`, also True Range mit Wilder-RMA;
- `trendUp` startet als `false` und wird über bestätigte Crosses fortgeschrieben;
- `flipUp`/`flipDn` sind tatsächliche Wechsel des Trendzustands, nicht beliebig wiederholte Bandkreuzungen im selben Zustand;
- Orders bleiben trotz Pine-Berechnung erst nach 400 lückenlosen Warm-up-Bars handelbar und werden im Backtest frühestens am nächsten Bar-Open gefüllt.

Mit den Pine-Defaultparametern 10/20/SMA15/ATR200/Band2,0 ergab der aktuelle Drei-Jahres-Produktionslauf dieselben Trades und dieselbe Performance wie V1. Die Pine-Startsemantik erklärt die schwachen V1-Coins deshalb nicht. Die vorherige Paper-V2 6/20/SMA8/ATR60/Band3,8 reduziert kurze Fehlausbrüche durch deutlich weitere Bänder. Auswahl, Ergebnisse, ältere Segmente und verworfene Varianten stehen in `backtests/v2/README.md`.

Der Eigentümer hat den kontrollierten Paperwechsel am 02.09.2026 ausdrücklich angeordnet. Die Umschaltung schließt vorhandene V1-Paperpositionen zum aktuellen geschlossenen Referenzpreis nach Baselinekosten, bewahrt sämtliche Ereignisse mit ihrer Strategieversion, setzt Checkpoints auf den letzten geschlossenen Bar und startet den V2-Soak neu. Dieser Paperentscheid ersetzt weder den vorgeschriebenen Soak noch das separate Live-Gate.
