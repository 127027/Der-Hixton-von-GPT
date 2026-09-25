# 13 – Konfiguration und Schemata

Status: CURRENT · 25.09.2026

Die Runtime-Konfiguration enthält für die Strategie nur:

    "strategy": { "key": "v6" }

V6-Version, slot_allocation und Coin-Profile kommen aus der **kanonischen StrategyDefinition** in `src/hixton/domain/versions.py`; sie werden nicht als zweiter Profil-/Digest-Snapshot in Config gepflegt.

Paper-Konfiguration:

- `starting_cash_usdc: 250.00`
- `max_capital_usdc: 250.00`
- `poll_seconds`
- `daily_audit_utc`

`slot_count`, `target_notional_usdc`, Reserve und Allocation-Policy werden ausschließlich aus `capital_plan(max_capital_usdc)` abgeleitet. Sie dürfen nicht als zweite editierbare Konfiguration geführt werden.

Aktueller Allocator: `CAPITAL-V1-2X50PCT` / ranked_repeat / 2 Tranchen zu je 50 %. Validierter Maximalbudgetbereich: 100 bis 1.000 USDC.

Persistente Altspalten in SQLite dürfen für Migration/Audit vorhanden bleiben; geladen wird die kanonische Maximalbudget-Einstellung.
