# Gemeinsame Kapitalbasis nach Signal-Kerzenschluss

Die versionierte Regel `FINALIZED_CLOSE_OWNED_POSITIONS_V1` vereinheitlicht die
Bewertung neuer Orders in Portfolio-Backtest, 250-USDC-Einzeldiagnose, Paper und
normalem Live. Tatsächlich freies USDC plus eigene offene Positionen, bewertet
mit den ausgerichteten endgültigen Schlusskursen des Signalzeitpunkts, ergeben
das Einstiegskapital. Neue Kurse der Ausführungskerze beeinflussen die Fills,
aber nicht diese Bewertung. Kleine nicht handelbare Restbestände bleiben in der
Kontorechnung sichtbar und werden nicht zum Budget weiterer Käufe gerechnet.
Eine Order bleibt durch tatsächlich freie USDC begrenzt. Live verwendet weiterhin
vor jedem Versuch einen frischen signierten Kontosnapshot und den Kontenabgleich.

Zuvor verwendeten Backtest/Paper die nächsten Open-Kurse einschließlich Dust,
Live dagegen die letzten abgeschlossenen Kurse ohne Dust. Bei einer Kurslücke
konnten dadurch die Budgetentscheidungen voneinander abweichen. Beispiel:
500 USDC frei, fünf eigene BTC, letzter Schlusskurs 100, nächster Open 50:
alte simulierte halbe Tranche 375, Live 500. Die neue gemeinsame Regel ergibt 500.
Das ist eine Korrektur der Entscheidungsgrundlage, keine Renditeprognose.

Der vollständige vorherige DIV32-/ATR0,75-Vertrag bleibt als
`V8_DIV32_PAPER_STRATEGY` registriert. Bereits eröffnete echte Einmaltests behalten
ihre ursprüngliche Strategie, Quelle, Order-/Fillidentitäten, Baseline und regulären
Ausstieg. Ein neuer ausdrücklich gestarteter Test verwendet den aktuellen Vertrag.
Der Einmaltest hat weiterhin seine feste 50-USDC-Kaufgrenze und wird nicht durch die
normale Portfolio-Allokation erweitert. Keine Aktualisierung aktiviert Echtgeld.

Für diese reine Änderung neuer Einstiegskapitalbewertungen existiert eine
ausdrückliche atomare Paper-Migration. Sie erlaubt keine Änderung von Indikatoren,
Ausstiegen, Routing oder Allokation. Sie erhält Cash, Positionen samt ursprünglicher
Einstiegsidentität, Restbestände, Risiko, Checkpoints, Ereignisse und den latched
Diversifikationsstand. Sie erzeugt keine künstlichen Verkäufe oder Kontoeinzahlungen.
Statusabfragen und Neustarts führen diese Migration nicht selbstständig aus.

Die historischen und synthetischen Zahlen älterer Regeln bleiben historische
Nachweise. Nach der Korrektur werden aktuelle Berichte neu berechnet. Gemeinsame
Regeln garantieren keine identischen echten Fillpreise, Gebühren oder Latenzen und
keine feste maximale Verlustgrenze. Der 5%-Tagesverlustschutz pausiert neue Käufe;
er liquidiert bestehende Positionen nicht sofort.
