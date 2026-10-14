"""Render audited synthetic risk results, not future-profit marketing."""
import csv,gzip,json,xml.etree.ElementTree as E
from pathlib import Path
from collections import Counter
from datetime import datetime,UTC
from decimal import Decimal as D
from dataclasses import asdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from future_scenarios_20261014 import OUT,jobs,START,WARM,candles,SCENARIOS
from hixton.backtest.models import CURRENT_COSTS,ExecutionRules
from hixton.backtest.portfolio import run_shared_portfolio_backtest
from hixton.domain.versions import strategy_definition
from hixton.backtest.reporting import source_fingerprint

def fmt(x,places=2):return f'{float(x):,.{places}f}'.replace(',','X').replace('.',',').replace('X','.')

def path_for(name,budget='1000',variant='current',cost='current',seed=1701,extra=False):
    return OUT/('additions' if extra else 'runs')/(f'{name}-b{budget}-{variant}-{cost}' if extra else f'{name}-s{seed}-b{budget}-{variant}-{cost}')

def load(**kw):return json.loads((path_for(**kw)/'Result.json').read_text())

def curve(path):
    with gzip.open(path/'Equity.csv.gz','rt',encoding='utf-8') as f:return list(csv.DictReader(f))

def timeline():
    strategy=strategy_definition('v8r');rows=[]
    for name in ('common_crash_70','gap_after_exit_90','flash_wick_recovery'):
        data,_=candles(name,1701)
        rules={s:ExecutionRules(step_size=D('.00000001'),min_qty=D('.00000001'),min_notional=D(5)) for s in strategy.symbols}
        result=run_shared_portfolio_backtest(candles_by_symbol=data,report_start_utc=START,report_end_utc=START+__import__('datetime').timedelta(hours=SCENARIOS[name][1]),starting_cash=D(1000),target_notional=D(500),costs=CURRENT_COSTS,execution_rules=rules,strategy=strategy,reinvest_profits=True,autonomous_spot=True)
        expected=load(name=name);assert str(result.metrics.ending_equity)==expected['end_usdc']
        lookup={s.signal_id:s for s in result.signals}
        for fill in result.fills:
            signal=lookup[fill.signal_id]
            assert signal.candle_close_time_utc<fill.fill_time_utc
            rows.append({'scenario':name,'symbol':signal.symbol,'action':fill.action.value,'signal_at_utc':signal.candle_close_time_utc.isoformat(),
                'modeled_fill_at_utc':fill.fill_time_utc.isoformat(),'signal_close_price':signal.close,'executable_open_price':str(fill.reference_open),
                'modeled_execution_price':str(fill.fill_price),'quantity':str(fill.base_quantity),'quote_value':str(fill.quote_value),
                'fee_quote_equivalent':str(fill.fee_quote_equivalent),'no_real_exchange_order':True})
    (OUT/'Event-Timeline.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')

