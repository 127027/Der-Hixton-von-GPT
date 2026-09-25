# 20 – Betriebsrunbook

Status: CURRENT · 25.09.2026

## Normalstart

Windows: `Startbot.bat`. UI: http://127.0.0.1:8765/

Diagnose:

    py -3 src/main.py status
    py -3 src/main.py data audit --symbol ALL
    py -3 src/main.py data sync --symbol ALL
    py -3 src/main.py backtest portfolio --strategy v6
    py -3 src/main.py backtest all --strategy v6

Portfolio-Backtest verwendet das gespeicherte **Maximalbudget** und denselben zentralen Allocator wie Paper/Live. 10×250 isoliert bleibt Forschung.

## Einstellungen

In der UI nur **Maximaler USDC-Einsatz** ändern. Standard: 250 USDC. Beim aktuellen Allocator bedeutet das 2 × 125 USDC ranked_repeat. Slotzahl/Tranche niemals separat als zweite Wahrheit pflegen.

## Gestufte lokale Echtgeld-Inbetriebnahme

1. Binance API-Key mit Lesen + Spot erstellen; IP-Beschränkung EIN; Withdrawal/Transfer/Margin/Futures/Optionen AUS.
2. In Hixton lokalen Schlüsselbereich entsperren, Key/Secret speichern und **Binance-Verbindung prüfen**.
3. Maximalbudget bleibt standardmäßig 250 USDC.
4. **1 × 50 USDC · Test freigeben**. Keine sofortige Order: Hixton wartet auf ein neues gültiges Signal, führt den einmaligen Entry und regulären Exit aus und reconciled Konto/Fills.
5. Erst nach vollständig abgeschlossenem Roundtrip und allen weiteren Gates kann **Live an** den gespeicherten Maximalbudget-Plan aktivieren.
6. Eine spätere Budgetänderung stoppt neue Echtgeld-Einstiege; erneute Freigabe bindet den neuen Plan nur bei sauberem Ledger.
7. **Live aus** stoppt neue Einstiege; offene eigene Positionen dürfen regulär aussteigen.

Cloud/CI/A01–A11 besitzen keine privaten Binance-Credentials und senden keine Orders.
