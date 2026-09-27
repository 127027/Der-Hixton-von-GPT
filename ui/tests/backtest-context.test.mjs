import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import ts from "typescript";
const source = readFileSync(new URL("../src/backtest-context.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
const { comparisonText, portfolioBlocksText } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);
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
