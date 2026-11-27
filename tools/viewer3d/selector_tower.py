"""Low-poly equivalents of promo/tools/detail6_latpulldown.py's selectorised hardware.

Parts are in metres, Z up, service window towards -Y. The consumer supplies the
stack axis, floor, pulley centres and stroke; neither the hardware nor its meshes
know exercise IDs, grips or human poses. Repeated placements share a catalogue PID.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path

import numpy as np

from part_catalog import SubPart, _ensure_outward, _merge_meshes, make_box, make_revolved_profile
from part_registry import MAT_ACCENT, MAT_CHROME, MAT_FRAME, MAT_RUBBER, MAT_SELECTOR_WINDOW

# Linear RGB, not sRGB swatches. Chrome is reserved for pins/rods and small fasteners.
COAT = (.042, .042, .042)
CHARCOAL = (.072, .072, .072)
RUBBER = (.028, .028, .028)
IRON = (.285, .285, .285)
STEEL = (.72, .73, .74)
YELLOW = (.98, .61, .016)


@dataclass
class Placed:
    name: str
    part: SubPart
    at: tuple
    lift: bool = False


def block(size, bevel=0, center=(0, 0, 0)):
    half = np.asarray(size) / 2
    if not bevel:
        return make_box(center - half, center + half)
    # Real rolled/folded members have long highlight edges, not bevels on every end face.
    axis = int(np.argmax(half))
    a,b = half[(axis+1)%3], half[(axis+2)%3]
    k = min(bevel, min(a,b)*.45)
    profile = [(-a+k,-b),(a-k,-b),(a,-b+k),(a,b-k),(a-k,b),(-a+k,b),(-a,b-k),(-a,-b+k)]
    v,t = side_profile(profile, 2*half[axis])
    return np.roll(v, axis, axis=1) + center, t


def cylinder(r, length, axis, n=10, at=(0, 0, 0)):
    return make_revolved_profile([(r, -length/2), (r, length/2)], n, axis, at)


def side_profile(yz, thickness):
    """Convex folded-sheet outline extruded along X."""
    n = len(yz)
    v = np.array([(x, y, z) for x in (-thickness/2, thickness/2) for y, z in yz])
    t = [(0, i+1, i) for i in range(1, n-1)] + [(n, n+i, n+i+1) for i in range(1, n-1)]
    for i in range(n):
        j = (i+1) % n
        t.extend([(i, j, n+j), (i, n+j, n+i)])
    return v, _ensure_outward(v, np.asarray(t))


def beam(a, b, width, depth):
    a, b = np.asarray(a), np.asarray(b)
    axis = (b-a)/np.linalg.norm(b-a)
    across = np.cross(axis, [0, 0, 1]); across /= np.linalg.norm(across)
    v,t = block((width, np.linalg.norm(b-a), depth), .0035)
    return v @ np.array([across, axis, np.cross(across, axis)]) + (a+b)/2, t


def cast_plate(width, depth, height):
    """One clipped-corner casting with a recessed selector socket, not painted bars."""
    x, y, z = width/2, depth/2, height/2
    xy = [(-x+.016,-y),(x-.016,-y),(x,-y+.014),(x,y),(-x,y),(-x,-y+.014)]
    v = [(a,b,-z) for a,b in xy] + [(a,b,z-.0035 if i<2 else z) for i,(a,b) in enumerate(xy)]
    v += [(a,b+.0035,z) for a,b in xy[:2]]
    top = [12,13,8,9,10,11]
    t = [(0,i+1,i) for i in range(1,5)] + [(top[0],top[i],top[i+1]) for i in range(1,5)]
    for i in range(1,6):  # rear and sides; the open face gets a pin socket below
        j = (i+1)%6
        t.extend([(i,j,j+6),(i,j+6,i+6)])
    t.extend([(6,7,13),(6,13,12),(7,8,13),(11,6,12)])
    rim = len(v)
    for q in np.deg2rad(np.arange(-135,225,45)):
        v.append((.0078*np.cos(q),-y,.0078*np.sin(q)))
    tip = len(v); v.append((0,-y+.015,0))
    corners = [0,1,7,6]
    for i,a in enumerate(corners):
        b=corners[(i+1)%4]; j=2*i
        h,k,l=rim+j,rim+j+1,rim+((j+2)%8)
        t.extend([(a,b,k),(b,l,k),(a,k,h)])
    for i in range(8):
        t.append((rim+i,rim+(i+1)%8,tip))
    v=np.asarray(v); return v,_ensure_outward(v,np.asarray(t))


@lru_cache(None)
def guide_ink(key):
    data=json.loads((Path(__file__).parent/'guides'/f'{key}.json').read_text())
    x,z=np.asarray(data['xz']).T*.0001
    return np.column_stack([x,np.zeros(len(x)),z]),np.asarray(data['tris'],dtype=np.int32)


class Kit(list):
    def put(self, name, mesh, at=(0,0,0), color=COAT, mat=MAT_FRAME, *, lift=False, smooth=False):
        self.append(Placed(name,SubPart(*mesh,color,mat,smooth),at,lift))

    def anchor(self, at, sign, height):
        # detail6: 72 x 74 x 10 mm toe, 12 mm return, washer + hex bolt on top; sole is Z=0.
        self.put('anchor', _merge_meshes([block((.072,.074,.010),center=(sign*.032,0,.005)),
                 block((.012,.066,height-.005),center=(sign*.006,0,(height+.005)/2))]), at)
        x,y,z = at
        washer = make_revolved_profile([(.0145,0),(.0145,.0026)],10,2,cap_bottom=False)
        bolt = make_revolved_profile([(.009,.0026),(.009,.0091)],6,2,cap_bottom=False)
        self.put('anchor_bolt',_merge_meshes([washer,bolt]),(x+sign*.042,y,z+.010), CHARCOAL)

    def sheave(self, at, radius, hanger):
        # The grooved sheave and hex spindle are separate from the pair of U-shaped steel cheek plates.
        r=radius
        self.put('sheave',make_revolved_profile([(r,-.016),(r*.82,-.002),(r*.82,.002),(r,.016)],
                 16,0), at, RUBBER, MAT_RUBBER, smooth=True)
        rg=r+.006
        arc=[(rg*np.cos(q),rg*np.sin(q)) for q in np.linspace(np.pi,2*np.pi,9)]
        cheek=side_profile([(-rg,hanger),*arc,(rg,hanger)],.008)
        x,y,z=at
        for s in (-1,1):
            self.put('sheave_cheek',cheek,(x+s*.024,y,z))
        self.put('sheave_axle',cylinder(.017,.068,0,6),at,CHARCOAL)

    def housing(self, height, plate_width, plate_depth, bed_top, guide):
        h=height; inside=plate_width/2+.012; post=inside+.027; outer=inside+.054
        front=-plate_depth/2-.022; back=plate_depth/2+.047
        # The header is a fascia + side returns, not a solid box through the load cable.
        self.put('header',block((2*inside+.006,.036,.172),.004), (0,front,h-.086))
        self.put('plinth',block((2*outer+.008,back-front+.044,bed_top),.007),
                 (0,(back+front)/2-.004,bed_top/2))
        self.put('back_skin',block((2*outer-.014,.016,h-.08),.003), (0,back,h/2+.04), CHARCOAL)
        self.put('guide_card',block((.368,.009,.129),.002),(0,front-.0215,h-.083),RUBBER,MAT_RUBBER)
        if guide:
            self.put('guide_ink',guide_ink(guide),(0,front-.027,h-.083),(.72,.72,.72))
        for s in (-1,1):
            self.put('post',block((.054,.100,h-.10),.005),(s*post,front+.029,(h+.10)/2))
            self.put('post_collar',block((.062,.108,.020),.002),(s*post,front+.029,.120),CHARCOAL)
            # Solid folded side skins with stepped seams. These are NOT windows.
            skin=side_profile([(front+.065,.098),(back-.035,.098),(back,.136),(back,h-.038),
                               (back-.024,h),(front+.065,h)],.016)
            self.put('side_skin',skin,(s*(outer-.010),0,0),CHARCOAL)
            self.put('side_return',block((.022,.027,h-.158),.004),(s*(outer-.012),back-.027,h/2+.064))
            self.put('rod_retainer',block((outer-.100,.043,.028),.003),(s*(outer+.100)/2,0,h-.045))
            # Two 4 mm neutral leaves inset behind the posts, 72 mm open selector slot.
            pw=inside-.036
            self.put('window',block((pw,.004,h-.172-.132)), (s*(.036+pw/2),front,(h-.172+.132)/2),
                     (.37,.37,.37),MAT_SELECTOR_WINDOW)
            for frac in (.06,.5,.94):
                z=.132+frac*(h-.172-.132)
                self.put('window_clip',block((.036,.014,.038)),(s*(inside-.013),front-.004,z))
                self.put('clip_bolt',cylinder(.006,.006,1,6),(s*(inside-.017),front-.012,z),CHARCOAL)
            self.anchor((s*(outer+.004),front+.051,0),s,.086)
        return post, front

    def stack(self, width, depth, pitch, selected_z, fixed_rows, lift_rows):
        mesh=cast_plate(width,depth,pitch-.004)
        for row in range(-fixed_rows,lift_rows):
            self.put('cast_plate',mesh,(0,0,selected_z+row*pitch),IRON,lift=row>=0)
        face=-depth/2
        knob=make_revolved_profile([(.015,-.062),(.023,-.058),(.023,-.044),(.015,-.038),(.013,-.034)],12,1)
        self.put('selector_knob',knob,(0,face,selected_z),YELLOW,MAT_ACCENT,lift=True,smooth=True)
        self.put('selector_shank',cylinder(.0058,.044,1), (0,face-.019,selected_z),STEEL,MAT_CHROME,lift=True,smooth=True)
        self.put('load_socket',make_revolved_profile([(.027,0),(.024,.010),(.010,.022)],12,2),
                 (0,0,selected_z+(lift_rows-1)*pitch+(pitch-.004)/2-.002),CHARCOAL,lift=True)


def lat_station(head, crown, outlet, pin_z, thigh, foot, guide='lat_pulldown'):
    """Fit the common kit to a single-boom station's existing sheaves, roller mount and floor foot.
    Points are relative to the stack axis at floor level. Each sheave supplies its original centre/radius.
    """
    kit=Kit(); (rear,r0),(mid,r1),(tip,r2)=head,crown,outlet
    height=rear[2]; width,depth=.380,.310
    pitch, fixed, moving = .039, 14, 14
    bed_top = pin_z-fixed*pitch-(pitch-.004)/2
    post,front=kit.housing(height,width,depth,bed_top,guide)
    kit.stack(width,depth,pitch,pin_z,fixed,moving)
    # Retain the app's three original axle/cable positions. Rise from the two tower shoulders,
    # not from a central mast in front of the selector slot. The boom runs above the live cable.
    for s in (-1,1):
        kit.put('tower_knee',beam((s*post,front+.041,height-.09), (s*.030,mid[1],mid[2]+r1+.060),.048,.062))
        kit.put('load_hanger',block((post-.020,.048,.040)),(s*(post+.020)/2,0,height-.027))
        kit.put('roller_mount',beam((s*post,front+.032,thigh[2]+.07), (s*post,thigh[1],thigh[2]),.044,.050))
        kit.anchor((s*foot[0],foot[1],0),s,.056)
    kit.sheave(rear,r0,.008)
    kit.sheave(mid,r1,r1+.066)
    kit.sheave(tip,r2,r2+.066)
    kit.put('boom',beam((0,mid[1]+.052,mid[2]+r1+.072), (0,tip[1]-.054,tip[2]+r2+.060),.064,.084))
    return kit
