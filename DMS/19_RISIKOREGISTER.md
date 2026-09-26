# 19 – Risikoregister

Status: CURRENT · 26.09.2026

| Risiko | Wirkung | Gegenmaßnahme |
|---|---|---|
| Overfitting | hohe Historienwerte, schwache Zukunft | Training-only Ranking, Validation, full/stress, bounded search |
| Slot-Timing | isoliert guter Coin schadet Portfolio | marginaler Test im kanonischen Maximalbudget-Portfolio + Kombination-Gate |
| USDC-Listinghistorie | unvollständige 3 Jahre | reale Listinggrenze, Proxy klar kennzeichnen |
| Config-/Digest-Drift | Startup-/E2E-Fehler | Config nur key=v6, Profile ausschließlich versions.py |
| stale Paper-State | falscher Runtimeeindruck | A05-Freshness-Gate, persistente Checkpoints |
| Strategie-Cutover | Historien-/Positionsbruch | explizite Aktivierung, kein Silent Reset |
| UI-Staleness | Nutzer sieht alte Modi/Daten | aktuelle V6-only UI, A04/E2E |
| Workflow-Verzögerung | 24/7 nicht exakt taktgenau | restartfeste Bars/State, Watchdog |
| Live-Risiko | Echtgeldverlust | Live/Testnet aktuell gesperrt |
| Ergebnisinterpretation | Backtest wird als Garantie gelesen | klare Simulation-/Proxy-Kennzeichnung |
