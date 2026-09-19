# 12 – Tests und Abnahmekriterien

Status: CURRENT · 19.09.2026

Ein aktueller Download-/Releasekandidat benötigt auf demselben Commit:
- Cloud Preflight PASS;
- vollständiges pytest PASS;
- Python compileall, Ruff und mypy PASS;
- UI TypeScript-Check und Produktionsbuild PASS;
- Dashboard Backtest E2E PASS;
- aktuelle V6-Produktvertrags-Tests PASS;
- A01–A08 PASS;
- A10 evidence_contract_passed=true und repair_required=false;
- A09 QA_PASS;
- A11 GOVERNANCE_PASS.

Für eine Profilpromotion zusätzlich: Top-K/Validation/full/stress, marginaler 3×80-Test, Kombinationstest und finaler 10×250-/3×80-Gate.

Paper-Freshness und aktive Strategie-Session müssen zum kanonischen V6-Digest passen. Alte grüne Runs werden durch spätere relevante Commits ungültig.
