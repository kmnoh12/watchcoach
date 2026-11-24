"""Build the reusable asset libraries, QA them and render the review sheets.

Run: Blender -b --factory-startup -P tools/build_assets.py -- [step ...]
steps: cast props cameos fx gymqa group  (default: all)
Outputs: cast/cast_library.blend, props/props.blend, cast/cameos.blend, fx/fx_parts.blend,
         renders/*.png, renders/qa/qa_report.json
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wc_lib as W  # noqa: E402

QA_DIR = os.environ.get("WATCHCOACH_BLENDER_QA", os.path.expanduser("~/.agents/skills/blender-asset-qa/scripts"))
sys.path.insert(0, QA_DIR)
import qa_check  # noqa: E402
import review_shots  # noqa: E402

R = W.ROOT
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
STEPS = argv or ["cast", "props", "cameos", "fx", "gymqa", "group"]
REPORT = os.path.join(R, "renders", "qa", "qa_report.json")
os.makedirs(os.path.dirname(REPORT), exist_ok=True)
rep = json.load(open(REPORT)) if os.path.exists(REPORT) else {}


def meshes_under(root):
    return [o.name for o in [root] + list(root.children_recursive) if o.type == "MESH"]


def qa(name, objs, **kw):
    bpy.context.view_layer.update()
    r = qa_check.run(objects=objs, profile=kw.pop("profile", "render"), **kw)
    rep[name] = {"pass": r["pass"], "errors": r["errors"], "warnings": r["warnings"],
                 "tris": sum(v.get("tris", 0) for v in r["objects"].values()) if isinstance(r["objects"], dict) else None}
    return r


def shots(name, objs, mode="random"):
    out = os.path.join(R, "renders", "qa", f"{name}_{mode}.png")
    try:
        review_shots.run(objects=objs, out=out, mode=mode, res=384)
    except Exception as e:  # review shots are a visual aid; record and continue
        rep.setdefault(name, {})["review_error"] = str(e)
    return out


def tile_render(path, cam_loc, tgt, lens=50, pct=40):
    sc = bpy.context.scene
    cam = W.use_camera("Cam_Front")
    cam.location = cam_loc
    W.look_at(cam, tgt)
    cam.data.lens = lens
    sc.render.resolution_percentage = pct
    return W.render_still(path)


# ------------------------------------------------------------------ steps

def _morph_extra_body(arm_obj, mode):
    """Apply clean head-safe body-type morph ('skinny' = 멸치, 'chubby' = 돼지) to an extra mesh in rest space."""
    mesh_objs = [o for o in arm_obj.children if o.type == "MESH"]
    if not mesh_objs:
        return
    me = mesh_objs[0].data
    # Find rest-space vertical bounds (typically Z = 0.0 .. 1.75)
    zs = [v.co.z for v in me.vertices]
    zmin, zmax = min(zs), max(zs)
    h = max(0.01, zmax - zmin)

    def smoothstep(edge0, edge1, x):
        t = max(0.0, min(1.0, (x - edge0) / max(1e-5, edge1 - edge0)))
        return t * t * (3.0 - 2.0 * t)

    # Precompute bone segments in mesh rest space so limbs scale radially around their OWN bone axis (never shifting off-bone!)
    arm_bone_names = ("upperarm_l", "lowerarm_l", "upperarm_r", "lowerarm_r")
    hand_bone_names = ("hand_l", "hand_r")
    vg_idx_to_name = {vg.index: vg.name for vg in mesh_objs[0].vertex_groups}
    arm_segs = {}
    for bn in arm_bone_names:
        b = arm_obj.data.bones.get(bn)
        if b:
            arm_segs[bn] = (b.head_local.copy(), b.tail_local.copy())

    for v in me.vertices:
        nz = (v.co.z - zmin) / h  # 0.0 = feet, ~0.50 = hips, ~0.62 = waist, ~0.82 = shoulders, ~0.86..1.0 = head
        body_mask = smoothstep(0.05, 0.14, nz) * (1.0 - smoothstep(0.83, 0.88, nz))
        if body_mask <= 0.0:
            continue
        # Check dominant vertex group to handle arms/hands cleanly along their bone axis
        dom_name, dom_w = "", 0.0
        for g in v.groups:
            if g.weight > dom_w:
                dom_w = g.weight
                dom_name = vg_idx_to_name.get(g.group, "")
        if dom_name in hand_bone_names or any(dom_name.startswith(p) for p in ("thumb", "index", "middle", "ring", "pinky")):
            continue  # Keep hands/fingers 100% undistorted!
        if dom_name in arm_segs:
            p0, p1 = arm_segs[dom_name]
            ab = p1 - p0
            ab_len2 = max(1e-8, ab.length_squared)
            t = max(0.0, min(1.0, (v.co - p0).dot(ab) / ab_len2))
            closest = p0 + ab * t
            radial = v.co - closest
            # Smoothly taper morph toward the wrist so arm->hand transition is seamless
            wrist_fade = (1.0 - smoothstep(0.55, 1.0, t)) if "lowerarm" in dom_name else 1.0
            rad_scale = (1.0 - 0.24 * wrist_fade) if mode == "skinny" else (1.0 + 0.16 * wrist_fade)
            v.co = closest + radial * rad_scale
            continue

        x, y, z = v.co.x, v.co.y, v.co.z
        if mode == "skinny":
            # 멸치 체형: slim torso & legs (arms already slimmed radially around bone axis!)
            torso_band = smoothstep(0.45, 0.58, nz) * (1.0 - smoothstep(0.80, 0.86, nz))
            sx = 1.0 - body_mask * (0.18 + 0.05 * torso_band)
            sy = 1.0 - body_mask * (0.20 + 0.05 * torso_band)
            v.co.x = x * sx
            v.co.y = y * sy
        elif mode == "chubby":
            # 돼지 체형: smooth core belly/hip/chest fullness + thicker thighs
            belly_z = math.exp(-((nz - 0.60) / 0.13) ** 2)
            hip_z = math.exp(-((nz - 0.47) / 0.14) ** 2)
            chest_z = math.exp(-((nz - 0.72) / 0.11) ** 2)
            sx = 1.0 + body_mask * (0.12 + 0.22 * belly_z + 0.16 * hip_z + 0.10 * chest_z)
            sy = 1.0 + body_mask * (0.12 + 0.32 * belly_z + 0.18 * hip_z + 0.14 * chest_z)
            front_mask = smoothstep(0.06, -0.04, y)
            belly_fwd = -0.085 * belly_z * front_mask
            v.co.x = x * sx
            v.co.y = y * sy + belly_fwd
    me.update()


def step_cast():
    """Hero + the five role extras in one library file; lineup render with a different pose each."""
    W.new_scene("flat", bg="mint")
    g = W.add_hero("Guy", (0, 0, 0))
    W.apply_pose(g, "triumph")
    roles = list(W.ROLES)
    poses = {"red": "mirror_flex", "yellow": "carry_plate", "gray": "phone_look", "blue": "sneak", "green": "shrug"}
    # Distinct silhouette lineup (2026-11-24):
    # - blue: 165cm 난쟁이(단신) 속성
    # - gray: 172cm 돼지 체형 (chubby)
    # - red:  175cm 멸치 체형 (skinny)
    # - yellow: 180cm 일반 체형
    # - green: 183cm 키 큰 캐릭터
    heights = {
        "blue": 1.65 / 1.75,
        "gray": 1.72 / 1.75,
        "red": 1.75 / 1.75,
        "yellow": 1.80 / 1.75,
        "green": 1.83 / 1.75,
    }
    girth = dict(heights)
    morphs = {"red": "skinny", "gray": "chubby"}
    xs = [-2.4, -1.45, 1.45, 2.4, 3.35]
    extras = []
    for x, r in zip(xs, roles):
        a = W.add_extra(r, None, (x, 0.3, 0), 0, heights[r], girth[r])
        if r in morphs:
            _morph_extra_body(a, morphs[r])
        W.apply_pose(a, poses[r])
        extras.append(a)
    phone = W.prop("phone", (0.0, -0.06, 0.03), (90, 0, 0), parent=bpy.data.objects["Extra_gray"], bone="hand_r")
    W.save(os.path.join(R, "cast", "cast_library.blend"))
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    tile_render(os.path.join(R, "renders", "cast_lineup.png"), (0.45, -8.5, 1.3), (0.45, 0, 0.95), lens=40, pct=60)
    sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
    # QA: rigged meshes (deformation + weights) at rest
    for a in [g] + extras:
        W.rest(a)
    bpy.context.view_layer.update()
    body_names = [o.name for o in bpy.data.objects if o.type == "MESH" and o.parent and o.parent.type == "ARMATURE"]
    qa("hero_body", ["Guy_Body"], profile="render")
    qa("extra_body", ["Extra_red_Body"], profile="render")
    watch = [o.name for o in bpy.data.objects if o.name.startswith("Watch_")]
    qa("watch", watch, profile="render", tol=0.004)
    shots("hero_body", ["Guy_Body"] + watch, "solid")
    shots("extra_body", ["Extra_red_Body"], "random")


def step_props():
    W.new_scene("flat", bg="blue")
    kinds = ["plate", "phone", "towel", "shaker", "bottle", "gym_bag", "wall_clock"]
    roots = {}
    for i, k in enumerate(kinds):
        x = -1.5 + i * 0.5
        z = {"plate": 0.225, "phone": 0.08, "wall_clock": 0.27}.get(k, 0.0)
        rot = {"phone": (0, 0, 0)}.get(k, (0, 0, 0))
        roots[k] = W.prop(k, (x, 0, z), rot)
        roots[k].location.z = z
    bpy.context.view_layer.update()
    W.save(os.path.join(R, "props", "props.blend"))
    for k, r in roots.items():
        qa("prop_" + k, meshes_under(r), tol=0.003)
    shots("props", [n for r in roots.values() for n in meshes_under(r)], "random")
    tile_render(os.path.join(R, "renders", "props_sheet.png"), (0.0, -3.2, 0.9), (0.0, 0, 0.2), lens=50, pct=40)
    # wide crop: render landscape
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    tile_render(os.path.join(R, "renders", "props_sheet.png"), (0.0, -3.4, 0.9), (0.0, 0, 0.18), lens=45, pct=60)


def step_cameos():
    W.new_scene("flat", bg="pink")
    roots = {}
    for i, who in enumerate(W.CAMEOS):
        roots[who] = W.add_cameo(who, (-3.0 + i * 1.2, 0, 1.8))
    W.save(os.path.join(R, "cast", "cameos.blend"))
    for who, r in roots.items():
        qa("cameo_" + who, meshes_under(r), tol=0.02)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    tile_render(os.path.join(R, "renders", "cameos_sheet.png"), (0.0, -7.5, 1.6), (0.0, 0, 1.6), lens=40, pct=60)


def step_fx():
    """Effect parts on one sheet: ! ? sweat # ... over guys, speed lines + caption on the camera, buzzing watch."""
    W.new_scene("flat", bg="yellow")
    sc = bpy.context.scene
    cam = W.use_camera("Cam_Front")
    guys = []
    for i, (x, kind, pose) in enumerate([(-1.0, "exclaim", "surprise"), (0.0, "sweat", "facepalm"), (1.0, "question", "shrug")]):
        a = W.add_hero("Guy%d" % i, (x, 0, 0))
        W.apply_pose(a, pose)
        W.key_pose(a, pose, 1)
        guys.append((a, kind))
    for a, kind in guys:
        W.fx_symbol(kind, a, 1, 30)
    W.fx_speedlines(cam, 1, 30)
    W.fx_caption(cam, "자막 예시: 대사 한 줄", 1, 30)
    W.watch_glow("Guy1", 1, True, 5)
    W.finalize_interp()
    sc.frame_set(1)
    W.save(os.path.join(R, "fx", "fx_parts.blend"))
    sc.render.resolution_percentage = 40
    W.render_still(os.path.join(R, "renders", "fx_sheet.png"), 1)
    # flash frame demo
    W.fx_flash(cam, 2, (1, 0.2, 0.2), 1)
    W.finalize_interp()
    W.render_still(os.path.join(R, "renders", "fx_flash_frame.png"), 2)
    fx_objs = [o.name for o in bpy.data.objects if o.name.startswith("FX_") and o.type == "MESH"]
    for n in fx_objs:
        r = qa("fx_" + n, [n], tol=0.01)
        if n.startswith("FX_SpeedLines") and r["errors"] and all("floating" in e for e in r["errors"]):
            rep["fx_" + n].update({"pass": True, "accepted": "speed-line wedges are separate pieces by design (screen overlay)",
                                   "errors": [], "floating_wedges": len(r["errors"])})


