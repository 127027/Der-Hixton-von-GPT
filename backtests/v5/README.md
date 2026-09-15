# Backtest V5 – Einzelcoin-Schwächen und Hixton-Schutzregeln

Status: **FORSCHUNG ABGESCHLOSSEN / NICHT AKTIVIEREN**, keine Paper-/Live-Freigabe. Versuchskatalog vor dem ersten Lauf am 05.09.2026 festgelegt. Ein gemeinsames Forschungsmodul, keine zehn Engines oder zusätzlichen Starter. Die bereitgestellte Pine-v6-Datei bleibt unverändert. 348 Kandidaten insgesamt; sämtliche zehn Coins ausgewertet.

Ergebnis vorweg: ETH und XRP liefern interessante Einzelansätze, aber weder das vollständige Kandidatenportfolio noch die isolierte XRP-Änderung verbessert alle Portfolio-Prüffenster. V2 bleibt aktiv. Es wäre falsch, aus dem neuen Dreijahresendwert von 808,30 USDT eine zuverlässige tägliche Profitabilität abzuleiten.

## Festgelegter Versuch

- Zehn DMS-Märkte, Binance Spot, 1h, je 400 Warm-up-Bars. Isoliert 250 USDT, maximale Folgeposition weiterhin 250 USDT, kein Compounding. Gewinne bleiben als Cash, Verluste reduzieren verfügbares Kapital.
- Drei Parameterbasen: aktive V2, Original-Pine (10/20/15/200/2), je Coin ausschließlich aus den ersten zwei Jahren gewählte V4-Parameter. Identische Basen werden dedupliziert.
- Je Basis zwölf Regeln: unverändert; absoluter CMO mindestens 0,2; positive geglättete VIDYA-Steigung über 24 oder 72 Bars; Verluststopp bei 4 oder 6 Einstiegs-ATR; nachgezogener Stopp bei 4 oder 6 Einstiegs-ATR; CMO+Trail6; Steigung24+Trail6; Steigung72+Trail6; Steigung24+Stop4. Maximal 36 Kandidaten je Coin.
- Diese Filter/Stops sind **neue Strategiehypothesen**, nicht Bestandteil des Original-Pine. Ein gefilterter BUY verfällt; ein Stop erzeugt keinen Wiedereinstieg auf einer späteren grünen Kerze. Es braucht wieder einen originalen Hixton-Trendwechsel. Original-SELL hat Vorrang.
- Stops werden ausschließlich am Kerzenschluss geprüft und am echten nächsten Open zuzüglich Kosten ausgeführt. Trail-Referenz ist das Maximum aus Einstiegspreis und seit Einstieg beobachteten Schlusskursen; ATR wird vom Einstiegssignal festgehalten. Keine idealisierten Intrabar-Stopfills.
- Trainiert wird getrennt auf [01.09.2023 12:00 UTC, 01.09.2024 12:00 UTC) und [01.09.2024 12:00 UTC, 01.09.2025 12:00 UTC), jeweils neues Konto und neuer Warm-up. Mindestens sechs abgeschlossene Trades pro Trainingsjahr. Auswahl: höchste schlechteste Stress-Jahresrendite, dann geringster schlechtester Drawdown, dann höchste Renditesumme, dann feste Katalogreihenfolge.
- Nach dem Einfrieren: exakte Einzeltests im vollen Dreijahresfenster bis 01.09.2026 12:00 UTC und im jüngsten separat gestarteten Jahr; zusätzlicher älterer Diagnosetest [16.10.2021 01:00 UTC, 24.03.2023 13:00 UTC). Ältere Daten beeinflussen die Auswahl nicht.
- Alle Zeiträume wurden früher bereits betrachtet: **kein unangetasteter Holdout**. Ein schlechtes Validierungsergebnis führt nicht zu einer heimlichen Neuauswahl.
- Screening: Float ohne Mengenrundung. Endgültige Messungen: produktive Decimal-Backtestengines, Binance-Mengenfilter, Reststaub, Baseline und Stress. Baseline je Seite 10 bp Gebühr + 2 bp Spread + 3 bp Slippage; Stress 10 + 10 + 20 bp, kein vorausgesetzter BNB-Rabatt.
- Gemeinsamer V2-/Kandidatenvergleich in allen drei Fenstern mit 240 USDT und drei festen 80-USDT-Slots, höchstens ein Slot je Coin, unverändert 5-%-Tagespause/20-%-Drawdown-Halt. Die isolierten Konten haben diesen gemeinsamen Portfoliohalt nicht.

