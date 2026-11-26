"""detail4 P7 wet_tiles: softer, non-repeating marble wall tiles and wet floor tiles in the men's/women's showers.

Materials are duplicated, never edited in place:
- `Dgym_wet_ShowerMarble_XZ/_YZ` users get `D4wet_Marble_XZ/_YZ`: 600x1200 portrait tiles, 3 mm mid-grey (0.60) grout,
  light warm base, thin low-contrast primary veins + finer secondary veins, vein position AND angle random per
  tile (tile id -> white noise -> rotate/offset vein coordinates), gloss 0.15-0.25.
  (ref work/refs/interior/026, 041, 042, 043, 046, 049)
- `Dgym_wet_AntiSlipTile` users get `D4wet_FloorWet`: same dark 300 mm tiles, plus wet glossy patches spreading
  from every floor/booth/linear drain (booth drains reach the booth fronts), and faint water-stained grout there
  (ref interior/046 glossy wet black floor, 049).
Original material names are stored on each object (`detail4_orig_materials`), re-runs restore them first.
Glass (`Suite_ClearGlass`, `Suite_FrostGlass`) and mirrors are not touched. No new geometry.

Run standalone (never saves unless --save is given):
  Blender -b promo/scenes/scene_gym.blend --python promo/tools/detail4_wet_tiles.py [-- --save out.blend]
"""
import json
import sys

import bpy

KEY = "wet_tiles"
COLL = "DETAIL4_wet_tiles"          # no new objects; kept for the shared API
PFX = "D4wet_"
SWAP = {
    "Dgym_wet_ShowerMarble_XZ": PFX + "Marble_XZ",
    "Dgym_wet_ShowerMarble_YZ": PFX + "Marble_YZ",
    "Dgym_wet_AntiSlipTile": PFX + "FloorWet",
}
DRAIN_PREFIXES = ("Dgym_wet_Floor drain grate", "Men Booth drain", "Women Booth drain",
                  "Men Entrance linear drain", "Women Entrance linear drain")


def _nodes(m):
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    return nt, nt.nodes, nt.links


def _n(nodes, kind, loc, **inputs):
    nd = nodes.new(kind)
    nd.location = loc
    for k, v in inputs.items():
        nd.inputs[k].default_value = v
    return nd


def _math(nodes, links, op, a, b=None, loc=(0, 0), clamp=False):
    nd = nodes.new("ShaderNodeMath")
    nd.operation = op
    nd.use_clamp = clamp
    nd.location = loc
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            nd.inputs[i].default_value = v
        else:
            links.new(v, nd.inputs[i])
    return nd.outputs[0]


def _vein(nodes, links, vec, scale, width, detail, distortion, loc):
    """Thin marble vein mask 0..1 from |noise-0.5| < width (smooth edges)."""
    nz = _n(nodes, "ShaderNodeTexNoise", loc, Scale=scale, Detail=detail, Roughness=0.55, Distortion=distortion)
    nz.noise_dimensions = "3D"
    links.new(vec, nz.inputs["Vector"])
    d = _math(nodes, links, "SUBTRACT", nz.outputs["Fac"], 0.5, (loc[0] + 200, loc[1]))
    d = _math(nodes, links, "ABSOLUTE", d, None, (loc[0] + 360, loc[1]))
    mr = nodes.new("ShaderNodeMapRange")
    mr.location = (loc[0] + 520, loc[1])
    mr.interpolation_type = "SMOOTHSTEP"
    mr.inputs["From Min"].default_value = width
    mr.inputs["From Max"].default_value = 0.0
    links.new(d, mr.inputs["Value"])
    return mr.outputs["Result"]


