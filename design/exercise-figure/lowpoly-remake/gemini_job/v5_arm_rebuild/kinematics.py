"""Scale-free arm kinematics with explicit degeneracy and continuity handling.
Pure NumPy; exercise-independent. Does not certify skin/tissue deformation.
"""
import math
import numpy as np

class PoseError(ValueError):
    pass

def _v(x):
    x=np.asarray(x,dtype=float)
    if x.shape!=(3,) or not np.isfinite(x).all():raise PoseError('Expected a finite 3D point/vector')
    return x

def normalize(x):
    x=_v(x);length=float(np.linalg.norm(x))
    if length<1e-12:raise PoseError('Zero-length direction')
    return x/length

def two_bone(shoulder,wrist,upper_length,lower_length,pole,previous_pole=None):
    """Preserve both lengths, including straight/folded limits; never stretch.
    A continuous projected pole selects the elbow plane. Unreachable targets
    are errors rather than silently stretching skin or clamping a square root.
    """
    s,w=_v(shoulder),_v(wrist);L1,L2=float(upper_length),float(lower_length)
    if not np.isfinite([L1,L2]).all() or min(L1,L2)<=0:raise PoseError('Invalid bone lengths')
    delta=w-s;d=float(np.linalg.norm(delta));tol=1e-9*max(1,L1+L2)
    if d>L1+L2+tol or d<abs(L1-L2)-tol:raise PoseError('Grip target unreachable at original bone lengths')
    if d<tol:
        if abs(L1-L2)>tol:raise PoseError('Coincident unequal-length endpoints')
        direction=normalize(pole if previous_pole is None else previous_pole)
        return s+direction*L1,direction
    line=delta/d;candidate=_v(pole).copy();candidate-=line*(candidate@line)
    if np.linalg.norm(candidate)<1e-8 and previous_pole is not None:
        candidate=_v(previous_pole).copy();candidate-=line*(candidate@line)
    if np.linalg.norm(candidate)<1e-8:
        seed=np.eye(3)[np.argmin(abs(line))];candidate=seed-line*(seed@line)
    candidate=normalize(candidate)
    # A pole vector is semantic input, so do not flip it just to resemble an
    # earlier frame. At degeneracy, the previous plane is the explicit fallback.
    x=(L1*L1-L2*L2+d*d)/(2*d);height=math.sqrt(max(0.,L1*L1-x*x));e=s+line*x+candidate*height
    if max(abs(np.linalg.norm(e-s)-L1),abs(np.linalg.norm(w-e)-L2))>2e-8:raise PoseError('IK length invariant failed')
    return e,candidate

def swing(a,b,antiparallel_axis=None):
    """Shortest rotation, with a stable explicit axis at 180 degrees."""
    a,b=normalize(a),normalize(b);c=float(np.clip(a@b,-1,1));v=np.cross(a,b)
    if c>1-1e-12:return np.eye(3)
    if c<-1+1e-10:
        axis=np.eye(3)[np.argmin(abs(a))] if antiparallel_axis is None else _v(antiparallel_axis).copy()
        axis-=a*(axis@a)
        if np.linalg.norm(axis)<1e-8:
            axis=np.eye(3)[np.argmin(abs(a))];axis-=a*(axis@a)
        axis=normalize(axis);return 2*np.outer(axis,axis)-np.eye(3)
    K=np.array([[0,-v[2],v[1]],[v[2],0,-v[0]],[-v[1],v[0],0]])
    return np.eye(3)+K+K@K/(1+c)

def rigid_rotation(matrix,tolerance=2e-5):
    """Reject scale, shear and reflection; never hide them in polar cleanup."""
    a=np.asarray(matrix,float)
    if a.shape!=(3,3) or not np.isfinite(a).all():raise PoseError('Invalid rotation matrix')
    if np.linalg.det(a)<=0:raise PoseError('Reflected or singular bone transform')
    u,s,vt=np.linalg.svd(a)
    if np.max(abs(s-1))>tolerance:raise PoseError('Bone scale/shear would change limb thickness')
    return u@vt

def continuous_twist(axis,reference,target,previous=None):
    """Signed axial angle with branch continuity and a flagged singular fallback.
    Projected palm references can vanish in a bent wrist; retaining the previous
    twist is explicit and testable, instead of producing a random half-turn.
    """
    axis=normalize(axis);a=_v(reference).copy();b=_v(target).copy();a-=axis*(a@axis);b-=axis*(b@axis)
    if min(np.linalg.norm(a),np.linalg.norm(b))<1e-8:
        if previous is None:raise PoseError('Initial palm reference parallel to forearm')
        if not math.isfinite(previous):raise PoseError('Nonfinite previous twist')
        return float(previous),True
    a=normalize(a);b=normalize(b);angle=math.atan2(float(axis@np.cross(a,b)),float(np.clip(a@b,-1,1)))
    if previous is not None:
        if not math.isfinite(previous):raise PoseError('Nonfinite previous twist')
        angle+=2*math.pi*round((previous-angle)/(2*math.pi))
    return angle,False
