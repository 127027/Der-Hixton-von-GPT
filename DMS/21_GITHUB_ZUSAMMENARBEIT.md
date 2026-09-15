# 21 – GitHub-Zusammenarbeit

## Repository

- Remote: `https://github.com/127027/Der-Hixton`
- vom Eigentümer für die gemeinsame Arbeit von Codex und GPT vorgesehen;
- Remoteprüfung am 31.08.2026: **öffentlich**, Branch `main` vorhanden und mit der DMS-Struktur befüllt;
- GitHub ist die zentrale Projektablage; geprüfte Arbeitsstände werden fortlaufend committed und gepusht. Der eingefrorene Dokumentationsstand erhält den Tag `dms-v1.0.0`; dieser ist kein fertiger Bot-/Live-Release.

Das lokale OneDrive-Verzeichnis ist die Arbeitskopie, GitHub die zentrale versionierte Projektablage. Synchronisation erfolgt kontrolliert per Commit/Push, niemals unbemerkt durch bloßes Speichern.

## Verbindliche Repository-Struktur

Die vollständige Struktur steht in Dokument 23. Im Hauptordner existiert nur `README.md` als menschlicher Einstieg. Die spätere Anwendung besitzt nur `src/main.py` als technischen Einstieg; Backtest, Paper, Live und UI sind Modi desselben Programms.

```text
README.md              # einziger Projektstart
DMS/
  ... verbindliche Dokumente ...
strategy/
  source_material/
  pine/                # einmalige, vom Eigentümer freigegebene Pine-Referenz
backtests/
  v1/                  # danach v2, v3 nur bei neuer Methodik
src/
tests/
config/
  examples/          # niemals echte Secrets
.gitignore
.gitattributes          # Pine-Referenz auf LF fixiert, damit SHA-256 plattformstabil bleibt
LICENSE              # in DMS V1 bewusst nicht vorhanden; siehe Lizenzregel
```

Historische Marktdaten, Datenbanken, große Logs, Backups, API-Schlüssel und lokale Secret-Dateien gehören nicht ins Git-Repository. Das gilt insbesondere für die beim Start und beim täglichen Audit automatisch geladenen `1h`-Kerzen und die SQLite-Datenbank. Lose oder durchnummerierte Startskripte im Hauptordner sind verboten.

Aktuelle Übergabe vom 02.09.2026: Gemeinsamer Arbeitsstand ist Branch `codex/build-foundation-v1` in Pull Request 2. Vor Weiterarbeit zuerst diesen Branch beziehungsweise nach Merge den neuesten `main`-Stand holen; DMS 00 beschreibt den fachlichen Übergabepunkt. Große lokale Daten- und Run-Artefakte werden anhand der gespeicherten Kommandos und Hashes reproduziert, nicht per Git verteilt.

## Branch- und Reviewregel

- `main`: nur geprüfte, konsistente Stände;
- Codex-Änderungen: Branch `codex/<kurzes-thema>`;
- GPT-Änderungen: Branch `gpt/<kurzes-thema>`;
- vor Arbeitsbeginn neuesten `main`-Stand holen;
- nicht gleichzeitig dieselbe Datei ohne vorherige Aufteilung bearbeiten;
- jede Änderung nennt betroffene Anforderungs-/Entscheidungs-IDs;
- Pull Request/Review vor Merge in `main`;
- Strategie-, Kapital- oder Orderänderungen benötigen Eigentümerfreigabe;
- Konflikte werden fachlich gelöst, nicht durch blindes Überschreiben.

## Commit-Konvention

Beispiele:

```text
docs(DMS): split paper 3x80 from backtest 10x250
docs(strategy): record DEC-003 timeframe decision
test(parity): add ETH golden bars for pine v1
fix(data): reject provisional candle as signal input
```

Commits sollen klein, nachvollziehbar und thematisch geschlossen sein. Ein DMS-Update und eine davon abweichende Codeänderung dürfen nicht unbemerkt in demselben Commit versteckt werden.

