"""Identify the user's FRONT biceps/axilla fold, distinct from rear deltoid.
Original guide versus one isolated six-vertex DQ/LBS diagnostic, not adoption.
"""
from pathlib import Path
import sys,json,argparse
import bpy,numpy as np
from mathutils import Vector,Matrix
D=Path(__file__).resolve().parent;SOURCE=D/'guide_suite';OUT=SOURCE/'front_axilla';OUT.mkdir(exist_ok=True)
b=json.loads((SOURCE/'base.json').read_text());V=np.array(b['rest']).reshape(-1,3);T=np.array(b['triangles']).reshape(-1,3);J=np.array(b['joints']);W=np.array(b['weights']);names=b['bone_names'];Q=np.fromfile(SOURCE/'flat_bench_press.positions.bin',dtype='<f4').reshape(-1,len(V),3);S=np.fromfile(SOURCE/'flat_bench_press.skin.bin',dtype='<f4').reshape(-1,len(names),4,4)
# Left front crease and proximal biceps, explicitly y<0 in the rest body.
ids=np.array([117,118,128,138,145,151]);assert (V[ids,1]<0).all()
rear=np.array([135,147,152]);assert (V[rear,1]>0).all()
parser=argparse.ArgumentParser();parser.add_argument('--orientation',action='store_true');parser.add_argument('--bench',action='store_true');options=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
frame=32;P=Q[frame].copy();alternative=P.copy()
for i in ids:
 alternative[i]=sum(w*(S[frame,k,:3,:3]@V[i]+S[frame,k,:3,3]) for k,w in zip(J[i],W[i]))
if options.orientation:
 alternative=np.fromfile(D/'front_orientation_case/frame32.positions.bin',dtype='<f4').reshape(P.shape)
 OUT=D/'front_orientation_case';OUT.mkdir(exist_ok=True)
if options.bench:
 alternative=np.fromfile(D/'front_orientation_bench/flat_bench_press.positions.bin',dtype='<f4').reshape(Q.shape)[frame]
 OUT=D/'front_orientation_bench/front_axilla';OUT.mkdir(exist_ok=True)
metrics=[]
for i in ids:
 metrics.append({'vertex':int(i),'rest_xyz':V[i].tolist(),'dq_to_lbs_mm':float(np.linalg.norm(P[i]-alternative[i])*1000),'weights':[(names[k],float(w)) for k,w in zip(J[i],W[i]) if w>1e-8]})
bpy.ops.wm.read_factory_settings(use_empty=True);sc=bpy.context.scene
sc.render.engine='BLENDER_WORKBENCH';sc.render.resolution_x=900;sc.render.resolution_y=900;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG'
sc.world=bpy.data.worlds.new('World');sc.world.color=(.09,.09,.09);sc.display.shading.light='STUDIO';sc.display.shading.show_cavity=True;sc.display.shading.cavity_type='BOTH';sc.display.shading.color_type='MATERIAL';sc.view_settings.view_transform='Standard'
for name,color in [('Body',(.58,.64,.68,1)),('FrontFold',(1,.55,.12,1)),('RearShoulder',(.3,.4,.5,1))]:
 mat=bpy.data.materials.new(name);mat.diffuse_color=color
me=bpy.data.meshes.new('FrontFoldDiagnosis');me.from_pydata(P.tolist(),[],T.tolist());me.update();ob=bpy.data.objects.new('FrontFoldDiagnosis',me);sc.collection.objects.link(ob)
for mat in bpy.data.materials:me.materials.append(mat)
for poly in me.polygons:
 if np.isin(T[poly.index],ids).any():poly.material_index=1
 elif np.isin(T[poly.index],rear).any():poly.material_index=2
cam=bpy.data.objects.new('ReviewCamera',bpy.data.cameras.new('ReviewCamera'));sc.collection.objects.link(cam);sc.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=.52
rot=S[frame,names.index('spine_03'),:3,:3];u,_,vt=np.linalg.svd(rot);rot=u@vt
center=P[ids].mean(0)
for view,v in [('front',[.35,-1.,.2]),('inner',[-.7,-1.,.2]),('side',[1.,-.3,.15])]:
 z=rot@np.array(v);z/=np.linalg.norm(z);up=rot@np.array([0.,0,1.]);x=np.cross(up,z);x/=np.linalg.norm(x);y=np.cross(z,x)
 cam.location=Vector(center)+Vector(z)*3;cam.rotation_euler=Matrix(np.stack([x,y,z],axis=1).tolist()).to_euler()
 for kind,points in [('guide',P),('front_only_linear_diagnostic',alternative)]:
  me.vertices.foreach_set('co',points.ravel());me.update();sc.render.filepath=str(OUT/f'{kind}_{view}.png');bpy.ops.render.render(write_still=True)
(OUT/'diagnosis.json').write_text(json.dumps({'target':'FRONT proximal biceps/axilla fold. Rear deltoid measurements from earlier response do NOT answer this target.','front_ids':ids.tolist(),'excluded_rear_ids':rear.tolist(),'metrics':metrics,'stage':'diagnosis only; no correction adopted'},indent=2))
print('FRONT_AXILLA_DIAGNOSIS',metrics,flush=True)
