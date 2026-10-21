import assert from "node:assert/strict";
import {test} from "node:test";
import {readFileSync} from "node:fs";
import {harness,initializeNotifications} from "./dom-harness.mjs";

function backend() {
  const state={authenticated:true,configured:false,enabled:false,recipient:"",secret_configured:false,pending:0,last_sent_at:null,last_error:null};
  const calls=[];let failSave=false;
  const fetcher=async(url,options={})=>{
    const body=JSON.parse(options.body??"{}");calls.push({url,options,body});
    const reply=(status,data)=>({ok:status<400,status,json:async()=>structuredClone(data)});
    if(options.method!=="POST")return reply(200,state.authenticated?state:{authenticated:false,configured:state.configured,enabled:state.enabled});
    if(!state.authenticated)return reply(401,{detail:"Sitzung fehlt."});
    if(url.endsWith("/discover"))return reply(200,{chats:[{id:"123456789",label:"Mein Chat"}]});
    if(url.endsWith("/test"))return reply(200,{accepted:true});
    if(url.endsWith("/delete")){Object.assign(state,{configured:false,enabled:false,recipient:"",secret_configured:false});return reply(200,state);}
    if(failSave)return reply(400,{detail:"Chat-ID ungültig."});
    Object.assign(state,{configured:true,enabled:body.enabled,recipient:body.recipient,secret_configured:true});return reply(200,state);
  };
  return {state,calls,fetcher,failSave(){failSave=true;}};
}

test("contact save is explicit, sends no message and polling preserves unsaved input",async()=>{
  const mock=backend(),ui=harness(mock.fetcher),controller=initializeNotifications();
  try {
    await controller.refresh();
    assert.equal(ui.node("notification-enabled").checked,false);
    ui.node("notification-recipient").value="123456789";await ui.node("notification-recipient").fire("input");
    ui.node("notification-secret").value="test-only-token";await ui.node("notification-secret").fire("input");
    ui.node("notification-enabled").checked=true;await ui.node("notification-enabled").fire("change");
    await controller.refresh();
    assert.equal(ui.node("notification-recipient").value,"123456789");
    assert.equal(ui.node("notification-secret").value,"test-only-token");
    assert.equal(ui.node("notification-enabled").checked,true);
    await ui.node("notification-form").fire("submit");
    const save=mock.calls.find(c=>c.options.method==="POST");
    assert.deepEqual(save.body,{channel:"telegram",enabled:true,recipient:"123456789",secret:"test-only-token"});
    assert.equal(save.options.headers["X-Hixton-Action"],"local-ui-v1");
    assert.equal(save.options.credentials,"same-origin");
    assert.equal(ui.node("notification-secret").value,"");
    assert.match(ui.node("notification-feedback").textContent,/keine Nachricht versendet/);
    assert.equal(mock.calls.filter(c=>c.url.endsWith("/test")).length,0);
    await ui.node("notification-test").fire("click");
    assert.equal(mock.calls.filter(c=>c.url.endsWith("/test")).length,1);
    assert.match(ui.node("notification-feedback").textContent,/vom Versanddienst angenommen/);
    assert.doesNotMatch(ui.node("notification-feedback").textContent,/erfolgreich zugestellt/);
  } finally {controller.dispose();ui.restore();}
});

test("empty token keeps a stored secret and unsaved changes cannot send a stale test",async()=>{
  const mock=backend();Object.assign(mock.state,{configured:true,recipient:"123456789",secret_configured:true});
  const ui=harness(mock.fetcher),controller=initializeNotifications();
  try {
    await controller.refresh();
    ui.node("notification-recipient").value="987654321";await ui.node("notification-recipient").fire("input");
    await ui.node("notification-test").fire("click");
    assert.equal(mock.calls.some(c=>c.url.endsWith("/test")),false);
    assert.match(ui.node("notification-feedback").textContent,/zuerst speichern/);
    await ui.node("notification-form").fire("submit");
    assert.equal(mock.calls.find(c=>c.options.method==="POST").body.secret,"");
  } finally {controller.dispose();ui.restore();}
});

