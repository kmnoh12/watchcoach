"""Candidate arm skin with mesh-fitted pivots and calibrated elbow-plane motion.
Fixed bone lengths, one coherent skin pass, unchanged V5 rest and weights.
No uniform muscle scaling, global body correction or exercise-specific shapes.
"""
exec(compile((__import__('pathlib').Path(__file__).parent/'build.py').read_text().split('def unit')[0],__file__,'exec'))
import sys
sys.path.insert(0,str(D));from kinematics import two_bone,shoulder_arm,swing,rigid_rotation,continuous_twist
fit=json.loads((D/'anatomical_rest.json').read_text());Rnew=np.array(fit['rest_matrices']);working=json.loads((D/'working_rest.json').read_text());T=np.array(working['tris'],int)
def unit(v):return v/max(np.linalg.norm(v),1e-12)
def apply(m,p):return m[:3,:3]@p+m[:3,3]
def transform(rot,rest,posed):
 m=np.eye(4);m[:3,:3]=rot;m[:3,3]=posed-rot@rest;return m

def triangle_frame(s,e,w,previous=None):
 x=unit(w-s);pole=e-s-x*((e-s)@x)
 if np.linalg.norm(pole)<1e-7:
  if previous is None:raise ValueError('Initial straight source needs a reference frame')
  rot=swing(previous[:,0],x,previous[:,2]);pole=rot@previous[:,1];pole-=x*(pole@x)
 y=unit(pole);z=unit(np.cross(x,y));return np.stack([x,y,z],axis=1)

def dq_point(palette,vertex):
 real=np.zeros(4);dual=np.zeros(4)
 for j,weight in zip(J[vertex],W[vertex]):
  if weight<1e-8:continue
  m=palette[j];q=Matrix(m[:3,:3].tolist()).to_quaternion();qr=np.array(q);qd=np.array(Quaternion((0,*m[:3,3]))@q)*.5;sign=-1 if qr@real<0 else 1;real+=qr*weight*sign;dual+=qd*weight*sign
 norm=np.linalg.norm(real);real/=norm;dual/=norm;v=V[vertex];u=real[1:];a=real[0];d=dual[1:];b=dual[0]
 return v+2*np.cross(u,np.cross(u,v)+a*v)+2*(a*d-b*u+np.cross(u,d))

mask=np.zeros(N,bool)
for side,sign in [('l',1),('r',-1)]:
 weights=np.where(np.isin(J,[ni['upperarm_'+side],ni['lowerarm_'+side]]),W,0).sum(1)
 mask|=(weights>1e-8)&(V[:,0]*sign>.135)&(V[:,2]<1.475)
ids=np.flatnonzero(mask);rest_frames={}
for side in 'lr':
 u,l,h=[ni[p+'_'+side] for p in ['upperarm','lowerarm','hand']];rest_frames[side]=triangle_frame(*R[[u,l,h],:3,3])

