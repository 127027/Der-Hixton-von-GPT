# 18 – Backteststatus und Ergebnisnachweis
## Aktueller Referenzstand 18.09.2026 – nach Entfernung des permanenten Drawdown-Halts

Zentraler fortlaufender Forschungsindex für alle zehn Coins: [backtests/README.md](../backtests/README.md). Dort werden Baselines, Verlustmuster, Hypothesen, akzeptierte und verworfene Kandidaten sowie die zwingende 10×250→3×80-Integrationsprüfung fortgeschrieben. DMS 18 bleibt der formale Ergebnisnachweis; das Backtest-README ist das Lernjournal.


Echter Dashboard-E2E, Drei-Jahresfenster **18.09.2023 18:00 UTC bis 18.09.2026 18:00 UTC**, aktive V6-USDC-Profile, historische gleiche-Basisasset-USDT-Preiswege nur dort als klar gekennzeichneter Preisproxy, wo echte gleichlange USDC-Historie fehlt:

- **Gemeinsames 3×80-USDC-Portfolio:** Start 250,00 USDC; Ende **750,7926241238353 USDC**; Rendite **+200,3170 %**; **111 Positionszyklen / 246 Slot-Trades**; maximaler Drawdown **31,9709 %**; kein permanenter Risikohalt; null `MAX_DRAWDOWN_20_PERCENT`-Blocks. Blockiert wurden 390 Kandidaten wegen `NO_FREE_SLOT`, 26 wegen VIDYA-Slope und 4 wegen CMO.
- **10×250-USDC isoliert:** Startsumme 2.500 USDC; Ende **7.269,4231344730335 USDC**; Rendite **+190,7769 %**; **492 Positionszyklen**; kombinierter Max-Drawdown **15,8921 %**. Einzelzahlen: ADA 54, AVAX 38, BNB 42, BTC 44, DOGE 47, DOT 43, ETH 36, LINK 50, SOL 57, XRP 81 abgeschlossene Trades.

Diese beiden Modi verwenden dieselbe kanonische V6-Profilmap, aber unterschiedliche Kapitalmodelle: 10×250 hat zehn getrennte Cashbestände ohne Slotkonkurrenz; 3×80 hat einen gemeinsamen Cashpool und drei Slots. Eine isolierte Verbesserung muss deshalb in den gemeinsamen Profildaten erscheinen und einen frischen 3×80-Lauf auslösen, garantiert wegen Slotkonkurrenz aber nicht automatisch einen höheren gemeinsamen Endwert.

**Neuer Forschungszyklus:** Alle zehn Coins werden einzeln auf Verlustmuster, Entry-/Exit-/Stop-/Trendfilter untersucht. Auswahl nur auf Trainingsfenstern; Validierung und Kostenstress danach. Der einmal zusammengesetzte Zehn-Coin-Kandidat wird unverändert erneut in 10×250 und 3×80 geprüft. Keine automatische Aktivierung allein aufgrund historischer Verbesserung.


## Kontrollierter USDT-/USDC-Migrationsvergleich, 15.09.2026

Mit dem heutigen unveränderten V6-Rechenkern sechs Portfolio- und 60 Einzel-
rechnungen ausgeführt (drei Datenfenster/-paare, jeweils Baseline und Stress).
Enddatum durchgehend **01.09.2026 12:00 UTC**, Ende exklusiv, 400 Warm-up-Bars.
Portfolio startet mit 250 und drei festen 80er-Slots; isoliert zehnmal 250.

| Baseline / wirtschaftliche Quote | Beginn UTC | Portfolio Ende | Abschlüsse | 10×250 Ende |
| --- | --- | ---: | ---: | ---: |
| USDT, ursprüngliches Fenster | 01.09.2023 12:00 | 733,31 | 187 | 7.152,29 |
| USDT, späterer Neustart | 24.03.2024 00:00 | 201,11 | 9 | 4.118,70 |
| USDC, gleicher späterer Neustart | 24.03.2024 00:00 | 203,62 | 14 | 4.007,26 |

Alte Portfolio-Referenz `56a34f10-58fa-4968-9b24-59e430196c6d` und Batch-
Referenz `20bc2a48-cc79-4761-9e49-8ca5fffde150`: Endwerte und Abschlusszahlen
werden **sowohl unter Baseline als auch unter Stress exakt reproduziert**.
Alle zehn numerischen Coinprofile und ursprünglichen USDT-Kerzenhashes stimmen
überein; die verwendeten aktuellen Börsenfilter sind zwischen den Paaren gleich.
USDT-Symbolbezeichner wurden ausschließlich im Arbeitsspeicher an den heutigen
USDC-Validator angepasst, ohne Preise umzuschreiben. Keine USDT-Historie wird
als echte USDC-Historie ausgegeben oder in das laufende Konto übernommen.

Die Differenz 733 gegenüber 203 ist damit in diesen Kontrollen kein Nachweis
einer kaputten Währungsumrechnung: Bereits **USDT selbst** fällt beim späteren
Neustart auf 201,11. Der ursprüngliche Lauf hatte am ersten Stundenschluss des
24.03.2024 bereits 681,09 Equity, einschließlich offener Positionen; der spätere
Versuch beginnt dagegen neu mit 250. Signalzustand, belegte Slots und relative
Kontorisiken folgen damit einem anderen Verlauf. Der spätere USDT-Lauf hält am
30.04.2024, der USDC-Lauf am 01.05.2024. Ein früherer Start ist keine heute
verfügbare Strategieverbesserung. Der Paarunterschied verbleibt, ist im direkten
Vergleich aber erheblich kleiner; einzelne Coin-Signale müssen nicht identisch sein.

Codevergleich gegen V6-Aktivierungscommit `226be5b`: keine numerische Änderung
der Coinprofile, Kosten oder Kontorisikogrenzen; TradePolicy unverändert,
Prioritätsrefaktorierung semantisch gleich. Das ursprüngliche Run-Manifest
enthält keinen bekannten Codecommit; daher keine Behauptung über vollständige
Identität der damaligen Anwendung. Die Reproduktion prüft den Handelsrechenkern,
nicht echte Binance-Ausführung oder künftige Profitabilität.

Vollständiger [Kontrollbericht](../backtests/v8/reports/quote-migration-audit-20260915.json)
mit allen Einzelwerten, Kostenfällen und Prüfkennzeichen. Aktiver Python-Hash
`a2eced48a11bbf6ddf678244b37bfe21f9501649ae91ff8a3e04eaa9295a3c9b`.
Kein Strategie-, Risiko- oder Kontowechsel und kein Echtgeldstart bei dieser
Prüfung. Die abweichenden aktuellen UI-Endwerte beziehen sich auf spätere
Enddaten; historische Resultate werden nicht überschrieben.

## Portfolio-Verbesserungsversuch V9, 15.09.2026

Zehn vorab festgelegte gemeinsame Einstiegs-/Exit-Varianten mit individuellen
unveränderten Hixton-Coinparametern über den bestehenden CLI-Einstieg getestet.
Training entscheidet auf Portfolio-Stress statt Auswahl zehn isolierter Gewinner.
28 Portfolio- und 80 Einzelrechnungen fertig; Trainingsfinalist `trail4`.
Gesamt-Baseline verbessert 203,72 → 265,59 USDC, 14 → 123 Abschlüsse, aber
Gesamt-Stress endet bei 218,45 und späterer Baseline-Neustart verschlechtert
220,72 → 208,99. Alle ausgewählten Portfolioversuche weiterhin im Risikohalt.

Explizite anschließende Diagnose ohne Kontorisikogates: 262,03 USDC / 313 Trades /
35,61 % DD, unter Stress nur 165,18 USDC / 290 Trades / 52,19 % DD. Kein Beleg
für eine Erholung auf 700 und kein Grund zur Abschaltung des Schutzes.
Keine Übernahme; aktives V6-Paper, drei Slots und Kontobestände unverändert.
Die gewünschten rund 733 USDC Endkapital sind **nicht erreicht**. Nicht durch
beliebiges Wiederholen auf denselben Daten eine scheinbare Freigabe erzeugen.

Details, alle zehn Coin-Diagnosen und Provenienzgrenzen: [V9](../backtests/v9/README.md).
335 Python-Tests / ein Skip, Ruff und mypy bestanden. V9 bleibt Forschung und
steht deshalb nicht als aktive Paperstrategie in der UI-Auswahl. Keine Livefreigabe.

Laptop nach Abschluss am 15.09.2026 um 15:58:38 Europe/Berlin über Startbot
sichtbar neu gestartet; HEALTHY / PAPER / LIVE_DISABLED, Konto und offene SOL-
Position erhalten. Reguläre Backtests ebenfalls fertig, Fenster nun bis
15.09.2026 16:00 Europe/Berlin: Portfolio `e549a5d0-6da8-4807-a7e0-edf5412b1247`
203,70 USDC / 14 Trades; 10×250 `b975692b-6e19-4acd-a5bf-3ca856e74634`
3.994,68 USDC / 443 Trades. Beide `MATCHING`, beide mit Baseline/Stress.
Produktiver Python-Quellhash:
`a2eced48a11bbf6ddf678244b37bfe21f9501649ae91ff8a3e04eaa9295a3c9b`.
Die kleine Abweichung zum festgeschriebenen Forschungsende 08:00 ist ein anderes
Datenende, kein aktivierter Parameterpatch. Portfolio-UI nach Neustart geprüft.

## Slot-Ursachenprüfung 15.09.2026 – 3, 6 und 9 Slots

Ziel präzisiert: Das gemeinsame Portfolio nutzt qualifizierte neue Signale aller
zehn Coins, um Wartezeiten einzelner Coins auszufüllen. Spätere 6×80 bzw. 9×80
benötigen zusätzliches Kapital, nicht bloß eine höhere Slotzahl. Keine Pflicht,
alte Trends nachzukaufen oder trotz Verlustschutz weitere Trades zu erzwingen.

Zwölf kontrollierte Rechnungen mit unveränderten V6-Profilen, identischen
USDC-Kerzen und Baseline/Stress abgeschlossen. Fenster wie der vorige Lauf:
24.03.2024–15.09.2026 08:00 Europe/Berlin. Ergebnisse:

| Versuch | Start USDC | Baseline Ende | Abschlüsse | Max. DD | Stress Ende |
| --- | ---: | ---: | ---: | ---: | ---: |
| Alle zehn, 1×80 | 250 | 272,89 | 36 | 23,28 % | 210,95 |
| Alle zehn, 3×80 | 250 | 203,72 | 14 | 20,83 % | 203,33 |
| Alle zehn, 6×80 | 490 | 390,12 | 37 | 21,48 % | 377,74 |
| Alle zehn, 9×80 | 730 | 585,18 | 52 | 20,92 % | 584,94 |
| Nur Diagnose: 3×80 ohne Kontorisikogates | 250 | 223,10 | 197 | 54,28 % | 156,23 |
| ADA allein, 1×80 mit Kontorisikogates | 250 | 346,80 | 20 | 21,12 % | 338,33 |

Risiko-aus ist **ausschließlich eine Ursachenmessung**, kein Kandidat zur
Aktivierung. ADA-Kontrolle hält die neun anderen Märkte künstlich konstant,
um nur ADA-Einstiege mit dem echten Portfolio-Risikomodell zu prüfen; keine
Behauptung über ein echtes Zehn-Coin-Marktszenario. Keine Konten/Profilparameter
oder Risikoschwellen im Bot geändert. Ein größerer Drawdown als 20 % ist möglich:
Der Halt sperrt neue Einstiege, liquidiert bestehende Positionen aber nicht.

