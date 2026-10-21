import assert from "node:assert/strict";
import {test} from "node:test";
import {harness, mockLive, initializeLivePreparation, initializeTradingSettings} from "./dom-harness.mjs";

async function unlockUI(ui) {
  ui.node("live-password").value="correct-password-123";
  await ui.node("live-auth-panel").fire("submit");
}

const acceptedTrial = () => ({eligible:true,state:"ACCEPTED",trial_id:"confirmed-trial",accepted_at_utc:"2026-10-21T10:00:00Z",reason:null});

test("durable trial acceptance survives a new UI session without automatically enabling Live",async()=>{
  const mock=mockLive();mock.state.credentials.configured=true;
  mock.state.trial_acceptance=acceptedTrial();
  const ui=harness(mock.fetcher);let live=initializeLivePreparation(()=>null);
  try {
    await live.refresh();
    assert.match(ui.node("live-trial-acceptance").textContent,/bestanden.*dauerhaft gespeichert.*separat einschalten/);
    assert.match(ui.node("live-state").textContent,/Live aus.*keine neuen Echtgeld-Einstiege/);
    assert.equal(ui.node("live-request").disabled,true);
    live.dispose();live=initializeLivePreparation(()=>null);await live.refresh();
    assert.match(ui.node("live-trial-acceptance").textContent,/dauerhaft gespeichert/);
    await unlockUI(ui);
    assert.equal(ui.node("live-request").disabled,true); // Other backend gates still apply.
    mock.state.ready=true;mock.state.order_dispatch_available=true;await live.refresh();
    assert.equal(ui.node("live-request").disabled,false);
    assert.equal(mock.state.state,"LIVE_DISABLED");
    assert.equal(mock.calls.some(c=>/\/(enable|trial\/start)$/.test(c.url)),false);
  } finally {live.dispose();ui.restore();}
});

test("an explicit optional retest warns about replacing eligibility and follows the new server gate",async()=>{
  const mock=mockLive();Object.assign(mock.state,{credentials:{configured:true},trial:{state:"COMPLETED"},
    trial_retest_available:true,trial_dispatch_available:true,trial_acceptance:acceptedTrial(),ready:true,order_dispatch_available:true});
  const ui=harness((url,options)=>{
    if(url.endsWith("/trial/start"))Object.assign(mock.state,{trial_acceptance:{...acceptedTrial(),eligible:false,state:"RETEST_REQUIRED"},ready:false,order_dispatch_available:false});
    return mock.fetcher(url,options);
  });
  const live=initializeLivePreparation(()=>null);
  try {
    await live.refresh();await unlockUI(ui);
    assert.match(ui.node("live-trial-status").textContent,/freiwilliger neuer.*sperrt Live.*erneuten erfolgreichen Abschluss/);
    await ui.node("live-trial-start").fire("click");
    assert.match(ui.node("live-trial-acceptance").textContent,/Neuer 50-USDC-Test noch nicht bestanden.*Live gesperrt/);
    assert.equal(ui.node("live-request").disabled,true);
    assert.equal(mock.calls.filter(c=>c.url.endsWith("/trial/start")).length,1);
    assert.equal(mock.calls.some(c=>c.url.endsWith("/enable")),false);
    Object.assign(mock.state,{trial_acceptance:acceptedTrial(),trial:{state:"COMPLETED"}});await live.refresh();
    assert.match(ui.node("live-trial-acceptance").textContent,/dauerhaft gespeichert/);
    assert.equal(ui.node("live-request").disabled,true); // Acceptance does not override other gates.
  } finally {live.dispose();ui.restore();}
});

test("COMPLETED alone or inconsistent acceptance never produces a saved passing notice",async()=>{
  const mock=mockLive();mock.state.trial={state:"COMPLETED"};
  const ui=harness(mock.fetcher),live=initializeLivePreparation(()=>null);
  try {
    for(const acceptance of [undefined,{...acceptedTrial(),eligible:false},{...acceptedTrial(),eligible:"true"},
      {...acceptedTrial(),state:"NOT_VERIFIED"}]){
      mock.state.trial_acceptance=acceptance;await live.refresh();
      assert.match(ui.node("live-trial-acceptance").textContent,/noch nicht bestätigt/);
      assert.doesNotMatch(ui.node("live-trial-acceptance").textContent,/dauerhaft gespeichert/);
    }
    mock.state.trial_acceptance={...acceptedTrial(),eligible:false,state:"ACCOUNT_MISMATCH"};await live.refresh();
    assert.match(ui.node("live-trial-acceptance").textContent,/passt nicht zum aktuellen Binance-Zugang.*Live gesperrt/);
  } finally {live.dispose();ui.restore();}
});

