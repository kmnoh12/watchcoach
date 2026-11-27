"""detail6 fix (v4): Chest Press (`P_chest_press_machine`) true forward-push overhead pivot + mid-chest handles.

Fixes both ergonomic & mechanical bugs on `P_chest_press_machine`:
  1. Raises pivot posts (`pivot_arm`, `pivot_arm.001`) to an overhead forward bracket at `(±0.320, -0.140, 1.380)`
     and replaces the broken Z-axis (sideways pec-deck) drivers on `P_Moving assembly.012/.013` with true
     horizontal X-axis forward-push drivers (`0.0 + -0.62*v`).
  2. Rebuilds the dropping red lever arms (`lever_knuckle*`, `press_forearm*`) from the overhead pivot down to
     mid-chest height (`z = 0.820, y = -0.200`), topped with the curved red inward stub + sleek black inverted-L
     dual grips (`z = 0.785..0.900`, directly below seated shoulder `0.915`).
  3. At `Stroke = 0 -> 1`, handles push cleanly +31 cm straight forward (`y = -0.20 -> -0.51`, `z = 0.83 -> 0.96`),
     allowing a seated mannequin to perform a realistic chest press with zero collisions.
  4. Re-anchors `Coated load cable.005` cleanly to the overhead pivot bracket.

Touches ONLY `P_chest_press_machine` descendants. 100% idempotent.
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT_NAME = "P_chest_press_machine"
TAG = "detail6_fix_chest_press"
TAG_VER = "v5"

PIVOT_X = 0.320
PIVOT_Y = -0.140
PIVOT_Z = 1.380


def _ensure_unique(root, ob):
    if ob.type != "MESH" or ob.data is None:
        return
    root_set = {root} | set(root.children_recursive)
    if any(o.data == ob.data and o not in root_set for o in bpy.data.objects):
        ob.data = ob.data.copy()


def _replace_mesh(root, ob, bm, mats=None):
    _ensure_unique(root, ob)
    me = ob.data
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.update()
    if mats is not None:
        me.materials.clear()
        for m in mats:
            if m is not None:
                me.materials.append(m)


def _add_beam(bm, p0, p1, wx, wz, bevel=0.004, mat_idx=0):
    p0 = Vector(p0)
    p1 = Vector(p1)
    d = p1 - p0
    length = d.length
    if length < 1e-6:
        return
    y_axis = d.normalized()
    x_axis = Vector((1.0, 0.0, 0.0))
    if abs(y_axis.dot(x_axis)) > 0.99:
        x_axis = Vector((0.0, 1.0, 0.0))
    z_axis = x_axis.cross(y_axis).normalized()
    x_axis = y_axis.cross(z_axis).normalized()
    mid = 0.5 * (p0 + p1)
    rot = Matrix((x_axis, y_axis, z_axis)).transposed().to_4x4()
    mat = Matrix.Translation(mid) @ rot @ Matrix.Diagonal((wx, length, wz, 1.0))
    ret = bmesh.ops.create_cube(bm, size=1.0, matrix=mat)
    verts = ret["verts"]
    edges = list({e for v in verts for e in v.link_edges})
    for f in {f for v in verts for f in v.link_faces}:
        f.material_index = mat_idx
    if bevel > 0.0:
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=2, affect="EDGES", clamp_overlap=True)


def _sweep_round_tube(bm, pts, radius, segs=20, mat_idx=0):
    pts = [Vector(p) for p in pts]
    rings = []
    for i, p in enumerate(pts):
        if i == 0:
            t = (pts[1] - pts[0]).normalized()
        elif i == len(pts) - 1:
            t = (pts[-1] - pts[-2]).normalized()
        else:
            t = ((pts[i] - pts[i - 1]).normalized() + (pts[i + 1] - pts[i]).normalized()).normalized()
        ref = Vector((0.0, 1.0, 0.0)) if abs(t.y) < 0.9 else Vector((0.0, 0.0, 1.0))
        u = t.cross(ref).normalized()
        v = u.cross(t).normalized()
        ring = []
        for k in range(segs):
            a = 2.0 * math.pi * k / segs
            ring.append(bm.verts.new(p + (u * math.cos(a) + v * math.sin(a)) * radius))
        rings.append(ring)
    for r0, r1 in zip(rings[:-1], rings[1:]):
        for k in range(segs):
            f = bm.faces.new((r0[k], r0[(k + 1) % segs], r1[(k + 1) % segs], r1[k]))
            f.material_index = mat_idx
    bm.faces.new(list(reversed(rings[0]))).material_index = mat_idx
    bm.faces.new(rings[-1]).material_index = mat_idx


def _clear_mesh(root, ob):
    ob.location = Vector((0.0, 0.0, 0.0))
    ob.rotation_mode = "XYZ"
    ob.rotation_euler = (0.0, 0.0, 0.0)
    ob.scale = Vector((1.0, 1.0, 1.0))
    _replace_mesh(root, ob, bmesh.new())


def _set_stroke_rot_x_driver(root, ob, expr):
    """Replace any rotation_euler drivers on ob with a single X-axis Stroke driver."""
    if ob.animation_data:
        for fc in list(ob.animation_data.drivers):
            if fc.data_path == "rotation_euler":
                ob.animation_data.drivers.remove(fc)
    ob.rotation_mode = "XYZ"
    ob.rotation_euler = (0.0, 0.0, 0.0)
    fc = ob.driver_add("rotation_euler", 0)
    drv = fc.driver
    drv.type = "SCRIPTED"
    drv.expression = expr
    var = drv.variables.new()
    var.name = "v"
    var.type = "SINGLE_PROP"
    tgt = var.targets[0]
    tgt.id_type = "OBJECT"
    tgt.id = root
    tgt.data_path = '["Stroke"]'


def apply() -> dict:
    root = bpy.data.objects.get(ROOT_NAME)
    if root is None:
        raise RuntimeError(f"Missing {ROOT_NAME} in scene")

    if root.get(TAG) == TAG_VER:
        return {"machine": ROOT_NAME, "status": "skipped", "reason": f"already {TAG_VER}"}

    saved_stroke = float(root.get("Stroke", 0.0))
    root["Stroke"] = 0.0
    bpy.context.view_layer.update()

    m_grip = bpy.data.materials.get("E_grip")
    m_steel = bpy.data.materials.get("E_steel")
    m_silver = bpy.data.materials.get("E_silver")
    m_red = bpy.data.materials.get("E_frame") or m_steel
    pf0 = bpy.data.objects.get("press_forearm")
    if pf0 and pf0.data and len(pf0.data.materials) > 0 and pf0.data.materials[0]:
        m_red = pf0.data.materials[0]
    pa0 = bpy.data.objects.get("pivot_arm")
    if pa0 and pa0.data and len(pa0.data.materials) > 0 and pa0.data.materials[0]:
        m_silver = pa0.data.materials[0]

    try:
        # 1. Extend pivot_arm / pivot_arm.001 up to z=1.380 and forward to overhead pivot y=-0.140
        for sx, pa_nm in ((-1.0, "pivot_arm"), (+1.0, "pivot_arm.001")):
            pa = bpy.data.objects[pa_nm]
            pa.location = Vector((0.0, 0.0, 0.0))
            pa.rotation_mode = "XYZ"
            pa.rotation_euler = (0.0, 0.0, 0.0)
            pa.scale = Vector((1.0, 1.0, 1.0))
            bm_pa = bmesh.new()
            # Vertical column rising from chassis z=0.540 -> 1.400 at (sx*0.320, 0.200)
            _add_beam(bm_pa, (sx * PIVOT_X, 0.200, 0.540), (sx * PIVOT_X, 0.200, 1.410), 0.072, 0.072, bevel=0.004, mat_idx=0)
            # Overhead forward arm to pivot (sx*0.320, -0.140, 1.380)
            _add_beam(bm_pa, (sx * PIVOT_X, 0.220, PIVOT_Z), (sx * PIVOT_X, PIVOT_Y - 0.030, PIVOT_Z), 0.068, 0.068, bevel=0.004, mat_idx=0)
            # Diagonal gusset brace under overhead arm
            _add_beam(bm_pa, (sx * PIVOT_X, 0.180, 1.160), (sx * PIVOT_X, -0.020, 1.360), 0.044, 0.044, bevel=0.003, mat_idx=0)
            # Matching overhead cross-tie (built on left side only so no overlap)
            if sx < 0:
                _add_beam(bm_pa, (-PIVOT_X, 0.200, PIVOT_Z), (PIVOT_X, 0.200, PIVOT_Z), 0.058, 0.058, bevel=0.004, mat_idx=0)
            _replace_mesh(root, pa, bm_pa, [m_silver])

        # Move existing left & right hub visuals to overhead pivots
        for h_nm in ("press_hub_body", "press_hub_cap", "press_hub_bolt"):
            hb = bpy.data.objects.get(h_nm)
            if hb is not None:
                hb.location = Vector((-PIVOT_X, PIVOT_Y, PIVOT_Z))
            hb2 = bpy.data.objects.get(h_nm + ".001")
            if hb2 is not None:
                hb2.location = Vector((+PIVOT_X, PIVOT_Y, PIVOT_Z))

        # 2. Move P_Moving assembly.012/.013 to overhead pivot & drive X-axis forward push (0 -> -35.5 deg)
        specs = [
            (-1.0, "P_Moving assembly.012", "lever_knuckle", "press_forearm",
             "handle.040", "handle_cap1", "handle_cap2", "handle_v", "handle_v_cap1", "handle_v_cap2"),
            (+1.0, "P_Moving assembly.013", "lever_knuckle.001", "press_forearm.001",
             "handle.041", "handle_cap1.001", "handle_cap2.001", "handle_v.001", "handle_v_cap1.001", "handle_v_cap2.001"),
        ]
        touched = []

        for sx, ma_nm, lk_nm, pf_nm, h_nm, c1_nm, c2_nm, hv_nm, vc1_nm, vc2_nm in specs:
            ma = bpy.data.objects[ma_nm]
            ma.location = Vector((sx * PIVOT_X, PIVOT_Y, PIVOT_Z))
            _set_stroke_rot_x_driver(root, ma, "0.0+-0.62*v")

            # Red upper lever arm (`lever_knuckle`) dropping down-outward from overhead pivot
            # Local (0, 0, 0) -> (sx*0.080, -0.020, -0.340) [root: (±0.400, -0.160, 1.040)]
            lk = bpy.data.objects[lk_nm]
            lk.location = Vector((0.0, 0.0, 0.0))
            lk.rotation_mode = "XYZ"
            lk.rotation_euler = (0.0, 0.0, 0.0)
            lk.scale = Vector((1.0, 1.0, 1.0))
            bm_lk = bmesh.new()
            _add_beam(bm_lk, (0.0, 0.0, 0.0), (sx * 0.080, -0.020, -0.340), 0.056, 0.058, bevel=0.005, mat_idx=0)
            _replace_mesh(root, lk, bm_lk, [m_red])

            # Red lower forearm (`press_forearm`) continuing down-forward to mid-chest height z_local = -0.560
            # [root: (±0.400, -0.200, 0.820)]
            pf = bpy.data.objects[pf_nm]
            pf.location = Vector((0.0, 0.0, 0.0))
            pf.rotation_mode = "XYZ"
            pf.rotation_euler = (0.0, 0.0, 0.0)
            pf.scale = Vector((1.0, 1.0, 1.0))
            bm_pf = bmesh.new()
            _add_beam(bm_pf, (sx * 0.080, -0.020, -0.320), (sx * 0.080, -0.060, -0.560), 0.054, 0.054, bevel=0.005, mat_idx=0)
            _replace_mesh(root, pf, bm_pf, [m_red])

            # Curved red inward stub + silver collars (`handle_v`) at mid-chest height
            y0 = -0.060
            x_arm = sx * 0.080
            x_in = sx * 0.015       # root |x| = 0.335 (clear of Extra_gray_Body)
            r_low = 0.024
            z_low = -0.595          # root z = 0.785
            z_collar = z_low + r_low  # -0.571 (root z = 0.809)

            z_bend = -0.490         # root z = 0.890 (mid-chest neutral grip: z = 0.81..0.89!)
            r_top = 0.026
            z_top = z_bend + r_top  # -0.464 (root z = 0.916, right at shoulder/upper-chest line!)
            x_end = sx * 0.200      # root |x| = 0.520 (wide chest-press grip!)

            hv_ob = bpy.data.objects[hv_nm]
            hv_ob.location = Vector((0.0, 0.0, 0.0))
            hv_ob.rotation_mode = "XYZ"
            hv_ob.rotation_euler = (0.0, 0.0, 0.0)
            hv_ob.scale = Vector((1.0, 1.0, 1.0))

            stub_pts = [
                (x_arm, y0, -0.555),
                (sx * 0.062, y0, z_low),
                (x_in + sx * r_low, y0, z_low),
            ]
            cx_low = x_in + sx * r_low
            cz_low = z_low + r_low
            for i in range(1, 9):
                a = (math.pi * 0.5) * i / 8.0
                stub_pts.append((cx_low - sx * r_low * math.sin(a), y0, cz_low - r_low * math.cos(a)))

            bm_stub = bmesh.new()
            _sweep_round_tube(bm_stub, stub_pts, radius=0.016, segs=20, mat_idx=0)
            _sweep_round_tube(
                bm_stub,
                [(x_in, y0, z_collar - 0.006), (x_in, y0, z_collar + 0.008)],
                radius=0.0195, segs=20, mat_idx=1,
            )
            _sweep_round_tube(
                bm_stub,
                [(x_end - sx * 0.004, y0, z_top), (x_end + sx * 0.012, y0, z_top)],
                radius=0.0195, segs=20, mat_idx=1,
            )
            _replace_mesh(root, hv_ob, bm_stub, [m_red, m_steel])

            # Continuous black inverted-L grip tube (`handle.040` / `handle.041`)
            h_ob = bpy.data.objects[h_nm]
            h_ob.location = Vector((0.0, 0.0, 0.0))
            h_ob.rotation_mode = "XYZ"
            h_ob.rotation_euler = (0.0, 0.0, 0.0)
            h_ob.scale = Vector((1.0, 1.0, 1.0))

            grip_pts = [
                (x_in, y0, z_collar + 0.004),
                (x_in, y0, z_bend),
            ]
            cx_top = x_in + sx * r_top
            cz_top = z_bend
            for i in range(1, 9):
                a = (math.pi * 0.5) * i / 8.0
                grip_pts.append((cx_top - sx * r_top * math.cos(a), y0, cz_top + r_top * math.sin(a)))
            grip_pts.append((x_end, y0, z_top))

            bm_g = bmesh.new()
            _sweep_round_tube(bm_g, grip_pts, radius=0.0175, segs=20, mat_idx=0)
            _replace_mesh(root, h_ob, bm_g, [m_grip])

            for c_nm in (c1_nm, c2_nm, vc1_nm, vc2_nm):
                _clear_mesh(root, bpy.data.objects[c_nm])

            touched.extend([ma_nm, lk_nm, pf_nm, h_nm, hv_nm])

        # 3. Re-anchor end of Coated load cable.005 to raised overhead pivot bracket (0.320, 0.200, 1.380)
        lc = bpy.data.objects.get("Coated load cable.005")
        if lc and lc.type == "CURVE" and lc.data.splines:
            pts = lc.data.splines[0].points
            if len(pts) >= 2:
                pts[-1].co = (PIVOT_X, 0.200, PIVOT_Z, 1.0)
                touched.append(lc.name)

        root[TAG] = TAG_VER
        bpy.context.view_layer.update()
    finally:
        root["Stroke"] = saved_stroke
        bpy.context.view_layer.update()

    return {"machine": ROOT_NAME, "status": "fixed", "version": TAG_VER, "touched": touched}


def _main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    save = None
    if "--save" in argv:
        save = Path(argv[argv.index("--save") + 1]).expanduser().resolve()
        root_dir = Path(__file__).resolve().parents[2]
        if any(save.is_relative_to((root_dir / "promo" / d).resolve()) for d in ("scenes", "models")):
            raise SystemExit("refusing to save into promo/scenes or promo/models")
        save.parent.mkdir(parents=True, exist_ok=True)
    res = apply()
    print("detail6_fix_chest_press", json.dumps(res, ensure_ascii=False))
    if save is not None:
        bpy.ops.wm.save_as_mainfile(filepath=str(save), copy=True, compress=True, relative_remap=False)
        print("saved", save)


if __name__ == "__main__":
    _main()
