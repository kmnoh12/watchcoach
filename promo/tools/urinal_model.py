"""Realistic wall-hung urinal for the men's restroom (gym_locker_suites).

Follows the modern sensor-integrated wall-hung urinals used in Korean commercial restrooms (대림바스 / 계림 / TOTO
UFS-type): a tall vitreous-china body with a flat top cover, a hood carrying a round sensor window, a wide U-shaped
mouth with a rounded lip, a deep bowl that flares up under the hood, a chrome strainer in the sump just behind the
lip, a concealed top spud (water enters through the wall, nothing exposed) and side wall-fixing caps.
Size ~0.36 W x 0.33 D x 0.66 H, mouth lip ~0.59 m above the floor, top ~1.20 m.

urinal(S, root, idx) has the signature and frame of gym_locker_suites._urinal: build into S.c, parented to `root`,
wall plane at local y = 0, local +y into the room, z = floor height.  urinal_screen(S, ...) is an optional
frosted-glass privacy screen with chrome wall clamps.

The body is one closed smooth-shaded mesh: rings of a shared "shield" contour (flat-topped, U-bottomed) lofted from
the wall plate, along the outside, over a rounded front face and lip, then back into the bowl to a closed back.
No runtime boolean is used.
"""
import math

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import wc_lib as W

N_RING = 96         # points per contour ring (even, symmetric about x = 0)

# contour rings: (y, half width, top z, bottom z, centre z, top exponent, bottom exponent)
_CZ = 0.95
_OUT = dict(cz=_CZ, nt=10.0, nb=2.6)
_LIP = dict(cz=_CZ, nt=3.0, nb=2.9)
_BOWL = dict(cz=_CZ, nt=3.6, nb=2.8)


def _ring_params():
    R = []
    # outside, from the wall plate forward (bottom slopes down toward the front tip)
    for y, a, zt, zb in ((0.003, 0.172, 1.152, 0.672), (0.010, 0.180, 1.160, 0.660), (0.080, 0.180, 1.160, 0.625),
                         (0.160, 0.180, 1.160, 0.592), (0.240, 0.180, 1.160, 0.565), (0.295, 0.180, 1.160, 0.550)):
        R.append(dict(y=y, a=a, zt=zt, zb=zb, **_OUT))
    # rounded front edge (r ~ 15 mm) onto the flat front face at y = 0.330
    for t in (0.35, 0.70, 0.92, 1.0):
        ang = t * math.pi / 2
        dy, dn = 0.015 * math.sin(ang), 0.015 * (1 - math.cos(ang))
        R.append(dict(y=0.315 + dy, a=0.180 - dn, zt=1.160 - dn, zb=0.547 + dn, **_OUT))
    # front face, blending from the outer shield to the mouth (lip contour expanded by 10 mm)
    o, l = R[-1], dict(a=0.138, zt=1.040, zb=0.578)
    for t in (0.45,):
        R.append(dict(y=0.330, a=o["a"] + (l["a"] - o["a"]) * t, zt=o["zt"] + (l["zt"] - o["zt"]) * t,
                      zb=o["zb"] + (l["zb"] - o["zb"]) * t, cz=_CZ, nt=4.5, nb=2.75))
    # rounded lip, radius 10 mm: front face -> mouth edge (y 0.320) -> undercut back into the bowl
    r = 0.010
    for k in range(9):
        ang = math.pi / 2 + k * math.pi / 8          # 90 .. 180 .. 270 deg
        e = r + r * math.cos(ang)                       # outward offset from the mouth edge
        y = 0.320 + r * math.sin(ang)
        R.append(dict(y=y, a=0.128 + e, zt=1.030 + e, zb=0.588 - e, **_LIP))
    # bowl: flares wider and up under the hood, floor rises toward the wall, closes on a curved back
    for y, a, zt, zb in ((0.290, 0.148, 1.068, 0.580), (0.255, 0.158, 1.096, 0.581), (0.205, 0.163, 1.115, 0.598),
                         (0.145, 0.164, 1.122, 0.624), (0.095, 0.159, 1.118, 0.650), (0.066, 0.146, 1.104, 0.672),
                         (0.050, 0.118, 1.078, 0.705), (0.041, 0.075, 1.045, 0.750), (0.037, 0.032, 1.010, 0.800)):
        R.append(dict(y=y, a=a, zt=zt, zb=zb, **_BOWL))
    return R