test("HTTP status failure clears an old passing notice and keeps activation disabled",async()=>{
  const mock=mockLive();mock.state.trial_acceptance=acceptedTrial();let failed=false;
  const ui=harness((...args)=>failed?Promise.resolve({ok:false,status:503,json:async()=>({detail:"unavailable"})}):mock.fetcher(...args));
  const live=initializeLivePreparation(()=>null);
  try {
    await live.refresh();assert.match(ui.node("live-trial-acceptance").textContent,/dauerhaft gespeichert/);
    failed=true;await live.refresh();
    assert.match(ui.node("live-trial-acceptance").textContent,/derzeit nicht bestätigt.*Verbindung zum Bot fehlt/);
    assert.doesNotMatch(ui.node("live-trial-acceptance").textContent,/bestanden|dauerhaft gespeichert/);
    assert.equal(ui.node("live-request").disabled,true);
  } finally {live.dispose();ui.restore();}
});

test("failed Binance diagnosis survives the action refresh and polling until a successful retry",async()=>{
  const mock=mockLive();mock.state.credentials.configured=true;
  let fail=true;
  const failure="Binance-Prüfung: API-Berechtigungen fehlgeschlagen (HTTP 400, Code -2015).";
  const ui=harness((url,options)=>url.endsWith("/check")&&fail
    ? Promise.resolve({ok:false,status:400,json:async()=>({detail:failure})})
    : mock.fetcher(url,options));
  const live=initializeLivePreparation(()=>null);
  try {
    await live.refresh();await unlockUI(ui);
    await ui.node("live-check").fire("click");
    assert.equal(ui.node("live-check-result").textContent,failure);
    await live.refresh();await live.refresh();
    assert.equal(ui.node("live-check-result").textContent,failure);
    assert.equal(ui.node("live-request").disabled,true);
    fail=false;await ui.node("live-check").fire("click");
    assert.match(ui.node("live-check-result").textContent,/bestanden/);
    mock.state.account_check=null;await live.refresh();
    assert.match(ui.node("live-check-result").textContent,/Kein frischer Diagnose-Check/);
    assert.doesNotMatch(ui.node("live-check-result").textContent,/-2015|bestanden/);
    assert.equal(mock.calls.some(c=>/\/(enable|trial\/start)$/.test(c.url)),false);
  } finally {live.dispose();ui.restore();}
});

test("prepared trial exit is distinguished from a submitted sale without enabling Live",async()=>{
  const mock=mockLive();mock.state.credentials.configured=true;
  mock.state.state="TRIAL_EXIT_PENDING";
  mock.state.trial={state:"EXIT_PENDING",symbol:"NEARUSDC",sell:{state:"CREATED"}};
  const ui=harness(mock.fetcher),live=initializeLivePreparation(()=>null);
  try {
    await live.refresh();await unlockUI(ui);
    assert.match(ui.node("real-trial-status").textContent,/vorbereitet, noch nicht an Binance gesendet/);
    assert.match(ui.node("live-check-result").textContent,/bestehende Test wartet auf Verkauf/);
    assert.equal(ui.node("live-request").disabled,true);
    mock.state.trial.sell.state="SUBMITTING";await live.refresh();
    assert.match(ui.node("real-trial-status").textContent,/Order ungeklärt/);
    assert.doesNotMatch(ui.node("real-trial-status").textContent,/noch nicht an Binance gesendet/);
  } finally {live.dispose();ui.restore();}
});

