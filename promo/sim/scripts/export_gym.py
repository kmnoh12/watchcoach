"""Headless Blender 5.2 exporter for WatchCoach Interactive 3D Gym Simulator.

Reads (never modifies):
  - promo/scenes/scene_gym.blend
  - promo/models/v6.blend
  - promo/tools/reel_gym.py (for cap + headset)
  - promo/poses/pose_library.json
  - promo/poses/posing_animations.blend

Outputs to promo/sim/public/assets/:
  - gym_world.glb
  - gym_manifest.json
  - player_v6.glb
"""
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

SIM_DIR = Path(__file__).resolve().parents[1]
PROMO_DIR = SIM_DIR.parent
TOOLS_DIR = PROMO_DIR / "tools"
ASSETS_DIR = SIM_DIR / "public" / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(TOOLS_DIR))


def bl_to_three(v):
    """Convert Blender (x, y, z) Z-up to Three.js (x, z, -y) Y-up."""
    return [round(float(v[0]), 4), round(float(v[2]), 4), round(float(-v[1]), 4)]


def bl_dir_to_three(v):
    return [round(float(v[0]), 4), round(float(v[2]), 4), round(float(-v[1]), 4)]


def world_bbox(obj):
    pts = [obj.matrix_world @ Vector(b) for b in obj.bound_box]
    mn = [min(p[i] for p in pts) for i in range(3)]
    mx = [max(p[i] for p in pts) for i in range(3)]
    return mn, mx


def three_bbox_from_bl(mn, mx):
    # Blender (x, y, z) -> Three (x, z, -y)
    return {
        "min": [round(mn[0], 4), round(mn[2], 4), round(-mx[1], 4)],
        "max": [round(mx[0], 4), round(mx[2], 4), round(-mn[1], 4)],
    }


def setup_door_hinges():
    """Ensure the 4 main/suite doors have clean pivot empties for Y-up Z-axis rotation."""
    doors_meta = []

    def make_hinge(name, loc_bl):
        h = bpy.data.objects.new(name, None)
        h.empty_display_type = "PLAIN_AXES"
        h.location = Vector(loc_bl)
        bpy.context.scene.collection.objects.link(h)
        bpy.context.view_layer.update()
        return h

    def reparent_keep_world(obj, new_parent):
        mw = obj.matrix_world.copy()
        obj.parent = new_parent
        obj.matrix_parent_inverse = new_parent.matrix_world.inverted()
        obj.matrix_world = mw

    # 1. Main Entrance double glass doors
    main_ent = bpy.data.objects.get("Door_MainEntrance")
    if main_ent:
        h_l = make_hinge("SimHinge_MainEntrance_L", (-7.55, -6.29, 0.0))
        h_r = make_hinge("SimHinge_MainEntrance_R", (-7.55, -4.81, 0.0))
        for ch in list(main_ent.children):
            cy = ch.matrix_world.translation.y
            reparent_keep_world(ch, h_l if cy < -5.55 else h_r)
        doors_meta.append({
            "id": "main_entrance",
            "label": "헬스장 출입문",
            "hinges": [
                {"node": "SimHinge_MainEntrance_L", "openAngle": 1.45},
                {"node": "SimHinge_MainEntrance_R", "openAngle": -1.45},
            ],
            "pos": bl_to_three((-7.55, -5.55, 1.0)),
            "suite": None,
        })

    # 2-4. Posing Room, Men Locker, Women Locker
    room_doors = [
        ("posing_room", "포징룸 문", "Door_PosingRoom", "SimHinge_PosingRoom", (-1.865, -6.73, 0.0), 1.5, "posing",
         (-1.45, -6.73, 1.0), ["Room door leaf", "Room door kickplate", "Room door accent bar", "Door rosette", "Door stem", "Door lever", "Door rosette.001", "Door stem.001", "Door lever.001"]),
        ("men_locker", "남자 탈의실 문", "Door_MenLocker", "SimHinge_MenLocker", (10.535, -6.73, 0.0), 1.5, "men",
         (10.95, -6.73, 1.0), ["Room door leaf.001", "Room door kickplate.001", "Room door accent bar.001", "Door rosette.002", "Door stem.002", "Door lever.002", "Door rosette.003", "Door stem.003", "Door lever.003"]),
        ("women_locker", "여자 탈의실 문", "Door_WomenLocker", "SimHinge_WomenLocker", (11.835, -6.73, 0.0), 1.5, "women",
         (12.25, -6.73, 1.0), ["Room door leaf.002", "Room door kickplate.002", "Room door accent bar.002", "Door rosette.004", "Door stem.004", "Door lever.004", "Door rosette.005", "Door stem.005", "Door lever.005"]),
    ]

    for did, label, parent_name, hinge_name, hpos, open_ang, suite, pos_bl, leaf_names in room_doors:
        p = bpy.data.objects.get(parent_name)
        if not p:
            continue
        h = make_hinge(hinge_name, hpos)
        for ch in list(p.children):
            if ch.name in leaf_names or (
                not ch.name.startswith("Room door jamb")
                and not ch.name.startswith("Room door header")
                and "sign" not in ch.name.lower()
                and abs(ch.matrix_world.translation.y - hpos[1]) < 0.15
                and abs(ch.matrix_world.translation.x - pos_bl[0]) < 0.43
            ):
                reparent_keep_world(ch, h)
        doors_meta.append({
            "id": did,
            "label": label,
            "hinges": [{"node": hinge_name, "openAngle": open_ang}],
            "pos": bl_to_three(pos_bl),
            "suite": suite,
        })

    # Interior shower booth, cubicle, and WC doors (already have hinge empties!)
    interior_hinges = [
        ("men_booth_0", "남자 샤워부스 1", "Men Booth door hinge 0", 1.35, "men"),
        ("men_booth_1", "남자 샤워부스 2", "Men Booth door hinge 1", 1.35, "men"),
        ("men_booth_2", "남자 샤워부스 3", "Men Booth door hinge 2", 1.35, "men"),
        ("women_booth_0", "여자 샤워부스 1", "Women Booth door hinge 0", -1.35, "women"),
        ("women_booth_1", "여자 샤워부스 2", "Women Booth door hinge 1", -1.35, "women"),
        ("women_booth_2", "여자 샤워부스 3", "Women Booth door hinge 2", -1.35, "women"),
        ("men_cubicle_0", "남자 화장실 칸 1", "Men Cubicle door hinge 0", 1.35, "men"),
        ("men_cubicle_1", "남자 화장실 칸 2", "Men Cubicle door hinge 1", 1.35, "men"),
        ("women_cubicle_0", "여자 화장실 칸 1", "Women Cubicle door hinge 0", -1.35, "women"),
        ("women_cubicle_1", "여자 화장실 칸 2", "Women Cubicle door hinge 1", -1.35, "women"),
        ("men_wc", "남자 화장실 문", "Men WC door hinge", 1.35, "men"),
        ("women_wc", "여자 화장실 문", "Women WC door hinge", -1.35, "women"),
    ]
    for did, label, hname, open_ang, suite in interior_hinges:
        h = bpy.data.objects.get(hname)
        if not h:
            continue
        # Center of door trigger is slightly offset from hinge
        c_bl = h.matrix_world.translation.copy()
        if h.children:
            mn, mx = world_bbox(h.children[0])
            c_bl = Vector(((mn[0] + mx[0]) * 0.5, (mn[1] + mx[1]) * 0.5, 1.0))
        doors_meta.append({
            "id": did,
            "label": label,
            "hinges": [{"node": hname, "openAngle": open_ang}],
            "pos": bl_to_three(c_bl),
            "suite": suite,
            "initialRotZ": round(float(h.rotation_euler.z), 4),
        })

    return doors_meta


