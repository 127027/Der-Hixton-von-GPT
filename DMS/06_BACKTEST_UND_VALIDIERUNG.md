# 06 – Backtest und Validierung
## Aktueller Validierungsvertrag 18.09.2026

Der Standardvergleich besteht aus demselben Drei-Jahresfenster für **10×250 USDC isoliert** und **3×80 USDC gemeinsam**. 10×250 dient der per-Coin-Diagnose und Kandidatensuche; Auswahl geschieht ausschließlich auf Trainingsfenstern. Danach werden Kandidaten auf getrennten Validierungsfenstern und unter Kostenstress geprüft. Der zusammengesetzte Zehn-Coin-Kandidat wird einmal versioniert und unverändert in den gemeinsamen 3×80-Lauf übernommen. Beide Modi müssen dieselben per-Symbol-Parameter-/Policy-Hashes ausweisen.

Der gemeinsame Lauf nutzt `ranked_repeat`, zählt Positionszyklen und Slot-Trades getrennt, behält die 5-%-UTC-Tagespause und verwendet **keinen permanenten Portfolio-Drawdown-Halt**. Eine isolierte Verbesserung ist ohne frischen gemeinsamen Lauf keine Freigabe. Wegen Slotkonkurrenz ist ein höherer isolierter Endwert allein kein mathematischer Beweis für einen höheren gemeinsamen Endwert; jede Abweichung muss aber durch die gemeinsame Signal-/Fillspur erklärbar sein.


## Eigentümerpräzisierung 15.09.2026: eine Regelbasis, mehrere Prüfsichten

Die aktive Strategie samt individuellen Parametern aller zehn Coins ist die
einzige fachliche Regelbasis. Paper verarbeitet aktuelle Marktdaten; der
Portfolio-Backtest verarbeitet historische Daten mit denselben Coin-Regeln,
Slotentscheidungen und Risikoregeln. Eine Verbesserung wird zentral versioniert,
nicht exklusiv in einem Simulator eingebaut. Erst nach geprüfter Aktivierung
ist sie neuer Istzustand; Forschungsvarianten sind ausdrücklich nicht aktiv.

Zielbetrieb bleibt ein gemeinsames Konto mit aktuell 250 USDC und drei
80-USDC-Slots, das neue qualifizierte Signale aller zehn Coins berücksichtigt.
Spätere Kapazitätsstufen 6×80 und 9×80 dienen demselben Zweck und benötigen
entsprechend finanziertes Kapital. Kein separates Coin- oder Backtest-Regelwerk.
Mehr gute ausgeführte Trades ist das Ziel, nicht künstliche Wiederholung eines
alten grünen Trends oder Aufhebung von Risikogrenzen.

Die isolierten Tests verwenden dieselben Hixton-/Coin-/Exit-Regeln, verändern
aber absichtlich das Versuchskonto: je ein Coin mit 250 USDC, keine Konkurrenz
um drei Slots und derzeit kein Konto-Drawdownhalt. Sie dienen zur gezielten
Diagnose, nicht als vollständiger Kontospiegel oder als Ersatz für den
gemeinsamen Portfolio-Test. Daher dürfen Ergebnisse und Tradezahlen voneinander
abweichen. Abweichende Signalregeln bei identischen Kerzen/Profilen wären ein
Fehler; Unterschiede durch Kapital, Besitzstatus, Slotbelegung und ausdrücklich
ausgewiesene Kontoregeln sind dagegen Bestandteil des Versuchsaufbaus.

Die beiläufige Nennung „10x50“ im Auftrag ersetzt die bisher ausdrücklich
festgelegten Einzeltests 10x250 nicht stillschweigend. Der separate
50-USDC-Echtgeld-Einmaltest bleibt ein anderes, weiterhin gesperrtes Verfahren.

Vor jeder Übernahme: zentrale Regeln ändern, Signal-/Exit-Parität prüfen,
zehn Einzeltests und gemeinsamen Portfoliolauf mit identischem Zeitfenster,
Kosten und dokumentiertem Startzustand neu rechnen. Kein Ergebnis wird auf
einen Zielgewinn geändert. Jeder neue Bericht hält Code und Kosten fest;
die UI vergleicht gespeicherte Regeln, Code und Portfolio-Einstellungen mit
dem aktiven Stand. Bei Dateipatches braucht die Laufzeit einen Neustart,
bevor ein neuer Backtest als Nachweis dieses Codes erzeugt werden darf.