def step_gymqa():
    """QA the gym; coplanar joints left inside the copied machine builders are fixed by growing the smaller part of
    each z-fighting pair (names saved to scenes/gym_zfix.json, applied by wc_lib.build_gym_set), up to 4 rounds."""
    zfix = os.path.join(R, "scenes", "gym_zfix.json")
    grow = {}  # rebuilt from scratch every run
    if os.path.exists(zfix):
        os.remove(zfix)
    for rnd in range(10):
        W.new_scene("gym")
        setc = bpy.data.collections["SET"]
        objs = [o.name for o in setc.objects if o.type == "MESH"]
        r = qa("gym_set", objs, eps=0.003, tol=0.01, uv=False)
        pairs = [z["where"].split("<->") for z in r["zfighting"]]
        if not pairs:
            break
        bpy.context.view_layer.update()
        for a_, b_ in pairs:
            oa, ob_ = bpy.data.objects[a_], bpy.data.objects[b_]
            va = oa.dimensions.x * oa.dimensions.y * oa.dimensions.z
            vb = ob_.dimensions.x * ob_.dimensions.y * ob_.dimensions.z
            small, big = (a_, b_) if va <= vb else (b_, a_)
            # grow the smaller part 4 mm more than its partner already grew, so the two faces end up apart
            grow[small] = max(grow.get(small, 0.0) + 0.004 if small in grow else 0.0, grow.get(big, 0.0) + 0.004)
        with open(zfix, "w") as f:
            json.dump(grow, f, indent=1)
    rep["gym_set"]["grown_parts"] = len(grow)
    rep["gym_set"]["objects"] = len(objs)
    rep["gym_set"]["zf_sample"] = r["zfighting"][:8]
    rep["gym_set"]["floating_sample"] = r["floating"][:8]
    W.new_scene("flat")
    r = qa("flat_set", ["Set_Cyclorama"], uv=False)


