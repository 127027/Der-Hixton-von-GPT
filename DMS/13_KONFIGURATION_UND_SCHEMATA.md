# 13 – Konfiguration und Schemata

Aktueller Vorrang: **DMS 1.12.0 / DEC-053 / Anwendung 0.4.7**. Der integrierte Code verwendet USDC (250 Modellstart, Standard 3×80; später genau ein 50-USDC-Test). Alte datierte USDT-Anforderungen/Ergebnisse sind Historie, keine umgerechneten USDC-Nachweise. Runtime- und Laptop-Deployment sind getrennt zu prüfen. Kein Echtgeldstart: technischer Restarbeitsplan in [DMS 20](20_BETRIEBSRUNBOOK.md), tatsächlicher Testnachweis in [DMS 12](12_TESTS_ABNAHMEKRITERIEN.md). Bestehende Live-Sicherheitsgates bleiben wirksam.

## Aktueller Einstellungsvertrag 0.4.5 / DEC-051

Persistente Einstellungen weiter in einer bestehenden paper_settings-Zeile; kein zweiter Live-Speicher. Gültig 1–10 Slots und positives endliches Zielnotional ohne feste 240-USDT-Grenze. `/api/status.trading_limits` liefert nur `max_slots: 10`; verfügbares Kontocash ist davon getrennt. UI verwendet 1-USDT-Schritte; interne Dezimalwerte bleiben kompatibel. 4×45, 5×50 und 10×100 sind gültig, erzeugen aber kein Cash und keine sofortigen Trades. Konfigurationsdatei-Startbaseline 3×80 wird nicht umgeschrieben. Gemeinsamer Portfoliobacktest muss die gespeicherte Aufteilung im Manifest nennen, frühere Runs bleiben unverändert.

Der Klick auf Übernehmen sendet den bestehenden technischen Bestätigungsmarker automatisch; es gibt kein Bestätigungswort-Eingabefeld. Der ausdrücklich beschriftete Einmaltestbutton sendet fest TEST 50 USDT und 50.00 ohne Checkbox; globale Einmalbegrenzung bleibt serverseitig. Legacy emergency_stop bleibt erhalten, aber ohne neue sichtbare Umschaltmöglichkeit; Entfernen der UI ist keine Freigabe eines bestehenden Sicherheitsstopps. Echtgeld-Gates bleiben unverändert. Ältere feste Budget-/UI-Grenzen darunter sind historische Stände, durch DEC-051 ersetzt.

DEC-049 / Anwendung 0.4.3: Gemeinsamer Speicherweg `POST /api/trading/settings`; der alte Paper-Pfad bleibt kompatibler Alias auf denselben Handler und dieselbe `paper_settings`-Zeile. Keine zweite Datenbank-Konfigurationskopie oder Ledger-Migration. `/api/live/status.trading_settings` liest exakt Slots, Notional und Einstiegspause dieser Zeile. `/api/status.trading_limits` liefert die zentral validierten Freigabegrenzen (weiterhin 3 Slots / 240 USDT). Größere Entwürfe werden mit HTTP 400 abgewiesen, nicht still korrigiert. Beim Speichern einer Einstiegspause wird zusätzlich ein angeschlossener Testcontroller für neue Entries gestoppt; Entpausieren startet ihn niemals neu. Normaler Echtgeldbetrieb muss vor späterer Freigabe dieselben gespeicherten Parameter und Pause durchsetzen, die jeweilige Kontofinanzierung aber separat prüfen. Der produktive Dispatcher fehlt weiterhin.

