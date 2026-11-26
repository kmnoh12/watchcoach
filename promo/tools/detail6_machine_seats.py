"""detail6 machine seats: put seats, pads, rollers and handles where a real user meets them.

Audit (work/detail6/machine_seats/REPORT.md) found these user-contact layouts wrong in
promo/scenes/scene_gym.blend. Each fix keeps the machine origin/location/rotation, the
existing drivers (Stroke / Pin row / Bench adjustment) and the shared E_* materials.
Moving levers are re-posed by changing the rest pose of their children (or the
un-driven location of their bearing empty), never by removing drivers.

  * P_adjustable_bench   back-pad driver rested at -45 deg (pad declined through the
                         floor); range becomes 0..85 deg, shown at 75 deg (seated press).
  * P_leg_press_45       footplate was parallel to the rails (feet pushed sideways) ->
                         turned 90 deg to face the user along the travel; back pad leaned
                         toward the sled -> reclined away; seat was 1.35 m from the plate
                         -> seat unit moved down to the rail foot (hip-plate 0.62 m).
  * P_preacher_machine   arm pad sloped up away from the user -> slopes down away from
                         the armpit; lever axis moved from 0.2 m above/behind the pad to
                         the elbow; hubs outboard of the pad on both sides.
  * P_hip_abductor       knee pads sat beside the seat 0.23 m outboard of the thighs ->
                         at the outside of the knees; foot pegs under the shins.
  * P_lateral_raise_machine  pivot 0.2 m above the shoulder and elbow pads 0.3 m outboard
                         -> pivot lowered to shoulder height behind the back pad, pads hang
                         against the outside of the elbows.
  * P_seated_leg_curl    pivot 0.2 m below the knee, roller mid-shin, thigh pad inside the
                         thigh -> pivot on the knee axis, roller under the ankle, thigh pad
                         on top of the thigh.
  * P_shoulder_press_machine  handles started 0.36 m in front of the shoulders -> rest
                         pose turned back so they start just above/in front of the shoulders.
  * P_tbar_row_machine   chest pad was knee-high for a standing user -> short pad at
                         chest height for the foot-rest stance, handles under the shoulders.
  * P_dip_machine        grips started 0.25-0.40 m in front of the hips -> beside the torso.

Not touched (owned by other workers): P_lat_pulldown, P_cable_crossover,
P_seated_cable_row, P_chest_press_machine, P_pec_deck, P_leg_extension.

apply() is idempotent: each fixed machine root gets root["detail6_machine_seats"]; a
second run skips it. Every changed/new object is tagged ob["detail6_ms"].

Usage:
    Blender -b promo/scenes/scene_gym.blend -P promo/tools/detail6_machine_seats.py [-- --save out.blend]
"""
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

TAG = "detail6_machine_seats"
OBTAG = "detail6_ms"
VER = "v1"
TOL = 0.012
LOG = []


# ----------------------------------------------------------------------------- helpers
def _root(name):
    return bpy.data.objects[name]


def _kid(root, name):
    for o in root.children_recursive:
        if o.name == name:
            return o
    raise KeyError(f"{root.name}: missing {name}")


def _upd():
    bpy.context.view_layer.update()


def _loc(root, ob):
    """Object world matrix expressed in machine-local space."""
    return root.matrix_world.inverted() @ ob.matrix_world


def _bbox(root, ob):
    M = _loc(root, ob)
    if ob.type == "MESH":
        pts = [M @ v.co for v in ob.data.vertices]
    else:
        pts = [M.translation]
    return (Vector([min(p[i] for p in pts) for i in range(3)]),
            Vector([max(p[i] for p in pts) for i in range(3)]))


def _center(root, ob):
    a, b = _bbox(root, ob)
    return (a + b) / 2


def _expect(root, ob, lo, hi):
    a, b = _bbox(root, ob)
    for i in range(3):
        if abs(a[i] - lo[i]) > TOL or abs(b[i] - hi[i]) > TOL:
            raise RuntimeError(f"{root.name}/{ob.name}: unexpected layout {tuple(round(x, 3) for x in a)}"
                               f"..{tuple(round(x, 3) for x in b)}; expected {lo}..{hi}")


