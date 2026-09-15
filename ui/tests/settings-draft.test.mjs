import assert from "node:assert/strict";
import {test} from "node:test";
import {readFileSync} from "node:fs";
import ts from "typescript";
const source=readFileSync(new URL("../src/settings-draft.ts",import.meta.url),"utf8");
const compiled=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText;
const {SettingsDraft,settingsProblem}=await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);

test("simple form: one save, ten slots, one-USDC steps, no pause/discard/typing ceremony",()=>{
  const html=readFileSync(new URL("../index.html",import.meta.url),"utf8");
  assert.match(html,/id="notional-input"[^>]+step="1"/);
  assert.match(html,/id="slot-input"[^>]+max="10"/);
  assert.match(html,/id="settings-button"[^>]+>Übernehmen</);
  assert.doesNotMatch(html,/id="(?:settings-confirmation|settings-discard|emergency-input|live-confirmation|live-trial-confirmation|live-trial-consent|settings-limits)"/);
  for(const id of ["live-auth-result","live-key-result","live-check-result","live-result","live-trial-result"])
    assert.ok(html.includes(`id="${id}"`));
  assert.match(html,/<fieldset id="live-protected" class="live-controls" disabled>/);
  assert.equal((html.match(/id="live-off"/g)??[]).length,1);
});
test("new controllers avoid native prompts and browser secret storage",()=>{
  for(const file of ["trading-settings.ts","live-preparation.ts"]){
    const code=readFileSync(new URL("../src/"+file,import.meta.url),"utf8");
    assert.doesNotMatch(code,/window\.(prompt|confirm|alert)\s*\(/);
    assert.doesNotMatch(code,/(localStorage|sessionStorage)\s*[.(]/);
  }
});
test("user chooses position budget, with valid slots and finite positive amounts",()=>{
  const limits={max_slots:10};
  assert.equal(settingsProblem({slot_count:4,target_notional_usdc:"45",emergency_stop:false},limits),null);
  assert.equal(settingsProblem({slot_count:10,target_notional_usdc:"24",emergency_stop:false},limits),null);
  for(const slot_count of [0,11,1.5]) assert.match(settingsProblem({slot_count,target_notional_usdc:"10"},limits),/1 bis 10/);
  assert.equal(settingsProblem({slot_count:5,target_notional_usdc:"50"},limits),null);
  assert.equal(settingsProblem({slot_count:10,target_notional_usdc:"100"},limits),null);
  for(const target_notional_usdc of ["0","-50","NaN","Infinity","1e309"])
    assert.match(settingsProblem({slot_count:3,target_notional_usdc},limits),/positive, endliche/);
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
