# 22 – Quellen und Binance-Prüfung

Status: CURRENT · 21.09.2026

Operative externe Quelle ist Binance Public Spot Market Data. A07 prüft ExchangeInfo, TRADING-Status aller zehn USDC-Symbole, Serverzeit und öffentliche 1h-Klines.

Research muss Quote, Listingfenster und Proxyherkunft explizit ausweisen. Öffentliche Preisreihen beweisen keine reale Fillqualität.

Private Binance-Endpunkte werden ausschließlich lokal für Kontovorprüfung, Orderabgabe und Reconciliation des gestuften Echtgeldpfads verwendet. API-Secrets dürfen niemals in GitHub, Cloudjobs oder Agentenläufen verwendet werden. A07 prüft weiterhin nur öffentliche Binance-Daten und aktuelle Spot-Filter.
