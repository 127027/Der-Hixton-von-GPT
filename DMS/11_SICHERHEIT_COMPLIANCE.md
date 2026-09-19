# 11 – Sicherheit und Compliance

Status: CURRENT · 19.09.2026

Aktuelle Releasegrenze: Paper/backtest only.

- Cloud-Swarm und Optimizer erhalten keine Binance-Private-Credentials.
- A01–A11 benötigen keinen OpenAI API Key.
- Real-/Testnet-Orders sind verboten.
- Keine Secrets in Git, Logs, Reports oder Frontend.
- Lokale API akzeptiert mutierende UI-Aufrufe nur aus dem lokalen Bedienkontext.
- Persistente Paperdaten werden nicht still gelöscht oder zurückgesetzt.
- Strategieänderungen erfordern explizite Versionierung/Aktivierung.
- Automatisches Merge und automatische Live-/Paper-Strategieaktivierung sind nicht erlaubt.

Vor einer zukünftigen Livefreigabe ist ein separater Sicherheits-/Order-/Reconciliation-Abnahmevertrag erforderlich.
