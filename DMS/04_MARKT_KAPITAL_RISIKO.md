# 04 – Märkte, Kapital und Risiko

Aktueller Vorrang: **DMS 1.12.0 / DEC-053 / Anwendung 0.4.7**. Der integrierte Code verwendet USDC (250 Modellstart, Standard 3×80; später genau ein 50-USDC-Test). Alte datierte USDT-Anforderungen/Ergebnisse sind Historie, keine umgerechneten USDC-Nachweise. Runtime- und Laptop-Deployment sind getrennt zu prüfen. Kein Echtgeldstart: technischer Restarbeitsplan in [DMS 20](20_BETRIEBSRUNBOOK.md), tatsächlicher Testnachweis in [DMS 12](12_TESTS_ABNAHMEKRITERIEN.md). Bestehende Live-Sicherheitsgates bleiben wirksam.

DEC-052 / 0.4.6: Zielwährung des künftigen Betreiber-Spotbetriebs ist USDC, erster geplanter Echtgeldversuch genau einmal 50 USDC. Aktive V6-Modelldaten bleiben USDT; V7-USDC ist zunächst eine gesonderte, nicht freigegebene Prüfung. Kein tatsächlicher Umtausch, Einzahlen oder Import der ca. 1200 USDC. Historische 3×80-Prüfung startet mit 250 Einheiten der jeweiligen Quote (240 Positionsbudget plus 10 Anfangsreserve). Gemeinsame Zeitfenster und identische Risikogates sind beim Vergleich Pflicht. Ein 20-%-Drawdown-Halt blockiert neue Entries, liquidiert aber nicht; der tatsächliche Drawdown kann darüber liegen. Keine tägliche Profitgarantie, kein Hebelauftrag.

Aktuell DEC-051 / 0.4.5: Baseline 3×80 bleibt unverändert, die UI erlaubt 1–10 Slots × gewähltes positives Zielnotional ohne feste 240-USDT-Grenze. 5×50 bzw. 10×100 sind speicherbar; kein zusätzlicher Cash und keine neue Profitbehauptung. Das Update verändert die gespeicherten Betreiberwerte nicht. Die folgenden 3×80-Angaben beschreiben die Baseline. Slotanzahl ist eine Obergrenze, kein Auftrag, ohne qualifiziertes Signal zu kaufen. Verfügbare Mittel und interne Risikogates bleiben maßgeblich. Änderungen gelten für neue Entries, nicht als Zwangsabbau vorhandener Positionen; Positionsbudget ist keine garantierte Verlustgrenze.

DEC-045: Der ausdrücklich beauftragte neue V6-Paperaccount beginnt separat mit 250 USDT. Die alte 240-USDT-Kontohistorie bleibt archiviert, nicht umgebucht. 3×80, höchstens ein Slot je Coin, Baselinekosten sowie 5-%-Tagespause und 20-%-Drawdown-Halt bleiben unverändert. Die 10 USDT sind eine Anfangsreserve, kein dauerhaft garantierter Mindestbetrag.

## Initiales Marktuniversum

Für DMS V1 festgelegte Binance-Spot-Paare:

1. BTC/USDT
2. ETH/USDT
3. BNB/USDT
4. SOL/USDT
5. XRP/USDT
6. ADA/USDT
7. LINK/USDT
8. AVAX/USDT
9. DOT/USDT
10. DOGE/USDT

Die Liste ist kein Versprechen, dass diese Assets in zehn Jahren die höchsten Renditen liefern. Eine solche Vorhersage ist nicht belastbar möglich. Die Auswahl priorisiert heute etablierte, liquide und unterschiedlich ausgerichtete Assets, Binance-Spot-Handelbarkeit und mindestens drei Jahre dort verfügbare Historie. Beim Abgleich am 31.08.2026 meldete die offizielle Binance-API für alle zehn Paare `TRADING` und Spot-Handel. Früheste verfügbare Binance-Tagesbars reichen von 2017 bis spätestens 2020 zurück.

Ein Paar darf nur aktiviert werden, wenn es beim jeweiligen Start weiterhin handelbar ist und die geplante Order die aktuellen Börsenfilter erfüllt. Delistings werden nicht automatisch durch ein anderes Asset ersetzt. Eine spätere Änderung der Liste erzeugt eine neue Universums-/Konfigurationsversion und neue Vergleichsbacktests.