DEC-047 (geplant): Der Echtgeld-Einmaltest besitzt eine eigene persistente Einmalbudgetfreigabe von 50 USDT Kaufnotional, unabhängig von `paper_settings`. Feste aktive Strategie-/Coin-Profile und einmalig verbrauchte Einstiegsberechtigung gehören zur Testidentität; Gebühren separat, keine Wiederauffüllung durch Gewinn/Neustart und keine Übergabe an den normalen 3×80-Betrieb. Eine bloße 50-USDT-Prüfung je Order ist keine globale Einmalbegrenzung. Diese Konfiguration wird in 0.4.1 noch nicht angeboten oder ausgeführt; keine Live-Flags in Dateien setzen. Details DMS 20.

DEC-046 / Anwendung 0.4.0: Der JSON-Baselinewert 3×80 bleibt unverändert. Aktive Paper-Settings kommen restartfest aus `paper_settings`; UI darf 1–3 Slots mit positivem endlichem Zielnotional, zusammen höchstens 240 USDT speichern. Beispiel 1×50 ändert weder Startcash noch Positionen oder Soak. Der gemeinsame UI-Portfoliobacktest liest die aktuellen gespeicherten Slotwerte und schreibt sie ins Manifest; historische 3×80-Ergebnisse sind kein Ergebnis einer neuen 1×50-Konfiguration.

Keine API-Keys, Secrets, lokalen Passwörter oder Live-Enable-Flags in JSON/YAML/ENV. Live-Vorbereitung verwendet Windows Credential Manager sowie ein getrenntes `data/live-preparation.sqlite3` nur für Vorbereitungs-Audit, nicht als zweites Handelskonto. Konto-Vorchecks bleiben maximal 60 Sekunden im Speicher und verfallen bei Schlüsseländerung oder Restart. Geplanter erster Echtgeldumfang ist 1×50 mit mindestens 60 freien USDT; dies ist noch keine wirksame Live-Konfiguration. Erhöhung auf 3×80/750 oder darüber benötigt neue ausdrücklich bestätigte Budgetgrenzen samt Spiegeltest; wird nicht vorweggenommen.

DEC-045: aktive JSON-Config `strategy.key=v6`, vollständige unveränderte Profilmap aus `candidate.json`, Runziel `backtests/v6/runs`, Paperstart 250 USDT / 3×80. Die Paperfreigabe gilt dem Experiment, nicht einer Live-Ausführung.

Aktuelle Runtime-Quelle ist ausschließlich `config/examples/config.example.json`, geprüft gegen `StrategyDefinition.config_payload()`. Neue Modellkonten starten gemäß DEC-044 mit `paper.starting_cash_usdt: "250.00"`, drei Slots à 80 USDT. Alte V2-Configs mit 240 USDT bleiben lesbar; vorhandene Konten werden bei normalen Starts nie umgebucht. Ein separater Offline-Neuanfang nach DEC-045 archiviert stattdessen das alte Konto. Das folgende umfangreiche YAML enthält auch zukünftige Live-Felder und ist kein Ersatz für diese streng geprüfte JSON-Datei.

Für V6 enthält `strategy.profiles` exakt alle zehn Coins in DMS-Reihenfolge mit `parameters` und `trade_policy`, keine irreführenden gemeinsamen Top-Level-Indikatorparameter. Snapshot: `backtests/v6/candidate.json`; gemeinsame Formel, 1h, 400 Warm-up-Bars, long-only, `one_per_symbol`, kein Compounding. Profiländerungen erzeugen eine neue hashgebundene Version. Reports enthalten die vollständige Profilmap. Eine Config darf kein Research-Profil stillschweigend als aktive Strategie ausgeben.

## Grundregeln

- Konfiguration ist schema-validiert und versioniert.
- Unbekannte Felder sind Fehler, keine still ignorierten Tippschreibfehler.
- Einheiten stehen im Feldnamen oder Schema.
- Secrets werden nur referenziert.
- Aktivierte Konfiguration hat Hash, Freigabezeit und Owner.
- Strategieänderung und Betriebsänderung sind getrennte Versionen.

## Historisches erweitertes Sollschema V2 (keine direkt ladbare Runtime-Config)

