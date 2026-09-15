# 07 – Ausführung und Orders

Ergänzung 0.4.1: `live/orders.py` enthält einen **nicht angeschlossenen** Orderjournal-Kern für isolierte Tests. Er persistiert den unveränderlichen Auftrag und `SUBMITTING` vor genau einem Sendeversuch. Bei Timeout/Restart wird nur abgefragt; auch „nicht gefunden“ erlaubt keinen blinden Neukauf. Fills sind über Konto/Symbol/Trade-ID dedupliziert; fehlende Filldetails halten die Buchung offen. Endzustand der Börse bleibt getrennt vom Vollständigkeitsstatus erhalten. BNB-Gebühren werden nicht als USDT ausgegeben. Freigabe, globale Budgetbindung, tatsächlicher Kontobesitz, frische Quotes/Filter und der produktive Adapter sind ausdrücklich **nicht** durch diesen Kern gelöst. Es existiert kein HTTP-Orderpfad; der folgende Vorbereitungsstand gilt weiter.

Implementierungsstand 0.4.0 / DEC-046: Die neue Live-Vorbereitung liest nur Binance-Zeit, Key-Rechte, Spotkonto, offene Orders und ExchangeInfo. **Kein Submit, kein Storno, kein Order-Test-POST, keine Kontoübernahme.** Strategielogik bleibt unverändert. Der spätere Echtgeldadapter darf die derzeitigen Paper-Fills nicht schlicht weiterleiten: Paper-Replay enthält historische Modellfills, Live muss ausschließlich frische Intents nach Freigabe ausführen und tatsächliche Börsenfills separat buchen. Paperpositionen werden beim Moduswechsel nicht gekauft oder verkauft. Die nachfolgenden Live-Orderregeln sind weiterhin verbindliches Zielbild, kein bereits implementierter Nachweis.

V6 ist technisch für coinindividuelle Regeln vorbereitet: CMO-/VIDYA-Filter prüfen nur frische Hixton-BUY-Flips; XRP kann zusätzlich bei `close <= entry_fill - 4 * entry_ATR` aussteigen. Der Entry-ATR bleibt gespeichert, der Stop gilt nur am Schlusskurs und wird mit dem tatsächlichen nächsten Open plus Kosten ausgeführt. Kein garantierter Stoppreis, kein intrabar erfundener Fill, kein erneuter Kauf ohne neuen Flip. Strategiewechsel verlangen eine gesonderte protokollierte Aktivierung; technische Implementierung allein aktiviert nichts.

## Grundmodell

Signal, Absicht und tatsächliche Ausführung sind getrennt:

```text
geschlossene Kerze
  -> Strategiesignal
  -> Risk-/Health-Prüfung
  -> Order-Intent
  -> Börsenorder
  -> Teil-/Vollfills
  -> Position und Cash
```

Diese Trennung ermöglicht Audit, Wiederanlauf und die Erklärung, warum ein Signal nicht zu einem Fill führte.

## Order-Intent

Pflichtfelder:

- eindeutige Intent-ID;
- Idempotency-Key aus Umgebung, Konto, Strategieversion, Symbol, Timeframe, Signalkerzenzeit und Aktion;
- Signal-ID und Signalwerte;
- gewünschte Seite, Menge/Notional und Ordertyp;
- Referenzpreis und Berechnungszeit;
- aktive Konfigurationsversion;
- Status und Blockierungsgrund.

## Verbindliche Orderarten

Eine später freigegebene Liveversion verwendet verbindlich Market-Orders nach bestätigtem Signal. Kauforders verwenden, sofern von Binance für das Symbol erlaubt, `quoteOrderQty` mit dem ausdrücklich freigegebenen Zielnotional: **beim einmaligen DEC-047-Test 50 USDT**, erst bei separat freigegebenem 3×80-Betrieb 80 USDT. Gebühren werden gesondert verbucht. Verkaufsorders schließen höchstens die tatsächlich verfügbare botzugehörige Basisassetmenge. Vor Submit darf der aktuelle ausführbare Referenzpreis höchstens 25 bps vom Intent-Referenzpreis abweichen. Limit-/Marketable-Limit-Orders gehören nicht zum beschlossenen Erst-Liveumfang. Beim Einmaltest sind genau eine Einstiegsberechtigung und ein anschließender Strategieausstieg zulässig; kein blinder Neuversand und keine automatische Wiederbewaffnung. DMS 20 beschreibt den noch nicht implementierten Ablauf.

Nach Submit gelten feste Zeiten:

- nach 10 Sekunden ohne eindeutige Binance-Bestätigung: Status `UNKNOWN`, sofortige Reconciliation, keine Ersatzorder;
- Teilfills werden fortlaufend gebucht;
- bleibt eine Market-Order nach 30 Sekunden teilweise offen, wird zuerst ihr Börsenstatus geklärt und ein stornierbarer Rest storniert; keine automatische Neuorder;
- jede Überschreitung der erwarteten 25-bps-Ausführungsabweichung erzeugt mindestens einen P2-Alarm und fließt in die Paper-/Live-Auswertung ein.

## Zustände

```text
INTENT_CREATED
  -> BLOCKED
  -> SUBMITTING
      -> SUBMITTED
          -> PARTIALLY_FILLED
          -> FILLED
          -> CANCELED
          -> REJECTED
          -> UNKNOWN
```

