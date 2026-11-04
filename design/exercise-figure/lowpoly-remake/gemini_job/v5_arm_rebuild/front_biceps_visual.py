"""Visual forward-extension biceps relief, not collision/volume enforcement.
Target: the medial/anterior biceps peak actually seen in the user's camera
(original vertex142 and its mirrored neighborhood), not the rear deltoid.
Original rest and input weights remain untouched. Natural overlaps are allowed.
"""
import math
import numpy as np

def smoothstep(t):
 t=np.clip(t,0.,1.);return t*t*(3-2*t)

def correct(rest,points,joints,weights,names,rest_bones,palette,max_relief=.020):
 rest=np.asarray(rest,float);out=np.asarray(points,float).copy();factors=np.zeros(len(rest));rows=[]
 body=palette[names.index('spine_03'),:3,:3];body_front=body@np.array([0.,-1.,0.]);body_front/=np.linalg.norm(body_front)
 for side,sign in [('l',1),('r',-1)]:
  u,l,h=[names.index(k+'_'+side) for k in ['upperarm','lowerarm','hand']]
  s,e,w=rest_bones[[u,l,h],:3,3];axis=e-s;axis/=np.linalg.norm(axis)
  ps=palette[u,:3,:3]@s+palette[u,:3,3];pe=palette[l,:3,:3]@e+palette[l,:3,3];pw=palette[h,:3,:3]@w+palette[h,:3,3]
  upper=pe-ps;upper/=np.linalg.norm(upper);lower=pw-pe;lower/=np.linalg.norm(lower)
  forward=max(0.,float(upper@body_front));extension=float(smoothstep(((upper@lower)-math.cos(math.radians(100)))/(math.cos(math.radians(20))-math.cos(math.radians(100)))))
  activation=float(smoothstep((forward*forward*extension)/.85))
  upper_weight=np.where(joints==u,weights,0).sum(1)
  distal=np.where(np.isin(joints,[l,h]),weights,0).sum(1)
  along=np.sum((rest-s)*axis,axis=1);radial=rest-s-along[:,None]*axis
  # The medial/anterior upper-arm peak, explicitly excluding the outer/rear arm.
  outward=np.array([float(sign),0.,0.]);outward-=axis*(axis@outward);outward/=np.linalg.norm(outward)
  medial_depth=-np.sum(radial*outward,axis=1)
  front=radial[:,1]<-.025;medial=medial_depth>0
  center=rest[142]*[sign,1,1]
  distance=np.linalg.norm(rest-center,axis=1)
  falloff=np.exp(-.5*(distance/.075)**2)
  eligible=(upper_weight>.5)&(distal<.01)&front&medial&(rest[:,0]*sign>0)&(distance<.16)
  strength=activation*falloff*np.clip((upper_weight-.4)/.5,0,1)
  strength[~eligible]=0
  ids=np.flatnonzero(strength>0)
  if len(ids):
   # Reduce the chestward protrusion only. Preserve the anterior muscle
   # thickness rather than radially shrinking the biceps toward its bone.
   world=palette[u,:3,:3]@outward
   amount=np.minimum(max_relief*strength[ids],.7*medial_depth[ids])
   out[ids]+=world[None,:]*amount[:,None];factors[ids]=strength[ids]
  rows.append({'side':side,'activation':activation,'forward':forward,'extension':extension,'vertices':ids.tolist()})
 return out,factors,rows
