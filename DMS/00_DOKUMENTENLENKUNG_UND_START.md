# 00 – Dokumentenlenkung und Start

Status: CURRENT · 26.09.2026

Dieses DMS beschreibt ausschließlich den heutigen Produktvertrag. Historische Stände bleiben in Git und kompakt im CHANGELOG/Entscheidungslog.

## Vorrang
1. Code + Tests des aktuellen Commits.
2. agent_memory/swarm/taskboard.json und A01–A11-Rollen.
3. DMS 00–23.
4. README.md und backtests/README.md.
5. Git-Historie ausschließlich als Archiv.

## Aktueller Stand
Der Hixton verwendet eine aktuelle V6 für zehn Binance-USDC-Märkte. `src/hixton/domain/versions.py` ist die einzige Profilquelle. Config enthält nur `strategy.key = v6`. Hauptmodell ist eine einzige Kapitalvorgabe `max_capital_usdc`; `CAPITAL-V1-2X50PCT` leitet daraus zwei `ranked_repeat`-Tranchen zu je 50 % ab (Standard 250 USDC → 2×125). 10×250 bleibt Diagnose/Forschung. Es gibt keinen permanenten Portfolio-Drawdown-Halt. Der lokale Echtgeldpfad ist ausschließlich für den separaten kontrollierten 1×50-USDC-Ersttest vorbereitet; Cloud/Agenten senden keine Orders.

## Start
Windows-Nutzer starten über Startbot.bat. Technischer Einstieg ist src/main.py. Die UI läuft lokal auf Port 8765.

## Änderungen
Jede materielle Änderung erfordert aktualisierte Dokumentation, frische Tests und frische A01–A11-Evidenz. Alte PASS-Ergebnisse gelten nach einer relevanten Änderung nicht weiter.
