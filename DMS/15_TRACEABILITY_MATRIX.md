# 15 – Traceability-Matrix

Aktueller Vorrang: **DMS 1.12.0 / DEC-053 / Anwendung 0.4.7**. Der integrierte Code verwendet USDC (250 Modellstart, Standard 3×80; später genau ein 50-USDC-Test). Alte datierte USDT-Anforderungen/Ergebnisse sind Historie, keine umgerechneten USDC-Nachweise. Runtime- und Laptop-Deployment sind getrennt zu prüfen. Kein Echtgeldstart: technischer Restarbeitsplan in [DMS 20](20_BETRIEBSRUNBOOK.md), tatsächlicher Testnachweis in [DMS 12](12_TESTS_ABNAHMEKRITERIEN.md). Bestehende Live-Sicherheitsgates bleiben wirksam.

DEC-052 → `domain/markets.py`, `domain/versions.py`, `backtest/usdc_review.py`, kanonische Einzel-/Portfolioengines, Quote im Reporting, `CandleStore(read_only=True)`: getrennte USDC-Prüfung und zeitraumgleiche USDT-Kontrolle, keine Kontomigration. Nachweise `tests/test_usdc_review.py`, `tests/test_storage.py`, `backtests/v7/validation-20260908.json`, DMS 18. Status **Validierungswerkzeug umgesetzt; Robustheit NICHT bestanden; USDC-Runtime/Live-Adapter OFFEN**. UI-Signalzeit → `ui/src/market-signal.ts`, `main.ts`, UI-Regression und sichtbare Laptop-Prüfung. Keine Finanztransaktion ausgeführt.

DEC-051 → `live/binance.py`, `paper/models.py`, `ui/api.py`, UI-Controller: kompakte Marktfilteranfrage und redigierte phasenbezogene Fehler; konfigurierbares Positionsbudget ohne 240-Grenze, kein erfundenes Guthaben; serverbestätigte Live-Markierung; genau ein 50-USDT-Test ohne Checkbox. Nachweis: Transport-/API-/Engine-Regressionen und UI-Zustands-/Speichertests, DMS 12/18. Echtgeldadapter/Abgleich unverändert OFFEN. DEC-050 bleibt Grundlage der drei UI-Bereiche und einfachen Speicherung.

DEC-049 → `ui/src/settings-draft.ts`, `main.ts`, `live-preparation.ts`, `ui/api.py`, `ui/live.py`, `paper/models.py`: gemeinsame persistente Einstellungen, eindeutige Entwurfs-/Speicherstandsanzeige, serverseitige Freigabegrenzen und Entry-Pause statt doppelter Echtgeld-Stopp-Aktionen. Sechs zusätzliche Pythonfälle und drei zusätzliche UI-Tests; insgesamt 196/7. Laptop-/Browsernachweis in DMS 18. Echtgeld-Ausführung bleibt separat offen, Grenze 3/240 nicht erweitert.

DEC-048 → `live/trial.py`, `tests/test_live_trial.py`, Live-Service/API/UI und Tests: Einmalbudget-/Signal-/Exitcontroller fake-getestet, sichtbare gesperrte Key-Felder und explizite 50-USDT-/Live-an/aus-Aktionen implementiert. Start bleibt absichtlich blockiert. **Produktiver Exchange-/Supervisor-/Konto-Reconciler, reale Positionsanzeige und Mehrslotbetrieb OFFEN**. Ein erfolgreicher Fake-Rundlauf ist kein echter Binance-Nachweis. Vollständiger Übergabestand DMS 20.

DEC-047 → DMS 07/08/12/13/20: signalgesteuerter 50-USDT-Einmaltest und echter Abschlussbericht verbindlich spezifiziert. **Globale Einmalbudget-Freigabe, Runtime-/UI-Anbindung, echter Binance-Adapter und Ausführungsabnahme weiterhin OFFEN.** Vorhandene `live/orders.py`-Tests decken nur die isolierten Orderprimitiven ab, nicht diesen vollständigen Einmaltest. Keine Strategieänderung und kein Teststart durch Dokumentationsfreigabe.

DEC-046, Ergänzung 0.4.1 → `src/hixton/live/orders.py` / `tests/test_live_orders.py`: isolierte Intent-/Submit-Beanspruchungs-/Teilfill-/Reconciliation-Primitiven mit Fake-Börse getestet. Kein produktiver Adapter und keine Verbindung zum UI oder Runtime; vollständige unten genannte Live-Nachweise bleiben offen.

