# Historischer Backtest: drei oder fünf Jahre

Die Oberfläche bietet für den aktiven V8/V8r-Bot drei und fünf Kalenderjahre.
Der Klick fixiert das Testende auf die letzte abgeschlossene UTC-Stunde;
der Beginn liegt genau drei bzw. fünf Kalenderjahre davor. Am 29. Februar
wird auf den 28. Februar des Zieljahres zurückgegangen. Die 400 Stunden
Aufwärmphase liegen zusätzlich vor dem Berichtsfenster.

Fünf Jahre verkürzen sich nicht auf den gemeinsamen Datenbeginn aller Coins.
Ein später verfügbarer Coin erhält ausschließlich echte Kerzen und seine
eigene vollständige Aufwärmphase. Davor gibt es für ihn keine Signale oder
Käufe. Vollständig fehlende Märkte bleiben unhandelbar. Die Oberfläche und
das Manifest nennen Datenlücken. Interne und nachlaufende Lücken nach Beginn
einer Historie bleiben Fehler; sie dürfen bestehende Positionen nicht falsch
bewerten. API-/Netzfehler gelten nicht als fehlende Historie.

Die bestehende historische USDT-Kursvertretung für ältere USDC-Zeiträume bleibt
ausgewiesen. Sie belegt keine historische USDC-Liquidität. Aktuelle Filter,
Gebührenmodell, Handelsregeln, Kapitalverteilung, Risiko und Wiederanlage
bleiben dieselben. Die Auswahl ist keine neue Handelsstrategie. Die aktuelle
Marktauswahl ist rückblickend festgelegt; das ist kein unabhängiger Holdout.

Bei einem ausgeschalteten Bot ergänzt der Fünfjahrestest fehlende letzte
USDC-Stunden ausschließlich in seinem Backtest-Speicher. Er verändert keine
Paper-/Live-Kerzen, Schlüssel, Freigaben, Orders oder fremden Bestände.
Automatik verwendet wie bisher frisch verfügbares Spot-USDC; eine gescheiterte
Abfrage wird nicht durch ein Ersatzbudget verdeckt.

CLI: `python src/main.py backtest portfolio --strategy v8r --years 5`.
Ohne Auswahl bleiben es drei Jahre. Berichte der zwei Zeiträume werden in der
Oberfläche getrennt angezeigt. Ein laufender Backtest blockiert weitere
Teststarts. V6 bleibt bei seiner bisherigen Dreijahresfunktion.
