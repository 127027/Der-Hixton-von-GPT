# Core-Ausstiege und DOGE-Einstiegsfilter — 12.10.2026

Ergebnis: Ein stärkerer DOGE-Einstiegsfilter ist ein aussichtsreicher Forschungskandidat. Im untersuchten Drei-Jahres-Zeitraum verbessert er Endkapital und Drawdown gegenüber der aktuellen V8r sowohl bei normalen als auch höheren Kosten. Die vorab festgelegte Mindestsenkung des Drawdowns unter Stress wird dennoch knapp verfehlt: 4,29% relative Senkung statt mindestens 5%. Die Kriterien wurden nicht nachträglich gelockert. Der Kandidat ist nicht aktiviert und besitzt keine formale Live-Abnahme. Der laufende Bot bleibt auf V8r/LINK8/ATR075.

## Gleiche Basis für alle Vergleiche

11.10.2023 19:00 UTC bis 11.10.2026 19:00 UTC, 400 Aufwärmkerzen, Startkapital 1.092,05773944 USDC, gemeinsames 15-Märkte-Portfolio, zwei Slots, Wiederanlage, Core-Priorität, unveränderte Risikogrenzen und heutige USDC-Handelsfilter. Kosten pro Seite: normal 10 Basispunkte Gebühr + 2 Spread + 3 Slippage; Stress 10 + 10 + 20. Es wurde keine BNB-Ermäßigung vorausgesetzt. Historische USDT-Kerzen ergänzen ältere USDC-Lücken; keine historische USDC-Liquiditätsbestätigung. Drawdown anhand stündlicher Schlusswerte; stärkere zwischenzeitliche Rückgänge sind möglich. Der aktuelle Produktbacktest mit anderem Startkapital und Zeitraum darf nicht direkt mit diesen Endwerten gleichgesetzt werden.

| Variante | Ende normal, USDC | DD normal | Ende Stress, USDC | DD Stress |
|---|---:|---:|---:|---:|
| Aktueller V8r | 29.459,95 | 41,81% | 20.803,15 | 50,75% |
| Nur DOGE: CMO-Mindestwert 0,50 statt 0,20 | 32.469,39 | 39,13% | 22.817,49 | 48,57% |

Der Kandidat fügt keinen Stop hinzu. DOGE darf nur bei stärkerem Momentum neu einsteigen; seine Indikatorparameter und Ausstiege bleiben gleich. Alle anderen Währungen, der ATR-Einsatzfaktor 0,0075 und die Slotaufteilung bleiben unverändert. Eine geringere Einstiegshäufigkeit kann die gesamte Slotverteilung verändern: Deshalb wurde das gemeinsame Portfolio geprüft.

## Chronologische Gegenprüfung und Auswahl

DOGE wurde nach Betrachtung seiner Verlustbeiträge in bereits untersuchten Daten gewählt. Dies ist eine adaptive Forschung, kein unberührter Holdout. Die Familie CMO 0,30 / 0,40 / 0,50 sowie VIDYA-Steigung über 24 / 72 Stunden wurde vor den neuen Rechnungen festgelegt. Zwei separate Trainingsjahre mit Stresskosten mussten profitabel bleiben, mindestens 95% der V8r-Rendite behalten und durften den Drawdown nicht erhöhen. Auswahl nach dem schlechtesten jährlichen Rendite/Drawdown-Verhältnis; CMO 0,50 wurde vor den Vollzeit- und Letztjahr-Prüfungen eingefroren.

Letztes Jahr, ebenfalls frischer Start in Cash:

| Variante | Rendite normal | DD normal | Rendite Stress | DD Stress |
|---|---:|---:|---:|---:|
| Aktueller V8r | 4,18% | 36,18% | -9,78% | 44,48% |
| DOGE CMO 0,50 | 8,98% | 33,24% | -5,78% | 42,02% |

Unter Stresskosten bleibt das letzte Jahr negativ. Vollzeit-Annahme verlangte mindestens 1% mehr Endkapital und mindestens 5% relative DD-Senkung in beiden Kostenfällen; zusätzlich durfte das letzte Jahr bei keiner Kostenannahme in Rendite oder DD schlechter werden. Drei von vier kombinierten Prüfungen bestehen, der Vollzeit-Stresstest verfehlt die DD-Vorgabe. `accepted=false` bleibt korrekt.

## Verworfene Core-Trailing-Ausstiege