test("ambiguous trial is explicit on locked overview and settings, without another order",async()=>{
  const mock=mockLive();
  mock.state.credentials.configured=true;
  mock.state.state="TRIAL_ENTRY_PENDING";
  mock.state.trial={state:"ENTRY_PENDING",symbol:"SOLUSDC",reason:"ORDER_UNKNOWN",
    has_unresolved_orders:true,buy:{state:"UNKNOWN",exchange_state:null}};
  const ui=harness(mock.fetcher),live=initializeLivePreparation(()=>null);
  try {
    await live.refresh();
    for(const id of ["real-trial-status","position-real-status","live-trial-status"]){
      assert.match(ui.node(id).textContent,/Order ungeklärt/);
      assert.match(ui.node(id).textContent,/Binance-Abgleich nötig/);
    }
    assert.equal(ui.node("live-trial-start").disabled,true);
    assert.equal(ui.node("live-request").disabled,true);
    assert.equal(mock.calls.some(c=>c.url.endsWith("/trial/start")||c.url.endsWith("/enable")),false);
  } finally {live.dispose();ui.restore();}
});

test("password failure is beside the input; successful submit unlocks actual key controls", async()=>{
  const mock=mockLive(), ui=harness(mock.fetcher);
  const live=initializeLivePreparation(()=>null);
  try {
    await live.refresh();
    assert.equal(ui.node("live-protected").disabled,true);
    ui.node("live-password").value="incorrect-password";
    await ui.node("live-auth-panel").fire("submit");
    assert.match(ui.node("live-auth-result").textContent,/nicht korrekt/);
    assert.equal(ui.node("live-protected").disabled,true);
    assert.equal(ui.node("live-password").value,"");
    await unlockUI(ui);
    assert.equal(ui.node("live-protected").disabled,false);
    assert.equal(ui.node("live-save-key").disabled,false);
    assert.equal(ui.node("live-api-key").focused,true);
    assert.equal(ui.node("live-auth-panel").classList.contains("hidden"),true);
    assert.match(ui.node("live-auth-result").textContent,/Entsperrt/);
    ui.node("live-api-key").value="TESTONLY".repeat(8);
    ui.node("live-api-secret").value="NOTAREAL".repeat(8);
    await ui.node("live-key-form").fire("submit");
    assert.equal(mock.state.credentials.configured,true);
    assert.equal(ui.node("live-api-secret").value,"");
    assert.match(ui.node("live-key-result").textContent,/gespeichert/);
    await ui.node("live-check").fire("click");
    assert.match(ui.node("live-check-result").textContent,/bestanden/);
    assert.equal(ui.node("live-request").disabled,true);
    assert.equal(ui.node("live-trial-start").disabled,true);
    assert.equal(mock.state.state,"LIVE_DISABLED");
    await ui.node("live-off").fire("click");
    assert.match(ui.node("live-result").textContent,/Kein Sofortverkauf/);
  } finally {live.dispose();ui.restore();}
});

test("first enrollment, deletion confirmation, lock and session expiry preserve access controls",async()=>{
  const mock=mockLive(); mock.state.password_configured=false;
  const ui=harness(mock.fetcher),live=initializeLivePreparation(()=>null);
  try {
    await live.refresh();
    assert.equal(ui.node("live-password-repeat").required,true);
    ui.node("live-password-repeat").value="correct-password-123";
    await unlockUI(ui);
    assert.equal(ui.node("live-password-repeat").required,false);
    mock.state.credentials.configured=true;
    await ui.node("live-delete-key").fire("click");
    assert.equal(mock.state.credentials.configured,true);
    await ui.node("live-delete-cancel").fire("click");
    assert.equal(mock.state.credentials.configured,true);
    await ui.node("live-delete-key").fire("click");
    await ui.node("live-delete-confirm").fire("click");
    assert.equal(mock.state.credentials.configured,false);
    ui.node("live-api-key").value="unsaved-test-data";
    mock.state.authenticated=false;
    await live.refresh();
    assert.equal(ui.node("live-api-key").value,"");
    assert.equal(ui.node("live-protected").disabled,true);
    assert.match(ui.node("live-auth-result").textContent,/Sitzung abgelaufen/);
    await unlockUI(ui);
    await ui.node("live-lock").fire("click");
    assert.equal(ui.node("live-protected").disabled,true);
    assert.match(ui.node("live-auth-result").textContent,/Zugang gesperrt/);
  } finally {live.dispose();ui.restore();}
});

test("unlock does not claim success when cookie/session verification fails",async()=>{
  const mock=mockLive();mock.rejectCookie();
  const ui=harness(mock.fetcher),live=initializeLivePreparation(()=>null);
  try {
    await live.refresh();await unlockUI(ui);
    assert.match(ui.node("live-auth-result").textContent,/Sitzung nicht bestätigt/);
    assert.equal(ui.node("live-protected").disabled,true);
    assert.equal(ui.node("live-request").disabled,true);
  } finally {live.dispose();ui.restore();}
});

