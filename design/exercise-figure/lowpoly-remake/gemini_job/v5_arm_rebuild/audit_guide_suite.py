"""Independent audit of persisted guide caches and real playback midpoints."""
from pathlib import Path
import sys,json,time,argparse
import bpy,numpy as np
from mathutils.bvhtree import BVHTree
D=Path(__file__).resolve().parent;sys.path.insert(0,str(D))
from material_contact import triangle_intersects
parser=argparse.ArgumentParser();parser.add_argument('--upper-frame',choices=['plane','source'],default='plane');parser.add_argument('--case',choices=['guide_suite','guide_shoulder_0.5','guide_shoulder_0.75','guide_shoulder_weights','guide_front_axilla','guide_front_support','guide_protraction']);options=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT=D/(options.case or ('guide_source_suite' if options.upper_frame=='source' else 'guide_suite'));manifest=json.loads((OUT/'manifest.json').read_text());base=json.loads((OUT/'base.json').read_text())
T=np.array(base['triangles']).reshape(-1,3);V=np.array(base['rest']).reshape(-1,3);N=len(V)
names=base['bone_names'];J=np.array(base['joints']);W=np.array(base['weights'])
arm=np.where(np.isin(J,[names.index(k+'_'+s) for s in 'lr' for k in ['upperarm','lowerarm']]),W,0).sum(1)>1e-8
face_sets=[set(t) for t in T]

def pairs(points):
 b=BVHTree.FromPolygons(points.tolist(),T.tolist(),all_triangles=True)
 return {(a,c) for a,c in b.overlap(b) if a<c and not(face_sets[a]&face_sets[c]) and triangle_intersects(points[T[a]],points[T[c]])}

rows=[]
for clip in manifest['clips']:
 key=clip['id'];Q=np.fromfile(OUT/clip['positions'],dtype='<f4').reshape(-1,N,3)
 P=np.fromfile(OUT/f'{key}.baseline.bin' if (OUT/'binding.json').exists() else D.parent/'v5_motion_pilot'/clip['positions'],dtype='<f4').reshape(-1,N,3)
 acts=np.array(clip['acts']);skin=np.fromfile(OUT/f'{key}.skin.bin',dtype='<f4').reshape(-1,len(names),4,4)
 samples=[];start=time.monotonic()
 for x in np.arange(0,len(Q)-.5,.5):
  f=int(x);g=min(f+1,len(Q)-1);t=x-f;q=Q[f]*(1-t)+Q[g]*t;p=P[f]*(1-t)+P[g]*t
  before=pairs(p);after=pairs(q);new=after-before
  samples.append({'frame':float(x),'phase':float(acts[f]*(1-t)+acts[g]*t),'total_pairs':len(after),'new_pairs':len(new),
                  'arm_pairs':sum(bool(arm[T[a]].any() or arm[T[b]].any()) for a,b in after)})
 delta=np.linalg.norm(np.diff(Q,axis=0),axis=2);speed=delta/np.diff(acts)[:,None]
 acceleration=np.linalg.norm(np.diff(Q,n=2,axis=0),axis=2)
 twists=json.loads((OUT/'kinematics.json').read_text());kr=next(c for c in twists['clips'] if c['id']==key)
 twist_jump={s:float(np.max(abs(np.diff([r[s]['twist_deg'] for r in kr['kinematics']])))) for s in 'lr'}
 row={'id':key,'samples':samples,'sample_count':len(samples),'max_new_pairs':max(r['new_pairs'] for r in samples),
      'max_arm_pairs':max(r['arm_pairs'] for r in samples),'max_vertex_step_mm':float(delta.max()*1000),
      'max_phase_speed_m':float(speed.max()),'max_second_difference_mm':float(acceleration.max()*1000),
      'max_twist_step_deg':twist_jump,'grip_exact':kr['grip_exact'],'stage':'pending visual and contact approval'}
 rows.append(row);print('AUDIT_GUIDE',key,{k:v for k,v in row.items() if k!='samples'},'seconds',round(time.monotonic()-start,1),flush=True)
report={'clips':rows,'playback_samples':sum(r['sample_count'] for r in rows),'approved':False,
        'note':'New-pair count uses the original 871-vertex surface, not subdivided duplicates. No automatic shape approval.'}
(OUT/'surface_audit.json').write_text(json.dumps(report,indent=2));print('GUIDE_AUDIT_DONE',report['playback_samples'],flush=True)
