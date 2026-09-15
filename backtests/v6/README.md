# Backtest V6 – eingefrorene Coin-Profile

Stand: 06.09.2026. **Aktives Paper-Experiment gemäß DEC-045. Keine Robustheits-/Livefreigabe. V2 bleibt Vergleichsreferenz.**

## Zweck und faire Einordnung

Das Ziel ist effizientes 3×80-Papertrading mit guten Signalen aus zehn Coins. Einzeltests à 250 USDT prüfen jede Signalquelle, der zusätzliche gemeinsame Test prüft Kapital, Konkurrenz und Risikogates. Rendite- und Tradezahlen aus Eigentümerbeispielen sind keine Quoten. Neue gemeinsame Vergleichskonten starten mit 250 USDT einschließlich 10 USDT Anfangsreserve; das frühere 240-USDT-Ledger wird beim ausdrücklich beauftragten Neuanfang nach DEC-045 vollständig archiviert, nicht als Gewinn im neuen Konto verbucht.

V6 verbessert den gemeinsamen Dreijahres-Endwert gegenüber V2, verschlechtert jedoch das jüngste und das ältere Fenster. Deshalb **keine automatische Übernahme** und kein Nachweis „alle zehn robust / optimal“. Genau diesen gesonderten Paper-Versuch hat der Eigentümer anschließend mit DEC-045 ausdrücklich beauftragt; dadurch werden die Rückschritte nicht behoben. Es gibt keine Gewinnerwartung pro Tag. Mehr Tradezahl ist kein Ersatz für Qualität.

## Vor der Messung eingefrorene Auswahl

Je Coin genau zwei bereits vermessene Optionen: bisherige V2 oder V5-Finalist. Auswahl: höchster minimaler Stress-Endwert über volles, jüngstes und älteres Fenster; Gleichstand: mehr abgeschlossene Trades im vollen Stressfenster, dann V2. Keine neue breite Parametersuche, keine Umwahl nach dem Portfolioergebnis.

**Alle drei Fenster beeinflussen diese nachträgliche Auswahl. Das ist retrospektive Kalibrierung, kein unabhängiger Holdout und kein Out-of-sample-Erfolg.** V5 hatte seine Finalisten ausschließlich im Training bestimmt; V6 ist ein neuer Versuch und ändert die V5-Historie nicht. Sieben Coins übernehmen den Finalisten; ADA, LINK und DOT behalten V2, weil deren schwächster Stress-Endwert besser bleibt.

Profilquelle: `candidate.json`, Version `HIXTON-V6-COIN-PAPER-1-9734f240e873`. Einzige produktive Definition: `src/hixton/domain/versions.py`; Configvalidierung verhindert abweichende Parameter unter derselben Version.

## Alle zehn Einzeltests

Parameterfolge: VIDYA / Momentum / SMA / ATR / Band. Gemeinsame Pine-v6-Formel, Schlusskursquelle, 1h und 400 Warm-up-Bars. Endwerte enthalten offene Bewertung und Dust; sie sind nicht vollständig realisierter Gewinn. Start je Test 250 USDT.

| Coin | Parameter | Zusatzregel | 3 Jahre Baseline, USDT | geschlossene Trades | jüngstes Jahr Stress, USDT | älteres Fenster Stress, USDT |
|---|---|---|---:|---:|---:|---:|
| BTC | 6/20/8/120/4.4 | CMO ≥ 0,2 | 559,73 | 44 | 206,64 | 370,91 |
| ETH | 6/20/8/60/3.8 | VIDYA-Steigung 24 Bars | 729,87 | 36 | 278,47 | 263,91 |
| BNB | 10/20/8/60/4.4 | keine | 418,31 | 41 | 210,90 | 190,30 |
| SOL | 6/20/15/60/3.8 | keine | 1.540,35 | 57 | 192,86 | 116,79 |
| XRP | 6/20/8/120/3.2 | Schlusskurs-Stop 4 Entry-ATR | 594,89 | 80 | 240,32 | 134,12 |
| ADA | 6/20/8/60/3.8 | keine | 678,79 | 55 | 114,86 | 186,94 |
| LINK | 6/20/8/60/3.8 | keine | 612,46 | 49 | 195,53 | 158,48 |
| AVAX | 6/20/8/60/4.4 | keine | 711,74 | 38 | 120,44 | 210,02 |
| DOT | 6/20/8/60/3.8 | keine | 447,99 | 44 | 145,47 | 194,28 |
| DOGE | 6/20/15/120/4.4 | CMO ≥ 0,2 | 858,16 | 46 | 190,34 | 208,66 |