test("server gates keep trial and continuous live controls disabled until explicit readiness",async()=>{
  const mock=mockLive();mock.state.credentials.configured=true;
  const ui=harness(mock.fetcher),live=initializeLivePreparation(()=>null);
  try {
    await live.refresh();await unlockUI(ui);
    assert.equal(ui.node("live-trial-start").disabled,true);
    assert.equal(ui.node("live-request").disabled,true);
    assert.equal(mock.calls.filter(c=>c.url.endsWith("/trial/start")).length,0);
    assert.equal(mock.calls.filter(c=>c.url.endsWith("/enable")).length,0);
  } finally {live.dispose();ui.restore();}
});

test("controlled 1x50 and budget Live send exact explicit confirmations",async()=>{
  const mock=mockLive();mock.state.credentials.configured=true;
  const ui=harness(mock.fetcher),live=initializeLivePreparation(()=>null);
  try {
    await live.refresh();await unlockUI(ui);
    mock.state.trial_dispatch_available=true;await live.refresh();
    assert.equal(ui.node("live-trial-start").disabled,false);
    await ui.node("live-trial-start").fire("click");
    const trial=mock.calls.find(c=>c.url.endsWith("/trial/start"));
    assert.deepEqual(trial.body,{confirmation:"TEST 50 USDC",quote_asset:"USDC",notional_quote:"50.00"});
    assert.match(ui.node("live-trial-result").textContent,/wartet auf ein neues gültiges Signal/);

    mock.state.state="LIVE_DISABLED";
    mock.state.ready=true;
    mock.state.order_dispatch_available=true;
    await live.refresh();
    assert.equal(ui.node("live-request").disabled,false);
    await ui.node("live-request").fire("click");
    const enable=mock.calls.find(c=>c.url.endsWith("/enable"));
    assert.deepEqual(enable.body,{confirmation:"LIVE MAXIMALBUDGET AKTIVIEREN"});
    assert.equal(mock.state.state,"LIVE_ENABLED");
  } finally {live.dispose();ui.restore();}
});

test("live state selection follows server acknowledgement, rejects false green and clears on failure",async()=>{
  const mock=mockLive();mock.state.credentials.configured=true;
  let offline=false;
  const ui=harness((...args)=>{if(offline) throw Error("offline");return mock.fetcher(...args);});
  const live=initializeLivePreparation(()=>null);
  const selected=id=>ui.node(id).getAttribute("aria-pressed");
  try {
    await live.refresh();await unlockUI(ui);
    assert.equal(selected("live-off"),"true");assert.equal(selected("live-request"),"false");
    assert.equal(ui.node("live-request").disabled,true);
    mock.state.state="LIVE_ENABLED";
    mock.state.ready=true;
    mock.state.order_dispatch_available=true;
    await live.refresh(); // Hypothetical confirmed server state, no exchange.
    assert.equal(selected("live-request"),"true");assert.match(ui.node("live-state").textContent,/Live an/);
    await ui.node("live-off").fire("click");
    assert.equal(selected("live-off"),"true");assert.equal(selected("live-request"),"false");
    mock.state.state="EXIT_ONLY";await live.refresh();
    assert.equal(selected("live-off"),"true");assert.match(ui.node("live-state").textContent,/laufen aus/);
    mock.state.state="TRIAL_ENTRY_PENDING";await live.refresh();
    assert.equal(selected("live-off"),"false");assert.equal(selected("live-request"),"false");
    assert.match(ui.node("live-state").textContent,/Einmaltest/);
    offline=true;await live.refresh();
    assert.equal(selected("live-request"),"false");assert.equal(selected("live-off"),"false");
    assert.match(ui.node("live-state").textContent,/unbekannt/);
  } finally {live.dispose();ui.restore();}
});