test("a successful HTTP response alone never proves test message acceptance",async()=>{
  const mock=backend();Object.assign(mock.state,{configured:true,recipient:"123456789",secret_configured:true});
  const ui=harness((url,options)=>url.endsWith("/test")
    ? Promise.resolve({ok:true,status:200,json:async()=>({accepted:false})})
    : mock.fetcher(url,options));
  const controller=initializeNotifications();
  try {
    await controller.refresh();await ui.node("notification-test").fire("click");
    assert.match(ui.node("notification-feedback").textContent,/Versandannahme nicht bestätigt/);
    assert.doesNotMatch(ui.node("notification-feedback").textContent,/vom Versanddienst angenommen/);
  } finally {controller.dispose();ui.restore();}
});

test("token clears on failed save, immediate lock, session expiry and pagehide",async()=>{
  const mock=backend(),ui=harness(mock.fetcher),controller=initializeNotifications();
  try {
    await controller.refresh();mock.failSave();
    ui.node("notification-secret").value="never-persist";await ui.node("notification-secret").fire("input");
    await ui.node("notification-form").fire("submit");
    assert.equal(ui.node("notification-secret").value,"");
    assert.match(ui.node("notification-feedback").textContent,/Chat-ID ungültig/);
    ui.node("notification-secret").value="before-lock";await ui.node("live-lock").fire("click");
    assert.equal(ui.node("notification-secret").value,"");
    assert.equal(ui.node("notification-protected").disabled,true);
    await controller.refresh();ui.node("notification-secret").value="before-expiry";
    mock.state.authenticated=false;await controller.refresh();
    assert.equal(ui.node("notification-secret").value,"");
    assert.equal(ui.node("notification-protected").disabled,true);
    ui.node("notification-secret").value="before-pagehide";await ui.fireWindow("pagehide");
    assert.equal(ui.node("notification-secret").value,"");
  } finally {controller.dispose();ui.restore();}
});

test("discover only reads chats and selecting one still requires explicit save",async()=>{
  const mock=backend(),ui=harness(mock.fetcher),controller=initializeNotifications();
  try {
    await controller.refresh();ui.node("notification-secret").value="test-only-token";
    await ui.node("notification-discover").fire("click");
    assert.deepEqual(mock.calls.find(c=>c.url.endsWith("/discover")).body,{secret:"test-only-token"});
    assert.equal(ui.node("notification-recipient").value,"");
    assert.equal(ui.node("notification-chat-choice").children[1].value,"123456789");
    ui.node("notification-chat-choice").value="123456789";await ui.node("notification-chat-choice").fire("change");
    assert.equal(ui.node("notification-recipient").value,"123456789");
    assert.equal(mock.state.configured,false);
    assert.equal(mock.calls.filter(c=>c.options.method==="POST").length,1);
    assert.match(ui.node("notification-edit-state").textContent,/noch nicht gespeichert/);
  } finally {controller.dispose();ui.restore();}
});

test("locked contact cannot save or send, and explicit deletion removes only notification config",async()=>{
  const mock=backend();mock.state.authenticated=false;
  const ui=harness(mock.fetcher),controller=initializeNotifications();
  try {
    await controller.refresh();await ui.node("notification-form").fire("submit");await ui.node("notification-test").fire("click");
    assert.equal(mock.calls.some(c=>c.options.method==="POST"),false);
    Object.assign(mock.state,{authenticated:true,configured:true,recipient:"123456789"});await controller.refresh();
    await ui.node("notification-delete").fire("click");
    assert.equal(mock.calls.filter(c=>c.url.endsWith("/delete")).length,1);
    assert.equal(mock.state.configured,false);
    assert.match(ui.node("notification-feedback").textContent,/Handelszustand bleibt unverändert/);
    assert.equal(mock.calls.some(c=>/trial|enable|credentials/.test(c.url)),false);
  } finally {controller.dispose();ui.restore();}
});

test("contact help and form describe only Telegram and never persist browser secrets",()=>{
  const html=readFileSync(new URL("../index.html",import.meta.url),"utf8");
  const contact=html.slice(html.indexOf('<article class="settings-card notification-card">'),html.indexOf('<article class="settings-card settings-live-card">'));
  assert.match(contact,/BotFather/);assert.match(contact,/\/start/);assert.match(contact,/keine Telefonnummer/);
  assert.match(contact,/Paper sendet keine Handelsmeldungen/);assert.match(contact,/Bestätigten|bestätigten/);
  assert.match(contact,/type="password"[^>]*autocomplete="off"/);
  const source=readFileSync(new URL("../src/notifications.ts",import.meta.url),"utf8");
  assert.doesNotMatch(source,/localStorage|sessionStorage|\/api\/live\/enable|\/trial\/start/);
});

