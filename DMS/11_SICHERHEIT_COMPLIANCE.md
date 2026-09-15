# 11 – Sicherheit und Compliance

## Implementierter Schutz ab 0.4.0 (Vorbereitung, keine Echtgeldfreigabe)

- Native Windows-Credential-Manager-API, Generic Credential, Persistenz `CRED_PERSIST_LOCAL_MACHINE`: **aktueller Windows-Benutzer auf diesem PC**, nicht alle Benutzer; kein Enterprise-Roaming und kein Klartext-Fallback. Ziel ist pro Installations-Datenbankpfad gehasht; Umzug benötigt erneute Einrichtung. Es werden nur zwei exakte Hixton-Ziele angesprochen, nie fremde Credentials aufgelistet.
- HMAC API-Key/Secret und der Salt/Scrypt-Verifier des getrennten lokalen Hixton-Passworts liegen außerhalb des Projekts im Windows-Speicher. Passwort wird nicht im Klartext persistiert; Scrypt N=32768/r=8/p=1. Binance-Kontopasswort wird nicht benötigt. Ersteinrichtung ist nur für den vertrauenswürdigen lokalen Betreiber vorgesehen, keine Mehrbenutzer-Webplattform.
- Geschützte Aktionen benötigen ein korrektes lokales Passwort und eine 15-Minuten-Sitzung; HttpOnly/SameSite=Strict-Cookie nur unter `/api/live`, serverseitiger Token-Hash, nach Restart abgelaufen, ein geschützter Browser zur Zeit. Fünf Fehlversuche führen zu einer prozesslokalen 60-Sekunden-Sperre. Nur exakt gleiche localhost-Origin, zusätzlich Action-Header/TrustedHost; keine CORS-Freigabe. Loopback-HTTP, kein Remotezugang.
- Secret-Eingaben maximal 4096 Byte, keine Pydantic-Input-Echos, keine URL/Signature/Header/Provider-Freitext-Fehlerausgabe, API `Cache-Control: no-store`. Kein Browserstorage oder Secret-Export; Fingerprint und Änderungsdatum nur entsperrt. Python kann Kopien sensitiver Strings im Prozessspeicher nicht garantiert überschreiben; Crash-/Speicherdumps sind deshalb weiter zu schützen.
- Read-only-Client besitzt **keine Order-/Transfer-/Auszahlungsfunktion**. Fester TLS-Host `api.binance.com`, keine Redirects oder Umgebungsproxies, kleine Endpunkt-Allowlist, zehn Sekunden Timeout, keine automatische Wiederholung, Rate-Limit-Wartezeit. Ein Netzwerkfehler bedeutet nie erfolgreiche Freigabe.
- Grenzen: Schadsoftware unter demselben Windows-Benutzer, Administratorzugriff, kompromittierte Browser/Erweiterungen oder Prozessdumps sind nicht durch dieses App-Passwort zuverlässig abwehrbar. Credential Manager ist kein absoluter Zugriffsschutz. Windows-Konto/BitLocker/Updates/IP-Allowlist und dedizierter Binance-Bot-Account bleiben Betreiberaufgaben.

