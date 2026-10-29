# Bestätigte Ausführung bei Stopp und Wiederanlauf behalten

29.10.2026. Diese Reparatur ändert Zustandsübergänge des bestehenden Live-Controllers,
keine Strategie, Ordergröße, Gebührenrechnung, Börsenprüfung oder Kapitalaufteilung.
Die Bestandsstrategie bleibt Version 6; der separat untersuchte Wachstumsentwurf
und die vier Winter-Regeln werden dadurch nicht übernommen.

## Konkreter Fehler

Ein Kauf kann bei Binance bereits ausgeführt und mit seinen Fills im lokalen
Orderjournal bestätigt sein, während die Verbuchung in die lokale Position noch
aussteht. Etwa ein Prozessabbruch kann zwischen diesen beiden Schritten liegen.
Die alte Zustandswahl prüfte offene Positionen und nicht endgültige Orders.
Ein bereits `FILLED` markierter Kauf erfüllte keine dieser beiden Bedingungen.
Stopp, Normalisierung oder Quellwechsel konnten deshalb fälschlich
`LIVE_DISABLED` setzen und das noch offene Ausführungsereignis übergehen.

Jetzt bleibt der Controller auch bei einem noch offenen Ausführungsereignis
`EXIT_ONLY`. Er verarbeitet die bereits vorhandenen Fill-Belege weiter und
übernimmt die Position genau einmal. Es wird kein zusätzlicher Kauf gesendet.
Die ursprüngliche Ausstiegsverpflichtung bleibt bestehen.

## Nur bewiesen ungesendete Käufe verwerfen

Ein normales `ORDER_PENDING`-Kaufereignis ohne angelegten Intent oder mit einem
weiterhin `CREATED` markierten Intent darf lokal verworfen werden. Die Prüfung,
die lokale Stornierung samt Auditbeleg und das Abschalten neuer Einstiege liegen
in einer gemeinsamen SQLite-Transaktion. Ein Speicherfehler darf keinen nur
teilweise erfolgreichen Stopp als Erfolg erscheinen lassen.

`SUBMITTING`, `UNKNOWN`, bereits bestätigte Fills und `RECONCILING` werden nicht
als ungesendet umgedeutet. Auch ein widersprüchliches `RECONCILING`-Ereignis ohne
Intent bleibt erhalten und benötigt Abgleich. Der Stopp verkauft keine Position
sofort und ist keine Aufforderung, eine ungeklärte Order erneut zu senden.

## Nachweise und Betriebsgrenze

Der Fehler wurde vor der Korrektur unabhängig mit temporären Datenbanken und
simuliertem Binance unter der unveränderten Sechser-Strategie reproduziert.
Die Tests decken bestätigte, noch nicht verbuchte Käufe bei Stopp, Normalisierung,
Quellwechsel und echter Neuerstellung des Controllers ab. Weitere Fälle prüfen
ungesendete Käufe, widersprüchliche Abgleichbelege, keine Doppelorder und atomaren
Rollback. Dabei werden keine echten Konten oder Schlüssel verwendet.

Eine technische Korrektur garantiert weder zukünftige Gewinne noch laufendes
Internet oder eine passende Binance-IP-Freigabe. Sie ersetzt keinen frischen
Kontenabgleich und aktiviert weder Echtgeld noch einen neuen 50-USDC-Test.
Ein bereits gespeicherter erfolgreicher technischer Einmaltest bleibt nach dem
bestehenden Abnahmevertrag erhalten; er wird nicht als echter Test neuer Regeln
umetikettiert. Die Installation in einer bereits laufenden Kopie ist ein
gesonderter Schritt.
