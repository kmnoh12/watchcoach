import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import test from 'node:test';
const sources = [
  ['canonical', '../../design/exercise-figure/viewer/index.html'],
  ['app asset', '../../phone/src/main/assets/viewer3d/index.html'],
];
for (const [label, path] of sources) {
const source = readFileSync(fileURLToPath(new URL(path, import.meta.url)), 'utf8');
const check = (name, body) => test(`${label}: ${name}`, body);
function fn(name) {
  const found = source.match(new RegExp(`function ${name}\\([^]*?\\n}`));
  assert.ok(found, `missing viewer function ${name}`);
  return found[0];
}
function runtime() {
  const value = () => ({ value: 0, lerpVectors(a,b,t){this.value=a+(b-a)*t;}, slerpQuaternions(a,b,t){this.value=a+(b-a)*t;} });
  const context = vm.createContext({ console, Float32Array, tp:value(), tq:value(), ts:value() });
  const optional = ['validatePhases','phaseBracket'].filter(n=>source.includes(`function ${n}(`));
  vm.runInContext([...optional,'humanFrame','poseHuman','pose','parse'].map(fn).join('\n'), context);
  return context;
}
function avatar(acts,values) {
  return { human: { acts, frames:values.map(x=>new Float32Array([x,0,0])), geom:{attributes:{position:{array:new Float32Array(3)}}} } };
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
  const r=runtime();assert.throws(()=>r.parse({acts:[0,1],objects:[{m:[1,2,3]}]}),/invalid equipment frame count/);
});
check('static equipment remains still alongside animated human motion',()=>{
  const r=runtime(),matrix={compose(p){this.x=typeof p==='number'?p:p.value;}},m={acts:[0,1],objs:[{steps:[{p:7,q:0,s:1}],mesh:{matrix}}]};
  for(const p of [0,.5,1]){r.pose(m,p);assert.equal(matrix.x,7);}
});
}
