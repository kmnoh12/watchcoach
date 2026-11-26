"""detail4 P3 suite_ceiling: fill the dark centre coffer of the men's / women's locker-room ceilings.

The coffer (men x 7.72..11.23, women x 11.97..15.48, y -11.93..-7.22, underside z 3.00) is lit only by the warm
cove strip, and the big room area light (z 2.95) shines down only, so in EEVEE it renders as a black hole.
Real Korean gym locker rooms (work/refs/interior/003, 004, 005, 008, 011, 014, 020) have a plain white ceiling with
flat LED panels, round downlights, a 4-way ceiling cassette air conditioner (interior/005), a square exhaust
grille (interior/011), a smoke detector and concealed sprinkler heads, and the ceiling itself is bright from
floor bounce.

Per room this module adds (all new objects, collection DETAIL4_suite_ceiling under SET):
  - 2 x 600x600 flat LED panels (white frame + opal emissive diffuser + a real 4000 K area light each)
  - 4 x 100 mm downlights (trim ring + lens + 4000 K spot, no shadow)
  - 1 x 840x840 4-way cassette AC panel (intake grille, 4 dark outlet slots with louvers)
  - 1 x square exhaust grille, 1 x smoke detector (tiny red LED), 2 x concealed sprinkler cover plates
  - 1 x Light Probe Volume sized to the locker room only (bake it with --bake; data is stored in the probe)
No existing object, material or light is changed. Repeated parts share mesh data.

Run standalone (never saves unless --save is given):
  Blender -b promo/scenes/scene_gym.blend --python promo/tools/detail4_suite_ceiling.py -- [--bake] [--save out.blend]
`--bake` bakes only this module's two volume probes (EEVEE, headless works on this Mac, about 1.5 min each).
Run apply() a second time and the probes are kept (same objects, same settings), so a bake survives a re-run.
"""
import math
import sys

import bmesh
import bpy
from mathutils import Vector

KEY = "suite_ceiling"
COLL = "DETAIL4_suite_ceiling"
PFX = "D4suite_"

CEIL_Z = 3.00          # coffer underside (Men/Women SuiteCeiling slab bottom)
MEN_CX = 9.475         # coffer centre x (men); women room is the mirror image about x = 11.6
MIRROR_X = 11.6
ROOM_CY = -9.575       # coffer centre y

# Layout in men-room coordinates (x, y) — mirrored for women. Coffer spans x 7.72..11.23, y -11.93..-7.22.
PANELS = [(MEN_CX, -8.05), (MEN_CX, -11.10)]
DOWNLIGHTS = [(8.35, -8.75), (10.60, -8.75), (8.35, -10.40), (10.60, -10.40)]
CASSETTE = (MEN_CX, ROOM_CY)
EXHAUST = (10.62, -11.35)
SMOKE = (8.30, ROOM_CY)
SPRINKLERS = [(10.65, ROOM_CY), (8.30, -11.35)]

LED_4000K = (1.0, 0.93, 0.86)
PANEL_W = 40.0         # W per panel area light
# Floor-bounce fill: the measured volume-probe bake barely reaches the coffer (ceiling 48.8 vs 48.7 grey level with
# the probe on/off, work/detail4/suite_ceiling/REPORT.md), so the light that a real white-tile floor bounces back up
# is added as an upward, shadowless, diffuse-only area light under the coffer (narrow spread keeps it in the room).
FILL_W = 60.0
FILL_COLOR = (1.0, 0.93, 0.85)
SPOT_W = 60.0          # W per downlight (brief: 60~90)