Am 15.09.2026 wurde der aktuelle gemeinsame USDC-Zeitraum mit der echten
Paper-Engine einschließlich zweier Verarbeitungsunterbrechungen nachgespielt:
28/28 Fills und Endkapital exakt wie im Portfolio (DMS 18). Offen bleiben weitere
Zeitfenster, Intrabar-Risikoüberwachung und umfassende Ausfall-/Live-Reconciliation.
Gemeinsame Parameter und erfolgreiche Einzeltests allein sind kein Nachweis,
dass sämtliche Ausführungspfade bereits vollständig identisch sind.

Aktivierung DEC-045: Backtests ohne `--strategy` spiegeln jetzt den V6-Paper-Coin-Mix; UI und CLI verwenden dieselben Profile. Historische Vergleichsdateien und deren damaliges `paper_approved: false` bleiben unverändert. Der explizite neue Paperlauf ist ein Vorwärtsversuch, kein nachträgliches Bestehen der Mehrfenstertests.

V6-Prüfstand (06.09.2026): `backtest research --study v6` bewertet eingefrorene Coin-Profile und V2 mit identischen Produktionsengines, Börsenfiltern, Kosten und Fenstern. Für einen fairen gemeinsamen Vergleich starten beide bei 250 USDT; alte 240-USDT-Nachweise bleiben unverändert. Auswahl zwischen V2 und V5-Finalist nutzt den höchsten schlechtesten Stress-Endwert aus allen drei bereits betrachteten Zeiträumen. Deshalb sind diese Zeiträume Kalibrierung/retrospektive Diagnose, **kein unangetasteter Holdout**. Keine nachträgliche Umwahl nach Portfoliobefund. Ergebnisse und Rückschritte: `backtests/v6/README.md`.

## Ziel

Der Backtest hat zwei getrennte Ziele: zuerst beweisen, dass der Bot auf jede historische Kerze exakt gemäß der ausgewählten, versionierten Strategie reagiert; danach reproduzierbar messen, wie diese unveränderte Version unter realistischen Kosten abgeschnitten hätte. V1 referenziert `HIXTON-SPEC-1.0`, V2 die vom Eigentümer bereitgestellte Pine-v6-Datei und einen eingefrorenen Parameter-Snapshot. Der Backtest beweist keine zukünftige Profitabilität.

## Testfenster

Primärtest je Coin:

- exakt drei vollständige Kalenderjahre im halboffenen Intervall `[report_start_utc, report_end_utc)`;
- `report_end_utc` liegt auf einer vollen UTC-Stunde und wird vor Datenabruf festgeschrieben; Standard ist der letzte planmäßig bereits finalisierte 1h-Bar-Schluss;
- `report_start_utc` ist dieselbe UTC-Uhrzeit drei Kalenderjahre früher; existiert der Tag nicht (29. Februar), wird auf den 28. Februar geklemmt;
- Datenlücken verändern niemals Start/Ende, sondern machen den Lauf bis zur Klärung ungültig;
- zusätzlich notwendiger Warm-up vor dem Start;
- Endkapital und Metriken werden nur innerhalb des Berichtsfensters gezählt;
- zusätzlich ein „volle verfügbare Historie“-Lauf, wenn die Datenqualität dies zulässt.

Für regelmäßige Neubewertung wird ein rollierendes 3-Jahres-Fenster verwendet. Ein veröffentlichter Bericht darf sein historisches Fenster nachträglich nicht ändern.

## Läufe

1. kapitalunabhängiger Golden-/Replay-Test der Indikatorwerte und Signale;
2. Standard-Batch mit zehn isolierten Einzeltests à 250 USDC;
3. Einzelmodus für ein frei gewähltes Paar, zum Beispiel nur ETH/USDT, mit 250 USDT;
4. Vergleichsaggregation der zehn isolierten Ergebnisse (2.500 USDT rechnerisches Simulationskapital, kein gemeinsamer Cashpool);
5. Paper-/Live-Spiegellauf mit gemeinsam 250 USDT und höchstens drei 80-USDT-Slots;
6. Buy-and-Hold-Benchmark je Coin;
7. Sensitivität gegenüber Kosten und Slippage;
8. Walk-forward-/Out-of-sample-Prüfung, falls Parameter überhaupt abgestimmt werden;
9. Replay-Test, der Bars chronologisch einzeln zuführt.

