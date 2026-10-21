# Telegram-Kontakt für bestätigte Echtgeld-Trades

Unter **Einstellungen → Kontakt · Telegram** lassen sich Handelsmeldungen separat
aktivieren. Es gelten das vorhandene lokale Hixton-Passwort und dieselbe
15-Minuten-Sitzung wie für den Binance-Zugang. Speichern oder eine Testfreigabe
lösen keine Handelsnachricht aus. Paper und Backtests werden nicht gemeldet.

## Einrichten

1. In Telegram den offiziellen **@BotFather** öffnen und mit `/newbot` einen
   eigenen Bot erstellen. Das Token ausschließlich in Hixtons Kontaktformular
   eintragen, nicht in einen öffentlichen Chat oder ein GitHub-Issue.
2. Den eigenen neuen Bot öffnen und `/start` senden. Telegram erlaubt Bots nicht,
   von sich aus ein Gespräch mit einem unbekannten Benutzer anzufangen.
3. In Hixton oben mit dem lokalen Passwort entsperren. Unter Kontakt das Token
   eintragen, **Privaten Chat finden** wählen und den eigenen Chat auswählen.
   Eine Chat-ID ist keine Telefonnummer. Die automatische Suche liest die letzten
   Nachrichten des eigenen Bots; bei einem bereits anderweitig verwendeten Bot
   kann stattdessen die private Chat-ID direkt eingetragen werden.
4. **Telegram-Handelsmeldungen aktivieren**, speichern und anschließend bewusst
   **Testmeldung senden** drücken. Den Empfang in Telegram selbst prüfen.

Ein vorhandenes Token kann durch ein leeres Tokenfeld beim Speichern beibehalten
werden. Entfernen löscht nur den lokalen Kontakt und dessen lokale Versandkopien;
es stoppt oder verkauft keine Position und widerruft den Bot nicht bei Telegram.

## Was gemeldet wird

- Bestätigter echter Kauf des einmaligen 50-USDC-Tests oder einer Dauer-Live-
  Position: Markt, tatsächlich ausgeführter Betrag und Menge, mittlerer Fillpreis,
  Gebühren nach Asset und Order-/Trade-IDs.
- Bestätigte Teilverkäufe sind als Teilverkauf gekennzeichnet und werden nicht
  als vollständiges Handelsergebnis ausgegeben.
- Ein vollständiger Abschluss erfordert belegte Kauf-/Verkaufs-Fills und den
  bestehenden Kontenabgleich. Einsatz, tatsächlicher Rückfluss, Cashdifferenz,
  Gebühren und verbleibender Restbestand werden genannt. Ein bestätigter Verkauf
  ohne abgeschlossenen Abgleich heißt ausdrücklich **Abschluss noch ungeklärt**.
- Eine nur vorbereitete, übermittelte oder ungeklärte Order ohne bestätigte Fills
  wird nicht als ausgeführter Kauf gemeldet. Laufende nichtterminale Teilfills
  warten auf die endgültige Orderbestätigung, damit kein Zwischenstand als
  endgültiger Kaufbetrag erscheint.

Gebühren in USDC sind in der Cashdifferenz berücksichtigt. Gebühren in der
gekauften Basiswährung reduzieren die erhaltene Menge und werden separat
ausgewiesen. Bei BNB oder anderen Drittassets wird **kein erfundener Netto-USDC-
Gewinn** angegeben: Es steht dann zum Beispiel „USDC-Differenz vor BNB-Gebühren“
mit der tatsächlichen BNB-Gebühr. Bei Dust wird die Menge genannt; die
Cashdifferenz bewertet diesen Rest nicht.

Die derzeitigen Fills speichern keine ursprünglichen Binance-Tradezeitstempel.
Meldungen nennen deshalb ehrlich die **Zeit der erfassten Binance-Bestätigung**;
die Strategie-Signalzeit wird getrennt ausgewiesen. Eine verspätete Meldung oder
Ausführung wird nicht auf die Signalzeit zurückdatiert.

## Speicherung, Wiederholungen und Betrieb