for (const revoke of ["lock","expiry"]) {
  test(`late chat discovery after ${revoke} cannot reveal chat identities`,async()=>{
    const mock=backend();let release;
    const ui=harness((url,options={})=>url.endsWith("/discover")
      ? new Promise(resolve=>{release=resolve;}) : mock.fetcher(url,options));
    const controller=initializeNotifications();
    try {
      await controller.refresh();
      ui.node("notification-secret").value="test-token";
      ui.node("notification-recipient").value="private-draft";await ui.node("notification-recipient").fire("input");
      const pending=ui.node("notification-discover").fire("click");
      assert.equal(typeof release,"function");
      mock.state.authenticated=false;
      if(revoke==="lock")await ui.node("live-lock").fire("click");else await controller.refresh();
      release({ok:true,status:200,json:async()=>({chats:[{id:"123456789",label:"Private name"}]})});
      await pending;
      assert.equal(ui.node("notification-chat-choice").children.length,0);
      assert.equal(ui.node("notification-chat-choice-wrap").classList.contains("hidden"),true);
      assert.equal(ui.node("notification-recipient").value,"");
      assert.equal(ui.node("notification-secret").value,"");
      assert.equal(ui.node("notification-protected").disabled,true);
      assert.doesNotMatch(ui.node("notification-feedback").textContent,/Chats gefunden|Private name|123456789/);
    } finally {controller.dispose();ui.restore();}
  });
}

test("late save acknowledgement after locking never reports success or reopens private fields",async()=>{
  const mock=backend();let release;
  const ui=harness((url,options={})=>options.method==="POST"&&url.endsWith("/notifications")
    ? new Promise(resolve=>{release=resolve;}) : mock.fetcher(url,options));
  const controller=initializeNotifications();
  try {
    await controller.refresh();
    ui.node("notification-secret").value="test-token";ui.node("notification-recipient").value="123456789";
    await ui.node("notification-recipient").fire("input");
    const pending=ui.node("notification-form").fire("submit");
    mock.state.authenticated=false;await ui.node("live-lock").fire("click");
    release({ok:true,status:200,json:async()=>({authenticated:true,configured:true,recipient:"123456789",enabled:true})});
    await pending;
    assert.doesNotMatch(ui.node("notification-feedback").textContent,/Kontakt gespeichert/);
    assert.equal(ui.node("notification-recipient").value,"");
    assert.equal(ui.node("notification-secret").value,"");
    assert.equal(ui.node("notification-protected").disabled,true);
  } finally {controller.dispose();ui.restore();}
});

test("a GET begun before an action cannot overwrite the saved contact afterward",async()=>{
  const mock=backend();let hold=false,release;
  const ui=harness((url,options={})=>hold&&options.method!=="POST"
    ? (hold=false,new Promise(resolve=>{release=resolve;})) : mock.fetcher(url,options));
  const controller=initializeNotifications();
  try {
    await controller.refresh();hold=true;
    const oldPoll=controller.refresh();
    ui.node("notification-recipient").value="987654321";await ui.node("notification-recipient").fire("input");
    ui.node("notification-secret").value="test-token";
    await ui.node("notification-form").fire("submit");
    release({ok:true,status:200,json:async()=>({authenticated:true,configured:true,recipient:"old-private-id",enabled:false})});
    await oldPoll;
    assert.equal(ui.node("notification-recipient").value,"987654321");
    assert.match(ui.node("notification-feedback").textContent,/Kontakt gespeichert/);
  } finally {controller.dispose();ui.restore();}
});

test("a GET begun before locking cannot restore private contact state",async()=>{
  const mock=backend();Object.assign(mock.state,{configured:true,recipient:"123456789"});
  let hold=false,release;
  const ui=harness((url,options={})=>hold&&options.method!=="POST"
    ? new Promise(resolve=>{release=resolve;}) : mock.fetcher(url,options));
  const controller=initializeNotifications();
  try {
    await controller.refresh();hold=true;
    const oldPoll=controller.refresh();
    await ui.node("live-lock").fire("click");
    release({ok:true,status:200,json:async()=>({authenticated:true,configured:true,recipient:"123456789",enabled:true})});
    await oldPoll;
    assert.equal(ui.node("notification-recipient").value,"");
    assert.equal(ui.node("notification-protected").disabled,true);
  } finally {controller.dispose();ui.restore();}
});
