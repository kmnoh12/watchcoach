"""Local-metre stage-one subparts from the saved lat station. See scene_lat_extract.py.
Do not apply machine placement or animation here. Only numeric labels accept externally
supplied load text. The physical pin socket is the APP's blind pocket, not the scene's bore.
"""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path

import numpy as np

from part_catalog import SubPart, _merge_meshes
from part_registry import MAT_FRAME, MAT_PAD, MAT_RUBBER


@lru_cache(maxsize=1)
def _source():
    data = json.loads(Path(__file__).with_name('scene_lat_source.json').read_text())
    if data['schema'] != 2 or data['units'] != 'um':
        raise ValueError('Unknown lat station schema')
    return data


def palette():
    """Saved Blender material swatches, LINEAR RGB. No procedural shader bake implied."""
    return {k: list(v) for k, v in _source()['palette'].items()}


def _m(v):
    return np.asarray(v, dtype=np.float64) * 1e-6


def _bounds(mn, mx):
    mn, mx = (np.asarray(p, dtype=float) for p in (mn, mx))
    if mn.shape != (3,) or mx.shape != (3,) or not np.all(np.isfinite([mn,mx])) or np.any(mx<=mn):
        raise ValueError('Expected two increasing XYZ metre bounds')
    return (mn+mx)/2, (mx-mn)/2


def _nine(q, half, new_half, edge):
    """Rigid outer bands translated on each axis; only the middle stretches."""
    edge = min(edge, half*.5)
    if new_half <= edge:
        raise ValueError('Target too small to retain source corner/seam bands')
    return q + np.clip(q/(half-edge), -1, 1)*(new_half-half)


def _part(v, t, name, mat, smooth, color):
    return SubPart(np.asarray(v), np.asarray(t, dtype=np.int32).reshape(-1),
                   list(_source()['palette'][color]), mat, smooth, name)


def _split_source(v, source, specs, reflected=False):
    t = np.asarray(source['tri']); tags = np.asarray(source['material'])
    if reflected:
        t = t[:,::-1]
    parts=[]
    for i,spec in enumerate(specs):
        used, ix = np.unique(t[tags==i], return_inverse=True)
        parts.append(_part(v[used], ix, *spec))
    return parts


def build_seat(mn, mx):
    """CUSHION bounds only, +Z top. Leave the current app trim untouched."""
    center, half = _bounds(mn,mx); s=_source()['seat']
    v = _m(s['verts']); h = np.ptp(v,axis=0)/2
    for j in range(3):
        v[:,j]=center[j]+_nine(v[:,j], h[j],half[j],.030)
    return _split_source(v,s,[('_cushion',MAT_PAD,True,'pad'),('_stitch',MAT_PAD,True,'stitch')])


def build_roller(mn, mx, outer_sign):
    """FULL roller (foam + cap) bounds. Axle local Z; outer_sign selects the OUTER cap end."""
    c,h=_bounds(mn,mx); s=_source()['roller']
    if outer_sign not in (-1,1) or abs(h[0]-h[1]) > 1e-5:
        raise ValueError('Need circular radial XY bounds and signed outer end')
    v = _m(s['verts']); old = np.ptp(v,axis=0)/2
    v[:,:2] *= h[:2]/old[:2]
    v[:,2] = outer_sign*_nine(v[:,2],old[2],h[2],.032)
    return _split_source(v+c,s,[('_foam',MAT_PAD,True,'pad'),('_caps',MAT_RUBBER,True,'grip')],outer_sign<0)


def _plate_size(width,depth,height):
    size=np.array([width,depth,height],dtype=float)
    if not np.all(np.isfinite(size)) or np.any(size<=0):
        raise ValueError('Invalid plate size in metres')
    return size


def _xyz(xz, y):
    x,z=xz.T
    return np.column_stack([x,np.full(len(x),y),z])


