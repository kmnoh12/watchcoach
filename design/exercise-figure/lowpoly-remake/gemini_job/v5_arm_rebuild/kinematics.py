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

def shoulder_arm(attachment,shoulder,wrist,upper_length,lower_length,pole,previous_pole=None,extension_margin=0.):
    """Reach with a rotating clavicle and two fixed-length arm segments.

    Keep a feasible shoulder fixed except in an explicitly requested soft
    extension band. Otherwise choose the nearest position on the clavicle
    sphere that permits the arm to reach at the original segment lengths.
    This is a geometric candidate, not an anatomical shoulder-limit model.
    An unreachable three-link chain raises rather than stretching a segment.
    """
    c,s,w=_v(attachment),_v(shoulder),_v(wrist)
    a,b=float(upper_length),float(lower_length)
    if not np.isfinite([a,b]).all() or min(a,b)<=0:raise PoseError('Invalid bone lengths')
    clavicle=float(np.linalg.norm(s-c))
    if clavicle<1e-12:raise PoseError('Zero-length clavicle')
    low,high=abs(a-b),a+b
    distance=float(np.linalg.norm(w-s))
    radius=high if distance>high else low
    if extension_margin:
        if not np.isfinite(extension_margin) or extension_margin<0:
            raise PoseError('Invalid extension margin')
        # Reserve a small bend near full reach. A C2 soft cap joins the
        # unchanged feasible region to shoulder-assisted reach without the
        # sqrt elbow-height cusp at a completely locked arm.
        minimum_radius=abs(float(np.linalg.norm(w-c))-clavicle)
        margin=min(float(extension_margin),max(0.,high-minimum_radius)*.8)
        if margin>1e-10 and distance>high-2*margin:
            x=float(np.clip((distance-(high-2*margin))/(2*margin),0,1))
            radius=(distance-2*margin*(x**3-.5*x**4)) if x<1 else high-margin
            radius=max(radius,min(high,minimum_radius+1e-8))
    if low<=distance<=high and (not extension_margin or radius>=distance-1e-10 or distance<=high-2*margin):
        e,p=two_bone(s,w,a,b,pole,previous_pole)
        return s.copy(),e,p
    axis=w-c;d=float(np.linalg.norm(axis));tol=1e-9*max(1.,clavicle+high)
    if d<tol or d>clavicle+radius+tol or d<abs(clavicle-radius)-tol:
        raise PoseError('Grip target unreachable at fixed clavicle and arm lengths')
    axis/=d
    x=(clavicle*clavicle-radius*radius+d*d)/(2*d)
    height=math.sqrt(max(0.,clavicle*clavicle-x*x))
    radial=s-c-axis*((s-c)@axis)
    if np.linalg.norm(radial)<1e-8:
        radial=_v(pole).copy();radial-=axis*(radial@axis)
    if np.linalg.norm(radial)<1e-8 and previous_pole is not None:
        radial=_v(previous_pole).copy();radial-=axis*(radial@axis)
    if np.linalg.norm(radial)<1e-8:
        radial=np.eye(3)[np.argmin(abs(axis))];radial-=axis*(radial@axis)
    corrected=c+axis*x+normalize(radial)*height
    if abs(np.linalg.norm(corrected-c)-clavicle)>2e-8:
        raise PoseError('Clavicle length invariant failed')
    e,p=two_bone(corrected,w,a,b,pole,previous_pole)
    return corrected,e,p

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