test("shared entry pause is visible, editable and blocks live until explicitly cleared",async()=>{
  const ui=harness(()=>{});const writes=[];
  const settings=initializeTradingSettings(async value=>{writes.push(value);return value;},()=>{});
  const limits={min_capital_usdc:"100.00",max_capital_usdc:"1000000.00",research_reference_max_usdc:"1000.00",allocator_version:"CAPITAL-V1-2X50PCT"};
  try {
    settings.render({
      max_capital_usdc:"250.00",slot_count:2,target_notional_usdc:"125.00",reserve_usdc:"0.00",
      allocation_policy:"ranked_repeat",allocator_version:"CAPITAL-V1-2X50PCT",emergency_stop:true,
    },limits);
    assert.equal(ui.node("entry-pause-input").checked,true);
    assert.match(settings.liveBlocker(),/Einstiegssperre/);
    ui.node("entry-pause-input").checked=false;
    await ui.node("entry-pause-input").fire("change");
    assert.match(settings.liveBlocker(),/Übernehmen/);
    await ui.node("trading-form").fire("submit");
    assert.equal(writes.at(-1).emergency_stop,false);
    assert.equal(settings.liveBlocker(),null);
  } finally {ui.restore();}
});

test("gap-filler switch saves independently and polling preserves an unsaved change",async()=>{
  const ui=harness(()=>{}), writes=[];
  const controller=initializeTradingSettings(async value=>{writes.push(value);return value;},()=>{});
  const saved={max_capital_usdc:"250",slot_count:2,target_notional_usdc:"125",reserve_usdc:"0",
    allocation_policy:"ranked_repeat",allocator_version:"CAPITAL-V1-2X50PCT",
    emergency_stop:false,gap_fillers_enabled:true};
  const limits={min_capital_usdc:"100",max_capital_usdc:"1000000",allocator_version:saved.allocator_version};
  try {
    controller.render(saved,limits);
    assert.equal(ui.node("gap-fillers-input").checked,true);
    ui.node("gap-fillers-input").checked=false;
    await ui.node("gap-fillers-input").fire("change");
    controller.render(saved,limits);
    assert.equal(ui.node("gap-fillers-input").checked,false);
    await ui.node("trading-form").fire("submit");
    assert.equal(writes.at(-1).gap_fillers_enabled,false);
    assert.equal(writes.at(-1).emergency_stop,false);
    assert.equal(writes.at(-1).max_capital_usdc,"250");
    assert.match(ui.node("settings-saved").textContent,/Zwischenfüller AUS/);
  } finally {ui.restore();}
});

test("250 and 500000 USDC maximum budgets use the single field and derived allocator",async()=>{
  const ui=harness(()=>{});const writes=[];
  const settings=initializeTradingSettings(
    async value=>{writes.push(value);return value;},
    ()=>{},
  );
  const limits={
    min_capital_usdc:"100.00",
    max_capital_usdc:"1000000.00",
    research_reference_max_usdc:"1000.00",
    allocator_version:"CAPITAL-V1-2X50PCT",
  };
  try {
    settings.render({
      max_capital_usdc:"250.00",slot_count:2,target_notional_usdc:"125.00",
      reserve_usdc:"0.00",allocation_policy:"ranked_repeat",
      allocator_version:"CAPITAL-V1-2X50PCT",emergency_stop:false,
    },limits);
    for(const amount of ["250","500000"]) {
      ui.node("capital-input").value=amount;
      await ui.node("capital-input").fire("input");
      await ui.node("trading-form").fire("submit");
      assert.equal(ui.node("settings-validation").textContent,"");
      assert.equal(settings.liveBlocker(),null);
    }
    assert.equal(writes.length,2);
    assert.equal(writes[0].slot_count,2);
    assert.equal(writes[0].target_notional_usdc,"125.00");
    assert.equal(writes[1].target_notional_usdc,"250000.00");
    assert.match(ui.node("live-plan").textContent,/500.000,00 USDC/);
    assert.match(ui.node("live-plan").textContent,/Forschungsreferenz/);
  } finally {ui.restore();}
});