def _no_drivers(ob, paths=("location", "rotation_euler", "rotation_quaternion", "scale")):
    ad = ob.animation_data
    if ad and any(fc.data_path in paths for fc in ad.drivers):
        raise RuntimeError(f"{ob.name} has transform drivers; refusing to move it")


def _tag(ob, what):
    ob[OBTAG] = f"{VER}:{what}"


def _record(root, ob, what, before):
    after = _bbox(root, ob)
    LOG.append({"machine": root.name, "object": ob.name, "change": what,
                "before": [[round(x, 3) for x in before[0]], [round(x, 3) for x in before[1]]],
                "after": [[round(x, 3) for x in after[0]], [round(x, 3) for x in after[1]]]})
    _tag(ob, what)


def _xform(root, ob, T, what):
    """Rigidly move an (un-driven) object by T given in machine-local space; children follow."""
    pure_move = all(abs(T[i][j] - (1.0 if i == j else 0.0)) < 1e-9 for i in range(3) for j in range(3))
    _no_drivers(ob, ("location",) if pure_move else ("location", "rotation_euler", "rotation_quaternion", "scale"))
    before = _bbox(root, ob)
    Mr = root.matrix_world
    ob.matrix_world = Mr @ T @ Mr.inverted() @ ob.matrix_world
    _upd()
    _record(root, ob, what, before)


def _mesh_xform(root, ob, T, what):
    """Bake a machine-local affine T into the mesh (keeps the object transform)."""
    if ob.data.users != 1:
        raise RuntimeError(f"{ob.name}: mesh {ob.data.name} is shared ({ob.data.users} users)")
    before = _bbox(root, ob)
    W = ob.matrix_world
    Mr = root.matrix_world
    L = W.inverted() @ Mr @ T @ Mr.inverted() @ W
    ob.data.transform(L)
    if L.to_3x3().determinant() < 0:
        ob.data.flip_normals()
    ob.data.update()
    _upd()
    _record(root, ob, what, before)


def _segment(root, ob):
    """Axis end points (machine-local) of a beam (local X) or rod (local Z) mesh."""
    vs = [v.co for v in ob.data.vertices]
    ext = [max(v[i] for v in vs) - min(v[i] for v in vs) for i in range(3)]
    ax = 0 if ext[0] >= ext[2] else 2
    c = Vector([(max(v[i] for v in vs) + min(v[i] for v in vs)) / 2 for i in range(3)])
    a, b = c.copy(), c.copy()
    a[ax] = min(v[ax] for v in vs)
    b[ax] = max(v[ax] for v in vs)
    M = _loc(root, ob)
    return M @ a, M @ b


def _seg_T(a0, b0, a1, b1):
    """Affine map taking segment a0-b0 onto a1-b1 (minimal rotation, stretch along axis only)."""
    d0, d1 = (b0 - a0), (b1 - a1)
    q = d0.normalized().rotation_difference(d1.normalized()).to_matrix().to_4x4()
    n = d1.normalized()
    s = d1.length / d0.length
    S = Matrix.Identity(4)
    for i in range(3):
        for j in range(3):
            S[i][j] += (s - 1.0) * n[i] * n[j]
    return Matrix.Translation(a1) @ S @ q @ Matrix.Translation(-a0)


def _retarget(root, ob, a1, b1, what):
    a0, b0 = _segment(root, ob)
    # keep the end order closest to the requested one
    if (a0 - Vector(a1)).length + (b0 - Vector(b1)).length > (b0 - Vector(a1)).length + (a0 - Vector(b1)).length:
        a0, b0 = b0, a0
    _mesh_xform(root, ob, _seg_T(a0, b0, Vector(a1), Vector(b1)), what)


def _rot_about(pivot, axis, deg):
    p = Vector(pivot)
    return Matrix.Translation(p) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-p)


def _T(v):
    return Matrix.Translation(Vector(v))


def _scale_along(center, axis_vec, s):
    n = Vector(axis_vec).normalized()
    S = Matrix.Identity(4)
    for i in range(3):
        for j in range(3):
            S[i][j] += (s - 1.0) * n[i] * n[j]
    c = Vector(center)
    return Matrix.Translation(c) @ S @ Matrix.Translation(-c)


def _local_axis(root, ob, i):
    return (_loc(root, ob).to_3x3() @ Vector([1.0 if k == i else 0.0 for k in range(3)])).normalized()