3×80-Baseline: **473 Kaufkandidaten = 14 Käufe + 431 Risikohalt + 24 Coinfilter
+ 4 volle Slots**. Keine unzugeordneten Kaufkandidaten, alle drei Slots tatsächlich
belegt. Auch sechs und neun Slots werden in ihren Baselines genutzt. Bei ADA
wurde der erste Einstieg durch volle Slots blockiert, die weiteren 49 durch
den Risikohalt. LINK (−16,18), BNB (−10,33) und DOT (−7,31 USDC) verursachen
den größten Teil der realisierten Portfolioverluste. Das Verlustproblem ist
nicht durch eine heimliche Ein-Slot-Grenze erklärt und nicht behoben, indem
man nur die Slotzahl erhöht. Mehr Märkte liefern zudem häufig gleichzeitige
statt zeitlich ergänzende Signale; keine monotone Gewinn-/Tradegarantie.

**Direkter tatsächlicher Paper-/Portfolio-Replay über das gesamte Fenster:**
temporäres Paperkonto 250 USDC, aktive zehn V6-Profile, echte Kerzen und normale
Risikoregeln. 28/28 Fills einschließlich Signal-ID, Referenzpreis, Ausführungspreis
und Menge exakt gleich; Endwert jeweils **203,718610797945 USDC**. Derselbe Test
mit zwei unterbrochenen/neu geöffneten Verarbeitungsschritten ergibt wieder
identische Fills und Equity. Dies bestätigt den untersuchten historischen
Paper-Engine-Pfad, nicht Binance-Livefills, Intrabar-Überwachung oder alle
denkbaren Restart-/Fehlerzustände.

Behobene UI-Nachweislücke: Portfolio zeigt nun maximale gleichzeitige Belegung
und konkrete Blockiergründe samt Anzahl. Auswahlwechsel/Fehler löschen die alte
Diagnose; Einzeltests zeigen keine fremden Portfoliozahlen. 22 UI-Tests,
TypeScript und Produktionsbuild bestanden. Python-Handelscode unverändert.

Nachweise: [Slotprüfung](../backtests/v8/reports/slot-capacity-audit-20260915.json),
[Paper-Replay](../backtests/v8/reports/paper-portfolio-parity-20260915.json).
Nächste Strategiearbeit muss verlustreiche Einstiege und überlappende Positionen
im gemeinsamen Portfolio verbessern und zeitlich getrennt validieren. Keine
spätere Verbesserung als bereits erreicht oder livefreigegeben ausweisen.

## Istzustands-Abgleich und Laptop-Neustart, 15.09.2026

Eigentümerauftrag: eine zentrale Strategie, nicht unabhängige Tuning-Regeln für
Paper, Portfolio und Einzeltests. Verbindliche Einordnung und Grenzen: DMS 06.
Die ausdrückliche Reparaturfreigabe gilt als auftragsbezogene Ausnahme von der
AGENTS-Lernphase; `bootstrap_complete` bleibt false. Kein Echtgeldauftrag.

Behoben wurde die fehlende Einordnung gespeicherter Ergebnisse: Die UI zeigt
jetzt Übereinstimmung, Abweichung oder fehlenden Nachweis gegenüber aktivem
Profil, Quote, Python-Quelltext und Kostenmodell; im Portfolio zusätzlich
Startkapital, Slots und Positionsbetrag. Historische Berichte bleiben erhalten.
Ein Dateipatch während des Betriebs erzwingt vor dem nächsten Backtest einen
Neustart, damit nicht alter geladener Code mit neuem Datei-Hash bescheinigt wird.
Der Vergleich bestätigt keinen Binance-Orderpfad und keine künftige Rendite.

20 neue kontrollierte Paritätstests (zehn Coins, jeweils Baseline/Stress)
vergleichen tatsächliche Einzel-/Portfolio-Engines: gleiche Signale, Fills,
Trades und Endwerte bei gleichen Kapitalbedingungen. Der Portfolio-Risikoschutz
ist **nur in diesem Vergleichstest** deaktiviert, um das Einzeltestmodell
abzugleichen, nicht im laufenden Bot. Vollständige Paper-/Live-/Restart-Parität
ist damit ausdrücklich noch nicht abgenommen.

Alter USDT-Referenzlauf `56a34f10-58fa-4968-9b24-59e430196c6d` mit aktuellen
Rechenregeln nachgerechnet: alle ursprünglichen Kerzen-Hashes identisch;
Baseline **733,30648172557635 USDT / 187 Abschlüsse**, Stress
**564,8193836271619 USDT / 25 Abschlüsse**, numerisch wie die Referenz.
Für die inzwischen USDC-validierende Engine wurden ausschließlich Symbolnamen
in der separaten In-Memory-Kontrollrechnung angepasst; Preise und wirtschaftliche
Quote bleiben USDT. Dies ist kein echter USDC-Lauf und kein veröffentlichtes
UI-Ergebnis. Nachweis: [Referenz-Replay](../backtests/v8/reports/portfolio-reference-replay-20260914.json).
Die dortigen String-Differenzen betreffen Nachkommastellenformat, nicht Zahlen.
Der historische USDT-Zeitraum beginnt September 2023; echte gemeinsame USDC-Daten
inklusive Warm-up erlauben erst März 2024. Zusätzlich können Unterschiede der
Paar-Kerzen Cross-Signale verändern. Ein bloßer Quote-Wechsel garantiert daher
keine nur geringfügige Ergebnisänderung.

Tatsächliche Installation am 15.09.2026 um 08:39:57 Europe/Berlin über ihre
vorhandene Startbot.bat in sichtbarer Konsole gestartet; sichtbarer Bot-Tab
verbunden. HEALTHY / PAPER / LIVE_DISABLED, zehn Märkte, Binance-WebSocket aktiv.
Kein Kontoreset: 3×80, eine offene SOL-Position und ein abgeschlossener XRP-Trade
bleiben erhalten. V6-Profile unverändert; V8-Kandidaten weiterhin abgelehnt.

Beide normalen Backtest-Modi über die laufende API vollständig neu berechnet,
jeweils Baseline und Stress, Fenster **24.03.2024 01:00 bis 15.09.2026 08:00
Europe/Berlin, Ende exklusiv**. Das sind verfügbare rund 2,5 Jahre, nicht drei.
Beide melden `MATCHING`; Python-Hash:
`343d2ef7a43e770c78dd70ec8a2faec94c858932192c0f21e66a1af437cef19f`.

| Prüfmodell / Run | Start | Baseline Ende | Trades | Max. DD | Stress Ende |
| --- | ---: | ---: | ---: | ---: | ---: |
| 3×80 / `8b9018d0-3914-4af2-831b-a8904c3ea64a` | 250 USDC | 203,72 | 14 | 20,83 % | 203,33 |
| 10×250 isoliert / `e5729c9f-b72d-465d-8fee-58739096f581` | 2.500 USDC | 4.004,18 | 443 | 25,72 % zusammen | 3.318,63 |

Portfolio-Baseline stoppt neue Entries ab **01.05.2024 21:59:59,999 Europe/Berlin**
wegen 20-%-Drawdown; kein Laufzeitfehler oder Haltefreigabe durch positive
Einzeltests. Der Kontosaldo verändert sich danach noch durch bewertete Restmengen.
Die 10×250-Summe ist weder das Konto des 3×80-Bots noch seine erwartete Rendite.

| Coin isoliert | Baseline Ende USDC | Abschlüsse | Max. DD |
| --- | ---: | ---: | ---: |
| ADA | 336,31 | 49 | 50,77 % |
| AVAX | 183,70 | 36 | 54,10 % |
| BNB | 264,94 | 37 | 44,62 % |
| BTC | 349,00 | 35 | 28,29 % |
| DOGE | 633,36 | 38 | 34,04 % |
| DOT | 163,19 | 50 | 74,17 % |
| ETH | 573,69 | 30 | 32,51 % |
| LINK | 375,36 | 46 | 46,16 % |
| SOL | 571,80 | 49 | 21,71 % |
| XRP | 552,81 | 73 | 36,81 % |

Prüfstand: **333 Python-Tests bestanden, ein Skip; 21 UI-Tests**, Ruff, mypy
(54 Quelldateien), TypeScript und Produktionsbuild bestanden. Neue UI am
laufenden Laptop kontrolliert. Noch keine robuste Portfolio-/Echtgeldfreigabe;
keine Änderung von Schutzgrenzen zur künstlichen Verbesserung des Ergebnisses.

## Schwachstellenprüfung V8, 14.09.2026 – keine Aktivierung

Mit ausdrücklicher Eigentümerfreigabe wurde die noch offene AGENTS-Lernphase
für diese getrennte Forschungsarbeit ausgenommen, nicht als abgeschlossen
markiert. DOT/AVAX/BNB: sechs vorab festgelegte Profile je Coin, Auswahl nur auf
zwei Trainingsabschnitten. 88 Einzelrechnungen und acht 3×80-Rechnungen mit den
vorhandenen Decimal-Engines, echten USDC-Kerzen und aktivem Risikoschutz.
Die sieben anderen Coinprofile und alle laufenden Konten blieben unverändert.

Ergebnis: kein bestandener Kandidat. AVAX verbessert sich im Gesamtfenster mit
4-ATR-Stop von 182,09 auf 361,15 USDC, aber der spätere Validierungsneustart
verliert weiterhin. DOT bleibt auch insgesamt negativ, BNB verschlechtert sich
im späteren Fenster. Gemeinsames Portfolio Gesamt-Baseline unverändert
203,71 USDC / 14 Abschlüsse / 20,83 % Max. Drawdown / Risikohalt; im späteren
Fenster sinkt es mit einem zusätzlichen Trade von 220,72 auf 217,16 USDC.

Der vollständige festgeschriebene Prüfplan, Kosten-Stress, alle zehn Coinprofile,
abgelehnte Varianten und Nachweisgrenzen stehen in
[V8](../backtests/v8/README.md). Keine historische Simulation als Prognose oder
Echtgeldausführungsfreigabe ausweisen. Fenster 24.03.2024–14.09.2026, nicht volle
drei Jahre. Neue Nachweise statt Umschreiben alter Ergebnisse; gleiches
Ergebnis trotz geändertem Code ist möglich, etwa beim gleichen frühen Risikohalt.

304 Python-Tests bestanden / ein optionaler Test übersprungen; Ruff und mypy
(53 Quelldateien) bestanden. Laufende API am 14.09. um 21:28 Berlin:
HEALTHY / PAPER / LIVE_DISABLED, 3×80, eine offene SOL-Position und ein
abgeschlossener Papertrade. Kein Einstellungswechsel, Neustart oder Echtgeldtest.

## Laptop-Abnahme 0.4.9 – gesperrter Einmaltest-Lifecycle, 09.09.2026

