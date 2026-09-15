import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import ts from "typescript";
const source = readFileSync(new URL("../src/market-signal.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
const { marketSignalText } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);
test("market cards distinguish old indicator flips from executed trades", () => {
  const format = value => `Berlin(${value})`;
  assert.equal(marketSignalText(null, format), "Noch kein Trendwechsel in den geladenen Daten");
  assert.equal(marketSignalText({ action: "ENTER_LONG", time_utc: "old" }, format), "Letzter Trendwechsel: Kauf · Berlin(old)");
  assert.match(marketSignalText({ action: "EXIT_LONG", time_utc: "now" }, format), /Verkauf/);
  assert.match(marketSignalText({ action: "OTHER", time_utc: "now" }, format), /Unbekannt/);
  const main = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");
  assert.match(main, /escapeHtml\(marketSignalText\(market.last_signal, formatDate\)\)/);
  assert.match(main, /Grüner Trend ≠ neuer Kauf/);
});
