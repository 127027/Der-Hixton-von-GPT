# 20 – Betriebsrunbook

Status: CURRENT · 21.09.2026

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

## Gestufte lokale Echtgeld-Inbetriebnahme
1. Bot lokal starten und unter **Einstellungen → Binance-Zugang & Sicherheit** entsperren.
2. API-Key/Secret lokal speichern. Erlaubt: Lesen + Spot; verboten: Withdrawal, Transfer, Margin, Futures und Optionen. IP-Beschränkung verwenden.
3. **Binance-Verbindung prüfen**. Ohne frische erfolgreiche Kontovorprüfung bleibt jeder Echtgeldstart gesperrt.
4. Für den ersten Test Einstellungen auf **1 Trade × 50 USDC** setzen und übernehmen.
5. **1 × 50 USDC · Test freigeben**. Dadurch wird keine sofortige Order gesendet; der Bot wartet auf ein neues gültiges V6-Signal. Nach Entry/Exit muss der Roundtrip vollständig reconciled sein.
6. Erst danach für Dauerbetrieb Einstellungen auf **3 × 80 USDC** setzen. Dauer-Live benötigt zusätzlich Paper-Soak, mindestens 250 freie USDC und eine frische Kontoprüfung.
7. **Live an** verlangt die separate Bestätigung für 3×80. Alte Signale werden nicht nachgehandelt.
8. **Live aus** sperrt neue Echtgeld-Einstiege. Eigene offene Positionen dürfen regulär aussteigen; unbekannte Orders werden nicht blind storniert.

## Sicherheit
Keine Binance-Private-Credentials in GitHub, Cloudjobs oder A01–A11. CI/Testnet sendet keine Orders. Der lokale Live-Ledger bindet Konto und Strategie; Saldo-/Orderabweichungen führen fail-closed zu NEEDS_REVIEW. Kein Kontoreset für einen normalen Update-/Backtestvorgang.
