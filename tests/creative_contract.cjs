// Run with node; exercise the actual TypeScript exports through TS transpilation.
const fs=require('node:fs'),vm=require('node:vm'),ts=require('../renderer/node_modules/typescript');
function load(file){const out=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;const box={exports:{}};vm.runInNewContext(out,box);return box.exports;}
const {camera}=load('renderer/src/direction.ts'),{planTransitions}=load('renderer/src/transitions.ts');
const motions=['push','pull','pan','orbit','rise','focus','page_scroll','split'];
if(new Set(motions.map(m=>camera(m,.4,false,1280,720))).size!==motions.length)throw Error('Motions still alias one another');
for(const m of motions){const value=camera(m,1,false,1280,720);if(/NaN|undefined/.test(value))throw Error(m);}
const input=['push','iris','iris','cut'].map(t=>({source:'image',asset_kind:'ai_image',motion:'focus',transition:t}));
const result=planTransitions(input,'douyin');if(result.filter(t=>t.kind==='iris').length!==1)throw Error('Iris cap');if(result[3].kind!=='cut')throw Error('Director ignored');
console.log('PASS: 8 distinct camera paths, director-controlled cuts, one iris maximum');
