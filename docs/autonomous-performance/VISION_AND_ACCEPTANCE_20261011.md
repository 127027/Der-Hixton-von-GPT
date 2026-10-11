# Hixton — Vision und Zielarchitektur: konservativer Kern + autonomer Performance-Modus

**Status:** Spezifikation und Forschungsaufträge, **KEIN aktivierbarer Trading-Release**.  
**Owner-Ziel:** Lokaler Laptop 24/7, genau ein vom Owner bewusst bestätigter Live-Start nach bestandenem 50-USDC-Single-Order-Test. Danach ohne manuelle Trade-Auswahl arbeiten. 1.100 USDC ist ein Startbeispiel; zukünftige Größe richtet sich nach aktuellem von Hixton verwalteten Vermögen, inklusive realisiertem und nicht realisiertem PnL. Der Owner akzeptiert erhebliches Verlust- bis Totalverlustrisiko, verlangt jedoch eine messbare, faktengeleitete Strategie statt blindem Trading.

## 1. Zwei voneinander getrennte Checkboxen, plus bestehender Live-Schalter

1. **„Bot entscheidet über das Budget“** (Flag `auto_budget_enabled`, Default OFF): potenziell gesamtes **von Hixton zugeordnetes** Spot-/Derivate-Equity, abzüglich expliziter Reserven; Compounding nach Gewinnen und Verlusten; beim Start, bei jedem geschlossenen 1h-Balken und **unmittelbar vor Order** per authentifiziertem Read-only-Snapshot neu bewerten. Kein künstlicher 1.100-USDC-Deckel.
2. **„Autonomer Performance-Modus“** (Flag `autonomous_performance_enabled`, Default OFF): Ziel ist optimale *risikoadjustierte, nach Kosten realisierte* Portfolio-Entwicklung mit selbst gewähltem Trade-/Slot-Kontingent, Koin/Richtung/Zeithorizont/Tranche, 1× oder geeigneter zugelassener Hebelstufe, dynamischen Regime-/Abbruchentscheidungen. **1×/keine Position sind gleichwertige gültige Entscheidungen.** Kein KI-Modell darf seine eigene Gewinnwahrscheinlichkeit unbelegt erfinden.
3. **Live-Freigabe bleibt ein eigener, expliziter Bedienvorgang** mit bestehendem bestätigtem 50-USDC-Trial, Credentials-/IP-/Account-Prüfung und Wiederanlaufkontrolle. Die zwei Checkboxen **lösen nie für sich selbst eine Order aus**. Solange autonomer Runtimepfad, Konto-/Order-Abgleich oder Produktberechtigung nicht vollständig geprüft sind, blockieren sie Live serverseitig; nicht nur optisch.

**Fallback:** Beide OFF → unveränderter aktueller konservativer V8-Spot-Bot.  
**Nur Budget ON:** gleicher geprüfter V8-Signal-/Risikoansatz, aber dynamische Kapitalbasis.  
**Nur Performance ON:** adaptive Entscheidungen innerhalb des bestehenden fest vereinbarten Budgetrahmens.  
**Beide ON:** vollständiger Autonomiepfad.  
Unabhängig davon: Hebel benötigt einen **separaten Produkt-Verfügbarkeits- und Freigabegate**. „Risikobereit“ ersetzt keine juristische/technische Marktberechtigung.

## 2. Kapital & Risiko (muss durch ein gemeinsames Ledger)

Definition in USDC:
- `managed_equity` = bot-eigenes freies Collateral + bot-eigene offene Positionen mit **passender Bewertungsmethode** (Spot-Mark-to-Market oder Derivate Mark Price inkl. Unrealized PnL/Funding/Debt) – bereits verbrauchte Gebühren und verfallene Margin. Keine stillschweigende Übernahme fremder manuell gehaltener Coins.
- `deployable_cash` = freie, **wirklich** handelbare Quote/Margin abzüglich reservierter Orders, bereits gebundener Initial-/Maintenance-Margin, Gebühren-/Slippage-Puffer, offener Settlement-Transaktionen. Freie Kaufkraft ist **nicht** gleich Equity.
- Cash/Equity/Positions/Orders bei jedem Trade aus frischem *Exchange-Snapshot* plus lokalem eindeutigen Orderjournal **atomar abgleichen**; unbekannte Ein-/Auszahlung, fremde Orders, unklare Fills, veraltete Snapshots → **keine neuen Orders** und Alarm.
- Compounding heißt: 1.100 → 1.200 → 950 sind zulässige neue Bemessungswerte nach Markt-/Kontoveränderungen. Es gibt **keine automatische Kreditaufnahme** und keine stillschweigende Kontoeinzahlung.
- Verlustrisiko über **Equity und Portfolio-Exposure** entscheiden: erwarteter Stop-Abstand, Gap-/Slippage-Stress, Korrelation, Netto-Risiko, Maximalverlust bei mehreren gleichzeitigen Positionen. Bloße Hebelzahl oder Signalstärke ist keine Risikoabschätzung.
- Kein erzwungenes „100 % immer investiert“: Die **100 % Kapitalzugriffsberechtigung** ist vom realen Einsatz zu unterscheiden; Cash oder 1× kann bestes Resultat sein.
- Equity 0 oder Konto-/Marktzustand nicht handelbar: **STOP/NOTIFY**, nie Schulden oder riskante Recovery-Strategien. Technische Verlust-, API-/Daten-/Kommunikations-Stoppregeln sind Sicherheitsfunktionen, keine willkürliche Renditebremse.

