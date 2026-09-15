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
test("comparison has a visible mount point and text-only rendering", () => {
  const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
  const main = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");
  assert.match(html, /id="backtest-comparison"/);
  assert.match(main, /text\("#backtest-comparison", comparisonText/);
  assert.match(main, /text\("#backtest-comparison", "Abgleich für diese Auswahl wird geladen/);
  assert.match(main, /text\("#backtest-comparison", "Abgleich derzeit nicht verfügbar/);
});
