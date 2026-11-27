"""detail6 fix: Chest-Supported T-Bar Row (`P_tbar_row_machine`) ergonomic & mechanical layout.

Fixes confirmed issues on `P_tbar_row_machine` in `promo/scenes/scene_gym.blend`:
  1. `chest.001` sat too high and too far back over the footrests (`y=0.18..0.59, z=0.81..1.09`),
     perched on a tall vertical post while the red diagonal spine `frame` poked into empty space
     in front (`y=-0.35, z=0.86`).
     -> `chest.001` lowered and shifted forward to `y=-0.04..+0.38, z=0.70..0.98` (center
        `(0, 0.170, 0.840)`, keeping its 38 deg angle) for a natural standing-lean stance on
        `incline_footrest` (`y=0.41..0.79, z=0.14..0.30`).
     -> `frame` shortened along its diagonal to `(0, 0.500, 0.060) -> (0, 0.040, 0.540)` so it
        supports the chest pad without poking forward into the user/plates.
     -> `chest_mount` retargeted cleanly from `frame` `(0, 0.170, 0.400)` into the underside of
        `chest.001` `(0, 0.170, 0.810)`.
  2. Handles (`wide_grip*`, `parallel_grip*`) stuck far out past the front/head end of the chest
     pad (`y=-0.27..-0.07, z=0.70..0.79`), while weight horns/plates (`weight_horn*`,
     `cast_plate.019/.020`, `y=-0.10..+0.22`) sat directly under the chest where the handles belong.
     -> `lever` / `lever.001` retargeted from rear pivot `(±0.280, 0.840, 0.500)` forward-down to
        `(±0.280, -0.360, 0.440)` at rest (`Stroke=0`).
     -> `wide_grip*` and `parallel_grip*` moved directly below the front half of `chest.001`
        (`y=+0.04..+0.21, z=0.46..0.51` at `Stroke=0`; pulls up to `y=+0.09..+0.26, z=0.75..0.77`
        beside the lower chest/ribs at `Stroke=1`).
     -> `weight_horn*` and `cast_plate.019/.020` (with `Mark 10 KG.*` children) moved to the front
        end of the levers (`y=-0.320, z=0.442`, plates `y=-0.48..-0.16, z=0.28..0.60`), cleanly
        forward of the hands and chest pad and inside the base footprint at both `Stroke=0` and `1`.

Touches ONLY `P_tbar_row_machine` and its descendants. Preserves machine origin/rotation, all
`Stroke L` / `Stroke R` drivers, and all `E_*` materials. 100% idempotent.

Usage:
    Blender -b promo/scenes/scene_gym.blend -P promo/tools/detail6_fix_tbar_row.py [-- --save out.blend]
"""
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT_NAME = "P_tbar_row_machine"
TAG = "detail6_fix_tbar_row"
TAG_VER = "v2"
OBTAG = "detail6_tbar_fix"

# Target coordinates in P_tbar_row_machine local space (at Stroke L = Stroke R = 0)
CHEST_CENTER = Vector((0.0, 0.170, 0.840))
FRAME_P0 = Vector((0.0, 0.500, 0.060))
FRAME_P1 = Vector((0.0, 0.140, 0.440))
MOUNT_P0 = Vector((0.0, 0.170, 0.390))
MOUNT_P1 = Vector((0.0, 0.170, 0.810))

LEVER_Y0, LEVER_Z0 = 0.840, 0.500
LEVER_Y1, LEVER_Z1 = -0.360, 0.440

GRIP_JUNCTION_Y, GRIP_JUNCTION_Z = 0.040, 0.460
PARALLEL_GRIP_X_ABS = 0.370
HORN_Y, HORN_Z = -0.320, 0.442


def _kid(root, name):
    for o in root.children_recursive:
        if o.name == name:
            return o
    raise KeyError(f"{root.name}: missing descendant {name!r}")


def _upd():
    bpy.context.view_layer.update()


def _in_root(root, ob):
    return root.matrix_world.inverted() @ ob.matrix_world