# ----------------------------------------------------------------------------------------------- materials
def _principled(name, base, rough, metal=0.0, emit=None, emit_strength=0.0, spec=0.5):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (*base, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Specular IOR Level"].default_value = spec
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = emit_strength
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    m.diffuse_color = (*base, 1)
    return m, nt, b


def _grille_material(name, base, dark, scale, axis="X"):
    """White ABS with fine dark slot lines (intake grille / exhaust louvers) — procedural, object space."""
    m, nt, b = _principled(name, base, 0.45)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = scale
    nt.links.new(sep.outputs[axis], mul.inputs[0])
    fr = nt.nodes.new("ShaderNodeMath"); fr.operation = "FRACT"
    nt.links.new(mul.outputs[0], fr.inputs[0])
    # slot = middle 45 % of every period
    lo = nt.nodes.new("ShaderNodeMath"); lo.operation = "GREATER_THAN"; lo.inputs[1].default_value = 0.30
    hi = nt.nodes.new("ShaderNodeMath"); hi.operation = "LESS_THAN"; hi.inputs[1].default_value = 0.75
    nt.links.new(fr.outputs[0], lo.inputs[0]); nt.links.new(fr.outputs[0], hi.inputs[0])
    both = nt.nodes.new("ShaderNodeMath"); both.operation = "MULTIPLY"
    nt.links.new(lo.outputs[0], both.inputs[0]); nt.links.new(hi.outputs[0], both.inputs[1])
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (*base, 1); mix.inputs["B"].default_value = (*dark, 1)
    nt.links.new(both.outputs[0], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    return m


def _materials():
    M = {}
    # powder-coated white aluminium / ABS, a touch warmer than the 0.76 ceiling paint so parts read as fittings
    M["white"] = _principled(PFX + "WhiteABS", (0.80, 0.80, 0.78), 0.40)[0]
    M["frame"] = _principled(PFX + "PanelFrame", (0.78, 0.78, 0.77), 0.32, metal=0.0)[0]
    M["opal"] = _principled(PFX + "OpalDiffuser", (0.92, 0.92, 0.90), 0.5, emit=LED_4000K, emit_strength=7.0)[0]
    M["lens"] = _principled(PFX + "DownlightLens", (0.95, 0.95, 0.93), 0.3, emit=LED_4000K, emit_strength=14.0)[0]
    M["slot"] = _principled(PFX + "SlotDark", (0.035, 0.036, 0.038), 0.7)[0]
    M["grille"] = _grille_material(PFX + "IntakeGrille", (0.74, 0.74, 0.72), (0.10, 0.10, 0.10), 95.0)
    M["louver"] = _grille_material(PFX + "ExhaustLouver", (0.80, 0.80, 0.78), (0.05, 0.05, 0.05), 55.0, axis="Y")
    M["red_led"] = _principled(PFX + "DetectorLED", (0.6, 0.02, 0.02), 0.4, emit=(1.0, 0.05, 0.03),
                               emit_strength=6.0)[0]
    return M


# ----------------------------------------------------------------------------------------------- meshes
def _mesh(name, build, mats):
    me = bpy.data.meshes.get(name)
    if me:
        bpy.data.meshes.remove(me)
    bm = bmesh.new()
    build(bm)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    for m in mats:                      # slots first: materials.clear() after to_mesh would zero material_index
        me.materials.append(m)
    bm.to_mesh(me)
    bm.free()
    return me, mats


def _box(bm, size, center=(0, 0, 0)):
    r = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=r["verts"])
    bmesh.ops.translate(bm, vec=Vector(center), verts=r["verts"])
    return r["verts"]


def _cyl(bm, r, h, z0, seg=24, mat=0):
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=h)
    bmesh.ops.translate(bm, vec=Vector((0, 0, z0 + h / 2)), verts=res["verts"])
    for f in {f for v in res["verts"] for f in v.link_faces}:
        f.material_index = mat
    return res["verts"]