## Ereignisreihenfolge je Bar

Die Engine verwendet eine feste Reihenfolge:

1. zu Beginn der Bar werden Orders verarbeitet, die aus der vorherigen geschlossenen Bar stammen;
2. Fill, Gebühren, Cash und Position werden verbucht;
3. Intrabar werden ohne explizites Modell keine Entscheidungen getroffen;
4. am Bar-Ende wird die Bar finalisiert;
5. Indikator und Trendwechsel werden berechnet;
6. ein neuer Order-Intent wird frühestens für die nächste Bar vorgemerkt.

Damit kann der Schlusskurs einer Bar nicht gleichzeitig rückwirkend als Fillpreis derselben Entscheidung dienen.

## Verbindliches Kostenmodell

Alle Werte gelten je ausgeführter Orderseite und wirken immer zu Ungunsten der Strategie.

| Szenario | Binance-Gebühr | Spreadanteil | zusätzliche Slippage | Summe je Seite | Round-Trip |
|---|---:|---:|---:|---:|---:|
| Baseline | 10 bps | 2 bps | 3 bps | 15 bps | 30 bps |
| Stress | 10 bps | 10 bps | 20 bps | 40 bps | 80 bps |

Regeln:

- Kein BNB-Rabatt und keine VIP-Vergünstigung werden in der Baseline vorausgesetzt.
- Kauf-Fill = Next-Bar-Open × `(1 + (Spread + Slippage)/10.000)`; Verkaufs-Fill entsprechend mit Minus.
- Ein Kauf verwendet höchstens das Ziel-Quote-Budget (initial 80 bzw. 250 USDT): `gross_base = quote_spend / Kauf-Fillpreis`; Kaufgebühr wird im Basissasset abgezogen, `net_base = gross_base × (1-fee_rate)`, Cash sinkt exakt um `quote_spend`.
- Beim Verkauf wird die gesamte regelkonform handelbare Basismenge zum adversen Fillpreis bewertet; Verkaufsgebühr wird vom Quote-Erlös abgezogen, `net_quote = gross_quote × (1-fee_rate)`.
- Damit können drei 80-USDT-Kaufbudgets aus 240 USDT belegt werden, ohne einen negativen Cashbestand zu erfinden. Tatsächliche Live-Gebührenassets werden aus Börsenfills übernommen und im Papervergleich separat ausgewiesen.
- Tick Size, Step Size und Mindestnotional werden mit dem zum Lauf gespeicherten Binance-Filterstand simuliert.
- Wird später die echte kontospezifische Binance-Gebühr automatisch abgefragt, erscheint sie als zusätzliches Account-Szenario; Baseline und Stress bleiben für Vergleichbarkeit erhalten.
- Reports zeigen Brutto-PnL, Gebühr, Spread, Slippage und Netto-PnL getrennt.

## Metriken je Coin

- Start- und Endkapital;
- Netto-PnL in USDT und Nettorendite in Prozent;
- annualisierte Rendite, nur mit sauber dokumentierter Formel;
- maximaler Drawdown in USDT und Prozent samt Zeitraum;
- Anzahl abgeschlossener Trades;
- Gewinnquote;
- durchschnittlicher Gewinn/Verlust und Payoff-Ratio;
- Profit Factor;
- Gebühren und geschätzte Slippage separat;
- Exposure/Marktzeit;
- durchschnittliche und maximale Haltedauer;
- größte Gewinn-/Verlustserie;
- Sharpe und Sortino mit dokumentierter Periodisierung und risikofreiem Satz;
- Calmar;
- Buy-and-Hold-Ergebnis und Differenz;
- monatliche Renditen und Equity-Kurve.

Bei zu wenigen Trades werden instabile Kennzahlen sichtbar als „nicht aussagekräftig“ markiert.

## Batch-, Einzel- und Portfolioauswertung

