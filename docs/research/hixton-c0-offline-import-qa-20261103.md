# Hixton C0 – nativer Offline-Replay und Importkorrektur (03.11.2026)

## Ergebnis und Freigabegrenze

Die sechs historischen nativen C0-Kontrollfälle wurden auf GitHub Actions tatsächlich ausgeführt, nicht bloß die Verifier gestartet. Alle sechs meldeten `baseline_exact: true` und Exitcode 0. Die separate, nachgelagerte Prüfung aus den gespeicherten Resultaten prüfte ohne weitere Backtest-Wiederholung die veröffentlichten C0-Originale gegen die neuen Outputs:

- `Trades.json`, `Fills.json`, `Signals.json` und dekomprimierte `Equity.csv.gz` sind **in allen 6 Fällen exakt gleich**.
- Alle Felder der neu berechneten `Result.json` stimmen mit den entsprechenden Werten im eingefrorenen Original überein.
- Das eingefrorene Original-`Result.json` besitzt aber zusätzliche Berichtsfelder, die der portable Replay nicht erneut ausgibt: `checks`, `control_exact`, `event_counts`, `events`, `execution_diagnostics`, `method_sha256`, `research_only_not_installed`, `seconds`, `strategy`. **Daher sind die vollständigen Result.json-Dateien nicht strukturell identisch; diese Berichtsdifferenz darf nicht verschwiegen werden.**
- QA-Urteil: `FINANCIAL_LEDGER_PARITY_PASS_WITH_FROZEN_EXTRA_RESULT_FIELDS`. Das ist eine belegte **numerische und Ledger-Parität**, aber keine Erklärung aller zusätzlichen eingefrorenen Diagnostik- und Methodenfelder und noch keine methodische Freigabe neuer Strategiekandidaten durch Dot 4.

### Verifizierte Kapital-Endstände (USD/USDC-Modellnotation)

| Historisches Fenster | Kosten | Nativer C0 Endstand |
|---|---|---:|
| `original_32k` | `current` | 33.867,796992897484 |
| `original_32k` | `stress` | 23.539,2748156655696 |
| `current_26oct` | `current` | 11.069,1269577412202 |
| `current_26oct` | `stress` | 7.612,3297185267768 |
| `latest_long` | `current` | 18.267,6599517494945 |
| `latest_long` | `stress` | 11.816,0501812735542 |

## Quellen und eigenständige Hashnachweise

- Originalprodukt-Code: `f56d48536525830dd6ea50bf5bc174a6f9aeff8c`.
- Normierte Originalquellen-SHA256: `5cf39658dc6b1ee827ec0daefd73b2384a9edd0ff116ba0203f9ab8bb7737797`.
- Originalresearch-ZIP `Hixton-Loss-Handoff-20261102.zip`, lokal geprüfte SHA256: `d1d1cde8347665d74da71f9e44bb3876dc6662bfe4bfc9e34dcab1dfecd84308`.
- Isolierter Research-Import-Bootstrap SHA256: `12dbc07482d037bef47305a9005124308e7215d24e9977c50c56ffcf77aad3b2`. Quelltext steht in dem GitHub-Actions-Workflow/Run-Manifest, einschließlich `source_files_modified=false` und `offline_guard_disabled=false`.
- Replay-Workflow-Code-Commit: `27d36333f40df056fabeb4b4c83619b947e54fb6`.
- Replay mit sechs C0-Einzelergebnissen, gehashten 49 Outputdateien und Exitcodes: https://github.com/127027/Der-Hixton-von-GPT/actions/runs/41624952024 .
- Unabhängiger finanzieller Ledger-/Result-Wertevergleich **ohne erneute sechs Replays**: https://github.com/127027/Der-Hixton-von-GPT/actions/runs/41625998843 .

## Root Cause

`hixton.backtest.engine` benötigt `hixton.data.quality`. Das normale Python-Importverhalten führt dabei `src/hixton/data/__init__.py` aus. Dieses importiert jedoch sofort `hixton.data.binance`. Der ausdrücklich offline-only portable Wrapper `run_baseline.py` verbietet dieses Modul in seiner `sys.modules`-Integritätsprüfung und bricht vor dem Rechnen ab. Der Netzwerkzugriff war dabei bereits via `sys.addaudithook` für Socket-Ereignisse gesperrt; es war kein Live-/Key-Aufruf nachgewiesen. Der Wrapper-Guard ist für diesen reinen Qualitätsimport zu streng.

Die bereits erfolgreiche Research-Lösung war ein **isolierter Import-Bootstrap**, der den Package-Namespace `hixton.data` ausschließlich für seinen benötigten Untermodulimport vorbereitet und damit den nicht benötigten eager Binance-Client-Import vermeidet. Der Originalwrapper wurde unverändert inklusive Audit-Hook, Guard und Source-/Data-Checks per `runpy.run_path` ausgeführt. Keine Originalstrategie- oder Daten-Dateien geändert. **Dies ist eine temporäre Research-Startmethode, keine freigegebene Änderung des Produkts oder eines eingefrorenen Originalpakets.**

## Präziser Codex-Handoff zur dauerhaften Korrektur

1. Diesen Importkonflikt in einer **neuen, eigenständig versionierten Research-Runner-Kopie** gezielt beheben. Der öffentliche `hixton.data.quality`-Import muss offline funktionieren. `socket.*` Audit-Block, Verbot privater Schlüssel/Live-Orders und Unveränderlichkeit der Archivdaten beibehalten. Keine pauschale Entfernung aller Modul-Sicherheitsprüfungen und keine stillen Änderungen der bereits veröffentlichen drei ZIPs.
2. Die Runner-Korrektur als separaten Research-Diff/Version sowie SHA256 für Runner und Eingabedaten ausweisen. Teste sowohl erfolgreiche Offline-Qualitätsimporte als auch absichtlich blockierte Netzwerk-/Private-Client-Pfade.
3. Bereits vorhandene sechs C0-Kontrollläufe/Artefakte als numerische Vergleichsbasis wiederverwenden. Wiederholung nur bei neuer Runner-Version oder wirklich anderer Rechenumgebung. Kontrolliere die im eingefrorenen `Result.json` zusätzlichen `checks` und `execution_diagnostics` separat, statt die reine Result-Objekt-Ungleichheit zu ignorieren.
4. Dot4 soll Methodik- und Originalergebnis-Parität unabhängig abnehmen. **Vor dieser Entscheidung: keine finanzielle Kandidatenrechnung und keine Live-Freigabe.**
5. Erst dann dürfen Dots 1–3 jeweils ihre eine bereits vorbereitete isolierte Hypothese gegen die unveränderte C0-Basis unter allen bestehenden Erhaltungs-, Kostenstress- und Crash-Gates prüfen. Dot5 dokumentiert alle Ergebnisse. Gewinnrangfolge: unter bestandenen Gates höchstes Netto-Endkapital; nur bei identischem Gewinn geringerer Drawdown.

## Sicherheitsgrenze

Die Änderungen dieser Vorbereitung beschränken sich auf `research/hixton-native-baseline-proof-20261103` und Read-only-GitHub-Actions-Artefakte. Keine API-Schlüssel, Echtgeldpositionen, Live-, Paper-, UI- oder produktiven Strategieänderungen.
