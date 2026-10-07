import assert from "node:assert/strict";
import {test} from "node:test";
import {readFileSync} from "node:fs";
import ts from "typescript";
const source=readFileSync(new URL("../src/activity.ts",import.meta.url),"utf8");
const compiled=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText;
const {activityText}=await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);
test("activity never claims a running strategy without proof or automatic real orders",()=>{
  assert.match(activityText(undefined,String),/noch nicht bestätigt/);
  const value={alive:false,message:"Zeitstempel prüfen",checked_markets:14,expected_markets:15,last_checked_closed_bar_utc:null};
  assert.match(activityText(value,String),/Aktivität prüfen.*14\/15/);
  const text=activityText({...value,alive:true,checked_markets:15,last_checked_closed_bar_utc:"now"},x=>`Berlin(${x})`);
  assert.match(text,/Zuletzt verarbeitet: Berlin\(now\)/);
  assert.match(text,/keinen Echtgeldtest automatisch/);
});