## 3. Hebel und Realismus (wichtigster Neubau)

Der aktuelle Hixton ist ein **Binance Spot-Long 1×-Produkt**. Sein Backtest und `LivePortfolioController` können aktuell keine Exchange-konforme Futures- oder Margin-Position ausführen.

- 5×, 10×, 100× werden **als Forschungsräume** betrachtet, nicht als notwendiger Handel oder impliziter Default. 100× auf volles Konto ist kein Qualitätsmerkmal; 1 % Gegenbewegung kann die eingezahlte Margin ungefähr auslöschen, Liquidation häufig früher.
- Keine 1h-Spot-OHLC-Daten als ausreichender Liquidationsbeweis. Reale historische **Kontrakt-, Mark-Price- und Funding-Zeitreihen**, Liquidations-/Margin-Tiers, Contract Specifications und je nach Produkt Borrow/Interest benötigen eigenen Provenienz- und Kalibrierungspfad.
- Eigenständiges `DerivativePaperExchange` und `MarginLedger`: Initial-/Maintenance-Margin, isoliert vs. Cross, Gebühren, Spread/Slippage, Funding, Liquidations- und Insurance Fees, Mark-Price-Touch intrabar, Partial/Forced Fills, Rundung/MinNotional, Gebührenstufen, Rebalancing, API-/Laptop-/Stromausfall-Gap.
- Gleiche synthetische Ereignisse in **Backtest und Paper** mit identischer Ausführungsfunktion. Derivate-Realhandel erst, wenn der **konkrete zugelassene Markt und das Nutzerkonto** aktuell nachgewiesen sind; keine Umgehung von Länderbeschränkungen. Die Spot-API verlangt derzeit `enableMargin=False`, `enableFutures=False`; das wird nicht stillschweigend geändert.
- Getrennte, *immutable* Szenarien: 1×, 2×, 3×, 5×, 10×, Extremtest 100×; eine dynamische Kandidatenstrategie darf die Hebelwahl **nur point-in-time** auf bereits bekannten Daten treffen. Eine hohe historische Quote erfolgreicher Trades beweist keine Prognosegüte.

## 4. Beobachtung → Entscheidung → Ausführung (24/7)

`Feed -> ClosedBar / OrderBook / MarkPrice -> RegimeClassifier -> OpportunityRanker -> RiskAndCapitalAllocator -> DecisionJournal -> ExecutionAdapter -> Reconciler -> Monitor`

Zielgröße: **risikoadjustierter Nettogewinn nach ALLEN Kosten mit Überlebens-/Ruin-Risiko**; parallel absolute USDC-Zuwächse, Max-Drawdown, Zeit im Markt, Tradefrequenz, Fee Drag, Slippage, Liquidationsrate und schlechtestes Jahr. Modelltraining gehört **offline** in die Research-Pipeline; Modell-/Konfigurations-Updates versioniert, reproduzierbar und **nicht** während Live ungeprüft selbstüberschreibend. Adaptive Live-Regeln können auf verifizierte Zustandsdaten reagieren, aber neue ungetestete Strategien bleiben gesperrt.

Vor jeder neuen Order: State-SHA, Signal-SHA, Timestamp, Exchange-Account-ID-Fingerprint, verfügbare Mittel, Margin Requirement, risk-at-stop, Gesamtportfolio-Exposure und Orderjournal überprüfen. **Idempotency**: bei unklarer Exchange-Antwort Order zuerst suchen/abgleichen, nicht erneut senden. Bei Netzwerk-/Systemausfall externe Schutzorders berücksichtigen. Dashboard zeigt Entscheidung + Alternative + Sperrgrund + Risiko, historische und aktuelle realisierte PnL.

