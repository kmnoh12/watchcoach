"""detail4 P2 freeweight_light: suspended ceiling track rail, 5 directional cylinder track spots,
and a 2.4 m linear indirect wall light above the dumbbell-rack mirror to illuminate the dark
freeweight corner (x -7.47..-1.55, y 2.19..4.97).

Rules honoured:
  - Creates ONLY new objects/lights in collection `DETAIL4_freeweight_light` under `SET`.
  - Touches ZERO existing lights, ZERO mirrors/probes, ZERO shadow_pool_size.
  - Enables shadows on ONLY 2 of the 5 track spots (keeps Shadow buffer full = 0).
  - Idempotent: running apply() twice yields identical object/light/triangle counts.

Run standalone (never saves unless --save is given):
  Blender -b promo/scenes/scene_gym.blend --python promo/tools/detail4_freeweight_light.py [-- --save out.blend]
"""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

KEY = "freeweight_light"
COLL = "DETAIL4_freeweight_light"
PFX = "D4fwl_"

SLAB_Z = 3.59        # Ceiling underside
GAP = 0.002          # 2 mm clearance against slab / wall

# Track rail geometry: spans x=-6.90..-2.00 along y=3.44 at z=3.35 (matches SURVEY z~3.35).
# Cleanly clears Spiral HVAC duct (y<=3.357), CeilBeam.004 (y>=3.53), Pipe_Left (z<=3.235),
# and Dgym_ceiling_CableTray (x<=-6.95) with >= 40 mm margin on every side.
RAIL_X0, RAIL_X1 = -6.90, -2.00
RAIL_Y = 3.44
RAIL_Z = 3.35        # rail center Z (35x35 mm cross-section -> z 3.3325..3.3675)
RAIL_W, RAIL_H = 0.035, 0.035
HANGER_XS = (-6.55, -2.45)  # clear of CableTray, HVAC duct, CeilBeam.004, Conduits, Pipe_Left

# 5 track spots: (x, target_xyz, spot_deg, energy_w, use_shadow)
# Only 2 spots enable shadows (per SURVEY P2 spec).
# Color ~3800 K warm-neutral white (matches gym/138, 139, 239, 244).
SPOT_COLOR = (1.0, 0.90, 0.77)
SPOTS = (
    (-6.70, (-7.10, 3.65, 0.80), 45.0, 250.0, False),  # barbell rack & left end of dumbbell rack
    (-6.05, (-6.35, 4.35, 0.55), 45.0, 250.0, True),   # dumbbell rack left (2-12 kg / 22.5-30 kg)
    (-5.15, (-5.30, 4.30, 0.58), 45.0, 250.0, True),   # dumbbell rack center & plate tree
    (-4.20, (-4.35, 4.35, 0.58), 45.0, 250.0, False),  # dumbbell rack right (16-20 kg / 35-40 kg)
    (-2.95, (-3.20, 4.25, 0.70), 44.0, 240.0, False),  # EZ barbell rack & floor dumbbells
)

# 2.4 m linear indirect wall light above the freeweight mirror:
# Mirror top cap z_max = 2.489, Korean lettering z_min = 2.618, Wall_Back front y = 5.000.
# Fixture sits cleanly at z = 2.518..2.556 (29 mm above mirror cap, 62 mm below lettering),
# attached to Wall_Back with 2 mm gap (y = 4.940..4.998).
WALL_BAR_X = -5.45
WALL_BAR_LEN = 2.40
WALL_BAR_Z = 2.537
WALL_BAR_H = 0.038
WALL_BAR_D = 0.058
WALL_Y = 5.000
WALL_BAR_COLOR = (1.0, 0.89, 0.75)  # ~3500 K warm indirect wash


def _mat(name, base_rgb, rough=0.35, metal=0.0, emit=0.0, emit_rgb=None):
    full = PFX + name
    m = bpy.data.materials.get(full)
    if m is None:
        m = bpy.data.materials.new(full)
    m.use_nodes = True
    m.diffuse_color = (*base_rgb, 1.0)
    m["detail4_pkg"] = KEY
    nt = m.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Base Color"].default_value = (*base_rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Emission Strength"].default_value = emit
    if emit > 0.0:
        bsdf.inputs["Emission Color"].default_value = (*(emit_rgb or base_rgb), 1.0)
    return m


