"""detail6 fix for P_plate_row: commercial Hammer Strength Iso-Lateral Row layout.

Fixes confirmed ergonomic and mechanical bugs on P_plate_row in scene_gym.blend:
  1. Footboards (footboard, footboard.001) had rotX = +25 deg (tilted away from
     the seated user so feet would slide off). Flipped to -30 deg and positioned
     cleanly below/ahead of the chest pad with connected footrest stays.
  2. Chest pad (chest.002) leaned back toward the user with its support post
     (post.002) protruding on the user's side (+Y). Tilted chest pad +10.3 deg
     forward and moved post.002 cleanly behind (-Y) the pad.
  3. Levers (P_row_lever_L / R) previously pivoted behind the chest pad near the
     seat (y=+0.30, z=0.80) with a crossbar through the user's torso, weight
     plates hanging beside/behind the user's hips (y=+0.63..1.07), and handles
     pointing away. Moved the iso-lateral pivot assembly (cross, bearing_support,
     iso_bearing_*, levers) to the front (y=-0.32, z=0.44):
       - pull_arm rises from the front pivot to comfortable chest-height handles
         in front of the chest pad at Stroke=0 (y=-0.24, z=0.92..1.10), pulling
         cleanly back beside the chest pad toward the ribs at Stroke=1
         (y=+0.05..0.11, z=0.76..0.82) via driver '0.0-0.70*v'.
       - neutral_grip stands vertically at the pull_arm tip; wide_grip extends
         horizontally inward with >4 cm clearance past the chest pad sides.
       - load_arm, balance_slug, peg, and cast_plate.021..024 extend forward
         (y=-0.72, z=0.46 at rest -> z=0.71 at Stroke=1), completely clear of
         the user's legs/hips and lifting upward on pull.
  4. Shifted side base rails (foot.013, foot.014) to y=-0.68..+0.72 and added
     floor-flush base crossbars and center spine (Ddetail6_PR_Base*) welded to
     post.002 and seat_post.007 so nothing floats.

Touches ONLY P_plate_row and its descendants. 100% idempotent.

Usage:
    Blender -b promo/scenes/scene_gym.blend -P promo/tools/detail6_fix_plate_row.py [-- --save out.blend]
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT_NAME = "P_plate_row"
TAG = "detail6_fix_plate_row"
TAG_VER = "v1"
PFX = "Ddetail6_PR_"

# Key layout constants in P_plate_row local space (floor is Z = -0.022)
FLOOR_Z = -0.022
BASE_H = 0.088          # base crossbar/spine height -> Z = -0.022 .. +0.066
BASE_W = 0.100
RAIL_Y_CENTER = 0.020   # foot.013/014 length 1.40 -> Y = -0.68 .. +0.72

PIVOT_X = 0.400
PIVOT_Y = -0.320
PIVOT_Z = 0.440
STROKE_EXPR = "0.0-0.70*v"

# Pull arm & grips in lever-local space
PULL_END = Vector((0.0, 0.080, 0.480))
NEUTRAL_Z0 = 0.474
NEUTRAL_Z1 = 0.686
NEUTRAL_ZC = 0.5 * (NEUTRAL_Z0 + NEUTRAL_Z1)  # 0.580 (matches mesh half-len 0.106)
WIDE_LEN = 0.155  # inner end at -side*0.155 -> root X = +-0.245 (>4 cm clear of chest pad +-0.20)

# Load arm & plates in lever-local space
LOAD_Y = -0.400
LOAD_Z = 0.020
LOAD_X_OFF = 0.040
SLUG_Y = -0.320
SLUG_Z = 0.016
PEG_X_OFF = 0.170
PLATE_X_OFFS = (0.220, 0.261)


def _tag(obj, note):
    obj[TAG] = TAG_VER
    obj[TAG + "_note"] = note


def _set_beam_endpoints(obj, p0, p1):
    """Reposition and resize an existing X-aligned box beam between p0 and p1."""
    v0 = Vector(p0)
    v1 = Vector(p1)
    diff = v1 - v0
    length = diff.length
    if length < 1e-6:
        raise ValueError(f"Zero-length beam for {obj.name}")
    half_len = 0.5 * length

    # Resize only local X extents of the 8-vert box, preserving Y/Z cross-section
    me = obj.data
    xs = [v.co.x for v in me.vertices]
    mid_x = 0.5 * (min(xs) + max(xs))
    bm = bmesh.new()
    bm.from_mesh(me)
    for v in bm.verts:
        v.co.x = half_len if v.co.x >= mid_x else -half_len
    bm.to_mesh(me)
    bm.free()
    me.update()

    obj.location = 0.5 * (v0 + v1)
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = diff.normalized().to_track_quat("X", "Z")
    obj.scale = (1.0, 1.0, 1.0)


def _ensure_box_child(root, name, center, size_xyz, mat):
    """Create or idempotently update an axis-aligned beveled frame box under root."""
    obj = bpy.data.objects.get(name)
    if obj is None:
        me = bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, me)
        for col in root.users_collection:
            col.objects.link(obj)
        obj.parent = root
    else:
        if obj.parent != root:
            obj.parent = root

    me = obj.data
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    sx, sy, sz = size_xyz
    for v in bm.verts:
        v.co.x *= sx
        v.co.y *= sy
        v.co.z *= sz
    bm.to_mesh(me)
    bm.free()
    me.update()

    if mat is not None:
        if len(me.materials) == 0:
            me.materials.append(mat)
        else:
            me.materials[0] = mat

    if "Bevel" not in obj.modifiers:
        bev = obj.modifiers.new("Bevel", "BEVEL")
        bev.width = 0.008
        bev.segments = 2
    if "WeightedNormal" not in obj.modifiers:
        wn = obj.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
        wn.keep_sharp = True

    obj.location = Vector(center)
    obj.rotation_mode = "XYZ"
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.scale = (1.0, 1.0, 1.0)
    _tag(obj, "base_frame_connector")
    return obj


def _set_lever_driver(lever_obj, expr):
    if not lever_obj.animation_data or not lever_obj.animation_data.drivers:
        raise RuntimeError(f"{lever_obj.name} has no drivers")
    updated = False
    for fc in lever_obj.animation_data.drivers:
        if fc.data_path == "rotation_euler" and fc.array_index == 0:
            fc.driver.expression = expr
            updated = True
    if not updated:
        raise RuntimeError(f"{lever_obj.name} missing rotation_euler[0] driver")


def _get_child(parent, name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise RuntimeError(f"Expected object {name!r} not found")
    # Verify ancestry under P_plate_row
    cur = obj.parent
    while cur is not None:
        if cur == parent:
            return obj
        cur = cur.parent
    raise RuntimeError(f"Object {name!r} is not a descendant of {parent.name!r}")


def apply() -> dict:
    root = bpy.data.objects.get(ROOT_NAME)
    if root is None:
        raise RuntimeError(f"{ROOT_NAME!r} not found in blend")

    # 1. Side base rails: shift forward to Y = -0.68 .. +0.72
    foot_l = _get_child(root, "foot.013")
    foot_r = _get_child(root, "foot.014")
    foot_l.location = (-0.550, RAIL_Y_CENTER, 0.040)
    foot_r.location = (0.550, RAIL_Y_CENTER, 0.040)
    _tag(foot_l, "shifted_base_rail")
    _tag(foot_r, "shifted_base_rail")

    frame_mat = foot_l.data.materials[0] if foot_l.data.materials else bpy.data.materials.get("E_frame")

    # 2. Floor-flush base connectors so post.002 & seat_post.007 never float
    base_zc = FLOOR_Z + 0.5 * BASE_H  # +0.022
    _ensure_box_child(
        root,
        PFX + "BaseCrossRear",
        center=(0.0, 0.500, base_zc),
        size_xyz=(1.100, BASE_W, BASE_H),
        mat=frame_mat,
    )
    _ensure_box_child(
        root,
        PFX + "BaseCrossFront",
        center=(0.0, -0.560, base_zc),
        size_xyz=(1.100, BASE_W, BASE_H),
        mat=frame_mat,
    )
    _ensure_box_child(
        root,
        PFX + "BaseSpine",
        center=(0.0, -0.030, base_zc),
        size_xyz=(BASE_W, 1.060, BASE_H),
        mat=frame_mat,
    )

    # 3. Seat & seat post (extend seat_post cleanly into base spine)
    seat = _get_child(root, "seat.010")
    seat.location = (0.0, 0.500, 0.440)
    seat.rotation_mode = "XYZ"
    seat.rotation_euler = (0.0, 0.0, 0.0)
    _tag(seat, "verified_seat")

    seat_post = _get_child(root, "seat_post.007")
    _set_beam_endpoints(seat_post, (0.0, 0.500, 0.020), (0.0, 0.500, 0.400))
    _tag(seat_post, "grounded_seat_post")

    # 4. Chest pad & chest post (tilt pad forward +10.3 deg, post behind pad on -Y side)
    chest = _get_child(root, "chest.002")
    chest.location = (0.0, 0.040, 0.940)
    chest.rotation_mode = "XYZ"
    chest.rotation_euler = (0.180, 0.0, 0.0)
    _tag(chest, "ergonomic_chest_pad")

    post = _get_child(root, "post.002")
    _set_beam_endpoints(post, (0.0, 0.020, 0.020), (0.0, -0.045, 0.940))
    _tag(post, "front_side_chest_post")

    # 5. Footboards & stays (face seated user with rotX = -30 deg)
    fb_names = ("footboard", "footboard.001")
    stay_names = ("footrest_stay.002", "footrest_stay.003")
    for side, fb_name, stay_name in ((-1, fb_names[0], stay_names[0]), (1, fb_names[1], stay_names[1])):
        fb = _get_child(root, fb_name)
        fb.location = (side * 0.350, -0.080, 0.210)
        fb.rotation_mode = "XYZ"
        fb.rotation_euler = (-math.radians(30.0), 0.0, 0.0)
        _tag(fb, "flipped_footboard_facing_seat")

        stay = _get_child(root, stay_name)
        _set_beam_endpoints(
            stay,
            (side * 0.520, -0.080, 0.050),
            (side * 0.350, -0.095, 0.195),
        )
        _tag(stay, "connected_footrest_stay")

    # 6. Front pivot crossbar, bearing supports, and bearing housings
    cross = _get_child(root, "cross")
    cross.location = (0.0, PIVOT_Y, PIVOT_Z - 0.020)
    cross.rotation_mode = "XYZ"
    cross.rotation_euler = (0.0, 0.0, 0.0)
    _tag(cross, "front_pivot_crossbar")

    sides_spec = (
        (
            -1,
            "P_row_lever_L",
            "bearing_support",
            "iso_bearing_body",
            "iso_bearing_cap",
            "iso_bearing_bolt",
            "pull_arm",
            "load_arm",
            "balance_slug",
            "peg.015",
            ("cast_plate.021", "cast_plate.022"),
            ("neutral_grip", "neutral_grip_cap1", "neutral_grip_cap2"),
            ("wide_grip.002", "wide_grip_cap1.002", "wide_grip_cap2.002"),
        ),
        (
            1,
            "P_row_lever_R",
            "bearing_support.001",
            "iso_bearing_body.001",
            "iso_bearing_cap.001",
            "iso_bearing_bolt.001",
            "pull_arm.001",
            "load_arm.001",
            "balance_slug.001",
            "peg.016",
            ("cast_plate.023", "cast_plate.024"),
            ("neutral_grip.001", "neutral_grip_cap1.001", "neutral_grip_cap2.001"),
            ("wide_grip.003", "wide_grip_cap1.003", "wide_grip_cap2.003"),
        ),
    )

    for (
        side,
        lever_name,
        bsup_name,
        bbody_name,
        bcap_name,
        bbolt_name,
        pull_name,
        load_name,
        slug_name,
        peg_name,
        plate_names,
        ngrip_names,
        wgrip_names,
    ) in sides_spec:
        bsup = _get_child(root, bsup_name)
        _set_beam_endpoints(
            bsup,
            (side * 0.550, PIVOT_Y - 0.050, 0.040),
            (side * 0.420, PIVOT_Y, PIVOT_Z),
        )
        _tag(bsup, "front_bearing_support")

        for bname in (bbody_name, bcap_name, bbolt_name):
            bobj = _get_child(root, bname)
            bobj.location = (side * PIVOT_X, PIVOT_Y, PIVOT_Z)
            bobj.rotation_mode = "XYZ"
            bobj.rotation_euler = (0.0, math.pi / 2.0, 0.0)
            _tag(bobj, "front_pivot_bearing")

        lever = _get_child(root, lever_name)
        lever.location = (side * PIVOT_X, PIVOT_Y, PIVOT_Z)
        lever.rotation_mode = "XYZ"
        lever.rotation_euler = (0.0, 0.0, 0.0)
        _set_lever_driver(lever, STROKE_EXPR)
        _tag(lever, "front_iso_lever")

        # Pull arm: up from front pivot to chest-height handle position
        pull = _get_child(lever, pull_name)
        _set_beam_endpoints(pull, (0.0, 0.0, 0.0), PULL_END)
        _tag(pull, "front_pull_arm")

        # Load arm: forward (-Y) from front pivot, lifts UP on pull
        load = _get_child(lever, load_name)
        _set_beam_endpoints(load, (0.0, 0.0, 0.0), (side * LOAD_X_OFF, LOAD_Y, LOAD_Z))
        _tag(load, "forward_load_arm")

        # Balance slug on load arm
        slug = _get_child(lever, slug_name)
        slug.location = (side * LOAD_X_OFF, SLUG_Y, SLUG_Z)
        slug.rotation_mode = "XYZ"
        slug.rotation_euler = (0.0, math.pi / 2.0, 0.0)
        _tag(slug, "forward_balance_slug")

        # Weight horn peg & cast plates (forward of machine, clear of user)
        peg = _get_child(lever, peg_name)
        peg.location = (side * PEG_X_OFF, LOAD_Y, LOAD_Z)
        peg.rotation_mode = "XYZ"
        peg.rotation_euler = (0.0, math.pi / 2.0, 0.0)
        _tag(peg, "forward_weight_peg")

        for pname, xoff in zip(plate_names, PLATE_X_OFFS):
            plate = _get_child(lever, pname)
            plate.location = (side * xoff, LOAD_Y, LOAD_Z)
            plate.rotation_mode = "XYZ"
            plate.rotation_euler = (0.0, 0.0, 0.0)
            _tag(plate, "forward_weight_plate")

        # Neutral (vertical) grip at top of pull arm
        ng, ng_c1, ng_c2 = (_get_child(lever, n) for n in ngrip_names)
        ng.location = (0.0, PULL_END.y, NEUTRAL_ZC)
        ng_c1.location = (0.0, PULL_END.y, NEUTRAL_Z0)
        ng_c2.location = (0.0, PULL_END.y, NEUTRAL_Z1)
        for o in (ng, ng_c1, ng_c2):
            o.rotation_mode = "XYZ"
            o.rotation_euler = (0.0, 0.0, 0.0)
            _tag(o, "vertical_neutral_grip")

        # Wide (horizontal pronated) grip extending inward, clear of chest pad
        wg, wg_c1, wg_c2 = (_get_child(lever, n) for n in wgrip_names)
        wg.location = (-side * 0.5 * WIDE_LEN, PULL_END.y, PULL_END.z)
        wg_c1.location = (0.0, PULL_END.y, PULL_END.z)
        wg_c2.location = (-side * WIDE_LEN, PULL_END.y, PULL_END.z)
        for o in (wg, wg_c1, wg_c2):
            o.rotation_mode = "XYZ"
            o.rotation_euler = (0.0, math.pi / 2.0, 0.0)
            _tag(o, "inward_wide_grip")

    _tag(root, "hammer_strength_iso_lateral_row_layout")
    bpy.context.view_layer.update()

    return {
        "root": ROOT_NAME,
        "version": TAG_VER,
        "pivot_local": [PIVOT_X, PIVOT_Y, PIVOT_Z],
        "stroke_expr": STROKE_EXPR,
        "footboard_rot_x_deg": -30.0,
        "chest_rot_x_deg": round(math.degrees(0.180), 2),
        "added_connectors": [
            PFX + "BaseCrossRear",
            PFX + "BaseCrossFront",
            PFX + "BaseSpine",
        ],
    }


def _main():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    save_path = None
    i = 0
    while i < len(argv):
        if argv[i] == "--save" and i + 1 < len(argv):
            save_path = argv[i + 1]
            i += 2
        else:
            i += 1

    res = apply()
    print("DETAIL6_FIX_PLATE_ROW:", json.dumps(res))
    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=save_path)
        print("SAVED:", save_path)


if __name__ == "__main__":
    _main()