## 5. Wissenschaftlich belastbarer Backtest

**Konkrete bisherige Referenz:** `c004eaf244e1638e6cbb4da8a4a9b5a9e8f71776`, V8, 15 Märkte, UTC 2023-10-10 19 bis 2026-10-10 19, 400 Warm-up, BTC/ETH/BNB/SOL/XRP/ADA/LINK/AVAX/DOT/DOGE Core, fünf Satellites; Spot-Regeln. 250-USDC Shared 198 Trades → 1.601,35 USDC. 1.100-USDC research: 2×550 fest ≈ 7.055 USDC, kompoundierend ≈ 24.673 USDC *mit ≈ 55,44 % Drawdown und ohne Hebel*. **Keine Zukunftsprognose, keine Derivate-Validierung.** 100×-Liquidationsscreen bisher lediglich indikative Spot-Lows, kein Portfolio-Backtest.

Kausalität: Point-in-time nur bereits abgeschlossene 1h-Balken, nächste ausführbare Order, vollständige Zukunftspreis-/Funding-/Margin-Events in chronologischer Reihenfolge. Bei Liquidation wird das zukünftige Konto *sofort* verändert; darf nicht denselben Spot-Trade später einfach als Normalgewinn abrechnen.

Tests müssen zeigen:
1. **Exakt reproduzierte alte Baseline** und V6-Regression (keine stillschweigende Ergebnisänderung).
2. Fixe Daten-SHA pro Coin/MarkPrice/Funding, echte USDC vs. USDT-Proxy markieren; Datenlücken/gaps → Test fehlschlagen.
3. Vergleiche: 1.100 USDC statisch, 1.100 USDC compounding, adaptive 1–N Slots, adaptive 1×/2×/3×/5×/10×/100× mit identischem Kapital und Kapazität.
4. **Kein Auswählen von Strategien nach ihrem 3-Jahres-Endgewinn.** Diese drei Jahre wurden bereits betrachtet und sind *keine* unberührten Holdout-Daten. Innerhalb davon Rolling Walk-Forward mit train-only Auswahl, plus spätere neue, tatsächlich unberührte Forward-Paper-Daten.
5. Robustheit: 2×/3× Kosten-/Slippage-Stress, illiquide Märkte, Spread-Spikes, Markpreis-Gaps, Systemausfall, Netzwerkunterbrechung, Doppel-Order, dynamisch neu berechneter Kontostand, Margin-Änderung, dreifach korrelierte Liquidationen.
6. Ein Backtest ohne echte Derivate-Daten/Contract-Mechanik muss ausdrücklich **UNREALISTIC_FOR_MARGIN** markieren und darf weder Gewinner noch 100× live promoten.

## 6. Rollen und Auftrag an den bestehenden Engineering-Swarm