Alle zehn sind im vollen Baselinefenster positiv. Acht überschreiten das illustrative 500-USDT-Beispiel. **Neun verlieren aber im separat gestarteten jüngsten Stressjahr; nur ETH endet über 250.** Damit ist die geforderte robuste Eignung aller zehn noch nicht nachgewiesen. Einzelgewinne dürfen nicht zu einem angeblichen gemeinsamen 3×80-Gewinn aufsummiert werden.

## Gemeinsames Konto – identische 250 USDT für beide Versionen

Unverändert: drei feste 80-USDT-Slots, höchstens ein Slot pro Coin, stärkster normalisierter frischer Ausbruch zuerst, keine Wiederholung eines dauergrünen Trends, kein Compounding, 5-%-Tagesverlustpause und 20-%-Drawdown-Halt. Ein ausgelöster Halt sperrt neue Entries; verbleibende Positionen können danach noch geschlossen werden. Der gemessene Drawdown kann deshalb 20 % überschreiten. Startreserve ist ein Puffer, keine gegen Verluste geschützte Einlage.

| Fenster | Profil / Kosten | Endkapital USDT | geschlossene Trades | max. Drawdown | erster Risikohalt UTC |
|---|---|---:|---:|---:|---|
| full | v2_baseline | 553,29 | 108 | 22,42 % | 2025-02-06 |
| full | v2_stress | 433,49 | 71 | 20,34 % | 2024-09-08 |
| full | v6_baseline | 733,31 | 187 | 20,46 % | 2026-02-25 |
| full | v6_stress | 564,82 | 25 | 20,59 % | 2024-01-24 |
| recent | v2_baseline | 226,71 | 17 | 22,85 % | 2025-11-16 |
| recent | v2_stress | 220,03 | 17 | 24,67 % | 2025-11-13 |
| recent | v6_baseline | 216,84 | 13 | 21,31 % | 2025-10-22 |
| recent | v6_stress | 211,83 | 13 | 22,96 % | 2025-10-21 |
| older | v2_baseline | 232,99 | 12 | 24,48 % | 2021-12-09 |
| older | v2_stress | 233,21 | 11 | 21,32 % | 2021-12-04 |
| older | v6_baseline | 222,42 | 12 | 22,74 % | 2021-12-05 |
| older | v6_stress | 225,40 | 11 | 21,25 % | 2021-12-03 |

Alle zwölf gemeinsamen Läufe halten vorzeitig. Der Dreijahres-Endwert ist **kein** dreijähriger ununterbrochener Handels-/Profitabilitätsnachweis. V2-Vergleichswerte unterscheiden sich von den alten 240-USDT-Berichten wegen des jetzt gleichen 250-USDT-Starts; alte Artefakte werden nicht überschrieben.

Fenster, jeweils `[Start, Ende)` UTC:

- full: 01.09.2023 12:00 bis 01.09.2026 12:00.
- recent: frisch gestartetes Konto 01.09.2025 12:00 bis 01.09.2026 12:00; Indikatorhistorie beginnt wie bei full.
- older: 16.10.2021 01:00 bis 24.03.2023 13:00 mit 400 vorhergehenden Stunden Warm-up.

Baseline pro Seite: 10 bp Gebühr + 2 bp Spread + 3 bp Slippage. Stress: 10 + 10 + 20 bp. Stress ist ungünstigere Ausführung, **kein intensiverer Handelsmodus**. Kein ungeprüfter BNB-Rabatt. Mengen werden mit gespeicherten Binance-Filtern gerundet.

## Regeln, Parität und Grenzen