# Equipment mapping: Blender object name prefix -> (Korean label, clip name, stand offset in local space, facing yaw)
EQUIPMENT_SPECS = [
    ("P_treadmill", "러닝머신", "ex_treadmill_run", (0.0, 0.0, 0.06), 0.0),
    ("P_power_rack", "파워랙 스쿼트", "ex_squat", (0.0, 0.0, 0.0), 0.0),
    ("P_smith_machine", "스미스 머신", "ex_squat", (0.0, 0.1, 0.0), 0.0),
    ("P_cable_crossover", "케이블 크로스오버", "ex_cable_fly", (0.0, 0.0, 0.0), 0.0),
    ("P_functional_trainer", "펑셔널 트레이너", "ex_cable_fly", (0.0, -0.35, 0.0), 0.0),
    ("P_lat_pulldown", "랫 풀다운", "ex_lat_pulldown", (0.0, 0.25, 0.0), 0.0),
    ("P_seated_cable_row", "시티드 케이블 로우", "ex_seated_row", (0.0, 0.2, 0.0), 0.0),
    ("P_chest_press_machine", "체스트 프레스", "ex_chest_press", (0.0, -0.15, 0.0), 0.0),
    ("P_shoulder_press_machine", "숄더 프레스", "ex_shoulder_press", (0.0, -0.15, 0.0), 0.0),
    ("P_pec_deck", "펙 덱 플라이", "ex_pec_deck", (0.0, -0.15, 0.0), 0.0),
    ("P_lateral_raise_machine", "레터럴 레이즈", "ex_lateral_raise", (0.0, -0.1, 0.0), 0.0),
    ("P_assisted_pullup", "어시스트 풀업", "ex_pullup", (0.0, -0.1, 0.25), 0.0),
    ("P_dip_machine", "딥스 머신", "ex_dip", (0.0, -0.1, 0.0), 0.0),
    ("P_preacher_machine", "프리처 컬", "ex_bicep_curl", (0.0, -0.15, 0.0), 0.0),
    ("P_plate_row", "플레이트 로우", "ex_seated_row", (0.0, -0.15, 0.0), 0.0),
    ("P_tbar_row_machine", "티바 로우", "ex_seated_row", (0.0, -0.25, 0.0), 0.0),
    ("P_leg_press_45", "레그 프레스", "ex_leg_press", (0.0, 0.15, 0.15), 0.0),
    ("P_leg_extension", "레그 익스텐션", "ex_leg_extension", (0.0, -0.15, 0.0), 0.0),
    ("P_seated_leg_curl", "시티드 레그 컬", "ex_leg_curl", (0.0, -0.15, 0.0), 0.0),
    ("P_hip_abductor", "힙 어브덕션", "ex_hip_abductor", (0.0, -0.15, 0.0), 0.0),
    ("P_adjustable_bench", "인클라인 덤벨 프레스", "ex_bench_press", (0.0, 0.0, 0.0), 0.0),
    ("P_flat_bench", "플랫 벤치 프레스", "ex_bench_press", (0.0, 0.0, 0.0), 0.0),
]


def _ensure_box_uv(obj, scale=0.5):
    """Create simple world-aligned box UVs in [0..1] if missing."""
    if obj.type != "MESH" or not obj.data:
        return
    mesh = obj.data
    if mesh.uv_layers:
        return
    uv_layer = mesh.uv_layers.new(name="UVMap")
    mw = obj.matrix_world
    mn, mx = world_bbox(obj)
    span = [max(0.01, mx[i] - mn[i]) for i in range(3)]
    for poly in mesh.polygons:
        n = (mw.to_3x3() @ poly.normal)
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        for li in poly.loop_indices:
            v = mw @ mesh.vertices[mesh.loops[li].vertex_index].co
            if az >= ax and az >= ay:
                u = (v.x - mn[0]) / span[0]
                w = (v.y - mn[1]) / span[1]
            elif ax >= ay:
                u = (v.y - mn[1]) / span[1]
                w = (v.z - mn[2]) / span[2]
            else:
                u = (v.x - mn[0]) / span[0]
                w = (v.z - mn[2]) / span[2]
            uv_layer.data[li].uv = (u, w)


BAKE_MAT_NAMES = {
    "Gym_SpeckledRubber",
    "InfoRef_WarmWood",
    "Hallway_TerrazzoFloor",
    "Suite_LockerFloor",
    "Suite_MarbleFloor",
    "Suite_PorcelainFloor",
}


