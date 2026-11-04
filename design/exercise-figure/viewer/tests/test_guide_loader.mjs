import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
const root = fileURLToPath(new URL('../../', import.meta.url));
const html = readFileSync(root+'viewer/index.html','utf8');
const phase = html.slice(html.indexOf('function validatePhases('), html.indexOf('function phaseBracket('));
const points = html.slice(html.indexOf('function validatePointCache('), html.indexOf('function poseHuman('));
class Geometry { constructor(){ this.attributes={}; } setAttribute(k,v){this.attributes[k]=v;} setIndex(v){this.index=v;} }
class Attribute { constructor(array){this.array=array;} setUsage(){} }
const tinyBase={vertices:3,rest:[0,0,0,1,0,0,0,1,0],triangles:[0,1,2],bone_names:['pelvis'],joints:[[0,0,0,0],[0,0,0,0],[0,0,0,0]],weights:[[1,0,0,0],[1,0,0,0],[1,0,0,0]]};
const tinyClip={machine:'bench',acts:[0,.2,1],tris:[0,1,2],frames:[[0,0,0,1,0,0,0,1,0],[0,0,0,1,0,0,0,1.2,0],[0,0,0,1,0,0,0,2,0]]};
const clone = x => JSON.parse(JSON.stringify(x));
function harness({review=true,base=tinyBase,clip=tinyClip,meta={id:'bench',acts:[0,.2,1],frames:3},fail=false}={}){
 const requests=[]; let binaryCalls=0;
 const ctx={console:{warn(){}}, Float32Array, Map, Set, Number, Math,
  THREE:{BufferGeometry:Geometry,BufferAttribute:Attribute,DynamicDrawUsage:1},
  GUIDE_REVIEW:review,guideManifest:new Map([['bench',meta]]),guideBasePromise:undefined,guideErrors:new Set(),humanCache:{},
  fetch:async path=>{requests.push(path);if(path==='v5-guide/base.json')return{ok:true,json:async()=>base};if(path==='v5-guide/bench.json')return{ok:!fail,json:async()=>clip};return{ok:true,json:async()=>tinyClip};},
  fetchHumanBinary:async()=>{binaryCalls++;return {format:'legacy'};}
 };
 vm.createContext(ctx);vm.runInContext(phase+points+'\nglobalThis.api={validatePointCache,pointHuman,fetchGuideBase,fetchGuideHuman,fetchHuman};',ctx);
 return {...ctx.api,ctx,requests,get binaryCalls(){return binaryCalls;}};
}
test('valid review uses exact source samples and independent geometry storage',async()=>{
 const h=harness();const r=await h.fetchHuman('bench');assert.equal(r.reviewGuide,true);assert.equal(h.binaryCalls,0);
 assert.deepEqual(Array.from(r.frames[1]),Array.from(new Float32Array(tinyClip.frames[1])));
 r.geom.attributes.position.array[0]=123;assert.equal(r.frames[0][0],0);
 assert.equal(await h.fetchHuman('bench'),r);
});
test('default viewer performs no review fetch',async()=>{const h=harness({review:false});assert.equal((await h.fetchHuman('bench')).format,'legacy');assert.equal(h.requests.length,0);});
test('unlisted exercise stays on existing model',async()=>{const h=harness();assert.equal((await h.fetchHuman('other')).format,'legacy');assert.equal(h.requests.length,0);});
test('failed review fetch falls back and records visible error state',async()=>{const h=harness({fail:true});assert.equal((await h.fetchHuman('bench')).format,'legacy');assert.equal(h.ctx.guideErrors.has('bench'),true);});
for(const [name,edit] of [
 ['unequal frame stride',d=>d.frames[1].pop()],['empty frames',d=>d.frames=[]],['nan coordinate',d=>d.frames[1][0]=NaN],['float32 overflow',d=>d.frames[1][0]=1e40],['non-number coordinate',d=>d.frames[1][0]='1'],['negative index',d=>d.tris[0]=-1],['fractional index',d=>d.tris[0]=.5],['out of bounds index',d=>d.tris[0]=3],['empty topology',d=>d.tris=[]],['nonincreasing phases',d=>d.acts=[0,0,1]],['phase nan',d=>d.acts[1]=NaN]
])test('reject '+name,()=>{const d=clone(tinyClip);edit(d);assert.throws(()=>harness().validatePointCache(d));});
test('topology/model mismatch is rejected',()=>{const h=harness();const d=clone(tinyClip);d.tris=[0,2,1];assert.throws(()=>h.pointHuman(d,{points:new Float32Array(9),tris:[0,1,2]}));});
test('manifest phase mismatch falls back',async()=>{const h=harness({meta:{frames:3,acts:[0,.5,1]}});assert.equal((await h.fetchHuman('bench')).format,'legacy');assert.equal(h.ctx.guideErrors.has('bench'),true);});
test('invalid base weights are rejected and failed promise can retry',async()=>{const base=clone(tinyBase);base.weights[0]=[0,0,0,0];const h=harness({base});await assert.rejects(h.fetchGuideBase());base.weights[0]=[1,0,0,0];await h.fetchGuideBase();});
const suite=root+'lowpoly-remake/gemini_job/v5_arm_rebuild/guide_suite/';
if (existsSync(suite+'manifest.json')) {
const suiteManifest=JSON.parse(readFileSync(suite+'manifest.json'));
const suiteBase=JSON.parse(readFileSync(suite+'base.json'));
for(const c of suiteManifest.clips)test('real guide round trip '+c.id,async()=>{
 const d=JSON.parse(readFileSync(suite+c.json));const h=harness({base:suiteBase});const b=await h.fetchGuideBase();const r=h.pointHuman(d,b);
 const bytes=readFileSync(suite+c.positions);assert.equal(r.frames.length,c.frames);
 for(let f=0;f<c.frames;f++)assert.deepEqual(Buffer.from(r.frames[f].buffer),bytes.subarray(f*suiteBase.vertices*12,(f+1)*suiteBase.vertices*12));
});

} else { test('real generated guide fixtures (build_guide_suite.py)', {skip:true}, () => {}); }
