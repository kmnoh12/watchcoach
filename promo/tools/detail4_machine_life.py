"""detail4 P8 machine_life: lived-in props around the selector machines, plate-loaded machines and the power rack.

New objects only (collection DETAIL4_machine_life under SET). Nothing existing is modified.
- white wire baskets on the side of 6 selector towers, each with a plain spray bottle and/or a folded towel
  (ref work/refs/gym/234: white basket + green sanitiser spray hung on the tower side)
- extra plates on the three plate-loaded machines, different load per machine (existing plate meshes linked)
- a lifting belt draped over the power-rack safety arm, a chalk bucket next to the lifting platform
- towels on two machine seats / back pads
No text, labels or logos anywhere.

Run standalone (never saves unless --save is given):
  Blender -b promo/scenes/scene_gym.blend --python promo/tools/detail4_machine_life.py [-- --save out.blend]
"""
import json
import math
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

KEY = "machine_life"
COLL = "DETAIL4_machine_life"
PFX = "D4ml_"

# selector towers that get a basket on their +x side face; (machine root, contents)
BASKETS = [
    ("P_chest_press_machine", "spray+towel"),
    ("P_pec_deck", "spray"),
    ("P_lateral_raise_machine", "spray+towel_hang"),
    ("P_preacher_machine", "spray"),
    ("P_leg_extension", "spray+towel"),
    ("P_hip_abductor", "spray"),
]
BASKET_LDH = (0.19, 0.12, 0.12)
# plate-loaded machines: (existing outermost plate per side, list of (scale of diameter, thickness gap)).
EXTRA_PLATES = [
    # leg press: +1 smaller (10 kg look) plate each side
    ("cast_plate.016", +1, [0.80]), ("cast_plate.018", -1, [0.80]),
    # t-bar row: +1 same (20 kg) + 1 small each side
    ("cast_plate.019", +1, [1.0, 0.72]), ("cast_plate.020", -1, [1.0, 0.72]),
]


# ---------------------------------------------------------------- helpers
def _coll():
    c = bpy.data.collections.get(COLL)
    if c is None:
        c = bpy.data.collections.new(COLL)
        bpy.data.collections["SET"].children.link(c)
    for ob in list(c.objects):
        data = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if data is not None and data.users == 0 and isinstance(data, bpy.types.Mesh):
            bpy.data.meshes.remove(data)
    for me in [m for m in bpy.data.meshes if m.name.startswith(PFX) and m.users == 0]:
        bpy.data.meshes.remove(me)
    return c


