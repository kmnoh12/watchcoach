"""Rest-relative geometric shoulder-support diagnostic; no anatomical claim."""
import math
import numpy as np


def protract(attachment,shoulder,source_upper,rest_upper,body_rotation,max_angle_deg,side):
    if side not in ('l','r') or not np.isfinite(max_angle_deg) or not 0<=max_angle_deg<=20:
        raise ValueError('Invalid diagnostic protraction')
    c,s=np.asarray(attachment,float),np.asarray(shoulder,float)
    upper,reference=np.asarray(source_upper,float),np.asarray(rest_upper,float)
    upper=upper/np.linalg.norm(upper);reference=reference/np.linalg.norm(reference)
    rotation=np.asarray(body_rotation,float)
    if not np.isfinite([*c,*s,*upper,*reference,*rotation.ravel()]).all():raise ValueError('Invalid motion input')
    rest_forward=float(reference@np.array([0.,-1.,0.]))
    forward=float(upper@(rotation@np.array([0.,-1.,0.])))
    activation=float(np.clip((forward-rest_forward)/max(1-rest_forward,1e-12),0,1))
    if activation<1e-10 or not max_angle_deg:return s.copy(),0.
    active=max_angle_deg*activation*activation
    theta=math.radians((-1 if side=='l' else 1)*active)
    axis=rotation@np.array([0.,0.,1.]);axis/=np.linalg.norm(axis)
    v=s-c
    moved=c+v*math.cos(theta)+np.cross(axis,v)*math.sin(theta)+axis*(axis@v)*(1-math.cos(theta))
    return moved,active