## Verlustdiagnose

Pro Coin werden abgeschlossene V2-Trades nach Haltedauer (<72 Stunden, 72 Stunden bis eine Woche, länger) zerlegt, die fünf schlechtesten Trades ausgewiesen und vorherige Kurschancen/Rückgänge während der Haltedauer gemessen (MFE/MAE). Diese rückblickenden Informationen sind keine im Voraus verfügbaren Signale. Ebenso wird die Abhängigkeit von den fünf größten Gewinnern ausgewiesen.

## Reproduktion

```powershell
py -3 src/main.py backtest research --study v5 --output backtests/v5/runs/neuer-review/research.json
```

Der lokale Datenbestand muss beide Fenster samt Warm-up vollständig enthalten. Die Anwendung lädt standardmäßig nur das aktuelle Dreijahresfenster; der ältere Diagnosedatensatz ist deshalb eine zusätzliche lokale Voraussetzung. Fehlende Daten führen zum Abbruch statt zu einem verkürzten Test. Vorhandene Ergebnisdateien werden nicht überschrieben. Große Rohberichte bleiben unter ignoriertem `runs/`; ein kompakter geprüfter Nachweis gehört nach `reports/`.

## Ergänzung nach dem ersten Kataloglauf

Der erste Lauf `coin-review-20260905` ist unverändert erhalten. Nur der ausgewählte XRP-Kandidat erhöhte alle sechs Einzel-Endwerte und senkte alle sechs Drawdowns gegenüber V2. Deshalb wird **nachträglich offen ausgewiesen**, nicht als vorab festgelegter Holdout, eine begrenzte Gegenprobe ergänzt: ausschließlich XRP ändern, die anderen neun V2-Coins unverändert lassen; gemeinsames Portfolio in allen drei Fenstern mit beiden Kostenmodellen. Außerdem sechs einachsige XRP-Nachbarn um den eingefrorenen Kandidaten: Stop 3,5/4,5 ATR, ATR-Länge 100/140, Band 3,0/3,4, jeweils voller/ jüngster/ älterer Stresslauf. Keine Nachbarauswahl anhand dieser Ergebnisse.

Die exakten Einzelberichte trennen zusätzlich realisierten PnL, Cash, offene Bewertung und Dust. Ein positiver Endwert durch eine noch offene Position darf nicht als bereits realisierter Gewinn bezeichnet werden. Aktive Paperstrategie bleibt V2; neue Forschung allein ist kein Aktivierungsgrund.

## Alle zehn Coins: Endkapital im Vergleich

Start **250 USDT je Zelle**. Dreijahresfenster einschließlich Training; jüngstes Jahr jeweils ein neues Konto, nicht der Reststand eines 2023 gestarteten Kontos. Endwerte enthalten offene Positionen und Dust zum Schlusskurs. „Kandidat“ bedeutet ausschließlich Trainingsgewinner, nicht freigegebene Verbesserung.

