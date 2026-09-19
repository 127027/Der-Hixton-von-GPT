# 23 – Ordnerstruktur und Einstiegspunkt

Status: CURRENT · 19.09.2026

Wesentliche Struktur:
- Startbot.bat — menschlicher Windows-Starter;
- src/main.py — technischer CLI-Einstieg;
- src/hixton/domain — V6/Modelle/Policies;
- src/hixton/data — Binance Public, Store, Sync, Qualität;
- src/hixton/backtest — aktuelle Engines;
- src/hixton/paper — persistentes Paper;
- src/hixton/runtime — Supervisor/Recovery;
- src/hixton/ui — Python-API und gebautes UI;
- ui — TypeScript-Quelloberfläche;
- config/examples/config.example.json — minimale Runtimeconfig mit strategy.key=v6;
- backtests/README.md — Lernjournal;
- backtests/v6 — einziger aktueller Backtestproduktordner;
- agent_memory/swarm — aktuelles A01–A11-System;
- DMS — aktueller Produktvertrag;
- tests — Regression/Contracts;
- .github/workflows — CI, Paper, Swarm, Optimierung.

Git ist das Archiv für entfernte Legacyartefakte. Es werden keine alt/backup-Kopien im Produktbaum gehalten.