`UNKNOWN` ist sicherheitskritisch: Es dürfen keine Ersatzorders gesendet werden, bevor der Börsenstatus über Client-ID, offene Orders, Trades und Salden abgeglichen wurde.

## Teilfills

- Jeder Fill wird separat mit Menge, Preis, Gebühr und Zeit gespeichert.
- Position basiert auf Fills, nicht auf der gewünschten Ordermenge.
- Restmenge bleibt gemäß Börsenstatus offen, wird nicht automatisch dupliziert.
- Nach 30 Sekunden gilt die oben definierte Klärungs-/Stornoregel. Ein Rest unter Binance-Mindestmenge oder Mindestnotional wird als `DUST` sichtbar verbucht und nicht durch eine regelwidrige Ersatzorder vergrößert; bei einem später regelkonformen Exit darf er mitgeschlossen werden.
- Exitmenge darf den tatsächlich verfügbaren Basisbestand nicht überschreiten.

## Restart und Reconciliation

Vor Live-Aktivierung nach jedem Start:

1. lokale offene Intents/Orders laden;
2. Börsenorder über Client-Order-ID abfragen;
3. Trades/Fills seit letztem Checkpoint laden;
4. freie/gesperrte Salden und Positionen vergleichen;
5. Differenzen als Incident markieren;
6. nur bei eindeutigem Zustand neuen Orderversand freigeben.

Lokaler Zustand ist nicht automatisch wahr; bei Live-Fills ist die Börse die Ausführungsquelle der Wahrheit. Manueller Handel auf dem Bot-Account/Subaccount ist verboten. Erkannte Fremdorders oder ungeklärte Salden führen zu `HALTED`; eine Fortsetzung erfordert geklärten Zustand und Audit, keine stille Importannahme.

## Fehlerverhalten

| Fehler | Verhalten |
|---|---|
| Rate-Limit | Retry nach Providerhinweis, Queue erhalten, keine Parallelflut |
| Netzwerk-Timeout vor Bestätigung | Status `UNKNOWN`, abfragen statt neu senden |
| Order abgelehnt | Grund speichern, keine unendliche Retry-Schleife |
| unzureichender Saldo | Intent blockieren, Alarm |
| Filteränderung | Metadaten neu laden, Menge neu bewerten, neue Intentversion erforderlich |
| stale Daten | keine neue Entry-Order |
| Stream getrennt | Signalverarbeitung pausieren, REST-Recovery |
| Prozessabsturz | atomare Persistenz und Reconciliation beim Neustart |

## Paper-/Live-Parität

Ziel ist eine gemeinsame Strategie-, Slot-, Risk- und Intentlogik für Paper und später Live. Die private Live-Order-/Reconciliation-Schicht ist noch nicht implementiert. Startkonfiguration sind 250 USDT Modellkapital (10 USDT anfängliche Reserve), drei Slots und 80 USDT Zielnotional.

Implementierter Stand ab `DEC-040`: `NEXT_BAR_OPEN_V1` verwendet nach dem bestätigten 1h-Signal das tatsächliche Open der Folgekerze plus Baselinekosten (10 bp Gebühr, 2 bp Spread, 3 bp Slippage je Seite). Das ersetzt den falschen Signalkerzen-Schlusskurs mit künstlichem 250-ms-Zeitstempel. Fehlt ein Folge-Open, bleibt die gesamte Zeitscheibe für alle zehn Märkte unverbucht. Zeitscheiben werden nach UTC-Open gruppiert, nicht nach möglicherweise verschiedenen Provider-Close-Millisekunden. Ausstiege laufen vor neuen Einstiegen; nicht ausführbare Kandidaten verbrauchen keinen Slot. Mengenreste werden als Dust behalten und in der Equity bewertet.

`occurred_at_utc` bezeichnet die **modellierte** Fillzeit, `processed_at_utc` den tatsächlichen Verarbeitungszeitpunkt. Alte Ereignisse ohne diese Metadaten heißen `LEGACY_CLOSE_OR_MIGRATION` und werden nicht umgeschrieben. Restart-Replay kann vergangene Modellfills buchen; diese sind keine damals ausführbaren Live-Orders und kein Latenznachweis. Gemessene Orderbuch-/Fill-/Teilfill-Simulation und echte Binance-Reconciliation bleiben Live-Blocker. Die automatische technische Soak-Neuepoche bewahrt Positionen, Cash und Ledger; Trades mit Einstieg vor dieser Epoche zählen nicht als vollständiger neuer Soak-Trade.

Der Backtest ist davon getrennt: Standard sind zehn isolierte 250-USDT-Läufe oder ein einzelner gewählter 250-USDT-Lauf. Zusätzlich muss der gemeinsame 250-USDT-/3×80-Spiegeltest die Paperregeln prüfen.

## Manuelle Eingriffe

- Not-Aus: neue Entry-Intents blockieren.
- „Position schließen“ ist eine separate, paarbezogene Aktion mit Bestätigung.
- „Alle Positionen schließen“ erfordert stärkere Bestätigung und zeigt geschätzte Kosten.
- Manuelle Order außerhalb des Bots wird nicht verschwiegen; Reconciliation meldet sie.
- Änderungen an Konfiguration wirken nicht rückwirkend auf bereits eingereichte Orders.