## Kapitalmodell

### System 1 – Paper und später Live

- Gesamtstartkapital: **250,00 USDT** für neue Konten (DEC-044). Davon höchstens 240 USDT in drei 80-USDT-Slots und 10 USDT anfängliche Cashreserve; Gewinne/Verluste verändern diesen Puffer. Bestehende Konten behalten ihren tatsächlichen Bestand und ursprünglichen Startwert.
- Gemeinsamer Cashbestand für alle zehn beobachteten Paare.
- Standard: **drei Positionsslots à 80,00 USDT Zielnotional**.
- Höchstens drei gleichzeitig offene Long-Positionen.
- Startzustand: Cash, keine Position, keine Altorder.
- Ein Exit gibt den Slot und das tatsächlich zurückgeflossene Kapital wieder frei.
- Paper läuft 24/7 mit echten Binance-Marktdaten, aber simulierten Orders/Fills.

Kapital, Slotanzahl und Zielnotional müssen wegen Gebühren und verfügbarem Cash konsistent sein. Der Bot darf niemals Kredit aufnehmen oder einen negativen Cashbestand erzeugen.

### System 2 – Backtest-Labor

- Standard-Batch: zehn strikt isolierte Tests mit jeweils **250,00 USDT** Startkapital, insgesamt 2.500,00 USDT reines Simulationskapital.
- Einzeltest: frei wählbares Binance-Paar, zum Beispiel nur ETH/USDT, mit **250,00 USDT** Startkapital.
- Ziel-Quote-Budget je Einstieg ist in diesen isolierten Läufen fest 250,00 USDT oder, nach Verlusten, der kleinere verfügbare Cashbetrag; Gewinne erhöhen die nächste Zielgröße nicht automatisch.
- Jeder Test startet ohne Position und Altorder.
- Einzeltests beeinflussen einander nicht; Ergebnisse werden je Coin und zusätzlich als Vergleichstabelle gezeigt.
- Der verpflichtende Spiegeltest bildet zusätzlich das Paper-/Live-Modell mit 250 USDT und 3×80 USDT samt Risikogates nach.
- 250→500 USDT je Coin in drei Jahren ist nur ein Beispiel für einen guten Test, keine verbindliche Quote oder Garantie. Zuerst wird korrekte Indikatorreaktion bewiesen; danach wird die vollständige Performance einschließlich Zielverfehlungen berichtet.

## Positionsgröße

Initiale Regel:

- maximal eine Long-Position pro Paar;
- kein Pyramiding;
- Zielnotional je neu belegtem Slot: 80,00 USDT;
- die 80,00 USDT sind das maximale Quote-Budget des Kaufs; bei modellierter Zahlung der Kaufgebühr im Basisasset wird die empfangene Assetmenge entsprechend reduziert;
- tatsächliches Notional höchstens verfügbarer Cash nach Reserven und Börsenfiltern;
- Menge wird abwärts auf Binance-Schrittweite gerundet;
- nach Rundung müssen Mindestmenge und Mindestnotional erfüllt sein;
- nicht investierbarer Rest verbleibt als Cash;
- keine Kreditaufnahme, kein negativer Cash-Bestand;
- eine UI-Änderung von Slotanzahl oder Positionsgröße wirkt nur auf neue Einstiege.

Automatisches Compounding ist deaktiviert. Das Zielnotional bleibt im Paper-/Live-Modell 80 USDT und im isolierten Backtest 250 USDT, auch wenn Gewinne entstehen. Nach Verlusten wird höchstens der verfügbare Cashbetrag eingesetzt. Nur eine bewusst bestätigte und auditierte UI-Änderung verändert die Größe künftiger Paper-/Live-Einstiege; bestehende Positionen bleiben unberührt.

## Slotvergabe

Freie Slots gehen verbindlich an den größten auf 12 Dezimalstellen mit Round-Half-Even gerundeten Wert `(close-upper)/ATR` der jeweiligen Flip-Up-Kerze. Gleichstand wird über diese feste Reihenfolge gebrochen: BTC, ETH, BNB, SOL, XRP, ADA, LINK, AVAX, DOT, DOGE. Die Regel verwendet ausschließlich Werte der jeweils ausgewählten Strategieversion und wird im Backtest mit simultanen Signalen geprüft.