DEC-046 → UI-Settings/SEC/Live-Vorbereitung: `ui/src/settings-draft.ts`, `ui/src/live-preparation.ts`, `src/hixton/live/`, `src/hixton/ui/live.py`, `tests/test_live_preparation.py` und `ui/tests/settings-draft.test.mjs`. Entwurf/gespeicherter Stand, Windows-Vault, Passwortsession, Read-only-Prüfung und fail-closed Live-Anforderung implementiert. **Order-Intent/Submit/Fill-/Reconciliation-/Live-aus mit offenen Echtgeldpositionen weiterhin OFFEN**; nicht durch positive UI-/Vault-Tests als abgenommen markieren. Umfang/Grenzen DMS 07/11/12/20.

DEC-045 → CAP-010/OPS-010: `paper/maintenance.py`, CLI `paper-fresh-start`, `tests/test_paper_maintenance.py`, aktive V6-Config und UI-Beschriftung. Vollarchiv, neues separates 250-USDT-Konto, ausschließlich neue Paperereignisse/Soak und unveränderte Marktdaten; Auslieferungsnachweis DMS 18.

DEC-043/044 → STR-009/CAP-009/CAP-001/BKT-010/UI-Profilanzeige: `tests/test_coin_profiles.py`, `StrategyDefinition`, `TradePolicyGate`, `PaperStore`, `backtests/v6/candidate.json` und `backtests/v6/README.md`. Alle zehn Profile, Kapitaltrennung, Neustart-/Fill-/Chart-Parität und erhaltene Altledger sind technisch geprüft. Die Mehrfenster-Portfoliorückschritte sind ein offener fachlicher Eignungsnachweis, keine grüne Robustheitsabnahme.

Zusätzlicher Nachweis ab 05.09.2026: `tests/test_runtime_parity.py` deckt DEC-040, DAT-006 (provisional), Folge-Open-Ausführung, Slot-/Cash-/Dust-Parität, Restart und Markerzeit ab. DEC-041 wird durch `backtests/v4/README.md` und den reproduzierbaren Befehl `backtest research` belegt. V4 ist keine aktive Strategie.

V5/DEC-042: `tests/test_trade_policy.py` belegt Identitäts-, Kausalitäts-, Versionssperr- und Einzel-/Portfolio-Parität der Forschungsregeln (STR-008, BKT-002/003/007). `backtests/v5/README.md` und sein kuratierter JSON-Nachweis ordnen alle zehn Coin-Schwächen, trainierte Finalisten, Original-Pine-Kontrolle und Rückschritte zu. Aktive V2-Konfiguration, Positionsbestand und Paper-Regeln bleiben unverändert; eine V5-Paperparität wird nicht behauptet.

Diese Matrix verhindert, dass eine Anforderung nur im Text existiert, aber später weder gebaut noch geprüft wird.