class _Builder:
    def __init__(self):
        self.bm = bmesh.new()

    def box(self, center, size, rot=None):
        g = bmesh.ops.create_cube(self.bm, size=1.0)
        vs = g["verts"]
        bmesh.ops.scale(self.bm, vec=Vector(size), verts=vs)
        if rot is not None:
            bmesh.ops.transform(self.bm, matrix=rot, verts=vs)
        bmesh.ops.translate(self.bm, vec=Vector(center), verts=vs)
        for f in {f for v in vs for f in v.link_faces}:
            f.smooth = False
        return vs

    def cyl(self, p0, p1, r, seg=18, r2=None, smooth=True, caps=True):
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        if d.length < 1e-6:
            return []
        g = bmesh.ops.create_cone(
            self.bm, cap_ends=caps, segments=seg,
            radius1=r, radius2=r if r2 is None else r2, depth=d.length,
        )
        vs = g["verts"]
        q = d.normalized().to_track_quat("Z", "Y")
        m = Matrix.Translation((p0 + p1) * 0.5) @ q.to_matrix().to_4x4()
        bmesh.ops.transform(self.bm, matrix=m, verts=vs)
        axis = d.normalized()
        for f in {f for v in vs for f in v.link_faces}:
            f.smooth = smooth and abs(f.normal.dot(axis)) < 0.5
        return vs

    def finish(self, name, mat, coll, bevel=0.0):
        me = bpy.data.meshes.new(PFX + name)
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-6)
        self.bm.normal_update()
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        self.bm.to_mesh(me)
        self.bm.free()
        me.materials.append(mat)
        ob = bpy.data.objects.new(PFX + name, me)
        coll.objects.link(ob)
        if bevel > 0.0:
            bv = ob.modifiers.new("Bevel", "BEVEL")
            bv.width = bevel
            bv.segments = 1
            bv.limit_method = "ANGLE"
            bv.angle_limit = math.radians(40)
            bv.harden_normals = False
        return ob


def _add_light(coll, name, kind, loc, rot, energy, color, **kw):
    lt = bpy.data.lights.new(PFX + name, kind)
    lt.energy = energy
    lt.color = color
    for k, v in kw.items():
        setattr(lt, k, v)
    ob = bpy.data.objects.new(PFX + name, lt)
    ob.location = loc
    ob.rotation_euler = rot
    coll.objects.link(ob)
    return ob


def _clear_coll(coll):
    for ob in list(coll.objects):
        data = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Light):
                bpy.data.lights.remove(data)


