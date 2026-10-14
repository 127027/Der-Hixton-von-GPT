import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import ts from "typescript";
const source = readFileSync(new URL("../src/backtest-context.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
const { comparisonText, portfolioBlocksText, savedRunNotice } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);
test("missing backend evidence never implies matching active bot", () => {
  assert.match(comparisonText(), /ungeprüft/);
  for (const status of ["MATCHING", "DIFFERENT", "UNVERIFIED"]) {
    const text = comparisonText({status, reasons:["Grund"], scope:"Diagnose", window_note:"Zeitfenster"});
    assert.match(text, /Grund Diagnose Zeitfenster/);
    if (status === "MATCHING") assert.match(text, /stimmen/);
    else assert.doesNotMatch(text, /stimmen mit aktivem Bot überein/);
  }
});

test("portfolio explains risk blocks separately from full slots", () => {
  assert.equal(portfolioBlocksText(), "");
  assert.match(portfolioBlocksText({}), /nicht verfügbar/);
  const text = portfolioBlocksText({max_concurrent_positions:3,blocked_reasons:{NO_FREE_SLOT:4,MAX_DRAWDOWN_20_PERCENT:431,POLICY_CMO:4}});
  assert.match(text, /3 Slots/);
  assert.match(text, /431 × dauerhafter Konto-Risikohalt/);
  assert.match(text, /4 × alle Slots belegt/);
  assert.match(portfolioBlocksText({blocked_reasons:{}}), /Keine blockierten/);
});
test("research comparison stays internal and has no current UI mount", () => {
  const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
  const main = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");
  assert.doesNotMatch(html, /id="backtest-comparison"/);
  assert.doesNotMatch(main, /#backtest-comparison/);
  assert.doesNotMatch(html, /Buy & Hold Ende/);
});

test("slot accounting uses the saved run tranche and never invents 80 USDC", () => {
  const portfolio = {blocked_reasons:{}, metrics:{completed_trades:87, completed_slot_trades:140}};
  assert.match(portfolioBlocksText({...portfolio, target_notional:"125.00"}), /125-USDC-Tranchen/);
  assert.match(portfolioBlocksText({...portfolio, target_notional:"250.00"}), /250-USDC-Tranchen/);
  assert.doesNotMatch(portfolioBlocksText(portfolio), /80|USDC-Tranchen/);
});


test("old saved evidence is explicitly historical even if a new calculation is running or failed", () => {
  const old={status:"DIFFERENT",reasons:[],scope:"",window_note:""};
  assert.match(savedRunNotice(true,"IDLE",old), /Historischer Lauf/);
  assert.match(savedRunNotice(true,"RUNNING",old), /Neuer Backtest läuft.*letzte gespeicherte.*Historischer Lauf/);
  assert.match(savedRunNotice(true,"FAILED",old), /fehlgeschlagen.*letzte gespeicherte.*Historischer Lauf/);
  assert.doesNotMatch(savedRunNotice(true,"IDLE",old), /passt zu den aktuellen/);
  assert.match(savedRunNotice(false,"RUNNING"), /Noch kein abgeschlossenes Ergebnis/);
  assert.match(savedRunNotice(true,"COMPLETE",{...old,status:"MATCHING"}), /gespeicherte Lauf passt/);
  assert.match(savedRunNotice(true,"IDLE"), /nicht vollständig belegt/);
});

test("the actual backtest page mounts the freshness notice and never calls an old run current", () => {
  const html=readFileSync(new URL("../index.html",import.meta.url),"utf8");
  const main=readFileSync(new URL("../src/main.ts",import.meta.url),"utf8");
  assert.match(html,/id="backtest-run-note"/);
  assert.match(main,/savedRunNotice\(Boolean\(latestRun\), response.status, latestRun\?\.comparison\)/);
  assert.doesNotMatch(main,/Aktueller V8-Lauf/);
});
