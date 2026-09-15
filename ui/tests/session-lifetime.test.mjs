import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import ts from "typescript";
const source = readFileSync(new URL("../src/session-lifetime.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
const { initializeSessionLifetime } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);

function harness() {
  const saved = { window: global.window, document: global.document, WebSocket: global.WebSocket, setTimeout: global.setTimeout, clearTimeout: global.clearTimeout };
  const events = {}, sockets = [], elements = [], timers = [];
  let reloads = 0;
  global.window = { location: { host: "127.0.0.1:8765", reload() { ++reloads; } }, addEventListener(name, fn) { events[name] = fn; } };
  global.document = {
    querySelector() { return { prepend() {} }; },
    createElement() { const el = { textContent: "", classList: {add() {}, remove() {}}, setAttribute() {}, append() {}, addEventListener(n,f) { this[n] = f; } }; elements.push(el); return el; },
  };
  global.WebSocket = class {
    static OPEN = 1;
    constructor(url) { this.url = url; this.events = {}; this.sent = []; this.readyState = 1; sockets.push(this); }
    addEventListener(n,f) { this.events[n] = f; }
    send(value) { this.sent.push(value); }
    close() { this.closed = true; this.events.close(); }
    message(instance) { this.events.message({data: JSON.stringify({instance, stopping:false})}); }
  };
  global.setTimeout = fn => { timers.push(fn); return timers.length; };
  global.clearTimeout = () => {};
  initializeSessionLifetime();
  return { events, sockets, elements, timers, reloads: () => reloads, cleanup: () => Object.assign(global, saved) };
}

test("closing page releases the lease without reconnect; BFCache restore reconnects", () => {
  const h = harness();
  try {
    assert.equal(h.sockets[0].url, "ws://127.0.0.1:8765/api/session/presence");
    h.sockets[0].message("first");
    h.events.pagehide();
    assert.equal(h.sockets[0].closed, true);
    assert.equal(h.timers.length, 0);
    h.events.pageshow({persisted: true});
    assert.equal(h.sockets.length, 2);
  } finally { h.cleanup(); }
});
test("explicit stop sends only a stop command and never reconnects", () => {
  const h = harness();
  try {
    h.sockets[0].message("first");
    h.elements[2].click();
    assert.deepEqual(h.sockets[0].sent, ["stop"]);
    assert.equal(h.timers.length, 0);
    assert.match(h.elements[1].textContent, /nicht verkauft/);
  } finally { h.cleanup(); }
});
test("replacement instance reloads the UI; same instance reconnect does not", () => {
  const h = harness();
  try {
    h.sockets[0].message("first");
    h.sockets[0].close();
    assert.match(h.elements[1].textContent, /keine laufende Überwachung bestätigt/);
    h.timers[0]();
    h.sockets[1].message("first");
    assert.equal(h.reloads(), 0);
    h.sockets[1].message("replacement");
    assert.equal(h.reloads(), 1);
  } finally { h.cleanup(); }
});