def _contour(p, n=N_RING, dense=1440):
    """Closed shield contour in the x-z plane, resampled to n points by arc length, starting at the bottom centre
    and running counter-clockwise seen from the front (+y)."""
    pts = []
    for i in range(dense):
        th = -math.pi / 2 + 2 * math.pi * i / dense
        c, s = math.cos(th), math.sin(th)
        ex = p["nt"] if s >= 0 else p["nb"]
        x = p["a"] * math.copysign(abs(c) ** (2 / ex), c)
        h = (p["zt"] - p["cz"]) if s >= 0 else (p["cz"] - p["zb"])
        z = p["cz"] + h * math.copysign(abs(s) ** (2 / ex), s)
        pts.append((x, z))
    pts.append(pts[0])
    cum = [0.0]
    for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
        cum.append(cum[-1] + math.hypot(x1 - x0, z1 - z0))
    out, j = [], 0
    for k in range(n):
        target = cum[-1] * k / n
        while cum[j + 1] < target:
            j += 1
        f = (target - cum[j]) / max(cum[j + 1] - cum[j], 1e-12)
        out.append((pts[j][0] + (pts[j + 1][0] - pts[j][0]) * f, pts[j][1] + (pts[j + 1][1] - pts[j][1]) * f))
    return out


def _body_bmesh():
    bm = bmesh.new()
    rings = []
    for p in _ring_params():
        rings.append([bm.verts.new((x, p["y"], z)) for x, z in _contour(p)])
    n = N_RING
    for ra, rb in zip(rings, rings[1:]):
        for i in range(n):
            bm.faces.new((ra[i], ra[(i + 1) % n], rb[(i + 1) % n], rb[i]))
    bm.faces.new(list(reversed(rings[0])))                     # wall plate (flat, against the wall)
    last = rings[-1]
    cz = sum(v.co.z for v in last) / n
    tip = bm.verts.new((0.0, last[0].co.y - 0.002, cz))        # bowl back closes on a fan
    for i in range(n):
        bm.faces.new((last[i], last[(i + 1) % n], tip))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def _mat(name, color, rough, metal=0.0):
    return bpy.data.materials.get(name) or W.mat(name, color, rough=rough, metal=metal)


def _bevel(ob, radius):
    bv = ob.modifiers.new("Bevel", "BEVEL")
    bv.width = radius
    bv.segments = 2
    bv.limit_method = "ANGLE"
    return ob


def _disc(c, root, name, r, h, m, base, normal, seg=32, r2=None):
    """Cylinder whose base centre sits at `base` and whose axis points along `normal` (frame-local)."""
    n = Vector(normal).normalized()
    ob = W.cyl(name, r, h, m, c, (0, 0, 0), seg=seg, r2=r2, parent=root)
    for p in ob.data.polygons:
        p.use_smooth = len(p.vertices) == 4
    q = Vector((0, 0, 1)).rotation_difference(n)
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = q
    ob.location = Vector(base) + n * (h / 2)
    return ob


def _rounded_slab(c, root, name, size, m, xyz, bevel, segments=2):
    ob = W.box(name, size, m, c, xyz, parent=root)
    _bevel(ob, min(bevel, min(size) * 0.45)).modifiers[-1].segments = segments
    return ob


