# 01 – Produktvision und Scope

Präzisierung 18.09.2026: Ziel ist die effiziente Nutzung von drei 80-USDC-Slots mit guten Signalen aus zehn Coins. Der Standard-Batch 10×250 USDC diagnostiziert und optimiert jeden Coin separat; der anschließend unverändert zusammengesetzte Zehn-Coin-Profilsatz wird im gemeinsamen 3×80-USDC-Portfolio geprüft. Hohe Tradezahl ist erwünscht, darf aber nicht durch erfundene Signale oder Look-ahead erzeugt werden. Jede Coin-Eignung bleibt nach Kosten, Trainings-/Validierungstrennung und unterschiedlichen Marktphasen nachzuweisen.

Status: `VERBINDLICH` für DMS V1.3.

## Produktziel

Der Bot soll die freigegebene Hixton-Indikatorlogik für zehn Kryptowährungspaare deterministisch auswerten, historische Daten reproduzierbar backtesten, im freigegebenen Modus Orders verwalten und Zustand, Charts, Signale, Performance und Systemgesundheit transparent in einer lokalen UI zeigen.

Der Bot ist ein regelbasiertes Ausführungs- und Beobachtungssystem. Er entscheidet nicht mittels KI, Nachrichten, Stimmung, manueller Interpretation oder nicht dokumentierten Zusatzindikatoren.

## Erfolgsbild

Ein fachkundiger Dritter kann anhand dieses DMS und der späteren Artefakte:

- exakt erklären, wann ein Signal entsteht;
- denselben Backtest mit identischen Ergebnissen wiederholen;
- jede Order auf Kerze, Signal, Konfiguration und Bot-Version zurückführen;
- Datenlücken, veraltete Kurse oder einen ausgefallenen Scheduler erkennen;
- den Bot nach Neustart ohne Doppelorder sicher fortsetzen;
- in der UI historische und laufende Zustände unterscheiden;
- nachvollziehen, warum eine Order ausgeführt, abgelehnt, blockiert oder übersprungen wurde.

## Enthalten

- zehn konfigurierte Binance-Spot-Paare mit USDC als aktive Quote-Währung; historische Langzeitanalyse darf denselben Basisasset-USDT-Preisweg ausschließlich als klar gekennzeichneten Proxy verwenden;
- Papersystem als Live-Vorbereitung mit gemeinsamem Modellkapital von 250 USDC (240 USDC Slots plus 10 USDC anfängliche Reserve) und drei anfänglichen Positionsslots à 80 USDC; freie Slots werden nach `ranked_repeat` auf gültige Kandidaten verteilt;
- getrenntes Backtestsystem mit zehn isolierten Tests à 250 USDC sowie frei wählbaren Einzeltests, zum Beispiel nur ETH/USDC; derselbe kanonische Profilsatz speist anschließend den gemeinsamen 3×80-Test;
- Einzelberichte pro Paar und ein aggregierter Portfoliobericht;
- Mindesttestfenster von drei vollständigen Jahren;
- historische OHLCV-Daten und laufende inkrementelle Aktualisierung;
- Startprüfung und täglicher Mitternachtsabgleich;
- Live-/Near-Live-Chart mit Heute, 1W, 1M, 1J und 3J;
- Paper-Trading als Pflichtstufe vor einem möglichen Live-Betrieb;
- Audit-Log, Metriken, Alerts, Backup und Wiederherstellung.

## Nicht enthalten

- undokumentierte Änderung der vom Eigentümer gelieferten Pine-Formel oder der visuell eingefrorenen UI;
- Ergebnis- oder Gewinnversprechen;
- Futures, Margin, Leverage oder Short-Positionen ohne neue Freigabe;
- Martingale, Grid oder DCA/Pyramiding;
- Social-Trading, Copy-Trading, News-/Sentiment-Handel oder ML-Prognosen;
- Steuerberatung, Rechtsberatung oder automatische Steuererklärung;
- mobile native App; responsive Webdarstellung kann später vorgesehen werden;
- Auszahlung, Einzahlungsverwaltung oder API-Schlüssel mit Auszahlungsrecht.

## Nutzerrollen

| Rolle | Rechte |
|---|---|
| Eigentümer/Admin | Konfiguration freigeben, Paper/Live umschalten, Not-Aus, Berichte exportieren |
| Beobachter | UI, Charts, Ergebnisse und Logs lesen; keine Handelsänderungen |
| Bot-Service | Daten lesen, freigegebene Orders im aktiven Modus senden, Zustand schreiben |

Für eine lokale Einzelbenutzerinstallation können Eigentümer und Beobachter dieselbe Person sein; Rechte und Audit bleiben dennoch getrennt modelliert.

## Betriebsmodi

1. `BACKTEST`: nur historische Simulation, niemals Börsenorders.
2. `PAPER`: 24/7 laufende Binance-Marktdaten und simulierte Orders als Live-Vorbereitung.
3. `LIVE_DISABLED`: Live-Adapter vorhanden, aber Orderversand technisch gesperrt.
4. `LIVE`: echte Orders; nur nach allen Freigabegates und expliziter Aktivierung.

Der sichere Standard nach Installation, Konfigurationsfehler, Restore oder unklarer Börsensynchronisation ist `LIVE_DISABLED`.

## Qualitätsziele

- deterministische Strategieauswertung;
- vollständige Reproduzierbarkeit;
- sichere Defaults;
- keine Doppelorders nach Restart;
- Datenfrische und Datenlücken sichtbar;
- verständliche deutsche UI-Texte;
- Zeitangaben eindeutig mit Zeitzone;
- Konfigurationsänderungen versioniert und auditierbar;
- Betrieb als lokaler Windows-Service mit localhost-Web-UI.