def _dup(root, ob, name, what):
    """Single-user copy of a mesh object under the same parent (for a mirrored hub/strut)."""
    new = ob.copy()
    new.data = ob.data.copy()
    new.name = name
    for c in ob.users_collection:
        c.objects.link(new)
    new.parent = ob.parent
    new.matrix_parent_inverse = ob.matrix_parent_inverse.copy()
    new.matrix_basis = ob.matrix_basis.copy()
    if new.animation_data:
        new.animation_data_clear()
    for k in list(new.keys()):
        if k.startswith("detail6_ms"):
            del new[k]
    _upd()
    _tag(new, what)
    LOG.append({"machine": root.name, "object": name, "change": what, "new": True})
    return new


def _curve_end(root, ob, new_xyz, what, index=-1, via=None):
    sp = ob.data.splines[0]
    if via is not None:                       # add one routing point before the end
        sp.points.add(1)
        last, prev = sp.points[-1], sp.points[-2]
        last.co = prev.co.copy()
        prev.co = (*(_loc(root, ob).inverted() @ Vector(via)), prev.co.w)
    pt = sp.points[index]
    M = _loc(root, ob)
    old = M @ pt.co.xyz
    if ob.data.animation_data:
        for fc in ob.data.animation_data.drivers:
            if fc.data_path.startswith(f"splines[0].points[{len(sp.points) + index if index < 0 else index}]"):
                raise RuntimeError(f"{ob.name}: point {index} is driven")
    pt.co = (*(M.inverted() @ Vector(new_xyz)), pt.co.w)
    ob.data.update_tag()
    _upd()
    _tag(ob, what)
    LOG.append({"machine": root.name, "object": ob.name, "change": what,
                "before": [[round(x, 3) for x in old]], "after": [[round(x, 3) for x in new_xyz]]})


def _done(root):
    return root.get(TAG) == VER


def _seal(root):
    root[TAG] = VER


# ----------------------------------------------------------------------------- machines
def fix_adjustable_bench():
    """FID bench: Bench adjustment 0 rested at -45 deg (pad through the floor, z -0.10)."""
    r = _root("P_adjustable_bench")
    if _done(r):
        return "skip"
    pv = _kid(r, "P_adj_back")
    fc = next(f for f in pv.animation_data.drivers if f.data_path == "rotation_euler" and f.array_index == 0)
    if not fc.driver.expression.startswith("-0.785"):
        raise RuntimeError("adjustable bench driver not in the expected state: " + fc.driver.expression)
    before = _bbox(r, _kid(r, "back.002"))
    old = fc.driver.expression
    full = math.radians(85.0)
    fc.driver.expression = f"0.0+{full!r}*v"           # flat .. 85 deg upright
    # the ladder under the pad (rails rising 40 deg) only clears the back frame from ~70 deg;
    # show the seated-press position (75 deg) rather than a pose that cuts through the ladder
    r["Bench adjustment"] = 75.0 / 85.0
    pv.rotation_euler.x = math.radians(75.0)
    r.update_tag()
    _upd()
    back = _kid(r, "back.002")
    _record(r, back, "back pad incline -45 -> +75 deg (seated press)", before)
    _tag(pv, f"driver {old} -> {fc.driver.expression}; Bench adjustment 0 -> {75/85:.4f}")
    LOG.append({"machine": r.name, "object": pv.name, "change": f"driver {old} -> {fc.driver.expression}"})
    _seal(r)
    return "fixed"


