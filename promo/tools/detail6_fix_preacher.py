"""detail6 preacher curl lever & handle fix.

Fixes P_preacher_machine so its lever arm and handles start at a natural
extended-arm curl angle (~38 deg forward-down, matching the -40 deg slant of
arm_pad) with realistic horizontal EZ-angled inward-pointing grips instead of
vertical cylinders hanging straight down beneath the arm tips, and curls
smoothly up toward the user's shoulders at Stroke=1.0 (+70 deg above horizontal)
with zero clipping and intact cable/hub connections.

Touches ONLY P_preacher_machine and its descendants:
  * P_Moving assembly.022: updates rotation_euler[0] driver to start at +8.5 deg
    (putting the -29.5 deg built lever arm at -38.0 deg along the arm_pad slant)
    and sweep -108.0 deg across Stroke 0..1 (reaching +70.0 deg at Stroke=1.0).
  * grip.002 / grip.003: rebuilds meshes in-place as horizontal inward-pointing
    ergonomic EZ-curl handles (37 mm diameter with chamfered end caps and inner
    arm-mount collar) seated solidly into the distal tips of arm.005 / arm.006,
    preserving object names, parenting, and E_grip material.

100% idempotent: running apply() multiple times produces identical transforms,
driver expression, and mesh geometry.

Usage:
    Blender -b promo/scenes/scene_gym.blend -P promo/tools/detail6_fix_preacher.py [-- --save out.blend]
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT_NAME = "P_preacher_machine"
MOVING_NAME = "P_Moving assembly.022"
GRIP_L_NAME = "grip.002"
GRIP_R_NAME = "grip.003"
TAG = "detail6_fix_preacher"
TAG_VER = "v1"

# Lever arm built angle is -29.5 deg below -Y in P_Moving assembly.022 local space.
# +8.5 deg at Stroke=0 puts lever arm at -38.0 deg (matching -40 deg arm_pad slant).
# -108.0 deg sweep puts lever arm at +70.0 deg at Stroke=1.0 (curled toward shoulders).
START_ROT_X_DEG = 8.5
SWEEP_ROT_X_DEG = -108.0
START_ROT_X_RAD = math.radians(START_ROT_X_DEG)
SWEEP_ROT_X_RAD = math.radians(SWEEP_ROT_X_DEG)
DRIVER_EXPR = f"{START_ROT_X_RAD:.16f}+{SWEEP_ROT_X_RAD:.16f}*v"

# Handle geometry in P_Moving assembly.022 local space (mirrored across X)
# Distal tips of arm.005 / arm.006 end near (s*0.200, -0.230, -0.130); seating
# the grip axis ~14 mm back from the end face keeps the collar flush on the
# inner flat wall of the tube with zero end-cap poke-through.
GRIP_OUTER_X = 0.200      # embedded solidly inside arm tube (x in [0.169, 0.231])
GRIP_COLLAR_X = 0.168     # inner face of arm tube where collar transitions to grip
GRIP_INNER_X = 0.045      # inner end of handle (9 cm center gap between L/R)
GRIP_OUTER_YZ = (-0.216, -0.122)
GRIP_INNER_YZ = (-0.224, -0.098)  # ~9 deg upward EZ-curl ergonomic angle
GRIP_RADIUS = 0.0185      # 37 mm diameter
COLLAR_RADIUS = 0.0210    # 42 mm mounting collar at arm face (well inside 56 mm tube)
GRIP_SEGS = 24


def _build_ez_grip_mesh(mesh: bpy.types.Mesh, side: int) -> None:
    """Rebuild grip mesh in-place in P_Moving assembly.022 local space.

    side = -1 for left (grip.002), +1 for right (grip.003).
    """
    p_outer = Vector((side * GRIP_OUTER_X, GRIP_OUTER_YZ[0], GRIP_OUTER_YZ[1]))
    p_inner = Vector((side * GRIP_INNER_X, GRIP_INNER_YZ[0], GRIP_INNER_YZ[1]))
    axis = p_inner - p_outer
    total_len = axis.length
    u = axis.normalized()

    # Orthonormal basis (v, w) perpendicular to handle axis u
    ref = Vector((0.0, 0.0, 1.0))
    v = u.cross(ref).normalized()
    w = u.cross(v).normalized()

    # Profile stations along u: (distance_from_outer, radius)
    # 0.000 -> inside arm tip, ~0.037 -> arm inner face, collar step, main grip, chamfered cap
    collar_end = (GRIP_OUTER_X - GRIP_COLLAR_X) / (GRIP_OUTER_X - GRIP_INNER_X) * total_len
    stations = [
        (0.0, COLLAR_RADIUS),
        (collar_end + 0.010, COLLAR_RADIUS),
        (collar_end + 0.014, GRIP_RADIUS),
        (total_len - 0.008, GRIP_RADIUS),
        (total_len - 0.003, GRIP_RADIUS * 0.86),
        (total_len, GRIP_RADIUS * 0.55),
    ]

    bm = bmesh.new()
    rings = []
    for dist, rad in stations:
        center = p_outer + u * dist
        ring = []
        for i in range(GRIP_SEGS):
            ang = (2.0 * math.pi * i) / GRIP_SEGS
            pt = center + (v * math.cos(ang) + w * math.sin(ang)) * rad
            ring.append(bm.verts.new(pt))
        rings.append(ring)

    # Connect adjacent rings
    for r0, r1 in zip(rings[:-1], rings[1:]):
        for i in range(GRIP_SEGS):
            j = (i + 1) % GRIP_SEGS
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))

    # Cap ends
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        f.smooth = True

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def _update_moving_driver(root: bpy.types.Object, mv: bpy.types.Object) -> str:
    """Set deterministic rotation_euler[0] driver on P_Moving assembly.022."""
    mv.rotation_mode = "XYZ"
    mv.rotation_euler = (START_ROT_X_RAD, 0.0, 0.0)

    if mv.animation_data is None:
        mv.animation_data_create()

    fcurve = None
    for fc in mv.animation_data.drivers:
        if fc.data_path == "rotation_euler" and fc.array_index == 0:
            fcurve = fc
            break
    if fcurve is None:
        fcurve = mv.driver_add("rotation_euler", 0)

    drv = fcurve.driver
    drv.type = "SCRIPTED"
    drv.expression = DRIVER_EXPR

    # Ensure single variable 'v' bound to root["Stroke"]
    while len(drv.variables) > 0:
        drv.variables.remove(drv.variables[0])
    var = drv.variables.new()
    var.name = "v"
    var.type = "SINGLE_PROP"
    tgt = var.targets[0]
    tgt.id_type = "OBJECT"
    tgt.id = root
    tgt.data_path = '["Stroke"]'

    return drv.expression


def _bbox_in_root(root_inv: Matrix, obj: bpy.types.Object, depsgraph) -> dict:
    ev = obj.evaluated_get(depsgraph)
    pts = [root_inv @ (ev.matrix_world @ v.co) for v in ev.data.vertices]
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    zs = [p.z for p in pts]
    return {
        "x": [round(min(xs), 4), round(max(xs), 4)],
        "y": [round(min(ys), 4), round(max(ys), 4)],
        "z": [round(min(zs), 4), round(max(zs), 4)],
    }


def apply() -> dict:
    root = bpy.data.objects.get(ROOT_NAME)
    if root is None:
        raise RuntimeError(f"Object not found: {ROOT_NAME}")

    mv = bpy.data.objects.get(MOVING_NAME)
    if mv is None or mv.parent != root:
        raise RuntimeError(f"Expected child {MOVING_NAME} under {ROOT_NAME}")

    grip_l = bpy.data.objects.get(GRIP_L_NAME)
    grip_r = bpy.data.objects.get(GRIP_R_NAME)
    for g, name in ((grip_l, GRIP_L_NAME), (grip_r, GRIP_R_NAME)):
        if g is None or g.parent != mv:
            raise RuntimeError(f"Expected child {name} under {MOVING_NAME}")

    # 1. Update driver on P_Moving assembly.022
    expr = _update_moving_driver(root, mv)

    # 2. Rebuild grip.002 and grip.003 in-place (preserving materials & parenting)
    for g, side in ((grip_l, -1), (grip_r, 1)):
        # Make sure mesh is single-user before editing
        if g.data.users > 1:
            g.data = g.data.copy()
        g.location = (0.0, 0.0, 0.0)
        g.rotation_mode = "XYZ"
        g.rotation_euler = (0.0, 0.0, 0.0)
        g.scale = (1.0, 1.0, 1.0)
        _build_ez_grip_mesh(g.data, side)

    # Tag root for traceability
    root[TAG] = TAG_VER

    # Evaluate Stroke=0 and Stroke=1 for report, then restore original Stroke
    orig_stroke = float(root.get("Stroke", 0.0))
    root_inv = root.matrix_world.inverted()
    sweep = {}
    for s_val, key in ((0.0, "stroke_0"), (1.0, "stroke_1")):
        root["Stroke"] = s_val
        root.update_tag()
        bpy.context.scene.frame_set(bpy.context.scene.frame_current)
        dg = bpy.context.evaluated_depsgraph_get()
        ev_mv = mv.evaluated_get(dg)
        sweep[key] = {
            "mv_rot_x_deg": round(math.degrees(ev_mv.rotation_euler.x), 2),
            "grip_l_bb": _bbox_in_root(root_inv, grip_l, dg),
            "grip_r_bb": _bbox_in_root(root_inv, grip_r, dg),
        }

    root["Stroke"] = orig_stroke
    root.update_tag()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)

    return {
        "root": ROOT_NAME,
        "tag": f"{TAG}:{TAG_VER}",
        "driver_expr": expr,
        "start_rot_x_deg": START_ROT_X_DEG,
        "sweep_rot_x_deg": SWEEP_ROT_X_DEG,
        "grip_l_verts": len(grip_l.data.vertices),
        "grip_r_verts": len(grip_r.data.vertices),
        "sweep": sweep,
    }


def _parse_args(argv):
    save_path = None
    if "--" in argv:
        extra = argv[argv.index("--") + 1 :]
        if "--save" in extra:
            idx = extra.index("--save")
            if idx + 1 < len(extra):
                save_path = extra[idx + 1]
    return save_path


if __name__ == "__main__":
    res = apply()
    print(json.dumps(res, indent=2))
    save_to = _parse_args(sys.argv)
    if save_to:
        out = Path(save_to).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(out))
        print(f"Saved: {out}")