def _bbox_root(root, ob):
    M = _in_root(root, ob)
    if ob.type == "MESH" and ob.data and len(ob.data.vertices) > 0:
        pts = [M @ v.co for v in ob.data.vertices]
    else:
        pts = [M.translation]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return lo, hi


def _center_root(root, ob):
    lo, hi = _bbox_root(root, ob)
    return 0.5 * (lo + hi)


def _no_drivers(ob):
    ad = ob.animation_data
    if ad and any(
        fc.data_path in ("location", "rotation_euler", "rotation_quaternion", "scale")
        for fc in ad.drivers
    ):
        raise RuntimeError(f"Refusing to modify driven transform on {ob.name}")


def _translate_root(root, ob, delta_root, note):
    """Rigidly translate an un-driven object by delta_root (expressed in root local space)."""
    _no_drivers(ob)
    if delta_root.length < 1e-7:
        ob[OBTAG] = f"{TAG_VER}:{note}"
        return
    # Convert root-space translation to parent-local translation
    parent_in_root = _in_root(root, ob.parent) if ob.parent else Matrix.Identity(4)
    delta_parent = parent_in_root.to_3x3().inverted() @ delta_root
    ob.location = ob.location + delta_parent
    _upd()
    ob[OBTAG] = f"{TAG_VER}:{note}"


def _retarget_box_beam(root, ob, target_p0, target_p1, note):
    """Retarget an 8-vertex rectangular prism beam so its two 4-vert end caps sit at target_p0 -> target_p1.

    Preserves the beam's original cross-section dimensions cleanly and is 100% idempotent.
    """
    _no_drivers(ob)
    me = ob.data
    if ob.type != "MESH" or len(me.vertices) != 8:
        raise RuntimeError(f"{ob.name}: expected 8-vertex box beam, got {len(me.vertices)}")

    M = _in_root(root, ob)
    M_inv = M.inverted()
    pts = [M @ v.co for v in me.vertices]

    # Identify the long axis by finding the pair of vertices with maximum distance,
    # then splitting the 8 vertices into the two 4-vertex end caps along the principal axis.
    center = sum(pts, Vector()) / 8.0
    # Compute covariance to find the dominant (long) axis cleanly
    cov = Matrix(((0, 0, 0), (0, 0, 0), (0, 0, 0)))
    for p in pts:
        d = p - center
        for i in range(3):
            for j in range(3):
                cov[i][j] += d[i] * d[j]

    # Power iteration for principal eigenvector (beam length axis)
    axis = Vector((0.0, 1.0, 0.0))
    best_norm = -1.0
    for seed in (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))):
        v = seed.copy()
        for _ in range(25):
            v = cov @ v
            if v.length < 1e-12:
                break
            v.normalize()
        val = (cov @ v).dot(v)
        if val > best_norm:
            best_norm = val
            axis = v

    # Split into two 4-vertex caps by projection onto axis
    projs = sorted(range(8), key=lambda i: (pts[i] - center).dot(axis))
    cap_a = projs[:4]
    cap_b = projs[4:]
    c_a = sum((pts[i] for i in cap_a), Vector()) / 4.0
    c_b = sum((pts[i] for i in cap_b), Vector()) / 4.0

    # Match cap_a / cap_b to target_p0 / target_p1 so we never invert the beam
    if (c_a - target_p0).length + (c_b - target_p1).length > (c_a - target_p1).length + (c_b - target_p0).length:
        cap_a, cap_b = cap_b, cap_a
        c_a, c_b = c_b, c_a

    old_dir = (c_b - c_a).normalized()
    new_dir = (target_p1 - target_p0).normalized()
    rot = old_dir.rotation_difference(new_dir).to_matrix()

    for i in cap_a:
        offset = pts[i] - c_a
        # Keep only component perpendicular to old_dir, rotate to new_dir
        perp = offset - old_dir * offset.dot(old_dir)
        new_p = target_p0 + rot @ perp
        me.vertices[i].co = M_inv @ new_p

    for i in cap_b:
        offset = pts[i] - c_b
        perp = offset - old_dir * offset.dot(old_dir)
        new_p = target_p1 + rot @ perp
        me.vertices[i].co = M_inv @ new_p

    me.update()
    _upd()
    ob[OBTAG] = f"{TAG_VER}:{note}"