Es gibt **11 definierte A01–A11-Engineering-Agenten** in `agent_memory/swarm/registry.json`. Ihr aktueller automatischer Lauf auf `main` schlägt fehl; der separate Checkout-Smoke von [PR #7](https://github.com/127027/Der-Hixton-von-GPT/pull/7) ist grün, beweist aber **nicht**, dass 11 Agents parallel durchgelaufen sind. DOTs D12–D20 sind hier **neue Forschungs-Workstreams**, keine aktuell nachgewiesenen laufenden unabhängigen Prozesse.

| Kennung | Eigenständiger Auftrag / Nachweis |
|---|---|
| A01 | Diese Vision gegen sämtliche V8, Frozen V6, alten Agent-Taskboard- und UI-Verträge reconciliieren; keine veralteten AAVE/NEAR/BCH-Freigaben |
| A02 | Rolling-3Y, 15 isolated × 1.100/250 Forschung, feste-vs-compounding Portfolio-/Strategie-Abstimmung, OOS-Reject-Gate |
| A03 | gemeinsamer dynamischer Ledger + chronologische Paper-Ausführung, Restart/Idempotency/Live-Parität |
| A04 | zwei persistente Haken, Live explizit separat, vollständiges Entscheidungs-/Risiko-Dashboard inkl. Klartext „nicht Live-freigegeben“ |
| A05 | Laptop 24/7, Reconnect, Watchdog, Stale Data/Mark Price/Funding, Shutdown und Fail-Closed |
| A06 | deterministische Regression Backtest/Paper/Trial/Live, V6 freeze, API/UI/static bundle |
| A07 | Binance öffentliche Kontraktdaten, API-Rechte, Länder- und KYC-/Marktfreigaben, exchange filters, Mark/Funding-Archive |
| A08 | Action-space, Portfoliorisiko, variable Kapital- und Hebelentscheidung, Opportunitätskosten, Ruin- und Korrelationsanalyse |
| A09 | unabhängige *exakt-Commit*-QA der Quellcode- und Paper-Belege, keine selbst erteilte Freigabe |
| A10 | Projektsteuerung, Aufgabenpriorisierung, Blocker, Reparatur-Reruns, Evidenz-Links |
| A11 | unabhängige Agentenaufsicht, gegen Scheinerfolge/falsche Backtestvergleiche, separate technische Freigabe |

**Spezialisierte DOT-Workstreams (erst implementieren/validieren, nicht als laufend ausgeben):** D12 Konto-Equity/Budget; D13 dynamischer Trade-Zähler und adaptive Allokation; D14 Trend/Seitwärts/Crash-Regime; D15 Leverage-Policy/Markprice; D16 Liquidations-/Funding-Ledger; D17 Portfolio-Korrelation/Risk-of-ruin; D18 Daten-/Trainingsintegrität und „no lookahead“; D19 Ausfallszenarien 24/7; D20 unabhängige Effekt-/Kosten-Falsifikation.

## 7. Harte Meilensteine / Abbruchgrenzen

**M0**: Konservativer Referenzbot als goldene Baseline unberührt; V6 unverändert.  
**M1**: Zwei Checkboxen als getrennte sichere *Forschungsvormerkung* speichern. Backend blockt beide im Livepfad; Tests.  
**M2**: Kompoundierender dynamischer Spot-Allocator über dieselbe Wallet-/Ledger-Schicht in Backtest/Paper implementieren; absolute Referenzkosten.  
**M3**: Vollständige Derivate-Simulationsdaten/Execution-Modell für mark/funding/margin/liquidation, inklusive tatsächlichem Portfolioeffekt; 100× rein als Stress-Szenario.  
**M4**: Selbstständige Entscheidungen über Anzahl/Größe/Instrument/Hebel durch robuste, point-in-time, train-only kalibrierte Policy; mehrere OOS/Walk-Forward-Szenarien, stabiler Nettoeffekt und Verlustkontrolle.  
**M5**: 24/7 Paper-Soak, Restart-Gap-/Network-Fault-Tests, unabhängiger QA_PASS und GOVERNANCE_PASS auf exakt einem finalen SHA.  
**M6**: Nutzer führt ausdrücklich 50-USDC-Trial und Live-Aktivierung durch; erst wenn das **konkret erlaubte Produkt** zusätzlich nachweisbar ist, kann dessen geprüfter ExecutionAdapter freigeschaltet werden. Ohne Zulässigkeit bleibt gehebelter Modus Paper-only, Spot 1× weiterhin verfügbar.

**Explizit verboten:** automatischer Live-Start durch das Setzen der Haken, Pushen von API-Secrets in GitHub, Nutzung einer historischen „Gewinnwahrscheinlichkeit“ als unkalibrierter Hebelindikator, stilles 100×-Live, Umgehung der geografischen Produktbeschränkung, automatische Selbstpromotion eines Modells ohne neue QA.

## 8. Sichtbarer heutiger Istzustand (Stand 11.10.2026)

- **Produkt:** V8 15 Spot-USDC-Märkte, long-only, 1h, zwei 50/50-Slots; historische Compounding-/5×/10×-Sensitivität nur isolierte Research-Skripte.
- **Live:** `src/hixton/live/production.py` akzeptiert nur 1–2 Slots mit festem Plan; `src/hixton/live/binance.py` blockiert Margin/Futures-Rechte. Keine `DerivativePaperExchange`-Komponente.
- **UI:** erster auto-budget-Haken in Draft PR #8, Default OFF; vorliegender Forschungsbranch baut zweiten Performance-Haken auf diesem Stand auf.
- **Daten:** 3Y USDC/USDT-Proxy mit Echtheitsprotokoll; **keine** drei Jahre historische Futures-Mark-Price-/Funding-/Maintenance-Tiers in den bestehenden V8-Evidenzdateien belegt.
- **A01–A11:** Agentenrollen vorhanden, automatisierter Schwarm auf `main` aktuell FAILED; letzter bewiesener Checkout-Smoke repariert nur den ersten Lifecycle-Aufruf.
- **Integration:** Bestehender 50-USDC-Trial und Live-Enable sind voneinander getrennt; diese Bedingung bleibt unverändert.
