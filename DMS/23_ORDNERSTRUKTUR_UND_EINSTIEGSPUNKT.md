# 23 – Ordnerstruktur und einziger Einstiegspunkt

Ergänzung 0.4.1: Der isolierte Orderjournal-Kern liegt ebenfalls unter `src/hixton/live/orders.py`, seine Tests unter `tests/test_live_orders.py`. Er ist nicht angeschlossen und legt im normalen Betrieb keine weitere Datenbank an. Kein zusätzlicher Testtrade-Starter und keine duplizierte Strategieengine.

Aktiver Stand: V6 unter `backtests/v6/`. Ein einziges Paper-Handelskonto bleibt unter `data/hixton.sqlite3`; abgelöste Paperkonten und alte Startlogs werden unter `backups/paper-v2-archive-20260906/` gesammelt. Ab 0.4.0 enthält `data/live-preparation.sqlite3` ausschließlich getrennten Sicherheits-/Vorbereitungs-Audit, **kein** zweites Paperkonto, keine Marktduplikate, keine Secrets. `src/hixton/live/` bündelt Schlüsselablage, Read-only-Binance-Prüfung und Vorbereitung. Keine `Startbot-neu.bat`, kein Löschen wissenschaftlicher Gegenbelege. Wartung ist ein Unterbefehl von `src/main.py`, nicht ein weiterer Starter.

Ergänzung DMS 1.7: `backtests/v6/` enthält nur `README.md`, den unveränderlichen `candidate.json`, einen kompakten kuratierten Nachweis unter `reports/` und ignorierte reproduzierbare Rohartefakte unter `runs/`. Keine neue Startdatei, keine zweite Handelsengine, keine großen Kerzendaten in Git. Der einzige Starter bleibt `Startbot.bat`.

## Verbindliches Prinzip

Das Projekt besitzt genau **eine zentrale menschliche Lesestartdatei**: `/README.md`, und genau **einen ausführbaren Windows-Starter**: `/Startbot.bat`.

Die Anwendung besitzt genau **einen technischen Einstiegspunkt**: `/src/main.py`. `Startbot.bat` enthält keine zweite Botlogik, sondern bereitet ausschließlich die lokale Python-Umgebung vor und delegiert an `src/main.py start`. Backtest, Paper, UI und der sicher gesperrte Live-Modus sind Modi dieses Einstiegs. Parallele Hauptskripte wie `start_backtest.py`, `paper_bot.py`, `live_bot.py`, `run_ui.py`, weitere `.bat`-Starter oder durchnummerierte Kopien sind verboten.

## Verbindliche Struktur

```text
Der-Hixton/
├── README.md                         # einziger Projektstart
├── Startbot.bat                      # einziger Windows-Starter, delegiert an src/main.py
├── pyproject.toml                    # Python-Paket und gepinnte Laufzeitabhängigkeiten
├── .gitignore
├── .gitattributes                    # byte-stabile LF-Zeilenenden für gehashte Pine-Quelle
├── DMS/                              # verbindliche Dokumentation
├── strategy/
│   ├── source_material/              # unveränderte Eingangsquellen
│   └── pine/                         # einmalige Eigentümer-Pine-Referenz für V2
├── backtests/
│   ├── v1/
│   │   ├── manifest-template.yaml
│   │   ├── runs/                     # konkrete Run-IDs
│   │   ├── reports/                  # freigegebene Berichte
│   │   ├── trades/                   # kleine/sanitisierte Tradeexports
│   │   └── data_quality/             # Qualitätsnachweise
│   ├── v2/                           # vorherige V2: README, Snapshot, lokale Runs
│   ├── v3/                           # verworfener Mehrfachslot-Versuch, lokale Runs
│   ├── v4/                           # coinindividuelle Parameterprüfung, nicht aktiv
│   └── v5/                           # Verlustdiagnose/Hixton-Schutzregeln, nicht aktiv
├── config/
│   └── examples/                     # secretfreie Beispiele
├── ui/                               # TypeScript-Quelle und reproduzierbarer UI-Build
├── src/                              # implementierte Anwendung
│   ├── main.py                       # einziger technischer Einstieg
│   └── hixton/                       # Domain, Daten, Backtest, Paper, Runtime und UI/API
└── tests/                            # Tests, Golden-Daten und Fixtures
```

Nicht versionierte Laufzeitdaten liegen in ignorierten Verzeichnissen wie `data/`, `runtime/`, `logs/` und `backups/`. Dazu gehören die beim Start und beim täglichen Audit automatisch ergänzten `1h`-Kerzen sowie die SQLite-Datenbank. `1m` in der UI bedeutet einen Monat und erzeugt keinen zweiten 1-Minuten-Datenbestand.

