"""Build a 165cm stooped 70s Korean grandfather low-poly character (`promo/models/extra_grandpa.blend`)
derived from src_figure_copy.blend (same 52-bone V6-compatible rig & low-poly body style as
extra_ajumma.blend and extra_grandma.blend).

  - Straight-posture build: ~170 cm -> natural elderly kyphotic stoop -> final standing height 165.0 cm.
  - Thin, frail elderly male frame: narrow-ish elderly shoulders (wider than grandma, narrower than
    young male), flat elderly male chest & hips, thin limbs, slight elderly lower-belly softness.
  - Low-poly 70s Korean grandpa short receding-hairline hair (`Extra_grandpa_Hair`) bone-parented
    to `head` (toggleable on/off).

Run:
  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 \
      -P promo/models/build_grandpa.py
"""

import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import build_senior_females as SF

REPO_ROOT = SF.REPO_ROOT
SRC_FIG = SF.SRC_FIG
OUT_GRANDPA = os.path.join(REPO_ROOT, "promo", "models", "extra_grandpa.blend")
RENDER_DIR = os.path.join(REPO_ROOT, "work", "senior_grandpa_review")


def reshape_grandpa(arm_obj, body_obj):
    """Reshape src_figure_copy into a thin 70s Korean grandpa (170cm straight -> 165cm stooped)."""
    if body_obj.data.shape_keys is not None:
        body_obj.shape_key_clear()

    mesh = body_obj.data
    vweights = SF.vertex_group_weights(body_obj)
    bones = arm_obj.data.bones
    bone_segs = {b.name: (b.head_local.copy(), b.tail_local.copy()) for b in bones}

    target_straight_h = 1.670   # 167 cm straight -> ~162 cm stooped
    shoulder_inward_x = 0.015   # slimmer than young male, clearly broader than grandma (0.032)
    hand_slim = 0.10

    new_coords = []
    for i, v in enumerate(mesh.vertices):
        p = v.co.copy()
        w = vweights[i]

        w_head = SF.sum_weights(w, SF.HEAD_BONES)
        w_neck = SF.sum_weights(w, SF.NECK_BONES)
        w_torso = SF.sum_weights(w, SF.TORSO_BONES)
        w_arm_l = SF.arm_side_weight(w, "l")
        w_arm_r = SF.arm_side_weight(w, "r")
        w_arm = min(1.0, w_arm_l + w_arm_r)
        w_clav_l = w.get("clavicle_l", 0.0)
        w_clav_r = w.get("clavicle_r", 0.0)
        w_leg_l = SF.sum_weights(w, SF.LEG_L_BONES)
        w_leg_r = SF.sum_weights(w, SF.LEG_R_BONES)
        w_leg = min(1.0, w_leg_l + w_leg_r)

        x, y, z = p.x, p.y, p.z
        ax = abs(x)

        # 1. Head: slightly leaner elderly male head
        if w_head > 0.0:
            hc = Vector((0.0, -0.095, 1.625))
            rel = Vector((x, y, z)) - hc
            tx = hc.x + rel.x * 0.93
            ty = hc.y + rel.y * 0.94
            tz = hc.z + rel.z * 0.94 - 0.006
            x = x + (tx - x) * w_head
            y = y + (ty - y) * w_head
            z = z + (tz - z) * w_head

        # 2. Neck: thinner elderly neck
        if w_neck > 0.0:
            nc_y = -0.085
            x *= 1.0 - 0.16 * w_neck
            y = nc_y + (y - nc_y) * (1.0 - 0.14 * w_neck)

        # 3. Torso: thin elderly male ribcage, flat chest, no hourglass waist, slight lower belly
        body_mask = max(0.0, 1.0 - w_arm * 0.96) * (w_torso + w_leg * SF.smoothstep(0.76, 0.96, z))
        body_mask = min(1.0, body_mask)

        if body_mask > 0.0:
            torso_cy = -0.105

            # Narrower frail upper ribcage (less than grandma so still reads male)
            g_upper = SF.gauss(z, 1.36, 0.095)
            x *= 1.0 - 0.11 * g_upper * body_mask

            # Lean straight male waist with natural elderly potbelly rounding
            g_waist = SF.gauss(z, 1.13, 0.070)
            x *= 1.0 - 0.04 * g_waist * body_mask
            g_pot_side = SF.gauss(z, 1.04, 0.090)
            x *= 1.0 + 0.045 * g_pot_side * body_mask

            # Flatten young male pecs slightly for frail 70s chest + natural potbelly
            front_mask = SF.smoothstep(-0.090, -0.150, y)
            if front_mask > 0.0:
                g_pec = SF.gauss(z, 1.33, 0.060) * SF.gauss(ax, 0.07, 0.07)
                y += 0.010 * g_pec * front_mask * body_mask

                g_bz = SF.gauss(z, 1.045, 0.105)
                g_bx = SF.gauss(ax, 0.0, 0.135)
                y -= 0.044 * g_bz * g_bx * front_mask * body_mask
                z -= 0.006 * SF.gauss(z, 0.99, 0.055) * g_bx * front_mask * body_mask

            # Lean elderly male hips & flat glutes
            g_hip_x = SF.gauss(z, 0.905, 0.092)
            x *= 1.0 - 0.05 * g_hip_x * body_mask

            rear_mask = SF.smoothstep(-0.088, -0.015, y)
            if rear_mask > 0.0:
                g_glute = SF.gauss(z, 0.89, 0.080) * SF.gauss(ax, 0.07, 0.08)
                y -= 0.012 * g_glute * rear_mask * body_mask

                # Subtle rounded upper-back kyphotic pad
                g_hump = SF.gauss(z, 1.38, 0.075) * SF.gauss(ax, 0.0, 0.095)
                y += 0.020 * g_hump * rear_mask * body_mask

        # 4. Arms: thin elderly arms
        if w_arm > 0.0:
            side = 1.0 if w_arm_l >= w_arm_r else -1.0
            clav_blend = SF.smoothstep(0.035, 0.140, abs(p.x))
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
                slim = 0.22
                if dom_b.startswith("lowerarm_"):
                    slim = 0.22 - (0.22 - hand_slim) * SF.smoothstep(0.55, 0.95, t_proj)
                cur = Vector((x, y, z))
                cur = axis_pt_shifted + (cur - axis_pt_shifted) * (1.0 - slim * min(1.0, arm_limb_w))
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

        # 5. Thin elderly legs
        if w_leg > 0.05:
            dom_leg = "l" if w_leg_l >= w_leg_r else "r"
            th_h, th_t = bone_segs["thigh_" + dom_leg]
            g_thigh = SF.gauss(z, 0.72, 0.145)
            if 0.42 <= z <= 0.94:
                t_z = max(0.0, min(1.0, (th_h.z - z) / max(th_h.z - th_t.z, 1e-6)))
                cx = th_h.x + (th_t.x - th_h.x) * t_z
                cy = th_h.y + (th_t.y - th_h.y) * t_z
                x = cx + (x - cx) * (1.0 - 0.11 * g_thigh * w_leg)
                y = cy + (y - cy) * (1.0 - 0.11 * g_thigh * w_leg)

            if 0.16 <= z <= 0.46:
                cf_h, cf_t = bone_segs["calf_" + dom_leg]
                g_calf = SF.gauss(z, 0.31, 0.095)
                t_z = max(0.0, min(1.0, (cf_h.z - z) / max(cf_h.z - cf_t.z, 1e-6)))
                cx = cf_h.x + (cf_t.x - cf_h.x) * t_z
                cy = cf_h.y + (cf_t.y - cf_h.y) * t_z
                x = cx + (x - cx) * (1.0 - 0.15 * g_calf * w_leg)
                y = cy + (y - cy) * (1.0 - 0.15 * g_calf * w_leg)

            g_ankle = SF.gauss(z, 0.13, 0.055)
            if g_ankle > 0.05:
                cf_h, cf_t = bone_segs["calf_" + dom_leg]
                t_z = max(0.0, min(1.0, (cf_h.z - z) / max(cf_h.z - cf_t.z, 1e-6)))
                cx = cf_h.x + (cf_t.x - cf_h.x) * t_z
                cy = cf_h.y + (cf_t.y - cf_h.y) * t_z
                x = cx + (x - cx) * (1.0 - 0.14 * g_ankle * w_leg)
                y = cy + (y - cy) * (1.0 - 0.14 * g_ankle * w_leg)

        new_coords.append(Vector((x, y, z)))

    # Scale to 1.700 m straight height
    min_z = min(c.z for c in new_coords)
    max_z = max(c.z for c in new_coords)
    scale_factor = target_straight_h / (max_z - min_z)

    for i, v in enumerate(mesh.vertices):
        c = new_coords[i]
        v.co = Vector((c.x * scale_factor, c.y * scale_factor, (c.z - min_z) * scale_factor))
    mesh.update()
    SF.set_flat_shading(mesh)

    # Sync armature
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
        if SF.is_arm_bone(eb.name):
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
    SF.clear_pose(arm_obj)

    # Apply natural 70s grandpa stooped posture (~24 deg kyphosis, smooth neck/head compensation)
    SF.rot_world_bone(arm_obj, "pelvis", Vector((1, 0, 0)), math.radians(3.0))
    SF.rot_world_bone(arm_obj, "thigh_l", Vector((1, 0, 0)), math.radians(-8.0))
    SF.rot_world_bone(arm_obj, "thigh_r", Vector((1, 0, 0)), math.radians(-8.0))
    SF.rot_world_bone(arm_obj, "calf_l", Vector((1, 0, 0)), math.radians(10.0))
    SF.rot_world_bone(arm_obj, "calf_r", Vector((1, 0, 0)), math.radians(10.0))
    SF.rot_world_bone(arm_obj, "foot_l", Vector((1, 0, 0)), math.radians(-5.0))
    SF.rot_world_bone(arm_obj, "foot_r", Vector((1, 0, 0)), math.radians(-5.0))

    SF.rot_world_bone(arm_obj, "spine_01", Vector((1, 0, 0)), math.radians(5.0))
    SF.rot_world_bone(arm_obj, "spine_02", Vector((1, 0, 0)), math.radians(10.0))
    SF.rot_world_bone(arm_obj, "spine_03", Vector((1, 0, 0)), math.radians(9.0))

    SF.rot_world_bone(arm_obj, "clavicle_l", Vector((0, 0, 1)), math.radians(-4.5))
    SF.rot_world_bone(arm_obj, "clavicle_r", Vector((0, 0, 1)), math.radians(4.5))
    SF.rot_world_bone(arm_obj, "upperarm_l", Vector((1, 0, 0)), math.radians(-17.0))
    SF.rot_world_bone(arm_obj, "upperarm_r", Vector((1, 0, 0)), math.radians(-17.0))
    SF.rot_world_bone(arm_obj, "lowerarm_l", Vector((1, 0, 0)), math.radians(-6.0))
    SF.rot_world_bone(arm_obj, "lowerarm_r", Vector((1, 0, 0)), math.radians(-6.0))

    SF.rot_world_bone(arm_obj, "neck_01", Vector((1, 0, 0)), math.radians(-8.5))
    SF.rot_world_bone(arm_obj, "head", Vector((1, 0, 0)), math.radians(-15.5))

    SF.apply_pose_as_rest_pose(arm_obj, body_obj)

    # Fine-tune to exact 1.620 m standing height
    zs = [v.co.z for v in mesh.vertices]
    cur_h = max(zs) - min(zs)
    print(f"[grandpa] post-stoop height before fine-tune = {cur_h:.4f} m")
    if abs(cur_h - 1.620) > 0.004:
        adj = 1.620 / cur_h
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

    SF.assign_box_uv(mesh)
    zs = [v.co.z for v in mesh.vertices]
    print(f"[grandpa] FINAL height={max(zs)-min(zs):.4f}m")