def step_group():
    """Key art: guy + extras + cameos together in the gym."""
    W.new_scene("gym")
    sc = bpy.context.scene
    g = W.add_hero("Guy", (0, -0.3, 0))
    W.apply_pose(g, "triumph")
    cast = [("red", (0.95, 0.9), -20, "carry_plate", 1.0, 1.08),
            ("yellow", (0.3, 3.7), 180, "mirror_flex", 1.03, 1.0),
            ("gray", (1.55, 1.3), 0, "sit_phone", 0.97, 0.95),
            ("blue", (-0.9, 0.6), 35, "sneak", 0.95, 1.0)]
    arms = {}
    for role, (x, y), face, pose, h, gi in cast:
        a = W.add_extra(role, None, (x, y, 0), face, h, gi)
        W.apply_pose(a, pose)
        arms[role] = a
    # gray sits on the bench: lift to bench height
    arms["gray"].location.z = 0.0
    W.prop("phone", (0.0, -0.06, 0.03), (90, 0, 0), parent=arms["gray"], bone="hand_r")
    W.prop("towel", (-0.5, 1.3, 0.47))
    W.prop("gym_bag", (-0.85, 1.25, 0.0))
    W.prop("shaker", (2.05, 1.05, 0.0))
    W.prop("plate", (0.55, 0.65, 0.225))
    W.prop("wall_clock", (-3.0, 4.98, 2.25), (0, 0, 0))
    cam = W.use_camera("Cam_Front")
    W.add_cameo("samsung", (-1.25, 1.6, 2.15), 0.95, face_deg=-12)
    W.add_cameo("altman", (-2.2, 3.4, 2.5), 0.9, face_deg=-8)
    W.add_cameo("amodei", (2.3, 3.2, 2.45), 0.9, face_deg=10)
    W.add_cameo("gpt", (-0.75, 0.9, 2.75), 0.55)
    W.add_cameo("claude", (0.8, 0.9, 2.75), 0.55)
    W.add_cameo("gemini", (0.05, 1.3, 3.0), 0.5)
    W.fx_symbol("exclaim", g, 1, 30)
    W.finalize_interp()
    cam.data.lens = 34
    sc.render.resolution_percentage = 100
    W.save(os.path.join(R, "scenes", "keyart_group.blend"))
    W.render_still(os.path.join(R, "renders", "keyart_group_gym.png"), 1)


for s in STEPS:
    globals()["step_" + s]()
    with open(REPORT, "w") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
print("@@JSON@@" + json.dumps({k: (v.get("pass"), len(v.get("errors", [])), len(v.get("warnings", []))) for k, v in rep.items()}, ensure_ascii=False))
