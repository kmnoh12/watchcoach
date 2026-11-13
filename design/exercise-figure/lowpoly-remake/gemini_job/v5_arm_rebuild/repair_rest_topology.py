"""Repair only collinear T-junction triangles; original mesh files untouched.
No vertices/weights are changed. A neighboring triangle is split at an existing
edge vertex, replacing a near-zero-area face without changing the silhouette.
"""
from pathlib import Path
import json,numpy as np
D=Path(__file__).resolve().parent;meta=json.loads((D.parent/'v5_joint_fit/mesh_data.json').read_text());V=np.array([[x,-z,y] for x,y,z in meta['verts']],float);T=np.array(meta['tris'],int);faces=[list(map(int,t)) for t in T];repairs=[]
while True:
 found=None
 for i,tri in enumerate(faces):
  p=V[tri];lengths=np.linalg.norm(np.roll(p,-1,axis=0)-p,axis=1);k=int(np.argmax(lengths));a,b=tri[k],tri[(k+1)%3];mid=tri[(k+2)%3];axis=V[b]-V[a];t=float((V[mid]-V[a])@axis/(axis@axis));height=float(np.linalg.norm(V[mid]-V[a]-axis*t))
  if 1e-5<t<1-1e-5 and height<1e-7:
   neighbors=[j for j,f in enumerate(faces) if j!=i and a in f and b in f]
   if len(neighbors)!=1:raise ValueError('Ambiguous degenerate-edge neighborhood')
   j=neighbors[0];f=faces[j];q=next(k for k in range(3) if {f[k],f[(k+1)%3]}=={a,b});u,v,w=f[q],f[(q+1)%3],f[(q+2)%3];found=(i,j,mid,u,v,w,height);break
 if found is None:break
 i,j,mid,u,v,w,height=found;old=[faces[i],faces[j]];new=[[u,mid,w],[mid,v,w]];faces=[f for k,f in enumerate(faces) if k not in (i,j)]+new;repairs.append({'removed':old,'replacement':new,'edge_vertex':mid,'surface_offset_m':height})
T2=np.array(faces,int);edges=np.sort(np.concatenate([T2[:,[0,1]],T2[:,[1,2]],T2[:,[2,0]]]),axis=1);_,counts=np.unique(edges,axis=0,return_counts=True);assert np.all(counts==2)
area=np.linalg.norm(np.cross(V[T2[:,1]]-V[T2[:,0]],V[T2[:,2]]-V[T2[:,0]]),axis=1)/2;assert area.min()>1e-12
out=D/'tetgen';out.mkdir(exist_ok=True)
with (out/'v5_clean.poly').open('w') as f:
 f.write(f'{len(V)} 3 0 0\n')
 for i,p in enumerate(V):f.write(str(i)+' '+' '.join(map(str,p))+'\n')
 f.write(f'{len(T2)} 0\n')
 for tri in T2:f.write('1 0\n3 '+' '.join(map(str,tri))+'\n')
 f.write('0\n0\n')
report={'vertices_unchanged':True,'weights_unchanged':True,'original_files_unchanged':True,'triangles_before':len(T),'triangles_after':len(T2),'repairs':repairs,'all_edges_two_faces':True,'minimum_area_m2':float(area.min())};(D/'rest_topology_repair.json').write_text(json.dumps(report,indent=2));(D/'working_rest.json').write_text(json.dumps({'verts':V.tolist(),'tris':T2.tolist(),'weights':meta['weights']}));print(json.dumps(report))
