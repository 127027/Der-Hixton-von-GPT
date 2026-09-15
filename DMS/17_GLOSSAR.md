# 17 – Glossar

| Begriff | Verbindliche Bedeutung |
|---|---|
| Bar/Kerze | OHLCV-Datensatz eines festen Timeframes |
| geschlossene Kerze | vom Datenprovider finalisierte Kerze; darf Signalsbasis sein |
| vorläufige Kerze | laufende Kerze; nur Anzeige, keine bestätigte Signalsbasis |
| VIDYA | Variable Index Dynamic Average gemäß `HIXTON-SPEC-1.0` in DMS 03 |
| ATR | Average True Range mit Wilder-RMA gemäß `HIXTON-SPEC-1.0` in DMS 03 |
| Band | VIDYA plus/minus ATR × Multiplikator |
| Trendzustand | persistenter Zustand `UP`, `DOWN` oder vor Initialisierung `UNINITIALIZED` |
| Flip | echter Wechsel zwischen Trendzuständen, nicht jeder Bar im selben Trend |
| Signal | deterministische Strategieausgabe zu einer geschlossenen Kerze |
| Order-Intent | interner, noch prüfbarer Wunsch, eine Order zu erzeugen |
| Order | an Paper-/Börsenadapter übermittelte Handelsanweisung |
| Fill | tatsächliche vollständige oder teilweise Ausführung |
| Position | aus Fills/Beständen abgeleitete offene Assetmenge |
| Long-only | kaufen und später verkaufen; kein Leerverkauf |
| Pyramiding | mehrfacher Einstieg/Vergrößerung im selben Trend; initial verboten |
| isolierter Backtesttopf | 250-USDT-Simulationskonto eines Coins; wird im 10er-Batch nicht mit anderen Tests geteilt |
| gemeinsamer Paper-Cashpool | 240-USDT-Modellkonto, aus dem anfänglich höchstens drei 80-USDT-Slots belegt werden |
| Positionsslot | maximal eine gleichzeitig offene Coin-Position mit konfiguriertem Zielnotional |
| Backtest | chronologische historische Simulation ohne echte Order |
| Paper | laufende Simulation mit realen Marktdaten, aber ohne echte Order |
| Live | Modus mit echten Börsenorders |
| Warm-up | Bars vor dem Berichtsstart zur vollständigen Indikatorinitialisierung |
| Look-ahead | unzulässige Nutzung zukünftiger Information |
| Repainting | nachträgliche Änderung eines bereits bestätigten historischen Signals |
| Slippage | Differenz zwischen Referenz-/erwartetem Preis und Fillpreis |
| Spread | Differenz zwischen bestem Kauf- und Verkaufskurs |
| Drawdown | Rückgang der Equity von einem vorherigen Hoch zum folgenden Tief |
| PnL | Gewinn/Verlust; `netto` nach dokumentierten Gebühren/Slippage |
| Mark-to-market | Bewertung einer offenen Position zum End-/Marktpreis ohne erfundenen Verkauf |
| Reconciliation | Abgleich lokalen Zustands mit Börsenorders, Fills und Salden |
| Idempotenz | Wiederholung desselben Events erzeugt keine zweite Wirkung/Order |
| stale | veraltet; Frischegrenze überschritten |
| Datenrevision | nachträgliche Änderung historischer Providerdaten |
| Run-Manifest | vollständige Metadaten eines reproduzierbaren Backtestlaufs |
| Golden-Daten | unabhängig berechnete Referenzwerte/-signale aus der normativen Spezifikation; optional ergänzt um rechtmäßig verfügbare externe Vergleichswerte |
| Not-Aus | Sperre neuer Entries; Liquidation ist eine getrennte Aktion |
| UTC | interne Standardzeitzone |
| Today/Heute | 00:00 bis jetzt in der sichtbar gewählten UI-Zeitzone |
