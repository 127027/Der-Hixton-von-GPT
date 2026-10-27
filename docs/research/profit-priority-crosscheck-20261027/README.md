# Heutiger Bot auf den ursprünglichen 32k-Daten · 27.10.2026

**Ja: Die heutigen Regeln ergeben auf den ursprünglichen Daten 33.867,80 USDC statt 32.469,39 USDC.**

Die heutigen Regeln sind die unveränderte aktive 15-Profil-Strategie `HIXTON-V8-LINK8-ATR075-DOGE50-DD10-ETH8-DIV32-CLOSECAP-PAPER-6`. Das interne Label `current_v6` bezeichnet hier ihre Versions-Endnummer 6, nicht den eingefrorenen Zehncoin-V6-Anker. Die ältere Vergleichsstrategie ist `HIXTON-V8-LINK8-ATR075-DOGE50-PAPER-2`.

## Regeln und Daten getrennt verglichen

Für alle acht Kreuzfälle gelten derselbe ursprüngliche Startbetrag **1.092,05773944 USDC**, dieselben aktuellen öffentlichen Exchangefilter vom 26.10., dieselben 15 Marktreihen/Rollen, je 400 Stunden Vorlauf, Start ohne Positionen und vollständige Wiederanlage. Jedes Datenfenster umfasst exakt drei Kalenderjahre. Es gibt weder Overlay noch Indikatorcache oder neue Parametersuche.

| Eingefrorenes Datenfenster | Alte DOGE50-Regeln: End-USDC / DD | Heutige Regeln: End-USDC / DD |
|---|---:|---:|
| 11.10.2023 19:00–11.10.2026 19:00 UTC | 32.469,39 / 39,13% | **33.867,80 / 30,48%** |
| 26.10.2023 14:00–26.10.2026 14:00 UTC | 10.776,99 / 39,17% | **11.069,13 / 38,23%** |

Auf dem ursprünglichen 32k-Fenster sind das **1.398,41 USDC mehr Endkapital und 8,65 Prozentpunkte weniger maximaler Drawdown**. Auf dem neueren Fenster schneiden die heutigen Regeln ebenfalls profitabler ab. Eine Rückkehr zu den alten Regeln würde auf diesem neueren Fenster den alten 32k-Betrag nicht wiederherstellen.

## Gleicher Vergleich unter erhöhten Kosten

| Datenfenster | Alte Regeln: End-USDC / DD | Heutige Regeln: End-USDC / DD |
|---|---:|---:|
| Originales 32k-Fenster | 22.817,49 / 48,57% | 23.539,27 / 47,73% |
| Neueres 26Oct-Fenster | 7.386,74 / 48,61% | 7.612,33 / 47,75% |

Normale Kosten je Seite:10bp Gebühren+2bpSpread+3bpSlippage. Stress:10+10+20bp. Es wird kein BNB-Rabatt unterstellt. Endkapital ist die markierte Modell-Equity einschließlich noch offener Bestände/Dust, kein erzwungener Schlussverkauf.

## Warum der andere Bericht nur etwa 11k ausweist

Die bekannten **11.004,18 USDC** sind zusätzlich mit ihrem damaligen Vergleichsstartbetrag **1.085,77093944 USDC** exakt reproduziert. Die 11.069,13 in der gemeinsamen Tabelle verwenden dagegen bewusst denselben 1.092,05773944-USDC-Startbetrag wie der alte32k-Vergleich. Beide sind simulierte Kapitalpfade, keine aktuelle Binance-Guthabenabfrage.

