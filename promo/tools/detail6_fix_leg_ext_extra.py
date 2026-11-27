"""detail6 leg-extension Extra_blue mannequin pose & seating fix.

After P_leg_extension was updated to proper commercial ergonomics (knee pivot
at local y=-0.300, z=0.555; contoured shin bolster roller Ddetail6_SM_LE_ShinRoller
at y=-0.465, z=0.197; backrest shifted +0.04 m in Y), the seated background
mannequin (Extra_blue / Extra_blue_Body) remained in its old forward-slouched
pose with knees far ahead of the pivot and shins in front of the shin roller.

This standalone, 100% idempotent module repositions ONLY Extra_blue's pose bones
(leaving P_leg_extension and all other scene objects untouched) so that:
  * Pelvis & torso sit back against the reclined backrest (back.009) with zero
    clipping.
  * Thighs rest cleanly on the seat cushion (seat.013) with knees aligned near
    the P_leg_lever knee pivot (y=-0.300, z=0.555) and cleanly inside the dual
    lever arms (arm.009 / arm.010).
  * Lower shins sit cleanly behind Ddetail6_SM_LE_ShinRoller (back surface
    y=-0.403) with zero clipping.
  * Arms clear the side cam bar (cam) and hands grip the side handles
    (side_grip.002 / side_grip.003).

Because every bone transform is computed from rest-pose geometry and written as
an absolute location/quaternion, calling apply() any number of times produces
the exact same pose.

Usage:
    Blender -b promo/scenes/scene_gym.blend \
        -P promo/tools/detail6_fix_leg_ext_extra.py [-- --save out.blend]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

ARM_NAME = "Extra_blue"
BODY_NAME = "Extra_blue_Body"
MACHINE_NAME = "P_leg_extension"
ROLLER_NAME = "Ddetail6_SM_LE_ShinRoller"

TAG = "detail6_leg_ext_extra_fix"
TAG_VER = "v1"

# Target coordinates in Extra_blue armature local space
# (Extra_blue sits at (7.15, -2.3, 0.0), rot=(0, 0, pi), matching P_leg_extension
# except P_leg_extension.location.z = 0.0042).
PELVIS_HEAD_TARGET = Vector((0.0, 0.155, 0.580))

# Torso sagittal rotations in armature space (deg about +X; negative = recline back)
TORSO_PITCH_DEG = {
    "pelvis": -6.0,
    "spine_01": -3.0,
    "spine_02": -1.5,
    "spine_03": 0.0,
    "neck_01": 6.5,
    "head": 4.5,
}

# Leg targets (x mirrored by side: +1 for left, -1 for right)
KNEE_X = 0.086
KNEE_Y = -0.320
KNEE_Z = 0.558

ANKLE_X = 0.086
ANKLE_Y = -0.345
ANKLE_Z = 0.180

# Arm / hand grip targets (side_grip.002/003 at x=+-0.270, y=-0.14..0.06, z=0.440)
WRIST_X = 0.305
WRIST_Y = -0.025
WRIST_Z = 0.498


def _reset_pose(arm: bpy.types.Object) -> None:
    for pb in arm.pose.bones:
        pb.location = Vector((0.0, 0.0, 0.0))
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))
        pb.scale = Vector((1.0, 1.0, 1.0))
    bpy.context.view_layer.update()


def _rot_arm_x(arm: bpy.types.Object, pb_name: str, deg: float) -> None:
    bpy.context.view_layer.update()
    pb = arm.pose.bones[pb_name]
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))
    bpy.context.view_layer.update()
    cur_m = pb.matrix.to_3x3()
    r_arm = Matrix.Rotation(math.radians(deg), 3, "X")
    r_local = cur_m.transposed() @ r_arm @ cur_m
    pb.rotation_quaternion = r_local.to_quaternion().normalized()
    bpy.context.view_layer.update()


def _set_bone_dir(
    arm: bpy.types.Object,
    pb_name: str,
    desired_dir_arm: Vector,
    twist_deg: float = 0.0,
) -> None:
    bpy.context.view_layer.update()
    pb = arm.pose.bones[pb_name]
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))
    bpy.context.view_layer.update()
    cur_m = pb.matrix.to_3x3()
    cur_y = cur_m.col[1].normalized()
    tgt_y = Vector(desired_dir_arm).normalized()
    q_arm = cur_y.rotation_difference(tgt_y)
    r_local = cur_m.transposed() @ q_arm.to_matrix() @ cur_m
    if abs(twist_deg) > 1e-4:
        r_local = r_local @ Matrix.Rotation(math.radians(twist_deg), 3, "Y")
    pb.rotation_quaternion = r_local.to_quaternion().normalized()
    bpy.context.view_layer.update()


def _solve_2bone_ik(
    arm: bpy.types.Object,
    upper_name: str,
    lower_name: str,
    target_arm: Vector,
    pole_dir_arm: Vector,
) -> None:
    bpy.context.view_layer.update()
    pb1 = arm.pose.bones[upper_name]
    pb2 = arm.pose.bones[lower_name]
    p0 = pb1.head.copy()
    L1 = pb1.bone.length
    L2 = pb2.bone.length
    tgt = Vector(target_arm)
    d_vec = tgt - p0
    d = d_vec.length
    d_clamped = min(max(d, abs(L1 - L2) + 1e-4), L1 + L2 - 1e-4)
    u = d_vec.normalized()
    cos_a = max(
        -1.0,
        min(1.0, (L1 * L1 + d_clamped * d_clamped - L2 * L2) / (2.0 * L1 * d_clamped)),
    )
    sin_a = math.sqrt(max(0.0, 1.0 - cos_a * cos_a))
    pole = Vector(pole_dir_arm)
    pole_perp = pole - u * pole.dot(u)
    if pole_perp.length < 1e-6:
        pole_perp = Vector((0.0, 1.0, 0.0))
    pole_perp.normalize()
    mid_pos = p0 + u * (L1 * cos_a) + pole_perp * (L1 * sin_a)
    _set_bone_dir(arm, upper_name, mid_pos - p0)
    bpy.context.view_layer.update()
    p1 = pb2.head.copy()
    _set_bone_dir(arm, lower_name, tgt - p1)
    bpy.context.view_layer.update()


def _measure_metrics(
    arm: bpy.types.Object,
    body: bpy.types.Object,
    machine: bpy.types.Object,
) -> dict:
    inv_le = machine.matrix_world.inverted()
    deps = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(deps)
    me = ev.to_mesh()
    verts_le = [inv_le @ (ev.matrix_world @ v.co) for v in me.vertices]
    body_bvh = BVHTree.FromPolygons(verts_le, [list(p.vertices) for p in me.polygons])

    def _mesh_bvh(obj: bpy.types.Object) -> BVHTree:
        vs = [inv_le @ (obj.matrix_world @ v.co) for v in obj.data.vertices]
        ps = [list(p.vertices) for p in obj.data.polygons]
        return BVHTree.FromPolygons(vs, ps)

    overlaps = {}
    for part_name in (
        ROLLER_NAME,
        "arm.009",
        "arm.010",
        "cam",
        "Ddetail6_SM_LE_Frame",
        "seat.013",
        "back.009",
        "side_grip.002",
        "side_grip.003",
    ):
        obj = bpy.data.objects.get(part_name)
        if obj and obj.type == "MESH":
            overlaps[part_name] = len(body_bvh.overlap(_mesh_bvh(obj)))

    roller = bpy.data.objects.get(ROLLER_NAME)
    roller_clearance_mm = None
    roller_verts_inside = None
    if roller and roller.type == "MESH":
        r_pts = [inv_le @ (roller.matrix_world @ v.co) for v in roller.data.vertices]
        r_cy = 0.5 * (min(p.y for p in r_pts) + max(p.y for p in r_pts))
        r_cz = 0.5 * (min(p.z for p in r_pts) + max(p.z for p in r_pts))
        r_rad = 0.5 * (max(p.z for p in r_pts) - min(p.z for p in r_pts))
        r_xmin = min(p.x for p in r_pts)
        r_xmax = max(p.x for p in r_pts)
        dists = [
            ((v.y - r_cy) ** 2 + (v.z - r_cz) ** 2) ** 0.5 - r_rad
            for v in verts_le
            if r_xmin <= v.x <= r_xmax
        ]
        if dists:
            roller_clearance_mm = round(min(dists) * 1000.0, 2)
            roller_verts_inside = sum(1 for d in dists if d < 0.0)

    knee_l_le = inv_le @ (arm.matrix_world @ arm.pose.bones["calf_l"].head)
    thigh_z = [
        v.z
        for v in verts_le
        if -0.22 <= v.y <= 0.18 and abs(v.x) < 0.18 and v.z < 0.65
    ]
    ev.to_mesh_clear()

    return {
        "roller_min_clearance_mm": roller_clearance_mm,
        "roller_verts_inside": roller_verts_inside,
        "overlaps_poly_pairs": overlaps,
        "knee_l_le": [round(c, 4) for c in knee_l_le],
        "thigh_min_z_le": round(min(thigh_z), 4) if thigh_z else None,
        "feet_min_z_le": round(min(v.z for v in verts_le), 4),
    }


def apply() -> dict:
    arm = bpy.data.objects.get(ARM_NAME)
    body = bpy.data.objects.get(BODY_NAME)
    machine = bpy.data.objects.get(MACHINE_NAME)
    if arm is None or arm.type != "ARMATURE":
        raise RuntimeError(f"Missing armature {ARM_NAME!r}")
    if body is None or body.type != "MESH":
        raise RuntimeError(f"Missing mesh {BODY_NAME!r}")
    if machine is None:
        raise RuntimeError(f"Missing machine {MACHINE_NAME!r}")

    # Snapshot previous pose to detect whether anything changed
    prev_state = {
        pb.name: (
            tuple(round(v, 6) for v in pb.location),
            tuple(round(v, 6) for v in pb.rotation_quaternion),
        )
        for pb in arm.pose.bones
    }

    # Ensure deterministic armature object transform (unchanged from scene_gym.blend)
    arm.location = Vector((7.15, -2.3, 0.0))
    arm.rotation_mode = "XYZ"
    arm.rotation_euler = (0.0, 0.0, math.pi)
    arm.scale = Vector((1.0, 1.0, 1.0))

    # 1. Reset pose bones cleanly so apply() is 100% idempotent
    _reset_pose(arm)

    # 2. Position pelvis & recline torso to match backrest slope
    pelvis = arm.pose.bones["pelvis"]
    rest_m = pelvis.bone.matrix_local.to_3x3()
    pelvis.location = rest_m.transposed() @ (PELVIS_HEAD_TARGET - pelvis.bone.head_local)

    for bname, deg in TORSO_PITCH_DEG.items():
        _rot_arm_x(arm, bname, deg)

    # 3. Pose legs: thighs on seat, knees near pivot, shins cleanly behind roller
    for side, sx in (("l", 1.0), ("r", -1.0)):
        bpy.context.view_layer.update()
        hip = arm.pose.bones[f"thigh_{side}"].head.copy()
        knee_tgt = Vector((sx * KNEE_X, KNEE_Y, KNEE_Z))
        _set_bone_dir(arm, f"thigh_{side}", knee_tgt - hip)

        bpy.context.view_layer.update()
        knee_act = arm.pose.bones[f"calf_{side}"].head.copy()
        ankle_tgt = Vector((sx * ANKLE_X, ANKLE_Y, ANKLE_Z))
        _set_bone_dir(arm, f"calf_{side}", ankle_tgt - knee_act)

        _set_bone_dir(arm, f"foot_{side}", Vector((sx * 0.01, -0.82, -0.57)))

    # 4. Pose arms & hands: clear side cam bar, wrap gently around side grips
    for side, sx in (("l", 1.0), ("r", -1.0)):
        wrist_tgt = Vector((sx * WRIST_X, WRIST_Y, WRIST_Z))
        _solve_2bone_ik(
            arm,
            f"upperarm_{side}",
            f"lowerarm_{side}",
            wrist_tgt,
            Vector((sx * 0.95, 0.55, 0.05)),
        )
        _set_bone_dir(
            arm,
            f"hand_{side}",
            Vector((-sx * 0.14, -0.86, -0.49)),
            twist_deg=sx * 55.0,
        )
        for fname in ("index", "middle", "ring", "pinky"):
            for seg, deg in (("01", 38.0), ("02", 48.0), ("03", 32.0)):
                fpb = arm.pose.bones.get(f"{fname}_{seg}_{side}")
                if fpb is not None:
                    fpb.rotation_mode = "QUATERNION"
                    fpb.rotation_quaternion = Matrix.Rotation(
                        math.radians(sx * deg), 3, "Z"
                    ).to_quaternion()
        for seg, deg in (("01", 22.0), ("02", 28.0), ("03", 18.0)):
            fpb = arm.pose.bones.get(f"thumb_{seg}_{side}")
            if fpb is not None:
                fpb.rotation_mode = "QUATERNION"
                fpb.rotation_quaternion = Matrix.Rotation(
                    math.radians(sx * deg), 3, "Z"
                ).to_quaternion()

    bpy.context.view_layer.update()

    # Tag Extra_blue objects
    arm[TAG] = TAG_VER
    body[TAG] = TAG_VER

    new_state = {
        pb.name: (
            tuple(round(v, 6) for v in pb.location),
            tuple(round(v, 6) for v in pb.rotation_quaternion),
        )
        for pb in arm.pose.bones
    }
    changed_bones = sorted(k for k in new_state if new_state[k] != prev_state.get(k))
    metrics = _measure_metrics(arm, body, machine)

    return {
        "status": "fixed" if changed_bones else "already_applied",
        "changed_bone_count": len(changed_bones),
        "tag": f"{TAG}:{TAG_VER}",
        "metrics": metrics,
    }


def main(argv: list[str]) -> None:
    save_path = None
    if "--" in argv:
        args = argv[argv.index("--") + 1 :]
        if "--save" in args:
            save_path = args[args.index("--save") + 1]

    res = apply()
    print(json.dumps(res, indent=2, ensure_ascii=False))

    if save_path:
        out = Path(save_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(out))
        print(f"Saved: {out}")


if __name__ == "__main__":
    main(sys.argv)
