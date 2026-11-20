"""Bake poses/pose_spec.py -> poses/pose_library.json + poses/poses.blend (Pose assets) and render pose sheets.

Run: Blender -b --factory-startup -P tools/bake_poses.py -- [--only name,name] [--no-render] [--angle front|three|side]
"""
import importlib.util
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wc_lib as W  # noqa: E402

ROOT = W.ROOT
spec_path = os.path.join(ROOT, "poses", "pose_spec.py")
sp = importlib.util.spec_from_file_location("pose_spec", spec_path)
PS = importlib.util.module_from_spec(sp)
sp.loader.exec_module(PS)

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ONLY = None
RENDER = "--no-render" not in argv
if "--only" in argv:
    ONLY = argv[argv.index("--only") + 1].split(",")

AX = {"pitch": Vector((1, 0, 0)), "side": Vector((0, 1, 0)), "twist": Vector((0, 0, 1))}
ORDER_ROT = ["spine_01", "spine_02", "spine_03", "neck_01", "head", "clavicle_l", "clavicle_r"]
ORDER_AIM = ["upperarm_l", "lowerarm_l", "upperarm_r", "lowerarm_r", "thigh_l", "calf_l", "thigh_r", "calf_r"]
FINGERS = ["index", "middle", "ring", "pinky"]
CURL = {"fist": (75, 95, 60), "relax": (14, 22, 14), "open": (0, 0, 0), "grip": (45, 60, 40), "point": (75, 95, 60)}


def wdir(v):
    x, f, z = v
    return Vector((x, -f, z)).normalized()


def mirror_name(n):
    return n[:-2] + ("_r" if n.endswith("_l") else "_l") if n.endswith(("_l", "_r")) else n


def resolve(name, seen=()):
    s = dict(PS.P[name])
    if "mirror" in s:
        src = resolve(s["mirror"])
        m = {"desc": s.get("desc", src.get("desc"))}
        for k in ("feet", "ground"):
            if k in src:
                m[k] = src[k]
        if "root" in src:
            m["root"] = {k: (-v if k in ("side", "twist") else v) for k, v in src["root"].items()}
        for key in ("rot", "rot_after"):
            if key in src:
                m[key] = {mirror_name(b): {k: (-v if k in ("side", "twist") else v) for k, v in r.items()} for b, r in src[key].items()}
        if "aim" in src:
            m["aim"] = {mirror_name(b): [-d[0], d[1], d[2]] for b, d in src["aim"].items()}
        if "fingers" in src:
            m["fingers"] = {("r" if k == "l" else "l"): v for k, v in src["fingers"].items()}
        return m
    if "base" in s:
        b = resolve(s["base"])
        out = dict(b)
        for k, v in s.items():
            if isinstance(v, dict) and isinstance(b.get(k), dict):
                nv = dict(b[k])
                nv.update(v)
                out[k] = nv
            else:
                out[k] = v
        out.pop("base", None)
        s = out
    # expand sym
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
    R = R3.to_4x4()
    pb.matrix = Matrix.Translation(h) @ R @ Matrix.Translation(-h) @ M
    bpy.context.view_layer.update()


def rot_from(r):
    q = Quaternion()
    for k in ("twist", "side", "pitch"):  # yaw, then lean, then pitch
        if k in r:
            q = Quaternion(AX[k], math.radians(r[k])) @ q
    return q.to_matrix()


def aim(pb, d):
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
    mw = np.array(body.matrix_world)
    z = co @ mw[2, :3] + mw[2, 3]
    return float(z.min())


def palm_dir(arm, side):
    B = arm.data.bones
    L = B["index_01_" + side].head_local - B["pinky_01_" + side].head_local
    F = (B["middle_01_" + side].tail_local - B["middle_01_" + side].head_local).normalized()
    D = L.cross(F).normalized()
    # This cross product is the back of the hand on the left side and the palm on the right. The thumb sits on
    # the palm side, so flip D to that side; with the back of the hand here the left fingers curled backwards.
    thumb = B["thumb_03_" + side].tail_local - (B["index_01_" + side].head_local + B["pinky_01_" + side].head_local) / 2
    return D if thumb.dot(D) > 0 else -D


