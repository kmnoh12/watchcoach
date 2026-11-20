"""Build 7 standard IFBB bodybuilding posing animations (stand -> setup -> peak flex hold -> return to stand)
rigged directly on the V5 base model.

Outputs:
  - promo/poses/posing_animations.blend  (V5 base rig + 7 full 90-frame Bezier Actions @ 30fps)
  - promo/poses/posing_animations.json   (keyframe bone transforms for web/Three.js simulator reuse)
  - promo/renders/posing_sheet.png       (visual verification grid of all 7 peak poses on V5)

Run:
  Blender -b --factory-startup -P promo/tools/build_posing_anims.py [-- --no-render]
"""
import importlib.util
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)
import wc_lib as W  # noqa: E402

ROOT = W.ROOT
FPS = 30
TOTAL_FRAMES = 90  # 3.0s @ 30fps: 1(stand) -> 16(setup) -> 32(hit) -> 54(peak hold) -> 72(release) -> 90(stand)

AX = {"pitch": Vector((1, 0, 0)), "side": Vector((0, 1, 0)), "twist": Vector((0, 0, 1))}
ORDER_ROT = ["spine_01", "spine_02", "spine_03", "neck_01", "head", "clavicle_l", "clavicle_r"]
ORDER_AIM = ["upperarm_l", "lowerarm_l", "upperarm_r", "lowerarm_r", "thigh_l", "calf_l", "thigh_r", "calf_r"]
FINGERS = ["index", "middle", "ring", "pinky"]
CURL = {"fist": (78, 96, 62), "relax": (14, 22, 14), "open": (0, 0, 0), "grip": (45, 60, 40)}

# ------------------------------------------------------------------ 7 Standard Bodybuilding Poses
STAND = {
    "sym": {"upperarm": [0.18, 0.02, -1], "lowerarm": [0.10, 0.12, -1], "thigh": [0.07, 0, -1], "calf": [0.04, 0, -1]},
    "fingers": {"l": "relax", "r": "relax"},
}

