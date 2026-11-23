"""Build a 161cm Korean-standard female low-poly extra rig from src_figure_copy.blend.

Keeps the exact 1,844-vert / 1,508-poly low-poly topology and 52-bone armature
in clean rest pose (scale 1,1,1, zero pose rotation) so all existing
pose_library.json poses work seamlessly.

Includes an optional low-poly ponytail mesh (`Extra_female_Hair`) bone-parented
to `head` so it moves with every pose and can be toggled on/off cleanly.

Outputs:
  promo/models/extra_female.blend
  promo/models/renders_female_extra/{front,three_quarter,side_female,back}.png
"""

import math
import os
import bpy
import bmesh
from mathutils import Vector, Matrix

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_FIG = os.path.join(REPO_ROOT, "promo", "cast", "src_figure_copy.blend")
OUT_BLEND = os.path.join(REPO_ROOT, "promo", "models", "extra_female.blend")
RENDER_DIR = os.path.join(REPO_ROOT, "promo", "models", "renders_female_extra")

TARGET_HEIGHT = 1.610  # 161 cm

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
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = roughness
    return mat


def set_flat_shading(mesh):
    for p in mesh.polygons:
        p.use_smooth = False


def reshape_female(arm_obj, body_obj):
    """Reshape mesh + armature in-place to 161cm Korean-standard female proportions."""
    # Clear any inherited shape keys so vertex edits are the true evaluated geometry
    if body_obj.data.shape_keys is not None:
        body_obj.shape_key_clear()

    mesh = body_obj.data
    vweights = vertex_group_weights(body_obj)

    bones = arm_obj.data.bones
    bone_segs = {b.name: (b.head_local.copy(), b.tail_local.copy()) for b in bones}

    # Narrow shoulders by ~2.4cm per side (in 1.75m base space)
    shoulder_inward_x = 0.024

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

        # 1. Head: smaller, slightly slimmer jaw/face
        if w_head > 0.0:
            hc = Vector((0.0, -0.095, 1.625))
            rel = Vector((x, y, z)) - hc
            # Extra slight taper on lower jaw (z < 1.61)
            jaw_taper = 1.0 - 0.06 * smoothstep(1.63, 1.54, z)
            tx = hc.x + rel.x * 0.86 * jaw_taper
            ty = hc.y + rel.y * 0.88
            tz = hc.z + rel.z * 0.89 - 0.010
            x = x + (tx - x) * w_head
            y = y + (ty - y) * w_head
            z = z + (tz - z) * w_head

        # 2. Neck: slimmer
        if w_neck > 0.0:
            nc_y = -0.085
            x *= 1.0 - 0.19 * w_neck
            y = nc_y + (y - nc_y) * (1.0 - 0.16 * w_neck)

        # 3. Torso (excludes arms)
        body_mask = max(0.0, 1.0 - w_arm * 0.96) * (w_torso + w_leg * smoothstep(0.76, 0.96, z))
        body_mask = min(1.0, body_mask)

        if body_mask > 0.0:
            torso_cy = -0.105

            # 3a. Narrow upper torso / ribcage
            g_upper = gauss(z, 1.36, 0.095)
            x *= 1.0 - 0.13 * g_upper * body_mask

            # 3b. Well-defined waist taper (z ~= 1.06..1.17)
            g_waist = gauss(z, 1.11, 0.072)
            x *= 1.0 - 0.21 * g_waist * body_mask
            y = torso_cy + (y - torso_cy) * (1.0 - 0.15 * g_waist * body_mask)

            # 3c. Bust volume (front -Y, smooth dual-mound low-poly silhouette)
            front_mask = smoothstep(-0.100, -0.160, y)
            if front_mask > 0.0:
                g_bust_z = gauss(z, 1.268, 0.056)
                g_bust_x = gauss(ax, 0.068, 0.052) + 0.30 * gauss(ax, 0.0, 0.035)
                bust_push = 0.048 * g_bust_z * g_bust_x * front_mask * body_mask
                y -= bust_push
                z -= 0.009 * gauss(z, 1.245, 0.038) * g_bust_x * front_mask * body_mask
                x += sx * 0.009 * g_bust_z * gauss(ax, 0.092, 0.038) * front_mask * body_mask

            # 3d. Pelvis & Hips width + glute fullness
            g_hip_x = gauss(z, 0.905, 0.092)
            x *= 1.0 + 0.145 * g_hip_x * body_mask

            # Rear glute fullness (+Y)
            rear_mask = smoothstep(-0.088, -0.015, y)
            if rear_mask > 0.0:
                g_glute_z = gauss(z, 0.890, 0.082)
                g_glute_x = gauss(ax, 0.076, 0.080) + 0.36 * gauss(ax, 0.0, 0.048)
                y += 0.042 * g_glute_z * g_glute_x * rear_mask * body_mask

            # Gentle lower-back inward curve (lordosis) for feminine S-curve
            if rear_mask > 0.0:
                g_lback = gauss(z, 1.09, 0.065)
                y -= 0.014 * g_lback * rear_mask * body_mask

        # 4. Arms: shift inward with narrower shoulders + slimmer limbs
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
            # Keep distal wrist/hand transition smooth: fade radial slimming near wrist
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
                # Taper slimming from 15% on upper/mid arm down to 7% at wrist so hand join is seamless
                slim = 0.15
                if dom_b.startswith("lowerarm_"):
                    slim = 0.15 - 0.08 * smoothstep(0.55, 0.95, t_proj)
                cur = Vector((x, y, z))
                radial = cur - axis_pt_shifted
                cur = axis_pt_shifted + radial * (1.0 - slim * min(1.0, arm_limb_w))
                x, y, z = cur.x, cur.y, cur.z

            # Gently slim female hand/fingers by 7% around wrist pivot to match slender wrist
            hand_w = sum(
                val for bn, val in w.items()
                if bn.startswith(("hand_", "thumb_", "index_", "middle_", "ring_", "pinky_"))
            )
            if hand_w > 0.05:
                hand_b = "hand_" + ("l" if side > 0 else "r")
                wh = bone_segs[hand_b][0]
                wrist_shifted = Vector((wh.x - side * shoulder_inward_x, wh.y, wh.z))
                cur = Vector((x, y, z))
                cur = wrist_shifted + (cur - wrist_shifted) * (1.0 - 0.07 * min(1.0, hand_w))
                x, y, z = cur.x, cur.y, cur.z

        # 5. Lower body (fuller thighs, smooth hip-thigh transition, slimmer ankles)
        if w_leg > 0.05:
            g_thigh = gauss(z, 0.74, 0.135)
            dom_leg = "l" if w_leg_l >= w_leg_r else "r"
            th_h, th_t = bone_segs["thigh_" + dom_leg]
            if 0.45 <= z <= 0.94:
                t_z = max(0.0, min(1.0, (th_h.z - z) / max(th_h.z - th_t.z, 1e-6)))
                cx = th_h.x + (th_t.x - th_h.x) * t_z
                cy = th_h.y + (th_t.y - th_h.y) * t_z
                dx = x - cx
                dy = y - cy
                x = cx + dx * (1.0 + 0.105 * g_thigh * w_leg)
                y = cy + dy * (1.0 + 0.095 * g_thigh * w_leg)

            g_ankle = gauss(z, 0.13, 0.055)
            if g_ankle > 0.05:
                cf_h, cf_t = bone_segs["calf_" + dom_leg]
                t_z = max(0.0, min(1.0, (cf_h.z - z) / max(cf_h.z - cf_t.z, 1e-6)))
                cx = cf_h.x + (cf_t.x - cf_h.x) * t_z
                cy = cf_h.y + (cf_t.y - cf_h.y) * t_z
                x = cx + (x - cx) * (1.0 - 0.11 * g_ankle * w_leg)
                y = cy + (y - cy) * (1.0 - 0.11 * g_ankle * w_leg)

        new_coords.append(Vector((x, y, z)))

    # Scale cleanly to TARGET_HEIGHT (1.610m) with feet at Z=0
    min_z = min(c.z for c in new_coords)
    max_z = max(c.z for c in new_coords)
    cur_h = max_z - min_z
    scale_factor = TARGET_HEIGHT / cur_h

    for i, v in enumerate(mesh.vertices):
        c = new_coords[i]
        v.co = Vector((c.x * scale_factor, c.y * scale_factor, (c.z - min_z) * scale_factor))
    mesh.update()
    set_flat_shading(mesh)

    # Sync armature bones
    bpy.context.view_layer.objects.active = arm_obj
    arm_obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    ebones = arm_obj.data.edit_bones

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

        # Match the 7% hand/finger slimming around the wrist pivot
        if eb.name.startswith(("hand_", "thumb_", "index_", "middle_", "ring_", "pinky_")):
            side = 1.0 if eb.name.endswith("_l") else -1.0
            wh = bone_segs["hand_" + ("l" if side > 0 else "r")][0]
            wrist_shifted = Vector((wh.x - side * shoulder_inward_x, wh.y, wh.z))
            h_co = wrist_shifted + (h_co - wrist_shifted) * 0.93
            t_co = wrist_shifted + (t_co - wrist_shifted) * 0.93

        eb.head = Vector((h_co.x * scale_factor, h_co.y * scale_factor, (h_co.z - min_z) * scale_factor))
        eb.tail = Vector((t_co.x * scale_factor, t_co.y * scale_factor, (t_co.z - min_z) * scale_factor))

        if eb.name == "head":
            eb.tail.z = TARGET_HEIGHT

    bpy.ops.object.mode_set(mode="OBJECT")
    arm_obj.select_set(False)

    verts_final = [v.co for v in mesh.vertices]
    zs = [v.z for v in verts_final]
    xs = [v.x for v in verts_final]
    print(f"[female_extra] scale={scale_factor:.5f} height={max(zs)-min(zs):.4f}m Z=[{min(zs):.4f},{max(zs):.4f}] X=[{min(xs):.4f},{max(xs):.4f}]")


