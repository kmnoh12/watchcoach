// Run alongside phase-playback.test.mjs against the generated viewer asset.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import * as THREE from '../../phone/src/main/assets/viewer3d/three/three.module.js';

const source=readFileSync(new URL('./index.html',import.meta.url),'utf8');
const section=(from,to)=>source.slice(source.indexOf(from),source.indexOf(to));
function fixture() {
  const calls=[], timers=new Map(); let now=1000, serial=0;
  const clock={now:()=>now};
  const window={__ready:true,WatchCoachHaptics:{tick:()=>calls.push(now)}};
  const document={hidden:false,addEventListener:(name,fn)=>document[name]=fn};
  const ctx=vm.createContext({THREE,window,document,performance:clock,params:new URLSearchParams(),
    setTimeout:(fn,delay)=>{const id=++serial;timers.set(id,{time:now+delay,fn});return id},clearTimeout:id=>timers.delete(id),
    makePresetMaterial:()=>new THREE.MeshStandardMaterial(),standTipGap:.006,standWidth:.064,
    buildGroup:()=>({group:new THREE.Group(),objs:[],instances:[]}),
    pose:(m,a)=>m.loadRig?.pose(a),act:.25,shown:[],UP:new THREE.Vector3(0,0,1)});
  vm.runInContext(section('function validLoad','// ---------- seated avatar')+section('function phaseBracket','function poseHuman')+section('function ringGeometry','const standWidth')+
    section('const COLLAR_WIDTH','const tp ='),ctx);
  function model(plan){const m={group:new THREE.Group(),acts:[0,.25,1],data:{parsed:[]},loadPlan:{...plan,remove:new Set()}};ctx.shown.push(m);return m;}
  function step(ms){now+=ms;for(const [id,t] of timers)if(now>=t.time){timers.delete(id);t.fn()}
    for(const m of ctx.shown)if(m.loadRig?.moving){ctx.advanceLoad(m.loadRig,now);m.loadRig.pose(ctx.act)}}
  return {ctx,model,step,set:window.setLoad,calls,document};
}
const v=(x=0,y=0,z=0)=>new THREE.Vector3(x,y,z);
const quat=new THREE.Quaternion().setFromUnitVectors(v(0,0,1),v(1,0,0));
const track=[0,.1,.2].map(z=>({p:v(0,0,z),q:quat,s:v(1,1,1)}));
const spec={20:{kg:20,diameter:.45,thick:.042},10:{kg:10,diameter:.325,thick:.027},5:{kg:5,diameter:.23,thick:.019}};
const sleeve={base:track,delta:0,run:.4,bore:.026,source:{mat:3,color:[1,1,1]}};
function bar(f){return f.model({kind:'plates',groups:[{...sleeve,sign:1},{...sleeve,sign:-1}],layout:kg=>{
  const sides={20:[],60:[20],70:[20,5],80:[20,10],90:[20,10,5],120:[20,20,10]};
  return sides[kg] ? {fit:1,specs:sides[kg].map(k=>spec[k])} : null;
}})}
function shown(r){return r.group.children.filter(o=>o.visible).map(o=>[o.id,...o.position,o.scale.z,o.material.opacity,o.material.emissiveIntensity])}
function tower(){const part=(z)=>({geom:new THREE.BoxGeometry(.2,.2,.03),steps:[{p:v(0,0,z),q:new THREE.Quaternion(),s:v(1,1,1)}]});
  const plates=Array.from({length:20},(_,i)=>({center:v(0,0,1-i*.04),part:part(1-i*.04)}));
  const pin={center:v(0,-.1,1),part:part(1)};
  return {plates,pitch:.04,rowPitch:.04,count:20,topZ:1,lowestLift:0,track,pin,pinParts:[pin],insertion:v(),outward:v(0,-.1,0)};}

