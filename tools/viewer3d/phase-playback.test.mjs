import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import test from 'node:test';
const sources = [
  ['canonical', '../../design/exercise-figure/viewer/index.html'],
  ['app asset', process.env.VIEWER3D_TEST_ASSET || fileURLToPath(new URL('../../phone/src/main/assets/viewer3d/index.html', import.meta.url))],
];
for (const [label, path] of sources) {
const source = readFileSync(label === 'app asset' ? path : new URL(path, import.meta.url), 'utf8');
const check = (name, body) => test(`${label}: ${name}`, body);
function fn(name) {
  const found = source.match(new RegExp(`function ${name}\\([^]*?\\n}`));
  assert.ok(found, `missing viewer function ${name}`);
  return found[0];
}
function runtime() {
  const value = () => ({ value: 0, lerpVectors(a,b,t){this.value=a+(b-a)*t;}, slerpQuaternions(a,b,t){this.value=a+(b-a)*t;} });
  const context = vm.createContext({ console, Float32Array, tp:value(), tq:value(), ts:value(),
    instancePose:{ compose(p){ this.x=p.value; return this; } } });
  const optional = ['validatePhases','phaseBracket'].filter(n=>source.includes(`function ${n}(`));
  vm.runInContext([...optional,'humanFrame','poseHuman','pose','parse'].map(fn).join('\n'), context);
  return context;
}
function avatar(acts,values) {
  const cache = label === 'app asset'
    ? { vertices:1, minimum:[0,0,0], scale:[1,1,1], quantized:Uint16Array.from(values.flatMap(x=>[x,0,0])), skinFrames:new Map() }
    : { frames:values.map(x=>new Float32Array([x,0,0])) };
  return { human: { acts, ...cache, geom:{attributes:{position:{array:new Float32Array(3)}}} } };
}
check('human reaches the stored keyframe at its actual nonuniform phase',()=>{
  const r=runtime(),m=avatar([0,.1,1],[0,10,100]);r.poseHuman(m,.1);assert.equal(m.human.geom.attributes.position.array[0],10);
});
check('human interpolation follows phase time on both sides of an adaptive sample',()=>{
  const r=runtime(),m=avatar([0,.1,1],[0,20,110]);r.poseHuman(m,.05);assert.equal(m.human.geom.attributes.position.array[0],10);r.poseHuman(m,.55);assert.equal(m.human.geom.attributes.position.array[0],65);
});
check('equipment and human stay synchronized with different sample counts',()=>{
  const r=runtime(),m=avatar([0,.1,1],[0,10,100]);
  const equipment={acts:[0,.25,.75,1],objs:[{steps:[0,25,75,100].map(p=>({p,q:0,s:1})),mesh:{matrix:{compose(p){this.x=p.value;}}}}]};
  for(const phase of [.1,.25,.55,.75,1]){r.poseHuman(m,phase);r.pose(equipment,phase);assert.ok(Math.abs(equipment.objs[0].mesh.matrix.x-m.human.geom.attributes.position.array[0])<1e-5,`desync at ${phase}`);}
});
check('uniform, static and endpoint playback retain their behavior',()=>{
  const r=runtime(),m=avatar([0,.5,1],[0,50,100]);for(const p of [0,.25,.5,.75,1]){r.poseHuman(m,p);assert.equal(m.human.geom.attributes.position.array[0],100*p);}
  const single=avatar([0],[42]);r.poseHuman(single,1);assert.equal(single.human.geom.attributes.position.array[0],42);
  r.poseHuman(m,-1);assert.equal(m.human.geom.attributes.position.array[0],0);r.poseHuman(m,2);assert.equal(m.human.geom.attributes.position.array[0],100);
});
check('reversing playback retraces the same poses without an extra phase jump',()=>{
  const r=runtime(),m=avatar([0,.1,.6,1],[0,10,60,100]);for(const p of [.9,.6,.4,.1,0,.1,.4,.6,.9]){r.poseHuman(m,p);assert.ok(Math.abs(m.human.geom.attributes.position.array[0]-100*p)<1e-5);}
});

check('invalid phase arrays and nonfinite inputs fail before deforming geometry',()=>{
  const r=runtime();
  for(const phases of [[],[0,0,1],[0,.5,.4,1],[0,NaN,1],[-.1,1],[0,1.1]])assert.throws(()=>r.validatePhases(phases),/animation phases/);
  assert.throws(()=>r.phaseBracket([0,1],NaN),/invalid animation phase/);
  assert.throws(()=>r.parse({acts:[0,0],objects:[]}),/invalid animation phases/);
});
check('inconsistent equipment samples fail at load instead of drifting during playback',()=>{
  const r=runtime();
  // The app intentionally accepts an independent uniform track (e.g. 9 equipment
  // samples alongside 25 human samples); the canonical viewer requires matching counts.
  const invalidTrack=label === 'app asset' ? [] : [1,2,3];
  assert.throws(()=>r.parse({acts:[0,1],objects:[{m:invalidTrack}]}),/invalid equipment frame count/);
});
check('static equipment remains still alongside animated human motion',()=>{
  const r=runtime(),matrix={compose(p){this.x=typeof p==='number'?p:p.value;}},m={acts:[0,1],objs:[{steps:[{p:7,q:0,s:1}],mesh:{matrix}}]};
  for(const p of [0,.5,1]){r.pose(m,p);assert.equal(matrix.x,7);}
});
if (label === 'app asset') check('shared moving equipment preserves each slot at nonuniform phases',()=>{
  const r=runtime(), slots=[], mesh={instanceMatrix:{},setMatrixAt(id,matrix){slots[id]=matrix.x;}};
  const m={acts:[0,.1,1],instances:[mesh],objs:[[0,10,100],[35,45,135]].map((ps,slot)=>({
    slot, mesh, steps:ps.map(p=>({p,q:0,s:1}))
  }))};
  for(const a of [0,.1,.55,1,.25]){
    r.pose(m,a); assert.ok(Math.abs(slots[0]-a*100)<1e-7); assert.ok(Math.abs(slots[1]-slots[0]-35)<1e-7);
    assert.equal(mesh.instanceMatrix.needsUpdate,true);
  }
});
if (label === 'app asset') check('independent equipment uses its own uniform grid',()=>{
  const r=runtime(), matrix={compose(p){this.x=p.value;}};
  const acts=Array.from({length:25},(_,i)=>(i/24)**2);
  const steps=Array.from({length:9},(_,i)=>({p:i/8,q:0,s:1}));
  for (const a of [0,.1,.5,.875,1]) {
    r.pose({acts,objs:[{steps,mesh:{matrix}}]},a);
    assert.ok(Math.abs(matrix.x-a)<1e-7);
  }
});
if (label === 'app asset' && source.includes('function addLatStackUV(')) check('stack decals use their own atlas half',()=>{
  const context=vm.createContext({Float32Array,THREE:{BufferAttribute:class { constructor(array){this.array=array;} }}});
  vm.runInContext(fn('addLatStackUV'),context);
  for (const [lo,hi,v0] of [[-.5655,-.0195,0],[-.0195,.5265,.5]]) {
    const geom={attributes:{position:{count:4,getX:i=>[-1,1,1,-1][i],getZ:i=>[lo,lo,hi,hi][i]}},
      hasAttribute(k){return k in this.attributes;}, getAttribute(k){return this.attributes[k];},
      setAttribute(k,v){this.attributes[k]=v;}, computeBoundingBox(){this.boundingBox={min:{x:-1,z:lo},max:{x:1,z:hi}};}};
    context.addLatStackUV(geom);
    assert.deepEqual(Array.from(geom.attributes.uv.array),[0,v0,1,v0,1,v0+.5,0,v0+.5]);
  }
});
if (label === 'app asset' && source.includes('function mergePlateOverlay(')) check('plate overlay replaces only named slots on the same timeline',()=>{
  const ctx=vm.createContext({parse:d=>({...d,parsed:d.objects.map(o=>({...o}))})});
  vm.runInContext(fn('mergePlateOverlay'),ctx);
  const raw={acts:[0,.3,1],objects:[{name:'grip'},{name:'plate'},{name:'footplate'}]};
  const overlay={acts:raw.acts.map(Math.fround),parsed:[{mat:10},{mat:3}]};
  const got=ctx.mergePlateOverlay(raw,overlay,{1:'plate'});
  assert.deepEqual(Array.from(got.parsed,o=>o.name??o.mat),['grip','footplate',10,3]);
  assert.equal(got.parsed[0].legacy,true);assert.equal(got.acts,raw.acts);assert.equal(raw.objects.length,3);
  for (const [targets,clip] of [[{0:'plate'},overlay],[{1:'plate'},{...overlay,acts:[0,.4,1]}],[{1:'plate'},{...overlay,parsed:[]}]])
    assert.throws(()=>ctx.mergePlateOverlay(raw,clip,targets),/stale plate overlay/);
});
}
