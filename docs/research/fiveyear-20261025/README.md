# Fünfjahres-Szenarienstudie · 25.–26.10.2026

**Ergebnis: NO_CHANGE. Die Handelsregeln des Bots bleiben unverändert.**

24 konstruierte Fünfjahres-Marktpfade wurden mit der aktuellen nativen Portfolioengine untersucht: 104 Auswahl- und 52 separate Prüfläufe einschließlich Kostenstress. Ein gemeinsames Modellstartkapital von 1.085,77093944 USDC wird wiederangelegt; kein vervielfachtes Kapital pro Coin.

Die ausgewählte Änderung „Core-Slots ohne doppelte Coinbelegung“ ist in der Prüfung gescheitert: 2 von 12 normalen Pfaden besser, 10 schlechter; Median des gepaarten Netto-Unterschieds −955,66 USDC, bei höheren Kosten −71,69 USDC. Keine Ersatzwahl, keine Übernahme in Paper/Live.

Beim aktuellen Bot erreichten alle 24 normalen Modellpfade mehr als 30 % Schlusskurs-Drawdown. Der höchste betrug 79,66 %; der niedrigste Modellkontostand 240,10 USDC. Auch ohne Makro-Extremhinweis bleibt der schlimmste DD 79,66 %. Das sind Eigenschaften dieser konstruierten Pfade, keine Zukunftswahrscheinlichkeiten.

- [Vollständiger Bericht mit Grenzen und nächsten Forschungsfragen](Bericht.md)
- [Portfolioverläufe](Szenarien.png) und [erzeugte Marktpreise](Marktpfade.png)
- [Alle 156 Ergebnisse](Alle-Ergebnisse.csv) und [Coinbeiträge im gemeinsamen Portfolio](Coin-Beitraege.csv)
- [Öffentliche Simulationsspezifikation](Simulation-Spezifikation.json)
- [Vorabplan](Study-Approval.json), [eingefrorene Auswahl](Discovery-Selection.json), [separate Prüfauswertung](Validation-Summary.json)
- [Methodenquellen als Archiv](Methoden-Code.zip), [Datei- und Quellenbindung](Public-Evidence.json)

**Aussagegrenzen:** Wiederverwendete bekannte historische Blöcke sind keine echten zukünftigen Daten. Positiv gewichtete Familien erzeugen teils wirtschaftlich extreme Preisniveaus und dienen als Extremtests. Hohe Modellgewinne sind keine realistische Gewinnerwartung. Feste Slippage und vorheriges Stundenvolumen ersetzen keine Orderbuch-/Markteinflussprüfung. Internet-/Börsenausfälle, Delistings und USDC-Entkopplung sind nicht vollständig modelliert. Endkapital umfasst markierte offene Bestände.

Referenz ist Produktquellstand `bd124cc5f72ea5b64179d0009420bfd4e96807bc`, Strategie `HIXTON-V8-LINK8-ATR075-DOGE50-DD10-ETH8-DIV32-CLOSECAP-PAPER-6`. Dieser Dokumentationsstand ändert keine Strategie, keine Schlüssel, keine Live-Freigabe und keinen laufenden Trade.

Die großen Eingabedatensätze und originalen Laufdateien bleiben lokal; ihre Hashes sind dokumentiert. Die öffentliche Spezifikation ist eine ausdrücklich gekennzeichnete Ableitung und kein Ersatz für das original eingefrorene Kontextdokument. Der veröffentlichte Simulationsstartbetrag ist ein Modellparameter; persönliche Kontosnapshots, API-/Telegram-Schlüssel und Passwörter sind ausgeschlossen.
