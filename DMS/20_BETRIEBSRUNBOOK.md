# 20 – Betriebsrunbook

Status: CURRENT · 19.09.2026

## Normalstart
Windows: Startbot.bat. Technisch: py -3 src/main.py start. Die UI ist lokal unter 127.0.0.1:8765.

## Diagnose
    py -3 src/main.py status
    py -3 src/main.py data audit --symbol ALL
    py -3 src/main.py data sync --symbol ALL

## Aktuelle Backtests
    py -3 src/main.py backtest all --strategy v6
    py -3 src/main.py backtest portfolio --strategy v6
    py -3 src/main.py backtest single --strategy v6 --symbol BTCUSDC

Der 10×250-USDC-Batch ist Diagnose; das 3×80-USDC-Portfolio ist das Haupt-Abnahmemodell.

## Strategie-Digest geändert
Nicht Datenbankdateien manuell ändern und nicht neu starten/resetten, um die Sperre zu umgehen.
1. neue V6 vollständig validieren;
2. laufenden Paperprozess geordnet beenden;
3. Backup/Integrität prüfen;
4. explizit paper-activate --strategy v6 --confirmation AKTIVIEREN;
5. neue Strategie-Session, Equity, Positionseffekte und Audit prüfen;
6. Paper neu starten;
7. A05/A03 sowie E2E/A01–A11 erneut ausführen.

## Runtimefehler
Bei stale Daten, Gaps, Checkpoint-/Ledgerfehlern oder Mismatch: neue Entries fail-closed, Zustand sichern, Ursache beheben, Recovery/Reconciliation ausführen, danach invalide Evidenz neu rechnen.

## Sicherheit
Kein Real-/Testnet-Handel im aktuellen Release. Keine Binance-Private-Credentials in Cloudjobs. Kein Kontoreset für einen normalen Update-/Backtestvorgang.