def build_lowpoly_ponytail(arm_obj, body_obj):
    """Create a clean faceted low-poly ponytail (cap + tie + tail) parented to `head` bone."""
    # Measure actual scaled head vertices so the hair cap hugs the head perfectly
    vweights = vertex_group_weights(body_obj)
    head_pts = [
        v.co.copy()
        for i, v in enumerate(body_obj.data.vertices)
        if vweights[i].get("head", 0.0) > 0.5
    ]
    hx_min = min(p.x for p in head_pts)
    hx_max = max(p.x for p in head_pts)
    hy_min = min(p.y for p in head_pts)
    hy_max = max(p.y for p in head_pts)
    hz_min = min(p.z for p in head_pts)
    hz_max = max(p.z for p in head_pts)

    hc = Vector(((hx_min + hx_max) * 0.5, (hy_min + hy_max) * 0.5, (hz_min + hz_max) * 0.5))
    rx = (hx_max - hx_min) * 0.5
    ry = (hy_max - hy_min) * 0.5
    rz = (hz_max - hz_min) * 0.5
    print(f"[hair] head center=({hc.x:.3f},{hc.y:.3f},{hc.z:.3f}) radii=({rx:.3f},{ry:.3f},{rz:.3f})")

    bm = bmesh.new()

    # 1. Low-poly hair cap covering crown, temples, and back of head
    # Built as a faceted dome slightly larger than head, trimmed cleanly across forehead/face
    rings = 5
    segs = 10
    ring_verts = []
    # Latitude from top pole (phi=0) down to hairline (phi_max varies by angle: higher on forehead, lower at back)
    top_v = bm.verts.new((hc.x, hc.y + 0.004, hz_max + 0.017))

    for r in range(1, rings + 1):
        frac = r / rings
        row = []
        for s in range(segs):
            # theta=0 is front (-Y), pi is back (+Y)
            theta = 2.0 * math.pi * s / segs
            # Hairline dips much lower in back (+Y, cos(theta) = -1) than forehead (-Y, cos(theta) = +1)
            frontness = math.cos(theta)  # +1 front, -1 back
            # Smooth interpolation of max_phi around head
            max_phi = math.radians(86.0 - 32.0 * frontness + 6.0 * (1.0 - frontness * frontness))
            phi = frac * max_phi

            # Generous hair thickness offset so faceted head corners never poke through
            pad = 0.015 + 0.005 * (1.0 - frontness) * 0.5
            px = hc.x + (rx + pad) * math.sin(phi) * math.sin(theta)
            py = hc.y - (ry + pad) * math.sin(phi) * math.cos(theta) + 0.004 * (1.0 - frontness) * 0.5
            pz = hc.z + (rz + 0.016) * math.cos(phi) + 0.005
            row.append(bm.verts.new((px, py, pz)))
        ring_verts.append(row)

    # Cap top fan
    for s in range(segs):
        s_next = (s + 1) % segs
        bm.faces.new((top_v, ring_verts[0][s_next], ring_verts[0][s]))
    # Cap side quads
    for r in range(rings - 1):
        for s in range(segs):
            s_next = (s + 1) % segs
            bm.faces.new((ring_verts[r][s], ring_verts[r][s_next], ring_verts[r + 1][s_next], ring_verts[r + 1][s]))
    # Close underside rim of cap toward head interior so there's no hollow gap
    inner_center = bm.verts.new((hc.x, hc.y + 0.015, hc.z - 0.015))
    for s in range(segs):
        s_next = (s + 1) % segs
        bm.faces.new((ring_verts[-1][s], ring_verts[-1][s_next], inner_center))

    # 2. Ponytail tie + sweeping faceted tail at upper-back of head
    tie_origin = Vector((hc.x, hy_max + 0.006, hc.z + rz * 0.34))
    # Spine points of ponytail (in world/rest coords, sweeping back +Y and down -Z)
    tail_spine = [
        (tie_origin + Vector((0.0, -0.006, 0.004)), 0.020, 0.020),  # inside tie
        (tie_origin + Vector((0.0, 0.014, 0.008)), 0.025, 0.024),   # tie knot
        (tie_origin + Vector((0.0, 0.046, 0.002)), 0.036, 0.032),   # upper puff
        (tie_origin + Vector((0.0, 0.072, -0.036)), 0.042, 0.034),  # mid full volume
        (tie_origin + Vector((0.0, 0.080, -0.095)), 0.036, 0.028),  # lower mid
        (tie_origin + Vector((0.0, 0.074, -0.155)), 0.022, 0.018),  # taper
        (tie_origin + Vector((0.0, 0.064, -0.198)), 0.005, 0.005),  # tip
    ]

    tail_segs = 7
    tail_rings = []
    for idx, (pt, rad_x, rad_y) in enumerate(tail_spine):
        if idx == 0:
            tangent = (tail_spine[1][0] - pt).normalized()
        elif idx == len(tail_spine) - 1:
            tangent = (pt - tail_spine[idx - 1][0]).normalized()
        else:
            tangent = (tail_spine[idx + 1][0] - tail_spine[idx - 1][0]).normalized()

        side_vec = Vector((1.0, 0.0, 0.0))
        up_vec = side_vec.cross(tangent).normalized()

        ring = []
        for s in range(tail_segs):
            ang = 2.0 * math.pi * s / tail_segs
            vpos = pt + side_vec * (math.cos(ang) * rad_x) + up_vec * (math.sin(ang) * rad_y)
            ring.append(bm.verts.new(vpos))
        tail_rings.append(ring)

    for r in range(len(tail_rings) - 1):
        for s in range(tail_segs):
            s_next = (s + 1) % tail_segs
            bm.faces.new((tail_rings[r][s], tail_rings[r][s_next], tail_rings[r + 1][s_next], tail_rings[r + 1][s]))
    # Cap tip
    tip_v = bm.verts.new(tail_spine[-1][0] + Vector((0.0, -0.004, -0.014)))
    for s in range(tail_segs):
        s_next = (s + 1) % tail_segs
        bm.faces.new((tail_rings[-1][s], tail_rings[-1][s_next], tip_v))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    hair_mesh = bpy.data.meshes.new("Extra_female_Hair_Mesh")
    bm.to_mesh(hair_mesh)
    bm.free()
    set_flat_shading(hair_mesh)

    hair_obj = bpy.data.objects.new("Extra_female_Hair", hair_mesh)
    bpy.context.scene.collection.objects.link(hair_obj)

    # Deep warm charcoal-brown low-poly hair material
    hair_mat = make_flat_material("Extra_female_Hair_Mat", (0.14, 0.11, 0.10, 1.0), roughness=0.65)
    hair_mesh.materials.append(hair_mat)

    # Bone-parent to `head` so it follows every head pose cleanly
    hair_obj.parent = arm_obj
    hair_obj.parent_type = "BONE"
    hair_obj.parent_bone = "head"
    # Compensate Blender's bone-parent tail offset so mesh stays at exact world coords
    head_bone = arm_obj.data.bones["head"]
    bone_mat = arm_obj.matrix_world @ Matrix.Translation(head_bone.tail_local) @ head_bone.matrix_local.to_3x3().to_4x4()
    hair_obj.matrix_parent_inverse = bone_mat.inverted()

    print(f"[hair] built ponytail: verts={len(hair_mesh.vertices)}, polys={len(hair_mesh.polygons)}")
    return hair_obj