POSING_ROUTINES = {
    "pose_front_double_biceps": {
        "label": "프론트 더블 바이셉스 (Front Double Biceps)",
        "setup": {
            "root": {"pitch": -3, "twist": -4},
            "rot": {"spine_02": {"pitch": -4}, "head": {"pitch": -4}},
            "sym": {"upperarm": [0.78, 0.12, -0.35], "lowerarm": [0.45, 0.25, 0.55]},
            "aim": {"thigh_l": [0.22, 0.16, -1], "calf_l": [0.14, 0.02, -1],
                    "thigh_r": [-0.14, -0.04, -1], "calf_r": [-0.08, 0, -1]},
            "fingers": {"l": "fist", "r": "fist"},
        },
        "hit": {
            "root": {"pitch": -7, "twist": -5},
            "rot": {"spine_02": {"pitch": -6}, "spine_03": {"pitch": -8}, "head": {"pitch": -8, "twist": 5},
                    "clavicle_l": {"side": 6}, "clavicle_r": {"side": -6}},
            "sym": {"upperarm": [1.0, 0.04, 0.16], "lowerarm": [-0.12, 0.08, 1.0]},
            "aim": {"thigh_l": [0.28, 0.22, -1], "calf_l": [0.18, 0.02, -1],
                    "thigh_r": [-0.16, -0.05, -1], "calf_r": [-0.09, 0, -1]},
            "fingers": {"l": "fist", "r": "fist"},
        },
        "peak": {
            "root": {"pitch": -9, "twist": -6},
            "rot": {"spine_02": {"pitch": -7}, "spine_03": {"pitch": -10}, "head": {"pitch": -10, "twist": 6},
                    "clavicle_l": {"side": 8}, "clavicle_r": {"side": -8}},
            "sym": {"upperarm": [1.0, 0.02, 0.22], "lowerarm": [-0.18, 0.08, 1.0]},
            "aim": {"thigh_l": [0.30, 0.24, -1], "calf_l": [0.19, 0.02, -1],
                    "thigh_r": [-0.16, -0.05, -1], "calf_r": [-0.09, 0, -1]},
            "fingers": {"l": "fist", "r": "fist"},
        },
    },
    "pose_front_lat_spread": {
        "label": "프론트 랫 스프레드 (Front Lat Spread)",
        "setup": {
            "root": {"pitch": 2},
            "rot": {"spine_03": {"pitch": -3}, "clavicle_l": {"twist": 10}, "clavicle_r": {"twist": -10}},
            "sym": {"upperarm": [0.68, -0.05, -0.68], "lowerarm": [-0.55, 0.15, -0.78],
                    "thigh": [0.18, 0.04, -1], "calf": [0.10, 0, -1]},
            "fingers": {"l": "fist", "r": "fist"},
        },
        "hit": {
            "root": {"pitch": -4},
            "rot": {"spine_02": {"pitch": -5}, "spine_03": {"pitch": -7}, "head": {"pitch": -6},
                    "clavicle_l": {"twist": 18, "side": 6}, "clavicle_r": {"twist": -18, "side": -6}},
            "sym": {"upperarm": [0.95, 0.10, -0.42], "lowerarm": [-0.88, 0.22, -0.45],
                    "thigh": [0.24, 0.08, -1], "calf": [0.12, 0, -1]},
            "fingers": {"l": "fist", "r": "fist"},
        },
        "peak": {
            "root": {"pitch": -6},
            "rot": {"spine_02": {"pitch": -6}, "spine_03": {"pitch": -9}, "head": {"pitch": -8},
                    "clavicle_l": {"twist": 22, "side": 8}, "clavicle_r": {"twist": -22, "side": -8}},
            "sym": {"upperarm": [1.0, 0.14, -0.36], "lowerarm": [-0.92, 0.24, -0.40],
                    "thigh": [0.26, 0.09, -1], "calf": [0.13, 0, -1]},
            "fingers": {"l": "fist", "r": "fist"},
        },
    },
    "pose_side_chest": {
        "label": "사이드 체스트 (Side Chest)",
        "setup": {
            "root": {"twist": 42, "pitch": -2},
            "rot": {"spine_02": {"twist": -10}, "head": {"twist": -32}},
            "aim": {"upperarm_l": [0.25, 0.25, -0.90], "lowerarm_l": [-0.30, 0.85, 0.15],
                    "upperarm_r": [-0.15, 0.45, -0.85], "lowerarm_r": [0.45, 0.80, 0.10],
                    "thigh_l": [0.12, 0.28, -1], "calf_l": [0.06, -0.18, -1],
                    "thigh_r": [-0.08, -0.06, -1], "calf_r": [-0.04, 0, -1]},
            "fingers": {"l": "fist", "r": "grip"},
        },
        "hit": {
            "root": {"twist": 68, "pitch": -5},
            "rot": {"spine_02": {"twist": -18, "pitch": -6}, "spine_03": {"twist": -14, "pitch": -8},
                    "neck_01": {"twist": -14}, "head": {"twist": -24, "pitch": -5}},
            "aim": {"upperarm_l": [0.18, 0.12, -0.96], "lowerarm_l": [-0.55, 0.78, 0.26],
                    "upperarm_r": [-0.12, 0.55, -0.82], "lowerarm_r": [0.68, 0.65, 0.22],
                    "thigh_l": [0.16, 0.42, -1], "calf_l": [0.08, -0.36, -1],
                    "thigh_r": [-0.10, -0.08, -1], "calf_r": [-0.05, 0, -1]},
            "fingers": {"l": "fist", "r": "grip"},
        },
        "peak": {
            "root": {"twist": 72, "pitch": -7},
            "rot": {"spine_02": {"twist": -20, "pitch": -7}, "spine_03": {"twist": -16, "pitch": -10},
                    "neck_01": {"twist": -16}, "head": {"twist": -24, "pitch": -6}},
            "aim": {"upperarm_l": [0.15, 0.10, -0.98], "lowerarm_l": [-0.60, 0.74, 0.30],
                    "upperarm_r": [-0.10, 0.58, -0.80], "lowerarm_r": [0.72, 0.62, 0.25],
                    "thigh_l": [0.16, 0.45, -1], "calf_l": [0.08, -0.40, -1],
                    "thigh_r": [-0.10, -0.08, -1], "calf_r": [-0.05, 0, -1]},
            "fingers": {"l": "fist", "r": "grip"},
        },
    },
    "pose_side_triceps": {
        "label": "사이드 트라이셉스 (Side Triceps)",
        "setup": {
            "root": {"twist": 44, "pitch": -2},
            "rot": {"spine_02": {"twist": -8}, "head": {"twist": -34}},
            "aim": {"upperarm_l": [0.18, -0.18, -0.96], "lowerarm_l": [0.08, -0.22, -0.96],
                    "upperarm_r": [-0.22, -0.22, -0.94], "lowerarm_r": [0.35, -0.35, -0.85],
                    "thigh_l": [0.12, 0.24, -1], "calf_l": [0.05, -0.16, -1],
                    "thigh_r": [-0.08, -0.06, -1], "calf_r": [-0.04, 0, -1]},
            "fingers": {"l": "fist", "r": "grip"},
        },
        "hit": {
            "root": {"twist": 74, "pitch": -4},
            "rot": {"spine_02": {"twist": -14, "pitch": -4}, "spine_03": {"twist": -12, "pitch": -6},
                    "neck_01": {"twist": -18}, "head": {"twist": -28, "pitch": -4}},
            "aim": {"upperarm_l": [0.14, -0.26, -0.95], "lowerarm_l": [-0.12, -0.32, -0.94],
                    "upperarm_r": [-0.18, -0.34, -0.92], "lowerarm_r": [0.62, -0.42, -0.66],
                    "thigh_l": [0.14, 0.36, -1], "calf_l": [0.06, -0.30, -1],
                    "thigh_r": [-0.10, -0.10, -1], "calf_r": [-0.05, 0, -1]},
            "fingers": {"l": "fist", "r": "grip"},
        },
        "peak": {
            "root": {"twist": 78, "pitch": -5},
            "rot": {"spine_02": {"twist": -16, "pitch": -5}, "spine_03": {"twist": -14, "pitch": -8},
                    "neck_01": {"twist": -20}, "head": {"twist": -28, "pitch": -5}},
            "aim": {"upperarm_l": [0.12, -0.30, -0.94], "lowerarm_l": [-0.16, -0.36, -0.92],
                    "upperarm_r": [-0.16, -0.38, -0.90], "lowerarm_r": [0.66, -0.44, -0.60],
                    "thigh_l": [0.15, 0.38, -1], "calf_l": [0.06, -0.32, -1],
                    "thigh_r": [-0.10, -0.10, -1], "calf_r": [-0.05, 0, -1]},
            "fingers": {"l": "fist", "r": "grip"},
        },
    },
    "pose_back_double_biceps": {
        "label": "백 더블 바이셉스 (Back Double Biceps)",
        "setup": {
            "root": {"twist": 100, "pitch": -2},
            "rot": {"spine_02": {"pitch": -4}},
            "sym": {"upperarm": [0.75, 0.05, -0.25], "lowerarm": [0.35, 0.15, 0.65]},
            "aim": {"thigh_l": [0.14, 0.06, -1], "calf_l": [0.08, 0, -1],
                    "thigh_r": [-0.14, -0.22, -1], "calf_r": [-0.08, -0.32, -1]},
            "fingers": {"l": "fist", "r": "fist"},
        },
        "hit": {
            "root": {"twist": 180, "pitch": -8},
            "rot": {"spine_02": {"pitch": -7}, "spine_03": {"pitch": -10}, "head": {"pitch": -10},
                    "clavicle_l": {"side": 6}, "clavicle_r": {"side": -6}},
            "sym": {"upperarm": [1.0, -0.05, 0.20], "lowerarm": [-0.14, 0.05, 1.0]},
            "aim": {"thigh_l": [0.18, 0.10, -1], "calf_l": [0.10, 0.02, -1],
                    "thigh_r": [-0.18, -0.32, -1], "calf_r": [-0.10, -0.46, -1]},
            "fingers": {"l": "fist", "r": "fist"},
        },
        "peak": {
            "root": {"twist": 180, "pitch": -10},
            "rot": {"spine_02": {"pitch": -8}, "spine_03": {"pitch": -12}, "head": {"pitch": -12},
                    "clavicle_l": {"side": 8}, "clavicle_r": {"side": -8}},
            "sym": {"upperarm": [1.0, -0.08, 0.26], "lowerarm": [-0.20, 0.05, 1.0]},
            "aim": {"thigh_l": [0.19, 0.10, -1], "calf_l": [0.10, 0.02, -1],
                    "thigh_r": [-0.18, -0.34, -1], "calf_r": [-0.10, -0.50, -1]},
            "fingers": {"l": "fist", "r": "fist"},
        },
    },
    "pose_back_lat_spread": {
        "label": "백 랫 스프레드 (Back Lat Spread)",
        "setup": {
            "root": {"twist": 100, "pitch": 0},
            "rot": {"clavicle_l": {"twist": 12}, "clavicle_r": {"twist": -12}},
            "sym": {"upperarm": [0.72, 0.05, -0.65], "lowerarm": [-0.58, 0.18, -0.72]},
            "aim": {"thigh_l": [0.14, 0.06, -1], "calf_l": [0.08, 0, -1],
                    "thigh_r": [-0.14, -0.22, -1], "calf_r": [-0.08, -0.32, -1]},
            "fingers": {"l": "fist", "r": "fist"},
        },
        "hit": {
            "root": {"twist": 180, "pitch": -5},
            "rot": {"spine_02": {"pitch": -5}, "spine_03": {"pitch": -6}, "head": {"pitch": -6},
                    "clavicle_l": {"twist": 20, "side": 4}, "clavicle_r": {"twist": -20, "side": -4}},
            "sym": {"upperarm": [0.96, 0.18, -0.38], "lowerarm": [-0.88, 0.25, -0.44]},
            "aim": {"thigh_l": [0.18, 0.10, -1], "calf_l": [0.10, 0.02, -1],
                    "thigh_r": [-0.18, -0.32, -1], "calf_r": [-0.10, -0.46, -1]},
            "fingers": {"l": "fist", "r": "fist"},
        },
        "peak": {
            "root": {"twist": 180, "pitch": -7},
            "rot": {"spine_02": {"pitch": -6}, "spine_03": {"pitch": -8}, "head": {"pitch": -8},
                    "clavicle_l": {"twist": 24, "side": 5}, "clavicle_r": {"twist": -24, "side": -5}},
            "sym": {"upperarm": [1.0, 0.22, -0.32], "lowerarm": [-0.92, 0.26, -0.38]},
            "aim": {"thigh_l": [0.19, 0.10, -1], "calf_l": [0.10, 0.02, -1],
                    "thigh_r": [-0.18, -0.34, -1], "calf_r": [-0.10, -0.50, -1]},
            "fingers": {"l": "fist", "r": "fist"},
        },
    },
    "pose_abs_and_thigh": {
        "label": "앱스 앤 타이 (Abdominal & Thigh)",
        "setup": {
            "root": {"pitch": 3},
            "rot": {"spine_02": {"pitch": 6}},
            "sym": {"upperarm": [0.75, 0.15, 0.55], "lowerarm": [-0.45, -0.10, 0.85]},
            "aim": {"thigh_r": [-0.14, 0.28, -1], "calf_r": [-0.08, 0.12, -1],
                    "thigh_l": [0.14, -0.06, -1], "calf_l": [0.08, 0, -1]},
            "fingers": {"l": "grip", "r": "grip"},
        },
        "hit": {
            "root": {"pitch": 6},
            "rot": {"spine_01": {"pitch": 8}, "spine_02": {"pitch": 12}, "spine_03": {"pitch": 10},
                    "neck_01": {"pitch": -8}, "head": {"pitch": -14}},
            "sym": {"upperarm": [0.78, 0.06, 0.62], "lowerarm": [-0.94, -0.22, 0.18]},
            "aim": {"thigh_r": [-0.16, 0.42, -1], "calf_r": [-0.10, 0.18, -1],
                    "thigh_l": [0.16, -0.10, -1], "calf_l": [0.09, 0, -1]},
            "fingers": {"l": "grip", "r": "grip"},
        },
        "peak": {
            "root": {"pitch": 8},
            "rot": {"spine_01": {"pitch": 10}, "spine_02": {"pitch": 15}, "spine_03": {"pitch": 12},
                    "neck_01": {"pitch": -10}, "head": {"pitch": -16}},
            "sym": {"upperarm": [0.76, 0.05, 0.64], "lowerarm": [-0.96, -0.24, 0.14]},
            "aim": {"thigh_r": [-0.17, 0.45, -1], "calf_r": [-0.10, 0.20, -1],
                    "thigh_l": [0.16, -0.10, -1], "calf_l": [0.09, 0, -1]},
            "fingers": {"l": "grip", "r": "grip"},
        },
    },
    "pose_most_muscular": {
        "label": "모스트 머스큘러 (Most Muscular - Crab)",
        "setup": {
            "root": {"pitch": 6},
            "rot": {"spine_02": {"pitch": 8}, "clavicle_l": {"twist": 14, "side": 6}, "clavicle_r": {"twist": -14, "side": -6}},
            "sym": {"upperarm": [0.65, 0.35, -0.68], "lowerarm": [-0.45, 0.75, -0.45],
                    "thigh": [0.22, 0.18, -1], "calf": [0.14, -0.10, -1]},
            "fingers": {"l": "fist", "r": "fist"},
        },
        "hit": {
            "root": {"pitch": 12},
            "rot": {"spine_01": {"pitch": 8}, "spine_02": {"pitch": 12}, "spine_03": {"pitch": 10},
                    "neck_01": {"pitch": -10}, "head": {"pitch": -16},
                    "clavicle_l": {"twist": 24, "side": 10}, "clavicle_r": {"twist": -24, "side": -10}},
            "sym": {"upperarm": [0.62, 0.58, -0.54], "lowerarm": [-0.72, 0.62, -0.32],
                    "thigh": [0.28, 0.32, -1], "calf": [0.16, -0.22, -1]},
            "fingers": {"l": "fist", "r": "fist"},
        },
        "peak": {
            "root": {"pitch": 14},
            "rot": {"spine_01": {"pitch": 10}, "spine_02": {"pitch": 14}, "spine_03": {"pitch": 12},
                    "neck_01": {"pitch": -12}, "head": {"pitch": -18},
                    "clavicle_l": {"twist": 28, "side": 12}, "clavicle_r": {"twist": -28, "side": -12}},
            "sym": {"upperarm": [0.58, 0.64, -0.50], "lowerarm": [-0.78, 0.56, -0.28],
                    "thigh": [0.30, 0.36, -1], "calf": [0.17, -0.26, -1]},
            "fingers": {"l": "fist", "r": "fist"},
        },
    },
}


