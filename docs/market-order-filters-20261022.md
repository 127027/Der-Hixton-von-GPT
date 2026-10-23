# MARKET-Orderfilter, 22.10.2026

Die gemeinsame Ausführung berücksichtigt LOT_SIZE (minQty, maxQty, stepSize),
zusätzlich MARKET_LOT_SIZE (minQty, maxQty, stepSize) sowie die für MARKET
aktivierten MIN_NOTIONAL-/NOTIONAL-Grenzen. `applyToMarket`,
`applyMinToMarket` und `applyMaxToMarket` mit explizitem `false` werden beachtet.
Die wirksame Mindestnotionalgrenze ist das Maximum der anwendbaren Minima.

Beide Mengenschritte gelten gemeinsam. Beispielsweise ergeben 0,02 und 0,03
einen gemeinsamen Schritt von 0,06. Es wird nur abgerundet. Ein Maximum wird
nicht durch eine heimliche kleinere Order oder durch mehrere echte Orders
umgangen. Eine zu große simulierte SELL-Order bleibt als offene Position
erhalten; sie wird weder als ausgeführter Verkauf noch als Dust verbucht.
Ein entsprechender Live-Ausstieg verlangt eine Klärung und behält das Eigentum.
Bereits gesendete oder ungeklärte Orders werden weiterhin über ihre vorhandene
Identität abgefragt, auch wenn inzwischen neue Filter gelten.

Die Werte werden vom öffentlichen exchangeInfo über SymbolRules,
StoredSymbolRules und ExecutionRules in alle Produktadapter übernommen.
Eine neue JSON-Spalte speichert die ergänzten Grenzen. Alte Datenbanken bleiben
auch nur lesend ladbar; ihre fehlenden Maxima sind ausdrücklich **unbekannt**
(`market_limits_known=false`), kein Nachweis unbegrenzter Binance-Kapazität.
Solche Grenzen sperren neue reale Orderübermittlungen, bis die reguläre
öffentliche Synchronisation vollständige neue Filter gespeichert hat. Der
Supervisor lädt exchangeInfo für jeden Markt vor der Veröffentlichung eines
vollständig gesunden Marktzustands erneut. Alte historische Offline-Stores
bleiben zur Reproduzierbarkeit lesbar, bestätigen aber keine unbekannten Caps.
Explizite synthetische ExecutionRules können absichtlich unbegrenzt sein.

Grenzen: Binance bewertet Market-Notional mit seinem eigenen Referenzpreis
oder dem Durchschnitt über avgPriceMins. Das größte anwendbare Zeitfenster bleibt
als Metadatum erhalten; unterschiedliche Filterfenster und der Exchange-VWAP
werden aus stündlichen OHLC-Daten nicht rekonstruiert.
Lokale Checks verwenden daher den verfügbaren Signal-/Modellpreis. Auch die
aus quoteOrderQty geschätzte BUY-Basismenge kann sich bis zum Fill ändern.
Ein lokaler erfolgreicher Check ist kein Garantieversprechen für die Annahme
oder exakte Fill-Menge bei Binance. Binance bleibt die letzte Prüfinstanz.
Historische Simulationen verwenden die ausgewählte Filteraufnahme, keine
erfundene vollständige Historie früherer Binance-Filter oder Liquidität.

Offizielle Spezifikation:
[Binance Spot API – Filters](https://github.com/binance/binance-spot-api-docs/blob/master/filters.md).