test("one submit derives 2x125, preserves draft across polls and blocks duplicate submits",async()=>{
  const ui=harness(()=>{throw Error("No network expected");});
  let resolveSave, writes=0, accepted;
  const settings=initializeTradingSettings(
    value=>{writes++;return new Promise(resolve=>{resolveSave=()=>resolve(value);});},
    value=>{accepted=value;},
  );
  const original={
    max_capital_usdc:"250.00",slot_count:2,target_notional_usdc:"125.00",
    reserve_usdc:"0.00",allocation_policy:"ranked_repeat",
    allocator_version:"CAPITAL-V1-2X50PCT",emergency_stop:false,
  };
  const limits={
    min_capital_usdc:"100.00",
    max_capital_usdc:"1000000.00",
    research_reference_max_usdc:"1000.00",
    allocator_version:"CAPITAL-V1-2X50PCT",
  };
  try {
    settings.render(original,limits);
    ui.node("capital-input").value="300";
    await ui.node("capital-input").fire("input");
    settings.render(original,limits);
    assert.equal(ui.node("capital-input").value,"300");
    assert.match(ui.node("live-plan").textContent,/2 × 150,00/);
    assert.match(settings.liveBlocker(),/Übernehmen/);
    const submit=ui.node("trading-form").fire("submit");
    assert.equal(ui.node("settings-button").disabled,true);
    await ui.node("trading-form").fire("submit");
    assert.equal(writes,1);resolveSave();await submit;
    assert.equal(accepted.max_capital_usdc,"300");
    assert.equal(accepted.slot_count,2);
    assert.equal(accepted.target_notional_usdc,"150.00");
    assert.match(ui.node("settings-saved").textContent,/Max. 300,00 USDC/);
    assert.equal(settings.liveBlocker(),null);
  } finally {ui.restore();}
});

test("save failure and invalid budget stay visible without reverting the user's value",async()=>{
  const ui=harness(()=>{});
  const settings=initializeTradingSettings(
    async()=>{throw Error("Speichern fehlgeschlagen");},
    ()=>{throw Error("Must not apply");},
  );
  const limits={
    min_capital_usdc:"100.00",
    max_capital_usdc:"1000000.00",
    research_reference_max_usdc:"1000.00",
    allocator_version:"CAPITAL-V1-2X50PCT",
  };
  try {
    settings.render({
      max_capital_usdc:"250.00",slot_count:2,target_notional_usdc:"125.00",
      reserve_usdc:"0.00",allocation_policy:"ranked_repeat",
      allocator_version:"CAPITAL-V1-2X50PCT",emergency_stop:false,
    },limits);
    ui.node("capital-input").value="99";
    await ui.node("capital-input").fire("input");
    await ui.node("trading-form").fire("submit");
    assert.match(ui.node("settings-validation").textContent,/100,00/);
    ui.node("capital-input").value="300";
    await ui.node("capital-input").fire("input");
    await ui.node("trading-form").fire("submit");
    assert.match(ui.node("settings-validation").textContent,/Speichern fehlgeschlagen/);
    assert.equal(ui.node("capital-input").value,"300");
  } finally {ui.restore();}
});

test("double login cannot create competing sessions and status failure locks key access",async()=>{
  const mock=mockLive(); let release, offline=false;
  const ui=harness(async(url,options)=>{
    if(offline) throw Error("Network unavailable");
    if(url.endsWith("/unlock")) await new Promise(resolve=>{release=resolve;});
    return mock.fetcher(url,options);
  });
  const live=initializeLivePreparation(()=>null);
  try {
    await live.refresh();
    ui.node("live-password").value="correct-password-123";
    const first=ui.node("live-auth-panel").fire("submit");
    assert.equal(ui.node("live-unlock").disabled,true);
    await ui.node("live-auth-panel").fire("submit");
    release(); await first;
    assert.equal(mock.calls.filter(c=>c.url.endsWith("/unlock")).length,1);
    ui.node("live-api-secret").value="test-only-unsaved";
    offline=true;await live.refresh();
    assert.equal(ui.node("live-protected").disabled,true);
    assert.equal(ui.node("live-api-secret").value,"");
    assert.match(ui.node("live-auth-result").textContent,/Verbindung zum Bot fehlt/);
    assert.equal(ui.node("live-unlock").disabled,false);
  } finally {live.dispose();ui.restore();}
});

test("unsaved settings block both trading start controls without sending requests",async()=>{
  const mock=mockLive();mock.state.credentials.configured=true;
  mock.state.ready=true;
  mock.state.order_dispatch_available=true;
  mock.state.trial_dispatch_available=true;
  const ui=harness(mock.fetcher),live=initializeLivePreparation(()=>"Zuerst Übernehmen");
  try {
    await live.refresh();await unlockUI(ui);
    await ui.node("live-request").fire("click");
    await ui.node("live-trial-start").fire("click");
    assert.equal(mock.calls.filter(c=>/\/(enable|trial\/start)$/.test(c.url)).length,0);
    assert.match(ui.node("live-result").textContent,/Übernehmen/);
    assert.match(ui.node("live-trial-result").textContent,/Übernehmen/);
  } finally {live.dispose();ui.restore();}
});