| Anforderung | Fachquelle | Zielkomponente/UI | Haupttest/Nachweis |
|---|---|---|---|
| STR-001 exakte Hixton-Logik | DMS 03, `HIXTON-SPEC-1.0` | Indicator/Strategy Engine | Golden-Spezifikationsparität |
| STR-002 nur geschlossene Bars | DMS 03 | Data/Strategy Engine, Chart | Streaming-vs-Batch-Test |
| STR-003 einmaliger Kauf bei Flip-Up | DMS 03 | Strategy Engine | Zustandsmaschinen-Unit-Test |
| STR-004 Down schließt Long | DMS 03 | Strategy/Execution | Szenario flat/long |
| STR-005 Parameter/Warm-up | DMS 03; DEC-001/002/003/011 | Config/Engine | Config-Schema + Golden-Test |
| STR-006 1.000 Golden-Bars je Testmarkt | DMS 03 | CI/Testartefakt | Abweichungsbericht = 0 Signale |
| STR-007 Signal-Audit | DMS 02/09 | Signal Store/UI | Persistenz-/Drill-down-Test |
| STR-008 getrennte Strategieversionen | DMS 03; DEC-034/036/037 | Strategy/Config/Backtest/Paper/UI | Pine-Golden-Test + explizite atomare Umschaltung + Fail-closed-Konflikttest |
| MKT-001 genau zehn Paare | Nutzerauftrag | Config/Dashboard | Schema- und UI-Test |
| MKT-002 Coinliste | DMS 04; DEC-005 | Config/Data | Symbolmetadatenprüfung |
| MKT-003 keine automatische Coinrotation | DMS 04/22; DEC-005 | Config/Data/Release | Delisting pausiert statt Ersatz zu wählen |
| CAP-001 neue Paperkonten 250 USDT / 10 USDT Reserve | DEC-044 | Paper-/Live-Ledger, UI | Startsaldo-/Cash-/Bestandsschutztest |
| CAP-002 drei Slots à 80 USDT | Nutzerauftrag | Portfolio/Execution/UI | Slotlimit- und Notionaltest |
| CAP-003 UI-änderbare Slotgröße | Nutzerauftrag | Settings/Config/Audit | Validierungs-/Vorwärtswirkungstest |
| CAP-004 250→500 als Wunsch, nicht Garantie | Nutzerklärung | Backtestreport | Zielerreichung und -verfehlung je Coin sichtbar |
| CAP-005 Slotpriorisierung | DMS 03/04; DEC-029 | Strategy/Portfolio | simultane Signale/volle Slots |
| CAP-006 Nettogewinn vor Tradezahl | Nutzerwunsch + Kostenrealität | Optimierung/Report | Gebühren-/Tradezahlvergleich |
| CAP-007 bestbelegte Verbesserung übernehmen | DMS 06; DEC-037/038 | Backtest/Config/Paper/Audit | V1/V2-Risikospiegel + expliziter Migrationstest |
| CAP-008 Mehrfachslots nur nach Nachweis | DMS 03/04/06; DEC-039 | Allocation/Backtest/Paper | Allokations-Unit-Test + negativer V3-Risikospiegel |
| RSK-003 Tagesverlust/Drawdown | DMS 04; DEC-015 | Risk/UI | UTC-Tagesgrenze und High-Water-Mark-Test |
| RSK-004 kein Auto-Compounding | DMS 04; DEC-030 | Backtest/Portfolio/Config/UI | Gewinn verändert weder 250- noch 80-USDT-Zielnotional |
| BKT-008 10×250 USDT | Nutzerauftrag | Backtest Batch | zehn isolierte Ledger-Fixtures |
| BKT-009 Einzeltest 250 USDT | Nutzerauftrag | Backtest UI/Engine | ETH-only-Test ohne andere Coins |
| BKT-010 250-USDT-Spiegellauf | DMS 04/06 | Backtest Portfolio | Parität zu Paper-Slotmodell; historische 240-USDT-Runs unverändert |
| BKT-011 Baseline-/Stresskosten | DMS 06; DEC-010 | Backtest/Report | 15/40-bps-je-Seite-Fixtures |
| BKT-012 versionierte Strategieverbesserung | DMS 06; DEC-035 | Backtest/Report | Suchraum-, Mehrfenster-, Stress- und Nachbarnachweis |
| RSK-001 kein Leverage/Margin/Futures | DMS 04/11 | Config/Execution | Startblockade/Permissionscheck |
| RSK-002 Börsenfilter | DMS 04/07 | Risk/Execution | Tick/Step/Min-Notional-Tests |
| DAT-001 OHLCV persistent | Nutzerauftrag/DMS 05 | DB/Data API | Schema-/Roundtrip-Test |
| DAT-002 Startup-Vollprüfung | Nutzerauftrag | Startup/UI Health | Lücken-/Duplikat-Fixtures |
| DAT-003 inkrementelles Nachladen | Nutzerauftrag | Data Adapter | Paging-/Retry-Test |
| DAT-004 00:05-UTC-Audit | DMS 05; DEC-012 | Scheduler/UI | Scheduler-/DST-Test |
| DAT-005 Stream + REST-Fallback | Live-UI-Ziel | Data Adapter | Disconnect-/Recovery-Test einschließlich Löschen nur des stream-eigenen Fehlers |
| DAT-006 offene Kerze vorläufig | DMS 05 | Engine/UI | kein Signal auf provisional |
| DAT-007 lokale 3-Jahres-Historie | Nutzerauftrag | Chart API/UI | Range-/Datenquellentest |
| BKT-001 drei Jahre | Nutzerauftrag | Backtest/Report | Fenstergrenzen-Test |
| BKT-002 Next-bar-Fill | DMS 06 | Backtest Engine | Look-ahead-Negativtest |
| BKT-003 Kosten/Rundung | DMS 06 | Backtest/Execution | handgerechnete Fixtures |
| BKT-004 keine Bias-/synthetischen Preise | DMS 06 | Data/Backtest | Qualitäts- und Code-Review |
| BKT-005 vollständige Metriken | DMS 06 | Report/UI | Snapshot-/Formeltests |
| BKT-006 Run-Manifest | DMS 13 | Artifact Store/UI | Reproduktionslauf |
| BKT-007 Signalparität getrennt von PnL | DMS 03/06 | Test/Report | Golden-Test ohne Kapital-/Kostenabhängigkeit |
| EXE-001 getrennte Zustände | DMS 07/09 | Domain/DB/UI | State-machine-Test |
| EXE-002 Idempotency | DMS 07 | Execution | Doppel-Submit-Failure-Test |
| EXE-003 Startup-Reconciliation | DMS 07/10 | Execution/Health | Restart zwischen Submit/Antwort |
| EXE-004 Teilfill/Fehlerzustände | DMS 07 | Execution/Ledger | Adapter-Szenarien |
| EXE-005 Not-Aus | DMS 07/08 | UI/Risk | E2E und Berechtigungstest |
| EXE-006 Market-/Timeoutschutz | DMS 07; DEC-009/014/016 | Execution/Risk/UI | 25-bps-, 10-s-UNKNOWN- und 30-s-Teilfill-Test |
| UI-001 zehn Marktkarten | Nutzerauftrag/DMS 08 | Dashboard | UI-Abnahme |
| UI-002 fünf Chartzeiträume | Nutzerauftrag | Chart UI/API | Grenz-/Zeitzonentest |
| UI-003 Indikatoroverlays | Indikatorbeschreibung | Chart UI | Golden-Screenshot/Datenvergleich |
| UI-004 vorläufige Kerze sichtbar | DMS 08 | Chart UI | Visual-/Semantiktest |
| UI-005 Einheiten/Zeitzone | DMS 08 | gesamte UI | UI-Inventur |
| UI-006 Modusunterscheidung | DMS 01/08 | Header/Settings | E2E Moduswechsel |
| UI-007 Kosten am Backtest | DMS 06/08 | Report UI | Report-Abnahme |
| UI-008 feste Chartauflösungen | DMS 08; DEC-025/026 | Chart UI/API | Zeitraum-/Aggregationstest |
| OPS-001 Health | DMS 10 | Health/API/UI | Komponentenausfalltests |
| OPS-002 strukturierte Logs | DMS 10/11 | Observability | Schema-/Secret-Scan |
| OPS-003 Backup/Restore | DMS 10 | Operations | isolierter Restore-Test |
| OPS-004 Paper-Soak-Gate | DMS 10/12; DEC-018 | Operations/Release | 30 Tage, 720 Bars, 20 Trades; Maximalverlängerung 90 Tage |
| OPS-005 kein manueller Handel | DMS 11; DEC-021 | Account/Reconciliation | Fremdorder sperrt Live-Entries |
| OPS-006 lokale Pflichtalarme | DMS 10; DEC-019 | Observability/UI | persistenter P1/P2-UI-/Logtest |
| OPS-007 Backup-Retention | DMS 10; DEC-020 | Operations/Storage | 7/4/12-Retention und vierteljährlicher Restore |
| OPS-008 localhost/Windows-Service | DMS 10/11; DEC-022/023 | API/Service | Bind-/Autostart-/Restart-Test |
| SEC-001 keine Secrets | DMS 11 | alle Komponenten | Secret-Scan/Logtest |
| SEC-002 eingeschränkter Key | DMS 11 | Exchange Setup | Berechtigungsnachweis |
| SEC-003 Live-Gates | DMS 12 | Config/UI/Deploy | negativer Freischalttest |
| QLT-001 Traceability | DMS 12/15 | DMS/Testmanagement | Review ohne kritische Lücke |
| COL-001 GitHub-Repository | Nutzerauftrag/DMS 21 | Git/CI/DMS | Remote-/Secret-/Review-Check |
| COL-002 öffentliche DMS/Eigentümer-Pine, kein fremder Source | DMS 21; DEC-031/034 | Git/DMS/Release | Sichtbarkeits-, Herkunfts- und Secret-Check |

## Pflege

Neue kritische Anforderungen erhalten mindestens einen positiven und einen negativen Test. Ein `OFFEN` in der Fachquelle darf nicht durch einen grünen Implementierungstest kaschiert werden. Die Matrix enthält für DMS V1.3 keine kritische Fachquelle mit ausstehender Entscheidung; noch fehlende Betriebs- und Live-Nachweise entstehen erst in den dafür vorgesehenen Phasen.
