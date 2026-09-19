# V9 – Portfolio zuerst: Einstiegsfilter und Ausstiege

> **HISTORIEN-/FORSCHUNGSGRENZE.** Diese Datei bewahrt den damaligen Prüfstand und seine Ergebnisse. Enthaltene USDT-, `one_per_symbol`- oder permanente 20-%-Portfoliohalt-Aussagen sind historische Evidenz, sofern sie nicht ausdrücklich als aktueller V6-Vertrag gekennzeichnet sind. Maßgeblich für den heutigen Betrieb sind `README.md`, DMS 02/04/06 und `agent_memory/swarm/taskboard.json`: ein kanonisches USDC-Zehn-Coin-System, gemeinsames 250-USDC-Hauptportfolio mit Baseline 3×80 `ranked_repeat`, kein permanenter Portfolio-Drawdown-Halt und 10×250 nur zur Coin-für-Coin-Diagnose/Optimierung. Historische Gegenbelege werden nicht gelöscht oder umgeschrieben.


Auftrag 15.09.2026: das gemeinsame 250-USDC-/3×80-System verbessern, nicht
isolierte Gewinner zu einer vermeintlichen Portfolio-Rendite addieren.
Auftragsbezogene Ausnahme von der offenen AGENTS-Lernphase; kein Echtgeldstart.
V9 ist Forschung, keine aktivierte Strategieversion.

## Ergebnis 15.09.2026: kein freigegebener Kandidat

28 Portfolio- und 80 Einzelrechnungen abgeschlossen. Die ausschließlich auf
Trainingsdaten festgelegte Auswahl ist `trail4`. Keine nachträgliche Umwahl.

| Portfolio | V6 Ende | Trailing4 Ende | Trades V6 → Trailing4 |
| --- | ---: | ---: | ---: |
| Gesamt / Baseline | 203,72 | 265,59 USDC | 14 → 123 |
| Gesamt / Stress | 203,33 | 218,45 USDC | 11 → 45 |
| Späterer Neustart / Baseline | 220,72 | 208,99 USDC | 15 → 33 |
| Späterer Neustart / Stress | 215,06 | 203,54 USDC | 15 → 31 |

Gesamtfenster 24.03.2024–15.09.2026 06:00 UTC; späterer Neustart ab 01.09.2025.
Alle vier Trailing-Portfolios erreichen den Risikohalt. Gesamt-Baseline-DD
23,66 %, Halt 21.02.2025; Stress-DD 20,16 %, Halt bereits 08.07.2024.
Mehr Trades und ein positiver Gesamt-Baseline-Endwert genügen nicht: unter
Stress und im späteren Neustart verliert der Kandidat weiterhin Kapital.

Isolierte Gesamt-Baselines (je 250): BTC 194,39; ETH 272,59; BNB 216,69;
SOL 376,74; XRP 280,22; ADA 194,77; LINK 365,62; AVAX 286,07; DOT 230,62;
DOGE 269,02 USDC. Der universelle Trailing-Ausgang verschlechtert beispielsweise
BTC, ADA und SOL gegenüber dem bisherigen Coinprofil deutlich. Deshalb nicht
global im Paperbetrieb aktivieren und nicht einzelne Werte nachträglich picken.

Zusätzliche, **nach der Auswahl deklarierte Risikosensitivität**, kein Bestandteil
des ursprünglichen Auswahlverfahrens: Trailing4 ohne sämtliche Kontorisikogates
ergibt insgesamt 262,03 USDC / 313 Abschlüsse / 35,61 % DD; unter Stress
165,18 / 290 / 52,19 %. Im späteren Neustart 206,86 Baseline bzw. 165,92 Stress.
Die These „tieferen Rückgang abwarten, dann wieder 700“ bestätigt sich hier nicht.
Produktive Schutzgrenzen wurden weder ausgeschaltet noch verändert.

Vollständige Nachweise: [Hauptstudie](reports/portfolio-first-20260915.json),
[separate Risikodiagnose](reports/risk-sensitivity-20260915.json).
Während der ersten Hauptrechnung wurden ausschließlich Typisierung der
Parameterübergabe und Zeilenumbruch der Fortschrittsausgabe bereinigt; der
Bericht behält den bei seinem Start gelesenen Quellhash. Kandidaten und
Rechenregeln blieben identisch. 335 Python-Tests bestanden, ein optionaler Skip;
Ruff und mypy (55 Quelldateien) bestanden. Keine neue profitable Strategie
nachgewiesen, keine Autoaktivierung, keine Echtgeldfreigabe.

## Vorab festgelegter Plan

Zehn Varianten: unverändert; CMO mindestens 0,2; VIDYA-Steigung über 24 bzw.
72 Stunden; Stop 2 bzw. 4 ATR; Trailing 4 ATR; CMO+Stop2; Steigung24+Stop2;
Steigung24+Trailing4. Vorhandene stärkere Einstiegsfilter bleiben erhalten.
Die individuellen Hixton-Parameter aller zehn Coins bleiben unverändert.
Stops/Trailing wirken am Kerzenschluss mit Ausführung am nächsten Open, nicht
als garantiert ausführbare Intrabar-Stoporders. Kontorisikoschutz bleibt aktiv.

Portfolio-Auswahl ausschließlich nach zwei Trainingsfenstern unter Stress:
gemeinsamer Datenbeginn bis 01.01.2025 sowie 01.01.–01.09.2025. Rangfolge:
höchste schlechteste Fensterrendite, dann Summe, bei Gleichstand Referenz.
Die Auswahl wird vor der nachfolgenden Validierung gespeichert. Auch der beste
Trainingskandidat darf negativ sein: Auswahl ist noch keine Freigabe.

Danach nur den ausgewählten Kandidaten und die Referenz auf Gesamtfenster und
01.09.2025–15.09.2026 prüfen, jeweils Baseline/Stress. Portfolio-Gate: positive
Rendite, kein Risikohalt, nicht schlechter als Referenz und höchstens zwei
Prozentpunkte mehr Drawdown. Danach alle zehn Coins für beide Profile einzeln
mit je 250 USDC über dieselben Fenster/Kosten diagnostizieren. Keine Nachwahl
aus dem Katalog aufgrund des späteren Ergebnisses, keine Autoaktivierung.

Diese Daten wurden in früheren Studien bereits betrachtet: **kein unberührter
Holdout**, kein Nachweis künftiger Rendite. Drei volle Jahre echte gemeinsame
USDC-Historie fehlen; tatsächlicher Start ist 24.03.2024. Aktuelle Börsenfilter
sind keine historischen Point-in-Time-Filter. Ziel 733 USDC ist kein Bestehens-
oder Abbruchkriterium, das nachträgliche Auswahl schöner Ergebnisse rechtfertigt.

## Reproduzieren

Einziger bestehender Einstieg, Datenbank nur lesend:

```powershell
py -3 src/main.py backtest research --study v9 --end 2026-09-15T06:00:00Z --output backtests/v9/runs/portfolio-first-20260915
```

Ein neuer Lauf benötigt einen neuen Ausgabepfad, um Beweise nicht zu überschreiben.
Der Bericht enthält Plan, Parameter, Kerzen-/Codehashes, Kosten, Auswahl und alle
getesteten Portfolio- sowie Einzelresultate. Forschung verwendet dieselben
Handelsengines wie normale Tests; kein separates profitgeschöntes Rechenmodell.
