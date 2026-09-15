# 19 – Risikoregister

Bewertung: Eintritt `N/M/H`, Auswirkung `N/M/H`. Das Register beschreibt Risiken und Kontrollen, keine Gewinnprognose.

| ID | Risiko | Eintritt | Auswirkung | Prävention/Erkennung | Reaktion | Owner |
|---|---|---:|---:|---|---|---|
| R-001 | V1, Eigentümer-Pine-V2 und ein nicht separat nachgewiesenes Herstellerprodukt werden fälschlich gleichgesetzt | M | H | getrennte Versionsnamen, Pine-Hash, Golden-Daten, keine Herkunftsbehauptung | Aussage korrigieren; Version/Runs nicht rückwirkend umdeuten | Strategie |
| R-002 | Repainting/Look-ahead | M | H | Bar-Close-Regel, Replay=Batch, Code-Review | Ergebnisse ungültig, Live sperren | Strategie/QA |
| R-003 | Datenlücke erzeugt falsches Signal | M | H | Raster-/Freshness-Audit, Symbolpause | nachladen, neu validieren, keine Nachholorder | Daten |
| R-004 | Provider korrigiert Historie | M | M | Datenrevision/Hash | Runs stale markieren, neu rechnen | Daten/Backtest |
| R-005 | Gebühren/Slippage unterschätzt | H | H | Baseline/Stress, Paper-Messung | Bericht korrigieren, Freigabe neu bewerten | Backtest |
| R-006 | Overfitting auf 3-Jahres-Ziel | H | H | Parameterfreeze, Holdout, Suchlog | Strategieversion verwerfen/neu validieren | Strategie |
| R-007 | Doppelorder nach Timeout/Restart | M | H | Idempotency, Client-ID, Reconciliation | Live halt, Börsenstatus klären | Execution |
| R-008 | Teilfill lokal falsch verbucht | M | H | Fill-Ledger, Integrationsfixtures | Reconciliation/Gegenbuchung | Execution |
| R-009 | Fremdorder/manueller Kontoeingriff | M | H | eigener Subaccount, Saldoabgleich | Live halt, Incident | Betreiber |
| R-010 | API-Key kompromittiert | N/M | H | Least Privilege, IP-Allowlist, Secret-Store | Key sperren/rotieren, Audit | Security |
| R-011 | API-Key besitzt Auszahlungsrecht | N | H | Setupcheck/Permissionsnachweis | Live nicht freigeben | Betreiber/Security |
| R-012 | Börse/Pair delistet oder pausiert | M | H | Metadaten-/Statusaudit | Coin pausieren, kein automatischer Ersatz | Daten/Betreiber |
| R-013 | Rate-Limit/Netzwerk trennt Feed | H | M/H | Backoff, Watchdog, REST-Fallback | Entries pausieren, Lücke schließen | Plattform |
| R-014 | falsche Uhr/Zeitzone | N/M | H | UTC intern, NTP/Uhrtoleranz | Halt bis Zeit korrekt | Plattform |
| R-015 | DB-Korruption/Speicher voll | N/M | H | Integritycheck, Speicherwarnung, Backup | Halt, Restore | Betrieb |
| R-016 | Backup unbrauchbar | M | H | Checksummen und Restore-Drill | letzte geprüfte Version nutzen, Incident | Betrieb |
| R-017 | UI zeigt stale Wert als live | M | H | Zeitstempel/Freshness/Provisional-Badge | Warnung, Entries pausieren | UI/Daten |
| R-018 | Modusverwechslung Paper/Live | N/M | H | permanentes Banner, Bestätigung, getrennte Keys | Not-Aus, Incident | UI/Betreiber |
| R-019 | Zielrendite als Garantie verstanden | M | H | klare Reportwarnung, Brutto/Netto trennen | Kommunikation korrigieren | Produkt |
| R-020 | 80-USDT-Paper-/Live-Order oder 250-USDT-Simulationsorder verletzt Min-Notional/Rundung | N/M | M | Binance-Filter vorab | Intent blockieren und sichtbar melden | Execution |
| R-021 | geringe Tradezahl macht Kennzahlen instabil | M | M | Tradezahl/Konfidenzwarnung | keine Überinterpretation | Backtest |
| R-022 | Coin-Auswahl erzeugt Survivorship-Bias | M | H | Universum vor Test einfrieren | Bericht neu aufsetzen | Strategie |
| R-023 | Dependency-/Update-Regression | M | H | Lockfile, Tests, Paper-Stufe | Rollback auf geprüften Release | Engineering |
| R-024 | lokale Maschine schläft/startet nicht | M/H | H | Service, Power-/Autostartcheck, Alarm | Recovery/Gap-Fill, keine Nachholorder | Betrieb |
| R-025 | offene Position bleibt bei Bot-Ausfall unüberwacht | M | H | externer Alarm, Börsen-Schutzentscheidung, Health | Betreiberaktion nach Runbook | Betreiber |
| R-026 | rohe Tradezahl wird über Nettoprofit gestellt und erzeugt Gebührenverluste | M/H | H | Nettoprofit nach Kosten als Primärziel | Variante verwerfen, Priorität korrigieren | Produkt/Backtest |
| R-027 | mehr gleichzeitige Kaufsignale als drei freie Slots | H | M/H | deterministische Priorisierung und verpasste-Signale-Report | keine willkürliche Auswahl/Nachholorder | Strategie/Portfolio |
| R-028 | Backtestkapital 10×250 wird mit Paperkapital 250 (historisch 240) verwechselt | M | H | getrennte Run-Modi, Ledgers und UI-Badges | Run invalidieren/korrigieren | QA/UI |
| R-029 | Mehrere Slots auf demselben Signal erhöhen Konzentration, aber nicht die Zahl unabhängiger Trades | H | H | eigene Strategieversion, 3×80-Risikospiegel, keine automatische Aktivierung | Challenger verwerfen; aktive Ein-Slot-Regel beibehalten | Strategie/Risiko |
| R-030 | Paperledger und konfigurierte Strategieversion werden nach Wechsel vermischt | N | H | persistente Sessionversion, atomare Migration, Fail-closed-Startprüfung, versionierte Events | Bot gestoppt lassen, Backup einspielen oder explizite Migration wiederholen | Paper/Operations |

## Reviewtakt

- vor jeder Gate-Freigabe;
- nach Incident oder wesentlicher Daten-/Börsenänderung;
- mindestens monatlich im Livebetrieb;
- Owner und die in DMS 04/05/07/10 festgelegten Schwellen werden vor jedem Gate auf Aktualität geprüft.

Risiken mit Auswirkung `H` dürfen nicht ohne dokumentierte Kontrolle und Owner in Live gehen.