def _ring(bm, r_out, r_in, z0, z1, seg=32, mat=0):
    """Closed annular tube (trim ring)."""
    vs = {}
    for i in range(seg):
        a = 2 * math.pi * i / seg
        for k, r in (("o", r_out), ("i", r_in)):
            for zk, z in (("b", z0), ("t", z1)):
                vs[k, zk, i] = bm.verts.new((r * math.cos(a), r * math.sin(a), z))
    for i in range(seg):
        j = (i + 1) % seg
        for quad in ((("o", "b", i), ("o", "b", j), ("o", "t", j), ("o", "t", i)),
                     (("i", "t", i), ("i", "t", j), ("i", "b", j), ("i", "b", i)),
                     (("i", "b", i), ("i", "b", j), ("o", "b", j), ("o", "b", i)),
                     (("o", "t", i), ("o", "t", j), ("i", "t", j), ("i", "t", i))):
            f = bm.faces.new([vs[q] for q in quad])
            f.material_index = mat


def _set_mat(bm, verts, idx):
    for f in {f for v in verts for f in v.link_faces}:
        f.material_index = idx


def _bevel_all(bm, w, segs=1):
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=w, segments=segs, affect="EDGES", profile=0.5,
                    clamp_overlap=True)


# Local frame for every fitting: z = 0 is the ceiling plane, the fitting hangs into -z, hidden parts go up to +0.01.
def build_meshes(M):
    meshes = {}

    def panel(bm):
        # 600x600 frame, 14 mm below ceiling, embedded 10 mm; opal diffuser 4 mm recessed inside the 18 mm lip
        fr = _box(bm, (0.595, 0.595, 0.024), (0, 0, -0.002))      # z -0.014 .. +0.010
        _bevel_all(bm, 0.003)
        dv = _box(bm, (0.555, 0.555, 0.004), (0, 0, -0.012))       # bottom -0.014 -> recessed? keep 2 mm proud
        bmesh.ops.translate(bm, vec=Vector((0, 0, -0.0035)), verts=dv)  # bottom at -0.0175 (3.5 mm proud of frame)
        _set_mat(bm, dv, 1)
    meshes["panel"] = _mesh(PFX + "LEDPanel", panel, [M["frame"], M["opal"]])

    def downlight(bm):
        _ring(bm, 0.060, 0.046, -0.008, 0.010, seg=32, mat=0)
        lens = _cyl(bm, 0.0465, 0.012, -0.004, seg=32, mat=1)    # lens 4 mm above ring bottom (reads recessed)
    meshes["downlight"] = _mesh(PFX + "Downlight", downlight, [M["white"], M["lens"]])

    def cassette(bm):
        body = _box(bm, (0.84, 0.84, 0.040), (0, 0, -0.010))     # z -0.030 .. +0.010 (30 mm proud)
        _bevel_all(bm, 0.006, 2)
        # centre intake grille, 1.5 mm proud of the panel face
        g = _box(bm, (0.50, 0.50, 0.004), (0, 0, -0.0305))
        _set_mat(bm, g, 1)
        # 4 outlet slots (dark), 2 mm proud, inset 75 mm from the edge
        for (sx, sy, cx, cy) in ((0.56, 0.065, 0, 0.3125), (0.56, 0.065, 0, -0.3125),
                                 (0.065, 0.56, 0.3125, 0), (0.065, 0.56, -0.3125, 0)):
            s = _box(bm, (sx, sy, 0.004), (cx, cy, -0.0315))
            _set_mat(bm, s, 2)
        # louver flaps hanging ~25 deg open in each slot
        for (lx, ly, cx, cy, ax, sgn) in ((0.54, 0.055, 0, 0.3125, "X", 1), (0.54, 0.055, 0, -0.3125, "X", -1),
                                          (0.055, 0.54, 0.3125, 0, "Y", -1), (0.055, 0.54, -0.3125, 0, "Y", 1)):
            v = _box(bm, (lx, ly, 0.003), (0, 0, 0))
            ang = math.radians(25) * sgn
            from mathutils import Matrix
            rot = Matrix.Rotation(ang, 3, ax)
            bmesh.ops.rotate(bm, verts=v, cent=Vector((0, 0, 0)), matrix=rot)
            bmesh.ops.translate(bm, vec=Vector((cx, cy, -0.044)), verts=v)
            _set_mat(bm, v, 0)
    meshes["cassette"] = _mesh(PFX + "CassetteAC", cassette, [M["white"], M["grille"], M["slot"]])

    def exhaust(bm):
        f = _box(bm, (0.27, 0.27, 0.022), (0, 0, -0.001))       # frame z -0.012 .. +0.010
        _bevel_all(bm, 0.003)
        l = _box(bm, (0.22, 0.22, 0.004), (0, 0, -0.0135))       # louver face 1.5 mm proud
        _set_mat(bm, l, 1)
    meshes["exhaust"] = _mesh(PFX + "ExhaustGrille", exhaust, [M["white"], M["louver"]])

    def smoke(bm):
        _cyl(bm, 0.055, 0.018, -0.008, seg=32, mat=0)            # base plate
        _cyl(bm, 0.045, 0.024, -0.032, seg=32, mat=0)            # body, bottom 32 mm below ceiling
        led = _cyl(bm, 0.003, 0.003, -0.0335, seg=8, mat=1)
        bmesh.ops.translate(bm, vec=Vector((0.028, 0, 0)), verts=led)
    meshes["smoke"] = _mesh(PFX + "SmokeDetector", smoke, [M["white"], M["red_led"]])

    def sprinkler(bm):
        _cyl(bm, 0.040, 0.016, -0.006, seg=32, mat=0)            # concealed cover plate, 6 mm proud
    meshes["sprinkler"] = _mesh(PFX + "SprinklerCover", sprinkler, [M["white"]])

    for me, mats in meshes.values():
        for p in me.polygons:
            p.use_smooth = False
    # round parts: smooth the cylinder walls
    for key in ("downlight", "smoke", "sprinkler"):
        me = meshes[key][0]
        for p in me.polygons:
            p.use_smooth = abs(p.normal.z) < 0.5
    return {k: v[0] for k, v in meshes.items()}