## Quellen der Wahrheit in Git

- `DMS/` beschreibt den freigegebenen Sollzustand.
- `DMS/03_STRATEGIE_HIXTON.md` mit `HIXTON-SPEC-1.0` definiert die historische V1-Signallogik weiterhin reproduzierbar.
- Die Eigentümer-Pine-Datei, ihr Hash und der jeweils ausdrücklich freigegebene Snapshot definieren die aktive Paperstrategie, ohne V1-Artefakte oder alte Ledgerereignisse umzudeuten.
- Neue Varianten liegen geordnet unter `backtests/v3`, `v4` usw.; eine verworfene Version bleibt als kleiner kuratierter Nachweis erhalten, große Runs bleiben lokal ignoriert.
- Konfigurationsbeispiele enthalten keine echten Schlüssel.
- Dependency-Lock und Codecommit definieren einen Build.
- Backtest-Manifest referenziert Code-, Config- und Datenhash.
- Ein Release-Tag wird erst nach bestandenem Gate gesetzt.

## Geheimnisse und sensible Dateien

Niemals committen:

- Binance API Key/Secret;
- `.env` mit echten Werten;
- Datenbank/Wallet-/Browserprofile;
- Account-, Saldo- oder Steuerexporte mit Identifikatoren;
- Backup-Archive;
- Screenshots mit Secrets;
- Pine-Quellen, für die Rechte oder Veröffentlichungsfreigabe fehlen.

Vor jedem Push läuft ein Secret-Scan. Ein versehentlich veröffentlichter Schlüssel wird nicht nur aus Git gelöscht, sondern sofort bei Binance gesperrt und rotiert.

## Öffentliche Sichtbarkeit, Pine und Lizenz

- Das Repository ist gemäß DEC-031 öffentlich.
- Öffentlich bedeutet nicht automatisch Open Source. Solange keine `LICENSE`-Datei vom Eigentümer bewusst freigegeben wurde, bleiben die üblichen Urheberrechte vorbehalten; fremde dürfen den Inhalt ansehen, erhalten aber keine darüber hinausgehende pauschale Nutzungslizenz.
- Eigene DMS- und Projektspezifikation dürfen veröffentlicht werden.
- Die am 01.09.2026 vom Eigentümer ausdrücklich zur Projektverwendung übermittelte Datei `strategy/pine/Der_Hixton_Indikator_v6.pine` darf committed werden. Andere proprietäre/fremde Pine-Quellen bleiben ohne eindeutigen Rechte- und Lizenznachweis ausgeschlossen.
- Öffentliche Backtestreports müssen reproduzierbare Methodik und alle Coins zeigen, dürfen aber keine Account-IDs, Keys, Saldenexporte oder sonstigen personenbezogenen Kontodaten enthalten.
- Eine spätere Open-Source-Lizenz ist eine neue Eigentümerentscheidung; sie wird nicht automatisch angenommen.

## 99-%-Releasegate

Ein Stand darf vorher als klar gekennzeichneter Arbeitsstand gepusht werden. Der reine DMS-99-%-Tag `dms-v1.0.0` entsteht, wenn:

- normative Referenzspezifikation vorhanden;
- kritische Entscheidungen geschlossen;
- DMS-Link-/Konsistenzprüfung grün;
- öffentliche Repo-Sichtbarkeit, Herkunft der Eigentümer-Pine-Datei und Ausschluss fremder Quellen dokumentiert sind;
- Secret-Scan grün;
- DMS-Changelog und Freeze-Status gesetzt sind.

Ein Bot-, Backtest-, Paper- oder Live-Release nutzt separate spätere Tags und benötigt zusätzlich die Gates aus DMS 12. `dms-v1.0.0` behauptet ausdrücklich keine implementierte oder profitable Software.

Jeder Push ist eine externe Änderung und wird als eigener Schritt verifiziert.
