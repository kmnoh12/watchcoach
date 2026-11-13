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

def dq_point(palette,vertex,quaternion_state=None):
 real=np.zeros(4);dual=np.zeros(4)
 previous=quaternion_state.get(vertex) if quaternion_state is not None else None
 signed=np.zeros((len(J[vertex]),4))
 # Seed against the torso's common motion, not whichever influence happens
 # to be first in this vertex's weight list. At an elevated starting pose the
 # arm/clavicle pair can already span 180 degrees although both are on the
 # same anatomical side of the torso reference. This also makes reversed
 # exercise sources start on the same branch as forward sources.
 initial_reference=np.array(Matrix(palette[ni['spine_03'],:3,:3].tolist()).to_quaternion()) if quaternion_state is not None and previous is None else None
 for slot,(j,weight) in enumerate(zip(J[vertex],W[vertex])):
  if weight<1e-8:continue
  m=palette[j];q=Matrix(m[:3,:3].tolist()).to_quaternion();qr=np.array(q);qd=np.array(Quaternion((0,*m[:3,3]))@q)*.5
  # A quaternion and its negative encode the same rotation. Re-selecting the
  # shortest hemisphere against the other bones EVERY frame makes an axillary
  # blend jump when upper arm versus clavicle crosses 180 degrees. Choose the
  # initial branch once, then transport each influence from its prior frame.
  reference=previous[slot] if previous is not None else (initial_reference if initial_reference is not None else real)
  if previous is None and initial_reference is not None and names[j].startswith('lowerarm_'):
   # A deeply folded forearm may lie beyond the torso's quaternion cut even
   # though its elbow rotation relative to the upper arm is ordinary. Seed
   # the distal chain against its anatomical parent, not against the torso.
   side=names[j][-1];parent=np.array(Matrix(palette[ni['upperarm_'+side],:3,:3].tolist()).to_quaternion())
   if parent@initial_reference<0:parent=-parent
   reference=parent
  sign=-1 if qr@reference<0 else 1
  signed[slot]=qr*sign;real+=qr*weight*sign;dual+=qd*weight*sign
 if quaternion_state is not None:quaternion_state[vertex]=signed
 norm=np.linalg.norm(real);real/=norm;dual/=norm;v=V[vertex];u=real[1:];a=real[0];d=dual[1:];b=dual[0]
 return v+2*np.cross(u,np.cross(u,v)+a*v)+2*(a*d-b*u+np.cross(u,d))

mask=np.zeros(N,bool)
for side,sign in [('l',1),('r',-1)]:
 weights=np.where(np.isin(J,[ni['upperarm_'+side],ni['lowerarm_'+side]]),W,0).sum(1)
 mask|=(weights>1e-8)&(V[:,0]*sign>.135)&(V[:,2]<1.475)
ids=np.flatnonzero(mask);rest_frames={}
for side in 'lr':
 u,l,h=[ni[p+'_'+side] for p in ['upperarm','lowerarm','hand']];rest_frames[side]=triangle_frame(*R[[u,l,h],:3,3])