def _principled(name, base, rough, metal=0.0, coat=0.0, alpha=1.0, sheen=0.0, bump=None, transmission=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.name = "Principled BSDF"
    b.inputs["Base Color"].default_value = (*base, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Sheen Weight"].default_value = sheen
    b.inputs["Transmission Weight"].default_value = transmission
    b.inputs["Alpha"].default_value = alpha
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    if bump:
        scale, strength = bump
        tc = nt.nodes.new("ShaderNodeTexCoord")
        n = nt.nodes.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = 4.0
        bp = nt.nodes.new("ShaderNodeBump")
        bp.inputs["Strength"].default_value = strength
        bp.inputs["Distance"].default_value = 0.001
        nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
        nt.links.new(n.outputs["Fac"], bp.inputs["Height"])
        nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    if alpha < 1.0:
        m.surface_render_method = "BLENDED"
    m.diffuse_color = (*base, 1.0)
    m["detail4_pkg"] = KEY
    return m


def _mats():
    return {
        "wire": _principled(PFX + "WireWhite", (0.80, 0.80, 0.78), 0.38, coat=0.1),
        "spray_g": _principled(PFX + "SprayGreen", (0.06, 0.42, 0.16), 0.22, transmission=0.0, coat=0.2),
        "spray_b": _principled(PFX + "SprayBlueClear", (0.30, 0.55, 0.75), 0.15, coat=0.3),
        "trigger": _principled(PFX + "TriggerWhite", (0.78, 0.78, 0.76), 0.40),
        "trigger_k": _principled(PFX + "TriggerBlack", (0.03, 0.03, 0.035), 0.45),
        "towel_w": _principled(PFX + "TerryWhite", (0.70, 0.70, 0.68), 0.95, sheen=0.6, bump=(900.0, 0.35)),
        "towel_g": _principled(PFX + "TerryGrey", (0.12, 0.13, 0.145), 0.95, sheen=0.6, bump=(900.0, 0.35)),
        "belt": _principled(PFX + "BeltLeather", (0.085, 0.038, 0.017), 0.50, bump=(260.0, 0.15)),
        "belt_edge": _principled(PFX + "BeltStitch", (0.30, 0.03, 0.03), 0.6),
        "buckle": _principled(PFX + "BuckleSteel", (0.62, 0.63, 0.65), 0.30, metal=1.0),
        "bucket": _principled(PFX + "BucketBlack", (0.025, 0.025, 0.028), 0.55),
        "chalk": _principled(PFX + "Chalk", (0.86, 0.86, 0.84), 1.0, bump=(300.0, 0.4)),
    }


def _obj(name, me, c, mw=None):
    ob = bpy.data.objects.new(name, me)
    c.objects.link(ob)
    if mw is not None:
        ob.matrix_world = mw
    ob["detail4_pkg"] = KEY
    return ob


def _bm_to_mesh(bm, name, mats, smooth=True):
    me = bpy.data.meshes.new(name)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = smooth
    return me


def _tube(bm, pts, r, sides=6, cyclic=False, mat=0):
    """Sweep a circle of radius r along a polyline; adds geometry to bm."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    rings = []
    ref = Vector((0, 0, 1))
    for i, p in enumerate(pts):
        if cyclic:
            t = (pts[(i + 1) % n] - pts[i - 1]).normalized()
        else:
            a = pts[max(i - 1, 0)]
            b = pts[min(i + 1, n - 1)]
            t = (b - a).normalized()
        if abs(t.dot(ref)) > 0.9:
            ref = Vector((1, 0, 0))
        u = t.cross(ref).normalized()
        v = t.cross(u).normalized()
        ring = [bm.verts.new(p + (u * math.cos(2 * math.pi * k / sides) + v * math.sin(2 * math.pi * k / sides)) * r)
                for k in range(sides)]
        rings.append(ring)
    segs = n if cyclic else n - 1
    for i in range(segs):
        a, b = rings[i], rings[(i + 1) % n]
        for k in range(sides):
            f = bm.faces.new((a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k]))
            f.material_index = mat
    if not cyclic:
        for ring, rev in ((rings[0], True), (rings[-1], False)):
            f = bm.faces.new(list(reversed(ring)) if rev else ring)
            f.material_index = mat


def _sweep_rect(bm, pts, side, width, thick, mat=0):
    """Sweep a width x thick rectangle along a polyline; `side` = fixed width direction."""
    pts = [Vector(p) for p in pts]
    side = Vector(side).normalized()
    rings = []
    for i, p in enumerate(pts):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, len(pts) - 1)]
        t = (b - a).normalized()
        nrm = t.cross(side).normalized()
        hw, ht = side * (width / 2), nrm * (thick / 2)
        rings.append([bm.verts.new(p - hw - ht), bm.verts.new(p + hw - ht), bm.verts.new(p + hw + ht),
                      bm.verts.new(p - hw + ht)])
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for k in range(4):
            f = bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
            f.material_index = mat
    bm.faces.new(list(reversed(rings[0]))).material_index = mat
    bm.faces.new(rings[-1]).material_index = mat


def _sweep_cloth(bm, pts, side, width, thick, mat=0, nw=12, folds=2.3, amp=0.012, calm=0.06,
                 soft=None):
    """Cloth strip: like _sweep_rect but the width is subdivided and rippled (soft folds) away from the
    highest point of the path (where the cloth rests on something it stays flat).
    soft (dict, optional) makes a hanging towel less board-like, all by shape:
      taper   - width lost at the hem of each tail (cloth gathers as it falls), fraction
      grow    - extra fold depth per metre of fall (folds deepen towards the hem)
      support - (minus, plus) distance from the strip centre to the edges of what it rests on, along side;
                the part beyond it droops over the edge
      droop   - drop (m) per metre of overhang at the support
      skew    - hem unevenness: along-path offset (m) between the two side edges at the hem"""
    soft = soft or {}
    taper, grow = soft.get("taper", 0.0), soft.get("grow", 0.0)
    support, droop, skew = soft.get("support"), soft.get("droop", 0.0), soft.get("skew", 0.0)
    pts = [Vector(p) for p in pts]
    side = Vector(side).normalized()
    peak = max(range(len(pts)), key=lambda i: pts[i].z)
    dist = [0.0] * len(pts)
    for i in range(peak + 1, len(pts)):
        dist[i] = dist[i - 1] + (pts[i] - pts[i - 1]).length
    for i in range(peak - 1, -1, -1):
        dist[i] = dist[i + 1] + (pts[i] - pts[i + 1]).length
    top, bot = [], []
    for i, p in enumerate(pts):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, len(pts) - 1)]
        t = (b - a).normalized()
        nrm = t.cross(side).normalized()
        fall = max(0.0, dist[i] - calm)
        k_amp = amp * min(1.0, fall / 0.12)
        if not soft:
            wf = 1.0 - 0.06 * k_amp / max(amp, 1e-6)
        else:
            k_amp += grow * fall
            wf = 1.0 - taper * min(1.0, fall / 0.22)
        tail_end = dist[0] if i < peak else dist[-1]
        rt, rb = [], []
        for k in range(nw + 1):
            u = k / nw
            off = side * (width * (u - 0.5) * wf)
            if not soft:
                wave = nrm * (k_amp * math.sin(2 * math.pi * folds * u + 0.7 * dist[i] / 0.1))
            else:
                # two fold trains with drifting phase -> irregular, slightly diagonal folds
                w1 = math.sin(2 * math.pi * folds * u + 0.7 * dist[i] / 0.1)
                w2 = math.sin(2 * math.pi * folds * 1.7 * u - 1.3 * dist[i] / 0.1 + 1.1)
                wave = nrm * (k_amp * (w1 + 0.45 * w2) / 1.2)
            c = p + off + wave
            if soft and support is not None:
                over = abs(width * (u - 0.5) * wf) - (support[1] if u > 0.5 else support[0])
                w_top = max(0.0, 1.0 - dist[i] / 0.07)
                if over > 0 and w_top > 0:
                    c = c - Vector((0, 0, 1)) * (droop * over * w_top) - side * (math.copysign(0.35, u - 0.5) * droop * over * over * w_top)
            if soft and skew and tail_end > 0:
                h = max(0.0, (dist[i] - (tail_end - 0.10)) / 0.10)
                c = c + t * ((u - 0.5) * skew * h * (1 if i > peak else -1))
            rt.append(bm.verts.new(c + nrm * thick / 2))
            rb.append(bm.verts.new(c - nrm * thick / 2))
        top.append(rt)
        bot.append(rb)
    n = len(pts)
    for i in range(n - 1):
        for k in range(nw):
            bm.faces.new((top[i][k], top[i][k + 1], top[i + 1][k + 1], top[i + 1][k])).material_index = mat
            bm.faces.new((bot[i][k], bot[i + 1][k], bot[i + 1][k + 1], bot[i][k + 1])).material_index = mat
        bm.faces.new((top[i][0], top[i + 1][0], bot[i + 1][0], bot[i][0])).material_index = mat
        bm.faces.new((top[i][nw], bot[i][nw], bot[i + 1][nw], top[i + 1][nw])).material_index = mat
    for i, rev in ((0, False), (n - 1, True)):
        for k in range(nw):
            q = (top[i][k], bot[i][k], bot[i][k + 1], top[i][k + 1])
            bm.faces.new(tuple(reversed(q)) if rev else q).material_index = mat


def _resample(pts, step=0.015):
    pts = [Vector(p) for p in pts]
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int((b - a).length / step))
        out += [a.lerp(b, k / n) for k in range(1, n + 1)]
    return out


def _lathe(bm, prof, seg=24, mat=0, z0=0.0):
    """Revolve (r, z) profile around Z. Profile from bottom centre to top centre."""
    rings = []
    for r, z in prof:
        if r < 1e-6:
            rings.append([bm.verts.new((0, 0, z + z0))])
        else:
            rings.append([bm.verts.new((r * math.cos(2 * math.pi * k / seg), r * math.sin(2 * math.pi * k / seg), z + z0))
                          for k in range(seg)])
    for a, b in zip(rings, rings[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        for k in range(seg):
            if len(a) == 1:
                f = bm.faces.new((a[0], b[k], b[(k + 1) % seg]))
            elif len(b) == 1:
                f = bm.faces.new((a[k], a[(k + 1) % seg], b[0]))
            else:
                f = bm.faces.new((a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k]))
            f.material_index = mat


def _rbox(bm, size, center=(0, 0, 0), bevel=0.006, mat=0):
    """Bevelled box; returns all verts of the new box."""
    before = set(bm.faces)
    geom = bmesh.ops.create_cube(bm, size=1.0)
    vs = geom["verts"]
    bmesh.ops.scale(bm, vec=Vector(size), verts=vs)
    bmesh.ops.translate(bm, vec=Vector(center), verts=vs)
    if bevel > 0:
        edges = list({e for v in vs for e in v.link_edges})
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=2, affect="EDGES", profile=0.5)
    new_faces = [f for f in bm.faces if f not in before]
    for f in new_faces:
        f.material_index = mat
    return list({v for f in new_faces for v in f.verts})


# ---------------------------------------------------------------- meshes (shared data)
def _basket_mesh(m):
    L, D, H = BASKET_LDH                # x along tower face, y outwards, z height (top rim at z=0)
    bm = bmesh.new()
    hx = L / 2
    ins = 0.008                         # bottom slightly smaller than the rim (pressed wire basket)
    top = [(-hx, 0.004, 0), (hx, 0.004, 0), (hx, D, 0), (-hx, D, 0)]
    bot = [(-hx + ins, 0.004 + ins * 0.5, -H), (hx - ins, 0.004 + ins * 0.5, -H), (hx - ins, D - ins, -H),
           (-hx + ins, D - ins, -H)]
    _tube(bm, top, 0.0028, 6, cyclic=True)
    _tube(bm, [(x, y, -0.035) for x, y, _ in top], 0.0017, 6, cyclic=True)      # mid band
    _tube(bm, bot, 0.0020, 6, cyclic=True)

    def lerp(a, b, t):
        return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))
    # vertical wires on front (y=D), two sides and back
    for edge in range(4):
        a0, a1 = top[edge], top[(edge + 1) % 4]
        b0, b1 = bot[edge], bot[(edge + 1) % 4]
        length = (Vector(a1) - Vector(a0)).length
        count = max(2, int(length / 0.025))
        for k in range(1, count):
            t = k / count
            _tube(bm, [lerp(a0, a1, t), lerp(b0, b1, t)], 0.0013, 5)
    # bottom grid
    for k in range(1, 10):
        t = k / 10
        _tube(bm, [lerp(bot[0], bot[1], t), lerp(bot[3], bot[2], t)], 0.0013, 5)
    for k in (1, 2):
        t = k / 3
        _tube(bm, [lerp(bot[0], bot[3], t), lerp(bot[1], bot[2], t)], 0.0013, 5)
    # two mounting hooks behind the rim that hang on the tower (flat steel, touch the face at y=0)
    for x in (-L / 2 + 0.03, L / 2 - 0.03):
        _rbox(bm, (0.018, 0.0035, 0.06), (x, 0.00175 + 0.0002, -0.02), bevel=0.0008)
    return _bm_to_mesh(bm, PFX + "WireBasket", [m["wire"]])


def _spray_mesh(m, body_mat):
    bm = bmesh.new()
    prof = [(0, 0), (0.030, 0), (0.0325, 0.004), (0.0325, 0.135), (0.029, 0.158), (0.016, 0.172), (0.0135, 0.176),
            (0.0135, 0.186), (0, 0.186)]
    _lathe(bm, prof, 24, mat=0)
    # trigger head
    _lathe(bm, [(0, 0.186), (0.016, 0.186), (0.016, 0.198), (0.012, 0.204), (0, 0.204)], 16, mat=1)
    _rbox(bm, (0.026, 0.070, 0.030), (0, 0.020, 0.220), bevel=0.004)
    _rbox(bm, (0.014, 0.012, 0.012), (0, 0.058, 0.226), bevel=0.002)          # nozzle
    _rbox(bm, (0.016, 0.010, 0.048), (0, 0.040, 0.192), bevel=0.003)          # trigger lever
    for f in bm.faces:
        if f.calc_center_median().z > 0.187 and f.material_index == 0:
            f.material_index = 1
    return _bm_to_mesh(bm, PFX + "SprayBottle_" + body_mat.name[len(PFX):], [body_mat, m["trigger"]])


def _towel_fold_mesh(m, mat, size=(0.30, 0.17, 0.034), name="TowelFolded"):
    sx, sy, sz = size
    # layered folded towel: 3 stacked soft slabs with rounded edges
    bm = bmesh.new()
    for i, h in enumerate((0.0, sz / 3, 2 * sz / 3)):
        inset = 0.004 * i
        _rbox(bm, (sx - inset, sy - inset * 0.5, sz / 3 - 0.001), (0.0, inset * 0.25, h + sz / 6), bevel=sz / 7)
    for v in bm.verts:    # soft sag towards the open edge
        v.co.z -= 0.004 * max(0.0, v.co.y / (sy / 2)) ** 2
    return _bm_to_mesh(bm, PFX + name + "_" + mat.name[len(PFX):], [mat])


def _drape_mesh(path, side, width, thick, mat, name, amp=0.012, folds=2.3, soft=None):
    bm = bmesh.new()
    _sweep_cloth(bm, _resample(path), side, width, thick, amp=amp, folds=folds, soft=soft)
    return _bm_to_mesh(bm, PFX + name, [mat])


def _arc(c, r, a0, a1, n, plane="xz"):
    pts = []
    for k in range(n + 1):
        a = a0 + (a1 - a0) * k / n
        if plane == "xz":
            pts.append(Vector((c[0] + r * math.cos(a), c[1], c[2] + r * math.sin(a))))
        else:
            pts.append(Vector((c[0], c[1] + r * math.cos(a), c[2] + r * math.sin(a))))
    return pts


# ---------------------------------------------------------------- scene queries
_BVH = {}


def _bvh(ob, dg):
    if ob.name not in _BVH:
        _BVH[ob.name] = BVHTree.FromObject(ob, dg)
    return _BVH[ob.name]


def _ray(objs, origin, direction, dg, maxd=2.0):
    best = None
    for ob in objs:
        inv = ob.matrix_world.inverted()
        o = inv @ origin
        d = (inv.to_3x3() @ direction)
        scale = d.length
        hit = _bvh(ob, dg).ray_cast(o, d.normalized(), maxd * scale)
        if hit[0] is not None:
            w = ob.matrix_world @ hit[0]
            dist = (w - origin).length
            if best is None or dist < best[0]:
                nrm = (ob.matrix_world.to_3x3().inverted().transposed() @ hit[1]).normalized()
                best = (dist, w, nrm, ob.name)
    return best


def _machine_meshes(root):
    return [o for o in bpy.data.objects[root].children_recursive if o.type == "MESH" and not o.hide_render]


def _bbox(objs):
    cs = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    return (Vector([min(c[i] for c in cs) for i in range(3)]), Vector([max(c[i] for c in cs) for i in range(3)]))


# ---------------------------------------------------------------- builders
def _build_baskets(c, m, dg, report):
    basket = _basket_mesh(m)
    sprays = {"g": _spray_mesh(m, m["spray_g"]), "b": _spray_mesh(m, m["spray_b"])}
    towel_w = _towel_fold_mesh(m, m["towel_w"], size=(0.080, 0.094, 0.045), name="TowelSmall")
    for i, (root, contents) in enumerate(BASKETS):
        ms = _machine_meshes(root)
        shroud = [o for o in ms if o.name.startswith("Side shroud")]
        lo, hi = _bbox(shroud)
        # widest side-shroud panel on the +x face of the tower
        panels = [(o, _bbox([o])) for o in shroud]
        panels = [p for p in panels if p[1][1].x > hi.x - 0.01]
        panel, (plo, phi) = max(panels, key=lambda p: p[1][1].y - p[1][0].y)
        yc = (plo.y + phi.y) / 2
        z_top = min(phi.z - 0.30, 1.12)
        L = BASKET_LDH[0]
        face_x = phi.x
        hit = None
        for dy in (-L / 2, -L / 4, 0.0, L / 4, L / 2):
            for dz in (-0.005, -0.06, -0.115):
                h = _ray(ms, Vector((phi.x + 0.6, yc + dy, z_top + dz)), Vector((-1, 0, 0)), dg)
                if h and h[1].x > face_x - 0.05:
                    face_x = max(face_x, h[1].x)
                    hit = h
        # basket frame: local x along the face (world y), local y outwards (world +x)
        rot = Matrix.Rotation(-math.pi / 2, 4, "Z")
        mw = Matrix.Translation((face_x + 0.0012, yc, z_top)) @ rot
        b = _obj(f"{PFX}Basket_{root[2:]}", basket, c, mw)
        report.append({"basket": b.name, "face_hit": hit[3] if hit else None, "face_x": round(face_x, 4)})
        # contents (in basket local space; basket inner floor at z=-0.118)
        floor = -0.118
        col = "g" if i % 3 != 2 else "b"
        if "spray" in contents:
            lx = -0.045 if "towel" in contents else 0.0
            sm = mw @ Matrix.Translation((lx, 0.062, floor + 0.0021)) @ Matrix.Rotation(math.radians(25 + 40 * i), 4, "Z")
            _obj(f"{PFX}Spray_{root[2:]}", sprays[col], c, sm)
        if contents.endswith("+towel"):
            tm = mw @ Matrix.Translation((0.043, 0.062, floor + 0.0022))
            _obj(f"{PFX}TowelInBasket_{root[2:]}", towel_w, c, tm)
        if contents.endswith("towel_hang"):
            # towel hung over the basket's front rim: inside down 6 cm, over the rim, outside down 20 cm
            r = 0.0028 + 0.006
            path = [Vector((0, 0.12 - r - 0.001, -0.06)), Vector((0, 0.12 - r - 0.001, -0.004))]
            path += _arc((0, 0.12, 0.0), r, math.pi, 0.0, 8, plane="yz")[1:-1]
            path += [Vector((0, 0.12 + r + 0.001, -0.004)), Vector((0, 0.12 + r + 0.004, -0.10)),
                     Vector((0, 0.12 + r + 0.010, -0.21))]
            me = _drape_mesh(path, (1, 0, 0), 0.23, 0.008, m["towel_g"], f"TowelHang_{root[2:]}")
            _obj(f"{PFX}TowelHang_{root[2:]}", me, c, mw @ Matrix.Translation((0.0, 0.0, 0.0)))


def _build_plates(c, report):
    for name, sign, scales in EXTRA_PLATES:
        src = bpy.data.objects.get(name)
        if src is None:
            report.append({"plate_skip": name})
            continue
        lb = [Vector(v) for v in src.bound_box]
        thick = max(v.x for v in lb) - min(v.x for v in lb)
        offset = 0.0
        for k, s in enumerate(scales):
            offset += thick + 0.0015
            # local x is the thin axis; world shift along +-x
            mw = Matrix.Translation((sign * offset, 0, 0)) @ src.matrix_world @ Matrix.Diagonal((1.0, s, s, 1.0))
            ob = _obj(f"{PFX}Plate_{name.replace('.', '_')}_{k}", src.data, c, mw)
            report.append({"plate": ob.name, "from": name, "scale": s})


def _build_belt(c, m, dg, report):
    safety = bpy.data.objects.get("safety")
    strip = bpy.data.objects.get("Safety landing strip")
    if safety is None:
        return
    lo, hi = _bbox([safety] + ([strip] if strip else []))
    yb = 3.74
    top = hi.z
    xc = (lo.x + hi.x) / 2
    half = (hi.x - lo.x) / 2
    t = 0.007
    r = half + t / 2 + 0.002
    path = [Vector((xc - r, yb, top - 0.30)), Vector((xc - r, yb, top - 0.12)), Vector((xc - r, yb, top - 0.02))]
    path += _arc((xc, yb, top - 0.02), r, math.pi, 0.0, 10, plane="xz")[1:-1]
    # top of arc must clear the strip: centre at top-0.02, radius r >= 0.02 + t/2 + gap
    path += [Vector((xc + r, yb, top - 0.02)), Vector((xc + r, yb, top - 0.14)), Vector((xc + r + 0.004, yb, top - 0.36))]
    path.reverse()          # tail with the buckle hangs on the outside (-x) of the rack
    # make sure the arc's highest point is above the strip
    peak = max(p.z for p in path)
    if peak - t / 2 < top + 0.0015:
        lift = top + 0.0015 - (peak - t / 2)
        path = [p + Vector((0, 0, lift)) if p.z > top - 0.05 else p for p in path]
    bm = bmesh.new()
    _sweep_rect(bm, path, (0, 1, 0), 0.100, t, mat=0)
    # buckle on the outer tail end + keeper loop
    end = path[-1]
    _rbox(bm, (0.010, 0.078, 0.055), (end.x - t / 2 - 0.0055, yb, end.z + 0.06), bevel=0.003, mat=1)
    _rbox(bm, (0.012, 0.108, 0.022), (end.x - t / 2 - 0.0065, yb, end.z + 0.13), bevel=0.003, mat=0)
    me = _bm_to_mesh(bm, PFX + "LiftingBelt", [m["belt"], m["buckle"]])
    for p in me.polygons:
        p.use_smooth = p.material_index == 0
    ob = _obj(PFX + "LiftingBelt_on_safety", me, c)
    report.append({"belt": ob.name, "bar_top": round(top, 4)})


def _build_chalk(c, m, report, loc=(1.48, 3.86)):
    bm = bmesh.new()
    wall = 0.006
    outer = [(0, 0.0), (0.130, 0.0), (0.134, 0.004), (0.150, 0.215), (0.156, 0.22)]
    inner = [(0.150 - wall, 0.22), (0.134 - wall, 0.012), (0, 0.012)]
    _lathe(bm, outer + inner, 32, mat=0)
    # chalk powder bed + two blocks
    _lathe(bm, [(0, 0.128), (0.134, 0.128), (0.134, 0.132), (0.10, 0.136), (0.05, 0.139), (0, 0.140)], 32, mat=1)
    for (x, y, rz) in ((0.03, -0.02, 20), (-0.05, 0.03, -35)):
        vs = _rbox(bm, (0.11, 0.055, 0.045), (0, 0, 0), bevel=0.008, mat=1)
        bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(rz), 3, "Z"))
        bmesh.ops.translate(bm, verts=vs, vec=(x, y, 0.136 + 0.012))
    me = _bm_to_mesh(bm, PFX + "ChalkBucket", [m["bucket"], m["chalk"]])
    ob = _obj(PFX + "ChalkBucket", me, c, Matrix.Translation((loc[0], loc[1], 0.0055)))
    report.append({"chalk": ob.name, "loc": loc})


def _push_out(path, objs, dg, side, width, clearance):
    """Move each path point away from nearby surfaces so the swept strip keeps `clearance`."""
    side = Vector(side).normalized()
    out = []
    for p in path:
        q = p.copy()
        for _ in range(4):
            worst = None
            for off in (-width / 2, -width / 4, 0.0, width / 4, width / 2):
                probe = q + side * off
                for ob in objs:
                    inv = ob.matrix_world.inverted()
                    loc, nrm, idx, dist = _bvh(ob, dg).find_nearest(inv @ probe, 1.0)
                    if loc is None:
                        continue
                    w = ob.matrix_world @ loc
                    d = (probe - w).length
                    if d < clearance and (worst is None or d < worst[0]):
                        n = (probe - w).normalized() if d > 1e-6 else \
                            (ob.matrix_world.to_3x3().inverted().transposed() @ nrm).normalized()
                        worst = (d, n)
            if worst is None:
                break
            q += worst[1] * (clearance - worst[0] + 0.0005)
        out.append(q)
    return out


def _build_seat_towels(c, m, dg, report):
    # 1) folded towel on the leg-curl seat: rest on the highest of 9 probe points under its footprint
    seat = bpy.data.objects.get("seat.006")
    if seat:
        lo, hi = _bbox([seat])
        cx, cy = (lo.x + hi.x) / 2 + 0.02, (lo.y + hi.y) / 2 + 0.03
        size = (0.30, 0.17, 0.030)
        rz = Matrix.Rotation(math.radians(8), 4, "Z")
        zs = []
        for fx in (-0.5, 0.0, 0.5):
            for fy in (-0.5, 0.0, 0.5):
                off = rz @ Vector((fx * size[0], fy * size[1], 0))
                h = _ray([seat], Vector((cx + off.x, cy + off.y, hi.z + 0.3)), Vector((0, 0, -1)), dg)
                if h:
                    zs.append(h[1].z)
        z = max(zs) if zs else hi.z
        me = _towel_fold_mesh(m, m["towel_w"], size=size, name="TowelSeat")
        ob = _obj(PFX + "Towel_on_legcurl_seat", me, c, Matrix.Translation((cx, cy, z + 0.0015)) @ rz)
        report.append({"towel": ob.name, "z": round(z, 4)})
    # 2) towel hung over the chest-press back pad (along y over the pad top, both tails hanging)
    back = bpy.data.objects.get("back.004")
    post = bpy.data.objects.get("back_post.001")
    if back:
        lo, hi = _bbox([back])
        plo, phi = _bbox([post]) if post else (lo, hi)
        xc = (lo.x + hi.x) / 2 - 0.04
        t, w = 0.008, 0.30
        g = t / 2 + 0.002
        y_rear = min(lo.y, plo.y) - g - 0.022           # room for the deeper hem folds in front of the post
        # front tail swings a little off the pad towards the hem instead of lying glued to it
        path = [Vector((xc, hi.y + g + 0.022, hi.z - 0.31)), Vector((xc, hi.y + g + 0.008, hi.z - 0.20)),
                Vector((xc, hi.y + g + 0.001, hi.z - 0.11)), Vector((xc, hi.y + g, hi.z - 0.04))]
        ztop = max(hi.z, phi.z)
        path += _arc((xc, hi.y - 0.03, ztop - 0.03), 0.03 + g, 0.0, math.pi / 2, 4, plane="yz")[1:]
        path += [Vector((xc, (lo.y + hi.y) / 2, ztop + g))]
        path += _arc((xc, y_rear + g + 0.03, ztop - 0.03), 0.03 + g, math.pi / 2, math.pi, 4, plane="yz")[1:]
        path += [Vector((xc, y_rear, ztop - 0.08)), Vector((xc, y_rear - 0.010, ztop - 0.15))]
        objs = [o for o in (back, post) if o]
        path = _push_out(path, objs, dg, (1, 0, 0), w, g)
        half, shift = (hi.x - lo.x) / 2, xc - (lo.x + hi.x) / 2       # towel centre is 4 cm off the pad centre
        support = (half + shift + 0.004, half - shift + 0.004)
        soft = {"taper": 0.16, "grow": 0.05, "support": support, "droop": 0.9, "skew": 0.035}
        me = _drape_mesh(path, (1, 0, 0), w, t, m["towel_g"], "TowelOverBack", amp=0.010, folds=2.0, soft=soft)
        ob = _obj(PFX + "Towel_over_chestpress_back", me, c)
        report.append({"towel": ob.name})


def apply() -> dict:
    _BVH.clear()
    c = _coll()
    m = _mats()
    dg = bpy.context.evaluated_depsgraph_get()
    report = []
    _build_baskets(c, m, dg, report)
    _build_plates(c, report)
    _build_belt(c, m, dg, report)
    _build_chalk(c, m, report)
    _build_seat_towels(c, m, dg, report)
    for me in {o.data for o in c.objects}:
        if me.name.startswith(PFX):
            me["detail4_pkg"] = KEY
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in c.objects)
    unique = sum(sum(len(p.vertices) - 2 for p in me.polygons) for me in {o.data for o in c.objects})
    return {"objects_added": len(c.objects), "triangles_added": tris, "unique_mesh_triangles": unique,
            "objects_touched": [], "details": report}


def _main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    res = apply()
    print(f"[detail4_{KEY}] {json.dumps(res)}")
    if "--save" in argv:
        out = argv[argv.index("--save") + 1]
        if "promo/scenes" in out or "promo/models" in out:
            raise SystemExit("refusing to save into promo/scenes or promo/models")
        bpy.ops.wm.save_as_mainfile(filepath=out, copy=True, compress=True)
        print(f"[detail4_{KEY}] saved copy -> {out}")


if __name__ == "__main__":
    _main()
