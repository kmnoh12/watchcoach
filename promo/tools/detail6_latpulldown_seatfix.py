"""detail6 latpulldown seat fix: make the seated user face the weight stack.

detail6_latpulldown.py (run before this module) builds the seat at local y=-0.18 and
the thigh rollers at y=-0.53 (on the far side of the seat from the stack at y>+0.38),
so a user with knees under the rollers would sit with his back to the stack. On a real
lat pulldown the user faces the stack: stack -> thigh rollers -> seat, with the bar
hanging slightly in front of the face.

This module swaps the two stations along local Y about the midpoint y=-0.355
(seat -> -0.53, rollers -> -0.18). Seat top 0.500, bar, cable and stack are untouched.

  * Seat cushion, seat trim, under-seat plate + bolts, seat post, gusset collar:
    translated dy=-0.350 (they are symmetric in Y, so translation == mirror, and the
    cushion's narrower nose keeps pointing at +Y = toward the rollers/stack).
  * Roller receiver sleeve, wear collar, chrome post, hub/shaft, both rollers + end
    caps: translated dy=+0.350.
  * Diagonal brace (seat post -> roller sleeve): mirrored in Y about y=-0.355 with
    face winding reversed (no inverted normals), so it again joins post and sleeve.
  * Seat post and its gusset collar are lengthened 14 mm downward so the part that
    overhangs the base-spine end (y<-0.55) sits on the front crossbar instead of
    hovering 8 mm above it.
  * Rollers, hub, shaft, index holes and chrome-post top raised 40 mm (roller z
    0.634..0.766, 134 mm above the seat top instead of 94 mm) so an average adult
    thigh (~130-140 mm compressed) fits under them; the post bottom stays in its sleeve.
  * Spring pop-pin and the chrome-post index holes are turned 90 deg about the post
    axis (+X side -> +Y side, toward the stack) so the pin knob is not in the seated
    user's right calf.

Only the five P_lat_pulldown seat/roller objects are touched (Ddetail6_LP_Seat,
_SeatTrim, _RollerPost, _ThighRollers and the seat islands of _LowerChassis). Each
object is checked by geometry: original layout -> fixed and tagged, already fixed ->
left alone, anything else -> error. Running apply() twice gives identical results.

Usage:
    Blender -b promo/scenes/scene_gym.blend -P promo/tools/detail6_latpulldown_seatfix.py [-- --save out.blend]
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT_NAME = "P_lat_pulldown"
PFX = "Ddetail6_LP_"
TAG = "detail6_lp_seatfix"
TAG_VER = "v1"

SEAT_Y_OLD, SEAT_Y_NEW = -0.180, -0.530
ROLL_Y_OLD, ROLL_Y_NEW = -0.530, -0.180
MID_Y = 0.5 * (SEAT_Y_OLD + ROLL_Y_OLD)  # -0.355
DY_SEAT = SEAT_Y_NEW - SEAT_Y_OLD  # -0.350
DY_ROLL = ROLL_Y_NEW - ROLL_Y_OLD  # +0.350
ROLLER_RAISE = 0.040  # roller z 0.594..0.726 -> 0.634..0.766: 134 mm under-roller gap (was 94 mm)
POST_EXTEND = 0.014  # seat post / gusset bottom 0.084/0.086 -> 0.070/0.072 (crossbar top 0.076)
TOL = 0.004


def _islands(bm):
    seen, out = set(), []
    for v in bm.verts:
        if v in seen:
            continue
        stack, isl = [v], []
        seen.add(v)
        while stack:
            a = stack.pop()
            isl.append(a)
            for e in a.link_edges:
                b = e.other_vert(a)
                if b not in seen:
                    seen.add(b)
                    stack.append(b)
        out.append(isl)
    return out


def _bbox(verts):
    xs = [v.co.x for v in verts]
    ys = [v.co.y for v in verts]
    zs = [v.co.z for v in verts]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def _mid(r):
    return 0.5 * (r[0] + r[1])


def _state(value, old, new, label):
    if abs(value - old) < TOL:
        return "old"
    if abs(value - new) < TOL:
        return "new"
    raise RuntimeError(f"{label}: unexpected y={value:.4f} (expected {old} or {new})")


def _tag(ob, note):
    ob[TAG] = TAG_VER
    ob[TAG + "_note"] = note


def _translate_mesh(ob, dy, dz=0.0):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0.0, dy, dz))
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def _fix_seat(ob):
    st = _state(ob.location.y, SEAT_Y_OLD, SEAT_Y_NEW, ob.name)
    if st == "old":
        ob.location.y = SEAT_Y_NEW
        _tag(ob, f"location.y {SEAT_Y_OLD} -> {SEAT_Y_NEW}")
        return "fixed"
    return "already"


def _fix_translated_mesh(ob, old, new, dy, dz=0.0, selector=None):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    verts = [v for v in bm.verts if selector is None or selector(v)]
    st = _state(_mid(_bbox(verts)[1]), old, new, ob.name)
    bm.free()
    if st == "old":
        _translate_mesh(ob, dy, dz)
        _tag(ob, f"mesh dy {dy:+.3f} dz {dz:+.3f}")
        return "fixed"
    return "already"


def _fix_roller_post(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    sleeve = [v for v in bm.verts if v.co.z < 0.40 and abs(v.co.x) <= 0.0285]
    st = _state(_mid(_bbox(sleeve)[1]), ROLL_Y_OLD, ROLL_Y_NEW, ob.name)
    if st == "new":
        bm.free()
        return "already"
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0.0, DY_ROLL, 0.0))
    # Turn pop-pin (+X at z~0.462) and index-hole detents 90 deg about the post axis.
    rot_verts = []
    n_pin = n_holes = 0
    for isl in _islands(bm):
        (x0, x1), (y0, y1), (z0, z1) = _bbox(isl)
        is_pin = x0 > 0.020 and x1 < 0.105 and 0.440 < z0 and z1 < 0.485
        is_hole = max(x1 - x0, y1 - y0, z1 - z0) < 0.011 and 0.515 < z0 and z1 < 0.630
        if is_pin:
            n_pin += 1
            rot_verts.extend(isl)
        elif is_hole:
            n_holes += 1
            rot_verts.extend(isl)
    if n_pin != 1 or n_holes != 10:
        bm.free()
        raise RuntimeError(f"{ob.name}: expected 1 pop-pin / 10 holes, got {n_pin} / {n_holes}")
    pivot = Matrix.Translation((0.0, ROLL_Y_NEW, 0.0))
    rot = pivot @ Matrix.Rotation(math.radians(90.0), 4, "Z") @ pivot.inverted()
    bmesh.ops.transform(bm, matrix=rot, verts=rot_verts)
    # Telescope the chrome post up by ROLLER_RAISE: hub, shaft and index holes ride up with
    # the post top; the post bottom stays 18 mm inside the receiver sleeve.
    raise_verts = []
    n_post = 0
    for isl in _islands(bm):
        (x0, x1), (y0, y1), (z0, z1) = _bbox(isl)
        if z0 > 0.515:  # holes, hub collar, shaft
            raise_verts.extend(isl)
        elif abs((x1 - x0) - 0.040) < 0.001 and abs((z1 - z0) - 0.190) < 0.002:  # chrome post
            n_post += 1
            raise_verts.extend(v for v in isl if v.co.z > 0.60)
    if n_post != 1:
        bm.free()
        raise RuntimeError(f"{ob.name}: expected 1 chrome post, got {n_post}")
    bmesh.ops.translate(bm, verts=raise_verts, vec=(0.0, 0.0, ROLLER_RAISE))
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    _tag(ob, f"mesh dy {DY_ROLL:+.3f}; pop-pin + 10 index holes rotated +90deg about post axis; "
             f"post/hub/shaft/holes raised {ROLLER_RAISE * 1000:.0f} mm")
    return "fixed"


def _fix_lower_chassis(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    seat_isl = []
    for isl in _islands(bm):
        bb = _bbox(isl)
        if bb[2][0] >= 0.060 and _mid(bb[1]) < -0.05:  # base spine/crossbar/feet/anchors all start below 0.020
            seat_isl.append((isl, bb))
    posts = [(i, b) for i, b in seat_isl if abs((b[0][1] - b[0][0]) - 0.060) < 0.002 and (b[2][1] - b[2][0]) > 0.30]
    braces = [(i, b) for i, b in seat_isl if (b[1][1] - b[1][0]) > 0.20]
    gussets = [(i, b) for i, b in seat_isl if abs((b[0][1] - b[0][0]) - 0.072) < 0.002 and (b[2][1] - b[2][0]) < 0.040]
    if len(posts) != 1 or len(braces) != 1 or len(gussets) != 1:
        bm.free()
        raise RuntimeError(f"{ob.name}: seat islands post/brace/gusset = {len(posts)}/{len(braces)}/{len(gussets)}")
    st = _state(_mid(posts[0][1][1]), SEAT_Y_OLD, SEAT_Y_NEW, ob.name + " seat post")
    if st == "new":
        bm.free()
        return "already"
    brace_set = set(braces[0][0])
    post_set = set(posts[0][0])
    gusset_set = set(gussets[0][0])
    moved = 0
    for isl, _bb in seat_isl:
        if isl[0] in brace_set:
            continue
        for v in isl:
            v.co.y += DY_SEAT
            moved += 1
    # lengthen seat post + gusset collar downward onto the front crossbar
    post_z0 = posts[0][1][2][0]
    for v in post_set:
        if v.co.z < post_z0 + 0.0055:
            v.co.z -= POST_EXTEND
    gus_mid = _mid(gussets[0][1][2])
    for v in gusset_set:
        if v.co.z < gus_mid:
            v.co.z -= POST_EXTEND
    # mirror the diagonal brace in Y about MID_Y and fix winding
    for v in brace_set:
        v.co.y = 2.0 * MID_Y - v.co.y
    brace_faces = list({f for v in brace_set for f in v.link_faces})
    bmesh.ops.reverse_faces(bm, faces=brace_faces, flip_multires=False)
    bm.normal_update()
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    _tag(ob, f"{len(seat_isl)} seat islands: {moved} verts dy {DY_SEAT:+.3f}, brace mirrored about y={MID_Y}, "
             f"post/gusset bottom -{POST_EXTEND * 1000:.0f} mm")
    return "fixed"


def apply() -> dict:
    root = bpy.data.objects.get(ROOT_NAME)
    if root is None:
        raise RuntimeError(f"{ROOT_NAME} not found")

    def get(name):
        ob = bpy.data.objects.get(PFX + name)
        if ob is None or ob.parent != root or ob.type != "MESH":
            raise RuntimeError(f"{PFX + name} missing; run detail6_latpulldown.py first")
        if ob.data.users != 1:
            raise RuntimeError(f"{ob.name}: mesh shared by {ob.data.users} users")
        return ob

    res = {}
    res["Seat"] = _fix_seat(get("Seat"))
    res["SeatTrim"] = _fix_translated_mesh(get("SeatTrim"), SEAT_Y_OLD, SEAT_Y_NEW, DY_SEAT)
    res["RollerPost"] = _fix_roller_post(get("RollerPost"))
    res["ThighRollers"] = _fix_translated_mesh(get("ThighRollers"), ROLL_Y_OLD, ROLL_Y_NEW, DY_ROLL, dz=ROLLER_RAISE)
    res["LowerChassis"] = _fix_lower_chassis(get("LowerChassis"))
    bpy.context.view_layer.update()
    return res


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
    print("detail6_latpulldown_seatfix", json.dumps(res, ensure_ascii=False))
    if save is not None:
        bpy.ops.wm.save_as_mainfile(filepath=str(save), copy=True, compress=True, relative_remap=False)
        print("saved", save)


if __name__ == "__main__":
    _main()
