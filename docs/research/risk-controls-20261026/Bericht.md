# Risikoregeln auf den aktuellen letzten drei Jahren · 26.10.2026

**Vorab festgelegter Vergleich, keine nachträgliche Parametersuche.**

Zeitraum: **2023-10-26 14:00:00+00:00 bis 2026-10-26 14:00:00+00:00**, plus 400 Stunden Vorlauf. Gemeinsames Startkapital **1.085,77093944USDC**, Start in Cash, Wiederanlage von Gewinnen/Verlusten. Der Benutzer hat ausdrücklich den zuletzt belegten Betrag als Vergleichsseed gewählt; er ist kein frisch bestätigter Kontostand.

15 Profile liefern gemeinsam Signale. 10 Core und 3 nominelle Shared-Filler bleiben erhalten; SUI/UNI sind weiterhin Research-only. Die tatsächliche Fillerfreigabe hängt zusätzlich von den bisherigen Profil-/Qualitäts-/Core-Prioritätsregeln ab.

## Ergebnis bei normalen Kosten

| Regel | End-USDC | Max. Schlusskurs-DD | Differenz zur Baseline |
|---|---:|---:|---:|
| Unveränderter Bot | 11.004,18 | 38,23% | 0,00 |
| 5%-Tagesausstieg, bis Tageswechsel pausieren | 3.642,60 | 37,25% | -7.361,58 |
| 5%-Tagesausstieg, mindestens 24 Stunden pausieren | 3.446,47 | 36,86% | -7.557,70 |
| Neue Positionen bei Drawdown verkleinern | 7.155,98 | 30,36% | -3.848,20 |
| Verlust-Coin 24 Stunden pausieren | 11.131,71 | 38,23% | 127,53 |
| Kaufgröße nach vorherigem Stundenvolumen begrenzen | 10.787,35 | 39,75% | -216,82 |
| Strengerer Core-Momentumfilter | 6.458,91 | 43,85% | -4.545,26 |
| Alle neuen Schutzregeln kombiniert | 3.155,48 | 32,40% | -7.848,69 |

## Gleiche Strategien unter höheren Ausführungskosten

| Regel | Erhöhte Kosten: End-USDC / DD | Impact-Annahme: End-USDC / DD | Zulässig nach Vorabgates |
|---|---:|---:|---|
| Unveränderter Bot | 7.568,85 / 47,75% | 9.215,81 / 42,16% | ja |
| 5%-Tagesausstieg, bis Tageswechsel pausieren | 2.401,39 / 47,02% | 3.155,95 / 39,75% | nein |
| 5%-Tagesausstieg, mindestens 24 Stunden pausieren | 2.257,74 / 46,68% | 2.943,58 / 39,29% | nein |
| Neue Positionen bei Drawdown verkleinern | 4.885,23 / 35,15% | 6.896,98 / 30,96% | nein |
| Verlust-Coin 24 Stunden pausieren | 7.669,27 / 47,75% | 9.323,82 / 42,17% | nein |
| Kaufgröße nach vorherigem Stundenvolumen begrenzen | 7.523,75 / 48,33% | 9.817,89 / 42,66% | nein |
| Strengerer Core-Momentumfilter | 4.550,30 / 52,18% | 5.802,91 / 46,52% | nein |
| Alle neuen Schutzregeln kombiniert | 2.455,75 / 37,55% | 2.834,61 / 33,21% | nein |

## Entscheidung

Auswahl: **current**. Status: **NO_CHANGE**. Zulässig sind nur technisch einwandfreie Fälle mit mindestens demselben Endkapital und keinem größeren Drawdown unter jedem der drei vorab festgelegten Ausführungsmodelle. Innerhalb dieser Menge gilt der höchste normale Nettogewinn zuerst, Drawdown zweitens. Ein neuer Gewinner benötigt anschließend den festgelegten Fünfjahres-Robustheitsvergleich und vollständige gemeinsame Produktintegration samt unabhängiger QA/Governance. Keine Ersatzwahl nach Ablehnung.

## Was die 5 % bedeuten

Die Baseline pausiert neue Käufe bei 5 % Verlust gegenüber der UTC-Tagesbasis. Sie verkauft deshalb keine offenen Positionen automatisch und kann sich am selben Tag wieder freigeben. Die beiden neuen Tagesausstiege lösen bei abgeschlossener Stundenkerze aus, verkaufen frühestens zur folgenden ausführbaren Eröffnung und bleiben bis Tageswechsel bzw mindestens 24 Stunden gesperrt. Solange Ausstiegspflichten offen sind, bleiben neue Käufe gesperrt; die Ausstiege werden weiter versucht. Dies ist weder ein börsenseitiger Stop noch eine5%-Verlustgarantie: Gaps, Gebühren, illiquide Reste und Ausfälle können die Schwelle überschreiten.

## Ausführungsannahmen und Grenzen

Normale Kosten je Seite:10bpGebühr+2bpSpread+3bpSlippage. Stress:10+10+20bp. Die zusätzliche Impact-Sensitivität verwendet normale Kosten plus10bp×sqrt(Orderquote/(1%vorheriges abgeschlossenes Stunden-Quotevolumen)). Das ist eine ausdrücklich unkalibrierte Annahme, kein rekonstruiertes historisches Orderbuch. BUY verwendet das vor dem Fill bekannte Budget; SELL die gerundete eigene Menge mal Referenz-Eröffnung. Fehlendes Volumen oder nichtpositive Ausführbarkeit macht einen Fall unbeurteilbar; kein günstiger Ersatzfill.

Historische USDC-Lücken sind transparent durch die bereits verwendete USDT-Kontinuitätsquelle ergänzt. Deren Preis und Quoteumsatz beweisen keine historische USDC-Liquidität. Aktuelle Exchangefilter sind eine einheitliche Annahme und keine historische Point-in-time-Rekonstruktion. Offene Endpositionen bleiben markiert, ohne erfundenen Schlussverkauf. Stundenschluss-DD kann höhere zwischenzeitliche Verluste unterschätzen. Internet-/Börsenausfälle, Delistings und USDC-Entkopplung sind durch diese Kursrechnung nicht vollständig abgedeckt.

Es wurden weder echte Orders noch Neustarts, Livefreigaben oder Schlüsseländerungen ausgelöst. Ein Researchoverlay ist kein bereits implementierter Livevertrag.
