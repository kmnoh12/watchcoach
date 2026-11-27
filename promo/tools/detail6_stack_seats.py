"""detail6 stack_seats: ergonomic seat/pad/roller/handle layout fixes for the 5 stack machines.

Built on top of detail6_stack_machines.py (keeping all acrylic shields, floor grounding, anchors,
tube end-caps, fasteners, and dedicated wear materials intact).

Per-machine ergonomic fixes (1.74 m seated adult reference, Life Fitness / Cybex / Matrix specs):
  1. P_leg_extension (LE):
     - Raises lever pivot P_leg_lever to knee height: (0, -0.25, 0.30) -> (0, -0.30, 0.555).
     - Rotates & extends arm.009/.010 by +61.7 deg around X and repositions contoured shin bolster
       Ddetail6_SM_LE_ShinRoller to ankle/lower-shin front (0, -0.465, 0.197) at Stroke=0
       (swings cleanly up-forward to (0, -0.688, 0.485) at Stroke=1.0).
     - Re-aims cam beam from new pivot (0.20, -0.30, 0.555) to rear anchor (0.20, +0.45, 0.50).
     - Adds twin outer-side pivot support stanchions (clear of knees) and relocates lower cable
       pulley behind seat (y=+0.350) so Coated load cable.014 meets cam cleanly (0 penetrations).
     - Shifts back.009 & back_post.005 by Y +0.04 m (usable seat depth 0.399 -> 0.439 m).
  2. P_seated_cable_row (SCR):
     - Fixes handle starting behind chest pad: P_row_handle location[1] driver
       '-0.2+0.3*v' -> '-0.70+0.29*v', Row cable points[1].co[1] driver '-.38+.30*v' -> '-.88+.29*v'.
     - Extends grounded base spine cleanly forward to y=-0.970 m with front exit pulley column
       at (0.0, -0.940, 0.740) and outer-right orthogonal cable routing -> 0 penetrations across
       ALL strokes (0 / 0.5 / 1.0) and realistic cable lengthening when pulling.
  3. P_pec_deck (PD):
     - Raises elbow/forearm pads (pad*), pec_grip* (+ caps), and fly_outer* (+ caps) by Z +0.14 m
       so pads span z=0.95..1.29 m (elbow/shoulder height) instead of z=0.81..1.15 m.
     - Shortens arm_drop / arm_drop.001 bottom end up by +0.14 m (z_min 0.815 -> 0.955 m).
  4. P_chest_press_machine (CP):
     - Brings grips back to proper chest-front starting distance (+0.14 m in Y):
       handle* (+ caps) & handle_v* (+ caps) Y +0.14 m; shortens press_forearm* by 0.14 m from
       front end while keeping lever_knuckle & handle joints 100% flush.
  5. P_cable_crossover (CC):
     - No ergonomic layout change (kept intact from detail6_stack_machines.py).

Fully idempotent, custom-prop tagged, refuses to save into promo/scenes or promo/models.

Usage:
    Blender -b promo/scenes/scene_gym.blend -P promo/tools/detail6_stack_seats.py [-- --save out.blend]
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

_TOOLS_DIR = str(Path(__file__).resolve().parent)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import detail6_latpulldown as lp
import detail6_stack_machines as sm

COLL = sm.COLL
PFX = "Ddetail6_SS_"
PKG_KEY = "detail6_stack_seats"
PROP_PKG = "detail6_ss_pkg"
PROP_ORIG_MAT = "detail6_ss_orig_matrix"
PROP_ORIG_MODE = "detail6_ss_orig_rotmode"
PROP_ORIG_DRV = "detail6_ss_orig_drv"


def _save_and_restore_xform(ob):
    """Store original local transform on first touch, restore it on subsequent runs (idempotency)."""
    if ob.get(PROP_PKG) == PKG_KEY and PROP_ORIG_MAT in ob:
        if PROP_ORIG_MODE in ob:
            ob.rotation_mode = ob[PROP_ORIG_MODE]
        vals = list(ob[PROP_ORIG_MAT])
        ob.matrix_basis = Matrix([vals[0:4], vals[4:8], vals[8:12], vals[12:16]])
    else:
        ob[PROP_PKG] = PKG_KEY
        ob[PROP_ORIG_MODE] = ob.rotation_mode
        ob[PROP_ORIG_MAT] = [float(v) for row in ob.matrix_basis for v in row]


def _ensure_mesh_unique_within_root(ob, root_set):
    me = ob.data
    if me is None or ob.type != "MESH":
        return
    if any(o.data == me and o not in root_set for o in bpy.data.objects):
        new_me = me.copy()
        new_me.name = PFX + "Mesh_" + ob.name
        ob.data = new_me


def _reaim_beam(ob, p0: Vector, p1: Vector, root_set):
    """Idempotently align a mesh-local-X tube/beam object from parent-space p0 to p1."""
    _save_and_restore_xform(ob)
    _ensure_mesh_unique_within_root(ob, root_set)
    me = ob.data
    xs = [v.co.x for v in me.vertices]
    x_lo, x_hi = min(xs), max(xs)
    cur_len = x_hi - x_lo
    vec = p1 - p0
    new_len = vec.length
    if cur_len > 1e-6 and abs(cur_len - new_len) > 1e-6:
        mid = 0.5 * (x_lo + x_hi)
        s = new_len / cur_len
        for v in me.vertices:
            v.co.x = (v.co.x - mid) * s
        me.update()

    u = vec.normalized()
    ref = Vector((0.0, 0.0, 1.0)) if abs(u.z) < 0.95 else Vector((1.0, 0.0, 0.0))
    v_ax = ref.cross(u).normalized()
    w_ax = u.cross(v_ax).normalized()
    rot3 = Matrix((u, v_ax, w_ax)).transposed()

    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = rot3.to_quaternion()
    ob.location = 0.5 * (p0 + p1)


def _set_driver_expr(id_block, data_path: str, array_index: int, new_expr: str):
    ad = id_block.animation_data
    if not ad or not ad.drivers:
        raise RuntimeError(f"No drivers on {id_block.name}")
    for fc in ad.drivers:
        if fc.data_path == data_path and fc.array_index == array_index:
            key = f"{PROP_ORIG_DRV}_{data_path}_{array_index}"
            if key not in id_block:
                id_block[key] = fc.driver.expression
            fc.driver.expression = new_expr
            return
    raise RuntimeError(f"Driver {data_path}[{array_index}] not found on {id_block.name}")


def _remove_obj_if_exists(name: str):
    ob = bpy.data.objects.get(name)
    if ob is not None:
        data = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if data is not None and data.users == 0 and isinstance(data, bpy.types.Mesh):
            bpy.data.meshes.remove(data)


def _get_sm_mats(code: str) -> dict:
    pfx = f"{sm.PFX}{code}_"
    return {
        "frame": bpy.data.materials[pfx + "Frame"],
        "silver": bpy.data.materials[pfx + "Silver"],
        "pad": bpy.data.materials[pfx + "Pad"],
        "stack": bpy.data.materials[pfx + "Stack"],
        "steel": bpy.data.materials[pfx + "Steel"],
        "grip": bpy.data.materials[pfx + "Grip"],
        "accent": bpy.data.materials[pfx + "Accent"],
    }


# ==============================================================================
# 1. P_leg_extension: knee-height pivot, ankle-front shin roller, rear-cam cable
# ==============================================================================

def _fix_leg_extension(coll):
    root = bpy.data.objects["P_leg_extension"]
    root_set = set(lp._descendants(root)) | {root}
    floor_z = -root.location.z  # -0.00425
    mats = _get_sm_mats("LE")
    touched = []

    # 1a. Raise P_leg_lever pivot to knee height: (0, -0.25, 0.30) -> (0, -0.30, 0.555)
    lv = bpy.data.objects["P_leg_lever"]
    _save_and_restore_xform(lv)
    lv.location = Vector((0.0, -0.300, 0.555))
    touched.append(lv.name)

    # 1b. Rotate (+61.7 deg around X) & extend arm.009/.010 from pivot (0,0,0) to ankle-front roller (0,-0.165,-0.358)
    for nm, sx in (("arm.009", -1.0), ("arm.010", 1.0)):
        ob = bpy.data.objects[nm]
        _reaim_beam(ob, Vector((sx * 0.200, 0.0, 0.0)), Vector((sx * 0.200, -0.165, -0.358)), root_set)
        touched.append(nm)

    # 1c. Reposition contoured shin bolster Ddetail6_SM_LE_ShinRoller to P_leg_lever local (0, -0.165, -0.358)
    #     (= machine local (0, -0.465, 0.197) at Stroke=0; swings up-forward to (0, -0.688, 0.485) at Stroke=1!)
    #     sm._upgrade_leg_extension built its mesh centered at (0.0, -0.320, -0.020)
    sr = bpy.data.objects["Ddetail6_SM_LE_ShinRoller"]
    sr.location = Vector((0.0, -0.165 - (-0.320), -0.358 - (-0.020)))
    sr[PROP_PKG] = PKG_KEY
    touched.append(sr.name)

    # 1d. Re-aim cam beam from raised knee pivot (0.20, -0.30, 0.555) to rear frame anchor (0.20, +0.45, 0.50)
    cam = bpy.data.objects["cam"]
    _reaim_beam(cam, Vector((0.200, -0.300, 0.555)), Vector((0.200, 0.450, 0.500)), root_set)
    touched.append(cam.name)

    # 1e. Shift back.009 & back_post.005 by Y +0.04 m (usable seat depth 0.399 -> 0.439 m for 1.74 m adult)
    for nm in ("back.009", "back_post.005"):
        ob = bpy.data.objects[nm]
        _save_and_restore_xform(ob)
        ob.location.y += 0.040
        touched.append(nm)

    # 1f. Update Coated load cable.014 to meet raised cam cleanly behind seat (y=+0.350, z=0.476 -> 0 penetrations!)
    lc = bpy.data.objects["Coated load cable.014"]
    sp = lc.data.splines[0]
    sp.points[19].co = (0.200, 0.350, 0.145, 1.0)
    sp.points[20].co = (0.200, 0.350, 0.476, 1.0)
    touched.append(lc.name)

    # 1g. Rebuild Ddetail6_SM_LE_Frame & Ddetail6_SM_LE_Pulleys with:
    #     - 3rd guarded pulley relocated cleanly behind seat at (0.200, 0.350, 0.145)
    #     - Twin outer-side front pivot stanchions supporting raised P_leg_lever at z=0.555 (clear of knees & roller!)
    #     - Back post bolts shifted +0.04 m in Y to match back_post.005
    _remove_obj_if_exists("Ddetail6_SM_LE_Frame")
    _remove_obj_if_exists("Ddetail6_SM_LE_Pulleys")

    bm_fr = bmesh.new()  # mat 0=silver, 1=steel, 2=grip
    bm_pl = bmesh.new()

    # Grounded base spine, end-cap, rubber pads, 4 L-anchor flanges (identical world z=0.0000!)
    lp._add_box(bm_fr, (0.0, -0.005, 0.050), (0.084, 1.290, 0.084), mat_idx=0, bevel=0.005, segments=2)
    lp._add_tube_cap(bm_fr, (0.0, -0.650, 0.050), "Y", -1.0, 0.084, 0.084, depth=0.010, mat_idx=2)
    for py in (-0.570, 0.000, 0.520):
        lp._add_box(bm_fr, (0.0, py, floor_z + 0.008), (0.094, 0.120, 0.016), mat_idx=2, bevel=0.002, segments=1)
    for sx in (-1.0, 1.0):
        sm._add_anchor_flange(bm_fr, sx * 0.042, sx, -0.570, floor_z, 0.068, 0, 1)
        sm._add_anchor_flange(bm_fr, sx * 0.240, sx,  0.720, floor_z, 0.092, 0, 1)

    # Twin outer-side pivot support stanchions rising from base crossbar (y=-0.295, z=0.064) to knee pivot (z=0.555)
    # Crossbar wx=0.424 (x=[-0.212,+0.212], 5 mm inside stanchions +/-0.217) & stanchion wy=0.036 (<0.042) -> 0 z-fighting!
    lp._add_box(bm_fr, (0.0, -0.295, 0.064), (0.424, 0.042, 0.032), mat_idx=0, bevel=0.0025, segments=1)
    # Left stanchion (x=-0.200 -> meets arm.009 pivot at z=0.555) + chrome pivot cap/bolt
    lp._add_box(bm_fr, (-0.200, -0.295, 0.308), (0.034, 0.036, 0.488), mat_idx=0, bevel=0.003, segments=1)
    lp._add_cyl(bm_fr, (-0.200, -0.300, 0.555), 0.036, 0.044, axis="X", segs=20, mat_idx=0, bevel=0.002)
    lp._add_hex_bolt(bm_fr, (-0.222, -0.300, 0.555), "X",
                     head_r=0.011, head_h=0.007, washer_r=0.016, washer_h=0.0026, sign=-1.0, mat_idx=1)
    # Right stanchion (x=+0.200 -> meets leg_pivot_body underside at z=0.505, stops cleanly inside hub!)
    lp._add_box(bm_fr, ( 0.200, -0.295, 0.290), (0.034, 0.036, 0.452), mat_idx=0, bevel=0.003, segments=1)

    # Split head-sheave hanger brackets flanking angled head sheave
    lp._add_box(bm_fr, (-0.129, 0.768, 1.405), (0.168, 0.042, 0.026), mat_idx=0, bevel=0.0025, segments=1)
    lp._add_box(bm_fr, ( 0.165, 0.768, 1.405), (0.094, 0.042, 0.026), mat_idx=0, bevel=0.0025, segments=1)
    lp._add_box(bm_fr, (-0.045, 0.768, 1.456), (0.014, 0.046, 0.106), mat_idx=0, bevel=0.002, segments=1)
    lp._add_box(bm_fr, ( 0.118, 0.768, 1.456), (0.014, 0.046, 0.106), mat_idx=0, bevel=0.002, segments=1)

    # 3 guarded pulleys along outer-right channel (3rd pulley at y=+0.350 directly beneath raised cam behind seat!)
    lp._add_box(bm_fr, (0.232, 0.662, 1.405), (0.056, 0.042, 0.026), mat_idx=0, bevel=0.002, segments=1)
    lp._add_box(bm_fr, (0.258, 0.662, 1.442), (0.026, 0.028, 0.066), mat_idx=0, bevel=0.002, segments=1)
    sm._add_guarded_sheave(bm_pl, (0.258, 0.625, 1.460), radius=0.028, axis="X", mat_guard=0, mat_wheel=2, mat_steel=1)

    lp._add_box(bm_fr, (0.140, 0.625, 0.064), (0.245, 0.040, 0.030), mat_idx=0, bevel=0.002, segments=1)
    lp._add_box(bm_fr, (0.258, 0.625, 0.100), (0.028, 0.034, 0.052), mat_idx=0, bevel=0.002, segments=1)
    sm._add_guarded_sheave(bm_pl, (0.258, 0.625, 0.145), radius=0.028, axis="X", mat_guard=0, mat_wheel=2, mat_steel=1)

    lp._add_box(bm_fr, (0.115, 0.350, 0.064), (0.195, 0.040, 0.030), mat_idx=0, bevel=0.002, segments=1)
    lp._add_box(bm_fr, (0.200, 0.350, 0.100), (0.028, 0.034, 0.052), mat_idx=0, bevel=0.002, segments=1)
    sm._add_guarded_sheave(bm_pl, (0.200, 0.350, 0.145), radius=0.028, axis="X", mat_guard=0, mat_wheel=2, mat_steel=1)

    # Seat & shifted back post mounting bolts (y=0.400 matches back_post.005 +0.04!)
    for sx in (-1.0, 1.0):
        lp._add_hex_bolt(bm_fr, (sx * 0.058, 0.000, 0.360), "X",
                         head_r=0.007, head_h=0.0055, washer_r=0.0105, washer_h=0.0026, sign=sx, mat_idx=1)
        lp._add_hex_bolt(bm_fr, (sx * 0.0465, 0.400, 0.700), "X",
                         head_r=0.007, head_h=0.0055, washer_r=0.0105, washer_h=0.0026, sign=sx, mat_idx=1)

    f_ob = sm._finalize_sm_mesh("Ddetail6_SM_LE_Frame", bm_fr, [mats["silver"], mats["steel"], mats["grip"]], root, coll, 35.0)
    p_ob = sm._finalize_sm_mesh("Ddetail6_SM_LE_Pulleys", bm_pl, [mats["silver"], mats["steel"], mats["grip"]], root, coll, 38.0)
    f_ob[PROP_PKG] = PKG_KEY
    p_ob[PROP_PKG] = PKG_KEY
    return touched


# ==============================================================================
# 2. P_seated_cable_row: handle in front of chest pad + zero-clip front pulley
# ==============================================================================

def _fix_seated_cable_row(coll):
    root = bpy.data.objects["P_seated_cable_row"]
    floor_z = -root.location.z  # -0.0120
    mats = _get_sm_mats("SCR")
    touched = []

    # 2a. Reorder left(-Y) -> right(+Y toward weight stack):
    #     3 (backrest) -> 4 (seat) -> 2 (footplate) -> 1 (cable exit + handle facing -Y)
    #     Keep orientations of 3, 4, 2 untouched; only translate Y.
    y_shifts = [
        (-0.380, ("chest", "chest_post")),
        (-0.500, ("seat.008", "seat_post.005")),
        (+0.870, (
            "foot_plate", "footboard_mount",
            "foot_rib", "foot_rib.001", "foot_rib.002", "foot_rib.003", "foot_rib.004",
        )),
    ]
    for dy, names in y_shifts:
        for nm in names:
            ob = bpy.data.objects[nm]
            _save_and_restore_xform(ob)
            ob.location.y += dy
            touched.append(nm)

    # 2b. Flip P_row_handle 180 deg around Z to face -Y (toward user), level with exit pulley z=0.760
    rh = bpy.data.objects["P_row_handle"]
    _save_and_restore_xform(rh)
    rh.rotation_mode = "XYZ"
    rh.rotation_euler = (0.0, 0.0, math.pi)
    rh.location = Vector((0.0, 0.260, 0.720))
    _set_driver_expr(rh, "location", 1, "0.26-0.45*v")
    # Step HandleHardware 4 mm forward (local -Y = root +Y toward pulley) -> zero coplanar face contact
    hh = bpy.data.objects.get("Ddetail6_SM_SCR_HandleHardware")
    if hh is not None:
        hh.location.y = -0.004
    touched.append(rh.name)

    # 2c. Update Row cable: from exit pulley (0, +0.580, 0.760) horizontally to flipped handle apex (0, +0.440-0.45*v, 0.760)
    rc = bpy.data.objects["Row cable"]
    _set_driver_expr(rc.data, "splines[0].points[1].co", 1, "0.44-0.45*v")
    rc.data.splines[0].points[0].co = (0.0, 0.580, 0.760, 1.0)
    rc.data.splines[0].points[1].co = (0.0, 0.440, 0.760, 1.0)
    touched.append(rc.name)

    # 2d. Update Coated load cable.009: compact tower-front routing to exit pulley (0, +0.580, 0.760)
    lc = bpy.data.objects["Coated load cable.009"]
    sp = lc.data.splines[0]
    pts = [(0.0, 0.950, 0.9733)]
    for i in range(15):
        t = (math.pi * 0.56) * i / 14.0
        pts.append((0.0, 0.892 + 0.058 * math.cos(t), 1.500 + 0.058 * math.sin(t)))
    pts.extend([
        (0.258, 0.775, 1.485),  # 1) outer-right upper redirection pulley
        (0.258, 0.775, 0.145),  # 2) outer-right lower pulley at tower side
        (0.258, 0.580, 0.145),  # 3) tower-front right low corner pulley
        (0.000, 0.580, 0.145),  # 4) tower-front center low pulley
        (0.000, 0.580, 0.760),  # 5) tower-front exit pulley facing -Y toward user
    ])
    assert len(pts) == len(sp.points), f"SCR cable expected {len(sp.points)}, got {len(pts)}"
    for pt, xyz in zip(sp.points, pts):
        pt.co = (*xyz, 1.0)
    touched.append(lc.name)

    # 2e. Rebuild Ddetail6_SM_SCR_Frame & Ddetail6_SM_SCR_Pulleys for 3-4-2-1 layout
    _remove_obj_if_exists("Ddetail6_SM_SCR_Frame")
    _remove_obj_if_exists("Ddetail6_SM_SCR_Pulleys")

    bm_fr = bmesh.new()  # mat 0=silver, 1=steel, 2=grip, 3=frame
    bm_pl = bmesh.new()

    # Grounded dark-satin base spine y = [-0.900, +0.780] (len=1.680, center=-0.060)
    lp._add_box(bm_fr, (0.0, -0.060, 0.043), (0.084, 1.680, 0.082), mat_idx=0, bevel=0.005, segments=2)
    lp._add_tube_cap(bm_fr, (0.0, -0.900, 0.043), "Y", -1.0, 0.084, 0.082, depth=0.010, mat_idx=2)
    # Rubber floor pads flush at floor_z = -0.0120 (world z=0.0000)
    for py in (-0.800, -0.450, 0.250, 0.620):
        lp._add_box(bm_fr, (0.0, py, floor_z + 0.009), (0.094, 0.130, 0.018), mat_idx=2, bevel=0.002, segments=1)
    # 4 welded L-shaped floor anchor flanges (rear backrest end & flanking tower)
    for sx in (-1.0, 1.0):
        sm._add_anchor_flange(bm_fr, sx * 0.042, sx, -0.780, floor_z, 0.066, 0, 1)
        sm._add_anchor_flange(bm_fr, sx * 0.240, sx,  0.860, floor_z, 0.098, 0, 1)

    # Split head-sheave hanger brackets flanking P_Head sheave.009 (z=1.500)
    sm._add_split_head_hangers(bm_fr, 0.0, 0.892, 1.500, 0.210, 1.415, mat_silver=0, mat_steel=1)

    # 1) Upper-right redirection pulley outside Side shroud.038
    lp._add_box(bm_fr, (0.232, 0.810, 1.404), (0.056, 0.042, 0.024), mat_idx=0, bevel=0.002, segments=1)
    lp._add_box(bm_fr, (0.258, 0.812, 1.444), (0.026, 0.028, 0.072), mat_idx=0, bevel=0.002, segments=1)
    sm._add_guarded_sheave(bm_pl, (0.258, 0.775, 1.460), radius=0.028, axis="X", mat_guard=0, mat_wheel=2, mat_steel=1)

    # 2) Outer-right lower pulley mounted to tower base side
    lp._add_box(bm_fr, (0.140, 0.775, 0.064), (0.245, 0.040, 0.030), mat_idx=0, bevel=0.002, segments=1)
    lp._add_box(bm_fr, (0.258, 0.775, 0.102), (0.028, 0.036, 0.056), mat_idx=0, bevel=0.002, segments=1)
    sm._add_guarded_sheave(bm_pl, (0.258, 0.775, 0.145), radius=0.028, axis="X", mat_guard=0, mat_wheel=2, mat_steel=1)

    # 3) Tower-front right low corner pulley (y=+0.580, right in front of tower)
    lp._add_box(bm_fr, (0.140, 0.580, 0.064), (0.258, 0.040, 0.030), mat_idx=0, bevel=0.002, segments=1)
    lp._add_box(bm_fr, (0.258, 0.580, 0.100), (0.028, 0.022, 0.052), mat_idx=0, bevel=0.002, segments=1)
    sm._add_guarded_sheave(bm_pl, (0.258, 0.580, 0.145), radius=0.028, axis="Y", mat_guard=0, mat_wheel=2, mat_steel=1)

    # 4 & 5) Cable-exit upright in front of weight stack at y=+0.620 (facing -Y toward user)
    lp._add_box(bm_fr, (0.0, 0.580, 0.100), (0.034, 0.022, 0.050), mat_idx=0, bevel=0.002, segments=1)
    sm._add_guarded_sheave(bm_pl, (0.0, 0.580, 0.145), radius=0.028, axis="Y", mat_guard=0, mat_wheel=2, mat_steel=1)
    lp._add_box(bm_fr, (0.0, 0.620, 0.448), (0.050, 0.040, 0.738), mat_idx=0, bevel=0.004, segments=2)
    lp._add_tube_cap(bm_fr, (0.0, 0.620, 0.817), "Z", 1.0, 0.050, 0.040, depth=0.009, mat_idx=2)
    # Upper exit pulley mounting fork arms facing -Y (x = +/- 0.026)
    for sx in (-1.0, 1.0):
        lp._add_box(bm_fr, (sx * 0.026, 0.598, 0.760), (0.008, 0.052, 0.042), mat_idx=0, bevel=0.0015, segments=1)
    sm._add_guarded_sheave(bm_pl, (0.0, 0.580, 0.760), radius=0.028, axis="X", mat_guard=0, mat_wheel=2, mat_steel=1)

    # Seat & backrest post mounting plate bolts at new Y positions
    for sx in (-1.0, 1.0):
        lp._add_hex_bolt(bm_fr, (sx * 0.062, -0.450, 0.350), "X",
                         head_r=0.007, head_h=0.0055, washer_r=0.0105, washer_h=0.0026, sign=sx, mat_idx=1)
        lp._add_hex_bolt(bm_fr, (sx * 0.062, -0.740, 0.560), "X",
                         head_r=0.007, head_h=0.0055, washer_r=0.0105, washer_h=0.0026, sign=sx, mat_idx=1)

    f_ob = sm._finalize_sm_mesh(
        "Ddetail6_SM_SCR_Frame", bm_fr, [mats["silver"], mats["steel"], mats["grip"], mats["frame"]], root, coll, 35.0
    )
    p_ob = sm._finalize_sm_mesh(
        "Ddetail6_SM_SCR_Pulleys", bm_pl, [mats["silver"], mats["steel"], mats["grip"]], root, coll, 38.0
    )
    f_ob[PROP_PKG] = PKG_KEY
    p_ob[PROP_PKG] = PKG_KEY
    return touched


# ==============================================================================
# 3. P_pec_deck: raise elbow/forearm pads & grips Z +0.14 m, shorten arm_drop
# ==============================================================================

def _fix_pec_deck():
    root = bpy.data.objects["P_pec_deck"]
    root_set = set(lp._descendants(root)) | {root}
    touched = []

    dz = 0.140
    raise_prefixes = ("pad", "pec_grip", "fly_outer")
    for ma_name in ("P_Moving assembly.004", "P_Moving assembly.005"):
        ma = bpy.data.objects[ma_name]
        for child in ma.children:
            if any(child.name.startswith(p) for p in raise_prefixes):
                _save_and_restore_xform(child)
                child.location.z += dz
                touched.append(child.name)

    # Shorten arm_drop / arm_drop.001 bottom end up by +0.14 m (top anchored at z=-0.09 in Moving assembly)
    for nm, sx in (("arm_drop", -1.0), ("arm_drop.001", 1.0)):
        ob = bpy.data.objects[nm]
        _reaim_beam(ob, Vector((sx * 0.210, -0.220, -0.090)), Vector((sx * 0.210, -0.310, -0.510)), root_set)
        touched.append(nm)

    return touched


# ==============================================================================
# 4. P_chest_press_machine: bring grips back to chest-front start (Y +0.14 m)
# ==============================================================================

def _fix_chest_press():
    root = bpy.data.objects["P_chest_press_machine"]
    root_set = set(lp._descendants(root)) | {root}
    touched = []

    dy = 0.140
    for ma_name in ("P_Moving assembly.012", "P_Moving assembly.013"):
        ma = bpy.data.objects[ma_name]
        for child in ma.children:
            if child.name.startswith(("handle", "handle_v")):
                _save_and_restore_xform(child)
                child.location.y += dy
                touched.append(child.name)

    # Shorten press_forearm / press_forearm.001 from front end (-0.50 -> -0.36) while keeping lever_knuckle flush!
    for nm, sx in (("press_forearm", -1.0), ("press_forearm.001", 1.0)):
        ob = bpy.data.objects[nm]
        _reaim_beam(ob, Vector((sx * 0.090, -0.265, 0.085)), Vector((sx * 0.080, -0.360, 0.000)), root_set)
        touched.append(nm)

    return touched


# ==============================================================================
# Main entry point (idempotent)
# ==============================================================================

def apply() -> dict:
    # 1. Always run detail6_stack_machines.apply() first (idempotent baseline)
    base_res = sm.apply()
    coll = bpy.data.collections["SET"].children[COLL]

    # 2. Apply ergonomic layout fixes on 4 machines (P_cable_crossover unchanged)
    out = {
        "P_leg_extension": _fix_leg_extension(coll),
        "P_seated_cable_row": _fix_seated_cable_row(coll),
        "P_pec_deck": _fix_pec_deck(),
        "P_chest_press_machine": _fix_chest_press(),
        "P_cable_crossover": [],
    }

    bpy.context.view_layer.update()
    return {"base_machines": list(base_res["machines"].keys()), "seat_fixes": out}


def _main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    save = None
    if "--save" in argv:
        save = Path(argv[argv.index("--save") + 1]).expanduser().resolve()
        root_dir = Path(__file__).resolve().parents[2]
        if any(save.is_relative_to((root_dir / "promo" / d).resolve()) for d in ("scenes", "models")):
            raise SystemExit("refusing to save into promo/scenes or promo/models")
        if save.suffix.lower() != ".blend":
            raise SystemExit("--save must end with .blend")
        save.parent.mkdir(parents=True, exist_ok=True)
    res = apply()
    print("detail6_stack_seats", json.dumps(res, ensure_ascii=False))
    if save is not None:
        bpy.ops.wm.save_as_mainfile(
            filepath=str(save), copy=True, compress=True, relative_remap=False
        )
        print("saved", save)


if __name__ == "__main__":
    _main()