def _marble(name, axis):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    nt, N, L = _nodes(m)
    out = _n(N, "ShaderNodeOutputMaterial", (1900, 0))
    bsdf = _n(N, "ShaderNodeBsdfPrincipled", (1550, 0))
    bsdf.inputs["Specular IOR Level"].default_value = 0.5
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    geo = _n(N, "ShaderNodeNewGeometry", (-1600, 0))
    sep = _n(N, "ShaderNodeSeparateXYZ", (-1420, 0))
    L.new(geo.outputs["Position"], sep.inputs["Vector"])
    uv = _n(N, "ShaderNodeCombineXYZ", (-1240, 0), Z=0.0)
    L.new(sep.outputs["X" if axis == "XZ" else "Y"], uv.inputs["X"])
    L.new(sep.outputs["Z"], uv.inputs["Y"])
    p = uv.outputs["Vector"]
    # tile id (600 x 1200 portrait, stacked) -> random vector per tile
    tid = _n(N, "ShaderNodeVectorMath", (-1060, 200))
    tid.operation = "SNAP"
    tid.inputs[1].default_value = (0.6, 1.2, 1.0)
    L.new(p, tid.inputs[0])
    # sample the noise at the tile centre to avoid edge flicker
    ctr = _n(N, "ShaderNodeVectorMath", (-900, 200))
    ctr.operation = "ADD"
    ctr.inputs[1].default_value = (0.3, 0.6, 0.0)
    L.new(tid.outputs["Vector"], ctr.inputs[0])
    wn = _n(N, "ShaderNodeTexWhiteNoise", (-740, 200))
    wn.noise_dimensions = "3D"
    L.new(ctr.outputs["Vector"], wn.inputs["Vector"])
    # rotate the in-tile coordinates by a random angle, then offset by a random amount
    ang = _math(N, L, "MULTIPLY", wn.outputs["Value"], 6.2832, (-560, 320))
    rot = _n(N, "ShaderNodeVectorRotate", (-560, 120))
    rot.rotation_type = "Z_AXIS"
    L.new(p, rot.inputs["Vector"])
    L.new(ctr.outputs["Vector"], rot.inputs["Center"])
    L.new(ang, rot.inputs["Angle"])
    off = _n(N, "ShaderNodeVectorMath", (-380, 120))
    off.operation = "MULTIPLY_ADD"
    off.inputs[1].default_value = (23.0, 23.0, 23.0)
    L.new(wn.outputs["Color"], off.inputs[0])
    L.new(rot.outputs["Vector"], off.inputs[2])
    q = off.outputs["Vector"]
    # stretch along one direction so veins run as long diagonal streaks
    st = _n(N, "ShaderNodeVectorMath", (-220, 120))
    st.operation = "MULTIPLY"
    st.inputs[1].default_value = (0.55, 1.6, 1.0)
    L.new(q, st.inputs[0])
    qv = st.outputs["Vector"]
    v1 = _vein(N, L, qv, 0.85, 0.010, 6.0, 0.6, (0, 400))          # primary: thin, soft
    v2 = _vein(N, L, qv, 2.6, 0.006, 8.0, 1.2, (0, 150))           # secondary: finer
    v3 = _vein(N, L, q, 7.0, 0.004, 4.0, 0.3, (0, -100))           # hair-line
    cloud = _n(N, "ShaderNodeTexNoise", (0, -350), Scale=3.0, Detail=5.0, Roughness=0.5)
    L.new(q, cloud.inputs["Vector"])
    # colours: base 0.83 (+-0.02 cloud), primary vein to ~0.62, secondary ~0.70, hairline ~0.74
    base = _n(N, "ShaderNodeMapRange", (720, -350))
    base.inputs["To Min"].default_value = 0.805
    base.inputs["To Max"].default_value = 0.855
    L.new(cloud.outputs["Fac"], base.inputs["Value"])
    c = base.outputs["Result"]
    for v, depth, amt in ((v3, 0.10, 0.6), (v2, 0.15, 0.75), (v1, 0.24, 0.85)):
        k = _math(N, L, "MULTIPLY", v, depth * amt, (900, 0))
        c = _math(N, L, "SUBTRACT", c, k, (1060, 0), clamp=True)
    tint = _n(N, "ShaderNodeCombineColor", (1220, -40))
    warm = _math(N, L, "MULTIPLY", c, 1.012, (1060, -150))
    cool = _math(N, L, "MULTIPLY", c, 0.985, (1060, -250))
    L.new(warm, tint.inputs["Red"])
    L.new(c, tint.inputs["Green"])
    L.new(cool, tint.inputs["Blue"])
    # grout: 3 mm mid grey (0.60), recessed
    brick = _n(N, "ShaderNodeTexBrick", (720, 300))
    brick.offset = 0.0
    brick.squash_frequency = 1
    brick.inputs["Color1"].default_value = (1, 1, 1, 1)
    brick.inputs["Color2"].default_value = (1, 1, 1, 1)
    brick.inputs["Mortar"].default_value = (0, 0, 0, 1)
    brick.inputs["Scale"].default_value = 1.0
    brick.inputs["Mortar Size"].default_value = 0.0015         # each side -> ~3 mm joint (2 mm vanished at 2-4 m)
    brick.inputs["Mortar Smooth"].default_value = 0.05
    brick.inputs["Brick Width"].default_value = 0.6
    brick.inputs["Row Height"].default_value = 1.2
    L.new(p, brick.inputs["Vector"])
    mix = _n(N, "ShaderNodeMix", (1380, 100))
    mix.data_type = "RGBA"
    mix.inputs["B"].default_value = (0.60, 0.60, 0.585, 1.0)   # mid grey so joints read at shower distance
    # brick Fac = 1 in the mortar joint -> B (grout colour)
    L.new(brick.outputs["Fac"], mix.inputs["Factor"])
    L.new(tint.outputs["Color"], mix.inputs["A"])
    L.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    rough = _n(N, "ShaderNodeMapRange", (1380, -150))
    rough.inputs["To Min"].default_value = 0.19
    rough.inputs["To Max"].default_value = 0.62
    L.new(brick.outputs["Fac"], rough.inputs["Value"])
    L.new(rough.outputs["Result"], bsdf.inputs["Roughness"])
    bump = _n(N, "ShaderNodeBump", (1380, -320), Strength=0.35, Distance=0.0015)
    bump.invert = True                       # joint recessed
    L.new(brick.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    m.diffuse_color = (0.83, 0.83, 0.82, 1.0)
    m["detail4_pkg"] = KEY
    return m


def _floor(name, drains):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    nt, N, L = _nodes(m)
    out = _n(N, "ShaderNodeOutputMaterial", (1700, 0))
    bsdf = _n(N, "ShaderNodeBsdfPrincipled", (1400, 0))
    bsdf.inputs["Specular IOR Level"].default_value = 0.5
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    geo = _n(N, "ShaderNodeNewGeometry", (-1400, 0))
    sep = _n(N, "ShaderNodeSeparateXYZ", (-1220, 0))
    L.new(geo.outputs["Position"], sep.inputs["Vector"])
    xy = _n(N, "ShaderNodeCombineXYZ", (-1040, 0), Z=0.0)
    L.new(sep.outputs["X"], xy.inputs["X"])
    L.new(sep.outputs["Y"], xy.inputs["Y"])
    p = xy.outputs["Vector"]
    # same tile layout as the original anti-slip tile (300 mm, dark, light grout)
    brick = _n(N, "ShaderNodeTexBrick", (-700, 300))
    brick.inputs["Color1"].default_value = (0.062, 0.064, 0.070, 1)
    brick.inputs["Color2"].default_value = (0.078, 0.080, 0.086, 1)
    brick.inputs["Mortar"].default_value = (0.36, 0.36, 0.35, 1)
    brick.inputs["Scale"].default_value = 1.0
    brick.inputs["Mortar Size"].default_value = 0.004
    brick.inputs["Mortar Smooth"].default_value = 0.2
    brick.inputs["Brick Width"].default_value = 0.3
    brick.inputs["Row Height"].default_value = 0.3
    brick.offset = 0.0                       # stacked grid like the original (default 0.5 = running bond)
    L.new(p, brick.inputs["Vector"])
    grain = _n(N, "ShaderNodeTexNoise", (-700, 0), Scale=900.0, Detail=2.0, Roughness=0.5)
    L.new(p, grain.inputs["Vector"])
    # wet mask: max over drains (radial falloff; booth drains reach the booth fronts), broken up by noise
    wet = None
    y = -400
    for (x0, y0, r0) in drains:
        d = _n(N, "ShaderNodeVectorMath", (-700, y))
        d.operation = "DISTANCE"
        d.inputs[1].default_value = (x0, y0, 0.0)
        L.new(p, d.inputs[0])
        fall = _n(N, "ShaderNodeMapRange", (-520, y))
        fall.interpolation_type = "SMOOTHSTEP"
        fall.inputs["From Min"].default_value = r0
        fall.inputs["From Max"].default_value = r0 * 0.25
        L.new(d.outputs["Value"], fall.inputs["Value"])
        wet = fall.outputs["Result"] if wet is None else _math(N, L, "MAXIMUM", wet, fall.outputs["Result"], (-340, y))
        y -= 160
    blot = _n(N, "ShaderNodeTexNoise", (-520, 200), Scale=2.2, Detail=4.0, Roughness=0.6, Distortion=0.4)
    L.new(p, blot.inputs["Vector"])
    blot_m = _n(N, "ShaderNodeMapRange", (-340, 200))
    blot_m.inputs["From Min"].default_value = 0.38
    blot_m.inputs["From Max"].default_value = 0.62
    L.new(blot.outputs["Fac"], blot_m.inputs["Value"])
    wet = _math(N, L, "MULTIPLY", wet, blot_m.outputs["Result"], (-160, -200))
    wet = _math(N, L, "MULTIPLY", wet, 1.4, (0, -200), clamp=True)
    # colour: original mix, darker where wet; grout gets a faint water stain
    base = _n(N, "ShaderNodeMix", (300, 250))
    base.data_type = "RGBA"
    base.blend_type = "MULTIPLY"             # same as the original anti-slip tile
    base.inputs["Factor"].default_value = 0.35
    L.new(brick.outputs["Color"], base.inputs["A"])
    L.new(grain.outputs["Color"], base.inputs["B"])
    dark = _n(N, "ShaderNodeMix", (520, 250))
    dark.data_type = "RGBA"
    dark.blend_type = "MULTIPLY"
    dark.inputs["B"].default_value = (0.66, 0.66, 0.66, 1)
    L.new(wet, dark.inputs["Factor"])
    L.new(base.outputs["Result"], dark.inputs["A"])
    stain_f = _math(N, L, "MULTIPLY", brick.outputs["Fac"], wet, (520, 450))   # Fac = 1 in the joint
    stain_f = _math(N, L, "MULTIPLY", stain_f, 0.55, (700, 450))
    stain = _n(N, "ShaderNodeMix", (900, 250))
    stain.data_type = "RGBA"
    stain.inputs["B"].default_value = (0.20, 0.21, 0.19, 1)
    L.new(stain_f, stain.inputs["Factor"])
    L.new(dark.outputs["Result"], stain.inputs["A"])
    L.new(stain.outputs["Result"], bsdf.inputs["Base Color"])
    # roughness: dry tile 0.74-0.92 (original), wet 0.14-0.22
    dry = _n(N, "ShaderNodeMapRange", (520, -50))
    dry.inputs["To Min"].default_value = 0.74      # tile (as original)
    dry.inputs["To Max"].default_value = 0.92      # joint
    L.new(brick.outputs["Fac"], dry.inputs["Value"])
    wr = _n(N, "ShaderNodeMapRange", (520, -250))
    wr.inputs["From Min"].default_value = 0.0
    wr.inputs["From Max"].default_value = 1.0
    wr.inputs["To Min"].default_value = 0.16
    wr.inputs["To Max"].default_value = 0.12
    L.new(grain.outputs["Fac"], wr.inputs["Value"])
    rmix = _n(N, "ShaderNodeMix", (900, -100))
    rmix.data_type = "FLOAT"
    L.new(wet, rmix.inputs["Factor"])
    L.new(dry.outputs["Result"], rmix.inputs["A"])
    L.new(wr.outputs["Result"], rmix.inputs["B"])
    L.new(rmix.outputs["Result"], bsdf.inputs["Roughness"])
    # bump: anti-slip grain fades where water fills it, grout recess everywhere
    gs = _math(N, L, "SUBTRACT", 1.0, wet, (700, -450))
    gs = _math(N, L, "MULTIPLY", gs, 0.25, (860, -450))
    b1 = _n(N, "ShaderNodeBump", (1050, -450), Distance=0.0004)
    L.new(gs, b1.inputs["Strength"])
    L.new(grain.outputs["Fac"], b1.inputs["Height"])
    b2 = _n(N, "ShaderNodeBump", (1220, -450), Strength=0.6, Distance=0.002)
    L.new(brick.outputs["Fac"], b2.inputs["Height"])
    L.new(b1.outputs["Normal"], b2.inputs["Normal"])
    L.new(b2.outputs["Normal"], bsdf.inputs["Normal"])
    m.diffuse_color = (0.07, 0.07, 0.075, 1.0)
    m["detail4_pkg"] = KEY
    return m


def _bbox(o):
    from mathutils import Vector
    cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return (Vector([min(c[i] for c in cs) for i in range(3)]), Vector([max(c[i] for c in cs) for i in range(3)]))


def _drains():
    drains = []
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name.startswith(DRAIN_PREFIXES):
            lo, hi = _bbox(o)
            c = (lo + hi) / 2
            r = 0.85 if "linear" in o.name else (0.75 if "Booth" in o.name else 0.95)
            drains.append((round(c.x, 4), round(c.y, 4), r))
    return sorted(set(drains))


def apply() -> dict:
    drains = _drains()
    new = {
        PFX + "Marble_XZ": _marble(PFX + "Marble_XZ", "XZ"),
        PFX + "Marble_YZ": _marble(PFX + "Marble_YZ", "YZ"),
        PFX + "FloorWet": _floor(PFX + "FloorWet", drains),
    }
    touched = []
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        if "detail4_orig_materials" in ob and ob.get("detail4_pkg") == KEY:
            # already handled (this run, an earlier run, or a scene saved after one): work from the stored
            # original names, because the original materials may have been purged when such a scene was saved
            orig = json.loads(ob["detail4_orig_materials"])
        else:
            orig = [s.material.name if s.material else None for s in ob.material_slots]
            if not any(n in SWAP for n in orig):
                continue
            ob["detail4_orig_materials"] = json.dumps(orig)
            ob["detail4_pkg"] = KEY
        for slot, mn in zip(ob.material_slots, orig):
            if mn in SWAP:
                slot.material = new[SWAP[mn]]
            elif mn and bpy.data.materials.get(mn):
                slot.material = bpy.data.materials[mn]
        touched.append(ob.name)
    return {"objects_added": 0, "triangles_added": 0, "objects_touched": touched,
            "materials_added": list(new), "drains": drains}


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
