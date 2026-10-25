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

const {phraseAt}=load('renderer/src/captions.ts');
const sentence='今天想画的小图，刚刚想到的几句话，都可以随手记下来，留给下一次翻看。';
const seen=[];for(let t=0;t<10;t+=.02){const part=phraseAt(sentence,0,10,t,true);if(seen.at(-1)!==part)seen.push(part);if(part.replace(/[，。！？；,.!?;]/g,'').length>14)throw Error('Vertical caption too long');if(/^[，。！？；,.!?;]+$/.test(part))throw Error('Orphan punctuation caption');}
if(seen.join('')!==sentence)throw Error('Caption phrase dropped text');
console.log('PASS: caption phrases fit vertical safe area and preserve sentence text');

const {shotcraftProgress}=load('renderer/src/shotcraft.ts');
if(shotcraftProgress(0,120,30)!==0||shotcraftProgress(8,120,30)!==0)throw Error('Missing establishing hold');
if(shotcraftProgress(90,120,30)!==1||shotcraftProgress(119,120,30)!==1)throw Error('Camera still drifts after landing');
const auto=planTransitions(Array.from({length:5},()=>({source:'image',asset_kind:'ai_image',motion:'focus',transition:'auto'})));
if(auto.some(t=>t.kind!=='cut'))throw Error('Automatic decorative transition rotation returned');
console.log('PASS: shotcraft establish/move/hold phases and content-led direct cuts');