def fix_leg_press_45():
    r = _root("P_leg_press_45")
    if _done(r):
        return "skip"
    sled = _kid(r, "P_sled")
    o = _loc(r, sled).translation.copy()                 # sled origin at stroke 0 (0,-0.6,0.62)
    if (o - Vector((0, -0.6, 0.62))).length > TOL:
        raise RuntimeError("leg press sled not at rest position")
    plate = _kid(r, "footplate")
    _expect(r, plate, (-0.455, -0.829, 0.391), (0.455, -0.371, 0.849))
    up = Vector((0, math.sqrt(.5), math.sqrt(.5)))       # toward the user and up, normal to the rails
    off = 0.305 + 0.060                                   # plate edge welded into the axle corner
    T = _T(up * off) @ _rot_about(o, "X", -90.0) @ _scale_along(o, (1, 0, 0), 0.835)
    ribs = [ob for ob in sled.children if ob.name.startswith("traction_rib")]
    for ob in [plate] + ribs:
        _mesh_xform(r, ob, T, "footplate turned to face the user along the sled travel")

    # seat unit: seat at the rail foot, back reclined away from the sled
    seat = _kid(r, "seat.007")
    _expect(r, seat, (-0.23, 0.39, 0.15), (0.23, 0.85, 0.25))
    _xform(r, seat, _T((0, -0.64, 0.11)), "seat moved to the rail foot (hip 0.62 m from plate)")
    u = Vector((0, math.cos(math.radians(45)), math.sin(math.radians(45))))   # back pad long axis
    nb = Vector((0, u.z, -u.y))                                                # behind the pad
    front0 = Vector((0, 0.192, 0.386))                                         # pad front, bottom end
    back = _kid(r, "back.006")
    c_old = _center(r, back)
    c_new = front0 + u * 0.255 + nb * 0.05
    _xform(r, back, _T(c_new) @ Matrix.Rotation(math.radians(-75), 4, "X") @ _T(-c_old),
           "back pad reclined away from the sled (45 deg)")
    head = _kid(r, "headrest")
    h_old = _center(r, head)
    h_new = front0 + u * 0.65 + nb * 0.0525
    _xform(r, head, _T(h_new) @ Matrix.Rotation(math.radians(-75), 4, "X") @ _T(-h_old),
           "headrest above the reclined back pad")
    sp = front0 + nb * 0.150
    _retarget(r, _kid(r, "backbone"), sp + u * -0.30, sp + u * 0.74, "back spine behind the reclined pad")
    _retarget(r, _kid(r, "seat_saddle"), (0, -0.05, 0.0), (0, -0.05, 0.266), "seat pillar to the floor")
    for nm, sx in (("seat_cradle", -1), ("seat_cradle.001", 1)):
        _retarget(r, _kid(r, nm), (sx * 0.40, 0.36, 0.095), (sx * 0.045, 0.14, 0.12),
                  "cradle from runner to the back spine")
    for nm in ("side_grip", "side_grip.001", "side_grip_cap1", "side_grip_cap1.001",
               "side_grip_cap2", "side_grip_cap2.001", "side_grip_mount", "side_grip_mount.001"):
        _xform(r, _kid(r, nm), _T((0, -0.35, 0)), "seat side grips moved with the seat")
    _seal(r)
    return "fixed"


