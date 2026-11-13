"""Visual extension and flexion biceps relief, not volume enforcement.
Target: the medial/anterior biceps peak actually seen in the user's camera
(original vertex142 and its mirrored neighborhood), not the rear deltoid.
Original rest and input weights remain untouched. Natural overlaps are allowed.
"""
import math
import numpy as np

def smoothstep(t):
 t=np.clip(t,0.,1.);return t*t*(3-2*t)

def correct(rest,points,joints,weights,names,rest_bones,palette,max_relief=.048):
 rest=np.asarray(rest,float);out=np.asarray(points,float).copy();factors=np.zeros(len(rest));rows=[]
 body=palette[names.index('spine_03'),:3,:3];body_front=body@np.array([0.,-1.,0.]);body_front/=np.linalg.norm(body_front)
 body_up=body@np.array([0.,0.,1.]);body_up/=np.linalg.norm(body_up)
 for side,sign in [('l',1),('r',-1)]:
  u,l,h=[names.index(k+'_'+side) for k in ['upperarm','lowerarm','hand']]
  s,e,w=rest_bones[[u,l,h],:3,3];axis=e-s;axis/=np.linalg.norm(axis)
  ps=palette[u,:3,:3]@s+palette[u,:3,3];pe=palette[l,:3,:3]@e+palette[l,:3,3];pw=palette[h,:3,:3]@w+palette[h,:3,3]
  upper=pe-ps;upper/=np.linalg.norm(upper);lower=pw-pe;lower/=np.linalg.norm(lower)
  forward=max(0.,float(upper@body_front));extension=float(smoothstep(((upper@lower)-math.cos(math.radians(100)))/(math.cos(math.radians(20))-math.cos(math.radians(100)))))
  raised=max(0.,float(upper@body_up))
  activation=float(smoothstep((min(1.,forward*forward+raised*raised)*extension)/.85))
  upper_weight=np.where(joints==u,weights,0).sum(1)
  distal=np.where(np.isin(joints,[l,h]),weights,0).sum(1)
  along=np.sum((rest-s)*axis,axis=1);radial=rest-s-along[:,None]*axis
  # The medial/anterior upper-arm peak, explicitly excluding the outer/rear arm.
  outward=np.array([float(sign),0.,0.]);outward-=axis*(axis@outward);outward/=np.linalg.norm(outward)
  medial_depth=-np.sum(radial*outward,axis=1)
  front=radial[:,1]<-.025;medial=medial_depth>0
  # Concentrate relief at the axillary end, leaving the biceps belly convex.
  # The previous midpoint-centred field flattened the whole visible biceps.
  center=rest[138]*[sign,1,1]
  distance=np.linalg.norm(rest-center,axis=1)
  fraction=along/np.linalg.norm(e-s)
  falloff=np.exp(-.5*(distance/.095)**2)*np.exp(-.5*((fraction-.28)/.20)**2)
  falloff*=smoothstep((.85-fraction)/.40)
  eligible=(upper_weight>.5)&(distal<.01)&front&medial&(rest[:,0]*sign>0)&(distance<.16)
  strength=activation*falloff*smoothstep((upper_weight-.35)/.45)
  strength[~eligible]=0
  # Preserve a convex belly, with modest additional relief at its peak.
  # Axilla relief remains stronger; neither the rest mesh nor elbow is scaled.
  belly_distance=np.linalg.norm(rest-rest[142]*[sign,1,1],axis=1)
  belly=activation*np.exp(-.5*((fraction-.50)/.12)**2)*np.exp(-.5*(belly_distance/.10)**2)*smoothstep((upper_weight-.35)/.45)
  belly[~eligible]=0
  # Folded-arm relief generalizes goblet_axilla's small anterior/medial
  # shell patch. Fade out completely below 40 degrees of elbow flexion;
  # straight-arm poses retain the existing extension correction exactly.
  flexion=float(smoothstep((math.cos(math.radians(40))-float(upper@lower))/(math.cos(math.radians(40))-math.cos(math.radians(100)))))
  folded=flexion*.024*np.exp(-.5*((fraction-.29)/.13)**2)
  folded_eligible=(upper_weight>.5)&(distal<.01)&front&medial&(rest[:,0]*sign>0)&(fraction>.12)&(fraction<.7)
  if side=='l':
   folded_left=np.flatnonzero(folded_eligible)
  else:
   # The original right axillary weights differ from the left. Select the
   # mirrored surface patch so that the same visual rule reaches both sides.
   folded_eligible[:]=False
   for i in folded_left:
    folded_eligible[np.argmin(np.linalg.norm(rest-rest[i]*[-1,1,1],axis=1))]=True
  folded[~folded_eligible]=0
  radius_all=np.linalg.norm(radial,axis=1)
  folded=np.minimum(folded,.35*radius_all)
  ids=np.flatnonzero((strength>0)|(folded>0))
  if len(ids):
   # The user's black contour marks a surface bulge: press that local shell
   # inward, rather than translating it sideways along the camera depth.
   radius=np.linalg.norm(radial[ids],axis=1)
   inward=-radial[ids]/radius[:,None]
   world=np.einsum('ij,nj->ni',palette[u,:3,:3],inward)
   amount=np.minimum(max_relief*strength[ids]+.010*belly[ids]+folded[ids],.65*radius)
   out[ids]+=world*amount[:,None];factors[ids]=np.maximum(strength[ids],folded[ids]/.024)
  rows.append({'side':side,'activation':activation,'flexion':flexion,'forward':forward,'raised':raised,'extension':extension,'vertices':ids.tolist()})
 return out,factors,rows