# ----------------------------------------------------------------------------------------------- scene
def _clear(coll):
    for ob in list(coll.objects):
        if ob.type == "LIGHT_PROBE":
            continue                       # keep probes so an existing bake survives a re-run
        data = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Light):
                bpy.data.lights.remove(data)


def _obj(name, data, coll, loc):
    ob = bpy.data.objects.new(name, data)
    coll.objects.link(ob)
    ob.location = loc
    ob["detail4_pkg"] = KEY
    return ob


def _light(name, kind, coll, loc, energy, **kw):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = LED_4000K
    ld.use_shadow = False
    for k, v in kw.items():
        setattr(ld, k, v)
    return _obj(name, ld, coll, loc)


def _probe(name, coll, loc, half):
    ob = bpy.data.objects.get(name)
    if ob is None:
        lp = bpy.data.lightprobes.new(name, "VOLUME")
        ob = bpy.data.objects.new(name, lp)
        coll.objects.link(ob)
    lp = ob.data
    ob.location = loc
    ob.scale = half
    ob.rotation_euler = (0, 0, 0)
    lp.resolution_x, lp.resolution_y, lp.resolution_z = 8, 10, 5
    lp.bake_samples = 1024
    lp.capture_world = True
    lp.capture_indirect = True
    lp.capture_emission = True
    lp.intensity = 1.0
    ob["detail4_pkg"] = KEY
    return ob


