import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
const source=html.slice(html.indexOf('async function show('),html.indexOf('\nfunction setView('));
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return{promise,resolve};};
class V{constructor(){this.x=0;}}
class Box{constructor(){this.min={x:0};this.max={x:1};}setFromObject(){return this;}getCenter(v){return v;}}
class Mesh{constructor(geom){this.geom=geom;}}
function harness({slowModel=false}={}){
 const slow=deferred(),entered=deferred();let touchedOld=false;
 const ctx={THREE:{Box3:Box,Vector3:V,Mesh,MeshLambertMaterial:class{}},showRequest:0,GUIDE_REVIEW:true,GUIDE_FRONT:false,guideErrors:new Set(),cache:{},shown:[],act:0,humanOn:true,
 world:{clear(){},add(){}},humanBtn:{classList:{toggle(){}},hidden:true},humanList:new Set(['first','second']),
 modelsEl:{textContent:''},kname:x=>x,baseOf:x=>x,
 document:{getElementById:()=>({style:{}})},setAct(){},setView(){},pose(){},
 fetchModel:async n=>{if(n==='first'&&slowModel){entered.resolve();return slow.promise;}return{faces:1};},
 buildGroup:(n,d)=>({name:n,faces:d.faces,group:{position:{x:0},children:[],localToWorld:v=>v,add(m){this.children.push(m);}}}),
 fetchHuman:async n=>{if(n==='first'&&!slowModel){entered.resolve();return slow.promise;}return{geom:n,reviewGuide:true};},
 };
 vm.createContext(ctx);vm.runInContext(source+'\nglobalThis.show=show;',ctx);
 return {ctx,slow,entered,get result(){return ctx.shown;}};
}
for(const slowModel of [false,true])test(`latest exercise wins while ${slowModel?'equipment':'human'} is loading`,async()=>{
 const h=harness({slowModel});const first=h.ctx.show(['first']);await h.entered.promise;
 await h.ctx.show(['second']);h.slow.resolve(slowModel?{faces:1}:{geom:'first'});await first;
 assert.equal(h.result[0].name,'second');assert.equal(h.result[0].group.children.length,1);
 assert.equal(h.result[0].group.children[0].geom,'second');assert.match(h.ctx.modelsEl.textContent,/^second/);
});
