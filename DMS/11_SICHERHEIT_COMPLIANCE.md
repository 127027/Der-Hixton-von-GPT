# 11 – Sicherheit und Compliance

Status: CURRENT · 19.09.2026

Aktuelle Releasegrenze: Paper/backtest only.

- Cloud-Swarm und Optimizer erhalten keine Binance-Private-Credentials.
- A01–A11 benötigen keinen OpenAI API Key.
- Real-/Testnet-Orders sind verboten.
- Keine Secrets in Git, Logs, Reports oder Frontend.
- Vorbestehende freie Spot-Bestände bleiben Fremdeigentum relativ zum Hixton-Ledger: Baseline erfassen, niemals adoptieren, SELL ausschließlich aus persistentem Hixton-Eigentum; unerwartete Kontobewegungen sperren neue Orders.
- Lokale API akzeptiert mutierende UI-Aufrufe nur aus dem lokalen Bedienkontext.
- Persistente Paperdaten werden nicht still gelöscht oder zurückgesetzt.
- Strategieänderungen erfordern explizite Versionierung/Aktivierung.
- Automatisches Merge und automatische Live-/Paper-Strategieaktivierung sind nicht erlaubt.

Für jede lokale Echtgeldfreigabe gilt der implementierte gestufte Sicherheits-/Order-/Reconciliation-Abnahmevertrag: zuerst die read-only Kontovorprüfung, danach ausschließlich der ausdrücklich freigegebene 1×50-USDC-Roundtrip; normaler Maximalbudget-Livebetrieb bleibt bis zu einer separaten Freigabe gesperrt.
