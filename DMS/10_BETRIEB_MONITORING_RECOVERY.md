# 10 – Betrieb, Monitoring und Recovery

Status: CURRENT · 19.09.2026

Paper ist für fortlaufenden Betrieb ausgelegt. Startup prüft Datenbank, Strategie-Session, zehn Checkpoints, Datenqualität und verfügbare Binance-Daten. Verpasste finalisierte Bars werden nach Restart nachverarbeitet.

A05 prüft in der Cloud persistierten Paper-State, 3×80-Settings, Integrität und Freshness. Ein State älter als zwei Stunden blockiert den Release-Gate.

Strategie-Digest-Wechsel sind absichtlich fail-closed. Nach vollständig validierter Promotion erfolgt ein expliziter paper-activate-Vorgang ohne Kontoreset. Bestehende Historie bleibt erhalten; gegebenenfalls werden alte Positionen kontrolliert zum Cutover modelliert.

Bei Daten-/Runtimefehlern: keine neuen Entries, Ursache beheben, Zustand reconciliieren, betroffene Tests neu ausführen.