# ------------------------------------------------------------------ V5 Rig Solver (mirrors bake_poses.py)

def wdir(v):
    x, f, z = v
    return Vector((x, -f, z)).normalized()


def expand_spec(spec):
    s = dict(spec)
    aim = dict(s.get("aim", {}))
    for b, d in s.get("sym", {}).items():
        aim.setdefault(b + "_l", d)
        aim.setdefault(b + "_r", [-d[0], d[1], d[2]])
    s["aim"] = aim
    s.pop("sym", None)
    return s


def world_rot(pb, R3):
    M = pb.matrix.copy()
    h = M.translation.copy()
    pb.matrix = Matrix.Translation(h) @ R3.to_4x4() @ Matrix.Translation(-h) @ M
    bpy.context.view_layer.update()


def rot_from(r):
    q = Quaternion()
    for k in ("twist", "side", "pitch"):
        if k in r:
            q = Quaternion(AX[k], math.radians(r[k])) @ q
    return q.to_matrix()


def aim_bone(pb, d):
    cur = pb.matrix.to_3x3().col[1].normalized()
    world_rot(pb, cur.rotation_difference(d).to_matrix())


def body_of(arm):
    return next(o for o in arm.children if o.type == "MESH" and any(m.type == "ARMATURE" for m in o.modifiers))