test("Binance credential and live readiness cards are visible in settings source",async()=>{
  const source = (await import("node:fs")).readFileSync(new URL("../index.html", import.meta.url), "utf8");
  const binanceCard = source.slice(source.indexOf("<h2>2 · Binance-Zugang"), source.indexOf("<h2>3 · Livehandel"));
  const liveCard = source.slice(source.indexOf("<h2>3 · Livehandel"), source.indexOf("</section>", source.indexOf("<h2>3 · Livehandel")));
  assert.doesNotMatch(binanceCard, /settings-card hidden/);
  assert.doesNotMatch(liveCard, /settings-live-card hidden/);
  assert.match(binanceCard, /Windows-Anmeldedatenspeicher/);
  assert.match(binanceCard, /Auszahlungen, Transfers, Margin, Futures und Optionen: AUS/);
});


test("automatic-budget gate blocks continuous live but permits exactly one explicit 50 trial",async()=>{
  const mock=mockLive();mock.state.credentials.configured=true;mock.state.trial_dispatch_available=true;
  const ui=harness(mock.fetcher);
  const settings=initializeTradingSettings(async value=>value,()=>{});
  const limits={min_capital_usdc:"100.00",max_capital_usdc:"1000000.00",research_reference_max_usdc:"1000.00",allocator_version:"CAPITAL-V1-2X50PCT"};
  const saved={max_capital_usdc:"1100.00",slot_count:2,target_notional_usdc:"550.00",reserve_usdc:"0.00",allocation_policy:"ranked_repeat",allocator_version:"CAPITAL-V1-2X50PCT",emergency_stop:false,auto_budget_enabled:true,auto_budget_live_available:false,autonomous_performance_enabled:true,autonomous_performance_live_available:false,gap_fillers_enabled:true};
  settings.render(saved,limits);
  const live=initializeLivePreparation(mode=>settings.liveBlocker(mode));
  try {
    await live.refresh(); await unlockUI(ui);
    assert.match(settings.liveBlocker(),/Live bleibt/);
    assert.equal(settings.liveBlocker("trial"),null);
    await ui.node("live-trial-start").fire("click");
    assert.equal(mock.calls.filter(c=>c.url.endsWith("/trial/start")).length,1);
    assert.equal(mock.state.trial.state,"WAITING_SIGNAL");
    assert.equal(mock.calls.filter(c=>c.url.endsWith("/enable")).length,0);
    settings.render({...saved,emergency_stop:true},limits);
    assert.match(settings.liveBlocker("trial"),/Einstiegssperre/);
    settings.render(saved,limits);
    await ui.node("capital-input").fire("input");
    assert.match(settings.liveBlocker("trial"),/Übernehmen/);
  } finally {live.dispose();ui.restore();}
});


test("overview distinguishes an armed real trial from an actual buy and disabled live slots",async()=>{
  const mock=mockLive(); mock.state.live={state:"LIVE_DISABLED",used_slots:0,free_slots:2};
  mock.state.trial={state:"WAITING_SIGNAL"};
  const ui=harness(mock.fetcher),live=initializeLivePreparation(()=>null);
  try {
    await live.refresh();
    assert.match(ui.node("real-trial-status").textContent,/Scharf.*noch kein Test-Kauf/);
    assert.equal(ui.node("real-live-slots").textContent,"2");
    assert.match(ui.node("real-live-slots-detail").textContent,/Dauer-Live aus.*Einmaltest separat/);
    mock.state.trial={state:"OPEN",symbol:"ADAUSDC"};await live.refresh();
    assert.match(ui.node("real-trial-status").textContent,/Kauf bestätigt.*ADAUSDC/);
    mock.state.trial={state:"EXIT_PENDING"};await live.refresh();
    assert.match(ui.node("real-trial-status").textContent,/Abschluss noch nicht bestätigt/);
  } finally {live.dispose();ui.restore();}
});