def apply() -> dict:
    parent = bpy.data.collections["SET"]
    coll = bpy.data.collections.get(COLL)
    if coll is None:
        coll = bpy.data.collections.new(COLL)
        parent.children.link(coll)
    elif coll.name not in parent.children:
        parent.children.link(coll)
    _clear_coll(coll)

    m_alu = _mat("BlackAlu", (0.018, 0.019, 0.021), rough=0.34, metal=0.82)
    m_rod = _mat("HangerRod", (0.12, 0.12, 0.13), rough=0.38, metal=0.88)
    m_slot = _mat("TrackSlotDark", (0.005, 0.005, 0.006), rough=0.90, metal=0.0)
    m_lens = _mat("SpotLensWarm", (0.98, 0.90, 0.78), rough=0.18, emit=14.0, emit_rgb=SPOT_COLOR)
    m_diff = _mat("WallBarDiffuser", (0.96, 0.90, 0.80), rough=0.35, emit=7.5, emit_rgb=WALL_BAR_COLOR)

    # 1. Suspended 35x35 mm black track rail + end caps + bottom channel recess + 2 hanger rods
    rail_len = RAIL_X1 - RAIL_X0
    rail_cx = 0.5 * (RAIL_X0 + RAIL_X1)
    rail_bm = _Builder()
    slot_bm = _Builder()
    rods_bm = _Builder()

    # Main 35x35 mm rail extrusion (hollow-look via dark bottom slot strip)
    rail_bm.box((rail_cx, RAIL_Y, RAIL_Z), (rail_len, RAIL_W, RAIL_H))
    # End caps (slightly proud)
    for xe in (RAIL_X0 - 0.004, RAIL_X1 + 0.004):
        rail_bm.box((xe, RAIL_Y, RAIL_Z), (0.008, RAIL_W + 0.003, RAIL_H + 0.003))
    # Dark underside conductor slot
    slot_bm.box((rail_cx, RAIL_Y, RAIL_Z - RAIL_H * 0.5 - 0.0005), (rail_len - 0.02, 0.014, 0.0015))
    # Live-end power feed canopy & cord near x=-6.55
    rail_bm.box((-6.45, RAIL_Y, RAIL_Z + RAIL_H * 0.5 + 0.009), (0.075, 0.032, 0.018))
    rail_bm.cyl((-6.45, RAIL_Y, RAIL_Z + RAIL_H * 0.5 + 0.018),
                (-6.45, RAIL_Y, SLAB_Z - GAP), 0.0045, seg=8)

    # 2 hanger rods (M8) + slab canopy + rail saddle clamp
    for hx in HANGER_XS:
        rods_bm.cyl((hx, RAIL_Y, RAIL_Z + RAIL_H * 0.5 + 0.004), (hx, RAIL_Y, SLAB_Z - 0.014), 0.0055, seg=10)
        rail_bm.cyl((hx, RAIL_Y, SLAB_Z - 0.014), (hx, RAIL_Y, SLAB_Z - GAP), 0.024, seg=16)  # ceiling canopy
        rail_bm.box((hx, RAIL_Y, RAIL_Z + RAIL_H * 0.5 + 0.004), (0.034, RAIL_W + 0.006, 0.012))  # saddle clamp

    # 2. 5 directional cylindrical track spots (dia 75 mm x len 120 mm) + SPOT lights
    heads_bm = _Builder()
    lenses_bm = _Builder()
    lights = []
    rail_bot = RAIL_Z - RAIL_H * 0.5

    for idx, (sx, target, spot_deg, energy, use_sh) in enumerate(SPOTS):
        # Track adapter box & drop stem
        heads_bm.box((sx, RAIL_Y, rail_bot - 0.020), (0.056, 0.032, 0.036))
        heads_bm.cyl((sx, RAIL_Y, rail_bot - 0.038), (sx, RAIL_Y, rail_bot - 0.078), 0.0065, seg=10)
        # Pivot yoke joint
        pivot = Vector((sx, RAIL_Y, rail_bot - 0.088))
        heads_bm.cyl((sx - 0.020, RAIL_Y, pivot.z), (sx + 0.020, RAIL_Y, pivot.z), 0.008, seg=10)

        d = (Vector(target) - pivot).normalized()
        # 120 mm long, 75 mm diameter cylinder (radius 0.0375)
        back = pivot - d * 0.048
        front = pivot + d * 0.072
        heads_bm.cyl(back, front, 0.0375, seg=24)
        # Rear heat-sink cap & front anti-glare bezel ring
        heads_bm.cyl(back - d * 0.006, back, 0.035, seg=24)
        heads_bm.cyl(front - d * 0.012, front + d * 0.002, 0.040, seg=24)
        # Recessed warm glowing lens (2 mm behind bezel lip)
        lenses_bm.cyl(front - d * 0.016, front - d * 0.010, 0.032, seg=24)

        rot = d.to_track_quat("-Z", "Y").to_euler()
        l_ob = _add_light(
            coll, f"Spot_{idx}", "SPOT",
            tuple(front + d * 0.012), rot, energy, SPOT_COLOR,
            spot_size=math.radians(spot_deg),
            spot_blend=0.55,
            shadow_soft_size=0.045,
            use_shadow=use_sh,
        )
        lights.append(l_ob)

    # 3. 2.4 m linear indirect wall light above the freeweight mirror
    bar_bm = _Builder()
    diff_bm = _Builder()
    bar_cy = WALL_Y - GAP - WALL_BAR_D * 0.5
    bar_bm.box((WALL_BAR_X, bar_cy, WALL_BAR_Z), (WALL_BAR_LEN, WALL_BAR_D, WALL_BAR_H))
    # Small wall mounting brackets (3x)
    for bx in (WALL_BAR_X - 0.95, WALL_BAR_X, WALL_BAR_X + 0.95):
        bar_bm.box((bx, WALL_Y - GAP - 0.006, WALL_BAR_Z), (0.040, 0.012, WALL_BAR_H + 0.008))
    # End caps
    for sgn in (-1, 1):
        bar_bm.box((WALL_BAR_X + sgn * (WALL_BAR_LEN * 0.5 + 0.003), bar_cy, WALL_BAR_Z),
                   (0.006, WALL_BAR_D + 0.002, WALL_BAR_H + 0.002))
    # Underside opal diffuser strip (recessed 1.5 mm below housing bottom)
    diff_bm.box((WALL_BAR_X, bar_cy - 0.003, WALL_BAR_Z - WALL_BAR_H * 0.5 - 0.0015),
                (WALL_BAR_LEN - 0.024, WALL_BAR_D - 0.018, 0.003))

    # Downward-angled linear AREA light washing the dumbbell rack front & aisle (no shadow cost, no mirror glare bar)
    wall_light_pos = Vector((WALL_BAR_X, bar_cy - 0.015, WALL_BAR_Z - WALL_BAR_H * 0.5 - 0.012))
    wall_light_target = Vector((WALL_BAR_X, 3.85, 0.55))
    wl_rot = (wall_light_target - wall_light_pos).normalized().to_track_quat("-Z", "Y").to_euler()
    wl_ob = _add_light(
        coll, "WallBar_Area", "AREA",
        tuple(wall_light_pos), wl_rot, 520.0, WALL_BAR_COLOR,
        shape="RECTANGLE",
        size=WALL_BAR_LEN - 0.02,
        size_y=0.14,
        specular_factor=0.45,
        use_shadow=False,
    )
    wl_ob.visible_glossy = False
    lights.append(wl_ob)

    meshes = [
        rail_bm.finish("TrackRail", m_alu, coll, bevel=0.0015),
        slot_bm.finish("TrackSlot", m_slot, coll),
        rods_bm.finish("HangerRods", m_rod, coll),
        heads_bm.finish("SpotHeads", m_alu, coll),
        lenses_bm.finish("SpotLenses", m_lens, coll),
        bar_bm.finish("WallBarHousing", m_alu, coll, bevel=0.0015),
        diff_bm.finish("WallBarDiffuser", m_diff, coll),
    ]

    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    tris = 0
    bboxes = {}
    for ob in meshes:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        tris += len(me.loop_triangles)
        pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        bboxes[ob.name] = (
            [round(min(p[i] for p in pts), 4) for i in range(3)]
            + [round(max(p[i] for p in pts), 4) for i in range(3)]
        )
        ev.to_mesh_clear()

    return {
        "collection": COLL,
        "objects_added": [o.name for o in meshes] + [l.name for l in lights],
        "mesh_count": len(meshes),
        "light_count": len(lights),
        "shadow_lights": sum(1 for l in lights if l.data.use_shadow),
        "triangles_added": tris,
        "existing_touched": [],
        "bbox_world": bboxes,
    }


def _main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    res = apply()
    print(f"[detail4_{KEY}] {json.dumps(res)}")
    if "--save" in argv:
        out = argv[argv.index("--save") + 1]
        norm = os.path.normpath(out).replace("\\", "/")
        if "promo/scenes" in norm or "promo/models" in norm:
            raise SystemExit("refusing to save into promo/scenes or promo/models")
        bpy.ops.wm.save_as_mainfile(filepath=out, copy=True, compress=True)
        print(f"[detail4_{KEY}] saved copy -> {out}")


if __name__ == "__main__":
    _main()
