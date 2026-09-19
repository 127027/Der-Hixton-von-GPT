# 05 – Marktdaten und Aktualisierung

Status: CURRENT · 19.09.2026

Operative Quelle sind öffentliche Binance-Spot-USDC-Endpunkte. Private Credentials sind für Daten, Backtests und A01–A11 nicht erforderlich.

Strategie arbeitet auf 1h. Nur abgeschlossene Kerzen dürfen Indikatoren/Signale erzeugen. Startup lädt bis zu drei Jahre verfügbare Historie plus 400 Warm-up-Bars; fehlende Vor-Listing-USDC-Historie wird nicht synthetisch aufgefüllt.

Für ausdrücklich historische Forschung darf ein gleiches Basisasset gegen USDT als klar gekennzeichneter Preisproxy dienen. Das ist kein historischer USDC-Liquiditäts- oder Fillnachweis.

Gap-Recovery und Neustart verarbeiten fehlende geschlossene Bars exakt einmal. Aktuelle Exchange-Filter werden separat geprüft.