Ein Kauf-Flip, der wegen voller Slots nicht ausgeführt wird, wird protokolliert. Er wird nicht später mitten im bestehenden Uptrend nachgeholt, außer die Strategie definiert ausdrücklich eine weiterhin gültige Entry-Bedingung.

Aktive V2 belegt höchstens einen Slot je Coin. Mehrfachslots im selben Coin sind nicht grundsätzlich verboten, benötigen aber eine eigene Strategieversion und denselben vollständigen Vergleich. `HIXTON-V3-SLOT-CANDIDATE-1` testete bis zu drei Slots auf dem stärksten gleichzeitigen Signal und wurde wegen des frühen 20-%-Risikohalts verworfen. Drei Slots im selben Coin erzeugen nur dreifaches Notional auf demselben Signal, nicht drei unabhängige Trades.

## Optimierungsziel

„So viele Trades wie möglich“ darf nicht zu sinnlosen Gebührenumsätzen führen. Rangfolge:

1. korrekte Hixton-Signale und Risikoregeln;
2. robuste Nettowirkung nach Gebühren und Slippage in unterschiedlichen Marktphasen, mit ausgewiesenen Rückschritten;
3. effiziente Slotnutzung durch gute Signale aller zehn Coins; Tradezahl allein ist kein Gütekriterium.

Timeframe oder Parameter werden nicht allein verändert, um künstlich mehr Trades zu erzeugen. Varianten müssen out-of-sample und nach Kosten bewertet werden.

## Schutzregeln, die die Strategie nicht ersetzen

Diese Regeln dürfen eine Order blockieren, erzeugen aber niemals selbst ein Handelssignal:

- Daten sind stale, lückenhaft oder noch nicht synchronisiert;
- Uhrzeit/Zeitzone unklar oder Systemuhr außerhalb Toleranz;
- Börsenmetadaten/Filter fehlen;
- API-/Authentifizierungsfehler;
- unbekannte offene Order oder Positionsabweichung;
- verfügbare Mittel reichen nicht;
- Not-Aus aktiv;
- Live-Modus nicht freigegeben;
- Preis weicht beim Absenden mehr als 25 bps vom Referenzpreis ab.

Jede Blockade wird sichtbar protokolliert.

## Verlustkontrollen

Da „alles über diesen Indikator“ laufen soll, werden keine heimlichen Stop-Loss-/Take-Profit-Signale ergänzt. Operative Schutzschalter bleiben dennoch nötig:

| Kontrolle | Verhalten | Status |
|---|---|---|
| Not-Aus | keine neuen Einstiege; Exit vorhandener Positionen nur separat bestätigen | VERBINDLICH |
| Max. Ordernotional | anfänglich 80 USDT Zielnotional und höchstens verfügbarer Cash | VERBINDLICH |
| Max. offene Positionen | anfangs drei, je Paar höchstens eine; UI-konfigurierbar | VERBINDLICH |
| Max. Tagesverlust | ab 5 % Verlust gegenüber Start-of-Day-Equity keine neuen Entries bis 00:00 UTC; Exits bleiben erlaubt | VERBINDLICH |
| Max. Drawdown live | ab 20 % unter globalem High-Water-Mark Zustand `HALTED`; keine automatische Liquidation | VERBINDLICH |
| Max. Preisabweichung vor Order | 25 bps gegenüber dem zum Intent gespeicherten Referenzpreis; bei Überschreitung blockieren | VERBINDLICH |
| Stale-data-Grenze | kein Streamupdate 90 Sekunden = `DEGRADED`; finale 1h-Bar mehr als 2 Minuten überfällig = Symbol pausieren und REST-Recovery | VERBINDLICH |

Eine Verlustschwelle soll standardmäßig neue Einstiege pausieren, nicht unkontrolliert alle Positionen als Market-Order liquidieren.

## Benchmark und Vergleich

Jede Coin- und Portfolioauswertung vergleicht die Strategie mindestens mit:

- Buy-and-Hold desselben Assets mit identischem Startkapital und Kostenannahme;
- 100 % Cash (0 % Rendite vor Inflation);
- optional einem gleichgewichteten Buy-and-Hold-Portfolio für die Aggregation.

Ein positives Ergebnis allein ist nicht ausreichend; Drawdown, Kosten, Aktivität und Benchmarkdifferenz werden gemeinsam bewertet.