| Coin | V2 3 Jahre Baseline | Kandidat 3 Jahre Baseline | V2 jüngstes Jahr Stress | Kandidat jüngstes Jahr Stress |
|---|---:|---:|---:|---:|
| BTC | 414,47 | 559,73 | 162,99 | 206,64 |
| ETH | 649,16 | 729,87 | 213,63 | 278,47 |
| BNB | 388,69 | 418,31 | 183,90 | 210,90 |
| SOL | 1.508,45 | 1.540,35 | 201,11 | 192,86 |
| XRP | 557,38 | 594,89 | 153,37 | 240,32 |
| ADA | 678,79 | 894,81 | 114,86 | 108,42 |
| LINK | 612,46 | 739,00 | 195,53 | 194,02 |
| AVAX | 526,69 | 711,74 | 116,51 | 120,44 |
| DOT | 447,99 | 346,64 | 145,47 | 105,59 |
| DOGE | 808,14 | 858,16 | 175,17 | 190,34 |

Sechs Kandidaten verbessern den jüngsten Stress-Endwert, vier verschlechtern ihn. Nur ETH liegt dort über 250 USDT. Im gesamten Dreijahresfenster erreichen acht Kandidaten mindestens 500 USDT statt sieben bei V2, aber DOT wird deutlich schlechter. Das Ziel „alle zehn robust verbessert“ ist nicht erreicht. Die zehn isolierten Konten schließen insgesamt 435 statt 549 Trades ab; mehr Trades allein war kein Auswahlziel.

## Konkrete Schwächen und Schlussfolgerung pro Coin

Kurztrade-PnL bezieht sich auf abgeschlossene V2-Trades unter 72 Stunden im vollen Baselinefenster. Die Haltedauer ist erst nach dem Trade bekannt: Daraus darf keine rückblickend perfekte Kaufregel konstruiert werden.

| Coin | Gefundene Schwäche | Geprüfter Ansatz und Grenze |
|---|---|---|
| BTC | Kurztrades −168,46 USDT; fünf größte Gewinner liefern 65 % der positiven Tradegewinne. | V4-Trainingsparameter + CMO-Filter erhöhen Endwerte und senken den jüngsten Stress-Drawdown von 52,47 auf 40,05 %. Älterer Stress-Endwert sinkt von 379,86 auf 370,91. Noch Verlust im jüngsten Jahr. |
| ETH | Kurztrades −247,38 USDT, 25 von 40 Verlusttrades waren zwischenzeitlich mindestens 2 % im Kursplus. | V2 + positive 24-Bar-VIDYA-Steigung reduziert 61 auf 36 Dreijahrestrades. Jüngster Stress-Drawdown 43,65→26,54 %, Endkapital 278,47; davon +28,46 realisierter PnL, keine offene Hauptposition. Älterer Stress-Endwert 268,58→263,91: kein durchgängiger Vorteil. |
| BNB | Kurztrades −145,09 USDT; jüngstes Jahr und Kostenstress schwach. | V4-Parameter verbessern das jüngste Jahr, verschlechtern älteren Stress aber massiv: 313,34→190,30. Verwerfen statt den besseren aktuellen Wert zu übernehmen. |
| SOL | Wenige sehr große Trends tragen das Ergebnis: fünf Gewinner liefern 75 % der positiven Gewinne. | V4-Parameter erzeugen 57 statt 44 Dreijahrestrades, aber jüngstes Stressjahr 201,11→192,86 und höherer Drawdown. Den starken Langtrend-Anteil nicht durch ungeprüfte frühere Ausstiege beschädigen. |
| XRP | Kurztrades −147,06 USDT; fünf Gewinner liefern 91 % der positiven Gewinne. | 6/20/SMA8/ATR120/Band3,2 + Schlusskurs-Stopp 4 Einstiegs-ATR verbessert alle sechs Einzel-Endwerte und Drawdowns; 80 statt 55 Dreijahrestrades. Älterer Stress endet trotzdem bei nur 134,12. Gemeinsamer Kontotest und Nachbarn bestehen die Übernahmeprüfung nicht. |
| ADA | Kurztrades −196,64 USDT; 25 von 33 Verlusttrades waren vorher mindestens 2 % im Kursplus. | V4-Parameter sehen über drei Jahre besser aus, jüngster Stress 114,86→108,42, älterer Stress 186,94→126,69. Deutliches Warnzeichen einer vom Marktabschnitt abhängigen Auswahl. |
| LINK | Kurztrades −105,17 USDT; Trades zwischen drei Tagen und einer Woche zusätzlich −249,10. | V4 + Steigung24 senkt jüngsten Stress-Drawdown 47,74→23,74 %, verbessert aber nicht das Endkapital. Älterer Stress 158,48→96,72. Weniger Risiko in einem Fenster reicht nicht. |
| AVAX | Kurztrades −239,29 USDT; jüngster V2-Stress-Drawdown 69,42 %. | V4 senkt diesen Drawdown auf 58,46 %, aber jüngste Baseline und beide älteren Endwerte verschlechtern sich. Älterer Stress 327,86→210,02. |
| DOT | Kurztrades −145,18 USDT; starke Rückgaben früherer Kursgewinne bei 22 von 28 Verlusttrades. | V4 + CMO verschlechtert sämtliche sechs Endwerte; jüngster Stress-Drawdown steigt 55,99→67,47 %. Dieser Trainingsgewinner ist klar verworfen. |
| DOGE | Kurztrades −241,11 USDT; 17 von 27 Verlusttrades waren vorher mindestens 2 % im Kursplus. | V4 + CMO erhöht die aktuellen Endwerte, aber älterer Stress 237,29→208,66. Kein robuster Mehrfenster-Vorteil. |

