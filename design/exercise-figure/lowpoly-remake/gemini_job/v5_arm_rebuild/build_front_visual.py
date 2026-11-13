from pathlib import Path
import argparse,json,numpy as np
from front_biceps_visual import correct
D=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--pilot-set',choices=['core','overhead'],default='core');args=parser.parse_args()
SOURCE=D/('guide_overhead' if args.pilot_set=='overhead' else 'guide_suite');OUT=D/('guide_front_overhead' if args.pilot_set=='overhead' else 'guide_front_visual');OUT.mkdir(exist_ok=True)
b=json.loads((SOURCE/'base.json').read_text());V=np.array(b['rest']).reshape(-1,3);J=np.array(b['joints']);W=np.array(b['weights']);names=b['bone_names'];R=np.array(json.loads((D/'anatomical_rest.json').read_text())['rest_matrices'])
identity=np.tile(np.eye(4),(len(names),1,1));rest,f,_=correct(V,V,J,W,names,R,identity);assert np.array_equal(rest,V)
m=json.loads((SOURCE/'manifest.json').read_text());reports=[]
for c in m['clips']:
 P=np.fromfile(SOURCE/c['positions'],dtype='<f4').reshape(-1,len(V),3);S=np.fromfile(SOURCE/f'{c["id"]}.skin.bin',dtype='<f4').reshape(-1,len(names),4,4);Q=[];rows=[];domain=np.zeros(len(V),bool)
 for p,s in zip(P,S):
  q,f,r=correct(V,p,J,W,names,R,s);Q.append(q);rows.append(r);domain|=f>0
 Q=np.asarray(Q,dtype='<f4');assert np.array_equal(Q[:,~domain],P[:,~domain]);Q.tofile(OUT/c['positions']);(OUT/f'{c["id"]}.skin.bin').write_bytes((SOURCE/f'{c["id"]}.skin.bin').read_bytes())
 (OUT/c['json']).write_text(json.dumps({'machine':c['id'],'acts':c['acts'],'tris':b['triangles'],'frames':Q.reshape(len(Q),-1).tolist()},separators=(',',':')))
 reports.append({'id':c['id'],'domain':np.flatnonzero(domain).tolist(),'max_delta_mm':float(np.linalg.norm(Q-P,axis=2).max()*1000),'poses':rows});print('VISUAL_RELIEF',c['id'],reports[-1]['domain'],reports[-1]['max_delta_mm'],flush=True)
m.update(stage='unapproved visual comparison',review_label='앞이두 연결부 완화 비교');(OUT/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2));(OUT/'base.json').write_bytes((SOURCE/'base.json').read_bytes());(OUT/'visual_report.json').write_text(json.dumps(reports,indent=2));(OUT/'kinematics.json').write_bytes((SOURCE/'kinematics.json').read_bytes())