- Tatsächliches Desktop-Projekt auf `c6b9051` fast-forward aktualisiert, keine neue Startdatei. Sichtbare `Startbot.bat --no-browser` um **20:01:22 Europe/Berlin** gestartet, Server PID 11884 ab 20:01:24. Sichtbare In-App-Browserseite verbunden. Ab **20:02:18 HEALTHY / PAPER / LIVE_DISABLED**, Binance-Marktdatenstream verbunden, kein Runtimefehler. API meldet `runtime_connected=true`, `balance_conservation_connected=true`, jedoch ausdrücklich `production_submission_accepted=false`, `trial_dispatch_available=false`, `ready=false`.
- Backup `backups/hixton-usdc-before-v049-20260909.sqlite3`, SHA-256 `6a2c4430ea34946ae0b10dce428fcd92ec6203c1613106ffff4586b03be6a038`; bestehende Vorbereitung separat in `backups/live-preparation-before-v049-20260909.sqlite3`, SHA-256 `f62579667246f4e2b7bfceb2b16df5dd422365280d38dcb2484774677025e41f`. Beide Integritätsprüfungen `ok`; kein Überschreiben älterer Backups, kein Export privater Daten nach GitHub.
- Kein Kontoreset: Paper 250 USDC Cash/Equity, 3×80, keine Positionen und keine abgeschlossenen Trades, ursprünglicher Soak-Start 08:19:54 erhalten. Die während der Arbeitsunterbrechung neu geschlossene Stunde wurde regulär nachgezogen: 11 → 12 verarbeitete Bars pro Coin. Deshalb vier der elf Paper-Tabellen fortgeschrieben (`paper_account`, Checkpoints, Soak und Soak-Symbole); im Account **ausschließlich `updated_at_utc` geändert**, keine Kapital-/Risikowertänderung. Die übrigen sieben Tabellen stimmen exakt mit der Sicherung überein.
- Schlüssel und Passwort weiterhin als eingerichtet sichtbar; nicht eingesehen, ersetzt oder zurückgesetzt. Die Tabellen `trial_intents`, `trial_fills`, `signal_trial` und `trial_account_baseline` enthalten **je null Zeilen**. Kein Test scharfgestellt, keine Baseline eines privaten Kontos erfasst, kein echter Binance-Auftrag gesendet. Kein externer Testnetlauf in diesem Patch.
- **292 Python-Tests bestanden / ein optionaler Vault-Test übersprungen**, sowohl in der Arbeitskopie als auch erneut direkt im Laptop-Projekt. Zusätzlich 19 UI-Tests, Ruff, mypy (52 Quelldateien), TypeScript und Produktionsbuild erfolgreich. Die zehn neuen Coin-Durchläufe sind synthetische Funktions-/Adaptertests mit gleichzeitig geprüfter Paper-Entscheidung, keine historischen Gewinnzahlen oder echten Ausführungsbelege.
- Sichtprüfung: gemeinsame Handelseinstellung 3×80 USDC unverändert, lokaler Passwort-/Schlüsselbereich vorhanden und gesperrt, Live ausdrücklich aus, Einmaltest weiterhin Vorbereitung. Backtestbereich zeigt die neue Abgrenzung zwischen gültiger Simulation und Binance-Ausführungsabnahme. Danach über **„Bot beenden“** geordnet gestoppt: bis **20:04:17** Serverprozess weg und Port 8765 frei, Testtab geschlossen. **Bot nach Abnahme aus**, keine versteckte Restinstanz.

Restarbeit vor echter Freigabe weiterhin konkret in DMS 20: direkt vor Versand wirksame Markt-/Preis-/Bestands-Gates, Restmengen-/Fremdorderbehandlung und externe Betriebs-/Testnet-Abnahme. Eine erfolgreiche Offline-Suite hebt die beiden produktiven `False`-Gates und HTTP 409 ausdrücklich nicht auf. Kein vollständiger gemeinsamer Ausführungsengine-Umbau oder Echtgeld-Ready behauptet.

## Laptop-Abnahme 0.4.8 – sichtbarer Betrieb und Instanzwechsel, 09.09.2026

- Tatsächliches Desktop-Projekt von `6f0f594` auf `a84f956` fast-forward aktualisiert. Die alte 0.4.7-Instanz wurde einmalig über vorher geprüfte eigene Prozess-/Eltern-IDs beendet; sie unterstützte das neue Abschaltprotokoll noch nicht. Keine fremden Prozesse, Binance-Orders oder Bestände verändert. Alle folgenden Starts liefen über die vorhandene `Startbot.bat --no-browser` in einer ausdrücklich sichtbaren Konsole; die Bot-Seite wurde für die Abnahme sichtbar im In-App-Browser geöffnet. Kein zweiter Starter im Projekt.
- Vorherige SQLite-Sicherung: `backups/hixton-usdc-before-v048-20260909.sqlite3`, SHA-256 `c7ba5afb185c8569043dcc74da3a8ac509ffbf9f693251a5a8b8bfd09255f646`. Nach sämtlichen Start-/Stopp-Tests **alle elf Paper-Tabellen exakt identisch**, Integritätsprüfung `ok`. Kein Kontoreset, keine neue Strategieaktivierung, keine Schlüssel-/Passwortänderung. Sicherung und Marktdaten bleiben lokal, nicht in Git.
- **Instanzersetzung:** Start 19:15:24 Berlin, Server PID 17440. Zweiter Start 19:16:47 führte zum authentifizierten Ende der alten Instanz; nach deren Prozessende neue PID 6116. Alte Server-, venv- und Launcherprozesse waren beendet. Die bereits offene UI verband sich automatisch mit der neuen Instanz und lud deren Oberfläche erneut. Kein Port-10048-Fehler, kein zweiter gleichzeitig handelnder Server beobachtet.
- **Konsolenverlust:** Bei verbundener UI wurde ausschließlich die geprüfte zugehörige CMD-Elterninstanz PID 18056 beendet. Der Server 6116 war danach beendet; um 19:17:42 kein Listener auf 8765. Dies prüft den Verlust des Konsolenprozesses; ein manueller Klick auf das Windows-Terminal-X wurde nicht separat automatisiert.
- **Zwei Tabs / Reload / letzter Tab:** Neuer Start 19:17:57, Server 15936. Zwei sichtbare Browser-Tabs ergaben zwei registrierte UI-Verbindungen. Einen Tab schließen und den verbleibenden neu laden ließ den Server mit einer Verbindung weiterlaufen. Nach Schließen des letzten Tabs war bis 19:19:37 der Server beendet, Port 8765 frei und die eigene Instanz-Metadatendatei entfernt. Keine versteckte Restinstanz blieb für den Weiterbetrieb zurück.
- **Betriebszustand vor letztem Stopp:** Seit 19:18:43 HEALTHY, V6-USDC `d57f88ec2e5f`, Paper 250 USDC Cash/Equity, 3×80, keine Positionen, Binance-Marktdatenstream verbunden, kein Runtimefehler, LIVE_DISABLED. Oberfläche zeigte die neue dauerhafte Abschalt-/Verbindungszeile und die USDC-Währung. Schließen liquidiert keine offenen Binance-Positionen; solche wären anschließend unbetreut.
- Vollständiger Codeprüfstand: 271 Python-Tests bestanden, ein optionaler Windows-Vault-Test übersprungen; die Python-Suite nach Auslieferung zusätzlich erfolgreich direkt im Laptop-Projekt wiederholt. 19 UI-Tests, Ruff, mypy (50 Quelldateien), TypeScript und Produktionsbuild bestanden. Die Browserprüfung erfolgte am echten Laptopprozess, nicht nur im Mock. Firefox-spezifisches Schließen und Stromausfall sind damit nicht als eigene manuelle Tests behauptet.
- Autorisierte Binance-Diagnose ausschließlich lesend durchgeführt. Neue Meldungen nennen konkrete ungeklärte/deaktivierte Rechte und blockierende Altbestände; der Kontocheck bleibt sicher gesperrt, solange Anforderungen fehlen. Private Kontobeträge/Schlüssel/IP-Daten gehören nicht in diese öffentliche Dokumentation. **Kein Echtgeldtest scharfgestellt oder ausgeführt, kein Dauer-Livebetrieb.** Kontoreconciler, produktiver Signal-/Exit-Anschluss und die in DMS 20 beschriebenen technischen Nachweise bleiben offen; ein korrigierter API-Schlüssel allein schließt diese Arbeit nicht ab.

## Tatsächliches USDC-Laptop-Deployment 0.4.7 – 09.09.2026

- Installation: `C:\Users\andre\OneDrive\Desktop\Der Hixton Indikator traiding BOT`, Code-Fast-forward `f976d6f` → `bc0b1215322e2b58466ba988a153ae76e0e5240e`. Der zuvor seit 08.09. laufende 0.4.6-USDT-Prozess wurde anhand seines Befehls/Pfads identifiziert und gestoppt; kein Echtgeldbetrieb und keine offenen Paperpositionen vorhanden. Ein zweiter, nur wartender Startversuch wurde beendet. Kein fremdes Programm beendet.
- SQLite-Sicherung `backups/hixton-usdt-before-v047-20260909.sqlite3`, SHA-256 `1dca195117686b08ed10019b9b628a091ab393d84ac713cb03e3a82cd4ee0d56`. Die bisherige `data/hixton.sqlite3` bleibt bestehen; nach dem neuen Start **alle elf alten Paper-Tabellen identisch zur Sicherung**. Keine USDT-Zahlen umbenannt, keine alten Positionen/Fills als USDC übertragen.
- Neue `data/hixton-usdc.sqlite3` aus der vorhandenen öffentlichen USDC-Prüfdatenbank mittels SQLite-Backup vorbefüllt. Quelle enthielt ausschließlich öffentliche Daten und keine Paperkontotabellen. Danach reguläre Startup-Synchronisation und frisches, getrenntes 250-USDC-Modellkonto. Die vollständigen Sicherungen/Kerzen bleiben lokal und Git-ignoriert.
- **Tatsächlich vorhandene `Startbot.bat` gestartet**, Serverprozess 28948 ab **09.09.2026 08:19:05 Europe/Berlin**, Startup-Sync fertig **08:19:54**. Anwendung 0.4.7, V6 `HIXTON-V6-COIN-PAPER-1-d57f88ec2e5f`, HEALTHY / PAPER / LIVE_DISABLED, WebSocket verbunden, kein Runtimefehler. Startprotokolle unter `data/startup-v047.log` und `data/startup-v047-error.log`, keine zusätzliche Startdatei.
- Paper bei Abnahme: 250 USDC Cash/Equity, 3×80, zehn Marktquellen, null Positionen/abgeschlossene Trades, kein Tages-/Drawdown-Halt. Separater USDC-Soak beginnt mit dieser Aktivierung; alte USDT-Betriebstage zählen nicht als USDC-Abnahme. Keine historischen Signale nachgehandelt.
- **50/50 Chart-API-Kombinationen** verfügbar: BTC, ETH, BNB, SOL, XRP, ADA, LINK, AVAX, DOT und DOGE gegen USDC × Heute/Woche/Monat/Jahr/3 Jahre. Bei Prüfung 9/168/720/2191/917 Anzeigebars je Coin. Langansicht nutzt die tatsächlich vorhandene gemeinsame Historie, nicht erfundene volle drei Jahre. Historische Signalmarker vorhanden, keine neuen Paperfills behauptet.
- Laufende Browseroberfläche geprüft: Übersicht zeigt zehn USDC-Marktkarten/DATEN OK, Chart-Auswahl zehn USDC-Paare, Monats-/Langansicht mit Candlesticks und Signalen, Einstellungen mit USDC-Beträgen und vorhandenem Schlüssel-/Passwortstatus. Schlüssel nicht ausgelesen/erneuert. Freischaltung bleibt an das bereits eingerichtete lokale Passwort gebunden.
- Python-Offline-Tests erneut **direkt im Laptop-Projekt** vollständig bestanden (262 bestanden, ein opt-in Windows-Vault-Test übersprungen). Kein privater Binance-Auftrag, kein Test-Trade und kein Dauer-Live gestartet. Die in DMS 20 aufgeführten fehlenden Runtime-/Konto-/Restmengen-/Testnet-Nachweise bleiben echte offene Arbeit; dieser Deploymentnachweis ist **keine Echtgeldfreigabe**.

## Direkter Paper-/Backtest-Spiegelnachweis – 08.09.2026

