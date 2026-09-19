# 15 – Traceability Matrix

Status: CURRENT · 19.09.2026

| Anforderung | Umsetzung | Kernprüfung |
|---|---|---|
| eine aktuelle V6 | domain/versions.py, config.py | test_current_v6_product_contract.py |
| 10 USDC-Märkte | constants.py, Binance Public | A07, Datenqualitätstests |
| 3×80 ranked_repeat | backtest/portfolio.py, allocation | Portfolio-/Slot-Tests |
| 10×250 Diagnose | backtest engine | Coin-Optimization / Backtesttests |
| kein permanenter DD-Halt | Risk-/Portfolio-Code | Risk-/DMS-Vertragstests |
| 5% UTC-Day-Pause | Risk-Code | Risk-Tests |
| Paper-Persistenz | paper/storage.py, engine.py | Paper-/Recoverytests, A03/A05 |
| Strategie-Cutover fail-closed | paper storage/maintenance | Paper-Maintenance/Runtimetests |
| nur V6 in UI/API/CLI | ui/, ui/api.py, cli.py | Current-V6-Contract, UI-E2E |
| Top-K Validation | coin_optimization_cycle.py | test_backtest_coin_optimization.py |
| unabhängige Releasegates | cloud swarm | A09/A11 |
| Paper-only Sicherheit | Workflows/Runtime | A01/A05/A11 |
