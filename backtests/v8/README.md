# V8 – begrenzte Schwachstellenprüfung (nur Forschung)

Owner-Freigabe vom 14.09.2026: getrennte Optimierungsversuche trotz noch offener
AGENTS-Lernphase. Kein Wechsel laufender Paperpositionen, kein Echtgeldauftrag.
`bootstrap_complete` bleibt falsch. V8 ist eine Studie, keine aktive Botversion.

Zusätzlicher [USDT-/USDC-Kontrollbericht vom 15.09.2026](reports/quote-migration-audit-20260915.json):
alter USDT-Lauf mit aktuellem Code exakt reproduziert (733,31 Portfolio,
7.152,29 Batch). Bei gleichem späteren Start: USDT 201,11 / 4.118,70,
USDC 203,62 / 4.007,26. Methodik und Grenzen in DMS18; kein Strategiepatch.

## Ergebnis vom 14.09.2026

**Keine Übernahme.** 18 Profilkombinationen einschließlich dreier Referenzen,
88 exakte Einzelrechnungen und 8 gemeinsame Portfoliorechnungen abgeschlossen.
Die Trainingsauswahl ergab bei allen drei Coins `stop4`; danach keine Nachwahl.
Gesamtfenster: **24.03.2024 00:00 bis 14.09.2026 13:00 UTC, Ende exklusiv**.
Start jeweils 250 USDC. Keine drei vollständigen Jahre verfügbar.

| Coin | Bisher Ende | Stop4 Ende | Trades bisher → Stop4 | Max. DD bisher → Stop4 |
| --- | ---: | ---: | ---: | ---: |
| DOT | 165,32 | 222,01 | 50 → 50 | 74,17 % → 68,60 % |
| AVAX | 182,09 | 361,15 | 36 → 36 | 54,10 % → 38,94 % |
| BNB | 264,91 | 264,70 | 37 → 37 | 44,62 % → 37,52 % |

Baseline nach Kosten, offene Endpositionen bewertet. Der Verbesserung bei AVAX
steht ein negativer separater Validierungsneustart ab 01.09.2025 gegenüber:
146,32 → 159,60 USDC. DOT dort 121,01 → 153,10; BNB 243,58 → 208,32.
Unter Stress ebenfalls kein bestandener Validierungskandidat: DOT 140,17,
AVAX 148,16, BNB 175,54 USDC aus jeweils 250. Daher alle drei Einzel-Gates falsch.

| Gemeinsames 3×80-Fenster | Bisher Ende | Trainingsauswahl Ende | Trades | Max. DD bisher → Auswahl |
| --- | ---: | ---: | ---: | ---: |
| Gesamt, Baseline | 203,71 | 203,71 | 14 → 14 | 20,83 % → 20,83 % |
| Gesamt, Stress | 203,32 | 203,32 | 11 → 11 | 20,37 % → 20,37 % |
| Validierung, Baseline | 220,72 | 217,16 | 15 → 16 | 20,28 % → 20,60 % |
| Validierung, Stress | 215,06 | 212,34 | 15 → 16 | 21,88 % → 22,18 % |

Alle acht Portfolioausführungen enden im Risikohalt. Im Gesamtfenster bleibt
der Baseline-Halt am 01.05.2024 19:59:59,999 UTC unverändert, unter Stress am
30.04.2024 12:59:59,999. Ein Patch muss also nicht zwingend den Portfoliogewinn
ändern. Die neuen Regeln haben hier keinen gemessenen Vorteil vor diesem Halt.
Im Validierungsportfolio führt ein zusätzlicher Trade sogar zu weniger Kapital.

Engere Bänder erhöhen z. B. bei DOT die Abschlüsse in den zwei Trainingsfenstern
von 15/12 auf 24/21, senken aber die Stress-Endwerte von 347,04/163,42 auf
241,99/158,41 USDC. Mehr Trades allein ist damit ausdrücklich kein Erfolg.
Stop4 senkt die durchschnittliche Haltedauer im Gesamtfenster bei DOT von
203,80 auf 134,46 Stunden, AVAX von 249,36 auf 163,61 und BNB von 276,24 auf
199,38, ohne in diesen Einzeltests die Gesamtzahl der Abschlüsse zu erhöhen.

