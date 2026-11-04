"""Render original guide candidates at start/middle/end without deformation edits."""
from pathlib import Path
import sys,json,argparse
import bpy,numpy as np
from mathutils import Vector,Matrix
D=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--case',choices=['guide_suite','guide_shoulder_0.5','guide_shoulder_0.75','guide_shoulder_weights','guide_front_axilla','guide_front_support','guide_protraction'],default='guide_suite');options=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT=D/options.case;REVIEW=OUT/'review';REVIEW.mkdir(exist_ok=True)
base=json.loads((OUT/'base.json').read_text());T=np.array(base['triangles']).reshape(-1,3);N=base['vertices'];names=base['bone_names']
manifest=json.loads((OUT/'manifest.json').read_text());audit=json.loads((OUT/'surface_audit.json').read_text())
bpy.ops.wm.read_factory_settings(use_empty=True);sc=bpy.context.scene
sc.render.engine='BLENDER_WORKBENCH';sc.render.resolution_x=720;sc.render.resolution_y=720;sc.render.resolution_percentage=100
sc.render.image_settings.file_format='PNG';sc.world=bpy.data.worlds.new('World');sc.world.color=(.09,.09,.09)
sc.display.shading.light='STUDIO';sc.display.shading.show_cavity=True;sc.display.shading.cavity_type='BOTH';sc.display.shading.color_type='OBJECT';sc.view_settings.view_transform='Standard'
me=bpy.data.meshes.new('GuideBody');me.from_pydata(np.array(base['rest']).reshape(-1,3).tolist(),[],T.tolist());me.update()
ob=bpy.data.objects.new('GuideBody',me);sc.collection.objects.link(ob);ob.color=(.62,.68,.72,1)
cam=bpy.data.objects.new('ReviewCamera',bpy.data.cameras.new('ReviewCamera'));sc.collection.objects.link(cam);sc.camera=cam;cam.data.type='ORTHO'
reports=[]
sys.path.insert(0,'/Users/kmnoh/.agents/skills/blender-asset-qa/scripts');import qa_check
for clip in manifest['clips']:
 key=clip['id'];Q=np.fromfile(OUT/clip['positions'],dtype='<f4').reshape(-1,N,3)
 skin=np.fromfile(OUT/f'{key}.skin.bin',dtype='<f4').reshape(-1,len(names),4,4)
 ar=next(r for r in audit['clips'] if r['id']==key);worst=max(ar['samples'],key=lambda r:r['new_pairs'])['frame'];worst=int(round(worst))
 frames=sorted(set([0,len(Q)//2,len(Q)-1,worst]))
 for f in frames:
  me.vertices.foreach_set('co',Q[f].ravel());me.update()
  rot=skin[f,names.index('spine_03'),:3,:3];u,_,vt=np.linalg.svd(rot);rot=u@vt
  for view,vector in [('oblique',[.8,-1.,.55]),('reverse',[-.8,1.,.55])]:
   # Body-local review: the same anatomical orientation as the user's reference.
   front=rot@np.array(vector);up=rot@np.array([0,0,1.]);z=front/np.linalg.norm(front)
   x=np.cross(up,z);x/=np.linalg.norm(x);y=np.cross(z,x)
   ids=np.flatnonzero((np.array(base['rest']).reshape(-1,3)[:,2]>1.02))
   local=Q[f,ids]@np.stack([x,y,z],axis=1);low=local.min(0);high=local.max(0)
   center=np.stack([x,y,z],axis=1)@((low+high)*.5)
   cam.location=Vector(center)+Vector(z)*3;cam.rotation_euler=Matrix(np.stack([x,y,z],axis=1).tolist()).to_euler();cam.data.ortho_scale=float(max((high-low)[:2])*1.12)
   sc.render.filepath=str(REVIEW/f'{key}_{f}_{view}.png');bpy.ops.render.render(write_still=True)
  if f==worst:
   reports.append({'id':key,'frame':f,'asset_qa':qa_check.run(objects=['GuideBody'],profile='render')})
   ob.show_wire=True;ob.show_all_edges=True;sc.render.filepath=str(REVIEW/f'{key}_{f}_wire.png');bpy.ops.render.render(write_still=True);ob.show_wire=False
(REVIEW/'asset_qa.json').write_text(json.dumps(reports,indent=2,default=lambda x:x.item()))
print('GUIDE_RENDERS_READY',len(reports),flush=True)