Abschließender Nachtrag: 224 Python-Tests in der Arbeitskopie, ein opt-in Vault-Test übersprungen; 16 UI-Tests. Laufende Laptop-API: 50/50 Chartkombinationen mit Daten, zehn valide Märkte und letzte Signalzeiten. Backtest-CLI-Größenkorrektur betrifft neue Aufrufe, nicht die bereits unverändert laufende Paperstrategie. Keine erneute Strategieaktivierung erforderlich.

Auf Eigentümerrückfrage ausdrücklich **den aktiven USDT-Bot** geprüft, nicht USDC-V7 mit V6 verwechselt. Alle zehn von `/api/markets` gemeldeten Coin-Parameter und Zusatzregeln stimmen mit `HIXTON-V6-COIN-PAPER-1-9734f240e873` überein. Gespeichert 3×80, Cash-Neustart 250, Einstiegspause aus.

| Prüfung | Ergebnis |
| --- | --- |
| Alter Zeitraum 06.09.2023 13:00–06.09.2026 13:00 UTC neu gerechnet | **739,51593332654975 USDT**, exakt identisch zum alten Run; auch Stress exakt **573,5368270751159** |
| Aktuelle drei Jahre 08.09.2023 11:00–08.09.2026 11:00 UTC | **742,60147103788215 USDT**, 192 abgeschlossene Trades, +197,04 %, maximaler Drawdown 21,54 % |
| Tatsächliche Paper-Engine separat über dieselben drei Jahre abgespielt | **384/384 Fills exakt gleich**: Signal-ID, Zeit, Preis, Menge und Gebühr; Equity-Differenz **0** |
| Tatsächliche Paper-Engine neu in Cash ab realer Aktivierung 06.09.2026 13:14:58.869511 UTC | **0 neue Trendwechsel bei allen zehn Coins, 0 Fills, 250 Equity**, identisch zum laufenden Paperkonto |

Neue volle Drei-Jahres-Referenz `backtests/v6/runs/9cda3e2f-5120-4ceb-8e0b-9e777d8ba48d/`, Wiederholung des alten Zeitraums `e668d192-1432-42f8-9cae-aac46a1d8f21` gegenüber altem `d97de0ed-733b-4b0b-891d-5b8fa3202fe8`. Baseline 3×80 identisch in CLI/UI und gespeicherten Settings. Sämtliche Schattenkonten lagen in eigenen temporären SQLite-Dateien, nicht im Betreiberkonto. Beide Simulatoren verwendeten echte identische USDT-Kerzen, 400 Warm-up-Bars, aktuelle gleiche Filter, die zehn individuellen Profile und gemeinsame Risikoregeln. Modellparität ist kein Nachweis tatsächlicher Binance-Fills.

**Einordnung:** Der Backtest spiegelt die aktuellen Handelsregeln, aber startet historisch 2023; das reale Paperkonto wurde 2026 frisch in Cash begonnen. Es übernimmt weder alte Positionen noch bereits erzielte Gewinne oder einen historischen Risikohalt. Der positive volle Verlauf kann deshalb gleichzeitig mit einem negativen Neustart ab März 2024 bestehen. Der volle Baseline-Run erreicht am 26.03.2026 05:59:59.999 UTC den dauerhaften Entry-Halt; die drei Jahre sind kein Nachweis ununterbrochen profitablen Dauerhandels. Sein Endwert besteht aus **709,37 Cash plus 33,23 bewerteten Restmengen**, nicht aus 742,60 frei handelbarem Cash. Keine Zwangsliquidation/Umwertung vorgenommen.

Zusätzlich eine echte, **nicht für die aktuelle Handelspause ursächliche** Inkonsistenz behoben: Der CLI-Portfolioaufruf verwendete bislang die Installationsdefaults für Slots/Betrag, während die UI bereits gespeicherte Handelseinstellungen nutzte. CLI liest jetzt ebenfalls gespeicherte Größen; nur ohne initialisierte Paper-Settings gelten explizite Configdefaults. Regression mit gespeichertem 4×45 gegenüber Config 3×80, in beiden Kostenszenarien, ohne Änderung des Kontos. Einzeltests bleiben absichtlich 1×250. Vorhandene 3×80-Ergebnisse werden dadurch nicht geändert.

## USDC-Validierung und Laptop-Abnahme 0.4.6 – 08.09.2026

- Code `81a8fb84cada14ea4172c908972df8997ea97711`, DMS 1.11.0 / DEC-052. Kanonische V7-Prüfung `385bc1f7-4dca-4dcd-a138-3c33bd9c7da8`: echte öffentliche USDC-Kerzen, unveränderte V6-Coin-Profile, keine Optimierung. Vollständige Einzelergebnisse und Grenzen in [V7](../backtests/v7/README.md), kompakter JSON-Nachweis dort. Kein privater Binance-Request/Orderversand für diesen Backtest.
- Keine vollen drei gemeinsamen Jahre: Start nach Datenverfügbarkeit und 400 Warm-up-Bars am 24.03.2024 00:00 UTC, Ende 08.09.2026 06:00 UTC. Portfolio 250/3×80 Baseline **203,83 USDC (−18,47 %)**, Stress **203,44**. 365 Tage **211,01 / 204,99**; 90 Tage **263,83 / 257,19**. USDT-Kontrolle mit identischen Fenstern **201,24 / 198,15**, **232,62 / 227,20**, **259,24 / 248,94**. Ein alter positiver Drei-Jahres-Run darf nicht als USDC- oder beliebiger Startnachweis übernommen werden.
- AVAX/DOT in allen drei USDC-Einzelfenstern negativ. Langes Portfolio 14 abgeschlossene Trades, früher Entry-Halt. Jüngstes Fenster trotz positiver End-Equity **−23,51 USDC aus abgeschlossenen Trades**, drei Positionen offen. Ergebnis enthält deren Bewertung und Restmengen. Keine Live-/Robustheitsfreigabe, kein Nachweis täglich zuverlässiger Gewinne.
- Laptop gezielt über vorhandene `Startbot.bat` neu gestartet am 08.09. um **13:32:41 Europe/Berlin**, Serverstart **13:32:43**, Prozess 19036. Sicherung `backups/hixton-before-v046-20260908.sqlite3`, SHA-256 `a1f561fb173801f8e2cba20b5856c2698a7cf87855808884ffbb32c9350258bb`, Integrität `ok`. Unmittelbar nach Start **alle elf Paper-Tabellen identisch**. Keine Schlüssel-/Passwortänderung, kein Cashreset und keine Strategieaktivierung.
- Nach Synchronisation **HEALTHY / PAPER / LIVE_DISABLED**, Stream verbunden. Weiter V6-USDT, 250 Cash/Equity, drei freie Slots, null abgeschlossene Trades. Soak bleibt seit 06.09. 15:16:26, zuletzt 46 neue abgeschlossene Bars je Coin. Keine Tagespause, kein Risikohalt; die letzten Trendwechsel aller zehn liegen vor der Aktivierung. DOT zuletzt 06.09. 12:59 Europe/Berlin, Aktivierung erst 15:14:58. Kein Nachkaufen alter Signale.
- **222 Python-Tests**, ein opt-in Vault-Test übersprungen; **16 UI-Tests**, Ruff, mypy (47 Dateien), TypeScript und Produktionsbuild bestanden. Browser zeigt zehn aktuelle Marktkarten mit letztem Signalzeitpunkt und Hinweis „Grüner Trend ≠ neuer Kauf“; Cash und Profil unverändert. Neues JS-Bundle `index-Dg8zueNR.js`, nur ein aktuelles JS-/CSS-Paar; alter Build in Git wiederherstellbar.

Offen bleiben vollständige USDC-Runtime-/Ledger-/UI-/Kontoprüfmigration, produktiver Binance-Orderadapter, Ausführungs-/Restart-Abgleich und Echtgeldabnahme. **Kein 50-USDC-Test gestartet, kein 3×80-Livebetrieb.** Diese Grenze ist unabhängig von der erfolgreichen technischen Abnahme dieses Diagnose-/Forschungsupdates.

## Einstellungen und Binance-Vorprüfung – Laptop-Abnahme 0.4.5, 08.09.2026

- Ausgelieferter Code `d8f9528`, enthält auch den zuvor lokal ausgelieferten 0.4.4-Stand `f1e7f6b`. Bestehender Branch, sauberer Fast-forward, keine zusätzliche Startdatei. Vor Auslieferung war auf Port 8765 kein Bot-Listener erreichbar; kein fremder Prozess beendet. Start über `Startbot.bat` um 07:19:41 Europe/Berlin, Serverstart 07:19:43.
- Backup `backups/hixton-before-v045-20260908.sqlite3`, Integrität `ok`, SHA-256 `bf8fd2b3ccd6f35ff5241f232e31f98de7df85b71d67a848e5935348b2a68336`. Unmittelbar nach Start alle elf Paper-Tabellen identisch zum Backup. Keine Passwörter oder API-Schlüssel gelesen, geändert oder veröffentlicht; Status meldet beide weiterhin eingerichtet.
- Nach Synchronisation HEALTHY / PAPER / LIVE_DISABLED, Binance-Stream verbunden, alle zehn Coin-Karten DATEN OK. Gespeichert unverändert 3×80, Cash 250 USDT, keine Positionen/abgeschlossenen Trades. Soak unverändert seit 06.09. 15:16:26; danach 40 geschlossene Bars je Coin. Kein Reset, kein Echtgeldauftrag und kein Profitnachweis.
- 207 Python-Tests auch im Laptop-Projekt bestanden, ein opt-in Vault-Test übersprungen. Arbeitskopie zusätzlich 15 UI-Tests, Ruff, mypy, TypeScript und Produktionsbuild bestanden. Nur aktuelle JS-/CSS-Bundles vorhanden; vorherige Builds in Git wiederherstellbar, Daten/Backtests/Backups nicht gelöscht.
- Browser geprüft: drei geordnete Einstellungsbereiche, bearbeitbarer 5×50-Entwurf ohne 240-Grenzfehler, gemeinsamer Live-Entwurf neben unverändertem 3×80-Speicherstand, eindeutig markiertes „Live ist aus“ ohne grünes Live-an, ein ausdrücklicher 50-USDT-Einmaltestbutton ohne Checkbox. Entwurf anschließend durch Reload verworfen, **nicht im Betreiberkonto gespeichert**. Passwort-/Key-Felder gesperrt bis zur Betreiberentsperrung; gespeicherter Schlüsselstatus sichtbar. Privater Login-/Kontoprüf-/Startablauf nur mit isolierten Fixtures geprüft, nicht mit Betreibergeheimnissen.
- Binance-Defekt separat öffentlich ohne Authentifizierung reproduziert: alte `symbols`-Serialisierung HTTP 400 / -1100; kompakte Serialisierung HTTP 200, zehn Symbolantworten. Die Rechte-/Saldo-/IP-Prüfung des Betreiberaccounts steht nach Update erneut durch den Betreiber an. Produktiver Orderadapter und Konto-/Runtime-Reconciliation bleiben offen; UI-Korrektur oder öffentliches HTTP 200 sind keine Echtgeldfreigabe.

Ältere datierte Abnahmen und Grenzen unten bleiben Historie. Kein Strategiebacktest neu berechnet; Coin-Profile und Signalregeln in diesem Update unverändert.

## Gemeinsame Einstellungen – Laptop-Abnahme 0.4.3, 07.09.2026

