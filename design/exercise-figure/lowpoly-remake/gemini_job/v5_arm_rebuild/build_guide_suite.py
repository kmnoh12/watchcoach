"""Apply the existing shape guide to the five saved source pilots, offline only.
Preserve source phase arrays, original resting physique/weights and grip vertices.
This exports REVIEW candidates; it never installs or marks a clip approved.
"""
from pathlib import Path
import argparse,hashlib,json,time,sys
import numpy as np
D=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--upper-frame',choices=['plane','source'],default='plane');parser.add_argument('--protraction-deg',type=float,default=0.)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
if not np.isfinite(args.protraction_deg) or not 0<=args.protraction_deg<=20:raise ValueError('Diagnostic protraction must be within 0..20 degrees')
source=(D/'supported_skin.py').read_text().split('# Complete arm influence domain;')[0]
ns={'__file__':str(D/'supported_skin.py'),'__name__':'guide_suite'}
exec(compile(source,str(D/'supported_skin.py'),'exec'),ns)
V,T,J,W,names,ni,N=[ns[k] for k in ['V','T','J','W','names','ni','N']]
armj=[ni[k+'_'+s] for s in 'lr' for k in ['upperarm','lowerarm']]
mask=np.where(np.isin(J,armj),W,0).sum(1)>1e-8
ns['mask']=mask;ns['ids']=np.flatnonzero(mask)
identity=np.tile(np.eye(4),(len(names),1,1))
rest,_,_=ns['deform'](identity,V,{},protraction_deg=args.protraction_deg)
rest_error=float(np.linalg.norm(rest-V,axis=1).max()*1000)
assert rest_error<1e-5
OLD=ns['OLD'];manifest=json.loads((OLD/'manifest.json').read_text());OUT=D/('guide_protraction' if args.protraction_deg else ('guide_source_suite' if args.upper_frame=='source' else 'guide_suite'));OUT.mkdir(exist_ok=True)
base={'vertices':N,'triangles':T.ravel().tolist(),'rest':V.ravel().tolist(),'bone_names':names,
      'joints':J.tolist(),'weights':W.tolist()}
(OUT/'base.json').write_text(json.dumps(base,separators=(',',':')))
clips=[];reports=[]
reference=np.load(D/'refined_fem_inputs.npz')['guide'][:,:N]
for clip in manifest['clips']:
    key=clip['id'];start=time.monotonic()
    A=np.fromfile(OLD/f'{key}.skin.bin',dtype='<f4').reshape(-1,len(names),3,4)
    P=np.fromfile(OLD/clip['positions'],dtype='<f4').reshape(-1,N,3)
    assert len(A)==len(P)==len(clip['acts'])
    state={};Q=[];rows=[];skins=[]
    for f,a in enumerate(A):
        pal=identity.copy();pal[:,:3]=a
        points,row,new=ns['deform'](pal,P[f],state,upper_frame=args.upper_frame,protraction_deg=args.protraction_deg)
        for side in 'lr':
            j=ni['clavicle_'+side];weight=np.where(J==j,W,0).sum(1)
            extra=np.flatnonzero((weight>1e-8)&~mask)
            points[extra]+=(ns['VH'][extra]@(new[j]-pal[j]).T)[:,:3]*weight[extra,None]
        Q.append(points);rows.append(row);skins.append(new)
    Q=np.asarray(Q,dtype='<f4');assert np.isfinite(Q).all()
    # The guide also follows geometric clavicle changes outside the arm domain.
    changed=np.any(Q!=P,axis=(0,2))
    hands=np.where(np.isin(J,[ni[k+'_'+s] for s in 'lr' for k in ['hand','thumb_01','thumb_02','thumb_03','index_01','index_02','index_03','middle_01','middle_02','middle_03','ring_01','ring_02','ring_03','pinky_01','pinky_02','pinky_03']]),W,0).sum(1)>.999
    grip_exact=bool(np.array_equal(Q[:,hands],P[:,hands]));assert grip_exact
    if key=='flat_bench_press' and args.upper_frame=='plane' and not args.protraction_deg:
        reference_error=float(np.linalg.norm(Q-reference,axis=2).max()*1000)
        assert reference_error<.001,reference_error
    else:reference_error=None
    payload={'machine':key,'acts':clip['acts'],'tris':T.ravel().tolist(),'frames':Q.reshape(len(Q),-1).tolist()}
    (OUT/f'{key}.json').write_text(json.dumps(payload,separators=(',',':')))
    Q.tofile(OUT/f'{key}.positions.bin')
    np.asarray(skins,dtype='<f4').tofile(OUT/f'{key}.skin.bin')
    report={'id':key,'frames':len(Q),'changed_vertices':int(changed.sum()),'grip_exact':grip_exact,
            'same_accepted_view_guide_max_error_mm':reference_error,
            'max_bone_length_error_mm':max(v[k] for row in rows for v in row.values() for k in ['upper_length_error_mm','lower_length_error_mm']),
            'kinematics':rows,'source_skin_sha256':hashlib.sha256((OLD/f'{key}.skin.bin').read_bytes()).hexdigest(),
            'stage':'review only; surface contact and full-motion appearance not approved'}
    reports.append(report);clips.append({**clip,'positions':f'{key}.positions.bin','json':f'{key}.json','approved':False})
    print('GUIDE_CLIP',key,len(Q),'GRIP_EXACT',grip_exact,'elapsed',round(time.monotonic()-start,2),flush=True)
(OUT/'manifest.json').write_text(json.dumps({'model':'V5 shape guide review','base':'base.json','clips':clips,'stage':'unapproved review','upper_frame':args.upper_frame,'protraction_deg':args.protraction_deg,'rest_error_mm':rest_error},ensure_ascii=False,indent=2))
(OUT/'kinematics.json').write_text(json.dumps({'rest_error_mm':rest_error,'clips':reports},indent=2))
print('GUIDE_SUITE_READY',len(clips),'REST_ERROR_MM',rest_error,flush=True)