Das Verschieben des Dreijahresfensters verändert den flachen Anfangszustand, den 400-Stunden-Indikatorvorlauf, die ersten verfügbaren Einstiege und danach den gesamten Wiederanlagepfad. Die vorherige [native Zerlegung des 21k/11k-Unterschieds](../risk-controls-20261026/Einordnung.md) ist unverändert maßgeblich: Das bloße Weiterlaufen bei altem Start änderte 22.526,13 auf 21.793,40 USDC; der spätere flache Start samt neuer Initialisierung ergab 11.004,18. 399.465 überlappende Kerzen waren vollständig identisch. Der frühe AVAX-Einstieg vom 26.10.2023 08:00 UTC ist ein konkreter Auslöser; die gesamte spätere Differenz ist nicht als isolierter Gewinn eines einzelnen Trades belegt.

**Die am 26.10. getesteten zusätzlichen Schutzregeln wurden nie in den aktiven Bot übernommen. Der große Unterschied zwischen den zwei Fenstern ist deshalb kein durch diese Varianten verursachter Strategiegewinnverlust.** Die erhebliche Startempfindlichkeit bleibt eine Grenze des historischen Nachweises. Eine ähnliche zukünftige Marktphase garantiert keinen 32k-Betrag.

## Ertragspriorität korrigiert

Die erneut ausdrücklich bestätigte Eigentümervorgabe lautet: **höchster Netto-USDC-Ertrag zuerst, geringerer Drawdown erst danach**. Mehr DD ist für belegten Mehrertrag zulässig. Die am 26.10. zusätzlich verwendete strikte wirtschaftliche DD-Nichtregressionshürde entsprach dieser Rangfolge nicht. Der ursprüngliche Studienvertrag und seine Ergebnisse bleiben unverändert archiviert; ihre nachträgliche Neusortierung wird offen als **POSTHOC** ausgewiesen.

Unter dieser Rangfolge liegt bei den acht bekannten Varianten die 24-Stunden-Coinpause nach abgeschlossenen Verlusttrades vorn: normal **+127,53 USDC**, Stress **+100,42 USDC**, Impact-Annahme **+108,01 USDC** gegenüber der unveränderten Baseline. Ihre DD-Erhöhungen von 0,00024775 /0,00248085 /0,01299035 Prozentpunkten sind kein wirtschaftliches Ausschlusskriterium mehr. Das sind bereits betrachtete Ergebnisse einer Forschungsvariante, keine neue unabhängige Validierung und keine automatisch übernommene Handelsregel. Technische Validierung, Ausführungs-/Kostenprüfung, gemeinsame Backtest/Paper/Trial/Live-Integration und gesonderte Aktivierung bleiben Pflicht.

## Nachweis und Grenzen

Alle zehn nativen Fälle sind vollständig abgeschlossen. Die unabhängige Prüfung rekonstruiert 50 Artefakthashes, 263.040 Stundenkontowerte und 3.217 Fills mit Geldabweichung null. Die Original32k- und bekannte11k-Kontrolle stimmen außerdem in sämtlichen gespeicherten Metriken, Fills und Trades mit ihren Originalbelegen überein. Beide schon bekannten Datenfenster sind keine unberührten Out-of-sample-Daten. Historische USDT-Proxykerzen und heutige Exchangefilter beweisen keine damalige USDC-Orderbuchtiefe oder tatsächliche Ausführbarkeit. Die Legacy-Metadatenangabe `compounding:false` ändert die expliziten tatsächlichen Laufparameter `reinvest_profits:true` und `autonomous_spot:true` nicht.

Keine Änderung von Produktquellen, Schlüsselmaterial, laufenden Positionen oder Echtgeldfreigaben, keine Orders und kein Neustart. Es wurden in dieser Runde keine neuen Fünfjahrespfade erzeugt oder Gewinnerparameter gesucht.

- [Alle zehn Ergebnisse als CSV](Comparison.csv) und [vollständige Modellmetriken](Results.json)
- [Abgeleitete öffentliche Vergleichsspezifikation](Comparison-Specification.json)
- [Nachträgliche ertragsorientierte Neusortierung der unveränderten Vorstudie](Posthoc-Profit-Rerank.json)
- [Methodenquellen](Methoden-Code.zip) und [Datei-/Quellenbindung](Public-Evidence.json)