Die Familie 4 / 6 / 8 / 12 Einstiegs-ATR hinter dem höchsten Schlusskurs der zehn Core-Währungen wurde mit gleichen Auswahlregeln untersucht. Sie wird ausschließlich nach Stunden-Kerzenschluss ausgewertet und ist kein Intrabar-Stop. Keine Variante bestand schon die Trainingsauswahl. Die vollständigen Rechnungen dienen nur der Diagnose; kein abgelehnter Kandidat wurde nachträglich ausgewählt.

Die Varianten erzielten im vollständigen normalen Backtest nur etwa 2.300 bis 5.824 USDC gegenüber 29.460 USDC beim aktuellen V8r. Zu frühe Ausstiege und veränderte Folgeeinstiege brachen große Gewinne weg; die Anzahl abgeschlossener Trades stieg von 148 auf 202 bis 435. Engere Trailing-Regeln sind damit keine geeignete Verbesserung dieses Modells.

## Nachrechnung und Betrieb

66 native Portfolio-Rechnungen. 44 gespeicherte Vollzeit-/Letztjahr-Szenarien wurden unabhängig anhand von equity.csv und trades.csv auf Endkapital, Rendite, Maximal-Drawdown und Anzahl abgeschlossener Trades geprüft; alle bestanden. Zwei zusätzliche Offline-Tests bestätigen für den DOGE-Kandidaten identische Paper-/Backtest-Fills und Equity, mit festem Budget sowie Wiederanlage und jeweils unterbrochen durch einen simulierten Neustart. Sie verwenden keine echten Börsenorders und sind keine formalen A09-/A11-Promotionsfreigaben.

Die aktuelle Strategie, der Python-Ausführungshash und der laufende Prozess blieben unverändert. Kein Neustart, keine Order durch die Forschung und keine automatische Test-/Live-Freigabe. Der echte 50-USDC-Test bleibt OPEN auf seiner eingefrorenen ursprünglichen Ausstiegsstrategie. Der tatsächliche Abschlussstatus steht in Abschluss.json. Alle drei Forschungsskripte bestehen Ruff und Formatprüfung.

## BNB und manuelle Kontobewegungen

Der laufende Echtgeldtest verwendet eine unveränderliche Konto-Baseline plus seine bestätigten Fills und Gebühren. Manuelle USDC→BNB-Umwandlungen während des Tests erzeugen zusätzliche USDC-/BNB-Bewegungen und können die Kontenabnahme blockieren. Gebührenvorrat daher zwischen abgeschlossenen Handelsläufen auffüllen. Kein Abgleich wird zu diesem Zweck abgeschaltet oder seine Baseline stillschweigend überschrieben.

## Dateien

- core-trailing/results.json und doge-filter/results.json: vollständige Familie, Trainingsauswahl, Kennzahlen, Ablehnungen und Quellenbindung.
- Jeweils reports/full und reports/last_year: native Manifest-, HTML-, Trade- und Equity-Berichte aller Varianten.
- CSV-Nachrechnung.json: unabhängiger Prüfnachweis.
- Drawdown-Ursachen.json: Zeitintervall und realisierte Beiträge; diese Beiträge sind keine vollständige Zuordnung des Equity-Drawdowns einschließlich offener Kursgewinne.
- Paper-Paritaet.xml und Offline-Paritaetspruefung.py: zwei simulierte Paritätsprüfungen.
- Forschungsskripte mit identischen Parametern für die Wiederholung auf einer vollständig vorhandenen reinen Marktdatenkopie, ohne Netzwerk-Ersatzdaten oder private API.


## Ausdrückliche lokale Auswahl durch den Benutzer

Nach Sichtung dieser Ergebnisse hat der Benutzer am 12.10.2026 ausdrücklich den Einbau und Neustart mit Erhalt des laufenden Echtgeldtests verlangt. Die lokale Paper-Variante heißt jetzt `HIXTON-V8-LINK8-ATR075-DOGE50-PAPER-2` (Schlüssel weiterhin `v8r`). Ausschließlich DOGE CMO wird von 0,20 auf 0,50 erhöht. Diese ausdrückliche Paper-Auswahl verändert nicht `accepted=false` der Forschungsfamilie und stellt keine A09-/A11-Promotions- oder Live-Freigabe dar. V6 und V8 bleiben unverändert. Die vorige V8r-Definition bleibt für die Auflösung alter offener Testverträge erhalten. Der vorhandene NEAR-Echtgeldtest behält seine eigene ursprüngliche V8-Strategie und Kauf-/Orderhistorie.