def deform(pal,baseline,state,upper_frame="plane",protraction_deg=0.,source_joints=None):
 posed=pal.copy();report={};twists={}
 for side in 'lr':
  u,l,h=[ni[p+'_'+side] for p in ['upperarm','lowerarm','hand']];old_s,old_e,old_w=R[[u,l,h],:3,3];s0,e0,w0=Rnew[[u,l,h],:3,3]
  oldposed=source_joints['lr'.index(side)] if source_joints is not None else [apply(pal[k],v) for k,v in zip([u,l,h],[old_s,old_e,old_w])];oldframe=triangle_frame(*oldposed,previous=state.get('frame_'+side,rest_frames[side]))
  if source_joints is not None:
   source_rotation=rigid_rotation(pal[u,:3,:3])
   if 'frame_'+side in state:
    predicted=source_rotation@state['source_rotation_'+side].T@state['frame_'+side]
    transport=swing(predicted[:,0],oldframe[:,0],predicted[:,2]);reference=transport@predicted[:,1]
    if oldframe[:,1]@reference<0:oldframe[:,1:]*=-1
    # Point-cache joint centers cannot determine an elbow plane near a
    # straight arm. Transport its last reliable frame using the rigid upper
    # patch, then smoothly recover the measured plane as bend returns.
    ss,ee,ww=oldposed;axis=unit(ww-ss);bend=np.linalg.norm(ee-ss-axis*((ee-ss)@axis))
    trust=float(np.clip((bend-.015)/.030,0,1));trust=trust*trust*(3-2*trust)
    yy=unit(reference*(1-trust)+oldframe[:,1]*trust)
    oldframe=np.stack([axis,yy,unit(np.cross(axis,yy))],axis=1)
   state['source_rotation_'+side]=source_rotation
  state['frame_'+side]=oldframe
  motion=oldframe@rest_frames[side].T;rest_pole=e0-s0-unit(w0-s0)*((e0-s0)@unit(w0-s0));source_rot=motion if upper_frame in {"plane","plane_source_roll"} else rigid_rotation(pal[u,:3,:3]);pole=source_rot@rest_pole
  s=apply(pal[ni['clavicle_'+side]],s0);w=apply(pal[h],w0);L1=np.linalg.norm(e0-s0);L2=np.linalg.norm(w0-e0);c=apply(pal[ni['clavicle_'+side]],Rnew[ni['clavicle_'+side],:3,3]);original_s=s.copy()
  # Isolated kinematic diagnostic. The source clavicle is otherwise nearly
  # torso-fixed throughout bench flexion; preserve its length and the grip.
  active_protraction=0.
  if protraction_deg:
   body_rotation=rigid_rotation(pal[ni['spine_03'],:3,:3])
   from clavicle_protraction import protract
   s,active_protraction=protract(c,s,oldposed[1]-oldposed[0],old_e-old_s,body_rotation,protraction_deg,side)
  s,e,p=shoulder_arm(c,s,w,L1,L2,pole,state.get('pole_'+side),extension_margin=state.get('extension_margin',0.));state['pole_'+side]=p;clav_rot=swing(original_s-c,s-c);posed[ni['clavicle_'+side]]=transform(clav_rot,c,c)@pal[ni['clavicle_'+side]]
  # Joint positions determine an elbow plane, not the upper arm's axial roll.
  # Repositioned grips can change that plane without rotating the shoulder.
  # This mode keeps the measured rigid roll while retaining the plane's IK pole.
  axial=rigid_rotation(pal[u,:3,:3]) if upper_frame=="plane_source_roll" else source_rot
  ru=swing(axial@(e0-s0),e-s,p)@axial;rl=swing(ru@(w0-e0),w-e,p)@ru;posed[u]=transform(ru,s0,s);posed[l]=transform(rl,e0,e)
  axis=unit(w-e);ref=unit(np.cross(e0-s0,w0-e0));angle,held=continuous_twist(axis,rl@ref,rigid_rotation(pal[h,:3,:3])@ref,state.get('twist_'+side));state['twist_'+side]=angle;twists[side]=(axis,angle,e,e0,w0,l)
  report[side]={'elbow':e.tolist(),'protraction_input_deg':active_protraction,'shoulder_shift_mm':float(np.linalg.norm(s-original_s)*1000),'twist_deg':math.degrees(angle),'palm_held':held,'upper_length_error_mm':float(abs(np.linalg.norm(e-s)-L1)*1000),'lower_length_error_mm':float(abs(np.linalg.norm(w-e)-L2)*1000)}
 out=baseline.astype(float).copy()
 skin_quaternions=state.setdefault('skin_quaternions',{})
 for i in ids:
  pp=posed.copy()
  for side,(axis,angle,e,e0,w0,l) in twists.items():
   if not np.any((J[i]==l)&(W[i]>1e-8)):continue
   along=float(np.clip((V[i]-e0)@(w0-e0)/np.sum((w0-e0)**2),0,1));along=along*along*(3-2*along);rot=np.array(Quaternion(Vector(axis),angle*along).to_matrix());pp[l,:3,:3]=rot@posed[l,:3,:3];pp[l,:3,3]=e-pp[l,:3,:3]@e0
  out[i]=dq_point(pp,i,skin_quaternions)
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