- Code `a5952af8da5b92e943482601e481a3969557763d`, unveränderter Projektbranch. Nach geprüftem Fast-forward Neustart über `Startbot.bat` um **18:59:50 Europe/Berlin**, keine zusätzliche Startdatei. Backup `backups/hixton-before-v043-20260907.sqlite3`, Integrität `ok`, SHA-256 `0c101dee1be9ef4d7f05ce5f4f463044fb70a71b21b734afe76bf3924306ff50`.
- Nach Start **alle elf Paper-Tabellen identisch** zum Backup. Um 19:01 Anwendung 0.4.3, HEALTHY/PAPER/LIVE_DISABLED, Cash/Equity 250 USDT, null Positionen/abgeschlossene Trades, unverändert 3×80 und Einstiegspause aus. Soak weiter seit 06.09. 15:16:26, zu diesem Zeitpunkt 27 neue geschlossene Bars je Coin. Kein Reset, kein zusätzlicher Cash und kein echter Orderversand.
- **196 Python-Tests auch auf dem Laptop bestanden**, ein opt-in Vault-Test übersprungen. Arbeitskopie zusätzlich sieben UI-Tests, TypeScript, Ruff, mypy und Produktionsbuild bestanden. Genau ein aktuelles JS-/CSS-Bundle; alte Builds durch Git ersetzt und dort wiederherstellbar. Keine Daten/Backups/Forschungsbelege gelöscht.
- Sichtbar auf dem laufenden Bot geprüft: eine gemeinsame Einstellungsgruppe; 1×50-Eingabe erscheint direkt auch bei Live als Entwurf, während gespeichert 3×80 bleibt; Entwurf über mehrere Statuspolls erhalten. Inline-Bestätigung nennt exakt 1×50 ohne vorzeitige Speicherung. 5×80 zeigt klar die bestehende 3/240-Grenze, statt erfolgreiche Übernahme vorzutäuschen. Verwerfen setzt Eingabe und gemeinsame Anzeige auf den echten Speicherstand zurück. Kein testweises Speichern im Betreiberkonto, kein Passwort/Key eingegeben. Browserkonsole ohne Warnung/Fehler.
- Kein neuer Strategiebacktest nötig für diese Einstellungs-/Darstellungskorrektur; die Coin-Profile und Handelslogik wurden nicht verändert. Kein Nachweis identischer Live-Fills oder künftiger Profitabilität; produktiver Echtgeldadapter/Abgleich bleibt offen.

## Laptop-Abnahme 0.4.2 – 07.09.2026

- Ausgelieferter Code `994627f574dad21beadd6997a3211d6eead38afd`, bestehender Branch `codex/build-foundation-v1`, Fast-forward ohne Überschreiben fremder Änderungen. Neustart am 07.09. um **14:12:17 Europe/Berlin** über die unveränderte `Startbot.bat`; Anwendung meldet 0.4.2. Keine zusätzliche Startdatei.
- Vorheriges SQLite-Backup: `backups/hixton-before-v042-20260907.sqlite3`, SHA-256 `b2987e8b4b72a8cf3f56cb7ddf71bf889161298daecde5c08b2bd27a2bdc9434`. Nach Start Integrität `ok`, **alle elf Paper-Tabellen identisch** zum Backup. Konto, Einstellungen, Ereignisse und Soak unverändert; weder Reset noch künstliche Einzahlung.
- Status um **14:16 Europe/Berlin**: `HEALTHY / PAPER / LIVE_DISABLED`, Binance-WebSocket verbunden, V6 `HIXTON-V6-COIN-PAPER-1-9734f240e873`, Cash/Equity 250 USDT, PnL 0, keine offenen Positionen oder abgeschlossenen Trades. Gespeichert 3×80; 23 neue geschlossene Bars je Coin seit dem unveränderten Soak-Beginn 06.09. 15:16:26. Noch kein Paper-Profitnachweis.
- **190 Python-Tests** auf Arbeitskopie und Laptop bestanden, ein opt-in Windows-Vault-Test übersprungen. Vier UI-Tests und TypeScript-Prüfung in der Arbeitskopie bestanden; dort auch Ruff, mypy (45 Source-Dateien) und Produktionsbuild erfolgreich. Der Laptop verwendet das gebaute UI-Bundle, keine separate UI-Entwicklungsinstallation.
- Alle **50/50 Chart-API-Kombinationen** (zehn Coins × Heute/Woche/Monat/Jahr/drei Jahre) erneut mit Daten geprüft. Sichtprüfung am laufenden Laptop-Bot: API-Key/Secret bereits vor Entsperrung erkennbar und deaktiviert, lokale Passwortschritte, separater 50-USDT-Testbereich, Live-an/aus-Bereich und korrekte gespeicherte 3×80-Vorlage. Bestehende Optik beibehalten; Browserkonsole ohne Warnungen/Fehler. Kein Passwort oder Binance-Key durch den Agenten eingegeben.
- **Nur weiterer Entwicklungs-Teilstand:** Die 25 neuen Einmaltest-Tests verwenden eine Fake-Börse. Der persistente Testcontroller ist noch nicht an den produktiven Binance-Orderversand/Runtime-Reconciler angeschlossen. Die neuen Test-/Live-Buttons melden deshalb fehlende Freigabe und lösen keinen Echtgeldauftrag aus. Echte Positionsanzeige, Binance-Ausführungsabnahme und normaler Mehrslot-Livebetrieb bleiben offen; Fortsetzung in DMS 20. Kein neuer Backtest und keine Änderung der aktiven Strategieparameter in dieser Lieferung.

## Live-Vorbereitung und unveränderter Paperbetrieb – 06./07.09.2026

- **Laptop-Abnahme 0.4.1, 07.09.2026:** Code `6e256152ff02eb89c06e9e9e56681b51c24c1cd5`, Fast-forward des bestehenden Branches, Neustart um 08:09:56 über `Startbot.bat`. Vorheriges geprüftes Backup `backups/hixton-before-v041-20260907.sqlite3`, SHA-256 `58c506e7a4d9e1167df091a38c0443e0e40531adc9f8926911bbae1d1709a812`. Nachher Integrität `ok`, alle elf Paper-Tabellen identisch zum Backup, 158 Tests auch im Laptop-Projekt bestanden (ein opt-in Test übersprungen). Um 08:12 HEALTHY/PAPER/LIVE_DISABLED, 250 USDT, 3×80, 17 neue Bars je Coin, unveränderter Soak-Beginn. Alle **50/50 Chart-API-Kombinationen** liefern Daten. Gerendert geprüft: 1×50-Entwurf, passende Inline-Bestätigung ohne Speichern, Polling-Erhalt, Verwerfen zurück auf 3×80 und neue Eingabefelder in bestehender Optik. Browserkonsole ohne Warnung/Fehler. Genau ein aktuelles JS-/CSS-Bundle; alte Bundles durch Git-Update ersetzt, über Git wiederherstellbar. Keine alten Konten, Forschungsbelege oder Marktdaten gelöscht.
- Anwendung 0.4.0 (`34f52f2`, danach UI-Korrektur `27c5a73`): Paper-Entwürfe werden nicht durch Statuspolling überschrieben; persistentes 1×50 samt Neustart ohne Kontoveränderung in isolierten API-Tests bestätigt. Laptop wurde nicht auf 1×50 umgestellt. Eigener Passwort-/Windows-Key-Bereich und ausschließlich lesender Binance-Vorcheck; weiterhin `LIVE_DISABLED` ohne echten Dispatcher.
- Vor dem normalen Neustart: `backups/hixton-before-v040-20260906.sqlite3`, Integrität `ok`, SHA-256 `ca38093ba7147d8eb66a425efc0e868114cde3c0a29ff5c672ffff0182a844c6`. Anschließend alle elf `paper_*`-Tabellen gegen diesen Snapshot identisch geprüft. Ein Starter, keine neue Paper-Session und kein erneuter Fresh-Start.
- 137 Python-Tests auf Arbeitskopie und Laptop bestanden; ein opt-in Windows-Vault-Test im normalen Lauf übersprungen. Der native Vault-Rundlauf wurde separat mit genau einem künstlichen, anschließend entfernten Eintrag bestanden. Kein echter Binance-Key wurde durch den Entwicklungsagenten eingerichtet und keine private Konto-/Orderabfrage ausgeführt.
- Sichtprüfung entdeckte, dass der eingebettete Browser `window.prompt()` nicht unterstützt. Ab `27c5a73` erfolgt Bestätigung direkt im Formular; Entwurf 1×50 blieb nach mehreren Polls erhalten, Anwenden zeigte die richtige Zusammenfassung ohne vorzeitigen Schreibzugriff. Die drei UI-Tests sichern auch den Verzicht auf native Prompt-/Confirm-Dialoge ab.
- Betrieb am **07.09.2026 um 08:02 Europe/Berlin**: `HEALTHY / PAPER / LIVE_DISABLED`, V6, 250 USDT Cash/Equity, PnL 0, null offene Positionen und abgeschlossene Trades. Weiterhin 3×80, Aktivierung 06.09. 15:14:58, Soak seit 15:16:26; mittlerweile 17 neue geschlossene Bars je Coin. Nächtlicher Daten-Audit um 02:06 abgeschlossen. Das ist ein Betriebsnachweis, noch kein Profit- oder Live-Nachweis.
- Entwicklung 0.4.1: 21 zusätzliche Offline-Orderjournal-Tests, insgesamt **158 bestanden / ein opt-in Test übersprungen**; Ruff, mypy (44 Source-Dateien), drei UI-Tests, TypeScript und Produktionsbuild bestanden. Fake-Börse prüft Doppelstart, Timeout, Neustart, Teilfills, Gebührenwährung, fehlende Filldetails und unveränderliche Identitäten/Endzustände. **Keine Binance-Testnet-/Echtgeld-Ausführungsabnahme.** Neue UI-Text-/Passwortfelder behalten die bestehende Optik. Kein neuer Backtest und keine Strategieänderung in dieser Lieferung.

## UI-Bereinigung abgenommen – 06.09.2026, Anwendung 0.3.2

- Code `2b8611a5d510f1236037bcf6f0e9c61924469251`: Liste und Tabelle gemeinsam nach Version/Testart/Einzelcoin gefiltert, neuester passender Lauf sichtbar, Historie eingeklappt. Keine historischen Dateien gelöscht und keine Handelsparameter geändert.
- Eigentümerläufe bleiben erhalten: V6-Batch `5a194dd7-ee6f-459b-be2e-c9ac8995c488`, V6-Portfolio `d97de0ed-733b-4b0b-891d-5b8fa3202fe8`. Letzterer verwendet **06.09.2023 13:00 bis 06.09.2026 13:00 UTC**, endet unter Baseline bei **739,52 USDT / 193 Trades / 21,66 % maximalem Drawdown**, mit Risikohalt am 24.03.2026. Er ist kein Widerspruch zum reproduzierten 733,31-USDT-Lauf: anderer Fensterbeginn, anderes Warm-up und andere historische Signalsequenz. Die UI nennt jetzt beide Fenster ausdrücklich.
- Vor normalem Neustart geprüftes Konto-Backup `backups/hixton-before-v032-20260906.sqlite3`, Integrität `ok`, SHA-256 `ac0551b298c54d5e88d10921b701bfa701578cbb1f46ed2d2a96d4afc1ac48a0`. Kein erneuter Fresh-Start-Befehl. Konto, Strategie-Session, Einstellungen, Positionen, Ereignisse, Audit und Soak-Beginn anschließend gegen Backup geprüft und erhalten.
- **107 Tests** auf Arbeitskopie und Laptop bestanden; Ruff, mypy, TypeScript und UI-Build erfolgreich. Gerendert geprüft: V6-Portfolio mit einer Karte, Aufklappen der drei älteren Portfolios, V6-Batch mit zehn Ergebniszeilen ohne Portfolio-Beimischung, leere V6-ETH-Einzelansicht ohne fremde Resultate, separate V2-Portfolioansicht und dynamische V6-Dokumentationskennung. Browserkonsole ohne Warnungen/Fehler. Vorherige unterbrochene Sichtprüfung damit ergänzt.
- Um **20:04 Europe/Berlin**: `HEALTHY / PAPER / LIVE_DISABLED`, Anwendung 0.3.2, zehn valide Märkte, **50/50 Chartkombinationen** erneut bestanden. Cash/Equity 250 USDT, PnL 0, keine offenen Positionen oder Paperfills. Kontoaktivierung weiterhin 15:14:58, Soak weiterhin seit 15:16:26, mittlerweile fünf neue Bars je Coin. Startup über die Stundengrenze wurde automatisch nachsynchronisiert; keine manuelle Soak-Rücksetzung.