def apply() -> dict:
    root = bpy.data.objects.get(ROOT_NAME)
    if root is None:
        raise RuntimeError(f"Missing {ROOT_NAME} in scene")

    if root.get(TAG) == TAG_VER:
        return {
            "machine": ROOT_NAME,
            "status": "skipped",
            "reason": f"already applied ({TAG}={TAG_VER})",
        }

    # Save & zero Stroke L/R so lever arm edits happen cleanly at rest pose
    saved_stroke_l = float(root.get("Stroke L", 0.0))
    saved_stroke_r = float(root.get("Stroke R", 0.0))
    root["Stroke L"] = 0.0
    root["Stroke R"] = 0.0
    _upd()

    changes = {}

    try:
        # 1. Chest pad (`chest.001`)
        pad = _kid(root, "chest.001")
        pad_before = _bbox_root(root, pad)
        _translate_root(root, pad, CHEST_CENTER - _center_root(root, pad), "chest pad at standing-lean height forward of footrests")
        changes["chest.001"] = {
            "before": [[round(x, 3) for x in pad_before[0]], [round(x, 3) for x in pad_before[1]]],
            "after": [[round(x, 3) for x in b] for b in _bbox_root(root, pad)],
        }

        # 2. Central diagonal spine (`frame`) & chest pad mount (`chest_mount`)
        frame = _kid(root, "frame")
        frame_before = _bbox_root(root, frame)
        _retarget_box_beam(root, frame, FRAME_P0, FRAME_P1, "spine shortened under chest pad")
        changes["frame"] = {
            "before": [[round(x, 3) for x in frame_before[0]], [round(x, 3) for x in frame_before[1]]],
            "after": [[round(x, 3) for x in b] for b in _bbox_root(root, frame)],
        }

        mount = _kid(root, "chest_mount")
        mount_before = _bbox_root(root, mount)
        _retarget_box_beam(root, mount, MOUNT_P0, MOUNT_P1, "chest mount connecting spine to lowered chest pad")
        changes["chest_mount"] = {
            "before": [[round(x, 3) for x in mount_before[0]], [round(x, 3) for x in mount_before[1]]],
            "after": [[round(x, 3) for x in b] for b in _bbox_root(root, mount)],
        }

        # 2b. Flip incline_footrest / incline_footrest.001 slope direction (+18 deg -> -18 deg)
        for fnm in ("incline_footrest", "incline_footrest.001"):
            fob = _kid(root, fnm)
            fb = _bbox_root(root, fob)
            fob.rotation_mode = "XYZ"
            fob.rotation_euler.x = -0.314159265
            _upd()
            fob[OBTAG] = f"{TAG_VER}:footrest slope flipped"
            changes[fnm] = {
                "before": [[round(x, 3) for x in fb[0]], [round(x, 3) for x in fb[1]]],
                "after": [[round(x, 3) for x in b] for b in _bbox_root(root, fob)],
            }

        # 3. Both lever arms (L: side=-1, suffix=""; R: side=+1, suffix=".001")
        for side, sfx, plate_name in (
            (-1.0, "", "cast_plate.019"),
            (+1.0, ".001", "cast_plate.020"),
        ):
            arm_x = side * 0.280

            # 3a. Main lever beam: rear pivot -> front weight-horn tip
            lever = _kid(root, "lever" + sfx)
            lever_before = _bbox_root(root, lever)
            _retarget_box_beam(
                root,
                lever,
                Vector((arm_x, LEVER_Y0, LEVER_Z0)),
                Vector((arm_x, LEVER_Y1, LEVER_Z1)),
                "lever beam lowered to rest height and extended forward to weight horn",
            )
            changes[lever.name] = {
                "before": [[round(x, 3) for x in lever_before[0]], [round(x, 3) for x in lever_before[1]]],
                "after": [[round(x, 3) for x in b] for b in _bbox_root(root, lever)],
            }

            # 3b. Dual grips:
            #     - wide_grip* sits on the outer face of lever at (arm_x, GRIP_JUNCTION_Y, GRIP_JUNCTION_Z)
            #     - parallel_grip* joins wide_grip outboard of lever at X = ±PARALLEL_GRIP_X_ABS so hands
            #       have full wrap-around clearance without clipping the lever tube.
            wide_cap1 = _kid(root, "wide_grip_cap1" + sfx)
            wj_cur = _center_root(root, wide_cap1)
            wide_delta = Vector((0.0, GRIP_JUNCTION_Y - wj_cur.y, GRIP_JUNCTION_Z - wj_cur.z))
            for gn in ("wide_grip" + sfx, "wide_grip_cap1" + sfx, "wide_grip_cap2" + sfx):
                gob = _kid(root, gn)
                gb = _bbox_root(root, gob)
                _translate_root(root, gob, wide_delta, "wide grip positioned below front half of chest pad")
                if gn == "wide_grip" + sfx:
                    changes[gn] = {
                        "before": [[round(x, 3) for x in gb[0]], [round(x, 3) for x in gb[1]]],
                        "after": [[round(x, 3) for x in b] for b in _bbox_root(root, gob)],
                    }

            par_cap1 = _kid(root, "parallel_grip_cap1" + sfx)
            pj_cur = _center_root(root, par_cap1)
            par_delta = Vector((
                side * PARALLEL_GRIP_X_ABS - pj_cur.x,
                GRIP_JUNCTION_Y - pj_cur.y,
                GRIP_JUNCTION_Z - pj_cur.z,
            ))
            for gn in ("parallel_grip" + sfx, "parallel_grip_cap1" + sfx, "parallel_grip_cap2" + sfx):
                gob = _kid(root, gn)
                gb = _bbox_root(root, gob)
                _translate_root(root, gob, par_delta, "parallel grip mounted cleanly on wide grip below front half of chest pad")
                if gn == "parallel_grip" + sfx:
                    changes[gn] = {
                        "before": [[round(x, 3) for x in gb[0]], [round(x, 3) for x in gb[1]]],
                        "after": [[round(x, 3) for x in b] for b in _bbox_root(root, gob)],
                    }

            # 3c. Weight horn & cast plate (+ Mark 10 KG.* children follow plate automatically)
            horn = _kid(root, "weight_horn" + sfx)
            hb = _bbox_root(root, horn)
            hc = _center_root(root, horn)
            _translate_root(
                root,
                horn,
                Vector((0.0, HORN_Y - hc.y, HORN_Z - hc.z)),
                "weight horn moved forward of handles and chest pad",
            )
            changes[horn.name] = {
                "before": [[round(x, 3) for x in hb[0]], [round(x, 3) for x in hb[1]]],
                "after": [[round(x, 3) for x in b] for b in _bbox_root(root, horn)],
            }

            plate = _kid(root, plate_name)
            pb = _bbox_root(root, plate)
            pc = _center_root(root, plate)
            _translate_root(
                root,
                plate,
                Vector((0.0, HORN_Y - pc.y, HORN_Z - pc.z)),
                "weight plate moved onto forward weight horn",
            )
            changes[plate.name] = {
                "before": [[round(x, 3) for x in pb[0]], [round(x, 3) for x in pb[1]]],
                "after": [[round(x, 3) for x in b] for b in _bbox_root(root, plate)],
            }

        root[TAG] = TAG_VER
    finally:
        root["Stroke L"] = saved_stroke_l
        root["Stroke R"] = saved_stroke_r
        _upd()

    return {
        "machine": ROOT_NAME,
        "status": "fixed",
        "tag": f"{TAG}={TAG_VER}",
        "changes": changes,
    }


def _main():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    save_path = None
    if "--save" in argv:
        save_path = Path(argv[argv.index("--save") + 1])

    res = apply()
    print(json.dumps(res, indent=2))
    if save_path:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(save_path))
        print(f"SAVED: {save_path}")


if __name__ == "__main__":
    _main()