def _bake_procedural_materials():
    """Bake exact Blender procedural shaders (Color-only, 1 sample) into packed textures."""
    scene = bpy.context.scene
    prev_engine = scene.render.engine
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 1
    scene.render.bake.use_pass_direct = False
    scene.render.bake.use_pass_indirect = False
    scene.render.bake.use_pass_color = True
    scene.render.bake.margin = 4

    baked_imgs = []
    targets = []
    for o in list(bpy.data.objects):
        if o.type != "MESH" or not o.data or not o.data.materials:
            continue
        if any(m and m.name in BAKE_MAT_NAMES for m in o.data.materials):
            targets.append(o)

    print(f"[export_gym] Baking exact Blender procedural shaders for {len(targets)} objects...")
    for idx, o in enumerate(targets):
        # Make material unique per baked object so UVs don't overwrite each other
        if o.data.users > 1:
            o.data = o.data.copy()
        for slot in o.material_slots:
            if slot.material and slot.material.name in BAKE_MAT_NAMES:
                slot.material = slot.material.copy()
                m = slot.material
                nt = m.node_tree
                if not o.data.uv_layers:
                    # Use Smart UV Project for clean non-overlapping islands
                    bpy.ops.object.select_all(action="DESELECT")
                    o.select_set(True)
                    bpy.context.view_layer.objects.active = o
                    bpy.ops.object.mode_set(mode="EDIT")
                    bpy.ops.mesh.select_all(action="SELECT")
                    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.02)
                    bpy.ops.object.mode_set(mode="OBJECT")

                sz = 1024 if "RubberFloorTiles" in o.name else 512
                img = bpy.data.images.new(f"Bake_{o.name}_{idx}", width=sz, height=sz, alpha=False)
                tex_node = nt.nodes.new("ShaderNodeTexImage")
                tex_node.image = img
                nt.nodes.active = tex_node

                bpy.ops.object.select_all(action="DESELECT")
                o.select_set(True)
                bpy.context.view_layer.objects.active = o
                try:
                    bpy.ops.object.bake(type="DIFFUSE", use_clear=True)
                    img.pack()
                    baked_imgs.append(m.name)
                    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
                    if bsdf:
                        for lnk in list(bsdf.inputs["Base Color"].links):
                            nt.links.remove(lnk)
                        nt.links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
                except Exception as e:
                    print(f"[export_gym] Bake skipped on {o.name}: {e}")
                break

    scene.render.engine = prev_engine
    return set(baked_imgs)


def flatten_materials_for_gltf():
    """Bake key procedural materials and flatten remaining procedural links for glTF."""
    _bake_procedural_materials()

    for m in bpy.data.materials:
        if not m.use_nodes or not m.node_tree:
            continue
        nt = m.node_tree
        has_image = any(n.type == "TEX_IMAGE" and n.image is not None for n in nt.nodes)
        if has_image:
            # Disconnect procedural roughness/normal noise links that glTF ignores, keeping baked image
            bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if bsdf:
                for sock_name in ("Roughness", "Normal", "Metallic"):
                    s_in = bsdf.inputs.get(sock_name)
                    if s_in and s_in.is_linked:
                        for lnk in list(s_in.links):
                            nt.links.remove(lnk)
            continue

        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        emis = next((n for n in nt.nodes if n.type == "EMISSION"), None)

        if emis and not bsdf:
            col = tuple(emis.inputs[0].default_value[:4])
            strength = float(emis.inputs[1].default_value)
            nt.nodes.clear()
            out = nt.nodes.new("ShaderNodeOutputMaterial")
            p = nt.nodes.new("ShaderNodeBsdfPrincipled")
            p.inputs["Base Color"].default_value = col
            p.inputs["Roughness"].default_value = 0.25
            if "Emission Color" in p.inputs:
                p.inputs["Emission Color"].default_value = col
                p.inputs["Emission Strength"].default_value = min(strength, 8.0)
            nt.links.new(p.outputs["BSDF"], out.inputs["Surface"])
            continue

        if bsdf:
            bc_in = bsdf.inputs["Base Color"]
            if bc_in.is_linked:
                # Pick representative dark/mid color from ColorRamp if present, else default_value
                ramps = [n for n in nt.nodes if n.type == "VALTORGB"]
                chosen = tuple(bc_in.default_value[:4])
                if ramps and len(ramps[0].color_ramp.elements) > 0:
                    elems = ramps[0].color_ramp.elements
                    # Use the darker/primary element for rubber/asphalt/wood, or mid for marble
                    chosen = tuple(elems[-1].color[:4]) if "rubber" in m.name.lower() else tuple(elems[0].color[:4])
                for lnk in list(bc_in.links):
                    nt.links.remove(lnk)
                bc_in.default_value = chosen

            em_in = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
            if em_in and em_in.is_linked:
                ramps = [n for n in nt.nodes if n.type == "VALTORGB"]
                em_col = tuple(em_in.default_value[:4])
                if ramps and len(ramps[0].color_ramp.elements) > 0:
                    em_col = tuple(ramps[0].color_ramp.elements[0].color[:4])
                for lnk in list(em_in.links):
                    nt.links.remove(lnk)
                em_in.default_value = em_col
                if "mirror" in m.name.lower():
                    es_in = bsdf.inputs.get("Emission Strength")
                    if es_in:
                        es_in.default_value = 0.0

            # Disconnect procedural roughness/normal noise links that glTF ignores
            for sock_name in ("Roughness", "Normal", "Metallic"):
                s_in = bsdf.inputs.get(sock_name)
                if s_in and s_in.is_linked:
                    for lnk in list(s_in.links):
                        nt.links.remove(lnk)
            if bsdf.inputs["Roughness"].default_value < 0.04:
                bsdf.inputs["Roughness"].default_value = 0.04


def merge_static_meshes(protected_names):
    """Merge static meshes by (suite_tag, primary_material_name) to slash WebGL draw calls 50x."""
    groups = {}
    for o in list(bpy.data.objects):
        if o.type != "MESH":
            continue
        if o.name in protected_names:
            continue
        # Don't merge objects parented to a door hinge
        p = o.parent
        is_door_child = False
        while p:
            if p.name in protected_names or "hinge" in p.name.lower() or "door" in p.name.lower():
                is_door_child = True
                break
            p = p.parent
        if is_door_child:
            continue
        # Skip curves/modifiers issues by ensuring mesh data is single-user if needed
        cols = {c.name for c in o.users_collection}
        tag = "world"
        if "Annex - Men Suite" in cols:
            tag = "men"
        elif "Annex - Women Suite" in cols:
            tag = "women"
        elif "Annex - Posing Room" in cols:
            tag = "posing"

        mat_name = o.data.materials[0].name if (o.data.materials and o.data.materials[0]) else "__none__"
        # Only merge single-material meshes cleanly; multi-material meshes also merge fine in Blender
        key = (tag, mat_name)
        groups.setdefault(key, []).append(o)

    merged_suite_objects = {"men": [], "women": [], "posing": []}
    for (tag, mat_name), objs in groups.items():
        if len(objs) == 1:
            if tag in merged_suite_objects:
                merged_suite_objects[tag].append(objs[0].name)
            continue
        bpy.ops.object.select_all(action="DESELECT")
        valid = []
        for o in objs:
            if o.data and len(o.data.polygons) > 0:
                o.select_set(True)
                valid.append(o)
        if not valid:
            continue
        # Apply modifiers & make single-user data before join
        for o in valid:
            if o.data.users > 1:
                o.data = o.data.copy()
            if o.modifiers:
                bpy.context.view_layer.objects.active = o
                for mod in list(o.modifiers):
                    try:
                        bpy.ops.object.modifier_apply(modifier=mod.name)
                    except Exception:
                        pass
        bpy.context.view_layer.objects.active = valid[0]
        bpy.ops.object.join()
        joined = valid[0]
        joined.name = f"Merged_{tag}_{mat_name}"[:60]
        if tag in merged_suite_objects:
            merged_suite_objects[tag].append(joined.name)

    return merged_suite_objects