- Batch: zehn Resultate mit je 250 USDT werden einzeln gezeigt und nur zum Vergleich summiert;
- Einzelmodus: Coin-Auswahl, zum Beispiel ETH, darf ohne die übrigen neun ausgeführt werden;
- Spiegelportfolio: gemeinsamer Cashpool 250 USDT, drei 80-USDT-Slots und dokumentierte Slotpriorisierung;
- Im Spiegelportfolio werden Ausstiege am nächsten Bar-Open vor Einstiegen verarbeitet. Gleichzeitige Einstiege werden nach normalisierter Ausbruchsstärke und danach in der festen DMS-Coinreihenfolge sortiert. Blockierte Signale werden nicht später künstlich nachgeholt;
- Der echte Paper-/Live-Spiegel wendet zusätzlich dieselbe 5-%-UTC-Tagesverlustpause und denselben persistenten 20-%-High-Water-Drawdown-Halt wie die Paperengine an. Ein Lauf ohne diese Gates heißt ausdrücklich `strategy-only` und darf nicht als Paper-/Live-Ergebnis bezeichnet werden;
- keine Verwechslung zwischen rechnerischer Batchsumme und realistischem gemeinsamen Cashbestand;
- Equity nach gemeinsamer UTC-Zeitachse;
- Korrelationen der Tagesrenditen;
- Beitrag jedes Coins zu PnL und Drawdown;
- maximale gleichzeitig investierte Summe;
- separate Darstellung von Brutto-, Nettoergebnis und Tradezahl; 250→500 USDT je Coin darf als Beispiel ausgewiesen werden, aber nie als Garantie oder Grund zum Verbergen schlechter Ergebnisse.

## Validierungsdesign und Anti-Overfitting

- Parameter werden vor dem finalen Test eingefroren.
- Ein finaler Holdout wird nur einmal für die Freigabe verwendet.
- Wenn Parameter optimiert werden, werden Suchraum, Anzahl Versuche und Auswahlregel vollständig gespeichert.
- Kein Coin darf aus dem Bericht verschwinden, weil er schlecht abschneidet.
- Delistete/umbenannte Märkte und Datenverfügbarkeit werden dokumentiert.
- Sensitivität prüft Nachbarparameter; ein nur an einem exakten Punkt gutes Ergebnis gilt als fragil.
- Monte-Carlo/Trade-Reordering kann als Robustheitsanalyse dienen, ersetzt aber keine Marktzeitsimulation.
- Die Strategie wird nicht so lange verändert, bis ein gewünschter Gewinnwert erscheint.
- Jede Verbesserung erhält `backtests/v2`, `v3` usw.; der aktive Paperstand wird nur nach explizitem, auditierbarem Wechsel vorwärtsgerichtet ersetzt.
- Ein gemeinsamer Parametersatz für alle zehn Coins wird vor Coin-spezifischen Sonderwerten bevorzugt, solange kein sauberer Out-of-sample-Nachweis die zusätzliche Komplexität rechtfertigt.
- Höhere Tradezahl ist nur ein Sekundärkriterium, wenn Baseline, Kosten-Stress, ältere Marktphasen und Nachbarparameter mindestens gleich robust bleiben.

## Mindest-Gates für fachliche Freigabe

Ein Backtest ist nur `VALID`, wenn:

- Spezifikationsparität ohne Wert-/Signalabweichung innerhalb der festgelegten numerischen Toleranz nachgewiesen ist;
- Datenqualitätsprüfung bestanden ist;
- keine fehlenden Bars im Berichtsfenster existieren oder Ausnahmen explizit dokumentiert sind;
- Kostenmodell vollständig ist;
- Konfiguration und Datenversion gehasht sind;
- alle zehn Einzeltests abgeschlossen sind;
- Lauf ohne Zufall oder mit gespeichertem Seed exakt reproduzierbar ist;
- Bericht auch Verlustperioden, nicht ausgeführte Signale und Kosten zeigt.

## Ergebnisinterpretation

Der UI-Portfoliovergleich übernimmt die aktuell gespeicherte Paper-Slotanzahl und das Zielnotional, startet aber ein neues simuliertes Konto mit dem Startkapital der aktiven Config (jetzt 250 USDC). Er übernimmt weder aktuelle offene Positionen noch bisherige Papergewinne. Sein Endzeitpunkt wird aus der letzten für alle zehn Coins vorhandenen geschlossenen Kerze bestimmt, nicht blind aus der Wanduhr.

V4-Prüfung vom 05.09.2026: 24 begrenzte Parametervarianten je Coin, Auswahl anhand der schlechtesten Stressrendite der ersten beiden einzeln gestarteten Trainingsjahre, danach festgehaltener Vergleich im dritten Jahr. Exakte Finalisten verwenden die produktiven Decimal-Engines. Zusätzlich wird eine getrennte, vereinfachte Nachkaufhypothese getestet. Ergebnisse und Grenzen stehen einmalig in `backtests/v4/README.md`; weder diese Hypothese noch der coinindividuelle Kandidat ist aktiv. Ein hoher Gesamtwert bei Verlusten im jüngsten Neustartfenster rechtfertigt keine Übernahme.