def fix_preacher_machine():
    r = _root("P_preacher_machine")
    if _done(r):
        return "skip"
    pad = _kid(r, "arm_pad")
    _expect(r, pad, (-0.21, -0.207, 0.67), (0.21, 0.203, 1.028))
    c_old = _center(r, pad)
    # pad: high edge under the armpit (y 0.13, z 0.96), slopes 40 deg down away from the user
    u = Vector((0, -math.cos(math.radians(40)), -math.sin(math.radians(40))))
    n = Vector((0, -math.sin(math.radians(40)), math.cos(math.radians(40))))  # pad top normal
    top_near = Vector((0, 0.13, 0.96))
    length = 0.40
    c_new = top_near + u * (length / 2) - n * 0.04
    long_axis = _local_axis(r, pad, 1)
    T = (_T(c_new) @ Matrix.Rotation(math.radians(80), 4, "X") @ _T(-c_old)
         @ _scale_along(c_old, long_axis, length / 0.50))
    _mesh_xform(r, pad, T, "arm pad flipped: high under the armpit, 40 deg down away, 0.40 m")
    bottom = c_new - n * 0.04
    _retarget(r, _kid(r, "pad_post"), (0, -0.05, 0.06), bottom + Vector((0, 0, 0.004)),
              "pad post shortened to the new pad underside")

    elbow = top_near + u * 0.30 + n * 0.05           # elbow joint on the pad
    piv = _kid(r, "P_Moving assembly.022")
    p_old = _loc(r, piv).translation.copy()
    if (p_old - Vector((0, 0.05, 1.0))).length > TOL:
        raise RuntimeError("preacher lever pivot not where expected")
    d = Vector((0, elbow.y, elbow.z)) - p_old
    _xform(r, piv, _T(d), "lever axis moved onto the elbow")
    hub_x = 0.27
    hw = ["bearing.001", "pop_pin.001", "Range lock bolt.001", "range_sector.001"] + \
         [f"range_index.{i:03d}" for i in range(5, 10)]
    for nm in hw:
        _xform(r, _kid(r, nm), _T(d + Vector((hub_x - 0.177, 0, 0))), "range hub outboard at the elbow axis")
    axis = Vector((0, elbow.y, elbow.z))
    # lever arms: from outboard hubs to the grips, forearm length from the elbow
    g = Vector((0, -0.23, -0.19))                     # grip centre relative to the axis (forearm on pad)
    for nm, sx in (("arm.005", -1), ("arm.006", 1)):
        _retarget(r, _kid(r, nm), axis + Vector((sx * (hub_x - 0.035), 0, 0)),
                  axis + Vector((sx * 0.20, g.y, g.z + 0.06)), "lever arm from outboard hub to grip")
    for nm, sx in (("grip.002", -1), ("grip.003", 1)):
        _retarget(r, _kid(r, nm), axis + Vector((sx * 0.20, g.y, g.z - 0.06)),
                  axis + Vector((sx * 0.20, g.y, g.z + 0.06)), "grip at forearm length on the pad line")
    mount = _kid(r, "lever_mount")
    left_strut = _dup(r, mount, "D6MS_preacher_strut_L", "left hub strut")   # copy before re-aiming
    hub_r = axis + Vector((hub_x, 0, -0.06))
    _retarget(r, mount, (0.10, -0.40, 0.10), hub_r, "hub strut from the base, outside the pad")
    left_hub = _dup(r, _kid(r, "bearing.001"), "D6MS_preacher_hub_L", "left hub (mirror of right)")
    _xform(r, left_hub, _T((-2 * hub_x, 0, 0)), "left hub at the elbow axis")
    _retarget(r, left_strut, (-0.10, -0.40, 0.10), axis + Vector((-hub_x, 0, -0.06)), "left hub strut from the base")
    _curve_end(r, _kid(r, "Coated load cable.012"), axis + Vector((hub_x, 0, 0.08)),
               "cable end follows the hub cam")
    _seal(r)
    return "fixed"


def fix_hip_abductor():
    r = _root("P_hip_abductor")
    if _done(r):
        return "skip"
    knee_z, knee_y = 0.56, -0.47
    for side, asm in ((-1, "P_Moving assembly.024"), (1, "P_Moving assembly.025")):
        mv = _kid(r, asm)
        hub = _loc(r, mv).translation.copy()
        sfx = "" if side < 0 else ".001"
        pad = _kid(r, "knee_pad" + sfx)
        _expect(r, pad, (min(side * .45, side * .35), -0.14, 0.52), (max(side * .45, side * .35), 0.04, 0.84))
        c = _center(r, pad)
        target = Vector((side * 0.215, knee_y, knee_z))
        _xform(r, pad, _T(target - c), "knee pad at the outside of the knee")
        arm = _kid(r, ("arm.011", "arm.012")[side > 0])
        _retarget(r, arm, hub, Vector((side * 0.215, knee_y + 0.02, knee_z - 0.15)),
                  "leg arm from hip hub forward under the knee pad")
        peg_arm = _kid(r, "foot_peg_arm" + sfx)
        _retarget(r, peg_arm, (side * 0.265, knee_y - 0.02, knee_z - 0.14), (side * 0.265, -0.60, 0.14),
                  "foot-peg drop from the knee pad")
        peg = _kid(r, "foot_peg" + sfx)
        _retarget(r, peg, (side * 0.06, -0.60, 0.14), (side * 0.30, -0.60, 0.14), "foot peg under the shin")
    _seal(r)
    return "fixed"