def export_gym_world():
    print("[export_gym] Loading scene_gym.blend...")
    bpy.ops.wm.open_mainfile(filepath=str(PROMO_DIR / "scenes" / "scene_gym.blend"))

    # Remove boolean cutters, mirror exclusions, lights, cameras, and probes so they don't export or block
    to_remove = []
    for o in list(bpy.data.objects):
        nl = o.name.lower()
        cols = {c.name for c in o.users_collection}
        if (
            "Gym Door Cutters" in cols
            or "Window light mirror exclusion" in cols
            or "CAST" in cols
            or "LOOK" in cols
            or "Selfie Guy" in o.name
            or "Cap and headphones" in o.name
            or (o.parent and "Cap and headphones" in o.parent.name)
            or "cutter" in nl
            or o.type in ("LIGHT", "CAMERA")
            or "probe" in nl
        ):
            to_remove.append(o)

    # Collect light metadata before removing lights
    lights_meta = []
    for o in bpy.data.objects:
        if o.type == "LIGHT":
            col = list(o.data.color)
            lights_meta.append({
                "name": o.name,
                "type": o.data.type,
                "pos": bl_to_three(o.matrix_world.translation),
                "color": [round(col[0], 3), round(col[1], 3), round(col[2], 3)],
                "energy": round(float(o.data.energy), 2),
            })

    doors_meta = setup_door_hinges()

    # Collect mirrors
    mirrors_meta = []
    mirror_specs = [
        ("Mirror", "main_mirror", (0.0, -1.0, 0.0), 18.0),
        ("Posing wall mirror 1", "posing_wall_1", (1.0, 0.0, 0.0), 8.0),
        ("Posing wall mirror 2", "posing_wall_2", (1.0, 0.0, 0.0), 8.0),
        ("Posing wall mirror 3", "posing_wall_3", (1.0, 0.0, 0.0), 8.0),
        ("Tilted mirror glass", "posing_tilted", (-0.85, 0.0, -0.52), 7.0),
        ("Stretch mirror glass", "stretch_mirror", (1.0, 0.0, 0.0), 10.0),
    ]
    for obj_name, mid, norm_bl, max_dist in mirror_specs:
        o = bpy.data.objects.get(obj_name)
        if not o:
            continue
        mn, mx = world_bbox(o)
        c_bl = [(mn[i] + mx[i]) * 0.5 for i in range(3)]
        sz_bl = [mx[i] - mn[i] for i in range(3)]
        half_thick = 0.5 * (sz_bl[0] if abs(norm_bl[0]) > 0.5 else sz_bl[1])
        mirrors_meta.append({
            "id": mid,
            "node": obj_name,
            "pos": bl_to_three(c_bl),
            "size": [round(sz_bl[0], 4), round(sz_bl[2], 4), round(sz_bl[1], 4)],
            "normal": bl_dir_to_three(norm_bl),
            "halfThickness": round(half_thick, 4),
            "maxDist": max_dist,
        })

    # Collect equipment stations
    equipment_meta = []
    for o in bpy.data.objects:
        matched = None
        for prefix, label, clip, offset, yaw_off in EQUIPMENT_SPECS:
            if o.name == prefix or o.name.startswith(prefix + "."):
                matched = (prefix, label, clip, offset, yaw_off)
                break
        if not matched:
            continue
        prefix, label, clip, offset, yaw_off = matched
        mw = o.matrix_world
        stand_bl = mw @ Vector(offset)
        yaw = float(o.rotation_euler.z) + yaw_off
        equipment_meta.append({
            "id": o.name,
            "label": label,
            "clip": clip,
            "pos": bl_to_three(mw.translation),
            "standPos": bl_to_three(stand_bl),
            "yaw": round(yaw, 4),
            "radius": 1.45,
        })

    # Collect showers (Men & Women Shower column 0..2)
    showers_meta = []
    for gender, label_prefix, x_stand_off in [("Men", "남자 샤워부스", -0.45), ("Women", "여자 샤워부스", 0.45)]:
        for idx in range(3):
            col_obj = bpy.data.objects.get(f"{gender} Shower column {idx}")
            if not col_obj:
                continue
            p = col_obj.matrix_world.translation
            head_bl = (p.x + x_stand_off * 0.65, p.y, 2.12)
            stand_bl = (p.x + x_stand_off, p.y - 0.1, 0.0)
            showers_meta.append({
                "id": f"{gender.lower()}_shower_{idx}",
                "label": f"{label_prefix} {idx + 1}",
                "headPos": bl_to_three(head_bl),
                "standPos": bl_to_three(stand_bl),
                "yaw": 1.5708 if gender == "Men" else -1.5708,
                "suite": gender.lower(),
            })

    # Collect toilets & urinals
    toilets_meta = []
    for idx in range(2):
        u = bpy.data.objects.get(f"Men Urinal {idx}")
        if u:
            p = u.matrix_world.translation
            toilets_meta.append({
                "id": f"men_urinal_{idx}",
                "label": "소변기 이용",
                "standPos": bl_to_three((p.x + 0.55, p.y, 0.0)),
                "yaw": -1.5708,
                "suite": "men",
            })
    # Cubicle toilets (Men & Women)
    cubicle_positions = [
        ("men_toilet_0", "화장실 이용", (8.94, -14.75, 0.0), 0.0, "men"),
        ("men_toilet_1", "화장실 이용", (7.92, -14.75, 0.0), 0.0, "men"),
        ("women_toilet_0", "화장실 이용", (14.26, -14.75, 0.0), 0.0, "women"),
        ("women_toilet_1", "화장실 이용", (15.28, -14.75, 0.0), 0.0, "women"),
    ]
    for tid, label, pos_bl, yaw, suite in cubicle_positions:
        toilets_meta.append({
            "id": tid,
            "label": label,
            "standPos": bl_to_three(pos_bl),
            "yaw": yaw,
            "suite": suite,
        })

    # Suite bounding boxes for culling when closed
    suite_boxes = {}
    for sname, col_name in [("men", "Annex - Men Suite"), ("women", "Annex - Women Suite"), ("posing", "Annex - Posing Room")]:
        col = bpy.data.collections.get(col_name)
        if not col:
            continue
        mn = [1e9, 1e9, 1e9]
        mx = [-1e9, -1e9, -1e9]
        for o in col.objects:
            if o.type != "MESH" or "cutter" in o.name.lower() or "probe" in o.name.lower():
                continue
            omn, omx = world_bbox(o)
            for i in range(3):
                mn[i] = min(mn[i], omn[i])
                mx[i] = max(mx[i], omx[i])
        suite_boxes[sname] = {
            "collection": col_name,
            "bounds": three_bbox_from_bl(mn, mx),
            "objects": [o.name for o in col.objects if o.type == "MESH" and "cutter" not in o.name.lower()],
        }

    # Build AABB colliders for walls, partitions, lockers, and equipment
    colliders = []
    skip_keywords = ["floor", "ceiling", "soffit", "cove", "downlight", "slab", "platform", "door leaf",
                     "glass door", "cubicle door", "booth door", "wc door", "mirror", "slogan", "neon",
                     "handwriting", "sticker", "drain", "vent", "hinge", "knob", "lever", "rosette", "stem",
                     "kickplate", "accent", "light", "mat ", "tray", "cable clip", "splice"]
    for o in bpy.data.objects:
        if o in to_remove or o.type != "MESH":
            continue
        nl = o.name.lower()
        if any(k in nl for k in skip_keywords):
            continue
        mn, mx = world_bbox(o)
        sx, sy, sz = mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2]
        # Only collide with torso-height obstacles (0.25m .. 1.35m) so overhead bars/arms don't block gaps
        if mx[2] < 0.25 or mn[2] > 1.35:
            continue
        if sx < 0.05 and sy < 0.05:
            continue
        if sx > 4.0 and sy > 4.0:
            continue
        # Slightly shrink AABB by 4cm so gaps between machines remain walkable
        mn = [mn[0] + 0.04, mn[1] + 0.04, mn[2]]
        mx = [mx[0] - 0.04, mx[1] - 0.04, mx[2]]
        if mn[0] >= mx[0] or mn[1] >= mx[1]:
            continue
        # Tag suite colliders
        cols = {c.name for c in o.users_collection}
        tag = "world"
        if "Annex - Men Suite" in cols:
            tag = "men"
        elif "Annex - Women Suite" in cols:
            tag = "women"
        elif "Annex - Posing Room" in cols:
            tag = "posing"
        colliders.append({
            "name": o.name,
            "tag": tag,
            **three_bbox_from_bl(mn, mx),
        })

    # Apply all BOOLEAN modifiers BEFORE removing DoorCutter_* objects so doorways are actually cut!
    for o in list(bpy.data.objects):
        if o.type != "MESH":
            continue
        bool_mods = [m for m in o.modifiers if m.type == "BOOLEAN"]
        if not bool_mods:
            continue
        bpy.context.view_layer.objects.active = o
        for m in bool_mods:
            try:
                bpy.ops.object.modifier_apply(modifier=m.name)
            except Exception as e:
                print(f"[export_gym] Warning: Boolean apply failed on {o.name}.{m.name}: {e}")

    # Remove unwanted objects before flattening
    for o in to_remove:
        bpy.data.objects.remove(o, do_unlink=True)

    flatten_materials_for_gltf()

    # Export gym_world.glb
    world_glb = ASSETS_DIR / "gym_world.glb"
    print(f"[export_gym] Exporting {world_glb}...")
    bpy.ops.export_scene.gltf(
        filepath=str(world_glb),
        export_format="GLB",
        export_yup=True,
        export_apply=True,
        export_materials="EXPORT",
        export_cameras=False,
        export_lights=False,
        export_animations=False,
    )

    posing_meta = []
    posing_json = PROMO_DIR / "poses" / "posing_animations.json"
    if posing_json.exists():
        pdata = json.loads(posing_json.read_text(encoding="utf-8"))
        for idx, (k, v) in enumerate(pdata.get("poses", {}).items(), start=1):
            posing_meta.append({"key": idx, "clip": k, "label": v.get("label", k)})

    manifest = {
        "spawn": {"pos": [0.0, 0.0, 0.5], "yaw": 0.0},
        "doors": doors_meta,
        "mirrors": mirrors_meta,
        "equipment": equipment_meta,
        "showers": showers_meta,
        "toilets": toilets_meta,
        "suites": suite_boxes,
        "posingClips": posing_meta,
        "lights": lights_meta,
        "colliders": colliders,
    }
    manifest_path = ASSETS_DIR / "gym_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[export_gym] Wrote {manifest_path} ({len(equipment_meta)} equipment, {len(doors_meta)} doors, {len(colliders)} colliders)")