Korrekte Botreaktion und Profitabilität sind zwei verschiedene Ergebnisse. Korrekte Software kann Verlust ausweisen. Dann wird die Strategie nicht still verändert; der Eigentümer entscheidet separat über eine neue Strategieversion. Hohe Tradezahl wird nur positiv bewertet, wenn die Nettoperformance nach Binance-Gebühren und Slippage nicht dadurch verschlechtert wird.

V5 ergänzt die Einzelcoin-Verlustdiagnose und bis zu 36 vorab begrenzte Kombinationen aus Original-Pine, V2-/V4-Trainingsparametern und Hixton-basierten Einstiegsfiltern bzw. Schlusskurs-ATR-Stops. Identische Parameterbasen werden dedupliziert: 348 Kandidaten insgesamt. Zwei separat gestartete Trainingsjahre bestimmen je Coin einen Finalisten; jüngstes Jahr und älteres Fenster ändern diese Auswahl nicht. Die XRP-Einzeländerungs-/Nachbarprüfung ist offen als nachträgliche Diagnose gekennzeichnet. Regeln, sämtliche Coins, Rückschritte und gemeinsame Portfoliowerte stehen in `backtests/v5/README.md`. Stops sind neue Forschung, nicht stillschweigend Teil der Original-Pine- oder aktiven Paperlogik.

V5-Finalisten rechnen in denselben Decimal-Backtestengines wie V2, verwenden aber explizit andere Regeln. Eine funktionierende Forschungs-Backtestausführung ist **kein** Nachweis, dass diese neuen Regeln bereits im Paper implementiert oder aktiviert wären. Vor einer Übernahme wären Paper-/Restart-/Chart-Parität dieser Regeln und ein neuer versionierter Vorwärtslauf erforderlich. Endkapital, realisierter Gewinn und offene Bewertung werden getrennt ausgewiesen.

## Auswahl- und Übernahmeprinzip

Der Zweck der Backtests ist nicht nur Archivierung: Eine nach dem vollständigen Prüfprogramm besser belegte, zulässige Version soll nach ausdrücklicher Eigentümerentscheidung als Paperstandard übernommen werden. Bewertet werden gemeinsam Nettoperformance, Stresskosten, ältere Zeitfenster, Nachbarstabilität, 3×80-Risikospiegel und Reproduzierbarkeit. Maximale Rendite in nur einem Fenster, mehr Trades allein oder gelockerte Risikogrenzen begründen keine Übernahme. Live-Freigabe bleibt davon strikt getrennt.

## V2-Zyklus und Paperfreigabe

Der Stand vom 02.09.2026 ist vollständig in `backtests/v2/README.md` und maschinenlesbar in `backtests/v2/candidate.json` dokumentiert. Der Zyklus umfasste ein breites Raster von 1.280 gemeinsamen Parametersätzen, eine Mehrfensterprüfung von 75 Finalisten, 48 Nachbarvarianten, Baseline-/Stresskosten und erneute Rechnung der Finalisten in der Produktionsengine. Im exakt gleichen aktuellen 3×80-Risikospiegel übertraf V2 V1: 542,49 statt 383,89 USDT Baseline und 406,29 statt 343,47 USDT Stress. Der Eigentümer gab V2 deshalb als bestbelegten bisherigen Stand für Paper frei. Ältere Verlustfenster und vorzeitige Risikohalts bleiben offen ausgewiesen und sperren weiterhin Live.

## V3-Mehrfachslot-Versuch

`HIXTON-V3-SLOT-CANDIDATE-1` ließ bei unveränderten V2-Signalen freie Slots auf demselben Coin wiederholen. Im aktuellen Dreijahres-Risikospiegel endete der Lauf `76a78440-405a-4624-bc0b-7765558b801c` bereits am 12.10.2023: 287,85 USDT Baseline beziehungsweise 282,16 USDT Stress, jeweils nur vier abgeschlossene Positionen. Weil diese Variante V2 deutlich untertraf und das Konzentrationsrisiko sofort auslöste, wurde sie am ersten Gate verworfen; weitere Altfensterrechnungen wären keine sinnvolle Nutzung von Rechenzeit. Der vollständige kuratierte Nachweis liegt unter `backtests/v3`.
