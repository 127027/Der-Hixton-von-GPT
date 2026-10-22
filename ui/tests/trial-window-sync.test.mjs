import assert from "node:assert/strict";
import {test} from "node:test";
import {harness, mockLive, initializeLivePreparation} from "./dom-harness.mjs";

function armed(mock) {
  Object.assign(mock.state, {state:"TRIAL_WAITING_SIGNAL",credentials:{configured:true},
    trial:{state:"WAITING_SIGNAL"},trial_dispatch_available:false,
    trial_blockers:["50-USDC-Test ist bereits im Zustand WAITING_SIGNAL."]});
}

test("locked and unlocked windows display the same armed trial without another activation",async()=>{
  const mock=mockLive();armed(mock);
  const ui=harness(mock.fetcher),live=initializeLivePreparation(()=>null);
  try {
    await live.refresh();
    const expected=ui.node("live-trial-status").textContent;
    assert.match(expected,/Scharf.*wartet auf ein neues Signal.*noch kein Test-Kauf/);
    assert.match(ui.node("real-trial-status").textContent,/Scharf.*noch kein Test-Kauf/);
    assert.match(ui.node("live-trial-start").textContent,/Test scharf.*wartet auf Signal/);
    assert.equal(ui.node("live-trial-start").getAttribute("aria-pressed"),"true");
    assert.equal(ui.node("live-trial-start").disabled,true);
    assert.match(ui.node("live-trial-start").title,/Bereits freigegeben.*nicht erneut starten/);
    mock.state.authenticated=true;await live.refresh();
    assert.equal(ui.node("live-trial-status").textContent,expected);
    assert.equal(ui.node("live-trial-start").disabled,true);
    assert.equal(mock.calls.some(call=>call.url.endsWith("/trial/start")),false);
  } finally {live.dispose();ui.restore();}
});

test("foreground, restored page and visibility refresh shared state using only GETs",async()=>{
  const mock=mockLive(),ui=harness(mock.fetcher),live=initializeLivePreparation(()=>null);
  try {
    await live.refresh();armed(mock);
    await ui.fireWindow("focus");
    assert.match(ui.node("live-trial-status").textContent,/Scharf/);
    Object.assign(mock.state,{state:"TRIAL_OPEN",trial:{state:"OPEN",symbol:"ADAUSDC"}});
    await ui.fireWindow("pageshow");
    assert.match(ui.node("live-trial-start").textContent,/Test offen/);
    assert.match(ui.node("live-trial-status").textContent,/Kauf bestätigt.*ADAUSDC/);
    mock.state.trial={state:"EXIT_PENDING",symbol:"ADAUSDC",sell:{state:"CREATED"}};
    await ui.fireDocument("visibilitychange");
    assert.match(ui.node("live-trial-status").textContent,/vorbereitet, noch nicht an Binance gesendet/);
    assert.equal(mock.calls.every(call=>call.url==="/api/live/status"),true);
  } finally {live.dispose();ui.restore();}
});

test("hidden tabs do not request a visibility refresh and disposal removes foreground handlers",async()=>{
  const mock=mockLive(),ui=harness(mock.fetcher),live=initializeLivePreparation(()=>null);
  try {
    await live.refresh();const count=mock.calls.length;
    document.visibilityState="hidden";await ui.fireDocument("visibilitychange");
    assert.equal(mock.calls.length,count);
    live.dispose();
    document.visibilityState="visible";
    await ui.fireDocument("visibilitychange");await ui.fireWindow("focus");await ui.fireWindow("pageshow");
    assert.equal(mock.calls.length,count);
  } finally {live.dispose();ui.restore();}
});

test("network failure removes stale armed confirmation from settings and button",async()=>{
  const mock=mockLive();armed(mock);let failed=false;
  const ui=harness((...args)=>failed?Promise.reject(Error("offline")):mock.fetcher(...args));
  const live=initializeLivePreparation(()=>null);
  try {
    await live.refresh();failed=true;await ui.fireWindow("focus");
    assert.match(ui.node("live-trial-status").textContent,/Teststatus unbekannt.*Verbindung zum Bot fehlt/);
    assert.equal(ui.node("live-trial-start").getAttribute("aria-pressed"),"false");
    assert.equal(ui.node("live-trial-start").disabled,true);
    assert.doesNotMatch(ui.node("live-trial-start").textContent,/scharf/);
    assert.match(ui.node("live-trial-start").title,/nicht bestätigt/);
    failed=false;await ui.fireWindow("focus");
    assert.match(ui.node("live-trial-status").textContent,/Scharf/);
  } finally {live.dispose();ui.restore();}
});

test("warmup states an execution block without presenting an armed trial as inactive",async()=>{
  const mock=mockLive();armed(mock);mock.state.trial_order_execution_blocked_by_health=true;
  const ui=harness(mock.fetcher),live=initializeLivePreparation(()=>null);
  try {
    await live.refresh();
    assert.match(ui.node("live-trial-status").textContent,/Scharf.*Warmup.*keine Binance-Order/);
    assert.match(ui.node("live-trial-start").title,/Bereits freigegeben.*Warmup/);
    assert.equal(ui.node("live-trial-start").getAttribute("aria-pressed"),"true");
    mock.state.trial_order_execution_blocked_by_health=false;await ui.fireWindow("focus");
    assert.doesNotMatch(ui.node("live-trial-status").textContent,/Warmup/);
  } finally {live.dispose();ui.restore();}
});

test("state changes clear old local action receipts and do not mark review or completed tests as armed",async()=>{
  const mock=mockLive();armed(mock);
  const ui=harness(mock.fetcher),live=initializeLivePreparation(()=>null);
  try {
    await live.refresh();ui.node("live-trial-result").textContent="1x50-Test scharf";
    mock.state.trial={state:"NEEDS_REVIEW",reason:"ORDER_UNKNOWN",has_unresolved_orders:true};
    await live.refresh();
    assert.equal(ui.node("live-trial-result").textContent,"");
    assert.match(ui.node("live-trial-status").textContent,/Order ungeklärt/);
    assert.equal(ui.node("live-trial-start").getAttribute("aria-pressed"),"false");
    mock.state.trial={state:"COMPLETED"};await live.refresh();
    assert.equal(ui.node("live-trial-start").getAttribute("aria-pressed"),"false");
    assert.equal(ui.node("live-request").disabled,true);
    assert.equal(mock.calls.every(call=>call.url==="/api/live/status"),true);
  } finally {live.dispose();ui.restore();}
});