# ------------------------------------------------------------------ Player V6 + Cap + Headset + Watch + Animations

def _pose_bones_from_dict(rig, bone_map):
    for pb in rig.pose.bones:
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    for bname, vals in bone_map.items():
        pb = rig.pose.bones.get(bname)
        if not pb:
            continue
        loc, quat = vals
        pb.location = Vector(loc)
        pb.rotation_quaternion = Quaternion(quat)


def _key_all_bones(rig, frame):
    for pb in rig.pose.bones:
        pb.keyframe_insert(data_path="location", frame=frame)
        pb.keyframe_insert(data_path="rotation_quaternion", frame=frame)


def _create_pose_loop_action(rig, name, keyframes_list):
    """keyframes_list: [(frame, bone_dict), ...]"""
    act = bpy.data.actions.new(name=name)
    rig.animation_data_create()
    rig.animation_data.action = act
    for frame, bdict in keyframes_list:
        _pose_bones_from_dict(rig, bdict)
        _key_all_bones(rig, frame)
    return act


def _make_procedural_clip(rig, name, frames_fn, total_frames=48):
    """frames_fn(t_norm) -> dict of {bone_name: (euler_deg_xyz_tuple, optional_pelvis_loc)}"""
    act = bpy.data.actions.new(name=name)
    rig.animation_data_create()
    rig.animation_data.action = act
    steps = [0, 12, 24, 36, 48] if total_frames == 48 else list(range(0, total_frames + 1, max(1, total_frames // 4)))
    if steps[-1] != total_frames:
        steps.append(total_frames)
    for f in steps:
        t = f / total_frames
        pose_spec = frames_fn(t)
        for pb in rig.pose.bones:
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        for bname, val in pose_spec.items():
            pb = rig.pose.bones.get(bname)
            if not pb:
                continue
            if isinstance(val, dict):
                if "loc" in val:
                    pb.location = Vector(val["loc"])
                if "rot" in val:
                    rx, ry, rz = val["rot"]
                    pb.rotation_quaternion = Euler((math.radians(rx), math.radians(ry), math.radians(rz)), "XYZ").to_quaternion()
            else:
                rx, ry, rz = val
                pb.rotation_quaternion = Euler((math.radians(rx), math.radians(ry), math.radians(rz)), "XYZ").to_quaternion()
        _key_all_bones(rig, f + 1)
    return act


def export_player_v6():
    print("[export_gym] Loading v6.blend...")
    bpy.ops.wm.open_mainfile(filepath=str(PROMO_DIR / "models" / "v6.blend"))
    bpy.context.scene.render.fps = 30

    # Remove non-character objects (ReviewCam, Sun)
    for o in list(bpy.data.objects):
        if o.type in ("CAMERA", "LIGHT"):
            bpy.data.objects.remove(o, do_unlink=True)

    rig = bpy.data.objects["V5_CommonRig"]
    body = bpy.data.objects["V5_Body"]

    # Build cap + headset using reel_gym.cap
    import reel_gym as RG
    cap_col = bpy.data.collections.new("PlayerHeadgear")
    bpy.context.scene.collection.children.link(cap_col)
    head_empty = bpy.data.objects.new("CapHeadAnchor", None)
    cap_col.objects.link(head_empty)
    head_empty.parent = rig
    head_empty.parent_type = "BONE"
    head_empty.parent_bone = "head"
    bpy.context.view_layer.update()
    head_empty.matrix_parent_inverse = head_empty.matrix_world.inverted()
    RG.cap(cap_col, head_empty)
    bpy.context.view_layer.update()

    # Bind cap/headset meshes to 'head' bone and Watch_* meshes to 'lowerarm_l' bone, then join into V5_Body
    def bind_to_bone(mesh_obj, bone_name):
        # Apply modifiers (e.g. BEVEL) before joining
        bpy.context.view_layer.objects.active = mesh_obj
        for m in list(mesh_obj.modifiers):
            if m.type != "ARMATURE":
                try:
                    bpy.ops.object.modifier_apply(modifier=m.name)
                except Exception:
                    pass
        mw = mesh_obj.matrix_world.copy()
        mesh_obj.parent = rig
        mesh_obj.parent_type = "OBJECT"
        mesh_obj.matrix_world = mw
        vg = mesh_obj.vertex_groups.get(bone_name) or mesh_obj.vertex_groups.new(name=bone_name)
        vg.add([v.index for v in mesh_obj.data.vertices], 1.0, "REPLACE")
        arm_mod = mesh_obj.modifiers.new("Armature", "ARMATURE")
        arm_mod.object = rig

    # Convert any CURVE objects in PlayerHeadgear (seams, stitching, headphone forks, W logo) to MESH
    for o in list(cap_col.objects):
        if o.type == "CURVE":
            bpy.ops.object.select_all(action="DESELECT")
            o.select_set(True)
            bpy.context.view_layer.objects.active = o
            bpy.ops.object.convert(target="MESH")

    headgear_meshes = [o for o in cap_col.objects if o.type == "MESH"]
    for m in headgear_meshes:
        bind_to_bone(m, "head")

    watch_meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("Watch_")]
    for m in watch_meshes:
        bind_to_bone(m, "lowerarm_l")

    # Join all character meshes into a single SkinnedMesh (V5_Body)
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    for m in headgear_meshes + watch_meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    body.name = "V5_Player"

    # Clean up temporary empties
    for o in list(bpy.data.objects):
        if o.type == "EMPTY" and o.name in ("CapHeadAnchor", "LowPolyWatch"):
            bpy.data.objects.remove(o, do_unlink=True)

    flatten_materials_for_gltf()

    # Load pose_library.json + posing_animations.json frame-1 stand (has clean inward finger curl on both hands!)
    pose_lib = json.loads((PROMO_DIR / "poses" / "pose_library.json").read_text(encoding="utf-8"))["poses"]
    posing_json = json.loads((PROMO_DIR / "poses" / "posing_animations.json").read_text(encoding="utf-8"))["poses"]
    p1_bones = posing_json["pose_front_double_biceps"]["keyframes"][0]["bones"]
    stand_bones = {bn: [v["loc"], v["quat"]] for bn, v in p1_bones.items()}
    finger_keys = {k: v for k, v in stand_bones.items() if any(k.startswith(f) for f in ("index_", "middle_", "ring_", "pinky_", "thumb_"))}

    def fix_fingers(bdict):
        out = {k: [list(v[0]), list(v[1])] for k, v in bdict.items()}
        for fk, fv in finger_keys.items():
            out[fk] = [list(fv[0]), list(fv[1])]
        return out

    actions_to_export = []

    # 1. stand (idle breathing loop)
    stand_breath = {k: [list(v[0]), list(v[1])] for k, v in stand_bones.items()}
    stand_breath["spine_02"] = [[0, 0, 0], [0.9998, -0.015, 0, 0]]
    actions_to_export.append(_create_pose_loop_action(rig, "stand", [(1, stand_bones), (30, stand_breath), (60, stand_bones)]))

    # 2. walk loop (walk_a -> walk_b -> walk_c -> walk_a)
    wa = fix_fingers(pose_lib["walk_a"]["bones"])
    wb = fix_fingers(pose_lib["walk_b"]["bones"])
    wc = fix_fingers(pose_lib["walk_c"]["bones"])
    actions_to_export.append(_create_pose_loop_action(rig, "walk", [(1, wa), (10, wb), (20, wc), (29, wa)]))

    # 3. run loop (run_a -> run_b -> run_a)
    ra = fix_fingers(pose_lib["run_a"]["bones"])
    rb = fix_fingers(pose_lib["run_b"]["bones"])
    actions_to_export.append(_create_pose_loop_action(rig, "run", [(1, ra), (10, rb), (19, ra)]))

    # 4. check_watch
    cw = pose_lib["check_watch"]["bones"]
    actions_to_export.append(_create_pose_loop_action(rig, "check_watch", [(1, stand_bones), (18, cw), (48, cw), (65, stand_bones)]))

    # 5. sit_phone
    sp = pose_lib["sit_phone"]["bones"]
    actions_to_export.append(_create_pose_loop_action(rig, "sit_phone", [(1, sp), (30, sp)]))

    # 6. IFBB Posing 8 clips from posing_animations.blend
    posing_blend = PROMO_DIR / "poses" / "posing_animations.blend"
    with bpy.data.libraries.load(str(posing_blend), link=False) as (src, dst):
        dst.actions = [n for n in src.actions if n.startswith("pose_")]
    for act in dst.actions:
        if act is not None:
            actions_to_export.append(act)

    # 7. Exercise & Facility clips (procedural 48-frame loops @ 30fps)
    s = lambda t: 0.5 - 0.5 * math.cos(t * math.tau)

    actions_to_export.append(_create_pose_loop_action(rig, "ex_treadmill_run", [(1, ra), (10, rb), (19, ra)]))

    actions_to_export.append(_make_procedural_clip(rig, "ex_squat", lambda t: {
        "pelvis": {"loc": (0, 0, -0.35 * s(t))},
        "spine_01": (15 * s(t), 0, 0),
        "thigh_l": (-78 * s(t), 0, 8), "thigh_r": (-78 * s(t), 0, -8),
        "calf_l": (88 * s(t), 0, 0), "calf_r": (88 * s(t), 0, 0),
        "upperarm_l": (-35, 0, 75), "upperarm_r": (-35, 0, -75),
        "lowerarm_l": (-95, 0, 0), "lowerarm_r": (-95, 0, 0),
    }))

    actions_to_export.append(_make_procedural_clip(rig, "ex_bench_press", lambda t: {
        "pelvis": {"loc": (0, 0.25, -0.52), "rot": (-82, 0, 0)},
        "upperarm_l": (-15 - 35 * s(t), 0, 55 - 25 * s(t)),
        "upperarm_r": (-15 - 35 * s(t), 0, -55 + 25 * s(t)),
        "lowerarm_l": (-75 + 60 * s(t), 0, 0),
        "lowerarm_r": (-75 + 60 * s(t), 0, 0),
        "thigh_l": (-55, 0, 10), "thigh_r": (-55, 0, -10),
        "calf_l": (75, 0, 0), "calf_r": (75, 0, 0),
    }))

    actions_to_export.append(_make_procedural_clip(rig, "ex_chest_press", lambda t: {
        "pelvis": {"loc": (0, 0, -0.32)},
        "thigh_l": (-85, 0, 6), "thigh_r": (-85, 0, -6),
        "calf_l": (85, 0, 0), "calf_r": (85, 0, 0),
        "upperarm_l": (-35 - 35 * s(t), 0, 62 - 38 * s(t)),
        "upperarm_r": (-35 - 35 * s(t), 0, -62 + 38 * s(t)),
        "lowerarm_l": (-78 + 62 * s(t), 0, 0),
        "lowerarm_r": (-78 + 62 * s(t), 0, 0),
    }))

    actions_to_export.append(_make_procedural_clip(rig, "ex_shoulder_press", lambda t: {
        "pelvis": {"loc": (0, 0, -0.32)},
        "thigh_l": (-85, 0, 6), "thigh_r": (-85, 0, -6),
        "calf_l": (85, 0, 0), "calf_r": (85, 0, 0),
        "upperarm_l": (-55 - 55 * s(t), 0, 70 - 30 * s(t)),
        "upperarm_r": (-55 - 55 * s(t), 0, -70 + 30 * s(t)),
        "lowerarm_l": (-88 + 75 * s(t), 0, 0),
        "lowerarm_r": (-88 + 75 * s(t), 0, 0),
    }))

    actions_to_export.append(_make_procedural_clip(rig, "ex_pec_deck", lambda t: {
        "pelvis": {"loc": (0, 0, -0.32)},
        "thigh_l": (-85, 0, 6), "thigh_r": (-85, 0, -6),
        "calf_l": (85, 0, 0), "calf_r": (85, 0, 0),
        "upperarm_l": (-60, 0, 75 - 65 * s(t)),
        "upperarm_r": (-60, 0, -75 + 65 * s(t)),
        "lowerarm_l": (-40, 0, -45),
        "lowerarm_r": (-40, 0, 45),
    }))

    actions_to_export.append(_make_procedural_clip(rig, "ex_lateral_raise", lambda t: {
        "pelvis": {"loc": (0, 0, -0.32)},
        "thigh_l": (-85, 0, 6), "thigh_r": (-85, 0, -6),
        "calf_l": (85, 0, 0), "calf_r": (85, 0, 0),
        "upperarm_l": (0, 0, 14 + 68 * s(t)),
        "upperarm_r": (0, 0, -14 - 68 * s(t)),
        "lowerarm_l": (-25, 0, 0), "lowerarm_r": (-25, 0, 0),
    }))

    actions_to_export.append(_make_procedural_clip(rig, "ex_lat_pulldown", lambda t: {
        "pelvis": {"loc": (0, 0, -0.34)},
        "thigh_l": (-85, 0, 6), "thigh_r": (-85, 0, -6),
        "calf_l": (85, 0, 0), "calf_r": (85, 0, 0),
        "spine_02": (-8 * s(t), 0, 0),
        "upperarm_l": (-135 + 75 * s(t), 0, 38 + 25 * s(t)),
        "upperarm_r": (-135 + 75 * s(t), 0, -38 - 25 * s(t)),
        "lowerarm_l": (-22 - 75 * s(t), 0, 0),
        "lowerarm_r": (-22 - 75 * s(t), 0, 0),
    }))

    actions_to_export.append(_make_procedural_clip(rig, "ex_seated_row", lambda t: {
        "pelvis": {"loc": (0, 0, -0.36)},
        "thigh_l": (-82, 0, 5), "thigh_r": (-82, 0, -5),
        "calf_l": (55, 0, 0), "calf_r": (55, 0, 0),
        "spine_02": (12 - 18 * s(t), 0, 0),
        "upperarm_l": (-68 + 65 * s(t), 0, 12),
        "upperarm_r": (-68 + 65 * s(t), 0, -12),
        "lowerarm_l": (-15 - 78 * s(t), 0, 0),
        "lowerarm_r": (-15 - 78 * s(t), 0, 0),
    }))

    actions_to_export.append(_make_procedural_clip(rig, "ex_cable_fly", lambda t: {
        "spine_01": (12, 0, 0),
        "thigh_l": (-15, 0, 4), "thigh_r": (12, 0, -4),
        "calf_l": (18, 0, 0),
        "upperarm_l": (-55, 0, 72 - 62 * s(t)),
        "upperarm_r": (-55, 0, -72 + 62 * s(t)),
        "lowerarm_l": (-28, 0, -25), "lowerarm_r": (-28, 0, 25),
    }))

    actions_to_export.append(_make_procedural_clip(rig, "ex_pullup", lambda t: {
        "pelvis": {"loc": (0, 0, 0.32 * s(t))},
        "upperarm_l": (-145 + 75 * s(t), 0, 35 + 25 * s(t)),
        "upperarm_r": (-145 + 75 * s(t), 0, -35 - 25 * s(t)),
        "lowerarm_l": (-20 - 82 * s(t), 0, 0),
        "lowerarm_r": (-20 - 82 * s(t), 0, 0),
        "calf_l": (45, 0, 0), "calf_r": (45, 0, 0),
    }))

    actions_to_export.append(_make_procedural_clip(rig, "ex_dip", lambda t: {
        "pelvis": {"loc": (0, 0, -0.24 * s(t))},
        "spine_01": (14 * s(t), 0, 0),
        "upperarm_l": (12 + 35 * s(t), 0, 22),
        "upperarm_r": (12 + 35 * s(t), 0, -22),
        "lowerarm_l": (-15 - 75 * s(t), 0, 0),
        "lowerarm_r": (-15 - 75 * s(t), 0, 0),
        "calf_l": (55, 0, 0), "calf_r": (55, 0, 0),
    }))

    actions_to_export.append(_make_procedural_clip(rig, "ex_bicep_curl", lambda t: {
        "pelvis": {"loc": (0, 0, -0.32)},
        "thigh_l": (-85, 0, 6), "thigh_r": (-85, 0, -6),
        "calf_l": (85, 0, 0), "calf_r": (85, 0, 0),
        "spine_01": (12, 0, 0),
        "upperarm_l": (-35, 0, 10), "upperarm_r": (-35, 0, -10),
        "lowerarm_l": (-18 - 95 * s(t), 0, 0),
        "lowerarm_r": (-18 - 95 * s(t), 0, 0),
    }))

    actions_to_export.append(_make_procedural_clip(rig, "ex_leg_press", lambda t: {
        "pelvis": {"loc": (0, 0, -0.38), "rot": (-38, 0, 0)},
        "thigh_l": (-65 - 45 * s(t), 0, 5), "thigh_r": (-65 - 45 * s(t), 0, -5),
        "calf_l": (15 + 75 * s(t), 0, 0), "calf_r": (15 + 75 * s(t), 0, 0),
        "upperarm_l": (-15, 0, 18), "upperarm_r": (-15, 0, -18),
    }))

    actions_to_export.append(_make_procedural_clip(rig, "ex_leg_extension", lambda t: {
        "pelvis": {"loc": (0, 0, -0.32)},
        "thigh_l": (-88, 0, 5), "thigh_r": (-88, 0, -5),
        "calf_l": (88 - 78 * s(t), 0, 0), "calf_r": (88 - 78 * s(t), 0, 0),
        "upperarm_l": (0, 0, 18), "upperarm_r": (0, 0, -18),
    }))

    actions_to_export.append(_make_procedural_clip(rig, "ex_leg_curl", lambda t: {
        "pelvis": {"loc": (0, 0, -0.32)},
        "thigh_l": (-88, 0, 5), "thigh_r": (-88, 0, -5),
        "calf_l": (15 + 75 * s(t), 0, 0), "calf_r": (15 + 75 * s(t), 0, 0),
        "upperarm_l": (0, 0, 18), "upperarm_r": (0, 0, -18),
    }))

    actions_to_export.append(_make_procedural_clip(rig, "ex_hip_abductor", lambda t: {
        "pelvis": {"loc": (0, 0, -0.32)},
        "thigh_l": (-88, 0, 6 + 32 * s(t)), "thigh_r": (-88, 0, -6 - 32 * s(t)),
        "calf_l": (85, 0, 0), "calf_r": (85, 0, 0),
        "upperarm_l": (0, 0, 16), "upperarm_r": (0, 0, -16),
    }))

    # 8. Facility clips: shower_wash & toilet_use
    actions_to_export.append(_make_procedural_clip(rig, "shower_wash", lambda t: {
        "head": (-14 + 6 * math.sin(t * math.tau), 0, 8 * math.sin(t * math.tau)),
        "upperarm_l": (-65 - 15 * math.sin(t * math.tau), 0, 28),
        "upperarm_r": (-65 + 15 * math.sin(t * math.tau), 0, -28),
        "lowerarm_l": (-95, 0, -20),
        "lowerarm_r": (-95, 0, 20),
    }))

    actions_to_export.append(_make_procedural_clip(rig, "toilet_use", lambda t: {
        "spine_01": (6 + 3 * s(t), 0, 0),
        "head": (12, 0, 0),
        "upperarm_l": (-18, 0, 10),
        "upperarm_r": (-18, 0, -10),
        "lowerarm_l": (-35, 0, -15),
        "lowerarm_r": (-35, 0, 15),
    }))

    # Push all actions onto NLA tracks so glTF exports every single animation clip
    rig.animation_data_create()
    rig.animation_data.action = None
    for act in actions_to_export:
        track = rig.animation_data.nla_tracks.new()
        track.name = act.name
        strip = track.strips.new(act.name, 1, act)
        strip.name = act.name

    player_glb = ASSETS_DIR / "player_v6.glb"
    print(f"[export_gym] Exporting {player_glb} ({len(actions_to_export)} animations)...")
    bpy.ops.export_scene.gltf(
        filepath=str(player_glb),
        export_format="GLB",
        export_yup=True,
        export_apply=True,
        export_materials="EXPORT",
        export_animations=True,
        export_nla_strips=True,
        export_nla_strips_merged_animation_name="Animation",
        export_animation_mode="NLA_TRACKS",
        export_def_bones=False,
    )
    print("[export_gym] Done!")


if __name__ == "__main__":
    export_gym_world()
    export_player_v6()