def mesh_min_z(arm):
    body = body_of(arm)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg)
    me = ev.to_mesh()
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    ev.to_mesh_clear()
    co = co.reshape(-1, 3)
    M = np.array(body.matrix_world, dtype=np.float32)
    return float((co @ M[:3, :3].T + M[:3, 3])[:, 2].min())


def solve_pose(arm, spec):
    """Solve a pose spec on the V5 52-bone rig and return {bone_name: (loc_tuple, quat_tuple)}."""
    s = expand_spec(spec)
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.scale = (1, 1, 1)
    bpy.context.view_layer.update()
    feet_rest = {n: arm.pose.bones[n].matrix.to_3x3().copy() for n in ("foot_l", "foot_r") if n in arm.pose.bones}

    # Root orientation
    root_pb = arm.pose.bones.get("pelvis") or arm.pose.bones[0]
    if "root" in s:
        r = {k: v for k, v in s["root"].items() if k != "lift"}
        if r:
            world_rot(root_pb, rot_from(r))

    # Spine / head / clavicle rotations
    for bn in ORDER_ROT:
        if bn in s.get("rot", {}):
            pb = arm.pose.bones.get(bn)
            if pb:
                world_rot(pb, rot_from(s["rot"][bn]))

    # Limbs aim (rotated by root twist so [x, f, z] is always in the character's own facing frame!)
    root_twist_deg = s.get("root", {}).get("twist", 0.0)
    twist_q = Quaternion(Vector((0, 0, 1)), math.radians(root_twist_deg))
    for bn in ORDER_AIM:
        if bn in s.get("aim", {}):
            pb = arm.pose.bones.get(bn)
            if pb:
                aim_bone(pb, (twist_q @ wdir(s["aim"][bn])).normalized())

    # Keep feet 100% flat on the floor using the V5 rig's exact rest foot orientation (matching bake_poses.py)
    if s.get("feet", "flat") == "flat":
        twist_m = twist_q.to_matrix()
        for fn, rest_m in feet_rest.items():
            fp = arm.pose.bones.get(fn)
            if fp:
                cur_m = fp.matrix.to_3x3()
                tgt_m = twist_m @ rest_m
                world_rot(fp, tgt_m @ cur_m.inverted())

    # Finger curls
    for side, style in s.get("fingers", {}).items():
        degs = CURL.get(style, CURL["relax"])
        for f in FINGERS:
            for idx, deg in enumerate(degs, 1):
                pb = arm.pose.bones.get(f"{f}_0{idx}_{side}")
                if pb:
                    # Curl is -X on both hands of this rig (measured in bake_poses.curl_fingers); Z bent them sideways.
                    pb.rotation_quaternion = Quaternion(Vector((1, 0, 0)), math.radians(-deg))
        th = arm.pose.bones.get(f"thumb_02_{side}")
        if th and style in ("fist", "grip"):
            th.rotation_quaternion = Quaternion(Vector((1, 0, 0)), math.radians(-40))
    bpy.context.view_layer.update()

    # Ground lowest vertex to z = 0
    if s.get("ground", True):
        dz = -mesh_min_z(arm)
        M_inv = arm.matrix_world.inverted().to_3x3()
        root_pb.location += M_inv @ Vector((0, 0, dz))
        bpy.context.view_layer.update()

    out = {}
    for pb in arm.pose.bones:
        out[pb.name] = (tuple(pb.location), tuple(pb.rotation_quaternion))
    return out