Bei **allen zehn Coins** sind auch die abgeschlossenen Trades zwischen 72 Stunden und einer Woche netto negativ. Lange Gewinner finanzieren diese Verluste. Ein pauschaler enger Stop kann deshalb zugleich Fehlsignale begrenzen und die wenigen wichtigen Gewinner abschneiden. Die Zahlen begründen eine Hypothese, keine garantierte Verbesserung.

Der Original-Pine wurde als unveränderte Parameterkontrolle mitgerechnet. Er erzeugt je Coin 161–181 Dreijahrestrades, verliert aber beispielsweise bei ETH (178,27 USDT), LINK (170,69) und DOT (75,70) bereits in der vollen Baseline. Häufigeres Handeln mit den Originalwerten ist daher keine allgemeine Lösung.

## Gemeinsames Konto: drei Slots à 80 USDT

Start jeweils **240 USDT**, dieselben Risikolimits und dieselbe Priorisierung. „Nur XRP“ lässt die anderen neun Coins exakt auf V2.

| Variante / Fenster | Ende Baseline | Ende Stress | abgeschlossene Trades Baseline / Stress |
|---|---:|---:|---:|
| V2, volle 3 Jahre | 542,49 | 406,29 | 108 / 30 |
| alle Coin-Kandidaten, volle 3 Jahre | 808,30 | 776,04 | 197 / 189 |
| nur XRP geändert, volle 3 Jahre | 547,84 | 435,37 | 117 / 32 |
| V2, jüngstes Neustartjahr | 216,71 | 210,47 | 17 / 17 |
| alle Coin-Kandidaten, jüngstes Neustartjahr | 202,81 | 202,55 | 15 / 13 |
| nur XRP geändert, jüngstes Neustartjahr | 213,15 | 206,73 | 18 / 18 |
| V2, älteres Fenster | 227,42 | 223,32 | 11 / 11 |
| alle Coin-Kandidaten, älteres Fenster | 219,20 | 215,46 | 11 / 11 |
| nur XRP geändert, älteres Fenster | 230,23 | 232,86 | 12 / 11 |

Alle diese Portfolioläufe lösen einen Risikohalt aus. Beim vollständigen Kandidatenportfolio tritt er im langen Fenster später auf: 17.06.2026 Baseline bzw. 23.05.2026 Stress. Das erklärt einen Teil der höheren Tradezahl und ist **kein** Nachweis für stabilen dauerhaften 24/7-Handel. Beim jüngsten Neustart und im älteren Fenster ist das Gesamtpaket schlechter als V2. Nur XRP verschlechtert im jüngsten Jahr zudem den Portfolio-Drawdown von 23,66 auf 25,12 % Baseline und 25,40 auf 26,74 % Stress. Keine Übernahme.