## Aktueller Betrieb – ausdrücklicher V6-Neuanfang, 06.09.2026

- DEC-045 umgesetzt mit Anwendung **0.3.1**, Code `226be5ba8755727fa19b024e0efce45e4f0f0071`. V6 `HIXTON-V6-COIN-PAPER-1-9734f240e873` ist ein ausdrücklich gewähltes Paper-Experiment, keine nachgewiesen robuste oder live-reife Strategie.
- Neues Konto angelegt **15:14:58 Europe/Berlin**: Cash/Startbasis/High-Water-Mark jeweils 250 USDT, drei Slots à 80, null Positionen, null alte Ereignisse, PnL 0. Kein Verkauf alter Modellpositionen und keine Einzahlung als Gewinn verbucht.
- Vollarchiv: `backups/paper-v2-archive-20260906/hixton.sqlite3`, Integrität `ok`, SHA-256 `3c024f65a38d8c5ea196c8b19bda74782c8a084c3575d5f4488cf5cec7d9a06d`. Darin drei alte Positionen und sieben Ereignisse (fünf Fills, zwei abgelehnte Einstiege), alte Kontobasis, Checkpoints, Soak und Audit. Audit `PAPER_FRESH_START` bindet das neue Konto an diesen Nachweis.
- Ausschließlich aktive Paperdaten zurückgesetzt. Vor dem Start beide Richtungen per SQL-EXCEPT geprüft: **268.310 Kerzen**, 50 Revisionszeilen, zehn Börsenregelsätze und Schema-Metadaten identisch zum Archiv. Historische Backtest-/Git-Nachweise bleiben erhalten.
- Zwei alte `startup-execution-fix*.log` und die ungenutzte Wurzel-`build/`-Kopie liegen wiederherstellbar im selben Archivordner, letztere unter `obsolete-build/`. Keine zusätzlichen Starter oder aktive Datenbanken. Große Daten/Archive bleiben aus Git ausgeschlossen.
- Neustart über die einzige `Startbot.bat` um 15:15:45; Startup abgeschlossen und neuer Soak ab **15:16:26**. `HEALTHY / PAPER / LIVE_DISABLED`, Binance-WebSocket verbunden, zehn valide Märkte. Alle zehn API-Profile exakt gegen den eingefrorenen V6-Snapshot geprüft; **50/50 Chartkombinationen** liefern Kerzen und keine alten Paperfills. Historische Indikatorsignale bleiben absichtlich sichtbar. Übersicht und XRP-Dreijahresauswahl sichtbar geprüft; weitergehende Browserprüfung wurde zunächst durch ein Werkzeug-Nutzungslimit unterbrochen, nicht als bestanden behauptet.
- **105 Tests** auf Arbeitskopie und Laptop; Ruff, mypy (38 Dateien), TypeScript und Produktionsbuild bestanden. Failure-Injection belegt atomaren Reset-Rollback und Wiederanlauf ohne erneuten Reset.
- Tatsächlich aktive V6 ohne CLI-Strategieoverride erneut getestet: Portfolio-Run `9bfa8216-ac1a-49ce-a075-9d29c80c5395`, Fenster 01.09.2023 12:00 bis 01.09.2026 12:00 UTC, Start 250 USDT. Manifest nennt obigen Codecommit, vollständige Profile und damalige Paperfreigabe. Baseline **733,30648172557635 USDT / 187 abgeschlossene Trades**, Stress **564,8193836 USDT / 25 Trades** (gerundet); beide mit vorzeitigem Risikohalt. `metrics.json`, `trades.csv`, `equity.csv` sind bytegleich zum vorherigen Referenzrun `95c0ca16-7385-4b57-9dd1-2cc1dc3ed047`. Aktivierung verändert keine historischen Handelsentscheidungen.
- Erneute Statusprüfung um **19:47 Europe/Berlin**: weiterhin HEALTHY, Cash/Equity 250, PnL 0, keine Position, vier neue geschlossene Bars je Coin verarbeitet, kein Risikohalt. Der Bot wartet korrekt auf zukünftige qualifizierte Einstiege. Keine Aussage über künftigen Tagesgewinn.

## Neuester Prüfstand 06.09.2026 – V6-Profilvergleich

Vollständiger Nachweis: `backtests/v6/README.md` und `reports/profile-review-20260906.json`. Neue Einzelergebnisse und ein technisch funktionsfähiger Paperpfad sind **kein** Nachweis eines besseren gemeinsamen Kontos. V6 verbessert das volle gemeinsame Fenster, verschlechtert aber jüngstes und älteres Fenster gegenüber V2. Alle gemeinsamen Läufe halten risikobedingt vorzeitig; kein kontinuierlich profitabler 24/7-Dreijahresnachweis. Die folgenden V1–V5-Werte bleiben historische Artefakte mit ihrem ursprünglichen Kapital.

### Auslieferung und Laptop-Abnahme 06.09.2026

- Ausgelieferter Code: `f633f389ae9e74480ab024d0934d90b5e53c1ea7`, Anwendung **0.3.0**, bestehender Branch `codex/build-foundation-v1` / PR 2. Kein Merge fremder Arbeit und keine neue Startdatei.
- **98 Tests** auf Arbeitskopie und Laptop bestanden; Ruff und mypy (37 Source-Dateien), TypeScript und Produktionsbuild ohne Befund. Auch bei kleineren UI-Ordergrößen bleiben drei Slots die Obergrenze.
- Vor dem Fast-forward wurde nur der identifizierte Hixton-Paperprozess gestoppt. Backup: `backups/hixton-before-v030-20260906.sqlite3`, SQLite-Integrität `ok`, SHA-256 `688D93CF1C7DEB0C731AE58EC1EC03BC939D4D995A260B095C36D97F58E32689`. Backup und Kerzendaten bleiben lokal.
- Neustart ausschließlich über `Startbot.bat`. Danach `HEALTHY / PAPER / LIVE_DISABLED`, zehn valide Märkte. **Keine V6-Aktivierung.** Alle sechs Ledgerereignisse, drei Positionen (ADA/DOGE/ETH), Einstellungen und Strategie-Session wurden gegen das Backup auf Identität geprüft. Cash bleibt `0,04279731558 USDT`, historische Startbasis 240 USDT. Die neue 250-USDT-Config schenkt dem bestehenden Konto keine 10 USDT.
- Soak-Beginn bleibt 05.09.2026 13:19:05 UTC, kein Soak-Reset. Snapshot nach Neustart: rund 244,75 USDT Equity, rund +7,30 USDT offene Bewertung seit V2-Start; kein neu abgeschlossener V2-Gewinn. Kein Zukunfts- oder Tagesprofitnachweis.
- Alle **50 API-Kombinationen** aus zehn Coins und Heute/Woche/Monat/Jahr/3 Jahre lieferten Kerzen. Sichtbar geprüft: Marktprofile, V2 als aktive Backtest-Vorauswahl, V6 ausdrücklich als Forschung, Risikohalt im V6-Bericht sowie ETH-Wochenchart mit Kauf/Verkauf und Paper-Fill. Browserkonsole ohne Warnungen/Fehler; kein Redesign.
- V6-Produktionsreproduktion: Batch `20bc2a48-cc79-4761-9e49-8ca5fffde150`, Portfolio `95c0ca16-7385-4b57-9dd1-2cc1dc3ed047`, jeweils mit Code-Commit `f633f38…` im Manifest. Alle 20 Einzel-Endwerte/Tradezahlen und beide gemeinsamen Endwerte bestätigen den Review; `metrics.json`, `trades.csv` und `equity.csv` jeweils bytegleich zum ersten Durchlauf. Hashes im V6-Nachweis.
- Die ersten Reproduktionen (`e85192ad…`, `56a34f10…`) hatten wegen fehlender Git-Verzeichnisfreigabe `code_commit: UNKNOWN`. Sie bleiben unverändert, gelten aber nicht als vollständiger Provenienznachweis. Neue Runs beheben ausschließlich diese Metadatenlücke; alte Manifeste werden nicht umgeschrieben.

## Historische Einzelcoin-Forschung: V5, 05.09.2026

Alle zehn Coins wurden mit 250 USDT einzeln diagnostiziert; 348 begrenzte Kombinationen aus Hixton-Parametern und expliziten Forschungsfiltern/-Stops wurden ausschließlich anhand der ersten zwei Trainingsjahre ausgewählt. Alle zehn V2-Kurztradegruppen unter 72 Stunden verlieren in Summe, während wenige lange Gewinner das Ergebnis tragen. ETH liefert einen interessanten 24-Bar-VIDYA-Steigungsfilter (jüngstes Stressjahr 213,63→278,47 USDT), aber einen älteren Rückschritt. XRP verbessert allein alle sechs Einzel-Endwerte und Drawdowns, besteht jedoch die gemeinsame Konto- und Nachbarprüfung nicht. Details für **jeden** Coin, einschließlich ADA-/DOT-Rückschritten, stehen zentral in `backtests/v5/README.md` und `backtests/v5/reports/coin-review-20260905.json`.

Das vollständige Kandidatenportfolio endet im Dreijahresfenster bei 808,30/776,04 USDT statt V2 542,49/406,29 (Baseline/Stress), aber bei einem Start im jüngsten Jahr nur bei 202,81/202,55 statt 216,71/210,47. Ein Austausch ausschließlich von XRP verschlechtert dieses Jahr ebenfalls auf 213,15/206,73. Jeder Portfoliolauf enthält einen Risikohalt. Keine neue Paperfreigabe nach DEC-042; V2 bleibt aktiv, Live bleibt gesperrt. Endwerte mit offenen Positionen werden nicht als realisierter Gewinn ausgegeben.

Hauptmesswerte in zwei Läufen identisch; Zusatzprüfung separat gekennzeichnet. 86 Tests, Ruff und mypy (37 Source-Dateien) bestanden. Kein UI-Redesign, keine Konfigurations-/Ledgeränderung und kein Neustart des Paper-Soaks für diese Forschung. Der parallel laufende Laptop meldete am 05.09.2026 um 21:47 Europe/Berlin `HEALTHY`, `PAPER`, `LIVE_DISABLED`, zehn aktuelle valide Märkte und weiterhin drei offene V2-Positionen (ADA/DOGE/ETH). Das ist ein Betriebs-, kein abgeschlossener Profitnachweis.

Auslieferung: Forschungs-Code `f138d134715475aab3699aa830ef117fac59c05e` auf den bestehenden GitHub-Branch `codex/build-foundation-v1` gepusht und den sauberen Laptop-Ordner ausschließlich per Fast-forward aktualisiert. Beide Rohberichte liegen zusätzlich hashgeprüft unter dessen ignoriertem `backtests/v5/runs/`. Anschließend dort alle 86 Tests erneut bestanden (11,77 Sekunden), V5-CLI verfügbar, laufender Prozess weiterhin `HEALTHY/PAPER/LIVE_DISABLED`, drei Slots à 80 USDT. Kein Prozessneustart nötig: Diese Lieferung ändert weder aktive Paperregeln noch UI, Pine, Konfiguration oder Ledger; Anwendungsversion bleibt 0.2.1.