## Ein einziger Programmstart

Verbindliche Bedienform:

```text
Startbot.bat
py -3 src/main.py backtest all
py -3 src/main.py backtest single --symbol ETHUSDT
py -3 src/main.py backtest portfolio
py -3 src/main.py backtest all --strategy v2
py -3 src/main.py backtest portfolio --strategy v2
py -3 src/main.py backtest portfolio --strategy v3
py -3 src/main.py backtest research --study v5 --output backtests/v5/runs/neuer-review/research.json
py -3 src/main.py paper
py -3 src/main.py live
py -3 src/main.py ui
```

Alle Befehle führen intern über denselben Einstieg und dieselbe Konfigurations-/Strategieengine. `live` bleibt technisch gesperrt, bis die Live-Gates bestanden sind. `Startbot.bat` startet den vorgesehenen Standard `PAPER + lokale UI`.

## Backtestversionierung

- `backtests/v1`: erste freigegebene Backtestmethodik.
- `backtests/v2`: vorherige Pine-v6-Paperreferenz; `README.md` ist der kuratierte Wahrheitsstand, `candidate.json` der maschinenlesbare Snapshot und `runs/` enthält lokale unveränderliche Läufe.
- `backtests/v3`: verworfener Mehrfachslot-Versuch mit eigener README und eigenem Snapshot; lokale Runs werden nicht eingecheckt.
- `backtests/v4` und `backtests/v5`: getrennte Forschungsberichte, jeweils ein README, ein kompakter Nachweis unter `reports/`, große lokale Rohberichte unter ignoriertem `runs/`. Keine aktivierbare Paperstrategie.
- Reine Wiederholung mit gleichen Regeln erhält innerhalb derselben Version eine neue unveränderliche Run-ID unter `runs/`.
- Ein gültiger Run wird nicht überschrieben oder nachträglich „verbessert“.
- Jede Version referenziert Code-, Strategie-, Config- und Datenhash; V2 referenziert zusätzlich verpflichtend den Eigentümer-Pine-Hash.
- Versionen werden numerisch ohne Fantasienamen geführt.

## Was nicht in den Hauptordner gehört

- Kopien wie `bot_final.py`, `bot_final2.py`, `bot_neu.py`;
- zehn coinbezogene Startdateien;
- separate Backtest-Engines je Coin;
- lose Reports oder CSV-Dateien;
- API-Keys, `.env`, Datenbanken, Marktdaten oder Logs;
- temporäre GPT-/Codex-Arbeitsdateien.
- weitere `.bat`-/PowerShell-Starter oder generierte UI-Abhängigkeiten wie `node_modules`.

## Verbindliche Aufräumregel

- Git ist die Historie; alte Dateien werden nicht als `old`, `backup`, `final2` oder ähnlich aufgehoben.
- Generierte Inhalte haben genau ein Buildziel. Temporäre Verzeichnisse und Abhängigkeitscaches bleiben ignoriert.
- Leere Platzhalter werden entfernt, sobald ein Ordner reale Inhalte besitzt.
- Lose Berichte, Datenbanken und Downloads im Hauptordner sind ein Fehler.
- Vor einem Commit werden verwaiste Dateien, konkurrierende Einstiegspunkte und nicht ignorierte Laufzeitdaten geprüft.
- Löschen oder Verschieben fremder/unklarer Dateien erfolgt erst nach Zielprüfung; Nutzeränderungen werden nicht still überschrieben.

## Neue Datei oder neuer Ordner

Ab 05.09.2026 ergänzen `backtests/v4/` und `backtests/v5/` die bestehende Versionsstruktur. Die Forschungsorganisation liegt in `src/hixton/backtest/research.py` (V4) und `coin_review.py` (V5); beide werden nur über `src/main.py backtest research` aufgerufen. Die V5-Filter-/Stopentscheidung liegt einmalig in `domain/trade_policy.py` und wird von Einzel- und Portfolioengine gemeinsam verwendet. Keine Kopie pro Coin, keine zweite produktive Signalengine. `Startbot.bat` bleibt der einzige Windows-Starter.

Vor dem Anlegen wird geprüft:

1. Hat die Datei eine eindeutige Verantwortung?
2. Gibt es bereits einen richtigen Zielordner?
3. Ist sie eine Quelle, Konfiguration, Testfixture, Laufzeitdatei oder Ergebnisartefakt?
4. Erzeugt sie einen zweiten Einstiegspunkt? Dann ist sie abzulehnen.
5. Muss sie überhaupt in Git oder gehört sie in einen ignorierten Laufzeitordner?

Diese Regel gilt gleichermaßen für Codex, GPT und manuelle Änderungen.
