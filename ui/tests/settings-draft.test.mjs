import assert from "node:assert/strict";
import {test} from "node:test";
import {readFileSync} from "node:fs";
import ts from "typescript";

const source=readFileSync(new URL("../src/settings-draft.ts",import.meta.url),"utf8");
const compiled=ts.transpileModule(
  source,
  {compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}},
).outputText;
const url="data:text/javascript;base64,"+Buffer.from(compiled).toString("base64");
const {SettingsDraft,settingsProblem,derivedDraft}=await import(url);

const limits={
  min_capital_usdc:"100.00",
  max_capital_usdc:"1000.00",
  allocator_version:"CAPITAL-V1-2X50PCT",
};

test("simple form has one max-capital field and no editable slot/notional controls",()=>{
  const html=readFileSync(new URL("../index.html",import.meta.url),"utf8");
  assert.match(html,/id="capital-input"[^>]+value="250"/);
  assert.doesNotMatch(html,/id="slot-input"/);
  assert.doesNotMatch(html,/id="notional-input"/);
  assert.match(html,/id="settings-button"[^>]+>Übernehmen</);
  assert.match(html,/Maximaler USDC-Einsatz/);
  assert.match(html,/1 × 50 USDC · Test freigeben/);
});

test("new controllers avoid native prompts and browser secret storage",()=>{
  for(const file of ["trading-settings.ts","live-preparation.ts"]){
    const code=readFileSync(new URL("../src/"+file,import.meta.url),"utf8");
    assert.doesNotMatch(code,/window\.(prompt|confirm|alert)\s*\(/);
    assert.doesNotMatch(code,/(localStorage|sessionStorage)\s*[.(]/);
  }
});

test("max capital validates the researched range and derives two 50-percent slots",()=>{
  const settings=derivedDraft("250",false,limits);
  assert.equal(settingsProblem(settings,limits),null);
  assert.equal(settings.slot_count,2);
  assert.equal(settings.target_notional_usdc,"125.00");
  assert.equal(settings.allocation_policy,"ranked_repeat");
  assert.equal(settingsProblem(derivedDraft("1000",false,limits),limits),null);
  assert.match(settingsProblem(derivedDraft("99",false,limits),limits),/100,00/);
  assert.match(settingsProblem(derivedDraft("1001",false,limits),limits),/1\.000,00/);
  assert.match(settingsProblem(derivedDraft("NaN",false,limits),limits),/gültige USDC-Zahl/);
});

test("failed save preserves edit and concurrent save cannot start",()=>{
  const draft=new SettingsDraft();draft.edit();
  assert.equal(draft.acceptsPolling,false);assert.equal(draft.beginSave(),true);
  assert.equal(draft.beginSave(),false);draft.finishSave(false);
  assert.equal(draft.dirty,true);assert.equal(draft.acceptsPolling,false);
});

test("successful save permits polling again",()=>{
  const draft=new SettingsDraft();draft.edit();draft.beginSave();draft.finishSave(true);
  assert.equal(draft.acceptsPolling,true);
});
