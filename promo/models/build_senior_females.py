"""Build two senior Korean female low-poly characters derived from src_figure_copy.blend
(same 1,844-vert / 1,508-poly body topology and 52-bone V6-compatible rig as extra_female.blend):

  1. promo/models/extra_ajumma.blend  — Late-50s Korean ajumma (~157 cm)
     - Slight age softening, fuller waist & realistic lower-belly protrusion,
       slightly lower/softer bust, slightly fuller upper arms.
     - Low-poly Korean ajumma bob haircut (`Extra_ajumma_Hair`) bone-parented to `head`.

  2. promo/models/extra_grandma.blend — 70s Korean grandmother (~150 cm stooped, ~155 cm straight)
     - Smaller, thinner elderly frame (slimmer limbs, flatter/lower bust & glutes),
       natural kyphotic stoop + forward head baked cleanly into rest pose & armature
       so standing height is ~150 cm while all 52 bones stay pose-compatible.
     - Low-poly curly perm hair (`Extra_grandma_Hair`, 뽀글머리) bone-parented to `head`.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 \
      -P promo/models/build_senior_females.py
"""

import json
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_FIG = os.path.join(REPO_ROOT, "promo", "cast", "src_figure_copy.blend")
EXTRA_FEMALE_BLEND = os.path.join(REPO_ROOT, "promo", "models", "extra_female.blend")
OUT_AJUMMA = os.path.join(REPO_ROOT, "promo", "models", "extra_ajumma.blend")
OUT_GRANDMA = os.path.join(REPO_ROOT, "promo", "models", "extra_grandma.blend")
RENDER_DIR = os.path.join(REPO_ROOT, "work", "senior_females_review")

TORSO_BONES = {"pelvis", "spine_01", "spine_02", "spine_03"}
HEAD_BONES = {"head"}
NECK_BONES = {"neck_01"}
LEG_L_BONES = {"thigh_l", "calf_l", "foot_l", "ball_l"}
LEG_R_BONES = {"thigh_r", "calf_r", "foot_r", "ball_r"}


def gauss(x, mu, sigma):
    return math.exp(-0.5 * ((x - mu) / sigma) ** 2)


def smoothstep(edge0, edge1, x):
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def vertex_group_weights(obj):
    idx_to_name = {vg.index: vg.name for vg in obj.vertex_groups}
    out = []
    for v in obj.data.vertices:
        w = {}
        for g in v.groups:
            name = idx_to_name.get(g.group, "")
            if g.weight > 1e-4:
                w[name] = g.weight
        out.append(w)
    return out


def sum_weights(wdict, name_set):
    total = 0.0
    for k, val in wdict.items():
        if k in name_set:
            total += val
    return min(1.0, total)


def is_arm_bone(name):
    return any(
        name.startswith(p)
        for p in ("clavicle_", "upperarm_", "lowerarm_", "hand_", "thumb_", "index_", "middle_", "ring_", "pinky_")
    )


def arm_side_weight(wdict, side):
    suf = "_" + side
    total = 0.0
    for k, val in wdict.items():
        if is_arm_bone(k) and k.endswith(suf):
            total += val
    return min(1.0, total)


def make_flat_material(name, rgba, roughness=0.58):
    mat = bpy.data.materials.new(name=name)
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = roughness
    return mat


def set_flat_shading(mesh):
    for p in mesh.polygons:
        p.use_smooth = False