def fix_lateral_raise_machine():
    r = _root("P_lateral_raise_machine")
    if _done(r):
        return "skip"
    seat = _kid(r, "seat.009")
    _expect(r, seat, (-0.21, -0.28, 0.405), (0.21, 0.12, 0.495))
    # shoulder joint of a seated 1.74 m user: seat top 0.495 + 0.56; pivot axis (along Y) at that height,
    # hubs behind the back pad so the bridge clears it
    piv_new = Vector((0.28, 0.245, 1.055))
    d = piv_new - Vector((0.28, 0.10, 1.25))
    for nm in ("pivot_bridge.001", "axle_body.002", "axle_bolt.002", "axle_cap.006", "drive_cam.002"):
        _xform(r, _kid(r, nm), _T(d), "pivot bridge lowered to shoulder height behind the back pad")
    _retarget(r, _kid(r, "bridge_stay"), (0, 0.59, 1.25), (0, 0.245, 1.055), "bridge stay from the stack cover (below the guide placard) down to the lowered bridge")
    for side, asm, sfx, cap in ((-1, "P_Moving assembly.019", "", ".002"), (1, "P_Moving assembly.020", ".001", ".003")):
        mv = _kid(r, asm)
        p0 = _loc(r, mv).translation.copy()
        p1 = Vector((side * 0.28, piv_new.y, piv_new.z))
        _xform(r, mv, _T(p1 - p0), "arm axis at shoulder height")
        pad = _kid(r, "elbow" + sfx)
        rel = _center(r, pad) - p1
        best = None
        for k in range(-1800, 1801):
            t = math.radians(k / 10.0)
            x = rel.x * math.cos(t) + rel.z * math.sin(t)
            z = -rel.x * math.sin(t) + rel.z * math.cos(t)
            if z < 0 and (best is None or abs(x) < best[0]):
                best = (abs(x), k / 10.0)
        group = [_kid(r, n) for n in ("elbow" + sfx, "grip" + sfx, "grip_stem" + sfx, "neutral" + cap,
                                      "neutral_cap1" + cap, "neutral_cap2" + cap)]
        for ob in group:
            _xform(r, ob, _rot_about(p1, "Y", best[1]), "elbow pad + handle turned to hang (arm at side)")
        target = Vector((side * 0.335, -0.02, 0.775))      # outside of the elbow, arm hanging
        mv_d = target - _center(r, pad)
        for ob in group:
            _xform(r, ob, _T(mv_d), "elbow pad + handle at the elbow")
        joint = Vector((side * 0.345, 0.11, 0.97))
        _retarget(r, _kid(r, "pivot" + sfx), p1, joint, "lever drop from the hub, outboard of back pad")
        top = _center(r, pad) + Vector((0, 0, 0.045))
        _retarget(r, _kid(r, ("arm.003", "arm.004")[side > 0]), joint, top, "lever arm down to the elbow pad")
    _curve_end(r, _kid(r, "Coated load cable.010"), (0.28, piv_new.y, piv_new.z + 0.075),
               "cable end follows the lowered cam, routed over the stack cover", via=(0.20, 0.55, 1.56))
    _seal(r)
    return "fixed"


def fix_seated_leg_curl():
    r = _root("P_seated_leg_curl")
    if _done(r):
        return "skip"
    mv = _kid(r, "P_Moving assembly.014")
    p0 = _loc(r, mv).translation.copy()
    if (p0 - Vector((0, -0.30, 0.43))).length > TOL:
        raise RuntimeError("leg curl pivot not where expected")
    p1 = Vector((0, -0.31, 0.63))                      # knee axis: seat top 0.573 + 0.06
    _xform(r, mv, _T(p1 - p0), "lever axis raised onto the knee")
    lever = _kid(r, "P_curl_lever")
    roller = _kid(r, "roller")
    rc = _center(r, roller)
    rel = rc - p1
    want = Vector((0, -0.388, -0.195))                 # under the ankle, legs ~15 deg below level
    ang = math.degrees(math.atan2(want.z, want.y) - math.atan2(rel.z, rel.y))
    _xform(r, lever, _rot_about(p1, "X", ang), "lever rest angle: legs near straight")
    rc = _center(r, roller)
    ext = (p1 + want) - rc
    for nm in ("roller", "roller_cap_l", "roller_cap_r"):
        _xform(r, _kid(r, nm), _T(ext), "ankle roller slid out to the ankle")
    for nm in ("arm.001", "arm.002"):
        a, b = _segment(r, _kid(r, nm))
        near, far = (a, b) if (a - p1).length < (b - p1).length else (b, a)
        _retarget(r, _kid(r, nm), near, far + ext, "lever arm lengthened to the ankle roller")
    thigh = _kid(r, "thigh")
    _expect(r, thigh, (-0.18, -0.33, 0.63), (0.18, -0.07, 0.73))
    _xform(r, thigh, _T((0, 0, 0.10)), "thigh pad on top of the thigh (was 0.10 m into it)")
    _retarget(r, _kid(r, "thigh_arm"), (0, -0.2, 0.2), (0, -0.2, 0.75), "thigh pad post lengthened")
    for nm in ("curl_grip", "curl_grip.001", "curl_grip_cap1", "curl_grip_cap1.001",
               "curl_grip_cap2", "curl_grip_cap2.001"):
        _xform(r, _kid(r, nm), _T((0, 0.10, 0.10)), "side grips beside the raised thigh pad")
    cab = (_rot_about(p1, "X", ang) @ Vector((0.239, p1.y, p1.z + 0.097)))
    _curve_end(r, _kid(r, "Coated load cable.006"), cab, "cable end follows the raised, turned cam")
    _seal(r)
    return "fixed"