```yaml
schema_version: 1
environment: paper
timezone_ui: Europe/Berlin

exchange:
  provider: binance
  market_type: spot
  quote_asset: USDT
  api_key_secret_ref: hixton/paper/api_key
  api_secret_secret_ref: hixton/paper/api_secret

strategy:
  id: hixton_vidya_atr
  key: v2
  version: HIXTON-V2-RESEARCH-CANDIDATE-1
  normative_spec: DMS/03_STRATEGIE_HIXTON.md
  normative_spec_git_commit: REQUIRED_AT_BUILD
  owner_pine_reference_sha256: 8af8e9a1e6c73dc66307271b7fd1141eaae02bc1fe88e8ba97b96e7a861263dd
  semantics: pine_v6
  timeframe: 1h
  source: close
  vidya_length: 6
  momentum_length: 20
  post_smoothing_type: sma
  post_smoothing_length: 8
  atr_type: wilder_rma
  atr_length: 60
  band_multiplier: 3.8
  warmup_bars: 400
  initial_trend: down_without_order
  evaluate_on_closed_bar_only: true
  position_mode: long_only
  pyramiding: 0
  slot_allocation: one_per_symbol

markets:
  - BTC/USDT
  - ETH/USDT
  - BNB/USDT
  - SOL/USDT
  - XRP/USDT
  - ADA/USDT
  - LINK/USDT
  - AVAX/USDT
  - DOT/USDT
  - DOGE/USDT

capital:
  paper_live_total_usdt: 240.00
  paper_live_slot_count: 3
  paper_live_target_notional_usdt: 80.00
  compounding: false
  slot_priority: normalized_breakout_desc_then_fixed_coin_order

backtest:
  primary_window_years: 3
  mode: all_ten_isolated  # alternativ single_symbol oder paper_live_mirror
  isolated_starting_usdt_per_symbol: 250.00
  isolated_target_notional_usdt: 250.00
  isolated_compounding: false
  single_symbol: null
  fill_model: next_bar_open
  baseline_fee_bps_per_side: 10
  baseline_spread_bps_per_side: 2
  baseline_slippage_bps_per_side: 3
  stress_fee_bps_per_side: 10
  stress_spread_bps_per_side: 10
  stress_slippage_bps_per_side: 20
  benchmark: buy_and_hold

data:
  store_closed_candles: true
  store_provisional_candle: true
  startup_gap_repair: true
  daily_audit_utc: "00:05"
  missing_bar_policy: halt_symbol
  stream_stale_seconds: 90
  final_bar_grace_seconds: 120

execution:
  live_enabled: false
  order_type: market
  max_price_deviation_bps: 25
  acknowledgement_timeout_seconds: 10
  partial_fill_resolution_seconds: 30
  unknown_order_policy: halt_and_reconcile

risk:
  leverage: 1
  allow_margin: false
  allow_futures: false
  allow_short: false
  max_open_positions: 3
  pause_new_entries_daily_loss_pct: 5
  daily_loss_reference_utc: "00:00"
  global_halt_drawdown_pct: 20
  drawdown_action: halt_without_auto_liquidation

operations:
  paper_soak_min_days: 30
  paper_soak_min_closed_bars_per_symbol: 720
  paper_soak_min_closed_trades: 20
  paper_soak_max_days_when_trade_count_low: 90
  manual_trading_same_account: false
  ui_bind: 127.0.0.1
  alert_primary: local_ui_and_structured_log
  windows_service_after_paper_gate: true
  operational_log_retention_days: 90
  backup_target_outside_git_required: true
  backup_retention_daily: 7
  backup_retention_weekly: 4
  backup_retention_monthly: 12

ui:
  chart_ranges: [today, 1w, 1m, 1y, 3y]
  default_range: 1m
  default_resolution_by_range:
    today: 1h
    1w: 1h
    1m: 1h
    1y: 4h
    3y: 1d
  strategy_signal_resolution: 1h
```