CMO/Steigung filtern nur frische BUY-Flips; abgelehnte Einstiege werden nicht später nachgeholt. XRP-Stop: `close <= entry_fill_price - 4 * entry_ATR`, mit dauerhaft gespeichertem Entry-ATR. Hixton-SELL hat Vorrang. Nur geschlossene Bars, tatsächliches Folge-Open plus Kosten; weder Docht-Stop noch garantierter Stoppreis. Ein Stop erzeugt keinen neuen BUY im unveränderten grünen Trend.

`tests/test_coin_profiles.py` belegt strikte vollständige Profile, Paper-/Portfolio-Fill- und Equity-Parität über Neustarts, Batch/Einzel/Charts, gespeicherten XRP-Stop trotz ATR-Änderung und Kurslücke, Cash-/Dust-/Risikohalt-Erhaltung bei ausdrücklich genehmigter Testmigration, Seedreserve ohne Kontogeschenk und technische Aktivierungssperre des nicht freigegebenen Kandidaten. Tests dürfen die Freigabe lokal simulieren; das erteilt keine Produktionsfreigabe.

Charts zeigen hypothetische qualifizierte Coin-Signale separat von tatsächlichen Paper-Fills. Die Portfolioverfügbarkeit kann einen Einstieg blockieren. Keine Erweiterung der ursprünglichen Pine-Quelle; Zusatzregeln und Parameter werden explizit als V6 gekennzeichnet.

## Artefakte und Wiederholung

```powershell
py -3 src/main.py backtest research --study v6 --output backtests/v6/runs/EIN_NEUER_NAME/research.json
py -3 src/main.py backtest all --strategy v6 --end 2026-09-01T12:00:00Z
py -3 src/main.py backtest portfolio --strategy v6 --end 2026-09-01T12:00:00Z
```

Alle Befehle laufen über den vorhandenen technischen Einstieg; einziger menschlicher Starter bleibt `Startbot.bat`. Ein Backtest schaltet Paper niemals um.

Kuratierter Nachweis: `reports/profile-review-20260906.json` mit allen Einzel-/Portfoliowerten, Daten-/Quellhashes, Kosten und Regeln. Der große Rohbericht bleibt lokal unter `runs/profile-review-20260906/research.json`; SHA-256 `50546F0A3458A33DF2D2A23FE509D3313A86C1249813759001F10DF76682AE6A`. Er enthält zusätzliche Verlustdiagnosen. Quellhashes dokumentieren den tatsächlich zu Beginn der Messung vorliegenden Arbeitsstand, nicht einen vorgetäuschten späteren Commit.

## Nächster fachlicher Schritt

Historische Abnahme vor DEC-045: 98 Tests auf Arbeitskopie und Laptop; Anwendung 0.3.0 / Code `f633f389ae9e74480ab024d0934d90b5e53c1ea7`. Geprüftes Backup, Neustart über Startbot.bat, 50 Chart-API-Kombinationen und sichtbare UI-Abnahme stehen in DMS 18. V2 bleibt aktiv; keine Positionsschließung, Kontoauffüllung oder Soak-Neustart.

Vollständig zugeordnete Produktionsruns: Batch `20bc2a48-cc79-4761-9e49-8ca5fffde150`, Portfolio `95c0ca16-7385-4b57-9dd1-2cc1dc3ed047`. `metrics.json`, `trades.csv` und `equity.csv` sind jeweils bytegleich zu den ersten Reproduktionen; Details unter `verified_reproduction` im kuratierten JSON. Die ersten Runs `e85192ad…`/`56a34f10…` behalten ihr unvollständiges `code_commit: UNKNOWN` und sind keine vollständigen Herkunftsnachweise. Für die Wiederholung war nur eine pro Prozess auf den verifizierten Projektpfad begrenzte Git-Verzeichnisfreigabe nötig, keine globale Wildcard-Freigabe.

Schwäche ist die gemeinsame Verlustphase und die Konzentration auf wenige lange Gewinner, nicht ein fehlender Schalter „mehr handeln“. Erst eine vorab definierte, begrenzte Portfoliohypothese mit stabilen Nachbarn, ehrlichen Kosten und neuen Vorwärtsdaten prüfen. Keine Optimierung bis alle historischen Coins grün erscheinen. V6 ist ein reproduzierbarer Vergleich, nicht das automatisch bessere Betriebsmodell.