def fix_shoulder_press_machine():
    r = _root("P_shoulder_press_machine")
    if _done(r):
        return "skip"
    for asm in ("P_Moving assembly.010", "P_Moving assembly.011"):
        mv = _kid(r, asm)
        p = _loc(r, mv).translation.copy()
        for ob in list(mv.children):
            _xform(r, ob, _rot_about(p, "X", 17.0), "press arm rest pose turned back to shoulder height")
    _seal(r)
    return "fixed"


def fix_tbar_row_machine():
    r = _root("P_tbar_row_machine")
    if _done(r):
        return "skip"
    pad = _kid(r, "chest.001")
    _expect(r, pad, (-0.2, -0.139, 0.484), (0.2, 0.437, 0.951))
    c_old = _center(r, pad)
    long_axis = _local_axis(r, pad, 1)
    c_new = Vector((0, 0.389, 0.943))
    T = (_T(c_new) @ Matrix.Rotation(math.radians(8), 4, "X") @ _T(-c_old)
         @ _scale_along(c_old, long_axis, 0.45 / 0.70))
    _mesh_xform(r, pad, T, "chest pad at chest height for the foot-rest stance (30 deg, 0.45 m)")
    n = Vector((0, math.sin(math.radians(30)), math.cos(math.radians(30))))
    _retarget(r, _kid(r, "chest_mount"), (0, 0.389, 0.17), c_new - n * 0.041, "chest pad post to the raised pad")
    _seal(r)
    return "fixed"


def fix_dip_machine():
    r = _root("P_dip_machine")
    if _done(r):
        return "skip"
    mv = _kid(r, "P_Moving assembly.023")
    p = _loc(r, mv).translation.copy()
    for side, arm, grip in ((-1, "arm.007", "grip.004"), (1, "arm.008", "grip.005")):
        g = _kid(r, grip)
        _expect(r, g, (min(side * .385, side * .335), -0.45, 0.755), (max(side * .385, side * .335), -0.3, 0.805))
        _retarget(r, g, (side * 0.32, -0.02, 0.80), (side * 0.32, -0.17, 0.80), "dip grip beside the torso")
        _retarget(r, _kid(r, arm), Vector((side * 0.29, p.y, p.z)), (side * 0.32, -0.02, 0.80),
                  "dip lever arm to the grip")
    _seal(r)
    return "fixed"


FIXES = [fix_adjustable_bench, fix_leg_press_45, fix_preacher_machine, fix_hip_abductor,
         fix_lateral_raise_machine, fix_seated_leg_curl, fix_shoulder_press_machine,
         fix_tbar_row_machine, fix_dip_machine]


def apply(only=None):
    LOG.clear()
    out = {}
    for f in FIXES:
        key = f.__name__[4:]
        if only and key not in only:
            continue
        out[key] = f()
    return out


def _main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    save = None
    if "--save" in argv:
        save = Path(argv[argv.index("--save") + 1]).expanduser().resolve()
        root = Path(__file__).resolve().parents[2]
        if any(save.is_relative_to((root / "promo" / d).resolve()) for d in ("scenes", "models")):
            raise SystemExit("refusing to save into promo/scenes or promo/models")
        if save.suffix.lower() != ".blend":
            raise SystemExit("--save must end with .blend")
        save.parent.mkdir(parents=True, exist_ok=True)
    print("detail6_machine_seats", apply())
    if save is not None:
        bpy.ops.wm.save_as_mainfile(filepath=str(save), copy=True, compress=True, relative_remap=False)
        print("saved", save)


if __name__ == "__main__":
    _main()
