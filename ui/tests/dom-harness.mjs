// Isolated DOM/event harness: executes production controllers, never a browser/account.
import {readFileSync} from "node:fs";
import ts from "typescript";

const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
function moduleUrl(name) {
  let source = readFileSync(new URL(`../src/${name}.ts`, import.meta.url), "utf8");
  source = source.replace(/from "\.\/settings-draft"/g, `from "${name === "settings-draft" ? "" : moduleUrl("settings-draft")}"`);
  const compiled = ts.transpileModule(source, {compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText;
  return `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`;
}
export const {initializeLivePreparation} = await import(moduleUrl("live-preparation"));
export const {initializeTradingSettings} = await import(moduleUrl("trading-settings"));

class Element {
  value = ""; checked = false; disabled = false; required = false; textContent = "";
  children = []; listeners = new Map(); classes = new Set(); focused = false;
  attributes = new Map();
  setAttribute(name, value) { this.attributes.set(name, value); }
  getAttribute(name) { return this.attributes.get(name); }
  classList = {
    add: (x) => this.classes.add(x), remove: (x) => this.classes.delete(x),
    contains: (x) => this.classes.has(x),
    toggle: (x, force) => force ? this.classes.add(x) : this.classes.delete(x),
  };
  addEventListener(event, callback) { this.listeners.set(event, [...(this.listeners.get(event) ?? []), callback]); }
  async fire(event) { await Promise.all((this.listeners.get(event) ?? []).map(fn => fn({preventDefault(){}}))); }
  focus() { this.focused = true; }
  reportValidity() { return true; } // Controller/server validation is tested explicitly.
  replaceChildren() { this.children = []; }
  append(child) { this.children.push(child); }
}

export function harness(fetcher) {
  const previous = {document:globalThis.document, window:globalThis.window, fetch:globalThis.fetch};
  const nodes = new Map();
  for (const match of html.matchAll(/<[^>]+\bid="([^"]+)"[^>]*>/g)) {
    const node = new Element();
    node.value = match[0].match(/\bvalue="([^"]*)"/)?.[1] ?? "";
    node.disabled = /\bdisabled\b/.test(match[0]);
    for (const name of (match[0].match(/class="([^"]*)"/)?.[1] ?? "").split(" ")) node.classes.add(name);
    nodes.set(match[1], node);
  }
  const timers = new Map(); let next = 0;
  globalThis.document = {getElementById:id=>nodes.get(id),createElement:()=>new Element()};
  globalThis.window = {addEventListener(){},removeEventListener(){},setInterval:fn=>{timers.set(++next,fn);return next;},clearInterval:id=>timers.delete(id)};
  globalThis.fetch = fetcher;
  return {node:id=>{if(!nodes.has(id))throw Error(`Missing ${id}`);return nodes.get(id);},timers,
    restore(){Object.assign(globalThis,previous);}};
}

export function mockLive() {
  const state = {state:"LIVE_DISABLED",authenticated:false,password_configured:true,
    credentials:{configured:false},blockers:["Produktive Orderanbindung fehlt"],account_check:null,trial:{state:"NOT_STARTED"}};
  const calls=[];
  let acceptCookie=true;
  const fetcher = async (url, options={}) => {
    const body=JSON.parse(options.body ?? "{}");
    calls.push({url,body});
    let status=200, data;
    if(url.endsWith("/status")) data=structuredClone(state);
    else if(url.endsWith("/unlock")) {
      if(body.password !== "correct-password-123" || (!state.password_configured && body.repeat!==body.password)) {
        status=400;data={detail:"Lokales Passwort ist nicht korrekt."};
      } else { state.password_configured=true;state.authenticated=acceptCookie;data={authenticated:true}; }
    } else if(!state.authenticated) {status=401;data={detail:"Sitzung fehlt."};}
    else if(url.endsWith("/credentials")) {state.credentials.configured=true;data={configured:true};}
    else if(url.endsWith("/credentials/delete")) {state.credentials.configured=false;data={removed:true};}
    else if(url.endsWith("/lock")) {state.authenticated=false;data={authenticated:false};}
    else if(url.endsWith("/check")) data={account_checks_passed:true};
    else if(url.endsWith("/enable") || url.endsWith("/trial/start")) {status=409;data=structuredClone(state);}
    else if(url.endsWith("/disable")) {state.state="LIVE_DISABLED";data={state:"LIVE_DISABLED"};}
    else throw Error(`Unexpected request ${url}`);
    return {ok:status<400,status,json:async()=>data};
  };
  return {state,calls,fetcher,rejectCookie(){acceptCookie=false;}};
}