def assign_box_uv(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    uv_layer = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        for loop in f.loops:
            co = loop.vert.co
            if az >= ax and az >= ay:
                loop[uv_layer].uv = (co.x * 2.0 + 0.5, co.y * 2.0 + 0.5)
            elif ax >= ay:
                loop[uv_layer].uv = (co.y * 2.0 + 0.5, co.z * 2.0)
            else:
                loop[uv_layer].uv = (co.x * 2.0 + 0.5, co.z * 2.0)
    bm.to_mesh(mesh)
    bm.free()


def clear_pose(arm_obj):
    for pb in arm_obj.pose.bones:
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()


def apply_pose_as_rest_pose(arm_obj, body_obj):
    """Bake current armature pose cleanly into both body mesh vertices and armature rest bones,
    keeping exact ground contact (min_z = 0) and clean pose-compatible bone rolls."""
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()

    # 1. Capture evaluated mesh vertex positions in armature-local space
    eval_body = body_obj.evaluated_get(dg)
    eval_mesh = eval_body.to_mesh()
    inv_arm = arm_obj.matrix_world.inverted()
    mw_body = eval_body.matrix_world
    baked_cos = [(inv_arm @ (mw_body @ v.co)) for v in eval_mesh.vertices]
    eval_body.to_mesh_clear()

    # 2. Capture evaluated pose bone heads, tails, and z-axes (for roll preservation)
    pose_bone_data = {}
    for pb in arm_obj.pose.bones:
        # pb.head and pb.tail are in armature object space
        z_axis = (pb.matrix.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
        pose_bone_data[pb.name] = (pb.head.copy(), pb.tail.copy(), z_axis)

    # Compute ground shift so feet sit cleanly at Z = 0
    min_z = min(c.z for c in baked_cos)
    z_shift = Vector((0.0, 0.0, -min_z))

    # 3. Write baked vertex positions to body mesh
    body_obj.location = (0.0, 0.0, 0.0)
    body_obj.rotation_euler = (0.0, 0.0, 0.0)
    body_obj.scale = (1.0, 1.0, 1.0)
    for v, co in zip(body_obj.data.vertices, baked_cos):
        v.co = co + z_shift
    body_obj.data.update()
    set_flat_shading(body_obj.data)

    # 4. Update armature edit bones to match posed heads/tails + align roll
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = arm_obj
    arm_obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    ebones = arm_obj.data.edit_bones
    for eb in ebones:
        h, t, z_ax = pose_bone_data[eb.name]
        eb.head = h + z_shift
        eb.tail = t + z_shift
        eb.align_roll(z_ax)
    bpy.ops.object.mode_set(mode="OBJECT")
    arm_obj.select_set(False)

    # 5. Reset pose bones to identity
    clear_pose(arm_obj)


def reshape_body(arm_obj, body_obj, profile):
    """Reshape mesh + armature from src_figure_copy.blend according to age/build profile.
    profile: 'ajumma' (50s late, 157 cm) or 'grandma' (70s, 155 cm straight -> 150 cm stooped).
    """
    if body_obj.data.shape_keys is not None:
        body_obj.shape_key_clear()

    mesh = body_obj.data
    vweights = vertex_group_weights(body_obj)
    bones = arm_obj.data.bones
    bone_segs = {b.name: (b.head_local.copy(), b.tail_local.copy()) for b in bones}

    if profile == "ajumma":
        target_straight_h = 1.570
        shoulder_inward_x = 0.022   # female shoulders, slightly sturdier than 20s extra_female (0.024)
        head_sx, head_sy, head_sz = 0.89, 0.90, 0.90
        jaw_taper_amt = 0.02        # softer middle-aged jaw
        neck_slim_x, neck_slim_y = 0.12, 0.10
        upper_narrow = 0.10         # slightly fuller upper torso
        waist_taper_x = 0.02        # almost no hourglass pinch
        waist_taper_y = 0.00
        # Realistic late-50s belly & love-handles (front -Y protrusion)
        belly_push = 0.044
        belly_z, belly_sig = 1.035, 0.088
        flank_wide = 0.085          # wider waist/flanks
        # Slightly lower, softer bust
        bust_z, bust_push, bust_drop = 1.225, 0.045, 0.016
        # Fuller middle-aged hips/glutes
        hip_wide = 0.145
        glute_push = 0.036
        lback_curve = 0.008
        # Arms: slightly fuller upper arms than 20s female
        arm_slim = 0.075
        hand_slim = 0.06
        # Legs: sturdy middle-aged thighs, slightly softer ankles
        thigh_x, thigh_y = 0.115, 0.105
        calf_slim = 0.02
        ankle_slim = 0.06
    elif profile == "grandma":
        target_straight_h = 1.550   # 155 cm straight -> ~150 cm after stoop
        shoulder_inward_x = 0.032   # noticeably smaller, narrower elderly frame
        head_sx, head_sy, head_sz = 0.87, 0.88, 0.89
        jaw_taper_amt = 0.05        # thinner elderly lower face
        neck_slim_x, neck_slim_y = 0.24, 0.20
        upper_narrow = 0.19         # narrow, frail ribcage
        waist_taper_x = 0.10
        waist_taper_y = 0.08
        # Thin frame overall, just tiny soft lower tummy
        belly_push = 0.016
        belly_z, belly_sig = 1.02, 0.075
        flank_wide = -0.02
        # Lower, flatter elderly bust
        bust_z, bust_push, bust_drop = 1.195, 0.024, 0.020
        # Smaller, flatter elderly hips & glutes
        hip_wide = 0.035
        glute_push = 0.008
        lback_curve = 0.002
        # Noticeably thinner elderly arms & hands
        arm_slim = 0.26
        hand_slim = 0.12
        # Thin elderly thighs, calves, ankles
        thigh_x, thigh_y = -0.09, -0.09
        calf_slim = 0.16
        ankle_slim = 0.16
    else:
        raise ValueError(f"Unknown profile: {profile}")

    new_coords = []
    for i, v in enumerate(mesh.vertices):
        p = v.co.copy()
        w = vweights[i]

        w_head = sum_weights(w, HEAD_BONES)
        w_neck = sum_weights(w, NECK_BONES)
        w_torso = sum_weights(w, TORSO_BONES)
        w_arm_l = arm_side_weight(w, "l")
        w_arm_r = arm_side_weight(w, "r")
        w_arm = min(1.0, w_arm_l + w_arm_r)
        w_clav_l = w.get("clavicle_l", 0.0)
        w_clav_r = w.get("clavicle_r", 0.0)
        w_leg_l = sum_weights(w, LEG_L_BONES)
        w_leg_r = sum_weights(w, LEG_R_BONES)
        w_leg = min(1.0, w_leg_l + w_leg_r)

        x, y, z = p.x, p.y, p.z
        sx = 1.0 if x >= 0 else -1.0
        ax = abs(x)

        # 1. Head
        if w_head > 0.0:
            hc = Vector((0.0, -0.095, 1.625))
            rel = Vector((x, y, z)) - hc
            jaw_taper = 1.0 - jaw_taper_amt * smoothstep(1.63, 1.54, z)
            tx = hc.x + rel.x * head_sx * jaw_taper
            ty = hc.y + rel.y * head_sy
            tz = hc.z + rel.z * head_sz - 0.010
            x = x + (tx - x) * w_head
            y = y + (ty - y) * w_head
            z = z + (tz - z) * w_head

        # 2. Neck
        if w_neck > 0.0:
            nc_y = -0.085
            x *= 1.0 - neck_slim_x * w_neck
            y = nc_y + (y - nc_y) * (1.0 - neck_slim_y * w_neck)

        # 3. Torso
        body_mask = max(0.0, 1.0 - w_arm * 0.96) * (w_torso + w_leg * smoothstep(0.76, 0.96, z))
        body_mask = min(1.0, body_mask)

        if body_mask > 0.0:
            torso_cy = -0.105

            # 3a. Upper torso width
            g_upper = gauss(z, 1.36, 0.095)
            x *= 1.0 - upper_narrow * g_upper * body_mask

            # 3b. Waist & flanks
            g_waist = gauss(z, 1.11, 0.075)
            x *= 1.0 - waist_taper_x * g_waist * body_mask
            y = torso_cy + (y - torso_cy) * (1.0 - waist_taper_y * g_waist * body_mask)

            if flank_wide != 0.0:
                g_flank = gauss(z, 1.04, 0.085)
                x *= 1.0 + flank_wide * g_flank * body_mask

            # 3c. Front belly (-Y)
            front_mask = smoothstep(-0.095, -0.155, y)
            if front_mask > 0.0 and belly_push > 0.0:
                g_bz = gauss(z, belly_z, belly_sig)
                g_bx = gauss(ax, 0.0, 0.115)
                y -= belly_push * g_bz * g_bx * front_mask * body_mask
                # Slight downward hang at lower belly for ajumma
                if profile == "ajumma":
                    z -= 0.008 * gauss(z, 0.99, 0.045) * g_bx * front_mask * body_mask

            # 3d. Bust volume
            if front_mask > 0.0:
                g_bust_z = gauss(z, bust_z, 0.058)
                g_bust_x = gauss(ax, 0.072, 0.055) + 0.30 * gauss(ax, 0.0, 0.038)
                y -= bust_push * g_bust_z * g_bust_x * front_mask * body_mask
                z -= bust_drop * gauss(z, bust_z - 0.025, 0.042) * g_bust_x * front_mask * body_mask
                x += sx * 0.007 * g_bust_z * gauss(ax, 0.095, 0.040) * front_mask * body_mask

            # 3e. Pelvis & hips
            g_hip_x = gauss(z, 0.905, 0.092)
            x *= 1.0 + hip_wide * g_hip_x * body_mask

            # Rear glutes (+Y)
            rear_mask = smoothstep(-0.088, -0.015, y)
            if rear_mask > 0.0:
                g_glute_z = gauss(z, 0.885, 0.082)
                g_glute_x = gauss(ax, 0.076, 0.080) + 0.36 * gauss(ax, 0.0, 0.048)
                y += glute_push * g_glute_z * g_glute_x * rear_mask * body_mask

                g_lback = gauss(z, 1.09, 0.065)
                y -= lback_curve * g_lback * rear_mask * body_mask

                # Subtle rounded upper-back dowager pad for grandma
                if profile == "grandma":
                    g_hump = gauss(z, 1.38, 0.075) * gauss(ax, 0.0, 0.095)
                    y += 0.022 * g_hump * rear_mask * body_mask

        # 4. Arms
        if w_arm > 0.0:
            side = 1.0 if w_arm_l >= w_arm_r else -1.0
            clav_blend = smoothstep(0.035, 0.140, abs(p.x))
            shift_w = max(w_arm - (w_clav_l + w_clav_r), 0.0) + (w_clav_l + w_clav_r) * clav_blend
            x -= side * shoulder_inward_x * min(1.0, shift_w)

            arm_limb_w = (
                w.get("upperarm_l", 0.0)
                + w.get("upperarm_r", 0.0)
                + w.get("lowerarm_l", 0.0)
                + w.get("lowerarm_r", 0.0)
            )
            if arm_limb_w > 0.05:
                dom_b = max(
                    ("upperarm_l", "upperarm_r", "lowerarm_l", "lowerarm_r"),
                    key=lambda bn: w.get(bn, 0.0),
                )
                bh, bt = bone_segs[dom_b]
                seg = bt - bh
                t_proj = max(0.0, min(1.0, (p - bh).dot(seg) / max(seg.length_squared, 1e-6)))
                axis_pt = bh + seg * t_proj
                axis_pt_shifted = Vector((axis_pt.x - side * shoulder_inward_x, axis_pt.y, axis_pt.z))
                slim = arm_slim
                if dom_b.startswith("lowerarm_"):
                    slim = arm_slim - (arm_slim - hand_slim) * smoothstep(0.55, 0.95, t_proj)
                cur = Vector((x, y, z))
                radial = cur - axis_pt_shifted
                cur = axis_pt_shifted + radial * (1.0 - slim * min(1.0, arm_limb_w))
                x, y, z = cur.x, cur.y, cur.z

            hand_w = sum(
                val for bn, val in w.items()
                if bn.startswith(("hand_", "thumb_", "index_", "middle_", "ring_", "pinky_"))
            )
            if hand_w > 0.05:
                hand_b = "hand_" + ("l" if side > 0 else "r")
                wh = bone_segs[hand_b][0]
                wrist_shifted = Vector((wh.x - side * shoulder_inward_x, wh.y, wh.z))
                cur = Vector((x, y, z))
                cur = wrist_shifted + (cur - wrist_shifted) * (1.0 - hand_slim * min(1.0, hand_w))
                x, y, z = cur.x, cur.y, cur.z

        # 5. Lower body
        if w_leg > 0.05:
            dom_leg = "l" if w_leg_l >= w_leg_r else "r"
            th_h, th_t = bone_segs["thigh_" + dom_leg]
            g_thigh = gauss(z, 0.72, 0.145)
            if 0.42 <= z <= 0.94:
                t_z = max(0.0, min(1.0, (th_h.z - z) / max(th_h.z - th_t.z, 1e-6)))
                cx = th_h.x + (th_t.x - th_h.x) * t_z
                cy = th_h.y + (th_t.y - th_h.y) * t_z
                x = cx + (x - cx) * (1.0 + thigh_x * g_thigh * w_leg)
                y = cy + (y - cy) * (1.0 + thigh_y * g_thigh * w_leg)

            if calf_slim > 0.0 and 0.16 <= z <= 0.46:
                cf_h, cf_t = bone_segs["calf_" + dom_leg]
                g_calf = gauss(z, 0.31, 0.095)
                t_z = max(0.0, min(1.0, (cf_h.z - z) / max(cf_h.z - cf_t.z, 1e-6)))
                cx = cf_h.x + (cf_t.x - cf_h.x) * t_z
                cy = cf_h.y + (cf_t.y - cf_h.y) * t_z
                x = cx + (x - cx) * (1.0 - calf_slim * g_calf * w_leg)
                y = cy + (y - cy) * (1.0 - calf_slim * g_calf * w_leg)

            g_ankle = gauss(z, 0.13, 0.055)
            if g_ankle > 0.05:
                cf_h, cf_t = bone_segs["calf_" + dom_leg]
                t_z = max(0.0, min(1.0, (cf_h.z - z) / max(cf_h.z - cf_t.z, 1e-6)))
                cx = cf_h.x + (cf_t.x - cf_h.x) * t_z
                cy = cf_h.y + (cf_t.y - cf_h.y) * t_z
                x = cx + (x - cx) * (1.0 - ankle_slim * g_ankle * w_leg)
                y = cy + (y - cy) * (1.0 - ankle_slim * g_ankle * w_leg)

        new_coords.append(Vector((x, y, z)))

    # Scale cleanly to target_straight_h with feet at Z=0
    min_z = min(c.z for c in new_coords)
    max_z = max(c.z for c in new_coords)
    scale_factor = target_straight_h / (max_z - min_z)

    for i, v in enumerate(mesh.vertices):
        c = new_coords[i]
        v.co = Vector((c.x * scale_factor, c.y * scale_factor, (c.z - min_z) * scale_factor))
    mesh.update()
    set_flat_shading(mesh)

    # Sync armature bones
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = arm_obj
    arm_obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    ebones = arm_obj.data.edit_bones
    orig_rolls = {eb.name: eb.roll for eb in ebones}
    orig_hand_dirs = {
        bn: (ebones[bn].tail - ebones[bn].head).copy()
        for bn in ("hand_l", "hand_r")
        if bn in ebones
    }

    hand_scale = 1.0 - hand_slim
    for eb in ebones:
        dx = 0.0
        if is_arm_bone(eb.name):
            side = 1.0 if eb.name.endswith("_l") else -1.0
            if eb.name.startswith("clavicle_"):
                eb.tail.x -= side * shoulder_inward_x
            else:
                dx = -side * shoulder_inward_x

        h_co = Vector((eb.head.x + dx, eb.head.y, eb.head.z))
        t_co = Vector((eb.tail.x + dx, eb.tail.y, eb.tail.z))

        if eb.name.startswith(("hand_", "thumb_", "index_", "middle_", "ring_", "pinky_")):
            side = 1.0 if eb.name.endswith("_l") else -1.0
            wh = bone_segs["hand_" + ("l" if side > 0 else "r")][0]
            wrist_shifted = Vector((wh.x - side * shoulder_inward_x, wh.y, wh.z))
            h_co = wrist_shifted + (h_co - wrist_shifted) * hand_scale
            t_co = wrist_shifted + (t_co - wrist_shifted) * hand_scale

        eb.head = Vector((h_co.x * scale_factor, h_co.y * scale_factor, (h_co.z - min_z) * scale_factor))
        eb.tail = Vector((t_co.x * scale_factor, t_co.y * scale_factor, (t_co.z - min_z) * scale_factor))

        if eb.name in orig_hand_dirs:
            eb.tail = eb.head + orig_hand_dirs[eb.name] * (scale_factor * hand_scale)

        if eb.name == "head":
            eb.tail.z = target_straight_h

    for eb in ebones:
        eb.roll = orig_rolls[eb.name]

    bpy.ops.object.mode_set(mode="OBJECT")
    arm_obj.select_set(False)
    clear_pose(arm_obj)

    straight_zs = [v.co.z for v in mesh.vertices]
    print(f"[{profile}] straight height = {max(straight_zs) - min(straight_zs):.4f} m")

    # Apply subtle age posture (ajumma) or distinct elderly kyphotic stoop (grandma)
    if profile == "ajumma":
        # Very subtle middle-aged upper-back rounding (~5 deg total), head stays level
        rot_world_bone(arm_obj, "spine_02", Vector((1, 0, 0)), math.radians(3.0))
        rot_world_bone(arm_obj, "spine_03", Vector((1, 0, 0)), math.radians(2.5))
        rot_world_bone(arm_obj, "neck_01", Vector((1, 0, 0)), math.radians(-2.0))
        rot_world_bone(arm_obj, "head", Vector((1, 0, 0)), math.radians(-3.5))
        apply_pose_as_rest_pose(arm_obj, body_obj)
    elif profile == "grandma":
        # Distinct 70s Korean grandma stoop — smoothly distributed so neck/chest never crease:
        # slight knee/hip settle + natural thoracic kyphosis (~25 deg) + balanced neck/head lift
        rot_world_bone(arm_obj, "pelvis", Vector((1, 0, 0)), math.radians(3.0))
        rot_world_bone(arm_obj, "thigh_l", Vector((1, 0, 0)), math.radians(-8.0))
        rot_world_bone(arm_obj, "thigh_r", Vector((1, 0, 0)), math.radians(-8.0))
        rot_world_bone(arm_obj, "calf_l", Vector((1, 0, 0)), math.radians(10.0))
        rot_world_bone(arm_obj, "calf_r", Vector((1, 0, 0)), math.radians(10.0))
        rot_world_bone(arm_obj, "foot_l", Vector((1, 0, 0)), math.radians(-5.0))
        rot_world_bone(arm_obj, "foot_r", Vector((1, 0, 0)), math.radians(-5.0))

        # Smooth upper-back kyphosis (25 deg total)
        rot_world_bone(arm_obj, "spine_01", Vector((1, 0, 0)), math.radians(5.0))
        rot_world_bone(arm_obj, "spine_02", Vector((1, 0, 0)), math.radians(10.0))
        rot_world_bone(arm_obj, "spine_03", Vector((1, 0, 0)), math.radians(10.0))

        # Shoulders subtly rounded forward; arms hang naturally down without pinching chest
        rot_world_bone(arm_obj, "clavicle_l", Vector((0, 0, 1)), math.radians(-5.0))
        rot_world_bone(arm_obj, "clavicle_r", Vector((0, 0, 1)), math.radians(5.0))
        rot_world_bone(arm_obj, "upperarm_l", Vector((1, 0, 0)), math.radians(-18.0))
        rot_world_bone(arm_obj, "upperarm_r", Vector((1, 0, 0)), math.radians(-18.0))
        rot_world_bone(arm_obj, "lowerarm_l", Vector((1, 0, 0)), math.radians(-7.0))
        rot_world_bone(arm_obj, "lowerarm_r", Vector((1, 0, 0)), math.radians(-7.0))

        # Distribute head compensation smoothly across neck_01 and head so throat stays clean
        rot_world_bone(arm_obj, "neck_01", Vector((1, 0, 0)), math.radians(-9.0))
        rot_world_bone(arm_obj, "head", Vector((1, 0, 0)), math.radians(-16.0))

        apply_pose_as_rest_pose(arm_obj, body_obj)

        # Fine-tune uniform scale slightly if needed so stooped height hits ~1.500 m cleanly
        zs = [v.co.z for v in mesh.vertices]
        cur_h = max(zs) - min(zs)
        print(f"[grandma] post-stoop height before fine-tune = {cur_h:.4f} m")
        if abs(cur_h - 1.500) > 0.006:
            adj = 1.500 / cur_h
            for v in mesh.vertices:
                v.co *= adj
            mesh.update()
            bpy.ops.object.select_all(action="DESELECT")
            bpy.context.view_layer.objects.active = arm_obj
            arm_obj.select_set(True)
            bpy.ops.object.mode_set(mode="EDIT")
            for eb in arm_obj.data.edit_bones:
                eb.head *= adj
                eb.tail *= adj
            bpy.ops.object.mode_set(mode="OBJECT")
            arm_obj.select_set(False)

    assign_box_uv(mesh)
    zs = [v.co.z for v in mesh.vertices]
    xs = [v.co.x for v in mesh.vertices]
    ys = [v.co.y for v in mesh.vertices]
    print(
        f"[{profile}] FINAL height={max(zs)-min(zs):.4f}m "
        f"X=[{min(xs):.3f},{max(xs):.3f}] Y=[{min(ys):.3f},{max(ys):.3f}] Z=[{min(zs):.3f},{max(zs):.3f}]"
    )


def rot_world_bone(arm_obj, bone_name, world_axis, angle_rad):
    """Apply an incremental rotation around a world/armature-space axis to a pose bone."""
    bpy.context.view_layer.update()
    pb = arm_obj.pose.bones[bone_name]
    pb.rotation_mode = "QUATERNION"
    # Convert world/armature axis into bone's local space
    bone_mat3 = pb.matrix.to_3x3()
    local_axis = (bone_mat3.inverted() @ world_axis).normalized()
    q_delta = Matrix.Rotation(angle_rad, 3, local_axis).to_quaternion()
    pb.rotation_quaternion = (pb.rotation_quaternion @ q_delta).normalized()
    bpy.context.view_layer.update()


def head_bounds(body_obj):
    """Return center and half-extents of the head vertices."""
    vweights = vertex_group_weights(body_obj)
    pts = [v.co.copy() for i, v in enumerate(body_obj.data.vertices) if vweights[i].get("head", 0.0) > 0.5]
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    zs = [p.z for p in pts]
    c = Vector(((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5, (min(zs) + max(zs)) * 0.5))
    r = Vector(((max(xs) - min(xs)) * 0.5, (max(ys) - min(ys)) * 0.5, (max(zs) - min(zs)) * 0.5))
    return c, r, pts


def parent_hair_to_head(arm_obj, body_obj, hair_obj):
    if body_obj.data.materials:
        hair_obj.data.materials.clear()
        hair_obj.data.materials.append(body_obj.data.materials[0])
    hair_obj.parent = arm_obj
    hair_obj.parent_type = "BONE"
    hair_obj.parent_bone = "head"
    head_bone = arm_obj.data.bones["head"]
    bone_mat = arm_obj.matrix_world @ Matrix.Translation(head_bone.tail_local) @ head_bone.matrix_local.to_3x3().to_4x4()
    hair_obj.matrix_parent_inverse = bone_mat.inverted()


def build_ajumma_bob_hair(arm_obj, body_obj):
    """Build a closed, watertight low-poly Korean late-50s ajumma bob haircut (단발)
    matching the uploaded photo references: soft crown volume, side-parted curtain framing
    around the forehead, rounded ear-to-jaw C-curl volume on both sides, full back bob."""
    hc, hr, _ = head_bounds(body_obj)

    # Build a thick, closed, watertight low-poly bob shell via voxel-remesh + decimate
    # from clean sculpted metaball/ellipsoid lobes so it has 0 z-fighting, 0 non-manifold edges,
    # and crisp, charming low-poly facets!
    tmp_objs = []

    def add_lobe(name, loc, scale, rot_deg=(0, 0, 0), sub=2):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)
        ob.location = loc
        ob.scale = scale
        ob.rotation_euler = tuple(math.radians(a) for a in rot_deg)
        bpy.context.scene.collection.objects.link(ob)
        tmp_objs.append(ob)
        return ob

    # 1. Crown / top hair dome (softly raised above skull)
    add_lobe(
        "bob_crown",
        hc + Vector((0.0, 0.008, hr.z * 0.34)),
        (hr.x * 1.24, hr.y * 1.18, hr.z * 0.84),
        rot_deg=(-6, 0, 0),
    )

    # 2. Side-parted forehead bangs (asymmetric 6:4 ajumma curtain framing, leaving face open)
    # Left (larger sweep)
    add_lobe(
        "bob_bang_l",
        hc + Vector((hr.x * 0.54, -hr.y * 0.72, hr.z * 0.64)),
        (hr.x * 0.66, hr.y * 0.42, hr.z * 0.36),
        rot_deg=(12, 16, -24),
    )
    # Right (shorter sweep)
    add_lobe(
        "bob_bang_r",
        hc + Vector((-hr.x * 0.50, -hr.y * 0.70, hr.z * 0.68)),
        (hr.x * 0.56, hr.y * 0.38, hr.z * 0.32),
        rot_deg=(10, -18, 22),
    )

    # 3. Left & Right bob curtains (upper temple -> mid cheek -> C-curl jaw volume)
    for sx in (-1.0, 1.0):
        # Upper side temple volume
        add_lobe(
            f"bob_side_hi_{sx}",
            hc + Vector((sx * hr.x * 1.02, -hr.y * 0.05, hr.z * 0.12)),
            (hr.x * 0.42, hr.y * 0.82, hr.z * 0.72),
            rot_deg=(0, sx * -10, sx * 8),
        )
        # Mid-lower ear-to-jaw fuller bob flare (signature ajumma 단발 silhouette)
        add_lobe(
            f"bob_side_mid_{sx}",
            hc + Vector((sx * hr.x * 1.08, 0.006, -hr.z * 0.48)),
            (hr.x * 0.44, hr.y * 0.78, hr.z * 0.62),
            rot_deg=(6, sx * 10, sx * -6),
        )
        # Lower jaw C-curl tuck-in tip
        add_lobe(
            f"bob_side_lo_{sx}",
            hc + Vector((sx * hr.x * 0.94, -hr.y * 0.14, -hr.z * 0.92)),
            (hr.x * 0.38, hr.y * 0.58, hr.z * 0.36),
            rot_deg=(12, sx * 22, sx * -10),
        )

    # 4. Back bob fullness (occiput + lower nape rounded bob)
    add_lobe(
        "bob_back_hi",
        hc + Vector((0.0, hr.y * 0.58, hr.z * 0.06)),
        (hr.x * 1.18, hr.y * 0.72, hr.z * 0.82),
        rot_deg=(10, 0, 0),
    )
    add_lobe(
        "bob_back_lo",
        hc + Vector((0.0, hr.y * 0.66, -hr.z * 0.62)),
        (hr.x * 1.16, hr.y * 0.62, hr.z * 0.60),
        rot_deg=(-12, 0, 0),
    )

    # Join all lobes into one object
    bpy.ops.object.select_all(action="DESELECT")
    for ob in tmp_objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = tmp_objs[0]
    bpy.ops.object.join()
    hair_obj = bpy.context.active_object
    hair_obj.name = "Extra_ajumma_Hair"
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    # Carve out front face cleanly using a smooth Boolean DIFFERENCE ellipsoid so face/eyes/nose/chin are 100% clear
    bm_cut = bmesh.new()
    bmesh.ops.create_icosphere(bm_cut, subdivisions=3, radius=1.0)
    cut_me = bpy.data.meshes.new("_bob_face_cut")
    bm_cut.to_mesh(cut_me)
    bm_cut.free()
    cut_ob = bpy.data.objects.new("_bob_face_cut", cut_me)
    # Positioned slightly forward and centered on face (below hairline, between cheeks)
    cut_ob.location = hc + Vector((0.0, -hr.y * 0.92, -hr.z * 0.24))
    cut_ob.scale = (hr.x * 0.88, hr.y * 0.98, hr.z * 0.96)
    bpy.context.scene.collection.objects.link(cut_ob)
    bpy.context.view_layer.update()

    # First remesh lobes into a unified manifold volume
    rem1 = hair_obj.modifiers.new("Remesh1", "REMESH")
    rem1.mode = "VOXEL"
    rem1.voxel_size = 0.0055
    rem1.adaptivity = 0.0
    bpy.ops.object.modifier_apply(modifier=rem1.name)

    # Subtract face opening
    bm_bool = hair_obj.modifiers.new("FaceCut", "BOOLEAN")
    bm_bool.operation = "DIFFERENCE"
    bm_bool.solver = "EXACT"
    bm_bool.object = cut_ob
    bpy.ops.object.modifier_apply(modifier=bm_bool.name)

    bpy.data.objects.remove(cut_ob, do_unlink=True)
    bpy.data.meshes.remove(cut_me)

    # Smooth & decimate into crisp low-poly bob (~350-450 tris)
    rem2 = hair_obj.modifiers.new("Remesh2", "REMESH")
    rem2.mode = "VOXEL"
    rem2.voxel_size = 0.0065
    bpy.ops.object.modifier_apply(modifier=rem2.name)

    sm = hair_obj.modifiers.new("Smooth", "SMOOTH")
    sm.factor = 0.5
    sm.iterations = 4
    bpy.ops.object.modifier_apply(modifier=sm.name)

    dec = hair_obj.modifiers.new("Decimate", "DECIMATE")
    dec.decimate_type = "COLLAPSE"
    dec.ratio = 0.045
    bpy.ops.object.modifier_apply(modifier=dec.name)

    # Final cleanup: remove doubles, recalc normals, triangulate/clean, box UV
    bm = bmesh.new()
    bm.from_mesh(hair_obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    bmesh.ops.dissolve_degenerate(bm, dist=0.0005, edges=bm.edges)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # Push any hair vertex grazing the skull surface within 2.5mm outward by 3.5mm so z-fighting is 0
    from mathutils.bvhtree import BVHTree
    dg_tmp = bpy.context.evaluated_depsgraph_get()
    bvh_body = BVHTree.FromObject(body_obj, dg_tmp)
    for v in bm.verts:
        hit_loc, hit_nrm, _, dist = bvh_body.find_nearest(v.co)
        if hit_loc is not None and dist < 0.0025:
            out_dir = (v.co - hc).normalized()
            v.co += out_dir * 0.0035
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(hair_obj.data)
    bm.free()

    hair_obj.data.name = "Extra_ajumma_Hair_Mesh"
    set_flat_shading(hair_obj.data)
    assign_box_uv(hair_obj.data)
    parent_hair_to_head(arm_obj, body_obj, hair_obj)

    print(f"[ajumma_hair] verts={len(hair_obj.data.vertices)}, polys={len(hair_obj.data.polygons)}")
    return hair_obj


def build_grandma_perm_hair(arm_obj, body_obj):
    """Build a closed, watertight low-poly Korean 70s grandmother curly perm (뽀글머리):
    fluffy rounded cluster of curls covering crown, temples, upper ears, and back of head,
    leaving the face clearly visible, remeshed & decimated to crisp low-poly."""
    hc, hr, _ = head_bounds(body_obj)
    rng = random.Random(20261127)

    tmp_objs = []

    def add_puff(name, loc, r_xyz, sub=2):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)
        ob.location = loc
        ob.scale = r_xyz
        bpy.context.scene.collection.objects.link(ob)
        tmp_objs.append(ob)

    # 1. Core rounded perm cap sitting snugly around upper/back skull (with >=3mm clearance from skull)
    add_puff(
        "perm_core",
        hc + Vector((0.0, 0.020, hr.z * 0.23)),
        (hr.x * 1.13, hr.y * 1.11, hr.z * 0.87),
    )

    # 2. Compact, dense Korean grandma curly perm curls (smaller, neater puffs, clean open face!)
    curl_idx = 0
    ring_specs = [
        # (phi_deg, n_curls, rad_mult_xy, rad_mult_z, curl_r, min_front_angle_deg)
        (0.0, 1, 0.0, 1.05, 0.024, 0.0),          # top center puff
        (26.0, 8, 1.08, 1.06, 0.024, 0.0),        # upper crown ring
        (50.0, 14, 1.14, 1.02, 0.023, 22.0),      # upper forehead hairline (leaves brow/face clear!)
        (74.0, 16, 1.18, 0.96, 0.023, 56.0),      # temple/ear ring (face fully open!)
        (96.0, 16, 1.14, 0.90, 0.022, 72.0),      # lower ear & back perm volume
        (114.0, 12, 1.02, 0.85, 0.020, 100.0),    # back nape curls
    ]

    for phi_deg, n_curls, rxy, rz_m, base_r, min_ang in ring_specs:
        phi = math.radians(phi_deg)
        for k in range(n_curls):
            theta = (2.0 * math.pi * (k + 0.35 * (curl_idx % 2)) / n_curls)
            ang_from_front = abs(math.degrees(math.atan2(math.sin(theta), math.cos(theta))))
            if ang_from_front < min_ang:
                continue

            r_j = base_r * rng.uniform(0.88, 1.12)
            dx = math.sin(phi) * math.sin(theta)
            dy = -math.sin(phi) * math.cos(theta)
            dz = math.cos(phi)

            pos = hc + Vector((
                dx * hr.x * rxy + rng.uniform(-0.003, 0.003),
                dy * hr.y * rxy + 0.010 + rng.uniform(-0.003, 0.003),
                dz * hr.z * rz_m + 0.006 + rng.uniform(-0.003, 0.003),
            ))
            add_puff(
                f"perm_c_{curl_idx}",
                pos,
                (r_j * rng.uniform(0.92, 1.08), r_j * rng.uniform(0.92, 1.08), r_j * rng.uniform(0.88, 1.06)),
                sub=2,
            )
            curl_idx += 1

    # Add a neat row of 3 tiny curled bangs right along the top forehead hairline
    for bx in (-0.032, 0.0, 0.032):
        add_puff(
            f"perm_bang_{curl_idx}",
            hc + Vector((bx, -hr.y * 0.78, hr.z * 0.76)),
            (0.021, 0.019, 0.019),
            sub=2,
        )
        curl_idx += 1

    # Join all puffs
    bpy.ops.object.select_all(action="DESELECT")
    for ob in tmp_objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = tmp_objs[0]
    bpy.ops.object.join()
    hair_obj = bpy.context.active_object
    hair_obj.name = "Extra_grandma_Hair"
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    # Voxel remesh into one watertight puffy perm volume
    rem = hair_obj.modifiers.new("Remesh", "REMESH")
    rem.mode = "VOXEL"
    rem.voxel_size = 0.0058
    bpy.ops.object.modifier_apply(modifier=rem.name)

    # Light smooth + crisp low-poly decimate
    sm = hair_obj.modifiers.new("Smooth", "SMOOTH")
    sm.factor = 0.35
    sm.iterations = 2
    bpy.ops.object.modifier_apply(modifier=sm.name)

    dec = hair_obj.modifiers.new("Decimate", "DECIMATE")
    dec.decimate_type = "COLLAPSE"
    dec.ratio = 0.060
    bpy.ops.object.modifier_apply(modifier=dec.name)

    bm = bmesh.new()
    bm.from_mesh(hair_obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    bmesh.ops.dissolve_degenerate(bm, dist=0.0005, edges=bm.edges)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # Push any hair vertex grazing the skull surface within 2.5mm outward by 3.5mm so z-fighting is 0
    from mathutils.bvhtree import BVHTree
    dg_tmp = bpy.context.evaluated_depsgraph_get()
    bvh_body = BVHTree.FromObject(body_obj, dg_tmp)
    for v in bm.verts:
        hit_loc, hit_nrm, _, dist = bvh_body.find_nearest(v.co)
        if hit_loc is not None and dist < 0.0025:
            out_dir = (v.co - hc).normalized()
            v.co += out_dir * 0.0035
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(hair_obj.data)
    bm.free()

    hair_obj.data.name = "Extra_grandma_Hair_Mesh"
    set_flat_shading(hair_obj.data)
    assign_box_uv(hair_obj.data)
    parent_hair_to_head(arm_obj, body_obj, hair_obj)

    print(f"[grandma_hair] curls={curl_idx}, verts={len(hair_obj.data.vertices)}, polys={len(hair_obj.data.polygons)}")
    return hair_obj


def build_character_blend(profile, out_blend, rgba):
    """Build standalone .blend for 'ajumma' or 'grandma' and return metrics dict."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0

    with bpy.data.libraries.load(SRC_FIG, link=False) as (src, dst):
        dst.objects = ["Fig.rig", "BASE_Low Poly Man"]
    for obj in dst.objects:
        if obj is not None:
            scene.collection.objects.link(obj)

    arm = bpy.data.objects["Fig.rig"]
    body = bpy.data.objects["BASE_Low Poly Man"]
    arm.location = (0.0, 0.0, 0.0)
    arm.rotation_euler = (0.0, 0.0, 0.0)
    arm.scale = (1.0, 1.0, 1.0)
    body.location = (0.0, 0.0, 0.0)
    body.rotation_euler = (0.0, 0.0, 0.0)
    body.scale = (1.0, 1.0, 1.0)
    clear_pose(arm)

    prefix = f"Extra_{profile}"
    arm.name = prefix
    arm.data.name = f"{prefix}_Rig"
    body.name = f"{prefix}_Body"
    body.data.name = f"{prefix}_Mesh"

    mat = make_flat_material(f"{prefix}_Mat", rgba, roughness=0.58)
    body.data.materials.clear()
    body.data.materials.append(mat)

    reshape_body(arm, body, profile)

    if profile == "ajumma":
        hair = build_ajumma_bob_hair(arm, body)
    else:
        hair = build_grandma_perm_hair(arm, body)

    clear_pose(arm)
    os.makedirs(os.path.dirname(out_blend), exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=out_blend, compress=True)

    zs = [v.co.z for v in body.data.vertices]
    hzs = [(hair.matrix_world @ v.co).z for v in hair.data.vertices]
    metrics = {
        "profile": profile,
        "out": out_blend,
        "body_height_m": round(max(zs) - min(zs), 4),
        "total_height_with_hair_m": round(max(max(zs), max(hzs)) - min(zs), 4),
        "body_verts": len(body.data.vertices),
        "body_polys": len(body.data.polygons),
        "hair_verts": len(hair.data.vertices),
        "hair_polys": len(hair.data.polygons),
        "bones": len(arm.data.bones),
    }
    print(f"BUILT_{profile.upper()}", json.dumps(metrics))
    return metrics


def render_lineup_review():
    """Render 3-way female lineup (161cm Extra_female | 157cm Ajumma | 150cm Grandma)
    from front, three-quarter, side profiles, back, and head closeup."""
    os.makedirs(RENDER_DIR, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 900
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"

    def load_char(blend_path, target_x):
        before = set(bpy.data.objects.keys())
        with bpy.data.libraries.load(blend_path, link=False) as (src, dst):
            dst.objects = list(src.objects)
        objs = []
        arm = None
        for ob in dst.objects:
            if ob is not None:
                scene.collection.objects.link(ob)
                objs.append(ob)
                if ob.type == "ARMATURE":
                    arm = ob
        if arm is not None:
            arm.location.x = target_x
        return arm, objs

    f_arm, f_objs = load_char(EXTRA_FEMALE_BLEND, -0.95)
    a_arm, a_objs = load_char(OUT_AJUMMA, 0.0)
    g_arm, g_objs = load_char(OUT_GRANDMA, 0.95)

    # Hide cap/headset on Extra_female if any exist so comparison is clean
    for ob in f_objs:
        if any(k in ob.name.lower() for k in ("cap", "headset", "gear", "airpod")):
            ob.hide_render = True
            ob.hide_viewport = True

    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    bg = next((n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND"), None)
    if bg:
        bg.inputs["Color"].default_value = (0.14, 0.16, 0.19, 1.0)
        bg.inputs["Strength"].default_value = 0.85

    def add_light(name, loc, rot_deg, energy, size=2.6):
        ldata = bpy.data.lights.new(name=name, type="AREA")
        ldata.energy = energy
        ldata.size = size
        lobj = bpy.data.objects.new(name=name, object_data=ldata)
        lobj.location = loc
        lobj.rotation_euler = tuple(math.radians(a) for a in rot_deg)
        scene.collection.objects.link(lobj)

    add_light("Key", (2.8, -3.8, 3.0), (58, 0, 34), 360, 2.5)
    add_light("Fill", (-3.2, -2.6, 2.0), (72, 0, -48), 160, 3.0)
    add_light("Rim", (0.0, 3.8, 2.6), (125, 0, 0), 280, 3.0)

    bpy.ops.mesh.primitive_plane_add(size=12.0, location=(0.0, 0.0, 0.0))
    ground = bpy.context.active_object
    ground.data.materials.append(make_flat_material("Ground", (0.20, 0.22, 0.26, 1.0)))

    # Height reference bars behind characters: 1.50m (lavender), 1.57m (coral), 1.61m (pink)
    for h_val, col in (
        (1.50, (0.72, 0.56, 0.86, 1.0)),
        (1.57, (0.94, 0.56, 0.44, 1.0)),
        (1.61, (0.95, 0.48, 0.56, 1.0)),
    ):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.55, h_val))
        bar = bpy.context.active_object
        bar.scale = (3.4, 0.008, 0.005)
        bar.data.materials.append(make_flat_material(f"Bar_{h_val}", col))

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = 65.0
    cam_obj = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    def look_at(obj, target):
        direction = Vector(target) - obj.location
        obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    def set_vis(objs, vis):
        for o in objs:
            if any(k in o.name.lower() for k in ("cap", "headset", "gear", "airpod")):
                o.hide_render = True
            else:
                o.hide_render = not vis

    views = [
        ("01_front_lineup", (0.0, -4.8, 0.85), (0.0, 0.0, 0.82), (True, True, True)),
        ("02_three_quarter", (2.6, -4.1, 0.92), (0.08, 0.0, 0.82), (True, True, True)),
        ("03_back_lineup", (0.0, 4.8, 0.85), (0.0, 0.0, 0.82), (True, True, True)),
        ("04_side_ajumma", (4.4, -0.05, 0.85), (0.0, -0.05, 0.82), (False, True, False)),
        ("05_side_grandma", (5.3, -0.08, 0.80), (0.95, -0.08, 0.78), (False, False, True)),
        ("06_head_closeup", (0.48, -2.55, 1.42), (0.48, -0.05, 1.38), (False, True, True)),
    ]

    for vname, loc, tgt, (vf, va, vg) in views:
        set_vis(f_objs, vf)
        set_vis(a_objs, va)
        set_vis(g_objs, vg)
        cam_obj.location = loc
        look_at(cam_obj, tgt)
        scene.render.filepath = os.path.join(RENDER_DIR, f"{vname}.png")
        bpy.ops.render.render(write_still=True)

    print(f"[review] Rendered 6 views to {RENDER_DIR}")


def main():
    # Ajumma: warm rose-pink (clearly in the pink female family, distinct from 20s extra_female)
    m_ajumma = build_character_blend("ajumma", OUT_AJUMMA, (0.84, 0.45, 0.54, 1.0))
    # Grandma: soft lavender-pink (pink family with gentle silver-lavender elderly tone)
    m_grandma = build_character_blend("grandma", OUT_GRANDMA, (0.78, 0.56, 0.70, 1.0))
    render_lineup_review()
    print("SUMMARY", json.dumps({"ajumma": m_ajumma, "grandma": m_grandma}, indent=2))


if __name__ == "__main__":
    main()
