# 09 – Systemarchitektur und Datenmodell

Status: CURRENT · 19.09.2026

Schichten:
- data: Binance Public, CandleStore, Qualität/Sync;
- domain: Modelle, V6-Profile, TradePolicy;
- backtest: Single, isolierter Batch, Shared Portfolio;
- paper: Account, Settings, Positionen, Events, Checkpoints, Strategie-Session;
- runtime: Supervisor, Recovery, Stream/REST, Scheduler;
- ui: lokale API + statisches TypeScript-Bundle;
- scripts: Optimierung und Cloud-Swarm.

SQLite ist Laufzeitquelle für Candles und Paperzustand. Strategieprofile liegen nicht in SQLite/Config, sondern kanonisch in versions.py. Paper speichert die aktive Strategie-Session/Digest, damit Änderungen fail-closed erkannt werden.
