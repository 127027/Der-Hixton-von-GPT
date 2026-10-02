# 24 – Autonomous Research Charter

Status: RESEARCH-CURRENT · 02.10.2026

## Zweck

Die Dokumente 02–23 beschreiben den aktuell freigegebenen Produkt- und
Sicherheitsvertrag. Sie sind **kein Forschungsdeckel**. Autonome Research-Dots
dürfen Annahmen des aktuellen Produkts herausfordern, solange Forschung,
Engineering-Promotion und Live-Aktivierung klar getrennt bleiben.

## Frei erforschbar

Research darf insbesondere untersuchen:

- die ursprüngliche Hixton-Basis als hochfrequenten Opportunity-Sensor;
- Micro-Harvest-/Sekundärstrategien neben der gefilterten V6;
- Entry-, Exit-, Haltezeit-, Stop-, Trailing- und Regime-Logik;
- alternative Slotzahl, Routing, Ranking und Opportunity-Cost-Steuerung;
- zusätzliche liquide Binance-USDC-Spotmärkte außerhalb der aktuellen zehn Coins;
- alternative Timeframes ausschließlich offline;
- point-in-time News-/Event-Features;
- Korrelation, Volatilität, Liquidität und Marktregime;
- Hebel/Sizing **nur als Offline-Simulation**, nachdem ein ungehebelter Edge robust bestätigt wurde.

## Nicht automatisch frei

Ein Research-Ergebnis ändert weder das aktuelle Produkt noch Live:

1. Research-Kandidat mit Kosten-, Stress-, Holdout-/Cross-Window- und Shifted-3Y-Evidence.
2. Unabhängiges Red-Team versucht den Fund zu widerlegen.
3. Erst danach entsteht ein enger Engineering-Kandidat.
4. Der exakte Kandidaten-Commit durchläuft A01–A11.
5. Nur A09 QA_PASS plus A11 GOVERNANCE_PASS erlaubt eine Engineering-Promotion.
6. Paper-/Live-Aktivierung, neue Echtgeldmärkte, Margin/Futures oder echter Hebel bleiben separat und werden nicht automatisch aktiviert.

## Forschungsziel

Primär: robusten Nettogewinn nach realistischen Kosten steigern.

Sekundär:
- mehr valide abgeschlossene Gewinngelegenheiten;
- weniger vermeidbare Idle-/NO_FREE_SLOT-Zeit;
- bessere Gewinn-/Positionsstunde und Gewinn-/Kalendertag;
- robuste Diversifikation, wenn bestehende Coins keine Gelegenheit liefern.

Mehr Trades allein sind kein Erfolg.

## Basis-Signal-Mining

Die ursprüngliche Hixton-Basis darf tausende Roh-Flips erzeugen. Ein Roh-Flip ist
kein Trade. D16 misst zunächst Forward Excursion, First-Touch, Kostenempfindlichkeit,
Signal-Overlap und Slot-Konflikte. Erst wenn ein Teilcluster nach Gebühren/Slippage
robust bleibt, darf daraus eine Micro-Harvest-Regel gebaut werden.

## Universe Discovery

D15 darf öffentliche Binance-USDC-Spotmärkte nominieren. Ein Coin wird nur dann
Engineering-Kandidat, wenn ausreichende Historie/Liquidität vorliegen und sein
**marginaler Beitrag zum gemeinsamen 250-USDC-Portfolio** Baseline und Stress
verbessert. Isolierter Gewinn reicht nicht.

## Events / News

D13 archiviert nur Informationen mit ursprünglichem Veröffentlichungszeitpunkt.
Spätere Kursentwicklung darf niemals rückwirkend als Eingangsfeature benutzt
werden. Eventregeln brauchen Replay, Walk-Forward, Red-Team und Paper-Forward.

## Hebel

Hebel ist eine Forschungsvariable, keine Produktfreigabe. Der aktuelle Livevertrag
bleibt Binance Spot ohne Margin/Futures. Eine Hebelsimulation muss Finanzierung,
Liquidation, Tail-Risk, Gebühren und Stress abbilden und darf erst nach einem
ungehebelten robusten Edge untersucht werden.