test("automatic mode disables and ignores manual capital; switching back restores remembered maximum",async()=>{
  const ui=harness(()=>{});const writes=[];
  const settings=initializeTradingSettings(async value=>{writes.push(value);return value;},()=>{});
  const limits={min_capital_usdc:"100.00",max_capital_usdc:"1000000.00",research_reference_max_usdc:"1000.00",allocator_version:"CAPITAL-V1-2X50PCT"};
  const saved={max_capital_usdc:"1100.00",slot_count:2,target_notional_usdc:"550.00",reserve_usdc:"0.00",allocation_policy:"ranked_repeat",allocator_version:"CAPITAL-V1-2X50PCT",emergency_stop:false,auto_budget_enabled:true,autonomous_performance_enabled:true};
  try {
    settings.render(saved,limits);
    assert.equal(ui.node("capital-input").disabled,true);
    assert.match(ui.node("budget-mode-help").textContent,/Betrag links ist inaktiv/);
    assert.match(ui.node("settings-saved").textContent,/alle verfügbaren Binance-USDC/);
    assert.doesNotMatch(ui.node("settings-saved").textContent,/1.100|550/);
    ui.node("capital-input").value="999999";
    await ui.node("trading-form").fire("submit");
    assert.equal(writes.at(-1).max_capital_usdc,"1100.00");
    ui.node("auto-budget-input").checked=false;
    await ui.node("auto-budget-input").fire("change");
    assert.equal(ui.node("capital-input").disabled,false);
    assert.equal(ui.node("capital-input").value,"1100");
    ui.node("capital-input").value="1000";
    await ui.node("capital-input").fire("input");
    await ui.node("trading-form").fire("submit");
    assert.equal(writes.at(-1).max_capital_usdc,"1000");
    assert.equal(writes.at(-1).auto_budget_enabled,false);
  } finally {ui.restore();}
});


test("expired test signal is explained without dispatching any order",async()=>{
  const mock=mockLive();mock.state.trial={state:"WAITING_SIGNAL",reason:"ENTRY_WINDOW_EXPIRED"};
  const ui=harness(mock.fetcher),live=initializeLivePreparation(()=>null);
  try {await live.refresh();assert.match(ui.node("live-trial-status").textContent,/90-Sekunden-Fenster/);assert.equal(mock.calls.filter(c=>c.url.endsWith("trial/start")).length,0);}
  finally {live.dispose();ui.restore();}
});


test("weighted live capacity shows three actual positions without inventing three of two slots", async()=>{
  const mock=mockLive();
  mock.state.live={state:"LIVE_ENABLED",used_slots:3,free_slots:0,slot_count:2,
    allocation_capacity_units:20,used_allocation_units:20,open_position_count:3};
  const ui=harness(mock.fetcher), live=initializeLivePreparation(()=>null);
  ui.node("real-live-slots").previousElementSibling={textContent:""};
  try {
    await live.refresh();
    assert.equal(ui.node("real-live-slots").textContent,"0 %");
    assert.match(ui.node("real-live-slots-detail").textContent,/3 normale Live-Positionen/);
    assert.equal(ui.node("real-live-slots").previousElementSibling.textContent,"Freie Dauer-Live-Kapazität");
    mock.state.live.used_allocation_units=15; mock.state.live.open_position_count=2;
    await live.refresh();
    assert.equal(ui.node("real-live-slots").textContent,"25 %");
  } finally {live.dispose();ui.restore();}
});


test("locked weighted status never infers free fractional capacity from legacy slot summary", async()=>{
  const mock=mockLive();
  mock.state.trading_settings={second_tranche_split_dd_pct:"10"};
  mock.state.live={state:"LIVE_ENABLED",used_slots:2,free_slots:0,slot_count:2};
  const ui=harness(mock.fetcher), live=initializeLivePreparation(()=>null);
  try {
    await live.refresh();
    assert.equal(ui.node("real-live-slots").textContent,"—");
    assert.match(ui.node("real-live-slots-detail").textContent,/entsperren/);
    mock.state.live.allocation_capacity_units=20;
    mock.state.live.used_allocation_units=10;
    mock.state.live.open_position_count=2;
    await live.refresh();
    assert.equal(ui.node("real-live-slots").textContent,"50 %");
  } finally {live.dispose();ui.restore();}
});