def _lid(c, root, name, m, w=0.354, d=0.322, h=0.030, r=0.026, z0=1.162, y0=0.005):
    """Top cover: plan-rounded slab (corner radius r) with softly rounded top edges, flat underside."""
    pts = []
    for cx, cy, a0 in ((w / 2 - r, d - r, 0), (-w / 2 + r, d - r, 90), (-w / 2 + r, r, 180), (w / 2 - r, r, 270)):
        for k in range(7):
            a = math.radians(a0 + 15 * k)
            pts.append((cx + r * math.cos(a), y0 + cy + r * math.sin(a)))
    bm = bmesh.new()
    prof = [(0.0, 0.0), (0.0, h - 0.010), (0.003, h - 0.003), (0.010, h)]   # (inset, z) up the edge
    rings = []
    for ins, z in prof:
        ring = []
        for x, y in pts:
            nx, ny = _sgn_n(x, y, w, d, r, y0)
            ring.append(bm.verts.new((x - ins * nx, y - ins * ny, z0 + z)))
        rings.append(ring)
    n = len(pts)
    for ra, rb in zip(rings, rings[1:]):
        for i in range(n):
            bm.faces.new((ra[i], ra[(i + 1) % n], rb[(i + 1) % n], rb[i]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = W.mesh_obj(name, bm, m, c, (0, 0, 0), parent=root)
    for p in ob.data.polygons:
        p.use_smooth = len(p.vertices) == 4
    return ob


def _sgn_n(x, y, w, d, r, y0):
    """Outward plan normal of the rounded rectangle at boundary point (x, y)."""
    cx = max(-w / 2 + r, min(w / 2 - r, x))
    cy = max(y0 + r, min(y0 + d - r, y))
    vx, vy = x - cx, y - cy
    L = math.hypot(vx, vy)
    return (vx / L, vy / L) if L > 1e-9 else (0.0, 0.0)


def urinal(S, root, idx):
    """Sensor-integrated wall-hung urinal, built into S.c and parented to `root` (fixture frame, wall at y = 0)."""
    c, M = S.c, S.M
    ceramic = M["ceramic"]
    sensor_glass = _mat("Urinal_SensorGlass", (0.035, 0.040, 0.048), 0.08)
    bezel = _mat("Urinal_SensorBezel", (0.70, 0.71, 0.71), 0.35)

    bm = _body_bmesh()
    tree = BVHTree.FromBMesh(bm)
    body = W.mesh_obj("Urinal body", bm, ceramic, c, (0, 0, 0), parent=root)
    for p in body.data.polygons:
        p.use_smooth = len(p.vertices) != N_RING           # all but the flat wall plate

    def hit(origin, direction):
        loc, nrm, _, _ = tree.ray_cast(Vector(origin), Vector(direction).normalized())
        return loc, nrm

    # top cover (separate lid, 2 mm seam above the body's flat top)
    _lid(c, root, "Urinal top cover", ceramic)

    # round sensor window on the hood (front face is flat at y = 0.330)
    _disc(c, root, "Urinal sensor bezel", 0.024, 0.0025, bezel, (0, 0.3305, 1.092), (0, 1, 0), seg=40)
    _disc(c, root, "Urinal sensor window", 0.016, 0.0035, sensor_glass, (0, 0.3305, 1.092), (0, 1, 0), seg=32)

    # chrome strainer in the sump just behind the lip (sits on the bowl floor, slightly sunk)
    loc, nrm = hit((0, 0.268, 0.75), (0, 0, -1))
    if loc is not None:
        if nrm.z < 0:
            nrm = -nrm
        base = loc - nrm * 0.0025
        _disc(c, root, "Urinal strainer", 0.034, 0.0040, M["chrome"], base, nrm, seg=36)
        _disc(c, root, "Urinal strainer slots", 0.026, 0.0050, M["dark"], base, nrm, seg=32)
        _disc(c, root, "Urinal strainer cap", 0.019, 0.0062, M["chrome"], base, nrm, seg=32, r2=0.016)

    # wall-fixing bolt caps on both sides of the hood and low on the body
    for x_sign in (-1, 1):
        for y, z in ((0.050, 1.110), (0.050, 0.725)):
            loc, nrm = hit((x_sign * 0.30, y, z), (-x_sign, 0, 0))
            if loc is not None:
                _disc(c, root, "Urinal fixing cap", 0.0085, 0.0065, M["chrome"], loc - nrm * 0.002, nrm, seg=20,
                      r2=0.0070)
    return body


def urinal_screen(S, name, root, depth=0.46, z0=0.42, z1=1.62, t=0.012):
    """Optional frosted tempered-glass privacy screen between urinals, in a fixture frame whose y = 0 is the wall
    and whose local x is the screen's plane normal; two chrome wall clamps and a rounded front edge."""
    c, M = S.c, S.M
    glass = M.get("frost") or _mat("Urinal_FrostGlass", (0.80, 0.86, 0.85), 0.5)
    h = z1 - z0
    pane = _rounded_slab(c, root, f"{name} glass", (t, depth - 0.004, h), glass, (0, 0.004 + (depth - 0.004) / 2,
                                                                                  z0 + h / 2), 0.004)
    for z in (z0 + 0.18, z1 - 0.18):
        for side in (-1, 1):
            _rounded_slab(c, root, f"{name} clamp", (0.008, 0.050, 0.045), M["chrome"],
                          (side * (t / 2 + 0.0045), 0.028, z), 0.002)
        _rounded_slab(c, root, f"{name} clamp base", (0.034, 0.004, 0.060), M["chrome"], (0, 0.0021, z), 0.0015)
    return pane