def apply() -> dict:
    set_coll = bpy.data.collections["SET"]
    coll = bpy.data.collections.get(COLL)
    if coll is None:
        coll = bpy.data.collections.new(COLL)
        set_coll.children.link(coll)
    _clear(coll)
    M = _materials()
    meshes = build_meshes(M)
    z = CEIL_Z
    added, tris = [], 0

    def tri_count(me):
        return sum(len(p.vertices) - 2 for p in me.polygons)

    for side in ("Men", "Women"):
        mx = (lambda x: x) if side == "Men" else (lambda x: 2 * MIRROR_X - x)
        p = f"{PFX}{side}_"
        for i, (x, y) in enumerate(PANELS):
            ob = _obj(f"{p}LEDPanel_{i}", meshes["panel"], coll, (mx(x), y, z)); added.append(ob)
            _light(f"{p}LEDPanel_{i}_Light", "AREA", coll, (mx(x), y, z - 0.019), PANEL_W,
                   shape="SQUARE", size=0.55, spread=math.radians(160))
        for i, (x, y) in enumerate(DOWNLIGHTS):
            ob = _obj(f"{p}Downlight_{i}", meshes["downlight"], coll, (mx(x), y, z)); added.append(ob)
            _light(f"{p}Downlight_{i}_Spot", "SPOT", coll, (mx(x), y, z - 0.012), SPOT_W,
                   spot_size=math.radians(75), spot_blend=0.45, shadow_soft_size=0.04)
        x, y = CASSETTE
        added.append(_obj(f"{p}CassetteAC", meshes["cassette"], coll, (mx(x), y, z)))
        x, y = EXHAUST
        added.append(_obj(f"{p}ExhaustGrille", meshes["exhaust"], coll, (mx(x), y, z)))
        x, y = SMOKE
        added.append(_obj(f"{p}SmokeDetector", meshes["smoke"], coll, (mx(x), y, z)))
        for i, (x, y) in enumerate(SPRINKLERS):
            added.append(_obj(f"{p}Sprinkler_{i}", meshes["sprinkler"], coll, (mx(x), y, z)))
        # floor-bounce fill: upward rectangle at z 1.6 under the coffer, diffuse only (no mirror / floor highlights).
        # 2.6 x 3.6 m with a 60 deg spread: its light lands only inside this room's walls (x 7.37..11.58,
        # y -6.97..-12.19 at ceiling height), so nothing leaks onto the shower / restroom / other suite ceilings.
        fl = _light(f"{p}CeilingBounceFill", "AREA", coll, (mx(MEN_CX), ROOM_CY, 1.6), FILL_W,
                    shape="RECTANGLE", size=2.6, size_y=3.6, spread=math.radians(60))
        fl.data.use_custom_distance = True
        fl.data.cutoff_distance = 2.4
        fl.rotation_euler = (math.pi, 0, 0)
        fl.data.color = FILL_COLOR
        fl.data.specular_factor = 0.0
        fl.data.volume_factor = 0.0
        # Light Probe Volume: locker room interior only (men x 7.40..11.55, y -12.25..-6.92, z 0..3.0),
        # kept off the walls and away from shower / restroom / gym.
        cx = mx(9.475)
        _probe(f"{p}LockerVolumeProbe", coll, (cx, -9.585, 1.49), (2.03, 2.62, 1.47))
    for ob in added:
        tris += tri_count(ob.data)
    lights = [o.name for o in coll.objects if o.type == "LIGHT"]
    probes = [o.name for o in coll.objects if o.type == "LIGHT_PROBE"]
    return {"objects_added": len(added), "triangles_added": tris, "lights_added": len(lights),
            "probes": probes, "existing_touched": []}


def bake():
    """Bake only this module's volume probes (EEVEE light cache). Blocking; ~1.5 min per probe on this Mac."""
    coll = bpy.data.collections[COLL]
    probes = [o for o in coll.objects if o.type == "LIGHT_PROBE" and o.data.type == "VOLUME"]
    vl = bpy.context.view_layer
    for ob in vl.objects:
        ob.select_set(False)
    for ob in probes:
        ob.select_set(True)
    vl.objects.active = probes[0]
    return bpy.ops.object.lightprobe_cache_bake(subset="SELECTED")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    print("D4SUITE APPLY", apply(), flush=True)
    if "--bake" in argv:
        import time
        t0 = time.time()
        print("D4SUITE BAKE", bake(), f"{time.time() - t0:.1f}s", flush=True)
    if "--save" in argv:
        out = argv[argv.index("--save") + 1]
        if "promo/scenes" in out or "promo/models" in out:
            raise SystemExit("refusing to save into promo/scenes or promo/models")
        bpy.ops.wm.save_as_mainfile(filepath=out, copy=True)
        print("D4SUITE SAVED", out, flush=True)