def render_comparison(male_arm, female_bald_arm, female_hair_arm):
    """Render 3-way comparison: 175cm Male | 161cm Female (Bald) | 161cm Female (Ponytail)."""
    os.makedirs(RENDER_DIR, exist_ok=True)

    male_arm.location = (-0.95, 0.0, 0.0)
    female_bald_arm.location = (0.0, 0.0, 0.0)
    female_hair_arm.location = (0.95, 0.0, 0.0)

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 900
    scene.render.film_transparent = False

    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.14, 0.16, 0.19, 1.0)
        bg.inputs["Strength"].default_value = 0.85

    def add_light(name, ltype, loc, rot_deg, energy, size=2.4):
        ldata = bpy.data.lights.new(name=name, type=ltype)
        ldata.energy = energy
        if ltype == "AREA":
            ldata.size = size
        lobj = bpy.data.objects.new(name=name, object_data=ldata)
        lobj.location = loc
        lobj.rotation_euler = tuple(math.radians(a) for a in rot_deg)
        scene.collection.objects.link(lobj)

    add_light("QA_Key", "AREA", (2.6, -3.6, 2.9), (58, 0, 34), 320, 2.4)
    add_light("QA_Fill", "AREA", (-3.0, -2.5, 1.9), (72, 0, -48), 140, 2.8)
    add_light("QA_Rim", "AREA", (0.0, 3.6, 2.6), (125, 0, 0), 260, 2.8)

    bpy.ops.mesh.primitive_plane_add(size=10.0, location=(0.0, 0.0, 0.0))
    ground = bpy.context.active_object
    ground.data.materials.append(make_flat_material("QA_Ground", (0.20, 0.22, 0.26, 1.0)))

    # Height reference lines behind characters: 1.61m (coral) and 1.75m (sky)
    for h_val, col in ((1.61, (0.95, 0.48, 0.56, 1.0)), (1.75, (0.45, 0.78, 0.95, 1.0))):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.45, h_val))
        bar = bpy.context.active_object
        bar.scale = (3.2, 0.008, 0.006)
        bar.data.materials.append(make_flat_material(f"Bar_{h_val}", col))

    cam_data = bpy.data.cameras.new("QA_Cam")
    cam_data.lens = 62.0
    cam_obj = bpy.data.objects.new("QA_Cam", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    def look_at(obj, target):
        direction = Vector(target) - obj.location
        obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    def set_group_hidden(arm, hidden):
        arm.hide_render = hidden
        for c in arm.children:
            c.hide_render = hidden

    views = [
        ("front", (0.0, -4.9, 0.90), (0.0, 0.0, 0.86), False),
        ("three_quarter", (2.9, -4.1, 0.96), (0.12, 0.0, 0.86), False),
        ("side_female", (4.6, -0.06, 0.84), (0.95, -0.06, 0.82), True),
        ("back", (0.0, 4.9, 0.90), (0.0, 0.0, 0.86), False),
        ("hands_closeup", (-0.45, -1.35, 0.88), (-0.46, -0.18, 0.82), False),
    ]

    for vname, loc, tgt, solo_hair in views:
        set_group_hidden(male_arm, solo_hair)
        set_group_hidden(female_bald_arm, solo_hair)
        set_group_hidden(female_hair_arm, False)
        cam_obj.location = loc
        look_at(cam_obj, tgt)
        scene.render.filepath = os.path.join(RENDER_DIR, f"{vname}.png")
        bpy.ops.render.render(write_still=True)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # Load clean rest-pose BASE_Low Poly Man + Fig.rig from src_figure_copy.blend
    with bpy.data.libraries.load(SRC_FIG, link=False) as (data_from, data_to):
        data_to.objects = ["Fig.rig", "BASE_Low Poly Man"]

    scene = bpy.context.scene
    for obj in data_to.objects:
        if obj is not None:
            scene.collection.objects.link(obj)

    male_arm = bpy.data.objects["Fig.rig"]
    male_body = bpy.data.objects["BASE_Low Poly Man"]
    male_arm.location = (0.0, 0.0, 0.0)
    male_arm.scale = (1.0, 1.0, 1.0)
    male_body.location = (0.0, 0.0, 0.0)
    male_body.scale = (1.0, 1.0, 1.0)
    # Clear any pose rotations just in case
    for pb in male_arm.pose.bones:
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)

    # Give male a neutral cool-gray flat material for clean comparison
    m_mat = make_flat_material("Extra_male_Ref_Mat", (0.52, 0.58, 0.66, 1.0))
    male_body.data.materials.clear()
    male_body.data.materials.append(m_mat)
    set_flat_shading(male_body.data)

    # Duplicate to create Extra_female + Extra_female_Body
    female_arm = male_arm.copy()
    female_arm.data = male_arm.data.copy()
    female_arm.name = "Extra_female"
    female_arm.data.name = "Extra_female_Rig"
    scene.collection.objects.link(female_arm)

    female_body = male_body.copy()
    female_body.data = male_body.data.copy()
    female_body.name = "Extra_female_Body"
    female_body.data.name = "Extra_female_Mesh"
    female_body.parent = female_arm
    for mod in female_body.modifiers:
        if mod.type == "ARMATURE":
            mod.object = female_arm
    scene.collection.objects.link(female_body)

    f_mat = make_flat_material("Extra_female_Mat", (0.86, 0.48, 0.56, 1.0))
    female_body.data.materials.clear()
    female_body.data.materials.append(f_mat)

    reshape_female(female_arm, female_body)
    hair_obj = build_lowpoly_ponytail(female_arm, female_body)

    # Save clean standalone blend containing ONLY Extra_female + Extra_female_Body + Extra_female_Hair
    scene.collection.objects.unlink(male_arm)
    scene.collection.objects.unlink(male_body)
    os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    print(f"[female_extra] saved standalone {OUT_BLEND}")

    # Re-link male and make a bald duplicate of female for 3-way visual comparison
    scene.collection.objects.link(male_arm)
    scene.collection.objects.link(male_body)

    female_bald_arm = female_arm.copy()
    female_bald_arm.data = female_arm.data.copy()
    female_bald_arm.name = "Extra_female_Bald"
    scene.collection.objects.link(female_bald_arm)

    female_bald_body = female_body.copy()
    female_bald_body.data = female_body.data.copy()
    female_bald_body.name = "Extra_female_Bald_Body"
    female_bald_body.parent = female_bald_arm
    for mod in female_bald_body.modifiers:
        if mod.type == "ARMATURE":
            mod.object = female_bald_arm
    scene.collection.objects.link(female_bald_body)

    render_comparison(male_arm, female_bald_arm, female_arm)
    print(f"[female_extra] QA renders saved in {RENDER_DIR}")


if __name__ == "__main__":
    main()