## Aktuelle Prüfung am 05.09.2026

Der laufende Laptop-Bot belegte bei der Prüfung alle drei Slots mit ADA, DOGE und ETH. AVAX war korrekt mit `NO_FREE_SLOT` blockiert; es existiert keine globale Ein-Positions-Sperre. V2 hatte drei eröffnete, aber noch keinen abgeschlossenen Trade. Am 05.09. um 15:11 Europe/Berlin betrug die modellierte Equity 236,85166839858 USDT, somit −0,59465736 USDT gegenüber dem V2-Start von 237,44632575858 USDT. Der frühere V1-Verlust von −2,55367424142 USDT ist separat zu behandeln. Offene Buchgewinne/-verluste schwanken und sind kein realisierter Profit.

Gefundene und korrigierte technische Defekte: permanent um eine Stunde verspätete Closed-Bar-Analyse; Paper-Fills zum Signalkerzen-Schlusskurs statt Folge-Open; fehlende separate Verarbeitungszeit; nicht erhaltene Mengenreste; ungenau gerasterte Paper-Chartmarker; keine fortlaufend angezeigte offene Chartkerze. DEC-040 beschreibt die Korrektur und den einmaligen technischen Soak-Neustart ohne Kontoreset. Historische Paperwerte werden nicht nachträglich verbessert und sind kein belastbarer Live-Latenznachweis.

Die V4-Prüfung hat die bisherigen V2-Dreijahreswerte exakt reproduziert, zusätzlich jeden Coin in einem neu gestarteten jüngsten Jahresfenster geprüft und 24 individuelle Kandidaten je Coin untersucht. Das jüngste Jahr verliert bei allen zehn V2-Einzelkonten auch unter Baselinekosten. Der neue Coin-Kandidat erhöht das Dreijahresportfolio, verschlechtert aber das jüngste Neustartjahr. Kein Wechsel. Alle Vergleichswerte und Grenzen stehen in `backtests/v4/README.md`; Quell-/Daten-/Kosten-/Filter-Nachweis unter `backtests/v4/reports/review-20260905.json`. Live bleibt deaktiviert.

### Abnahme des Laptop-Updates

Code `0e6c41d54642f1a42a7e3dce953fcfd9bc29810f`, Anwendung 0.2.1, am 05.09.2026 über die unveränderte `Startbot.bat` neu gestartet. SQLite-Backup vor dem Wechsel: `backups/hixton-before-execution-fix-20260905-151821.sqlite3`, SHA-256 `8F280DAB95078FE46F2A604677D00E79896EA2AFF4B0FAEA6974AB4EABBDDDAD`. Integrität `ok`; alle sechs alten Ledgerereignisse und alle drei Positionsdatensätze wurden gegen das Backup verglichen und sind identisch geblieben. Technische Soak-Epoche: 05.09.2026 13:19:05 UTC; kein Cash-/Positionsreset.

Nach dem Start: `HEALTHY`, `PAPER`, `LIVE_DISABLED`, zehn frische Symbolpreise und zehn Datenaudits ohne Lücken. Um 15:20 Europe/Berlin war die letzte abgeschlossene Kerze korrekt 14:00–14:59, nicht mehr eine Stunde zurück. 50/50 Chart-API-Kombinationen liefern Daten und zeitlich passende Fill-Buckets. Sichtbar geprüft: ADA-Wochenchart mit Kauf, Verkauf und Paper-Fill, BTC-Dreijahreschart, Coin-/Zeitraumwechsel und fertige Backtestergebnisse. Browserkonsole ohne Warnung/Fehler. Zwischenstand rund 239,17 USDT Equity bzw. +1,72 USDT V2-Buch-PnL; weiterhin kein abgeschlossener V2-Trade. Die Änderung dieser Bewertung ist kein nachträglicher Ledgergewinn: Marktkurse werden jetzt frisch statt aus der verspäteten Schlusskerze angezeigt.

Zwei weitere Läufe wurden direkt über die laufende UI gestartet und erfolgreich beendet. Gemeinsames Fenster: `[2023-09-05 13:00 UTC, 2026-09-05 13:00 UTC)`. Dies ist ein anderes Fenster als die fixierte V4-Forschung; Werte nicht still gegeneinander austauschen.

| Lauf | Baseline Ende | Stress Ende | Trades je Szenario |
|---|---:|---:|---:|
| 3×80, Start 240 USDT | 543,83 USDT | 406,67 USDT | 108 / 30 |
| 10×250, rechnerische Summe Start 2.500 USDT | 6.661,92 USDT | 5.910,45 USDT | 549 / 549 |

Portfolio-Run `5db104a2-974d-496d-a8f8-05293407aa6c`, `metrics.json` SHA-256 `7C66613D3BE632AE3083A4AC237F53948FC1536F7012DC4B2B82421A6C275707`. Batch-Run `81851f17-e401-46d3-bc92-9ee0a605a436`, `metrics.json` SHA-256 `00F44073D2B2CDE0DD23A0C7D23050D16C6AD50AB6D8D65A6D0090CF3B4A7827`. Beide Manifeste nennen den obigen Code-Commit. Der Portfoliohalt liegt unverändert am 06.02.2025 (Baseline) bzw. 05.02.2024 (Stress). Der frische Batch ist bei allen zehn positiv, aber BTC, BNB und DOT bleiben unter 500 USDT. Die jüngste Verlustperiode und alle Live-Blocker bleiben bestehen.

Die folgenden Abschnitte dokumentieren frühere Runs und damalige Abnahmen; sie ersetzen nicht die obige aktuelle Fehler- und Robustheitsbewertung.

## Wahrheitsgemäßer Ist-Stand

Am 01.09.2026 wurden der verbindliche V1-Drei-Jahres-Batch für alle zehn DMS-Märkte und ein ETH-Einzeltest erfolgreich ausgeführt. Die Strategie reagiert im Backtest deterministisch gemäß `HIXTON-SPEC-1.0`. Danach wurde V2 getrennt gegen die Eigentümer-Pine-Quelle entwickelt, reproduziert und am 02.09.2026 ausdrücklich für Paper freigegeben. Kein Ergebnis ist eine Zusage zukünftiger Gewinne oder eine Live-Freigabe.

Der technische Nachweis ist vollständig genug für Gate B:

- ausführbare Strategie- und Backtestengine vorhanden;
- 67 automatisierte Tests einschließlich V1-/Pine-v6-Golden-, Daten-, Paper-, Strategiemigration/-sperre, Portfolio-Risiko-, Restart-, API-, Reporting- und Charttests bestanden;
- je Markt 26.704 geschlossene 1h-Kerzen geprüft: 26.304 Auswertungsbars plus 400 Warm-up-Bars;
- zehn isolierte Konten à 250 USDT, ohne automatisches Compounding;
- Baseline- und Stresskosten auf Ein- und Ausstieg angewendet;
- frei wählbarer Einzeltest nachgewiesen;
- Wiederholung mit festem Endzeitpunkt erzeugte bytegleiche Kernartefakte.

## Verbindlicher Validierungslauf

| Feld | Nachweis |
|---|---|
| Batch-Run-ID | `68e84b25-91f9-4faa-9a65-a6699b8bd7d5` |
| Wiederholungs-Run-ID | `5192d8fd-7e16-41d8-b0de-214593878a76` |
| ETH-Einzeltest-Run-ID | `cb4d0b5e-b903-4bba-895f-c92a9da5c1d1` |
| Code-Commit | `3472415ec683597301eaed8c8ce930edec8804e8` |
| Strategie | `HIXTON-SPEC-1.0` |
| Config-SHA-256 | `b2d5caafab7f702cabcc872b7078d4bf199d45fd8e5c6dd25fcba52e428b5966` |
| Datenquelle | Binance Spot, öffentliche Marktdaten |
| Auswertungsfenster | `[2023-09-01 12:00 UTC, 2026-09-01 12:00 UTC)` |
| Warm-up-Beginn | 400 Stunden vor Auswertungsbeginn |
| Timeframe | 1h |
| Kapital | 10 × 250 USDT isoliert = 2.500 USDT rechnerische Summe |
| Ausführung | Signal auf Bar-Close, Fill zum nächsten Bar-Open |
| Baselinekosten | 10 bps Gebühr + 2 bps Spread + 3 bps Slippage = 15 bps je Seite |
| Stresskosten | 10 bps Gebühr + 10 bps Spread + 20 bps Slippage = 40 bps je Seite |
| Status | `VALID` gegen die eigene normative Spezifikation |

## Batch-Ergebnis

| Szenario | Start | Ende | Netto-PnL | Rendite | Trades | Max. Drawdown |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 2.500,00 | 3.387,67 | +887,67 | +35,51 % | 1.724 | 45,48 % |
| Stress | 2.500,00 | 1.681,85 | −818,15 | −32,73 % | 1.724 | 68,06 % |

Die Batchsumme ist nur die Summe zehn isolierter 250-USDT-Konten. Sie ist nicht mit dem 240-USDT-Paperkonto und dessen drei Slots gleichzusetzen.

## Baseline-Ergebnis je Markt

| Symbol | Endkapital | Rendite | Trades | Max. Drawdown |
|---|---:|---:|---:|---:|
| BTCUSDT | 277,06 | +10,82 % | 180 | 49,41 % |
| ETHUSDT | 178,27 | −28,69 % | 181 | 64,58 % |
| BNBUSDT | 341,12 | +36,45 % | 169 | 36,18 % |
| SOLUSDT | 551,83 | +120,73 % | 173 | 45,66 % |
| XRPUSDT | 485,23 | +94,09 % | 161 | 59,45 % |
| ADAUSDT | 375,10 | +50,04 % | 168 | 61,16 % |
| LINKUSDT | 170,69 | −31,72 % | 181 | 74,12 % |
| AVAXUSDT | 410,14 | +64,06 % | 172 | 45,16 % |
| DOTUSDT | 75,70 | −69,72 % | 169 | 86,16 % |
| DOGEUSDT | 522,51 | +109,01 % | 170 | 48,99 % |

Der ausdrücklich verlangte ETH-Einzeltest startete ebenfalls mit 250 USDT und lieferte bei identischem Fenster 181 abgeschlossene Trades. Baseline: 178,27 USDT Endkapital und −28,69 %. Stress: 73,92 USDT und −70,43 %.

## Reproduzierbarkeit

Der Wiederholungslauf verwendete denselben Code, dieselbe Konfiguration, dieselben Daten-Snapshots und denselben exklusiven Endzeitpunkt. Folgende SHA-256-Werte sind in beiden Runs identisch:

| Artefakt | SHA-256 |
|---|---|
| `metrics.json` | `9BDE37DE072ACFC37B9799013EC48AF32730D02CCF0DF63E0040907296467A01` |
| `trades.csv` | `3CF6AD814D1DD73E35D4689A38870FC91DB4BF31D4C0A8CF98046837A4375CAB` |
| `equity.csv` | `8FADBD9B8A89796D37A301708A8FDAAC7DCCA32FED1B10781FDABC85972FED73` |

`report.html` enthält absichtlich die individuelle Run-ID und wird deshalb nicht als bytegleiches Kernartefakt gewertet.

## Ergebnisformat jedes lokalen Runs

Jeder unveränderliche Run-Ordner enthält genau:

- `manifest.json`: Run-ID, Status, Zeitraum, Code-/Config-/Datenhashes und Szenarien;
- `metrics.json`: Batch- und Coinmetriken einschließlich Kosten, Benchmark und Monatsrenditen;
- `trades.csv`: Signal-/Fillzeiten, Mengen, Preise, Gebühren und Netto-PnL;
- `equity.csv`: vollständige Equity-Zeitreihe;
- `report.html`: lokal lesbarer Bericht.

