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
2. In Hixton lokalen Schlüsselbereich entsperren und Key/Secret speichern. **Binance-Verbindung prüfen** ist nur eine Diagnosefunktion; der 50-USDC-Test und „Live an“ führen ihre ausreichende Kontoprüfung beim Klick automatisch aus. Bereits vorhandene freie BTC-/Altcoin-/USDT-Bestände werden als Hinweis angezeigt, blockieren den Test aber nicht und werden niemals als Hixton-Position übernommen. Nach dem Scharfschalten keine manuellen Spot-Bestandsbewegungen durchführen, bis der Lauf reconciled bzw. Live wieder sicher deaktiviert ist.
3. Maximalbudget bleibt standardmäßig 250 USDC.
4. **1 × 50 USDC · Test freigeben**. Keine sofortige Order: Hixton wartet auf ein neues gültiges Signal, führt den einmaligen Entry und regulären Exit aus und reconciled Konto/Fills.
5. Erst wenn der 1×50-Roundtrip einschließlich echtem Binance-BUY, echtem Binance-SELL und Konten-/Fill-Reconciliation vollständig abgeschlossen ist, wird **Live an** freigegeben. Beim Klick prüft Hixton Konto/API-Rechte, zehn Märkte, Marktdaten und das gespeicherte Maximalbudget erneut; ein separater Paper-Soak ist kein zusätzliches Gate.
6. Eine spätere Budgetänderung stoppt neue Echtgeld-Einstiege; erneute Freigabe bindet den neuen Plan nur bei sauberem Ledger.
7. **Live aus** stoppt neue Einstiege; offene eigene Positionen dürfen regulär aussteigen.

Cloud/CI/A01–A11 besitzen keine privaten Binance-Credentials und senden keine Orders.

### Live-Abnahme-/Fehlerbericht
Im geschützten Bereich **Live-Abnahme- & 24/7-Bericht** kann der aktuelle JSON-Bericht aktualisiert und heruntergeladen werden. Zusätzlich wird `live-execution-report.json` lokal bei Zustandsänderungen und spätestens im 5-Minuten-Heartbeat aktualisiert. Bei Fehlern zuerst diesen Bericht sichern. Er enthält keine API-Schlüssel/Secrets, dafür aber Signalzeit, Order-Submit-Zeit, Binance-Order-/Fill-Zustand, Trial-/Live-Roundtrips, offene/ungeklärte Intents, Paper-vs-Live-Abweichungen sowie eingefrorene und aktuell laufende Source-/Strategie-/Allocator-Versionen.

### Patch während Echtgeldbetrieb
Ein Patch darf nie still neue Orders mit einer alten Live-Source erzeugen. Erkennt der laufende Bot einen Source-Wechsel, werden neue Einstiege gesperrt. Bei eigenen offenen Positionen wechselt der Ledger auf EXIT_ONLY, damit nur deren regulärer überwachte Ausstieg/Reconciliation erfolgen kann. Ohne offene/unaufgeklärte Position wird Live deaktiviert und muss mit dem neuen Patch ausdrücklich erneut aktiviert werden. Eine Strategieabweichung ist kein normaler Hot-Patch und bleibt fail-closed/NEEDS_REVIEW.