def build_plate(width, depth, height, socket_radius=.0078):
    """ONE-element list. Source casting and rear bevel; adapt only the through-bore.
    Origin is the casting centre. Preserve the app's service face and 15 mm blind pocket.
    """
    size = _plate_size(width,depth,height); s = _source()['plate']
    v = _m(s['verts'])*size/_m(s['size']); t = np.asarray(s['tri'])
    shoulder = v[48,1]-v[64,1]
    if (not 0 < shoulder < .015 or depth <= .015+shoulder
            or not np.isfinite(socket_radius) or not 0 < 2*socket_radius < min(width,height)):
        raise ValueError('Target cannot fit the selector pocket')
    # Keep the actual service-face and rim triangulation. Use all 16 source mouth
    # samples so the bevel reads round; this is at least as open as the old octagon.
    # At the shoulder, blend into the original octagonal cone. From there to the
    # blind tip the clearance is identical to the previous app geometry.
    xz = _m(s['verts'][64:80])[:,[0,2]]
    mouth = xz * (socket_radius/np.linalg.norm(xz,axis=1))[:,None]
    throat = mouth.copy()
    throat[1::2] = (mouth[::2]+np.roll(mouth[::2],-1,axis=0))/2
    v[64:80] = _xyz(mouth,-depth/2)
    v[48:64] = _xyz(throat*(1-shoulder/.015), v[48,1])
    v = np.vstack([v, [0,v[32,1],0], [0,-depth/2+.015,0]])
    # Remove only the through wall (source grip slot), cap rear bevel and front cone separately.
    j = np.arange(16); k = (j+1)%16
    t = np.vstack([t[np.asarray(s['material'])==0],
                   np.column_stack([32+j,32+k,np.full(16,96)]),
                   np.column_stack([48+k,48+j,np.full(16,97)])])
    return [_part(v,t,'',MAT_FRAME,False,'casting')]


def sticker_layout(width,depth,height):
    """Return {kg/lb: {center,outline_xz,ink_y}} in casting-local metres. center = XYZ;
    outline_xz is relative to center. Looking toward +Y: kg on +X, lb on -X, as saved.
    Retain sticker and glyph size if they fit, otherwise shrink uniformly, never squash.
    """
    _plate_size(width,depth,height); s=_source()['plate']; result={}
    for unit,i in s['units'].items():
        label=s['labels'][i]; center=_m(label['center']); outline=_m(label['outline']); span=np.ptp(outline,axis=0)
        # Reserve the source's clear central pin strip (13 mm per side).
        gutter=abs(center[0])-span[0]/2
        factor=min(1,(width/2-gutter-.001)/span[0],(height-.001)/span[1]);
        if factor<=0: raise ValueError('No room for a selector sticker')
        center[0]=np.sign(center[0])*(gutter+span[0]*factor/2); center[1]-=depth/2
        result[unit]=dict(center=center,outline_xz=outline*factor,ink_y=-depth/2+s['ink_offset_y']*1e-6,
                          font_scale=factor)
    return result


def build_stickers(width,depth,height,kg,lb):
    """Two reusable triangle layers [dark backing, light ink], drawn toward -Y, for atlas baking.
    Numbers only, exactly as on the saved source. The caller owns row order, units and tracks.
    """
    layouts=sticker_layout(width,depth,height); backgrounds=[]; labels=[]
    for unit,val in [('kg',kg),('lb',lb)]:
        txt=f'{val:g}' if isinstance(val,float) else str(val)
        if not txt or any(c not in _source()['glyphs'] for c in txt): raise ValueError('Not a numerical label: '+txt)
        g=layouts[unit]; center=g['center']; q=g['outline_xz']; n=len(q)
        # Source sticker ring is clockwise in XZ, so reverse triangles to face -Y.
        backgrounds.append((_xyz(q+center[[0,2]],center[1]),np.array([(0,i+1,i) for i in range(1,n-1)]).ravel()))
        chars=[_source()['glyphs'][c] for c in txt]; width_text=sum(c['advance'] for c in chars)*1e-6
        scale=min(g['font_scale'],.94*np.ptp(q[:,0])/width_text); cursor=-width_text/2
        for glyph in chars:
            xz=_m(glyph['xz']); xz[:,0]+=cursor+glyph['bearing']*1e-6
            labels.append((_xyz(xz*scale+center[[0,2]],g['ink_y']),np.array(glyph['tri']).ravel()))
            cursor+=glyph['advance']*1e-6
    return [_part(*_merge_meshes(backgrounds),'_backing',MAT_RUBBER,False,'grip'),
            _part(*_merge_meshes(labels),'_ink',MAT_PAD,False,'ink')]