test('first open and rapid edits: immediate target, one debounce, mirrored prefix, one collar tick',()=>{
  const f=fixture(),m=bar(f);f.set(60,false);const r=m.loadRig,initial=shown(r);assert.equal(initial.length,4);assert.equal(r.moving,false);
  const kept=r.group.children.filter(o=>o.geometry.type==='LatheGeometry' && Math.abs(o.position.x)<.03);
  assert.equal(kept.length,2); const xs=kept.map(o=>o.position.x);
  f.set(1);f.step(90);f.set(12);f.step(90);f.set(120);f.step(349);assert.deepEqual(shown(r),initial);
  f.step(1);assert.ok(r.moving);f.step(230);assert.ok(r.group.children.some(o=>o.visible && o.material.opacity<1));
  assert.deepEqual(kept.map(o=>o.position.x),xs);assert.equal(xs[0],-xs[1]);
  f.step(520);assert.equal(shown(r).length,8);assert.equal(f.calls.length,1);assert.equal(r.moving,false);f.step(500);assert.equal(f.calls.length,1);
});
test('retarget while plates are partly out/in: no teleport or ghosts, empty and fallback restore',()=>{
  for(const when of [83,195,390,466,686]){
    const f=fixture(),m=bar(f);f.set(90,false);const r=m.loadRig;f.set(60);f.step(350);f.step(when);
    const before=shown(r);f.ctx.applyEquipmentLoad(m,80,true);r.pose(.25);assert.deepEqual(shown(r),before);
    f.step(750);assert.equal(shown(r).length,6);assert.ok(shown(r).every(row=>row.at(-2)===1));
    f.set(20,false);assert.equal(shown(r).length,0);f.set(999,false);assert.equal(r.group.visible,false);
    f.set(80,false);assert.equal(r.group.visible,true);assert.equal(shown(r).length,6);
  }
});
test('pin follows the carriage through withdrawal, retarget, click and a top-down sweep',()=>{
  const f=fixture(),m=f.model({kind:'stack',towers:[tower()]});f.set(30,false);const r=m.loadRig,rows=r.group.children,pin=rows[20];
  const z=pin.position.z;f.set(45);f.step(350);f.step(135);assert.equal(pin.position.z,z);assert.equal(pin.position.y,-.1);
  f.step(130);assert.ok(pin.position.z<z);const before=shown(r);f.ctx.applyEquipmentLoad(m,25,true);r.pose(.25);assert.deepEqual(shown(r),before);
  f.step(565);assert.ok(rows[0].material.emissiveIntensity>rows[4].material.emissiveIntensity);
  f.step(95);assert.ok(rows[0].material.emissiveIntensity<rows[4].material.emissiveIntensity);assert.equal(rows[5].material.emissiveIntensity,0);
  f.step(90);assert.equal(pin.position.y,0);assert.equal(f.calls.length,1);assert.ok(rows.every(o=>o.material.emissiveIntensity===0 || !o.material.emissive.getHex()));
  r.pose(.25);const a=rows.map(o=>o.position.z);r.pose(1);rows.forEach((o,i)=>assert.ok(Math.abs(o.position.z-a[i]-(i<5 || i===20 ?.1:0))<1e-9));
});
test('hiding during a pending edit or sweep settles immediately and never buzzes on return',()=>{
  const f=fixture(),m=f.model({kind:'stack',towers:[tower()]});f.set(30,false);const r=m.loadRig;
  f.set(45);f.step(100);f.document.hidden=true;f.document.visibilitychange();assert.equal(r.moving,false);
  f.step(900);f.document.hidden=false;f.set(45);f.step(400);assert.equal(r.moving,false);
  f.set(25);f.step(350);f.step(290);f.document.hidden=true;f.document.visibilitychange();f.step(1000);assert.equal(f.calls.length,0);
});

test('every plate size keeps its printed weight on both bumper and iron, including fractional changes',()=>{
  const extra={},ctx=vm.createContext({smallPlateMap:extra});
  vm.runInContext(section('const bumperPlateCells','function fitDiscGeometry'),ctx);
  for(const [base,expected] of [[5,[5,6,7,0,4,5,6]],[1,[1,0,2,3,1,2,3]]]){
    [20,15,10,5,2.5,1.25,1].forEach((kg,i)=>{
      const g=new THREE.BufferGeometry(),uv=new THREE.Float32BufferAttribute([((base%4)+.5)/4,((base>>2)+.5)/2],2);
      g.setAttribute('uv',uv);const texture=ctx.finishPlateFace(g,kg);
      assert.equal(texture,(kg<5 || (base===1 && kg===15)) ? extra : undefined);
      assert.equal(Math.floor(uv.getX(0)*4)+4*Math.floor(uv.getY(0)*2),expected[i]);
    });
  }
});

test('repeat playback reuses the same two vertex buffers and phase cursor when direction reverses',()=>{
  const ctx=vm.createContext({Float32Array});vm.runInContext(section('function humanFrame','async function fetchHuman(')+section('function phaseBracket','function poseHuman'),ctx);
  const h={vertices:1,minimum:[0,0,0],scale:[1,1,1],quantized:Uint16Array.from([1,1,1,2,2,2,3,3,3,4,4,4])};
  const buffers=new Set(),out={};
  for(const a of [0,.12,.55,.8,1,.44,.1,0]){
    assert.equal(ctx.phaseBracket([0,.2,.7,1],a,out),out);
    const A=ctx.humanFrame(h,out.i), B=ctx.humanFrame(h,out.j);buffers.add(A);buffers.add(B);
    assert.equal(A[0],1+out.i);assert.equal(B[0],1+out.j);
  }
  assert.equal(buffers.size,2);
});
