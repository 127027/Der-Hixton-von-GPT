# HIXTON V3 – Mehrfachslot-Versuch verworfen

Status: `REJECTED`, weder Paper noch Live. V3 verändert keine Hixton-Signalparameter gegenüber V2. Untersucht wurde ausschließlich der Eigentümerwunsch, bei wenigen gleichzeitigen Kaufsignalen mehrere der drei 80-USDT-Slots demselben Coin zu geben.

## Deterministische Regel

`ranked_repeat` verteilt zuerst je einen Slot an jeden gleichzeitig vorhandenen Kandidaten in der V2-Ausbruchsrangfolge. Bleiben Slots frei, gehen alle an den stärksten Kandidaten. Damit gilt bei drei freien Slots:

- ein Kandidat: `3×80` auf diesen Coin;
- zwei Kandidaten: `2×80` auf Rang 1 und `1×80` auf Rang 2;
- mindestens drei Kandidaten: je `1×80` auf die ersten drei.

Mehrere Slots auf demselben Signal werden als eine aggregierte Position mit entsprechendem Notional gerechnet. Das sind keine unabhängigen Trades.

## Disqualifizierender aktueller Dreijahreslauf

- Run-ID: `76a78440-405a-4624-bc0b-7765558b801c`
- Fenster: `[2023-09-01 12:00 UTC, 2026-09-01 12:00 UTC)` plus 400 Warm-up-Bars
- Kapital/Risiko: 240 USDT, drei Slots à 80 USDT, kein Compounding, 5-%-Tagespause, 20-%-Drawdown-Halt
- Signale: V2 mit 1h, 6/20/SMA8/ATR60/Band3,8

| Szenario | Ende | Rendite | abgeschlossene Positionen | Max-DD | Risikohalt |
|---|---:|---:|---:|---:|---|
| Baseline | 287,85 USDT | +19,94 % | 4 | 23,79 % | 12.10.2023 01:59:59,999 UTC |
| Stress | 282,16 USDT | +17,57 % | 4 | 23,78 % | 12.10.2023 01:59:59,999 UTC |

Aktive V2 `one_per_symbol` erreichte im identischen Fenster 542,49 beziehungsweise 406,29 USDT und hielt wesentlich später. V3 bündelte das Risiko eines einzigen Signals, verlor früh die Handlungsfähigkeit und verbesserte weder die unabhängige Tradezahl noch die Nettoperformance. Damit war die Variante bereits am ersten Gate eindeutig unterlegen; weitere Altfenster- oder Nachbarrechnungen wurden bewusst nicht als Rechenzeitverschwendung ausgeführt.

## Entscheidung

V3 bleibt als kleiner kuratierter Negativnachweis erhalten. Große Runs bleiben wie alle automatisch reproduzierbaren Runartefakte lokal ignoriert. Eine spätere andere Mehrfachslotlogik benötigt eine neue Version und muss V2 im vollständigen Baseline-/Stress-/Altfenster-/Risikoprogramm übertreffen. Risikogrenzen dürfen dafür nicht gelockert werden.