def curl_fingers(arm, side, mode):
    if mode == "open":
        return
    a = CURL[mode]
    # pick the curl sign once per side: curl must move the finger tip towards the palm side
    pbs = arm.pose.bones
    base = pbs["hand_" + side].matrix.to_3x3()
    rest_hand = arm.data.bones["hand_" + side].matrix_local.to_3x3()
    palm = (base @ rest_hand.inverted()) @ palm_dir(arm, side)
    tip0 = pbs["middle_03_" + side].tail.copy()
    sign = 1
    for s in (1, -1):
        for i in range(3):
            pbs["middle_0%d_%s" % (i + 1, side)].rotation_quaternion = Quaternion((1, 0, 0), math.radians(s * 40))
        bpy.context.view_layer.update()
        mv = (pbs["middle_03_" + side].tail - tip0).dot(palm)
        if s == 1:
            m1 = mv
        else:
            sign = 1 if m1 > mv else -1
    # the 'back of hand' cross product flips on the right hand: decide with the measured motion, not with a constant
    for fi in FINGERS:
        ang = (0, 0, 0) if (mode == "point" and fi == "index") else a
        for i in range(3):
            pbs["%s_0%d_%s" % (fi, i + 1, side)].rotation_quaternion = Quaternion((1, 0, 0), math.radians(sign * ang[i]))
    # thumb: half curl
    tc = {"fist": 30, "grip": 25, "point": 30, "relax": 8}.get(mode, 0)
    for i in range(2, 4):
        pbs["thumb_0%d_%s" % (i, side)].rotation_quaternion = Quaternion((1, 0, 0), math.radians(sign * tc))
    bpy.context.view_layer.update()
    return sign


def build_pose(arm, s):
    W.rest(arm)
    bpy.context.view_layer.update()
    pbs = arm.pose.bones
    feet_rest = {n: pbs[n].matrix.to_3x3() for n in ("foot_l", "foot_r")}
    r = s.get("root", {})
    Rroot = rot_from(r)
    world_rot(pbs["pelvis"], Rroot)
    for b in ORDER_ROT:
        if b in s.get("rot", {}):
            world_rot(pbs[b], rot_from(s["rot"][b]))
    for b in ORDER_AIM:
        if b in s.get("aim", {}):
            aim(pbs[b], wdir(s["aim"][b]))
    for b, rr in s.get("rot", {}).items():
        if b not in ORDER_ROT:
            world_rot(pbs[b], rot_from(rr))
    if s.get("feet", "flat") == "flat":
        for n in ("foot_l", "foot_r"):
            cur = pbs[n].matrix.to_3x3()
            tgt = Rroot.to_3x3() @ feet_rest[n] if False else feet_rest[n]
            if "twist" in r:
                tgt = Quaternion(AX["twist"], math.radians(r["twist"])).to_matrix() @ feet_rest[n]
            world_rot(pbs[n], tgt @ cur.inverted())
    for b, rr in s.get("rot_after", {}).items():
        world_rot(pbs[b], rot_from(rr))
    signs = {}
    for side, mode in s.get("fingers", {}).items():
        signs[side] = curl_fingers(arm, side, mode)
    # grounding
    M = pbs["pelvis"].matrix.copy()
    if s.get("ground", True):
        M.translation.z -= mesh_min_z(arm)
    M.translation.z += r.get("lift", 0.0)
    pbs["pelvis"].matrix = M
    bpy.context.view_layer.update()
    return signs


def capture(arm):
    out = {}
    for pb in arm.pose.bones:
        q = pb.rotation_quaternion
        l = pb.location
        if pb.name == "pelvis" or abs(q.w) < 0.99999 or l.length > 1e-6:
            out[pb.name] = [[round(x, 5) for x in l], [round(x, 6) for x in q]]
    return out


