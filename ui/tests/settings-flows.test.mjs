import assert from "node:assert/strict";
import {test} from "node:test";
import {harness, mockLive, initializeLivePreparation, initializeTradingSettings} from "./dom-harness.mjs";

async function unlockUI(ui) {
  ui.node("live-password").value="correct-password-123";
  await ui.node("live-auth-panel").fire("submit");
}

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
