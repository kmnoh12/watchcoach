"""detail6 fix (v3): Chest Press (`P_chest_press_machine`) curved inward-stub + inverted-L dual-grip handles.

Matches the exact commercial reference handle geometry:
  - From the front tip of the red lever arm (`press_forearm` at `P_Moving assembly` local `(sx*0.080, -0.380, 0.000)`),
    a matching red curved bracket tube goes INWARD toward the chest (`x = sx*0.080 -> sx*0.010`, dipping slightly to
    `z = -0.045` for chest-height ergonomics) and bends smoothly 90 deg UPWARD into a silver trim collar.
  - From that collar, a continuous black inverted-L grip tube rises vertically (neutral grip, `z = -0.020 -> +0.085`),
    curves smoothly 90 deg OUTWARD (radius 0.028), and extends horizontally outward (`x = sx*0.038 -> sx*0.200`,
    `z = +0.113`, wide chest-press grip) with a silver outer end-cap.
  - Zero collision with `Extra_gray_Body` (innermost grip at `root |x| = 0.330`).

Touches ONLY `P_chest_press_machine` handle objects. 100% idempotent.
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT_NAME = "P_chest_press_machine"
TAG = "detail6_fix_chest_press"
TAG_VER = "v3"


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
    ob.location = Vector((0.0, -0.380, 0.0))
    ob.rotation_mode = "XYZ"
    ob.rotation_euler = (0.0, 0.0, 0.0)
    ob.scale = Vector((1.0, 1.0, 1.0))
    _replace_mesh(root, ob, bmesh.new())


def apply() -> dict:
    root = bpy.data.objects.get(ROOT_NAME)
    if root is None:
        raise RuntimeError(f"Missing {ROOT_NAME} in scene")

    if root.get(TAG) == TAG_VER:
        return {"machine": ROOT_NAME, "status": "skipped", "reason": f"already {TAG_VER}"}

    m_grip = bpy.data.materials.get("E_grip")
    m_steel = bpy.data.materials.get("E_steel")
    m_frame = bpy.data.materials.get("E_frame") or m_steel
    # Reuse the exact red accent material from press_forearm if present
    pf = bpy.data.objects.get("press_forearm")
    if pf and pf.data and len(pf.data.materials) > 0 and pf.data.materials[0]:
        m_frame = pf.data.materials[0]

    specs = [
        (-1.0, "handle.040", "handle_cap1", "handle_cap2", "handle_v", "handle_v_cap1", "handle_v_cap2"),
        (+1.0, "handle.041", "handle_cap1.001", "handle_cap2.001", "handle_v.001", "handle_v_cap1.001", "handle_v_cap2.001"),
    ]
    touched = []

    for sx, h_nm, c1_nm, c2_nm, hv_nm, vc1_nm, vc2_nm in specs:
        y0 = -0.380
        # Geometry in P_Moving assembly local space (root pivot at (sx*0.320, 0.200, 0.950)):
        # 1. Curved red stub (`handle_v`) goes INWARD from forearm tip (sx*0.085, y0, -0.015)
        #    -> inward to (sx*0.036, y0, -0.045) -> curves 90 deg UP (r=0.026) to (sx*0.010, y0, -0.019)
        x_arm = sx * 0.085
        x_in = sx * 0.010       # root |x| = 0.330 (cleanly inside lever arm, clear of Extra_gray_Body)
        r_low = 0.026
        z_low = -0.045
        z_collar = z_low + r_low  # -0.019 (root z = 0.931)

        z_bend = 0.082            # vertical neutral grip ~10.1 cm straight + bends
        r_top = 0.028
        z_top = z_bend + r_top    # +0.110 (root z = 1.060)
        x_end = sx * 0.205        # root |x| = 0.525 (17 cm wide horizontal grip)

        # Build red curved inward stub + silver trim collars in `handle_v`
        hv_ob = bpy.data.objects[hv_nm]
        hv_ob.location = Vector((0.0, 0.0, 0.0))
        hv_ob.rotation_mode = "XYZ"
        hv_ob.rotation_euler = (0.0, 0.0, 0.0)
        hv_ob.scale = Vector((1.0, 1.0, 1.0))

        stub_pts = [
            (x_arm, y0, -0.008),
            (sx * 0.060, y0, z_low),
            (x_in + sx * r_low, y0, z_low),
        ]
        # Smooth 90-deg arc from inward (-sx*X) to upward (+Z)
        cx_low = x_in + sx * r_low
        cz_low = z_low + r_low
        for i in range(1, 9):
            a = (math.pi * 0.5) * i / 8.0
            px = cx_low - sx * r_low * math.sin(a)
            pz = cz_low - r_low * math.cos(a)
            stub_pts.append((px, y0, pz))

        bm_stub = bmesh.new()
        _sweep_round_tube(bm_stub, stub_pts, radius=0.016, segs=20, mat_idx=0)
        # Silver collar at transition from red stub to black vertical grip
        _sweep_round_tube(
            bm_stub,
            [(x_in, y0, z_collar - 0.006), (x_in, y0, z_collar + 0.008)],
            radius=0.0195, segs=20, mat_idx=1,
        )
        # Silver outer end-cap at horizontal grip tip
        _sweep_round_tube(
            bm_stub,
            [(x_end - sx * 0.004, y0, z_top), (x_end + sx * 0.012, y0, z_top)],
            radius=0.0195, segs=20, mat_idx=1,
        )
        _replace_mesh(root, hv_ob, bm_stub, [m_frame, m_steel])

        # Build continuous black inverted-L grip tube in `handle.040` / `handle.041`
        h_ob = bpy.data.objects[h_nm]
        h_ob.location = Vector((0.0, 0.0, 0.0))
        h_ob.rotation_mode = "XYZ"
        h_ob.rotation_euler = (0.0, 0.0, 0.0)
        h_ob.scale = Vector((1.0, 1.0, 1.0))

        grip_pts = [
            (x_in, y0, z_collar + 0.004),
            (x_in, y0, z_bend),
        ]
        # Smooth 90-deg arc from vertical (+Z) to outward (+sx*X)
        cx_top = x_in + sx * r_top
        cz_top = z_bend
        for i in range(1, 9):
            a = (math.pi * 0.5) * i / 8.0
            px = cx_top - sx * r_top * math.cos(a)
            pz = cz_top + r_top * math.sin(a)
            grip_pts.append((px, y0, pz))
        grip_pts.append((x_end, y0, z_top))

        bm_g = bmesh.new()
        _sweep_round_tube(bm_g, grip_pts, radius=0.0175, segs=20, mat_idx=0)
        _replace_mesh(root, h_ob, bm_g, [m_grip])

        for c_nm in (c1_nm, c2_nm, vc1_nm, vc2_nm):
            _clear_mesh(root, bpy.data.objects[c_nm])

        touched.extend([h_nm, hv_nm, c1_nm, c2_nm, vc1_nm, vc2_nm])

    root[TAG] = TAG_VER
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
