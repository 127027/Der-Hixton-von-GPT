# Sichere Ausführung und nachvollziehbare Orderklärung

Die Handelsstrategie bleibt DIV32/PAPER-5. Erfundenen Zukunftsverläufen lässt sich
keine bestätigte Verbesserung der Handelsregeln entnehmen. Ein historischer
Drawdown ist weiterhin keine Verlustbegrenzung.

Diese technische Korrektur behebt zwei reproduzierte Fehler: Eine gescheiterte
Zeitprüfung vor einem noch nicht versandten POST konnte einen Auftrag dauerhaft
als UNKNOWN markieren. Zudem zeigte der Ausführungsbericht bei einer ungeklärten
Testorder fälschlich OK. Die historische Ursache eines bereits vorhandenen UNKNOWN
lässt sich ohne damals gespeicherte Transportdaten nicht rückwirkend bestimmen.

Test- und normale Live-Ausführung speichern nun eine bestätigte ACK-Orderkennung
vor nachfolgenden Statusabfragen. Ein ACK ist kein Fill und erhält keine erfundene
Börsen-Endbestätigung. Transportfehler speichern ausschließlich feste Stufen,
HTTP-Status und numerischen Fehlercode. Schlüssel, Signaturen, URLs, Rohantworten
und freie Exception-Texte werden nie protokolliert. Ein nachweislich vor dem POST
gescheiterter Clock-Check kann seinen aktuellen Submit-Claim freigeben. Frühere
Proofs, vorhandene ACKs, Mengen, Fills und bereits ungeklärte Orders können dies
nicht. Alle bisherigen Signal-, Zeit-, Konto- und Besitzprüfungen bleiben erhalten.

Bericht, Übersicht und Einstellungen kennzeichnen ungeklärte Testorders als
Fehler. Marktfeed-Gesundheit und Orderklärung sind unterschiedliche Zustände;
eine offene Klärung sperrt weiterhin einen neuen Test und Dauer-Live.

## Eng begrenzte administrative Klärung

`recover_missing_trial_order` dient ausschließlich einer ausdrücklich autorisierten
lokalen Klärung bei exklusiv gestoppter Runtime. Es kann keine Order senden oder
stornieren und keine Live-Freigabe bzw. erfolgreichen Test erzeugen. Voraussetzungen:

- genau ein über eine Stunde alter, nie bestätigter UNKNOWN-Testkauf, keine Fills,
  ACKs, Mengen, andere ungeklärte Orders oder Live-Positionen;
- unveränderte ursprüngliche Konto-, Strategie-, Quell- und Client-ID-Zuordnung;
- drei zeitlich getrennte frische Abfragen der originalen Orderkennung mit -2013;
- vollständige `allOrders`- und `myTrades`-Historie seit vor dem ursprünglichen
  Submit-Claim, ohne Order-/Tradeaktivität im betroffenen Symbol;
- stabile volle Kontoantworten um die Abfrage aller offenen Orders, exakt passend
  zur unveränderlichen Baseline einschließlich BNB und fremder Bestände;
- gültige Serverzeit, vollständige begrenzte Pagination und weiterhin gestoppte
  Runtime. Jeder Fehler oder Widerspruch blockiert den Vorgang.

Ein erfolgreich belegter lokaler Nichtfund wird als
`FAILED / MANUAL_NO_ORDER_CONFIRMED` archiviert, ohne einen Binance-Endstatus
vorzutäuschen. Die ursprüngliche UNKNOWN-Historie und Quellidentität bleiben
erhalten. Ein dauerhafter SQLite-Tombstone verhindert die Wiederverwendung der
alten Intent- und Client-ID. Normale Retry- und UNKNOWN-Sperren werden nicht gelockert.
Ein anschließend ausdrücklich gewünschter Test erhält erst über die normale
frische Kontovorprüfung eine neue ID und aktuelle Quellbindung. Er wartet auf ein
neues gültiges Signal und handelt genau einmal bis zum regulären Ausstieg.

Die Recherche- und Installationsnachweise mit konkreten Kontodaten bleiben lokal.
Öffentliche Dokumentation enthält keine API-Schlüssel oder individuellen Salden.

Primärquellen: [Binance Konto-/Orderhistorie](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/account),
[Binance Hinweise zu ungeklärtem Ausführungsstatus](https://developers.binance.com/en/docs/products/spot/rest-api).