In `chart_ranges` und `default_range` steht `1m` für **einen Monat**. Es bezeichnet niemals einen 1-Minuten-Timeframe. Der native Daten- und Signaltimeframe bleibt `1h`; nur lange UI-Ansichten werden wie angegeben deterministisch aggregiert.

Runtimewerte wie Secret-Referenzen und konkrete Account-ID werden bei der Installation gesetzt. Die aktive V6-JSON-Konfiguration ist verbindlich; das obige V2-YAML ist historisch und und darf nicht durch Frameworkdefaults ersetzt werden. V1 bleibt als historische, reproduzierbare Konfiguration in ihrer Strategieversion erhalten. Telegram ist nicht erforderlich.

## Strategie-Snapshot

Jedes Signal und jeder Backtest referenziert mindestens:

- Strategie-ID/-Version;
- Git-Commit der normativen Spezifikation;
- Hash der vom Eigentümer bereitgestellten Pine-Referenz;
- Parameterhash;
- Timeframe und Quelle;
- Warm-up-Regel;
- Bar-Close-Regel;
- Positionsmodus/Pyramiding;
- Build-/Codeversion.

## Backtest-Run-Manifest

```yaml
run_id: UUID
created_at_utc: ISO-8601
status: valid|invalid|failed|stale
code_version: COMMIT_OR_BUILD_HASH
strategy_version: HIXTON-V2-RESEARCH-CANDIDATE-1
normative_spec_git_commit: VALUE
owner_pine_reference_sha256: 8af8e9a1e6c73dc66307271b7fd1141eaae02bc1fe88e8ba97b96e7a861263dd
config_sha256: VALUE
data_snapshot_sha256: VALUE
exchange: VALUE
symbols: [TEN_CONFIRMED_SYMBOLS]
timeframe: 1h
warmup_start_utc: VALUE
report_start_utc: VALUE
report_end_utc: VALUE
starting_usdt_per_symbol: 250.00
run_mode: all_ten_isolated|single_symbol|paper_live_mirror
paper_live_mirror_total_usdt: 250.00
paper_live_mirror_slot_count: 3
paper_live_mirror_target_notional_usdt: 80.00
slot_allocation: one_per_symbol
fee_model: baseline_10bps_per_side
spread_model: baseline_2bps_per_side
slippage_model: baseline_3bps_per_side
fill_model: next_bar_open
random_seed: null
runtime:
  os: VALUE
  language: VALUE
  dependency_lock_sha256: VALUE
artifacts:
  data_quality_report: PATH
  trades_csv: PATH
  metrics_json: PATH
  report_html_or_pdf: PATH
```

## Validierung

Start muss fehlschlagen bzw. Live deaktiviert bleiben bei:

- fehlender Git-Commit der normativen Strategiequelle;
- weniger/mehr als zehn Märkten im Standard-Batch oder nicht genau einem Markt im Einzelmodus;
- doppeltem Symbol;
- nicht positivem Kapital;
- unbekanntem Timeframe;
- Live ohne Paper-/Freigabestatus;
- Short/Futures/Margin entgegen Strategieprofil;
- fehlender Parameter-/Konfigurationshash;
- ungültiger Zeitzone;
- Geheimnis im Klartextfeld.

## Freigabestatus

Binance Spot, Coinliste, 10×250-USDT-Batch, 250-USDT-Einzeltest, 3×80-USDT-Paperbetrieb, aktive V6 mit zehn Profilen auf 1h, Long-only, kein Compounding, höchstens ein Slot je Coin, Slotpriorisierung, Kostenbaseline und 00:05-UTC-Audit sind fachlich beschlossen. Ein Strategiewechsel benötigt eine explizite Bestätigung und persistiert Strategieversion, Aktivierungszeit, Start-Equity und Audit. Live bleibt bis zu Tests, Secrets, Accountabgleich und Gate D deaktiviert.