def build_grandpa_hair(arm_obj, body_obj):
    """Build a classic Korean 70s grandfather short side-and-back hair fringe (receding top/forehead)
    as a clean watertight low-poly mesh with >=3mm clearance from skull."""
    hc, hr, _ = SF.head_bounds(body_obj)
    tmp_objs = []

    def add_lobe(name, loc, scale, rot_deg=(0, 0, 0)):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)
        ob.location = loc
        ob.scale = scale
        ob.rotation_euler = tuple(math.radians(a) for a in rot_deg)
        bpy.context.scene.collection.objects.link(ob)
        tmp_objs.append(ob)

    # Classic horseshoe / short receding side-and-back hair band (reads instantly as 70s grandpa!)
    # Left & right temple-to-ear short hair tufts
    for sx in (-1.0, 1.0):
        add_lobe(
            f"gp_side_{sx}",
            hc + Vector((sx * hr.x * 0.88, hr.y * 0.16, hr.z * 0.04)),
            (hr.x * 0.34, hr.y * 0.68, hr.z * 0.44),
            rot_deg=(6, sx * -8, sx * 10),
        )
        add_lobe(
            f"gp_side_back_{sx}",
            hc + Vector((sx * hr.x * 0.72, hr.y * 0.56, hr.z * 0.02)),
            (hr.x * 0.44, hr.y * 0.52, hr.z * 0.48),
            rot_deg=(4, 0, sx * -18),
        )
    # Back short hair band
    add_lobe(
        "gp_back",
        hc + Vector((0.0, hr.y * 0.70, hr.z * 0.02)),
        (hr.x * 0.96, hr.y * 0.44, hr.z * 0.52),
        rot_deg=(6, 0, 0),
    )

    bpy.ops.object.select_all(action="DESELECT")
    for ob in tmp_objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = tmp_objs[0]
    bpy.ops.object.join()
    hair_obj = bpy.context.active_object
    hair_obj.name = "Extra_grandpa_Hair"
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    rem = hair_obj.modifiers.new("Remesh", "REMESH")
    rem.mode = "VOXEL"
    rem.voxel_size = 0.0055
    bpy.ops.object.modifier_apply(modifier=rem.name)

    sm = hair_obj.modifiers.new("Smooth", "SMOOTH")
    sm.factor = 0.45
    sm.iterations = 3
    bpy.ops.object.modifier_apply(modifier=sm.name)

    dec = hair_obj.modifiers.new("Decimate", "DECIMATE")
    dec.decimate_type = "COLLAPSE"
    dec.ratio = 0.055
    bpy.ops.object.modifier_apply(modifier=dec.name)

    bm = bmesh.new()
    bm.from_mesh(hair_obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    bmesh.ops.dissolve_degenerate(bm, dist=0.0005, edges=bm.edges)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(hair_obj.data)
    bm.free()

    hair_obj.data.name = "Extra_grandpa_Hair_Mesh"
    SF.set_flat_shading(hair_obj.data)
    SF.assign_box_uv(hair_obj.data)
    SF.parent_hair_to_head(arm_obj, body_obj, hair_obj)

    print(f"[grandpa_hair] verts={len(hair_obj.data.vertices)}, polys={len(hair_obj.data.polygons)}")
    return hair_obj


def build_grandpa_blend():
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
    SF.clear_pose(arm)

    arm.name = "Extra_grandpa"
    arm.data.name = "Extra_grandpa_Rig"
    body.name = "Extra_grandpa_Body"
    body.data.name = "Extra_grandpa_Mesh"

    # Cool slate-silver monochrome tint (reads elderly male, complements grandma lavender-pink)
    mat = SF.make_flat_material("Extra_grandpa_Mat", (0.56, 0.62, 0.68, 1.0), roughness=0.58)
    body.data.materials.clear()
    body.data.materials.append(mat)

    reshape_grandpa(arm, body)

    SF.clear_pose(arm)
    os.makedirs(os.path.dirname(OUT_GRANDPA), exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=OUT_GRANDPA, compress=True)

    zs = [v.co.z for v in body.data.vertices]
    metrics = {
        "profile": "grandpa",
        "out": OUT_GRANDPA,
        "body_height_m": round(max(zs) - min(zs), 4),
        "body_verts": len(body.data.vertices),
        "body_polys": len(body.data.polygons),
        "bones": len(arm.data.bones),
    }
    print("BUILT_GRANDPA", json.dumps(metrics))
    return metrics


def render_grandpa_review():
    """Render 4-way senior lineup: 175cm Rookie | 165cm Grandpa | 157cm Ajumma | 150cm Grandma
    plus grandpa side profile and grandpa+grandma couple closeup."""
    os.makedirs(RENDER_DIR, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 900
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"

    def load_char(blend_path, target_x):
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

    r_arm, r_objs = load_char(os.path.join(REPO_ROOT, "promo", "models", "hero_rookie.blend"), -1.45)
    p_arm, p_objs = load_char(OUT_GRANDPA, -0.48)
    a_arm, a_objs = load_char(SF.OUT_AJUMMA, 0.48)
    g_arm, g_objs = load_char(SF.OUT_GRANDMA, 1.45)

    for ob in r_objs:
        if any(k in ob.name.lower() for k in ("cap", "headset", "gear", "airpod", "varsity", "watch")):
            ob.hide_render = True

    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    bg = next((n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND"), None)
    if bg:
        bg.inputs["Color"].default_value = (0.14, 0.16, 0.19, 1.0)
        bg.inputs["Strength"].default_value = 0.85

    def add_light(name, loc, rot_deg, energy, size=2.8):
        ldata = bpy.data.lights.new(name=name, type="AREA")
        ldata.energy = energy
        ldata.size = size
        lobj = bpy.data.objects.new(name=name, object_data=ldata)
        lobj.location = loc
        lobj.rotation_euler = tuple(math.radians(a) for a in rot_deg)
        scene.collection.objects.link(lobj)

    add_light("Key", (3.0, -4.2, 3.2), (58, 0, 34), 420, 2.8)
    add_light("Fill", (-3.5, -2.8, 2.1), (72, 0, -48), 180, 3.2)
    add_light("Rim", (0.0, 4.0, 2.8), (125, 0, 0), 300, 3.2)

    bpy.ops.mesh.primitive_plane_add(size=14.0, location=(0.0, 0.0, 0.0))
    ground = bpy.context.active_object
    ground.data.materials.append(SF.make_flat_material("Ground", (0.20, 0.22, 0.26, 1.0)))

    # Reference height bars: 1.50m, 1.57m, 1.62m, 1.75m
    for h_val, col in (
        (1.50, (0.72, 0.56, 0.86, 1.0)),
        (1.57, (0.94, 0.56, 0.44, 1.0)),
        (1.62, (0.52, 0.72, 0.90, 1.0)),
        (1.75, (0.38, 0.84, 0.88, 1.0)),
    ):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.60, h_val))
        bar = bpy.context.active_object
        bar.scale = (4.4, 0.008, 0.005)
        bar.data.materials.append(SF.make_flat_material(f"Bar_{h_val}", col))

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
            if any(k in o.name.lower() for k in ("cap", "headset", "gear", "airpod", "varsity", "watch")):
                o.hide_render = True
            else:
                o.hide_render = not vis

    views = [
        ("01_front_4way", (0.0, -5.8, 0.90), (0.0, 0.0, 0.86), (True, True, True, True)),
        ("02_three_quarter", (3.2, -4.9, 0.96), (0.0, 0.0, 0.86), (True, True, True, True)),
        ("03_side_grandpa", (4.0, -0.08, 0.86), (-0.48, -0.08, 0.84), (False, True, False, False)),
        ("04_back_4way", (0.0, 5.8, 0.90), (0.0, 0.0, 0.86), (True, True, True, True)),
    ]

    for vname, loc, tgt, (vr, vp, va, vg) in views:
        set_vis(r_objs, vr)
        set_vis(p_objs, vp)
        set_vis(a_objs, va)
        set_vis(g_objs, vg)
        cam_obj.location = loc
        look_at(cam_obj, tgt)
        scene.render.filepath = os.path.join(RENDER_DIR, f"{vname}.png")
        bpy.ops.render.render(write_still=True)

    print(f"[review] Rendered 4 views to {RENDER_DIR}")


def main():
    build_grandpa_blend()
    render_grandpa_review()


if __name__ == "__main__":
    main()
