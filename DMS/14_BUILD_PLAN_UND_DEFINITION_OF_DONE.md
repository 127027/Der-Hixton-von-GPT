# 14 – Build-Plan und Definition of Done

Status: CURRENT · 26.09.2026

Die aktuelle Produktlinie ist V6 mit gemeinsamem Backtest/Paper-Kern und separat fail-closed vorbereitetem lokalem Livepfad. „Done“ für einen Releasekandidaten bedeutet:
1. ein sauberer V6-Produktpfad ohne auswählbare Legacystrategien;
2. aktuelle DMS/README/Agent-Memory;
3. keine duplizierte Strategieversion in Config;
4. aktuelle V6-Evidenz unter backtests/v6 einschließlich frischem Maximalbudget-Portfolio-E2E;
5. reproduzierbare Baseline-/Stress-Backtests;
6. persistentes, frisches Paper;
7. UI-Quellcode und ausgeliefertes Bundle synchron;
8. vollständige Python/UI-Regressionsuite;
9. A09 QA_PASS und A11 GOVERNANCE_PASS.

Ein Release darf nur dann als Live-readiness-fähig bezeichnet werden, wenn der separate lokale Ersttest weiterhin explizit gesperrt/freigabepflichtig ist, Cloud/Agenten keine Orderrechte besitzen und die vollständigen Release-/QA-/Governance-Gates auf exakt demselben Download bestanden wurden.