Primärquellen, geprüft 06.09.2026: [Microsoft Credential-Struktur/Persistenz](https://learn.microsoft.com/en-us/windows/win32/api/wincred/ns-wincred-credentialw), [CredWriteW](https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-credwritew), [Binance Signatur und Request-Sicherheit](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/request-security), [Binance Key-Rechte](https://developers.binance.com/docs/wallet/account/api-key-permission).

## Sicherheitsziele

- keine unbefugten Orders;
- keine Auszahlungsmöglichkeit über den Bot-Key;
- keine Secrets in Dateien, Logs, Screenshots oder Backtestartefakten;
- Manipulationen an Strategie, Konfiguration und Ergebnissen erkennbar;
- kontrollierte Recovery ohne Doppelorders;
- geringstmögliche Rechte.

## API-Schlüssel

- Live verwendet einen eigenen Bot-Account oder Binance-Subaccount; manueller Handel auf genau diesem Account ist verboten;
- eigener API-Key nur für diesen Bot;
- ausschließlich Leserechte und Spot-Handel;
- Withdrawal/Auszahlung deaktiviert;
- Margin/Futures deaktiviert;
- wenn verfügbar IP-Allowlist;
- getrennte Schlüssel für Test/Paper und Live;
- Rotation nach Incident oder regelmäßig gemäß Betriebsentscheidung;
- Schlüsselwerte werden nie in Git, Markdown, YAML-Beispielen oder UI-Export gespeichert.

Erkennt die Reconciliation eine manuelle/Fremdorder oder eine nicht erklärbare Saldenänderung, werden neue Live-Entries global pausiert, bis der Eigentümer den Zustand geklärt und auditiert hat. Der Bot eignet sich nicht zum parallelen Verwalten eines manuell gehandelten Spotbestands.

## Secret-Speicherung

Bevorzugt Betriebssystem-Credential-Store oder dedizierter Secret-Store. Umgebungsvariablen sind nur zulässig, wenn Prozess-, Dump- und Logzugriffe ausreichend geschützt sind. Die UI zeigt höchstens „gesetzt“, Fingerprint/Endziffern und Rotationsdatum.

## Zugriff und lokale Installation

- API standardmäßig nur an localhost binden;
- externe Erreichbarkeit ist gesonderter Scope mit TLS, Auth und Firewall;
- schreibende UI-Aktionen erfordern Authentisierung;
- Sitzungen laufen ab;
- Brute-Force-/Rate-Limit-Schutz für Login und sensitive Aktionen;
- Dateirechte beschränken Datenbank, Logs, Backups und Config auf den Servicebenutzer.

## Integrität und Supply Chain

- Abhängigkeiten werden versioniert und auf bekannte Schwachstellen geprüft;
- Builds sind reproduzierbar soweit praktikabel;
- Strategie-, Config-, Daten- und Berichtshashes werden gespeichert;
- Updates laufen erst in Test/Paper, nicht direkt in Live;
- signierte Releases/Checksums sind für Live vorgesehen;
- DMS und Codeänderungen erhalten Review und Changelog.

## Audit

Auditpflichtig sind:

- Login/Logout und fehlgeschlagene Authentisierung;
- Moduswechsel;
- Aktivieren/Deaktivieren des Tradings;
- Not-Aus und manuelles Schließen;
- API-Key setzen/rotieren (ohne Secretwert);
- Konfigurations- und Strategieänderung;
- Backteststart und -freigabe;
- Datenrevision;
- Order-/Reconciliation-Intervention;
- Backup/Restore.

Auditdaten sind append-only bzw. manipulationsgeschützt und werden nicht über normale UI-Löschfunktionen entfernt.

## Datenschutz

Das System benötigt keine unnötigen personenbezogenen Daten. Account-IDs werden, soweit möglich, pseudonymisiert. Logs/Supportpakete redigieren Tokens, Secrets, vollständige Kontokennungen und ggf. IP-Adressen. Markt-/Backtestdaten, Trade-Ledger, Auditdaten, Incidentberichte und Release-Nachweise bleiben dauerhaft; normale Betriebslogs werden 90 Tage online gehalten und dürfen danach nach dokumentiertem Retention-Job gelöscht werden.

## Rechtliche und finanzielle Grenzen

- Der Bot stellt keine Rendite sicher.
- Historische Ergebnisse sind keine Prognose.
- Gebühren, Steuern, Börsenregeln und lokale rechtliche Anforderungen können sich ändern.
- Vor Livebetrieb sind Nutzungsbedingungen der gewählten Börse, regionale Verfügbarkeit und steuerliche Aufzeichnungspflichten durch den Betreiber zu prüfen.
- Diese DMS ersetzt keine Rechts-, Steuer- oder Anlageberatung.

## Threat-Szenarien

Mindestens testen:

- gestohlener Read/Trade-Key;
- manipulierte Konfigurationsdatei;
- Replay einer Orderanfrage;
- gefälschte/verspätete Marktdaten;
- UI-CSRF bzw. unberechtigter Moduswechsel;
- Log-Injection/Secret-Leak;
- Abhängigkeit mit Schadcode;
- kompromittiertes Backup;
- DoS/Rate-Limit mit stale Daten;
- lokaler Benutzer ändert DB-Zustand.

## Live-Freigabebedingung

Live bleibt technisch gesperrt, bis mindestens Secretschutz, Least Privilege, Reconciliation, Idempotenz, Not-Aus, Audit, Backup/Restore, Paper-Soak-Test und Incident-Runbook bestanden sind.