Große, reproduzierbare Run-Dateien und Marktdaten werden nicht in Git eingecheckt. Der kuratierte, versionierte Nachweis liegt unter `backtests/v1/reports/`.

## Fachliche Bewertung und Grenzen

- Gate B ist technisch bestanden: Daten, Kosten, Regeln und Ergebnisse sind reproduzierbar.
- Die Baseline ist im Gesamtbatch positiv, aber drei von zehn Märkten verlieren Geld.
- Der Stressfall ist deutlich negativ; Gebühren, Spread und Slippage sind daher erfolgskritisch.
- Drawdowns bis 86,16 % je Coin und 68,06 % im Stress-Batch sind hoch. Ein positiver Endwert bedeutet keine akzeptable Live-Risikoeignung.
- Der Test optimiert keine Parameter und verspricht keine künftige Rendite.
- Eine Identität der Eigentümerquelle mit einem separat vertriebenen Herstellerprodukt wird ohne Herkunftsnachweis nicht behauptet.
- Parität der V2-Pythonsemantik zur vom Eigentümer bereitgestellten Pine-v6-Quelle wird durch einen unabhängigen Golden-Test geprüft; dies ist keine Behauptung über die Herkunft eines Herstellerprodukts.
- Der 240-USDT-Paperbetrieb ist implementiert, muss Gate C und den vorgeschriebenen Soak-Test aber noch bestehen.
- Echtes Binance-Trading bleibt technisch `LIVE_DISABLED` und ist nicht Bestandteil dieses Backtestnachweises.

## V2-Nachweis und Paperstatus

Der vollständige Stand liegt unter `backtests/v2/README.md`. Kandidat 1 verwendet 1h, VIDYA 6, Momentum 20, SMA 8, ATR 60 und Band 3,8. Im aktuellen Dreijahresfenster endeten die zehn isolierten 250-USDT-Konten zusammen bei 6.592,22 USDT (+163,69 %) in der Baseline und 5.843,73 USDT (+133,75 %) im Stress, jeweils mit 549 Trades. Alle zehn waren dort positiv; sieben überschritten 500 USDT.

Der Primär-Run `8dbdeb5b-a4e8-4b56-b6dc-61c7f0d54e93` und Wiederholungs-Run `a7c96450-29f6-437d-af97-402d9d9c58cc` wurden über denselben technischen Einstieg ausgeführt. `metrics.json`, `trades.csv` und `equity.csv` sind jeweils bytegleich. UI und CLI können V1/V2 getrennt rechnen und auflisten. Historische Manifeste behalten wahrheitsgemäß ihren damaligen Wert `paper_approved: false`; neue V2-Runs tragen seit `DEC-037` den aktuellen Freigabestatus.

## V2-Strategiereplay mit gemeinsam 3×80 USDT

Zunächst wurde die reine Strategie mit einem gemeinsamen Cashbestand von 240 USDT, höchstens drei gleichzeitig offenen Positionen, je Einstieg maximal 80 USDT und ohne automatische Hochskalierung gerechnet. Ausstiege erfolgen am nächsten 1h-Bar-Open vor neuen Einstiegen; bei Konkurrenz entscheidet die dokumentierte Ausbruchsstärke mit fester Coin-Tie-Break-Reihenfolge. Dieser erste Lauf enthielt noch nicht die Paper-Risikogates und heißt deshalb rückwirkend eindeutig `strategy-only`, nicht Paper-/Live-Spiegel.

| Szenario | Start | Ende | Netto-PnL | Rendite | Trades | Max. Drawdown | Profit Factor |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 240,00 | 528,38 | +288,38 | +120,16 % | 227 | 34,10 % | 1,37 |
| Stress | 240,00 | 436,31 | +196,31 | +81,79 % | 227 | 43,33 % | 1,22 |

Im Baselinefall wurde das Konto historisch mehr als verdoppelt; im Stressfall blieb es deutlich positiv, erreichte 480 USDT aber nicht. Die Baseline übertraf im selben Fenster ein gleichgewichtet gekauftes und gehaltenes 10-Coin-Portfolio von 490,90 USDT; im Stress lag die Strategie mit 436,31 USDT unter dessen 489,68 USDT. Von 781 erzeugten Order-Signalen wurden 456 ausgeführt; 325 Einstiegssignale wurden ausschließlich mit `NO_FREE_SLOT` dokumentiert und nicht später nachgeholt. Am Fensterende waren BTC und SOL noch offen und deshalb zum letzten Schlusskurs bewertet.

- Primär-Run: `4aa4d135-b077-4c29-a839-fa141952113b`
- Wiederholungs-Run: `060745da-5e9f-4445-a768-0b2c2da63851`
- Code-Commit beider Manifeste: `30c8db4d494d5f4a394fc869d40bbc2e62d59896`
- `metrics.json`: `62BE829B0B57354AB2EBD5F824C576ECEE86B6B9829ABA33382272C8820B0119`
- `trades.csv`: `47D6063FE662E0223D0A4FB3E6C27613D765E6C0C98A606DB6A47D707BB74AA0`
- `equity.csv`: `5B8994F48EC7B2756CC73B58839B7AF521F7D3A6E6FD2FAE34F3A5A15AE43E48`

Die drei Kernartefakte sind zwischen beiden Läufen bytegleich. Dieses Ergebnis beschreibt die Strategieauslastung mit 240 USDT, während der 10×250-Lauf ausschließlich die isolierte Eignung jedes Coins misst.

## Korrigierter Paper-/Live-Risikospiegel

Bei der Prüfung vor Live wurde eine Paritätslücke gefunden und behoben: Der gemeinsame Kapitallauf musste zusätzlich die bereits verbindlichen Paperregeln anwenden. Ab dieser Korrektur pausiert ein Verlust von 5 % gegenüber der UTC-Tagesstart-Equity neue Einstiege bis zum nächsten UTC-Tag; 20 % Drawdown vom globalen High-Water-Mark setzt dauerhaft `HALTED`. Ausstiege bleiben erlaubt, offene Positionen werden nicht notliquidiert.

| Szenario | Start | Ende | Netto-PnL | Rendite | Trades | Max. Drawdown | Risikohalt |
|---|---:|---:|---:|---:|---:|---:|---|
| Baseline | 240,00 | 542,49 | +302,49 | +126,04 % | 108 | 22,77 % | 06.02.2025 15:59:59,999 UTC |
| Stress | 240,00 | 406,29 | +166,29 | +69,29 % | 30 | 20,13 % | 05.02.2024 21:59:59,999 UTC |

Das höhere Baseline-Endkapital gegenüber `strategy-only` entstand nicht durch bessere Signale, sondern weil der Halt spätere Verlustphasen vermied. Danach wurden jedoch keine neuen Positionen mehr eröffnet. Im Baselinefall blockierte der Halt 307 weitere Einstiege, im Stressfall 487. Ein positiver Endwert darf daher nicht als drei Jahre kontinuierlicher Betrieb oder täglicher Profit gelesen werden.

- Primär-Run: `83b38ab1-cf26-4ab2-a4b1-6e1e290822ea`
- Wiederholungs-Run: `c908cf2f-5910-4dfe-97b0-e6c40465205d`
- Code-Commit beider Manifeste: `50c5327af42328824b9d06387d0bb19d7e9e92eb`
- `metrics.json`: `DBF2F599F533A2B8BED40DB71835DA2B197E3D9F306E12D22B6FA3D09BE5446C`
- `trades.csv`: `FFD91869C4FD3F4D24AA41F00B2758D2FE70B05FF9215D8B95FA14E1016B15D8`
- `equity.csv`: `3914FC1FDC11C24DCAD94F95D65EA29842678E3BDA25A9CB414338DE70DBCB6C`

Die Kernartefakte sind in beiden korrigierten Läufen bytegleich. Zwei ältere lückenlose Segmente bestätigen die fehlende Live-Reife: Im Segment 16.10.2021–24.03.2023 endete der Risikospiegel bei 227,42 USDT Baseline beziehungsweise 223,32 USDT Stress und hielt am 04.12.2021. Im Segment 10.04.2023–01.09.2024 endete er bei 207,24 beziehungsweise 201,90 USDT und hielt am 10.06.2023.

Der nachträglich mit identischem Fenster, Kapital und Risikomodell erzeugte V1-Vergleichsrun `70089491-f5b6-4388-a420-b2c7f4641225` endete bei 383,89 USDT Baseline beziehungsweise 343,47 USDT Stress. V2 lag damit im unmittelbaren Papervergleich um 158,60 beziehungsweise 62,82 USDT höher. Der Eigentümer ordnete deshalb die kontrollierte V2-Paperaktivierung an. Die älteren Verlustfenster – im Abschnitt 16.10.2021–24.03.2023 aggregiert nur +4,26 % Baseline und −7,82 % Stress – bleiben ein klarer Live-Blocker.

## V3-Mehrfachslot-Test verworfen

Run `76a78440-405a-4624-bc0b-7765558b801c` verwendete exakt die V2-Signale, erlaubte aber bis zu drei 80-USDT-Slots auf demselben stärksten gleichzeitigen Kaufsignal. Baseline endete bei 287,85 USDT (+19,94 %), Stress bei 282,16 USDT (+17,57 %); beide Fälle hielten am 12.10.2023 nach nur vier abgeschlossenen Positionen. Das ist deutlich schlechter als V2 `one_per_symbol`. V3 ist daher verworfen und nicht im Paper aktiv. Weitere Details stehen unter `backtests/v3/README.md`.

## Kontrollierte V2-Paperaktivierung und Ist-Stand

Am 02.09.2026 um 13:36:56 UTC wurde `DEC-037` einmalig ausgeführt. Vorher wurden alle zehn Märkte mit jeweils 26.704 lokalen 1h-Bars ohne Lücke auditiert und die SQLite-Datei lokal byte-/hashgleich gesichert. Die einzige offene V1-Position in DOT wurde mit dem Migrationsgrund `STRATEGY_SWITCH_TO_HIXTON-V2-RESEARCH-CANDIDATE-1` geschlossen; realisierter V1-Paper-PnL dieses Trades: `-2,55367424142 USDT`. Das historische V1-Entry- und Exit-Ereignis bleibt versioniert im Ledger.

Die neue V2-Session startete vorwärtsgerichtet bei `237,44632575858 USDT`, ohne offene Position und mit drei freien 80-USDT-Slots. Unmittelbar nach Aktivierung und Neustart lautet ihr eigener PnL `0 USDT`, ihre abgeschlossene Tradezahl `0`; historische V1-Ergebnisse werden nicht V2 zugerechnet. Der neue 30- bis 90-tägige Soak begann mit der Aktivierungszeit und ist ausdrücklich noch nicht erfüllt.

Die anschließende Betriebsabnahme bestätigte `PAPER`, `LIVE_DISABLED`, `HEALTHY`, zehn valide Märkte, Websocket-Feed, 50 von 50 verfügbare Coin-/Zeitraumcharts, sichtbare Strategie- und Paper-Fill-Markierungen sowie eine fehlerfreie Browserkonsole. Ein während der Abnahme beobachteter, bereits wieder verbundener Stream mit stehen gebliebenem Fehlerstatus wurde in Commit `3deea9e` behoben und durch einen Regressionstest abgesichert. Das ist ein Betriebsnachweis, kein Profitversprechen und keine Live-Freigabe.

Paperfreigabe bedeutet ausschließlich, dass V2 jetzt mit echten Binance-Marktdaten und simulierten Fills vorwärts geprüft wird. Sie verspricht keinen täglichen Gewinn, hebt keinen Risikohalt auf und erteilt keine Live-Freigabe.
