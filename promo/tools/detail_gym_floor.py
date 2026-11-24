"""Gym floor zoning detail pass (package key: gym_floor).

Real Korean gyms split the floor into zones instead of one flat black surface:
  * machine floor: black EPDM rubber with fine light-grey flecks (refs gym 207 209 213 216 138 139 140)
  * free-weight / rack area: heavier 1 m EPDM tiles with grey + a few blue flecks, visible tile seams,
    edged with a satin aluminium L-trim where it meets other flooring (refs 207 208 209 212 216 164 172)
  * main walkway + cardio line: wood-look deco tile (데코타일) planks, aluminium reducer trim at the
    rubber edge (refs 217 218 252 246 207 209)
  * stretching zone: the existing pad gets a darker wood-deck finish + aluminium edge trim (refs 247 253)
  * deadlift platform: existing rubber sides switch to the free-weight EPDM (ref 164 140)

Usage (scene open):  import sys; sys.path.insert(0, "promo/tools"); import detail_gym_floor; detail_gym_floor.apply()
"""
import json
import sys
import os

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

KEY = "gym_floor"
COLL = "DETAIL_gym_floor"
P = "Dgym_floor_"

# ---- zone layout (world metres; floor top z = 0, gym x -7.5..13.5, y -6.68..4.97) --------------------
FW_X = (-3.45, 10.20)   # free-weight tiles: clear of cable crossover (x<=-3.55) and selfie stool (x>=10.57)
FW_Y = (2.20, 4.955)    # clear of kettlebells (y<=2.11) up to the mirror wall (wainscot y 4.97)
FW_TOP = 0.004          # 4 mm proud of the machine floor
WALK_X = (-3.55, 10.80)  # wood walkway along the locker wall, from the info-desk pad to the cardio line
WALK_Y = (-6.665, -3.70)  # front wainscot at y -6.68, machine row 1 starts at y -3.45
CARD_X = (10.80, 13.455)  # cardio line: right of the pillar (x<=10.64), to the right wainscot (13.47)
CARD_Y = (-3.70, 2.58)    # treadmills end at y 2.51, selfie stool starts at 2.61
WOOD_TOP = 0.004
TRIM_W, TRIM_TOP = 0.030, 0.0065