Token und Chat-ID liegen unter einem eigenen Eintrag im Windows-Schlüsselspeicher.
Der Token wird nie vom API zurückgegeben, nicht im Browser gespeichert und nicht
in die Versanddatenbank geschrieben. Die separate lokale
`data/notification-outbox.sqlite3` speichert nur Nachrichten und Versandstatus.
Der Ereignissammler öffnet ausschließlich das echte Ausführungsjournal lesend;
er kann weder Schlüssel ändern noch Orders auslösen oder Handelsprüfungen umgehen.

Der eigene Versandtask prüft etwa alle fünf Sekunden neue bestätigte Ereignisse.
Er läuft unabhängig von der Handelsverarbeitung; ein Telegram-Ausfall hält keinen
Strategieausstieg auf. Nach einem Fehler werden anstehende Nachrichten mit
Wartezeit erneut versucht. Neustarts behalten die Warteschlange und bestätigte
Versandmarkierungen. Bereits erledigte alte Trades werden bei der ersten
Aktivierung nicht nachträglich versendet. Maßgeblich ist der belegte
Bestätigungszeitpunkt; ein schon vor Aktivierung gefüllter normaler Verkauf mit
erst später beendetem Kontenabgleich kann nicht als neues Ereignis erkannt werden,
weil das vorhandene normale Live-Journal diesen Abgleichzeitpunkt nicht speichert.

Änderung des Kontakts oder Ausschalten verwirft ausstehende Meldungen an den alten
Kontakt. Eine neue Aktivierung beginnt ab diesem Zeitpunkt. Normaler unveränderter
Speichervorgang erhält ausstehende Nachrichten.

Eine positive Telegram-Antwort bedeutet **vom Versanddienst angenommen**, nicht
„auf dem Handy angekommen“ oder „gelesen“. Nach einem Timeout oder Prozessabbruch
zwischen Annahme und lokaler Speicherung ist eine Doppelmeldung möglich. Jede
Nachricht trägt dafür eine stabile Meldungs-ID. Eine globale Genau-einmal-
Zustellung wird nicht behauptet.

Hixton muss laufen und eine Internetverbindung haben. Bei geschlossenem Bot oder
ausgeschaltetem Laptop gibt es keinen unabhängigen externen Wächter. Ausstehende
Meldungen können nach dem nächsten regulären Start nachgeholt werden.

## Kosten und recherchierte Anbieterbedingungen

Telegram bietet einen kostenlosen normalen Botversand innerhalb seiner
[Versandgrenzen](https://core.telegram.org/bots/faq#how-can-i-message-all-of-my-bot-subscribers-at-once).
Hixton sendet nur einzelne persönliche Meldungen und aktiviert keine
kostenpflichtigen Broadcasts. Aufbau und Versand folgen der
[offiziellen Bot-API](https://core.telegram.org/bots/api#sendmessage).

WhatsApp benötigt für unbeaufsichtigte Benachrichtigungen außerhalb des
24-Stunden-Fensters normalerweise einen eingerichteten Business-Versand und
[freigegebene Vorlagen](https://www.twilio.com/docs/whatsapp/key-concepts).
Dienstleister können [Nachrichtengebühren](https://www.twilio.com/en-us/whatsapp/pricing)
berechnen. Eine Telefonnummer allein genügt dafür nicht. Der Nutzer hat deshalb
für diese Umsetzung ausdrücklich **Telegram** gewählt; WhatsApp, SMS und E-Mail
werden nicht als bereits funktionierende Kanäle angeboten.

## Installation bei bereits freigegebenem Echtgeldtest

Diese Erweiterung verändert Python-Dateien und damit den Ausführungsfingerabdruck.
Sie wird nicht heimlich in einen laufenden freigegebenen Test kopiert. Die
vorhandenen Versionsprüfungen bleiben wirksam. Vor Installation ist der aktuelle
Testzustand zu sichern und der Wechsel abzustimmen. Ein noch nicht gekaufter Test
benötigt nach einem Quellwechsel eine neue ausdrückliche Freigabe; ein bereits
gekaufter Test behält seine gefrorenen Ausstiegs- und Abgleichpflichten. Die
Benachrichtigungsfunktion darf keine neue Echtgeldfreigabe selbst auslösen.
