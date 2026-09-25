# 08 – UI/UX-Spezifikation

Status: CURRENT · 25.09.2026

Die lokale deutsche UI zeigt System/Paperstatus, zehn USDC-Marktkarten, Charts/Signale/Fills, Positionen, Datenqualität, Logs und aktuelle V6-Backtests.

## Einstellungen

Unter **1 · Handel** existiert genau eine editierbare Kapitalvorgabe:

**Maximaler USDC-Einsatz**

Standard: 250 USDC. Aktuell validierter Bereich: 100–1.000 USDC. Die UI zeigt Slotzahl, Tranchengröße, Reserve und Policy nur als vom Server/Allocator abgeleitete Information; sie sind nicht separat editierbar. Allocator-Version: **CAPITAL-V1-2X50PCT**.

Dasselbe gespeicherte Maximalbudget gilt für Portfolio-Backtest, Paper und normalen Livebetrieb.

## Binance und Live

API-Key/Secret werden lokal gespeichert und niemals im Browser persistiert. IP-Beschränkung ist für die Freigabe erforderlich. Lesen und Spot-Handel EIN; Withdrawal, Transfer, Margin, Futures und Optionen AUS.

Der kontrollierte 1×50-USDC-Test ist ein separater Sicherheitsmodus und ändert das Maximalbudget nicht. Nach Freigabe wartet er auf ein neues gültiges Signal. Erst nach vollständig reconciliertem Roundtrip können die übrigen Live-Gates den normalen Maximalbudget-Betrieb freigeben.

Oben rechts zeigt die UI permanent die installierte Hixton-Version.