def main():
    base=list((OUT/'runs').rglob('Result.json'));extras=list((OUT/'additions').rglob('Result.json'))
    assert len(base)==len(jobs())==93,(len(base),len(jobs()))
    assert len(extras)==22,len(extras)
    allrows=[json.loads(p.read_text()) for p in base+extras]
    assert all(x['nonnegative_cash_and_inventory'] for x in allrows)
    assert all(len(x['data_hashes'])==15 for x in allrows)
    # Same scenario seed must have identical candles across budgets, cost models and protection variants.
    hashes={}
    for row in allrows:
        key=(row['scenario'],row.get('seed',1701))
        if key in hashes:assert hashes[key]==row['data_hashes']
        else:hashes[key]=row['data_hashes']
    history=json.loads((OUT/'History-Comparison.json').read_text());assert len(history)==8
    tech=json.loads((OUT/'technical-report.json').read_text())
    assert len(tech['scenarios'])==31 and all(x['passed'] for x in tech['scenarios'].values())
    test=E.parse(OUT/'full-regression-final.xml').getroot()[0]
    assert test.attrib['failures']=='0' and test.attrib['errors']=='0'
    timeline()
    long=[r for r in allrows if r['scenario']=='twenty_year_regimes']
    summary={'synthetic_runs_completed':115,'examined_historical_comparison_runs':8,'technical_cases_passed':31,
        'regression':dict(test.attrib),'synthetic_market_cases':16,'synthetic_not_prediction':True,
        'risk_30pct_cap_exists':False,'baseline_commit':'b15e6775ea11e13e225481aada3d56468ae5c67b',
        'baseline_source':'f34ced870a598442e722a556917035923c461263d45d0305865a97c11cadec58',
        'prepared_fix_source':source_fingerprint(),'prepared_fix_installed_in_running_bot':False,
        'long_range_closed_dd_pct':[min(float(x['close_dd_pct']) for x in long),max(float(x['close_dd_pct']) for x in long)],
        'long_end_capital_not_validated_for_liquidity':True,
        'counts_trades_field_means_realized_exit_lots_including_partial_trims':True,
        'intrabar_value_means_assumed_synchronous_low_versus_previous_closed_peak_not_actual_binance_fill':True}
    (OUT/'Summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    fields=('scenario','budget','variant','cost','end_usdc','close_dd_pct','synchronous_low_dd_vs_previous_closed_peak_pct','trades')
    with (OUT/'Vergleich.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter=';');w.writerow(fields)
        for r in allrows:w.writerow([r['cost']['name'] if k=='cost' else r.get(k) for k in fields])
    plot(long)
    text=f'''# Hixton: erfundene Extremszenarien und 20-Jahres-Pfade

Prüfung vom 14.10.2026. **Keine Prognose, keine Wahrscheinlichkeit und keine echte Order.**
Aktuell installierter Vertrag: HIXTON-V8-LINK8-ATR075-DOGE50-DD10-ETH8-DIV32-PAPER-5.
Baseline-Commit: `b15e677`; ursprünglicher Quellhash `{summary['baseline_source']}`.
Nur der isolierte Live-BUY-Sicherheitscheck wurde verbessert; der Markt-/Paper-/Backtest-Algorithmus blieb unverändert.
Vorbereiteter neuer Quellhash: `{summary['prepared_fix_source']}`. **Nicht im laufenden Bot installiert.**

## Wesentliche Antwort

**Der aktuelle Bot besitzt keine harte 30-%-Drawdown-Grenze. Diese Sicherheit kann ich nicht bestätigen.**
Die 30,50 % waren das Ergebnis einer bestimmten vergangenen Historie. Die Risikofunktion erzeugt
auch bei 75 oder 100 % DD keinen permanenten Halt. Die 5-%-UTC-Tagespause blockiert neue Einstiege,
verkauft jedoch keine bestehenden Positionen und wird am nächsten Tag neu bewertet.
Stops und reguläre Ausstiege sehen vollständig geschlossene 1h-Kerzen; danach wird ausgeführt.
Ein Crash innerhalb der Stunde oder vor dem nächsten ausführbaren Zeitpunkt kann diese Schwellen weit überschreiten.

## Durchführung

115 synthetische Portfolio-Läufe über 16 Marktfall-Typen, darunter sechs vollständige 20-Jahres-Läufe
von 01.01.2027 bis 01.01.2047 mit drei festen Zufallsseeds und jeweils normalen/erhöhten Kosten.
Alle 15 Märkte erhalten gültige synchronisierte 1h-OHLC mit 400 Warm-up-Stunden. Research-only-Coins
bleiben von der normalen Kapitalzuteilung ausgeschlossen. Normale und alternative Läufe benutzen nachweislich
identische Kerzen. Endliche Kandidaten: originale Strategie, 75 % oder 50 % Neueinstiegsvolumen und
eine zusätzliche Einstiegspause ab 20 % geschlossenem DD. Keine davon wurde live freigegeben.

Anfangskapital gewöhnlich 1.000 USDC; 35.000 USDC testet eine bereits aktive Dreieraufteilung.
Kosten je Seite: normal 10 bp Gebühren + 2 bp Spread + 3 bp Slippage; Stress 10 + 10 + 20 bp.
Illiquiditätsfall: 10 bp Gebühren + 100 bp Spread + 400 bp Slippage. Diese Kosten sind Annahmen,
keine echten Binance-Fills. Hypothetische Filtersätze: Mengenschritt/Minimum 0,00000001 und 5 USDC Mindestwert.
Es wird kein historisches Orderbuch nachgebaut und keine Wahrscheinlichkeit dieser Szenarien behauptet.

Der erste Einzelcoin-Test traf BTC, obwohl BTC nicht gehalten war. Das wurde erkannt und **nicht als Schutzbeweis gewertet**.
Ein eigener zusätzlicher Fall erzeugt vor dem Crash ausschließlich ein gültiges BTC-Signal und bestätigt BTC-Besitz.
Die Ergänzungen und Forschungsregeln sind separat dokumentiert; die Ausgangshistorie ist mehrfach untersucht,
kein unberührter Holdout. Die Änderungen sind adversariale Tests, keine Optimierung auf einen behaupteten Zukunftsgewinn.

## Beobachtetes Risiko, normale Kosten

Maximaler DD bedeutet Verlust vom jeweiligen vorherigen Höchststand, nicht automatisch Verlust vom Anfangskapital.

| Belastung | Start-USDC | End-USDC im Modell | Max. Schlusskurs-DD |
|---|---:|---:|---:|
'''
    table=[('Gemeinsamer Kurssturz 35 %','common_crash_35','1000',False),('Gemeinsamer Kurssturz 70 %','common_crash_70','1000',False),('90-%-Gap nach dem Verkaufssignal','gap_after_exit_90','1000',False),('Gehaltener BTC verliert 99 %','owned_coin_99','1000',True),('BTC-Kollaps mit Dreierbudget und Rest-Cash','owned_coin_99','35000',True),('Drei tatsächlich gehaltene Coins fallen gemeinsam','all_three_correlated','35000',False),('Langsame zweijährige Baisse','slow_crypto_winter','1000',False),('Wiederholte Pump-/Crash-Verlustserie, fünf Jahre','chronic_chop_no_initial_rally','1000',True),('Crash mit extremen Ausführungskosten','illiquid_crash','1000',False)]
    for label,name,budget,extra in table:
        r=load(name=name,budget=budget,extra=extra,cost='illiquid' if name=='illiquid_crash' else 'current')
        text+=f"| {label} | {fmt(budget)} | {fmt(r['end_usdc'])} | {fmt(r['close_dd_pct'])} % |\n"
    flash=load(name='flash_wick_recovery')
    text+=f'''
Beim Flash-Dip fällt der modellierte gemeinsame Zwischenwert um **{fmt(flash['synchronous_low_dd_vs_previous_closed_peak_pct'])} %**
gegen den vorherigen Schlusskurs-Höchststand, während der gesamte Lauf nur **{fmt(flash['close_dd_pct'])} % Schlusskurs-DD** ausweist.
Der Kurs erholt sich bis zum Stundenschluss; der aktuelle Bot behauptet keinen Intrabar-Stop und verkauft deshalb in diesem Fall nicht.
Der Zwischenwert ist der ausdrücklich erfundene gleichzeitige Tiefstkurs, keine Binance-Ausführung und kein vollständiger Intrabar-Hoch-Tief-DD.

Die sechs 20-Jahres-Läufe erzeugen **{fmt(summary['long_range_closed_dd_pct'][0])} bis {fmt(summary['long_range_closed_dd_pct'][1])} % DD**.
Ihre extrem großen rechnerischen Endkapitalwerte sind **wirtschaftlich nicht validiert**: das Modell reinvestiert ohne
Markttiefen-/Markteinflussmodell bei fest erfundenem Stundenvolumen. Sie stehen in den Rohdaten zur Reproduzierbarkeit,
werden aber weder als realistisches Vermögensziel noch als Gewinnprognose gewertet.

## Was mögliche Schutzänderungen kosten

Die 20-%-Einstiegspause senkt im erfundenen Dauerverlustfall den DD von rund 99,82 % auf 23,13 %
und erhält rund 856 statt 2 USDC. Nach Verlust und vollständigem Verkauf kann sie ohne zusätzliche
manuelle Freigabe dauerhaft in Cash bleiben, weil Cash allein den früheren Höchststand nicht zurückgewinnt.
Bestehende Positionen verlassen weiterhin nach ihrer regulären Strategie; es ist keine Zwangsliquidation.
Beim gemeinsamen 70-%-Gap bleibt selbst diese Pause bei ungefähr 71 % DD. Sie ist kein hartes Verlustlimit.
Eine halbe Neueinstiegsgröße bedeutet zudem keine dauerhaft halbe Exposition: eine offene Gewinnerposition
kann wachsen und später einen großen Anteil der Equity ausmachen. Deshalb war im Einzelcoin-Crash selbst
die 50-%-Variante noch bei etwa 77,61 % DD; dauerhafte Konzentrationsgrenzen würden zusätzliche Rebalancierung benötigen.

Gleicher bereits untersuchter Drei-Jahres-Datensatz wie zuvor; Anfangskapital laut lokalem History-Contract.json:

| Forschungsregel | End-USDC normal | DD normal | End-USDC Stress | DD Stress |
|---|---:|---:|---:|---:|
'''
    for variant in ('current','exposure75','exposure50','entry_pause20'):
        a=next(r for r in history if r['variant']==variant and r['cost']['name']=='current');b=next(r for r in history if r['variant']==variant and r['cost']['name']=='stress')
        text+=f"| {variant} | {fmt(a['end_usdc'])} | {fmt(a['close_dd_pct'])} % | {fmt(b['end_usdc'])} | {fmt(b['close_dd_pct'])} % |\n"
    text+='''
Keine dieser Varianten liefert gleichzeitig den bisherigen Ertrag und eine garantierte Verlustgrenze.
Ich habe deshalb keine Marktstrategie allein aufgrund erfundener Szenarien in den Echtgeldbot übernommen.

## Technische Fehler und Abnahme

Ein neuer vorgemerkter normaler Live-BUY konnte zuvor bei nachträglich gestörter Laufzeit ausgeführt werden.
Vier weitere reproduzierte ungültige Zustände betrafen unzulässige OHLC, nicht handelbare Punkte,
falsche Strategiebindung und inzwischen veraltete vollständige Marktdaten.
Die vorbereitete Korrektur prüft unmittelbar vor einem **neuen** Kauf gesunde Laufzeit und vollständig
gültige, abgeschlossene, handelbare, gleichzeitige Daten der aktuellen Strategie zur gespeicherten Signalzeit.
Der 90-Sekunden-Ablauf bleibt erhalten. Bereits gesendete unklare Orders werden weiter abgefragt;
bereits gültig vorgemerkte eigene SELLs behalten Konto-/Eigentums-/Freigabeprüfungen und können weiterlaufen.

31 erfundene technische Fälle bestanden: fehlende/veraltete Daten, API-/Kontofehler, verlorene Antwort,
Neustart ohne Doppelorder, verzögerter Ausstieg, abgelehnte oder teilweise Verkäufe und Gebührenstaub.
Ein teilweise ausgeführter normaler SELL kann NEEDS_REVIEW erfordern; keine automatische vollständige Bereinigung behauptet.
Schlechter globaler Zustand oder ein fehlender unbeteiligter Markt kann weiterhin die **Erzeugung eines neuen Ausstiegssignals** blockieren.
Der BUY-Patch beseitigt diese separate Architekturabhängigkeit nicht. Während Prozess-/API-Ausfall gibt es keine garantierte Ausführung.

Gesamtregression der vorbereiteten Korrektur: **650 bestanden, zwei übersprungen, keine Fehler**.
Unabhängige lokale Quellprüfung vorhanden, keine formale GitHub-Swarm-Cloudzertifizierung.
Crash, Flash-Dip und gemeinsamer Dreicoin-Crash stimmen zusätzlich zwischen tatsächlichem Paper-Engine-Replay
und Backtester in Equity, Fillanzahl und allen gespeicherten Stundenreferenzen überein; Restart erzeugt keine Duplikate.
Beim Anhängen/Ändern künftiger Kerzen bleiben alle ersten 750 Stunden und ihre Käufe identisch: kein Vorwissen im geprüften Präfix.
Das Rohfeld `trades` zählt realisierte Ausgangslose einschließlich Teilverkäufen, nicht zwingend vollständig geschlossene Positionszyklen.

## Offene Prioritäten

1. Geprüften BUY-Fehler bei einer eigenen Aktualisierung übernehmen. Ein Quellwechsel bindet den 50-USDC-Test neu;
   der laufende Bot wurde deshalb in dieser Offlineprüfung nicht gepatcht, neu gestartet oder freigegeben.
2. Ausstiegsmöglichkeiten von unbeteiligten Marktausfällen entkoppeln, ohne Quellen-, Eigentums-, Konto- und Orderprüfungen zu entfernen.
3. Explizit festlegen, wie viel dauerhafter Kapitalverlust toleriert wird und wann eine Portfoliobremse freigegeben werden darf.
   Der Performanceverlust dieser Regel muss bewusst akzeptiert und erneut getestet werden.
4. Börsenseitige Schutzorders als eigenen Ausführungsumbau prüfen; Gaps, fehlende Käufer, Handelsstopps und Plattformausfall bleiben Grenzen.
5. USDC-Depeg und Plattformrisiko getrennt betrachten: 1.000 USDC können bei USDC/USD=0,8 nur 800 USD wert sein,
   obwohl ein reines USDC-Konto keinen Stückzahlverlust anzeigt. Eine völlige Plattform-/Asset-Ausfallannahme kann bis Totalverlust gehen.
   Diese Umrechnung ist eine Annahme, kein Markt-Backtest und keine automatische Erkennungsfunktion.

Keine Newsregel oder weitere Renditeoptimierung wurde als Ersatz für diese konkreten Lücken eingebaut.
Diese künstlichen Fälle können Lücken finden; sie gewährleisten keinen unbeaufsichtigten Betrieb über zwanzig Jahre.

## Nachweise und Quellen

- [Alle Ergebnisse als CSV](Vergleich.csv), Contract.json und Additions-Contract.json: Szenarien/Seeds/Annahmen.
- [Technischer Prüfbericht](technical-report.json), Originalfehlerberichte und independent-review.json.
- [Paper-Parität](Synthetic-Paper-Parity.json), [Kausalitätsprüfung](Causality.json), [Signal-/Fill-Timeline](Event-Timeline.json).
- [Historischer Variantenvergleich](History-Comparison.json), Rohkurven/Positionslose unter runs und additions.
- [Binance Spot API: Ordertypen und Ausführung](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md):
  Market-Menge/Kurs hängen von verfügbarer Liquidität ab; die lokale Modellfüllung ist kein Börsenversprechen.
- [Binance Spot Glossar](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/spot_glossary.md):
  Handelszustände und Orderbegriffe; ein API-Prozess kann eine Handelssperre nicht umgehen.
- [CFTC zu hypothetischen Handelsmodellen](https://www.cftc.gov/LearnAndProtect/AdvisoriesAndArticles/fraudadv_tradingsystem.html):
  Modellrenditen sind kein Beleg echter Ausführungen oder künftiger Gewinne.
'''
    (OUT/'Bericht.md').write_text(text,encoding='utf-8')
    print(json.dumps(summary,indent=2))

def plot(long):
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,2,figsize=(12,4.2),layout='constrained')
    for variant,color,label in [('current','#dc2626','Aktuell'),('entry_pause20','#059669','Einstiegspause ab 20 % DD')]:
        vals=curve(path_for('chronic_chop_no_initial_rally',variant=variant,extra=True))
        cut=24*90;axes[0].plot([i/24 for i in range(min(cut,len(vals)))],[float(v['equity']) for v in vals[:cut]],color=color,label=label)
    axes[0].set(title='Erfundene Verlustserie: erste 90 Tage',xlabel='Tage',ylabel='Simulierte Equity (Start 1.000 USDC)');axes[0].legend(fontsize=8);axes[0].grid(alpha=.2)
    for r in long:
        vals=curve(path_for('twenty_year_regimes',cost=r['cost']['name'],seed=r['seed']));peak=1000;ys=[]
        for v in vals:
            equity=float(v['equity']);peak=max(peak,equity);ys.append((1-equity/peak)*100)
        step=24
        label='Normale Kosten' if r['seed']==1701 and r['cost']['name']=='current' else 'Erhöhte Kosten' if r['seed']==1701 else None
        axes[1].plot([i/8766 for i in range(0,len(vals),step)],ys[::step],alpha=.55,lw=.8,color='#2563eb' if r['cost']['name']=='current' else '#f97316',label=label)
    axes[1].axhline(30,color='#111827',ls='--',label='30 % Vergleichslinie, kein Bot-Limit');axes[1].set(title='Sechs erfundene 20-Jahres-Pfade',xlabel='Erfundene Jahre',ylabel='Schlusskurs-Drawdown (%)',ylim=(0,100));axes[1].legend(fontsize=7);axes[1].grid(alpha=.2)
    fig.suptitle('Stresstests des aktuellen Hixton — künstliche Daten, keine Prognose',fontsize=12)
    fig.savefig(OUT/'Stressvergleich.png',dpi=170);plt.close(fig)

if __name__=='__main__':main()
