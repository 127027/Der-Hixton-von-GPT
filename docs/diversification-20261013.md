# Eigentümergewählte Diversifikation ab 32.000 USDC

Stand: 13.10.2026. Strategie: HIXTON-V8-LINK8-ATR075-DOGE50-DD10-ETH8-DIV32-PAPER-5.

Bis zur Schwelle bleibt der bisherige ETH8-Allocator mit zwei Haupttranchen und dem DD10-Schutz erhalten. Sobald die letzte vollständig geschlossene Portfolio-Bewertung mindestens 32.000 USDC erreicht, wird dauerhaft auf höchstens drei verschiedene Coins umgeschaltet. Ein Verlust unter die Schwelle oder ein Neustart stellt die Konzentration nicht wieder her.

Bei diesem Wechsel wird eine zu große bestehende Position einmal teilweise reduziert. Die Verkaufsmenge wird aus vorheriger geschlossener Equity, damaligem Schlusskurs und dem Börsen-Mengenschritt bestimmt; der Verkauf folgt am nächsten ausführbaren Zeitpunkt. Neue Käufe erhalten maximal ein Drittel der verfügbaren verwalteten Equity vor ATR-Anpassung. Es werden ausschließlich neue gültige Signale verwendet. Fehlende Signale lassen Kapital in Cash. Bereits offene Coins erhalten keine zusätzliche Tranche. Core-Vorrang, Qualitätsfilter, Tagespause, Kontenabgleich und Source-/Strategie-Bindung bleiben erhalten.

Die sechs internen Kapazitätseinheiten je Position sind reine Buchführung: drei Positionen reservieren 18 von 20 Einheiten. Das Kaufbudget beträgt tatsächlich 1/3, nicht 6/20. Die zusätzliche Positionsanzahl-Grenze verhindert eine vierte Order. Benutzeroberfläche und Berichte zeigen die echte Anzahl und 33,33-Prozent-Anteile; Teilverkäufe zählen nicht als abgeschlossene Positionszyklen.

## Vergleich auf demselben historischen Datensatz

Zeitraum: 13.10.2023 15:00 UTC bis 13.10.2026 15:00 UTC; Startkapital 1.087,68133944 USDC. Alle V8r-Parameter und aktiven Märkte bleiben gleich; nur die Kapitalaufteilung wird verändert.

| Variante | End-USDC | Maximaler Drawdown |
|---|---:|---:|
| Bisheriges ETH8/DD10 | 31.825,37 | 38,22 % |
| Sechs verschiedene Coins ab 25k | 25.846,19 | 30,53 % |
| Sechs verschiedene Coins ab 30k | 29.819,50 | 30,53 % |
| Drei verschiedene Coins ab 32k, gewählt | 32.727,15 | 30,50 % |
| 3@30k / 4@35k / 6@40k | 31.716,81 | 30,50 % |

Die gewählte Variante verbessert im untersuchten Gesamtlauf das Endkapital um 901,78 USDC und den maximalen Drawdown um 7,72 Prozentpunkte. Frühere Schwellen und zusätzliche Stufen brachten keinen überzeugenderen Gesamtkompromiss. Insbesondere wurde die zunächst gute 30/35/40-Staffel wegen schwächerem Kosten-Stresstest mit frischem Jahreskonto verworfen. Vier oder sechs Positionen werden im Produkt nicht aufgrund ungeprüfter zukünftiger Schwellen aktiviert.

Im vollen Drei-Jahres-Kostenstress erreicht das Konto die neue Schwelle nicht: unverändert 22.399,56 USDC / 47,75 % DD. Das ist keine Behauptung, der Stress-DD sei auf 30,50 % begrenzt.

Separater Jahreslauf 13.10.2025 bis 13.10.2026 mit 30.000 USDC Start:

| Kosten | Bisheriges ETH8 | Gewählte DIV32-Regel | DD bisher / neu |
|---|---:|---:|---:|
| Normal | 32.827,90 | 31.604,81 | 31,58 % / 31,58 % |
| Stress | 28.368,56 | 30.117,63 | 38,47 % / 38,47 % |

Die bessere Gesamtlauf-Zahl bedeutet nicht, dass jeder Zeitraum besser wird. Bei einem weiteren Drei-Jahres-Lauf, der bereits mit 50.000 USDC beginnt, fällt das normale Endkapital durch dauerhafte Drittelung deutlich geringer aus: 527.056,96 statt 1.463.388,60 USDC; DD 31,75 statt 38,19 %. Solche hohen historischen Reinvestitionswerte enthalten kein historisches Orderbuch-/Liquiditätsmodell. Die Wahl ist ein Kompromiss für den aktuellen kleinen Startbestand und die untersuchte Historie, keine garantierte optimale Regel für jedes Startkapital.

## Technische Abnahme

Der native neue Backtester stimmt stündlich mit dem isolierten Forschungsmodell überein. Der alte ETH8-Vertrag bleibt eingefroren und liefert unverändert seine Regression. Drei Jahre Paper entsprechen allen 363 normalen und partiellen modellierten Fills sowie 26.303 gespeicherten Stundenreferenzen. Der Live-Controller verwendet dieselben Entscheidungs- und Mengenfunktionen. Offline-Fake-Exchange-Tests prüfen drei unterschiedliche Käufe, Abweisung eines vierten, Teilverkauf, verlorene HTTP-Antwort, Neustart, regulären Restverkauf und Sperre bei unvollständigem Teilverkauf.

Teilorders werden vor Versand dauerhaft gespeichert und nach unklarer Antwort abgefragt. Ein Teilverkauf darf weder die Restposition löschen noch ein abgeschlossenes Live-Roundtrip vortäuschen. Bereits gekaufte 50-USDC-Tests behalten ihren ursprünglichen gefrorenen Vertrag für den Ausstieg. Ein noch nicht gekaufter wartender Test kann nach ausdrücklich autorisiertem Versionswechsel über die normale frische Binance-Prüfung neu vorgemerkt werden; kein Kauf wird vom Installationsskript gesendet. Live bleibt eine separate Freigabe nach einem vollständig abgeglichenen, zur Version passenden Test.

Diese Historie wurde mehrfach untersucht und für die Auswahl verwendet. Sie ist kein unberührter Zukunftstest. Ältere USDC-Historie wird bei fehlenden Listings ausdrücklich mit USDT-Kerzen ergänzt. Gewinn, Liquidität, eine absolute Drawdown-Grenze und zukünftige Endbeträge werden damit nicht garantiert.