# ---------------------------------------------------------------- materials
def _principled(name):
    m = bpy.data.materials.get(name)
    if m:
        return m, None
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def _epdm(name, base, flecks, cell, radius, tile=None, rough=0.86):
    """Black EPDM rubber: random Voronoi cells become flecks. flecks = [(rgb, share), ...] (shares sum = coverage).
    tile = (pitch, offset) gives each tile its own slight value/sheen shift."""
    m, b = _principled(name)
    if b is None:
        return m
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    m.diffuse_color = (*base, 1)
    geo = N.new("ShaderNodeNewGeometry")
    vor = N.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 1.0 / cell
    L.new(geo.outputs["Position"], vor.inputs["Vector"])
    sep = N.new("ShaderNodeSeparateColor")
    L.new(vor.outputs["Color"], sep.inputs["Color"])
    # cell selected as fleck when its random R < total coverage AND we are near the cell centre
    cover = sum(s for _, s in flecks)
    sel = N.new("ShaderNodeMath"); sel.operation = "LESS_THAN"; sel.inputs[1].default_value = cover
    L.new(sep.outputs["Red"], sel.inputs[0])
    near = N.new("ShaderNodeMath"); near.operation = "LESS_THAN"; near.inputs[1].default_value = radius / cell  # Voronoi distance is in cell units
    L.new(vor.outputs["Distance"], near.inputs[0])
    mask = N.new("ShaderNodeMath"); mask.operation = "MULTIPLY"
    L.new(sel.outputs["Value"], mask.inputs[0]); L.new(near.outputs["Value"], mask.inputs[1])
    # fleck colour from the cell's random G (constant ramp)
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    acc = 0.0
    for i, (rgb, share) in enumerate(flecks):
        e = els[i] if i < len(els) else els.new(acc)
        e.position = acc
        e.color = (*rgb, 1)
        acc += share / cover
    while len(els) > len(flecks):
        els.remove(els[-1])
    L.new(sep.outputs["Green"], ramp.inputs["Fac"])
    mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"
    L.new(mask.outputs["Value"], mix.inputs["Factor"])
    mix.inputs["A"].default_value = (*base, 1)
    L.new(ramp.outputs["Color"], mix.inputs["B"])
    col_out = mix.outputs["Result"]
    rough_src = None
    if tile:
        pitch, off = tile
        add = N.new("ShaderNodeVectorMath"); add.operation = "ADD"; add.inputs[1].default_value = off
        L.new(geo.outputs["Position"], add.inputs[0])
        snap = N.new("ShaderNodeVectorMath"); snap.operation = "SNAP"; snap.inputs[1].default_value = (pitch, pitch, pitch)
        L.new(add.outputs["Vector"], snap.inputs[0])
        wn = N.new("ShaderNodeTexWhiteNoise")
        L.new(snap.outputs["Vector"], wn.inputs["Vector"])
        shade = N.new("ShaderNodeMapRange")
        shade.inputs["To Min"].default_value, shade.inputs["To Max"].default_value = 0.88, 1.12
        L.new(wn.outputs["Value"], shade.inputs["Value"])
        mul = N.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"
        mul.inputs["Factor"].default_value = 1.0
        L.new(col_out, mul.inputs["A"])
        cmb = N.new("ShaderNodeCombineColor")
        for ch in ("Red", "Green", "Blue"):
            L.new(shade.outputs["Result"], cmb.inputs[ch])
        L.new(cmb.outputs["Color"], mul.inputs["B"])
        col_out = mul.outputs["Result"]
        rough_src = wn.outputs["Value"]
    L.new(col_out, b.inputs["Base Color"])
    # roughness: broad scuff noise + per-tile sheen; flecks a touch smoother
    wear = N.new("ShaderNodeTexNoise"); wear.inputs["Scale"].default_value = 0.6; wear.inputs["Detail"].default_value = 4.0
    L.new(geo.outputs["Position"], wear.inputs["Vector"])
    rmix = N.new("ShaderNodeMix"); rmix.data_type = "FLOAT"; rmix.inputs["Factor"].default_value = 0.4
    L.new(wear.outputs["Fac"], rmix.inputs["A"])
    if rough_src:
        L.new(rough_src, rmix.inputs["B"])
    else:
        rmix.inputs["B"].default_value = 0.5
    rr = N.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value, rr.inputs["To Max"].default_value = rough - 0.16, rough + 0.06
    L.new(rmix.outputs["Result"], rr.inputs["Value"])
    L.new(rr.outputs["Result"], b.inputs["Roughness"])
    b.inputs["Specular IOR Level"].default_value = 0.35
    # granules: fine bump from the fleck mask + grain noise
    grain = N.new("ShaderNodeTexNoise"); grain.inputs["Scale"].default_value = 260.0
    L.new(geo.outputs["Position"], grain.inputs["Vector"])
    h = N.new("ShaderNodeMath"); h.operation = "ADD"
    L.new(grain.outputs["Fac"], h.inputs[0]); L.new(mask.outputs["Value"], h.inputs[1])
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.18; bump.inputs["Distance"].default_value = 0.0008
    L.new(h.outputs["Value"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def _wood_deco(name, c1, c2, plank=(1.22, 0.18), rough=0.42, offset=0.37):
    """Wood-look vinyl deco tile (데코타일): random-offset planks along world X, thin dark joints, grain."""
    m, b = _principled(name)
    if b is None:
        return m
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    m.diffuse_color = (*c1, 1)
    geo = N.new("ShaderNodeNewGeometry")
    brick = N.new("ShaderNodeTexBrick")
    brick.offset = offset
    brick.offset_frequency = 1
    brick.squash = 1.0
    brick.inputs["Scale"].default_value = 1.0
    brick.inputs["Brick Width"].default_value = plank[0]
    brick.inputs["Row Height"].default_value = plank[1]
    brick.inputs["Mortar Size"].default_value = 0.0011
    brick.inputs["Mortar Smooth"].default_value = 0.4
    brick.inputs["Bias"].default_value = 0.0
    brick.inputs["Color1"].default_value = (*c1, 1)
    brick.inputs["Color2"].default_value = (*c2, 1)
    brick.inputs["Mortar"].default_value = (c2[0] * 0.35, c2[1] * 0.35, c2[2] * 0.35, 1)
    L.new(geo.outputs["Position"], brick.inputs["Vector"])
    # grain runs along the plank (X): stretch the noise space across Y
    sc = N.new("ShaderNodeVectorMath"); sc.operation = "MULTIPLY"; sc.inputs[1].default_value = (0.6, 38.0, 1.0)
    L.new(geo.outputs["Position"], sc.inputs[0])
    grain = N.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = 1.6; grain.inputs["Detail"].default_value = 6.0
    grain.inputs["Distortion"].default_value = 1.2
    L.new(sc.outputs["Vector"], grain.inputs["Vector"])
    gr = N.new("ShaderNodeMapRange")
    gr.inputs["From Min"].default_value, gr.inputs["From Max"].default_value = 0.3, 0.7
    gr.inputs["To Min"].default_value, gr.inputs["To Max"].default_value = 0.80, 1.12
    L.new(grain.outputs["Fac"], gr.inputs["Value"])
    mul = N.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.inputs["Factor"].default_value = 1.0
    L.new(brick.outputs["Color"], mul.inputs["A"])
    cmb = N.new("ShaderNodeCombineColor")
    for ch in ("Red", "Green", "Blue"):
        L.new(gr.outputs["Result"], cmb.inputs[ch])
    L.new(cmb.outputs["Color"], mul.inputs["B"])
    L.new(mul.outputs["Result"], b.inputs["Base Color"])
    # satin vinyl wear layer: slightly rougher in the joints and along broad scuffs
    wear = N.new("ShaderNodeTexNoise"); wear.inputs["Scale"].default_value = 0.8
    L.new(geo.outputs["Position"], wear.inputs["Vector"])
    rr = N.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value, rr.inputs["To Max"].default_value = rough - 0.08, rough + 0.12
    L.new(wear.outputs["Fac"], rr.inputs["Value"])
    rj = N.new("ShaderNodeMath"); rj.operation = "MAXIMUM"
    L.new(rr.outputs["Result"], rj.inputs[0]); L.new(brick.outputs["Fac"], rj.inputs[1])
    L.new(rj.outputs["Value"], b.inputs["Roughness"])
    inv = N.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0
    L.new(brick.outputs["Fac"], inv.inputs[1])
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.35; bump.inputs["Distance"].default_value = 0.0008
    L.new(inv.outputs["Value"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def _materials():
    light, mid, blue = (0.40, 0.40, 0.38), (0.16, 0.16, 0.16), (0.08, 0.15, 0.30)
    return {
        # machine floor: light-grey granules ~6 mm, ~12 % coverage (refs 207 209 213)
        "base": _epdm(P + "EPDM_Machine", (0.018, 0.018, 0.020),
                      [(light, 0.25), (mid, 0.20)], cell=0.010, radius=0.003,
                      tile=(0.60, (0.0, 0.2, 0.1)), rough=0.86),
        # free-weight 1 m tiles: blacker base, denser grey + blue granules (refs 208 213 216)
        "fw": _epdm(P + "EPDM_FreeWeight", (0.011, 0.011, 0.013),
                    [(light, 0.30), (mid, 0.20), (blue, 0.20)], cell=0.010, radius=0.003,
                    tile=(1.0, (-FW_X[0], -FW_Y[1], 0.0)), rough=0.80),
        "wood": _wood_deco(P + "DecoTile_Oak", (0.30, 0.150, 0.060), (0.20, 0.100, 0.042)),
        "deck": _wood_deco(P + "DecoTile_Walnut", (0.095, 0.056, 0.032), (0.062, 0.037, 0.022),
                           plank=(0.90, 0.15), rough=0.40, offset=0.5),
        "trim": _alu(),
    }


def _alu():
    m, b = _principled(P + "TrimAlu")
    if b is None:
        return m
    m.diffuse_color = (0.75, 0.75, 0.76, 1)
    b.inputs["Base Color"].default_value = (0.78, 0.78, 0.79, 1)
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.30
    b.inputs["Anisotropic"].default_value = 0.4
    return m


# ---------------------------------------------------------------- geometry helpers
def _obj(name, bm, mat, c, smooth_bevel=None):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    c.objects.link(ob)
    return ob


def _add_box(bm, x0, x1, y0, y1, z0, z1, bevel=0.0):
    r = bmesh.ops.create_cube(bm, size=1.0)
    vs = r["verts"]
    for v in vs:
        v.co.x = x0 if v.co.x < 0 else x1
        v.co.y = y0 if v.co.y < 0 else y1
        v.co.z = z0 if v.co.z < 0 else z1
    if bevel > 0:
        top = [e for e in {e for v in vs for e in v.link_edges}
               if all(v.co.z > z1 - 1e-6 for v in e.verts)]
        bmesh.ops.bevel(bm, geom=top, offset=bevel, segments=1, affect="EDGES", profile=0.5)
    return vs


def _tiles(c, mat):
    """Free-weight zone: 1 m tiles laid from the mirror wall forward; 2 mm seams; 1.2 mm top chamfer."""
    bm = bmesh.new()
    gap = 0.001
    y = FW_Y[1]
    while y > FW_Y[0] + 1e-6:
        y0 = max(FW_Y[0], y - 1.0)
        x = FW_X[0]
        while x < FW_X[1] - 1e-6:
            x1 = min(FW_X[1], x + 1.0)
            _add_box(bm, x + gap, x1 - gap, y0 + gap, y - gap, -0.004, FW_TOP, bevel=0.0012)
            x = x1
        y = y0
    return _obj(P + "FreeWeight_Tiles", bm, mat, c)


def _wood_slab(c, mat):
    """One L-shaped deco-tile slab: walkway along the locker wall + cardio line (3 mm tile, top z 4 mm)."""
    bm = bmesh.new()
    pts = [(WALK_X[0], WALK_Y[0]), (CARD_X[1], WALK_Y[0]), (CARD_X[1], CARD_Y[1]),
           (CARD_X[0], CARD_Y[1]), (CARD_X[0], WALK_Y[1]), (WALK_X[0], WALK_Y[1])]
    vs = [bm.verts.new((x, y, WOOD_TOP - 0.006)) for x, y in pts]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f], use_keep_orig=True)
    up = [g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=up, vec=(0, 0, 0.006))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    return _obj(P + "DecoTile_Walkway_Cardio", bm, mat, c)


def _trims(c, mat):
    """Satin aluminium L-trims / reducers on every exposed flooring edge (refs 207 209 216)."""
    bm = bmesh.new()
    w, t = TRIM_W, TRIM_TOP
    h = w / 2
    fw = 0.018  # slimmer L-trim on the rubber-on-rubber free-weight edge
    runs = [  # (axis the trim runs along, fixed coord, start, end, width); corners butt, never overlap
        # wood walkway & cardio edges against the machine rubber
        ("x", WALK_X[0], WALK_Y[0], WALK_Y[1] - h, w),
        ("y", WALK_Y[1], WALK_X[0] - h, CARD_X[0] - h, w),
        ("x", CARD_X[0], WALK_Y[1] - h, CARD_Y[1] + h, w),
        ("y", CARD_Y[1], CARD_X[0] + h, CARD_X[1], w),
        # free-weight tiles: front edge + both open ends (back edge is the mirror wall)
        ("y", FW_Y[0] - 0.001 - fw / 2, FW_X[0] - 0.001 - fw, FW_X[1] + 0.001 + fw, fw),
        ("x", FW_X[0] - 0.001 - fw / 2, FW_Y[0] - 0.001, FW_Y[1], fw),
        ("x", FW_X[1] + 0.001 + fw / 2, FW_Y[0] - 0.001, FW_Y[1], fw),
    ]
    for axis, k, a0, a1, ww in runs:
        if axis == "x":
            _add_box(bm, k - ww / 2, k + ww / 2, a0, a1, -0.002, t, bevel=0.0025)
        else:
            _add_box(bm, a0, a1, k - ww / 2, k + ww / 2, -0.002, t, bevel=0.0025)
    return _obj(P + "Trims_Alu", bm, mat, c)


def _stretch_trim(c, mat):
    """Aluminium L-edge around the existing stretching pad (top z 14 mm); wall side open, roller rack left clear."""
    pad = bpy.data.objects.get("Stretching zone mat base")
    if pad is None:
        return None
    cs = [pad.matrix_world @ Vector(v) for v in pad.bound_box]
    x0, x1 = min(v.x for v in cs), max(v.x for v in cs)
    y0, y1 = min(v.y for v in cs), max(v.y for v in cs)
    top = max(v.z for v in cs) + 0.002
    bm = bmesh.new()
    t = 0.004
    _add_box(bm, x1 + 0.001, x1 + 0.001 + t, y0 - 0.001 - t, y1 + 0.001 + t, -0.002, top, bevel=0.001)
    _add_box(bm, x0, x1 + 0.001, y0 - 0.001 - t, y0 - 0.001, -0.002, top, bevel=0.001)
    _add_box(bm, -6.98, x1 + 0.001, y1 + 0.001, y1 + 0.001 + t, -0.002, top, bevel=0.001)  # roller rack ends x -7.02
    return _obj(P + "Stretch_EdgeTrim", bm, mat, c)


# ---------------------------------------------------------------- existing-object material swaps
def _swap(name, mat):
    ob = bpy.data.objects.get(name)
    if ob is None or not ob.material_slots:
        return None
    slot = ob.material_slots[0]
    if "dgf_orig" not in ob:
        ob["dgf_orig"] = json.dumps({"link": slot.link, "material": slot.material.name if slot.material else None})
    ob["detail_pkg"] = KEY
    slot.link = "OBJECT"           # object-level slot: the original mesh/material stay untouched
    slot.material = mat
    return name


def restore():
    """Undo the material swaps (keeps the added collection)."""
    for ob in bpy.data.objects:
        if ob.get("detail_pkg") == KEY and "dgf_orig" in ob:
            st = json.loads(ob["dgf_orig"])
            slot = ob.material_slots[0]
            slot.material = None
            slot.link = st["link"]
            del ob["dgf_orig"]
            del ob["detail_pkg"]


# ---------------------------------------------------------------- entry point
def apply() -> dict:
    parent = bpy.data.collections["SET"]
    c = bpy.data.collections.get(COLL)
    if c is None:
        c = bpy.data.collections.new(COLL)
        parent.children.link(c)
    for ob in list(c.objects):
        me = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if me and me.users == 0:
            bpy.data.meshes.remove(me)

    M = _materials()
    added = [
        _tiles(c, M["fw"]),
        _wood_slab(c, M["wood"]),
        _trims(c, M["trim"]),
        _stretch_trim(c, M["trim"]),
    ]
    added = [o for o in added if o]
    touched = [n for n in (
        _swap("RubberFloorTiles", M["base"]),
        _swap("Platform_Base", M["fw"]),
        _swap("Stretching zone mat base", M["deck"]),
    ) if n]

    dg = bpy.context.evaluated_depsgraph_get()
    tris, bbox = 0, {}
    for ob in added:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh(); me.calc_loop_triangles()
        tris += len(me.loop_triangles)
        ws = [ob.matrix_world @ v.co for v in me.vertices]
        bbox[ob.name] = [round(min(v[i] for v in ws), 3) for i in range(3)] + \
                        [round(max(v[i] for v in ws), 3) for i in range(3)]
        ev.to_mesh_clear()
    return {"collection": COLL, "objects_added": [o.name for o in added], "triangles_added": tris,
            "existing_touched": touched, "bbox_world": bbox}


if __name__ == "__main__":
    print("DETAIL_GYM_FLOOR", apply())