def deform(pal,baseline,state,upper_frame="plane"):
 posed=pal.copy();report={};twists={}
 for side in 'lr':
  u,l,h=[ni[p+'_'+side] for p in ['upperarm','lowerarm','hand']];old_s,old_e,old_w=R[[u,l,h],:3,3];s0,e0,w0=Rnew[[u,l,h],:3,3]
  oldposed=[apply(pal[k],v) for k,v in zip([u,l,h],[old_s,old_e,old_w])];oldframe=triangle_frame(*oldposed,previous=state.get('frame_'+side,rest_frames[side]));state['frame_'+side]=oldframe
  motion=oldframe@rest_frames[side].T;rest_pole=e0-s0-unit(w0-s0)*((e0-s0)@unit(w0-s0));pole=motion@rest_pole
  s=apply(pal[ni['clavicle_'+side]],s0);w=apply(pal[h],w0);L1=np.linalg.norm(e0-s0);L2=np.linalg.norm(w0-e0);c=apply(pal[ni['clavicle_'+side]],Rnew[ni['clavicle_'+side],:3,3]);original_s=s.copy();s,e,p=shoulder_arm(c,s,w,L1,L2,pole,state.get('pole_'+side));state['pole_'+side]=p;clav_rot=swing(original_s-c,s-c);posed[ni['clavicle_'+side]]=transform(clav_rot,c,c)@pal[ni['clavicle_'+side]]
  source_rot=motion if upper_frame=="plane" else rigid_rotation(pal[u,:3,:3]);ru=swing(source_rot@(e0-s0),e-s,p)@source_rot;rl=swing(ru@(w0-e0),w-e,p)@ru;posed[u]=transform(ru,s0,s);posed[l]=transform(rl,e0,e)
  axis=unit(w-e);ref=unit(np.cross(e0-s0,w0-e0));angle,held=continuous_twist(axis,rl@ref,rigid_rotation(pal[h,:3,:3])@ref,state.get('twist_'+side));state['twist_'+side]=angle;twists[side]=(axis,angle,e,e0,w0,l)
  report[side]={'elbow':e.tolist(),'twist_deg':math.degrees(angle),'palm_held':held,'upper_length_error_mm':float(abs(np.linalg.norm(e-s)-L1)*1000),'lower_length_error_mm':float(abs(np.linalg.norm(w-e)-L2)*1000)}
 out=baseline.astype(float).copy()
 for i in ids:
  pp=posed.copy()
  for side,(axis,angle,e,e0,w0,l) in twists.items():
   if not np.any((J[i]==l)&(W[i]>1e-8)):continue
   along=float(np.clip((V[i]-e0)@(w0-e0)/np.sum((w0-e0)**2),0,1));along=along*along*(3-2*along);rot=np.array(Quaternion(Vector(axis),angle*along).to_matrix());pp[l,:3,:3]=rot@posed[l,:3,:3];pp[l,:3,3]=e-pp[l,:3,:3]@e0
  out[i]=dq_point(pp,i)
 return out,report,posed


# Complete arm influence domain; extra clavicle-only vertices receive only the
# clavicle delta, so unchanged torso skin is never replaced by a different method.
armj=[ni[k+'_'+s] for s in 'lr' for k in ['upperarm','lowerarm']]
mask=np.where(np.isin(J,armj),W,0).sum(1)>1e-8;ids=np.flatnonzero(mask)
identity=np.tile(np.eye(4),(len(names),1,1));rest,_,_=deform(identity,V,{})
assert np.max(abs(rest-V))<1e-8
state={};result=[];skins=[];audit=[]
for f,a in enumerate(A):
 pal=identity.copy();pal[:,:3]=a;out,row,new=deform(pal,P[f],state)
 for side in 'lr':
  j=ni['clavicle_'+side];weight=np.where(J==j,W,0).sum(1);extra=np.flatnonzero((weight>1e-8)&~mask)
  out[extra]+=(VH[extra]@(new[j]-pal[j]).T)[:,:3]*weight[extra,None]
 result.append(out);skins.append(new);audit.append(row)
np.asarray(result,dtype='<f4').tofile(D/'supported.positions.bin');np.asarray(skins,dtype='<f4').tofile(D/'supported.skin.bin')
from containment import TetVolume
volume=TetVolume.from_tetgen(D/'tetgen/v5_clean.1.node',D/'tetgen/v5_clean.1.ele')
assert np.max(abs(volume.points[:N]-V))<1e-7
anchors=[];anchor_tets=[];bary=[];anchor_targets=[]
for side in 'lr':
 for segment,start,end in [('upperarm','upperarm','lowerarm'),('lowerarm','lowerarm','hand')]:
  j=ni[segment+'_'+side];p0,p1=Rnew[[ni[start+'_'+side],ni[end+'_'+side]],:3,3]
  for t in [.15,.35,.55,.75,.9]:
   p=p0*(1-t)+p1*t;witness=volume.locate(p)
   if witness is None:continue
   tet,w=witness;anchors.append(p);anchor_tets.append(volume.tets[tet]);bary.append(w);anchor_targets.append([apply(m[j],p) for m in skins])
np.savez(D/'fem_inputs.npz',rest=volume.points,tets=volume.tets,surface=V,triangles=T,arm_mask=mask,
 baseline=P,guide=np.asarray(result),palettes=np.asarray(skins),root_palettes=A[:,ni['spine_03']],
 anchor_rest=np.asarray(anchors),anchor_tets=np.asarray(anchor_tets),anchor_bary=np.asarray(bary),anchor_targets=np.asarray(anchor_targets).transpose(1,0,2))
print('SUPPORTED_SKIN',len(result),'ARM',mask.sum(),'TETS',len(volume.tets),'ANCHORS',len(anchors))
