"""detail6 fix (v4): Chest-Supported T-Bar Row (`P_tbar_row_machine`) rebuilt to match commercial A-frame reference.

Reference layout (side view, -Y = front-left, +Y = rear-right footplate end, floor z = -0.022):
  1. Sleek A-frame:
     - Rear main spine sloping down-right from chest pad apex (0, +0.16, 0.96) to footplate base (0, +0.66, 0.02).
     - Twin front legs sloping down-left from chest pad apex (±0.15, +0.12, 0.94) to floor (±0.34, -0.48, -0.022).
     - Front leg cross-bar with yellow bumper stop at y = -0.30, z = 0.38.
     - Grounded rear footplate cradle + twin footplates sloping `/` (rotX = +0.48, facing UP-LEFT perpendicular
       to forward-leaning legs) at y = +0.74, z = 0.16.
     - Chest pad (`chest.001`) at top apex (0, +0.14, 1.04), tilted `\\` (-36 deg).
  2. Low rear pivot (`P_tbar_lever`) right above the footplates at (0, +0.58, +0.20).
  3. Center T-bar lever shaft angling UP-LEFT from low pivot (0, +0.58, +0.20) past the front legs to
     (0, -0.58, +0.52), continuing into a front chrome Olympic weight sleeve (`y = -0.58..-0.86`) holding
     `cast_plate.019/.020` cleanly in front.
  4. Separate U-shaped curved handle risers sweeping OUTWARD & UPWARD from the shaft (`y = -0.36, z = 0.46`)
     up to `z = 0.68`, topped by wide horizontal grips (`x = ±0.22..±0.42`) and parallel neutral grips
     (`y = -0.36..-0.18`).

Touches ONLY `P_tbar_row_machine` and its descendants. Preserves `Stroke L`/`Stroke R` drivers and `E_*` materials.
100% idempotent.
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT_NAME = "P_tbar_row_machine"
TAG = "detail6_fix_tbar_row"
TAG_VER = "v4"
OBTAG = "detail6_tbar_fix"
FLOOR_Z = -0.022


def _kid(root, name):
    for o in root.children_recursive:
        if o.name == name:
            return o
    raise KeyError(f"{root.name}: missing descendant {name!r}")


def _upd():
    bpy.context.view_layer.update()


def _in_root(root, ob):
    return root.matrix_world.inverted() @ ob.matrix_world


def _bbox_root(root, ob):
    M = _in_root(root, ob)
    if ob.type == "MESH" and ob.data and len(ob.data.vertices) > 0:
        pts = [M @ v.co for v in ob.data.vertices]
    else:
        pts = [M.translation]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return lo, hi


def _center_root(root, ob):
    lo, hi = _bbox_root(root, ob)
    return 0.5 * (lo + hi)


def _ensure_unique_mesh(root, ob):
    if ob.type != "MESH" or ob.data is None:
        return
    root_set = {root} | set(root.children_recursive)
    if any(o.data == ob.data and o not in root_set for o in bpy.data.objects):
        ob.data = ob.data.copy()


def _replace_mesh(root, ob, bm, mats=None):
    _ensure_unique_mesh(root, ob)
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
    """Add rectangular tube from p0 to p1 with cross-section (wx along X, wz perpendicular in YZ)."""
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
    faces = list({f for v in verts for f in v.link_faces})
    for f in faces:
        f.material_index = mat_idx
    if bevel > 0.0:
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=2, affect="EDGES", clamp_overlap=True)


def _add_cyl(bm, p0, p1, radius, segs=20, mat_idx=0):
    p0 = Vector(p0)
    p1 = Vector(p1)
    d = p1 - p0
    length = d.length
    if length < 1e-6:
        return
    z_axis = d.normalized()
    up = Vector((1.0, 0.0, 0.0)) if abs(z_axis.x) < 0.9 else Vector((0.0, 1.0, 0.0))
    x_axis = up.cross(z_axis).normalized()
    y_axis = z_axis.cross(x_axis).normalized()
    mid = 0.5 * (p0 + p1)
    rot = Matrix((x_axis, y_axis, z_axis)).transposed().to_4x4()
    mat = Matrix.Translation(mid) @ rot
    ret = bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=segs,
        radius1=radius, radius2=radius, depth=length, matrix=mat,
    )
    for v in ret["verts"]:
        for f in v.link_faces:
            f.material_index = mat_idx


def _add_curved_tube(bm, pts, wx, wz, mat_idx=0):
    """Sweep rectangular profile along polyline pts."""
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
        for su, sv in ((-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)):
            ring.append(bm.verts.new(p + u * (su * wx) + v * (sv * wz)))
        rings.append(ring)
    for r0, r1 in zip(rings[:-1], rings[1:]):
        for k in range(4):
            f = bm.faces.new((r0[k], r0[(k + 1) % 4], r1[(k + 1) % 4], r1[k]))
            f.material_index = mat_idx
    bm.faces.new(list(reversed(rings[0]))).material_index = mat_idx
    bm.faces.new(rings[-1]).material_index = mat_idx


def _hide_helper_mesh(root, ob):
    """Collapse obsolete duplicate/helper meshes cleanly into a tiny hidden triangle inside the spine."""
    ob.location = Vector((0.0, 0.16, 0.50))
    ob.rotation_mode = "XYZ"
    ob.rotation_euler = (0.0, 0.0, 0.0)
    ob.scale = Vector((1.0, 1.0, 1.0))
    bm = bmesh.new()
    _replace_mesh(root, ob, bm)


def apply() -> dict:
    root = bpy.data.objects.get(ROOT_NAME)
    if root is None:
        raise RuntimeError(f"Missing {ROOT_NAME} in scene")

    if root.get(TAG) == TAG_VER:
        return {"machine": ROOT_NAME, "status": "skipped", "reason": f"already {TAG_VER}"}

    saved_sl = float(root.get("Stroke L", 0.0))
    saved_sr = float(root.get("Stroke R", 0.0))
    root["Stroke L"] = 0.0
    root["Stroke R"] = 0.0
    _upd()

    m_silver = bpy.data.materials.get("E_silver")
    m_frame = bpy.data.materials.get("E_frame") or m_silver
    m_steel = bpy.data.materials.get("E_steel")
    m_grip = bpy.data.materials.get("E_grip")
    m_yellow = bpy.data.materials.get("E_yellow") or m_steel

    try:
        # 1. Chest pad (`chest.001`) at A-frame top apex (0, +0.14, +1.04), tilted `\` (-36 deg)
        pad = _kid(root, "chest.001")
        pad.rotation_mode = "XYZ"
        pad.rotation_euler = (-0.63, 0.0, 0.0)
        _upd()
        pad_c = _center_root(root, pad)
        pad.location += Vector((0.0, 0.140, 1.040)) - pad_c
        pad[OBTAG] = f"{TAG_VER}:chest_apex"
        _upd()

        # 2. Sleek A-frame (`frame`): rear main spine + twin front legs + cross-bar + yellow stop + rear cradle
        frame = _kid(root, "frame")
        frame.location = Vector((0.0, 0.0, 0.0))
        frame.rotation_mode = "XYZ"
        frame.rotation_euler = (0.0, 0.0, 0.0)
        frame.scale = Vector((1.0, 1.0, 1.0))
        bm_fr = bmesh.new()
        # Rear main spine from chest apex down-right to footplate base
        _add_beam(bm_fr, (0.0, 0.18, 0.96), (0.0, 0.68, 0.05), 0.072, 0.056, bevel=0.004, mat_idx=0)
        # Chest pad mounting neck plate
        _add_beam(bm_fr, (0.0, 0.14, 0.94), (0.0, 0.16, 1.01), 0.110, 0.055, bevel=0.003, mat_idx=0)
        # Twin front legs sloping down-left to floor (z = FLOOR_Z)
        for sx in (-1.0, 1.0):
            _add_beam(bm_fr, (sx * 0.11, 0.12, 0.93), (sx * 0.30, -0.44, FLOOR_Z + 0.015), 0.056, 0.068, bevel=0.004, mat_idx=0)
            # Floor footpad plates
            _add_beam(bm_fr, (sx * 0.30, -0.50, FLOOR_Z + 0.008), (sx * 0.30, -0.38, FLOOR_Z + 0.008), 0.110, 0.016, bevel=0.002, mat_idx=0)
        # Upper front leg tie bar under chest apex
        _add_beam(bm_fr, (-0.14, 0.12, 0.91), (0.14, 0.12, 0.91), 0.056, 0.056, bevel=0.003, mat_idx=0)
        # Lower front cross-bar (rest stop for T-bar shaft) + yellow rubber bumper pad
        _add_beam(bm_fr, (-0.25, -0.26, 0.35), (0.25, -0.26, 0.35), 0.044, 0.044, bevel=0.003, mat_idx=0)
        _add_beam(bm_fr, (0.0, -0.26, 0.372), (0.0, -0.26, 0.402), 0.075, 0.046, bevel=0.003, mat_idx=1)
        # Rear footplate cradle & floor skid base (grounded at FLOOR_Z)
        _add_beam(bm_fr, (-0.34, 0.68, 0.06), (0.34, 0.68, 0.06), 0.060, 0.060, bevel=0.003, mat_idx=0)
        for sx in (-1.0, 1.0):
            _add_beam(bm_fr, (sx * 0.30, 0.56, FLOOR_Z + 0.012), (sx * 0.30, 0.92, FLOOR_Z + 0.012), 0.064, 0.024, bevel=0.003, mat_idx=0)
            _add_beam(bm_fr, (sx * 0.30, 0.88, FLOOR_Z + 0.012), (sx * 0.30, 0.94, 0.28), 0.050, 0.042, bevel=0.003, mat_idx=0)
        # Rear curved heel-rail lip behind footplates
        _add_beam(bm_fr, (-0.32, 0.93, 0.27), (0.32, 0.93, 0.27), 0.045, 0.036, bevel=0.003, mat_idx=0)
        # Low pivot clevis bracket mounted on front face of rear spine at (0, +0.58, +0.20)
        for sx in (-1.0, 1.0):
            _add_beam(bm_fr, (sx * 0.042, 0.63, 0.16), (sx * 0.042, 0.56, 0.22), 0.014, 0.068, bevel=0.002, mat_idx=0)
        _replace_mesh(root, frame, bm_fr, [m_silver, m_yellow])
        frame[OBTAG] = f"{TAG_VER}:aframe"

        # 3. Footplates (`incline_footrest`, `incline_footrest.001`):
        #    Sloping `/` (rotX = +0.50 rad = +28.6 deg: LOW-left, HIGH-right, facing UP-LEFT perpendicular to legs!)
        for sx, fnm in ((-1.0, "incline_footrest"), (+1.0, "incline_footrest.001")):
            fob = _kid(root, fnm)
            fob.location = Vector((sx * 0.21, 0.74, 0.15))
            fob.rotation_mode = "XYZ"
            fob.rotation_euler = (0.50, 0.0, 0.0)
            fob.scale = Vector((1.0, 1.0, 1.0))
            bm_fp = bmesh.new()
            _add_beam(bm_fp, (0.0, -0.18, 0.0), (0.0, 0.18, 0.0), 0.22, 0.022, bevel=0.003, mat_idx=0)
            # Bottom heel lip perpendicular to footplate
            _add_beam(bm_fp, (0.0, 0.175, 0.0), (0.0, 0.175, 0.055), 0.22, 0.016, bevel=0.002, mat_idx=0)
            _replace_mesh(root, fob, bm_fp, [m_silver])
            fob[OBTAG] = f"{TAG_VER}:footplate_slash"

        # Clear obsolete old rail/post objects cleanly (no stray red bars or floating posts)
        for ob_name in (
            "foot.011", "foot.012", "foot_tie",
            "footrest_stay", "footrest_stay.001",
            "pivot_stand", "pivot_stand.001",
            "chest_mount", "counterweight", "counterweight.001",
            "lever_bearing_body.001", "lever_bearing_bolt.001", "lever_bearing_cap.001",
        ):
            _hide_helper_mesh(root, _kid(root, ob_name))

        # 4. Low rear pivot (`P_tbar_lever`) at (0, +0.58, +0.20) right above footplates!
        piv = _kid(root, "P_tbar_lever")
        piv.location = Vector((0.0, 0.58, 0.20))
        piv.rotation_mode = "XYZ"
        piv.rotation_euler = (0.0, 0.0, 0.0)
        piv[OBTAG] = f"{TAG_VER}:low_pivot"

        # Bearing hub visuals centered at (0, 0, 0) in P_tbar_lever space
        for nm, rad, ln, mat in (
            ("lever_bearing_body", 0.042, 0.072, m_silver),
            ("lever_bearing_cap",  0.032, 0.088, m_yellow),
            ("lever_bearing_bolt", 0.016, 0.104, m_steel),
        ):
            bob = _kid(root, nm)
            bob.location = Vector((0.0, 0.0, 0.0))
            bob.rotation_mode = "XYZ"
            bob.rotation_euler = (0.0, 0.0, 0.0)
            bm_b = bmesh.new()
            _add_cyl(bm_b, (-ln * 0.5, 0.0, 0.0), (ln * 0.5, 0.0, 0.0), rad, segs=24, mat_idx=0)
            _replace_mesh(root, bob, bm_b, [mat])

        # Center both arm empties on the low rear pivot (preserving Stroke L / Stroke R drivers)
        arm_l = _kid(root, "P_tbar_arm_L")
        arm_r = _kid(root, "P_tbar_arm_R")
        arm_l.location = Vector((0.0, 0.0, 0.0))
        arm_r.location = Vector((0.0, 0.0, 0.0))
        _upd()

        # 5. Center T-bar shaft + curved upward handle risers (in P_tbar_arm local space; pivot = (0,0,0))
        #    Pivot in root is (0, +0.58, +0.20):
        #    - Shaft runs from (0, 0, 0) -> (0, -1.16, +0.32) [root: (0, -0.58, +0.52)]
        #    - Handle riser branches at (0, -0.94, +0.26) [root: (0, -0.36, +0.46)]
        #      curving OUTWARD (±0.22) and UPWARD to ( ±0.22, -0.94, +0.48) [root: (±0.22, -0.36, +0.68)]!
        lever_l = _kid(root, "lever")
        lever_l.location = Vector((0.0, 0.0, 0.0))
        lever_l.rotation_mode = "XYZ"
        lever_l.rotation_euler = (0.0, 0.0, 0.0)
        bm_ll = bmesh.new()
        # Main center round shaft
        _add_cyl(bm_ll, (0.0, 0.0, 0.0), (0.0, -1.18, 0.325), 0.022, segs=20, mat_idx=0)
        # Left curved upward riser bracket (from shaft outward & up to handle top)
        _add_curved_tube(bm_ll, [
            (0.00, -0.94, 0.258),
            (-0.14, -0.94, 0.258),
            (-0.22, -0.94, 0.320),
            (-0.22, -0.94, 0.480),
        ], 0.032, 0.036, mat_idx=0)
        _replace_mesh(root, lever_l, bm_ll, [m_silver])

        lever_r = _kid(root, "lever.001")
        lever_r.location = Vector((0.0, 0.0, 0.0))
        lever_r.rotation_mode = "XYZ"
        lever_r.rotation_euler = (0.0, 0.0, 0.0)
        bm_lr = bmesh.new()
        # Right curved upward riser bracket
        _add_curved_tube(bm_lr, [
            (0.00, -0.94, 0.258),
            (0.14, -0.94, 0.258),
            (0.22, -0.94, 0.320),
            (0.22, -0.94, 0.480),
        ], 0.032, 0.036, mat_idx=0)
        _replace_mesh(root, lever_r, bm_lr, [m_silver])

        # 6. Dual grips at TOP of each upward riser: (±0.22, -0.94, +0.48) [root: (±0.22, -0.36, +0.68)]
        for side, sfx in ((-1.0, ""), (+1.0, ".001")):
            gx = side * 0.220
            gy = -0.940
            gz = 0.480

            # Wide grip extending outward: x = ±0.22 -> ±0.43
            wg = _kid(root, "wide_grip" + sfx)
            wg.location = Vector((0.0, 0.0, 0.0))
            wg.rotation_mode = "XYZ"
            wg.rotation_euler = (0.0, 0.0, 0.0)
            bm_wg = bmesh.new()
            _add_cyl(bm_wg, (gx, gy, gz), (side * 0.430, gy, gz), 0.018, segs=20, mat_idx=0)
            _replace_mesh(root, wg, bm_wg, [m_grip])

            for cname, cx in (("wide_grip_cap1" + sfx, gx), ("wide_grip_cap2" + sfx, side * 0.432)):
                cob = _kid(root, cname)
                cob.location = Vector((0.0, 0.0, 0.0))
                cob.rotation_mode = "XYZ"
                cob.rotation_euler = (0.0, 0.0, 0.0)
                bm_c = bmesh.new()
                _add_cyl(bm_c, (cx - 0.008, gy, gz), (cx + 0.008, gy, gz), 0.021, segs=20, mat_idx=0)
                _replace_mesh(root, cob, bm_c, [m_steel])

            # Parallel neutral grip extending backward toward user: y = -0.94 -> -0.75
            pg = _kid(root, "parallel_grip" + sfx)
            pg.location = Vector((0.0, 0.0, 0.0))
            pg.rotation_mode = "XYZ"
            pg.rotation_euler = (0.0, 0.0, 0.0)
            bm_pg = bmesh.new()
            _add_cyl(bm_pg, (gx, gy, gz), (gx, gy + 0.190, gz - 0.025), 0.018, segs=20, mat_idx=0)
            _replace_mesh(root, pg, bm_pg, [m_grip])

            for cname, py, pz in (
                ("parallel_grip_cap1" + sfx, gy, gz),
                ("parallel_grip_cap2" + sfx, gy + 0.192, gz - 0.025),
            ):
                cob = _kid(root, cname)
                cob.location = Vector((0.0, 0.0, 0.0))
                cob.rotation_mode = "XYZ"
                cob.rotation_euler = (0.0, 0.0, 0.0)
                bm_c = bmesh.new()
                _add_cyl(bm_c, (gx, py - 0.008, pz), (gx, py + 0.008, pz), 0.021, segs=20, mat_idx=0)
                _replace_mesh(root, cob, bm_c, [m_steel])

        # 7. Front chrome Olympic weight sleeve (`weight_horn`) + 2 stacked plates on the front shaft tip
        #    Shaft angle = atan2(0.325, 1.18) = +0.269 rad (~15.4 deg rising forward-left)
        horn = _kid(root, "weight_horn")
        horn.location = Vector((0.0, 0.0, 0.0))
        horn.rotation_mode = "XYZ"
        horn.rotation_euler = (0.0, 0.0, 0.0)
        bm_h = bmesh.new()
        _add_cyl(bm_h, (0.0, -1.16, 0.320), (0.0, -1.48, 0.408), 0.025, segs=24, mat_idx=0)
        # Collar flange
        _add_cyl(bm_h, (0.0, -1.14, 0.314), (0.0, -1.175, 0.324), 0.038, segs=24, mat_idx=0)
        _replace_mesh(root, horn, bm_h, [m_steel])
        _hide_helper_mesh(root, _kid(root, "weight_horn.001"))

        # Position cast_plate.019 and cast_plate.020 coaxially on the front Olympic weight sleeve!
        # Original cast_plate disc normal is along local X -> rotate Z by +90 deg so disc faces along Y,
        # then tilt X by -0.269 rad to match the rising front sleeve.
        for p_name, py, pz in (
            ("cast_plate.019", -1.23, 0.339),
            ("cast_plate.020", -1.28, 0.353),
        ):
            pob = _kid(root, p_name)
            pob.rotation_mode = "XYZ"
            pob.rotation_euler = (-0.269, 0.0, math.pi * 0.5)
            pob.location = Vector((0.0, py, pz))
            pob[OBTAG] = f"{TAG_VER}:front_sleeve_plate"

        root[TAG] = TAG_VER
        _upd()
    finally:
        root["Stroke L"] = saved_sl
        root["Stroke R"] = saved_sr
        _upd()

    return {"machine": ROOT_NAME, "status": "fixed", "version": TAG_VER}


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
    print("detail6_fix_tbar_row", json.dumps(res, ensure_ascii=False))
    if save is not None:
        bpy.ops.wm.save_as_mainfile(filepath=str(save), copy=True, compress=True, relative_remap=False)
        print("saved", save)


if __name__ == "__main__":
    _main()