## XRP: Nachbarstabilität und offene Bewertung

Nachträgliche Sensitivität, alle Werte Stress-Endkapital aus separat gestarteten 250 USDT. Nur eine Achse geändert; keine neue Gewinnerauswahl.

| Variante | Volle 3 Jahre | Jüngstes Jahr | Älteres Fenster |
|---|---:|---:|---:|
| eingefrorener Kandidat | 507,40 | 240,32 | 134,12 |
| Stop 3,5 ATR | 423,61 | 232,44 | 120,93 |
| Stop 4,5 ATR | 480,49 | 250,45 | 172,11 |
| ATR-Länge 100 | 469,12 | 226,41 | 127,63 |
| ATR-Länge 140 | 527,60 | 211,11 | 126,23 |
| Band 3,0 | 419,17 | 213,13 | 108,94 |
| Band 3,4 | 467,15 | 215,82 | 153,42 |

Das 500-USDT-Ziel ist nicht nachbarstabil. Außerdem sind die 275,64 USDT des XRP-Kandidaten im jüngsten **Baseline**jahr kein realisierter Gewinn: Die abgeschlossenen Trades verlieren dort zusammen 45,87 USDT; am Ende besteht eine offene Position. Der Bericht verschweigt diese Abhängigkeit nicht. Beim jüngsten **Stress**jahr sind es 240,32 Endkapital bei −71,33 realisiertem PnL.

## Nachweis, Übergabe und nächste Arbeit

- [Kuratierter JSON-Nachweis](reports/coin-review-20260905.json): alle zehn Parametersätze, Regeln, Trainingswerte, Kosten, Filter, Daten-/Quellhashes, exakte Kennzahlen, Cash/offene Bewertung, Verlustdiagnosen, Portfoliohaltes und Nachbarwerte.
- Rohbericht `coin-review-20260905-verified/research.json`, SHA-256 `5A4F5C63DF20A976D43A034BBD48927A4356E0D8FBED3951AA9ED9765D791B99`; bleibt lokal unter ignoriertem `runs/`.
- Der erste und zweite Lauf liefern identische zehn Auswahlen, alle 348 Trainingskandidaten, Einzelkennzahlen, Verlustdiagnosen, Datenhashes und ursprünglichen zwölf Portfoliowerte. Im zweiten Lauf zusätzlich: Cash-/Positionsaufteilung, XRP-Einzeländerungsportfolio und Nachbarsensitivität. Diese Ergänzungen wurden einmal historisch gerechnet, nicht als separat wiederholte Messungen behauptet.
- 86 automatisierte Tests bestanden; Ruff und mypy (37 Source-Dateien) ohne Befund. Oberfläche und aktive Konfiguration unverändert. Keine neue Pine-Quelle, keine realen Orders, kein Ledgerreset.

Nächster sinnvoller Forschungszyklus: vorab definierte rollierende Trainingsfenster mit Auswahl ausschließlich aus jeweils bereits vergangenen Daten prüfen, statt weiter denselben Zweijahresgewinner auf das bekannte Wunschziel zu trimmen. ETH-Steigungsfilter und XRP-Risikobegrenzung bleiben nachvollziehbare Hypothesen, keine freigegebenen Sonderparameter. ADA, DOT, AVAX und LINK benötigen weiter Schutz vor schwachen Marktphasen. Ein adaptiver Filter muss ausschließlich damals verfügbare Informationen nutzen und zunächst in Einzel- **und** gemeinsamen Konto-Tests überzeugen. Der aktuelle Paper-Vorwärtslauf bleibt die einzige noch neu entstehende Markterfahrung; Profit pro Tag wird nicht versprochen.