def build_action(arm, action_name, keyframe_poses):
    """Create a smooth 90-frame Bezier Action with quaternion hemisphere continuity on the V5 rig."""
    act = bpy.data.actions.new(name=action_name)
    act.use_fake_user = True
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = act

    prev_q = {}
    for frame, pose_dict in keyframe_poses:
        for bn, (loc, q_tup) in pose_dict.items():
            pb = arm.pose.bones.get(bn)
            if not pb:
                continue
            q = Quaternion(q_tup)
            if bn in prev_q and prev_q[bn].dot(q) < 0:
                q = -q
            prev_q[bn] = q.copy()
            pb.rotation_mode = "QUATERNION"
            pb.location = loc
            pb.rotation_quaternion = q
            pb.keyframe_insert("location", frame=frame)
            pb.keyframe_insert("rotation_quaternion", frame=frame)

    # Smooth Bezier easing on all F-curves
    fcurves = []
    if hasattr(act, "fcurves") and act.fcurves:
        fcurves = list(act.fcurves)
    elif hasattr(act, "layers"):
        for layer in act.layers:
            for strip in layer.strips:
                if hasattr(strip, "channelbags"):
                    for bag in strip.channelbags:
                        fcurves.extend(bag.fcurves)
    for fc in fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.handle_left_type = "AUTO_CLAMPED"
            kp.handle_right_type = "AUTO_CLAMPED"
    return act