Alle zehn bestehenden Profile wurden zusätzlich über Gesamt- und
Validierungsfenster mit beiden Kostenmodellen gerechnet. Die Gesamt-Baselines
stimmen mit den vorherigen frischen V6-Läufen überein. Auffällig im späteren
Validierungsneustart ist außerdem ADA (116,84 Baseline / 104,42 Stress), obwohl
sein Gesamtfenster positiv aussieht. Eine spätere eigene Studie sollte deshalb
Verlustregime und Einstiegsqualität untersuchen; kein nachträgliches Weiterdrehen
dieses bereits ausgewerteten Prüfplans und kein Abschalten des Risikoschutzes.

Maschinenlesbarer vollständiger Nachweis inklusive aller verworfenen
Trainingsvarianten: [Bericht](reports/weak-coin-review-20260914.json).
Python-Quelltext-Hash: `e360a5f9f607ceae063f640e85784214aca39f584561ca7bec9ffcf91d25e5d2`.
Abnahme: 304 Python-Tests bestanden, 1 optionaler Test übersprungen; Ruff und
mypy (53 Quelldateien) erfolgreich. UI unverändert, daher kein neuer UI-Build.
Paper weiterhin V6, 3×80 USDC; kein Neustart, Kontoreset oder Echtgeldauftrag.

## Fester Prüfplan

Nur DOT, AVAX und BNB: bestehendes Profil, Bandabstand minus 0,6, Stop 4 ATR,
Trailing 6 ATR sowie engeres Band mit jeweils einem dieser Ausstiege (6 Varianten).
Hixton-Formel, Stundenkerzen, Next-Bar-Open, 400 Warm-up-Bars und die sieben
anderen Coinprofile bleiben unverändert. Stop/Trailing verwenden die vorhandene
Bar-Close-Logik; sie garantieren keinen intrabar ausführbaren Stoppreis.

Training: verfügbarer gemeinsamer Beginn bis 01.01.2025, danach bis 01.09.2025.
Auswahl nur aus diesen zwei Fenstern unter Stresskosten: mindestens 5 Abschlüsse
pro Fenster, Drawdown höchstens 2 Prozentpunkte schlechter als die Referenz,
Summe der Trades und Nettoergebnisse nicht schlechter. Rangfolge: höchste
schlechteste Fensterrendite, dann Nettogewinn, Tradezahl, Name. Sonst Referenz.
Danach wird die Auswahl gespeichert und nicht anhand der Validierung ersetzt.

Validierung: 01.09.2025 bis festgeschriebenes Ende; zusätzlich Gesamtfenster.
In beiden Fenstern und beiden Kostenmodellen: positiver Nettogewinn, Endkapital
und Tradeanzahl mindestens Referenz, Drawdown höchstens 2 Prozentpunkte höher.
Der gemeinsame 250-USDC-Start / 3×80-Test muss diese Bedingungen ebenfalls
erfüllen und darf nicht im Risikohalt enden. Schutzgrenzen bleiben unverändert.
Die gemeinsame Trainingsauswahl wird auch bei Einzelablehnung nur diagnostisch
getestet. Besteht sie nicht, erfolgt keine Übernahme und keine Nachwahl anhand
bereits gelesener Validierungsergebnisse.

## Ausführen / Herkunft

Ein bestehender Einstieg, kein zusätzlicher Starter:

```powershell
py -3 src/main.py backtest research --study v8 --end 2026-09-14T13:00:00Z --output backtests/v8/runs/review-20260914
```

Die Datenbank wird read-only in einer konsistenten SQLite-Lesetransaktion gelesen.
Keine Downloads, Kontozurücksetzungen, Aktivierungen oder Binance-Orders.
Manifest vor Berechnungsbeginn, danach eingefrorene Trainingsauswahl und Ergebnis.
Bericht enthält Quellcode-, Candle-Hashes, Parameter, Kosten und Börsenfilter.
Es rechnen dieselben Decimal-Einzel-/Portfolioengines wie die normalen Backtests.

Das gemeinsame echte USDC-Fenster ist kürzer als drei Jahre. Frühere Sichtung
dieser Historie und bisherige Profilwahl bedeuten: **kein unberührter Holdout**.
Gespeicherte aktuelle Börsenfilter sind keine historischen Point-in-Time-Filter.
Auch ein bestandener Forschungsvergleich wäre keine Echtgeldausführungsfreigabe.
Jeder Logik-/Parameterpatch braucht einen neuen Vergleich; nicht jeder Patch
muss numerisch andere Renditen erzeugen. Alte Berichte bleiben historische Belege.
