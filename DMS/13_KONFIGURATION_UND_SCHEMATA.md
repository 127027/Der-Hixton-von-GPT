# 13 – Konfiguration und Schemata

Status: CURRENT · 19.09.2026

## Aktueller Konfigurationsvertrag 19.09.2026

config/examples/config.example.json enthält bei strategy ausschließlich:

    "strategy": { "key": "v6" }

V6-Version, slot_allocation und Coin-Profile kommen aus der kanonischen StrategyDefinition in src/hixton/domain/versions.py. Damit kann ein Profilupdate keinen zweiten, veralteten Config-Snapshot erzeugen.

Paper-Baseline:
- starting_cash_usdc: 250.00
- slot_count: 3
- target_notional_usdc: 80.00
- poll_seconds: 30
- daily_audit_utc: 00:05

slot_allocation ist ranked_repeat und wird von der StrategyDefinition geliefert.

Ein permanenter globaler Drawdown-Halt ist **kein** aktiver Konfigurationsparameter mehr.

Unbekannte Config-Felder werden fail-closed abgelehnt.
