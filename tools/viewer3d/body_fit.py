"""Fit a static support to a named skin region, independent of clip, mesh indices and sex."""
import numpy as np
from scipy.spatial import ConvexHull


def roller_depth_bound(frames, surface, *, swept):
    """Skin-vertex depth in metres. Exact on stored poses for a convex solid;
    an upper bound throughout every interpolated interval for an enclosing hull.
    Each plane's signed distance interpolates linearly along a vertex path.
    """
    start, end = (frames[:-1], frames[1:]) if swept and len(frames)>1 else (frames, frames)
    mask = ((np.maximum(start, end) >= surface.min(0)) &
            (np.minimum(start, end) <= surface.max(0))).all(2)
    planes = np.unique(ConvexHull(surface).equations.round(12), axis=0)
    def depths(points):
        return -np.einsum('vk,pk->vp', points[mask], planes[:,:3])-planes[:,3]
    depth = depths(start)
    if swept:
        depth = np.maximum(depth, depths(end))
    return float(depth.min(1).max(initial=0.))


def contact_region(base, role):
    """Include entire triangles incident to the contact anatomy, including joint blends."""
    regions = {'thigh_roller': ('thigh_',), 'seat_pad': ('thigh_', 'pelvis'),
               'back_pad': ('pelvis', 'spine_', 'clavicle_'), 'arm_pad': ('upperarm_', 'lowerarm_'),
               'ankle_roller': ('calf_', 'foot_', 'ball_')}[role]
    names = np.asarray(base['bone_names'])
    weights, joints = np.asarray(base['weights']), np.asarray(base['joints'])
    dominant = joints[np.arange(len(joints)), weights.argmax(1)]
    faces = np.asarray(base['triangles']).reshape(-1, 3)
    selected = np.logical_or.reduce([np.char.startswith(names[dominant], r) for r in regions])[faces].any(1)
    if not selected.any():
        raise ValueError(f'Missing skin region for {role}')
    return faces[selected], faces[~selected]


def surface_peak(frames, faces, lo, hi):
    """Highest skin in a rectangular footprint, in the contact coordinate system.

    A clipped triangle's extrema are original vertices, edge/box crossings, or box corners
    inside the triangle. Clipping matters here: the high point can be inside a large face.
    """
    tri = frames[:, faces].reshape(-1, 3, 3)
    tri = tri[((tri[:,:,:2].max(1) >= lo) & (tri[:,:,:2].min(1) <= hi)).all(1)]
    inside = ((tri[:,:,:2] >= lo) & (tri[:,:,:2] <= hi)).all(2)
    peak = tri[:,:,2][inside].max(initial=-np.inf)
    d = np.roll(tri, -1, axis=1) - tri
    for j in (0, 1):
        for boundary in (lo[j], hi[j]):
            t = np.divide(boundary-tri[:,:,j], d[:,:,j], out=np.full_like(d[:,:,j], -2.), where=d[:,:,j]!=0)
            k = 1-j; lateral = tri[:,:,k]+t*d[:,:,k]
            ok = (t>=0)&(t<=1)&(lateral>=lo[k])&(lateral<=hi[k])
            peak = max(peak, (tri[:,:,2]+t*d[:,:,2])[ok].max(initial=-np.inf))
    a, b, c = tri.transpose(1,0,2); ab, ac = b-a, c-a
    cross = lambda p,q: p[:,0]*q[:,1]-p[:,1]*q[:,0]
    det = cross(ab, ac); valid = abs(det)>1e-15
    for x in (lo[0], hi[0]):
        for y in (lo[1], hi[1]):
            q = [x,y]-a[:,:2]
            u = np.divide(cross(q,ac), det, out=np.zeros_like(det), where=valid)
            v = np.divide(cross(ab,q), det, out=np.zeros_like(det), where=valid)
            ok = valid&(u>=0)&(v>=0)&(u+v<=1)
            peak = max(peak, (a[:,2]+u*ab[:,2]+v*ac[:,2])[ok].max(initial=-np.inf))
    if not np.isfinite(peak):
        raise ValueError('No contact skin under this part')
    return peak


def fit_body_part(frames, base, role, position, surface, axis, axle, clearance=.0035):
    """Return the fitted world position; preserve orientation and both transverse coordinates."""
    up = np.asarray(axis, dtype=float); up = up / np.linalg.norm(up)
    across = np.asarray(axle, dtype=float); across = across-up*np.dot(across, up)
    across /= np.linalg.norm(across)
    basis = np.stack([across, np.cross(up, across), up]); faces, _ = contact_region(base, role)
    part = np.einsum('ij,vj->vi', basis, surface)
    skin = np.einsum('ij,fvj->fvi', basis, frames)
    peak = surface_peak(skin, faces, part[:,:2].min(0), part[:,:2].max(0))
    return position + up*(peak+clearance-part[:,2].min())


class SkinSweep:
    """Conservative collision test: skin triangles stay inside their six endpoint vertices'
    convex hull between stored frames (the viewer linearly interpolates world vertices).
    Reject even ambiguous candidates instead of treating a vertex-only test as clearance.
    """
    def __init__(self, frames, faces):
        self.frames, self.faces = frames, faces
        tri = frames[:, faces]; lo, hi = tri.min(2), tri.max(2)
        if len(frames)==1:
            self.lo, self.hi = lo, hi
        else:
            self.lo, self.hi = np.minimum(lo[:-1], lo[1:]), np.maximum(hi[:-1], hi[1:])

    def clear(self, surface, margin=.0003):
        i, f = np.nonzero(((self.hi >= surface.min(0)-margin) & (self.lo <= surface.max(0)+margin)).all(2))
        if not len(i):
            return True
        planes = np.unique(ConvexHull(surface).equations.round(9), axis=0)
        for start in range(0,len(i),128):
            step=i[start:start+128,None]; idx=self.faces[f[start:start+128]]
            following=np.minimum(step+1,len(self.frames)-1)
            v=np.concatenate((self.frames[step,idx], self.frames[following,idx]), axis=1)
            if (((np.einsum('fvk,pk->fvp', v, planes[:,:3]) + planes[:,3]).min(1) <= margin).all(1)).any():
                return False
        return True
