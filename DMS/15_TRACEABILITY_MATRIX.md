# 15 – Traceability Matrix

Status: CURRENT · 26.09.2026

| Anforderung | Umsetzung | Kernprüfung |
|---|---|---|
| eine aktuelle V6 | domain/versions.py, config.py | test_current_v6_product_contract.py |
| 10 USDC-Märkte | constants.py, Binance Public | A07, Datenqualitätstests |
| max_capital_usdc + CAPITAL-V1-2X50PCT ranked_repeat | domain/capital.py, backtest/portfolio.py, Paper/Live settings | Kapital-/Portfolio-/Parity-Tests |
| 10×250 Diagnose | backtest engine | Coin-Optimization / Backtesttests |
| kein permanenter DD-Halt | Risk-/Portfolio-Code | Risk-/DMS-Vertragstests |
| 5% UTC-Day-Pause | Risk-Code | Risk-Tests |
| Paper-Persistenz | paper/storage.py, engine.py | Paper-/Recoverytests, A03/A05 |
| Strategie-Cutover fail-closed | paper storage/maintenance | Paper-Maintenance/Runtimetests |
| nur V6 in UI/API/CLI | ui/, ui/api.py, cli.py | Current-V6-Contract, UI-E2E |
| Top-K Validation | coin_optimization_cycle.py | test_backtest_coin_optimization.py |
| unabhängige Releasegates | cloud swarm | A09/A11 |
| Cloud/Agenten ohne Orderrechte | Workflows/Runtime | A01/A05/A11 |
