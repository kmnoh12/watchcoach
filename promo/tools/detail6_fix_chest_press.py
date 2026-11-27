"""detail6 fix: Chest Press (`P_chest_press_machine`) sleek inverted-L dual-grip handles.

Replaces the awkward `+`-shaped / forward-pointing handles on `P_chest_press_machine` with the
continuous inverted-L curved commercial chest-press handle from the user's reference photo:
  - Mounting collar welded cleanly onto the front tip of `press_forearm` / `press_forearm.001`
    at `P_Moving assembly` local `(sx*0.080, -0.380, 0.000)` (= root `(±0.400, -0.180, 0.950)`).
  - Sweeps smoothly UP into the vertical neutral grip (`z_root = 0.87..1.03`), then curves 90 deg
    OUTWARD along `±X` into the horizontal wide chest-press grip (`x_root = ±0.40..±0.57`, `z_root = 1.03`)
    with silver trim collars & outer end-cap.
  - Zero collision with `Extra_gray_Body` (all geometry stays at `|x| >= 0.37`).

Touches ONLY `P_chest_press_machine` handle objects. 100% idempotent.
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
TAG_VER = "v2"


def _ensure_unique(root, ob):
    if ob.type != "MESH" or ob.data is None:
        return
    root_set = {root} | set(root.children_recursive)
    if any(o.data == ob.data and o not in root_set for o in bpy.data.objects):
        ob.data = ob.data.copy()


def _replace_mesh(root, ob, bm, mat=None):
    _ensure_unique(root, ob)
    me = ob.data
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.update()
    if mat is not None:
        me.materials.clear()
        me.materials.append(mat)


def _sweep_round_tube(bm, pts, radius, segs=20):
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
            bm.faces.new((r0[k], r0[(k + 1) % segs], r1[(k + 1) % segs], r1[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])


def _add_cyl(bm, p0, p1, radius, segs=20):
    _sweep_round_tube(bm, [p0, p1], radius, segs=segs)


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

    specs = [
        (-1.0, "handle.040", "handle_cap1", "handle_cap2", "handle_v", "handle_v_cap1", "handle_v_cap2"),
        (+1.0, "handle.041", "handle_cap1.001", "handle_cap2.001", "handle_v.001", "handle_v_cap1.001", "handle_v_cap2.001"),
    ]
    touched = []

    for sx, h_nm, c1_nm, c2_nm, hv_nm, vc1_nm, vc2_nm in specs:
        # Anchor at press_forearm tip in P_Moving assembly local space:
        # (sx*0.080, -0.380, 0.000) -> root (±0.400, -0.180, 0.950).
        # Build sleek inverted-L handle:
        #   - Base stem from press_forearm tip (sx*0.080, -0.380, 0.000) -> slightly down/in to (sx*0.075, -0.380, -0.070)
        #   - Vertical neutral grip rising from z = -0.070 -> +0.065 at x = sx*0.075
        #   - Smooth 90-deg rounded corner (radius 0.032) bending OUTWARD along +sx*X
        #   - Horizontal wide chest-press grip extending outward from x = sx*0.107 -> sx*0.255 at z = +0.097
        #     (root: x = ±0.427..±0.575, y = -0.180, z = 1.047)
        x0 = sx * 0.075
        y0 = -0.380
        z_bot = -0.075
        z_bend = 0.065
        r_bend = 0.032
        z_top = z_bend + r_bend  # +0.097
        x_end = sx * 0.255

        # 1. Continuous black grip inverted-L tube (`handle.040` / `handle.041`)
        h_ob = bpy.data.objects[h_nm]
        h_ob.location = Vector((0.0, 0.0, 0.0))
        h_ob.rotation_mode = "XYZ"
        h_ob.rotation_euler = (0.0, 0.0, 0.0)
        h_ob.scale = Vector((1.0, 1.0, 1.0))

        pts = [
            (x0, y0, z_bot),
            (x0, y0, z_bend),
        ]
        # Smooth 90-deg arc from vertical (+Z) to outward (+sx*X)
        cx_arc = x0 + sx * r_bend
        cz_arc = z_bend
        for i in range(1, 9):
            a = (math.pi * 0.5) * i / 8.0
            px = cx_arc - sx * r_bend * math.cos(a)
            pz = cz_arc + r_bend * math.sin(a)
            pts.append((px, y0, pz))
        pts.append((x_end, y0, z_top))

        bm_h = bmesh.new()
        _sweep_round_tube(bm_h, pts, radius=0.0175, segs=20)
        _replace_mesh(root, h_ob, bm_h, m_grip)

        # 2. Mounting bracket & collar connecting press_forearm tip cleanly to handle base (`handle_v` / `.001`)
        hv_ob = bpy.data.objects[hv_nm]
        hv_ob.location = Vector((0.0, 0.0, 0.0))
        hv_ob.rotation_mode = "XYZ"
        hv_ob.rotation_euler = (0.0, 0.0, 0.0)
        hv_ob.scale = Vector((1.0, 1.0, 1.0))
        bm_b = bmesh.new()
        # Sleek steel sleeve collar at press_forearm junction
        _add_cyl(bm_b, (sx * 0.080, y0 + 0.025, 0.000), (x0, y0 - 0.002, 0.000), radius=0.024, segs=20)
        # Bottom cap collar under vertical grip
        _add_cyl(bm_b, (x0, y0, z_bot - 0.012), (x0, y0, z_bot + 0.004), radius=0.0205, segs=20)
        # Outer end-cap collar at horizontal grip tip
        _add_cyl(bm_b, (x_end - sx * 0.004, y0, z_top), (x_end + sx * 0.012, y0, z_top), radius=0.0205, segs=20)
        _replace_mesh(root, hv_ob, bm_b, m_steel)

        # Clear redundant old cap objects so no stray caps float
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