def main():
    W.new_scene("flat", bg="gray", preview=True)
    arm = W.add_hero("Guy")
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
    names = list(PS.P.keys())
    lib_path = W.POSE_LIB
    lib = {"version": 1, "rig": "52-bone WatchCoach rig (V5_CommonRig == Fig.rig rest)", "poses": {}}
    if os.path.exists(lib_path) and ONLY:
        with open(lib_path) as f:
            lib = json.load(f)
    report = {}
    for n in names:
        if ONLY and n not in ONLY:
            continue
        s = resolve(n)
        signs = build_pose(arm, s)
        lib["poses"][n] = {"desc": s.get("desc", ""), "grounded": s.get("ground", True), "bones": capture(arm)}
        report[n] = {"min_z": round(mesh_min_z(arm), 4), "finger_sign": signs}
    with open(lib_path, "w") as f:
        json.dump(lib, f, ensure_ascii=False, indent=1)
    print("@@JSON@@" + json.dumps({"poses": len(lib["poses"]), "report": report}, ensure_ascii=False))
    W._LIB = None
    if RENDER:
        render_sheet(arm, [n for n in lib["poses"] if not ONLY or n in ONLY])
    save_blend(lib)


def save_blend(lib):
    """poses.blend: hero + one Action per pose marked as a Pose asset (Blender pose library)."""
    W.new_scene("flat", bg="gray", preview=True)
    arm = W.add_hero("Guy")
    W.pose_lib(reload=True)
    for n in lib["poses"]:
        W.rest(arm)
        if arm.animation_data and arm.animation_data.action:
            arm.animation_data.action = None
        W.key_pose(arm, n, 1)
        act = arm.animation_data.action
        act.name = "PO_" + n
        act.use_fake_user = True
        try:
            act.asset_mark()
            act.asset_data.description = lib["poses"][n]["desc"]
        except Exception:
            pass
        arm.animation_data.action = None
    W.rest(arm)
    W.save(os.path.join(ROOT, "poses", "poses.blend"))


def render_sheet(arm, names, cols=6):
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
    sc.render.resolution_percentage = 25
    cams = {"three": ((3.4, -5.0, 1.35), (0, 0, 0.8)), "front": ((0, -6.0, 1.25), (0, 0, 0.85)), "side": ((6.0, 0, 1.25), (0, 0, 0.85))}
    tmp = os.path.join(ROOT, "renders", "_pose_tmp")
    os.makedirs(tmp, exist_ok=True)
    for view in ("three", "side"):
        cam = W.use_camera("Cam_Front")
        cam.location, tgt = cams[view]
        W.look_at(cam, tgt)
        cam.data.lens = 55
        tiles = []
        for n in names:
            W.apply_pose(arm, n)
            p = W.render_still(os.path.join(tmp, f"{view}_{n}.png"))
            tiles.append((n, p))
        grid(tiles, os.path.join(ROOT, "renders", f"pose_sheet_{view}.png"), cols)


def grid(tiles, out, cols):
    imgs = []
    for n, p in tiles:
        im = bpy.data.images.load(p)
        w, h = im.size
        a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
        imgs.append(a)
        bpy.data.images.remove(im)
    h, w = imgs[0].shape[:2]
    rows = (len(imgs) + cols - 1) // cols
    big = np.ones((rows * h, cols * w, 4), dtype=np.float32)
    for i, a in enumerate(imgs):
        r, c = divmod(i, cols)
        big[(rows - 1 - r) * h:(rows - r) * h, c * w:(c + 1) * w] = a
    im = bpy.data.images.new("sheet", cols * w, rows * h, alpha=True)
    im.pixels[:] = big.ravel()
    im.filepath_raw = out
    im.file_format = "PNG"
    im.save()
    # label file
    with open(out.replace(".png", ".txt"), "w") as f:
        for i, (n, _) in enumerate(tiles):
            f.write(f"{i // cols},{i % cols}: {n}\n")


main()