def main():
    sc = W.new_scene("flat", bg="yellow", preview=False)
    sc.render.fps = FPS
    sc.frame_start = 1
    sc.frame_end = TOTAL_FRAMES

    hero = W.add_hero("V5_Posing_Base", loc=(0, 0, 0))
    stand_solved = solve_pose(hero, STAND)

    export_json = {"fps": FPS, "total_frames": TOTAL_FRAMES, "poses": {}}
    solved_peaks = {}

    for name, routine in POSING_ROUTINES.items():
        setup_s = solve_pose(hero, routine["setup"])
        hit_s = solve_pose(hero, routine["hit"])
        peak_s = solve_pose(hero, routine["peak"])
        solved_peaks[name] = peak_s

        keyframes = [
            (1, stand_solved),
            (16, setup_s),
            (32, hit_s),
            (54, peak_s),
            (72, setup_s),
            (90, stand_solved),
        ]
        build_action(hero, name, keyframes)
        export_json["poses"][name] = {
            "label": routine["label"],
            "keyframes": [{"frame": fr, "bones": {bn: {"loc": list(v[0]), "quat": list(v[1])} for bn, v in pd.items()}}
                          for fr, pd in keyframes],
        }

    # Set default active action to Front Double Biceps at peak frame 45
    hero.animation_data.action = bpy.data.actions["pose_front_double_biceps"]
    sc.frame_set(45)

    blend_out = os.path.join(ROOT, "poses", "posing_animations.blend")
    json_out = os.path.join(ROOT, "poses", "posing_animations.json")
    W.save(blend_out)
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(export_json, f, ensure_ascii=False)

    if "--no-render" in sys.argv:
        print("@@POSING_OK@@", blend_out, json_out)
        return
    # Render a clean 7-pose lineup contact sheet on V5 base model for visual verification!
    sc_sheet = W.new_scene("flat", bg="yellow", preview=False)
    sc_sheet.render.resolution_x, sc_sheet.render.resolution_y = 1920, 720
    sc_sheet.render.resolution_percentage = 100
    names = list(POSING_ROUTINES.keys())
    spacing = 1.25
    x0 = -spacing * (len(names) - 1) / 2
    for idx, name in enumerate(names):
        h = W.add_hero(f"V5_{name}", loc=(x0 + idx * spacing, 0, 0))
        pd = solved_peaks[name]
        for bn, (loc, q_tup) in pd.items():
            pb = h.pose.bones.get(bn)
            if pb:
                pb.rotation_mode = "QUATERNION"
                pb.location = loc
                pb.rotation_quaternion = q_tup
    bpy.context.view_layer.update()
    cam = sc_sheet.camera
    cam.location = (0, -9.2, 1.15)
    W.look_at(cam, (0, 0, 0.98))
    cam.data.lens = 25
    sheet_out = os.path.join(ROOT, "renders", "posing_sheet.png")
    W.render_still(sheet_out)
    print("@@POSING_OK@@", blend_out, json_out, sheet_out)


if __name__ == "__main__":
    main()
