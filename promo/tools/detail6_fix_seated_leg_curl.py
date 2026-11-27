"""detail6 fix: P_seated_leg_curl thigh hold-down pad assembly.

Fixes the thigh hold-down pad assembly on P_seated_leg_curl so it matches a real
commercial Seated Leg Curl machine (Life Fitness / Cybex / Matrix):

  * Previously `thigh_arm` rose vertically straight up through the dead center
    (x=0, y=-0.20) right through the front of `seat.006` (between the user's
    legs) while floating at z=0.20 above `base.005`, `thigh_pop_pin` sat
    embedded in the seat cushion, and `curl_grip*` floated in midair.
  * Now the thigh hold-down mounts on the open -X (outer) side of the frame at
    x=-0.280, y=-0.220 — clear of `seat.006` (x in [-0.21, +0.21]), clear of
    `arm.001` (y <= -0.269 across Stroke 0..1), and clear of the +X lever pivot,
    range sector, idler sheave, and cable.
  * Structural load path (all connected, zero floating):
      base.005 -> horizontal outrigger beam (with floor rubber foot)
      -> outer vertical receiver sleeve + diagonal gusset + sleeve wear collar
      -> outer -X yellow spring pop-pin (`thigh_pop_pin`) with steel barrel
      -> chrome telescoping inner post with index detents
      -> horizontal cantilever cross-bar across top of `thigh` pad
      -> top mounting plate bolted onto `thigh` + left/right angled handle
         stems entering `curl_grip_cap1` / `curl_grip_cap1.001`.
  * `thigh` pad lowered 50 mm (loc.z 0.78 -> 0.73, z=[0.68, 0.78]) for a
    comfortable ~15-16 cm thigh clearance gap above the front of `seat.006`
    (z_top ~ 0.524 at y=-0.20).
  * `curl_grip*` side handles lowered 70 mm (loc.z 0.82 -> 0.75, z=[0.73, 0.77])
    at natural thigh-pad / hip height, attached directly to the cantilever
    cross-bar via left/right handle stems.

Only P_seated_leg_curl and its descendants are touched. apply() is 100%
idempotent: running it twice produces identical object locations, vertex counts,
and bounding boxes.

Usage:
    Blender -b promo/scenes/scene_gym.blend -P promo/tools/detail6_fix_seated_leg_curl.py [-- --save out.blend]
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT_NAME = "P_seated_leg_curl"
TAG = "detail6_fix_seated_leg_curl"
TAG_VER = "v1"
HW_NAME = "Ddetail6_SLC_ThighHardware"

# Key dimensions in P_seated_leg_curl local coordinates
POST_X = -0.280
POST_Y = -0.220
THIGH_Z_NEW = 0.730       # thigh pad z=[0.680, 0.780] -> ~15.6 cm above seat front (0.524)
GRIP_Z_NEW = 0.750        # curl_grip* z=[0.730, 0.770] -> thigh-pad / hip height
POP_PIN_LOC = Vector((-0.342, POST_Y, 0.500))
POP_PIN_ROT = (0.0, math.pi * 0.5, 0.0)
FLOOR_Z = -0.012          # matches base.005 bottom (world z = 0.000)

GRIP_NAMES = (
    "curl_grip",
    "curl_grip.001",
    "curl_grip_cap1",
    "curl_grip_cap1.001",
    "curl_grip_cap2",
    "curl_grip_cap2.001",
)


def _kid(root, name):
    for ob in root.children_recursive:
        if ob.name == name:
            return ob
    raise RuntimeError(f"{root.name}: missing descendant '{name}'")


def _get_mat(name):
    mat = bpy.data.materials.get(name)
    if mat is None:
        raise RuntimeError(f"Expected shared material '{name}' not found")
    return mat


def _add_beveled_box(bm, x0, x1, y0, y1, z0, z1, bevel=0.004, mat_idx=0):
    cx = 0.5 * (x0 + x1)
    cy = 0.5 * (y0 + y1)
    cz = 0.5 * (z0 + z1)
    sx = x1 - x0
    sy = y1 - y0
    sz = z1 - z0
    ret = bmesh.ops.create_cube(bm, size=1.0)
    verts = ret["verts"]
    mat = Matrix.Translation((cx, cy, cz)) @ Matrix.Diagonal((sx, sy, sz, 1.0))
    bmesh.ops.transform(bm, matrix=mat, verts=verts)
    edges = list({e for v in verts for e in v.link_edges})
    faces = list({f for v in verts for f in v.link_faces})
    for f in faces:
        f.material_index = mat_idx
    if bevel > 0.0:
        b = min(bevel, 0.25 * min(sx, sy, sz))
        res = bmesh.ops.bevel(
            bm,
            geom=edges,
            offset=b,
            offset_type="OFFSET",
            segments=2,
            profile=0.5,
            affect="EDGES",
            clamp_overlap=True,
        )
        for f in res.get("faces", []):
            f.material_index = mat_idx


def _add_cylinder(bm, p0, p1, radius, segments=20, mat_idx=0):
    v0 = Vector(p0)
    v1 = Vector(p1)
    axis = v1 - v0
    length = axis.length
    if length < 1e-6:
        return
    mid = 0.5 * (v0 + v1)
    quat = Vector((0.0, 0.0, 1.0)).rotation_difference(axis.normalized())
    xform = Matrix.Translation(mid) @ quat.to_matrix().to_4x4()
    ret = bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        cap_tris=False,
        segments=segments,
        radius1=radius,
        radius2=radius,
        depth=length,
        matrix=xform,
    )
    verts = ret["verts"]
    for f in {f for v in verts for f in v.link_faces}:
        f.material_index = mat_idx
        f.smooth = True


def _add_prism_segment(bm, p0, p1, width_x, width_t, bevel=0.003, mat_idx=0):
    """Rectangular bar connecting p0 -> p1 with cross-section width_x along X and width_t perpendicular."""
    v0 = Vector(p0)
    v1 = Vector(p1)
    axis = v1 - v0
    length = axis.length
    if length < 1e-6:
        return
    u = axis.normalized()
    x_dir = Vector((1.0, 0.0, 0.0))
    if abs(u.dot(x_dir)) > 0.99:
        x_dir = Vector((0.0, 1.0, 0.0))
    t_dir = u.cross(x_dir).normalized()
    x_dir = t_dir.cross(u).normalized()

    mid = 0.5 * (v0 + v1)
    rot = Matrix((
        (x_dir.x, t_dir.x, u.x, 0.0),
        (x_dir.y, t_dir.y, u.y, 0.0),
        (x_dir.z, t_dir.z, u.z, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    ))
    xform = Matrix.Translation(mid) @ rot @ Matrix.Diagonal((width_x, width_t, length, 1.0))
    ret = bmesh.ops.create_cube(bm, size=1.0)
    verts = ret["verts"]
    bmesh.ops.transform(bm, matrix=xform, verts=verts)
    edges = list({e for v in verts for e in v.link_edges})
    for f in {f for v in verts for f in v.link_faces}:
        f.material_index = mat_idx
    if bevel > 0.0:
        b = min(bevel, 0.22 * min(width_x, width_t, length))
        res = bmesh.ops.bevel(
            bm,
            geom=edges,
            offset=b,
            offset_type="OFFSET",
            segments=2,
            profile=0.5,
            affect="EDGES",
            clamp_overlap=True,
        )
        for f in res.get("faces", []):
            f.material_index = mat_idx


def _build_frame_mesh(mesh):
    """Build painted frame geometry for `thigh_arm` (material slot 0 = E_silver)."""
    bm = bmesh.new()

    # 1. Base outrigger beam: solidly embeds into base.005 (x in [-0.1085, 0.1085], z in [-0.012, 0.112])
    _add_beveled_box(bm, -0.312, -0.055, POST_Y - 0.034, POST_Y + 0.034, 0.008, 0.088, bevel=0.005, mat_idx=0)

    # 2. Outer vertical receiver sleeve at (POST_X, POST_Y)
    _add_beveled_box(
        bm,
        POST_X - 0.032, POST_X + 0.032,
        POST_Y - 0.032, POST_Y + 0.032,
        0.072, 0.560,
        bevel=0.005,
        mat_idx=0,
    )

    # 3. Inner diagonal gusset brace connecting outrigger to receiver sleeve
    _add_prism_segment(
        bm,
        (-0.145, POST_Y, 0.076),
        (POST_X + 0.024, POST_Y, 0.220),
        width_x=0.038,
        width_t=0.036,
        bevel=0.004,
        mat_idx=0,
    )

    # 4. Horizontal cantilever cross-bar spanning from -X telescoping post across top of thigh pad to +X handle
    _add_beveled_box(
        bm,
        POST_X - 0.026, 0.256,
        POST_Y - 0.022, POST_Y + 0.022,
        0.772, 0.808,
        bevel=0.005,
        mat_idx=0,
    )

    # 5. Thigh-pad top mounting plate (embeds cleanly into top of `thigh` z_top=0.780)
    _add_beveled_box(
        bm,
        -0.115, 0.115,
        POST_Y - 0.044, POST_Y + 0.044,
        0.762, 0.784,
        bevel=0.004,
        mat_idx=0,
    )

    # 6. Left (-X) and right (+X) handle stems: from cantilever cross-bar to curl_grip_cap1 (y=-0.159, z=0.750)
    for sx in (-0.240, 0.240):
        # Short elbow transition from bar center (sx, POST_Y, 0.790) -> grip cap center (sx, -0.155, GRIP_Z_NEW)
        _add_prism_segment(
            bm,
            (sx, POST_Y, 0.790),
            (sx, -0.155, GRIP_Z_NEW),
            width_x=0.026,
            width_t=0.026,
            bevel=0.004,
            mat_idx=0,
        )

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def _build_hardware_mesh(mesh):
    """Build chrome post, wear collar, pop-pin barrel, index detents, and rubber foot."""
    # material slots: 0 = E_steel, 1 = E_grip
    bm = bmesh.new()

    # 1. Chrome telescoping inner post (slides inside receiver sleeve up into cantilever cross-bar)
    _add_beveled_box(
        bm,
        POST_X - 0.024, POST_X + 0.024,
        POST_Y - 0.024, POST_Y + 0.024,
        0.450, 0.792,
        bevel=0.004,
        mat_idx=0,
    )

    # 2. Steel pop-pin barrel on outer -X face of receiver sleeve (connects sleeve wall to thigh_pop_pin)
    _add_cylinder(
        bm,
        (POST_X - 0.048, POST_Y, 0.500),
        (POST_X - 0.026, POST_Y, 0.500),
        radius=0.013,
        segments=20,
        mat_idx=0,
    )

    # 3. Sleeve top wear collar (E_grip)
    _add_beveled_box(
        bm,
        POST_X - 0.036, POST_X + 0.036,
        POST_Y - 0.036, POST_Y + 0.036,
        0.556, 0.576,
        bevel=0.003,
        mat_idx=1,
    )

    # 4. Rubber floor foot under outer end of outrigger (flush with floor z=-0.012)
    _add_cylinder(
        bm,
        (POST_X, POST_Y, FLOOR_Z),
        (POST_X, POST_Y, 0.014),
        radius=0.032,
        segments=24,
        mat_idx=1,
    )

    # 5. Four height-adjustment index detent buttons on outer -X face of chrome post (E_grip)
    for hz in (0.605, 0.645, 0.685, 0.725):
        _add_cylinder(
            bm,
            (POST_X - 0.026, POST_Y, hz),
            (POST_X - 0.022, POST_Y, hz),
            radius=0.0055,
            segments=16,
            mat_idx=1,
        )

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def _ensure_hardware_obj(root, ref_obj):
    hw = bpy.data.objects.get(HW_NAME)
    created = False
    if hw is None:
        mesh = bpy.data.meshes.new(HW_NAME + "_Mesh")
        hw = bpy.data.objects.new(HW_NAME, mesh)
        cols = list(ref_obj.users_collection) or list(root.users_collection) or [bpy.context.scene.collection]
        for col in cols:
            col.objects.link(hw)
        hw.parent = root
        created = True
    else:
        if hw.parent != root:
            hw.parent = root
        if hw.data.users != 1:
            hw.data = hw.data.copy()

    hw.location = (0.0, 0.0, 0.0)
    hw.rotation_euler = (0.0, 0.0, 0.0)
    hw.scale = (1.0, 1.0, 1.0)
    hw.matrix_parent_inverse.identity()

    hw.data.materials.clear()
    hw.data.materials.append(_get_mat("E_steel"))
    hw.data.materials.append(_get_mat("E_grip"))
    _build_hardware_mesh(hw.data)
    hw[TAG] = TAG_VER
    return hw, created


def apply() -> dict:
    root = bpy.data.objects.get(ROOT_NAME)
    if root is None:
        raise RuntimeError(f"{ROOT_NAME} not found")

    already_tagged = (root.get(TAG) == TAG_VER)

    thigh = _kid(root, "thigh")
    thigh_arm = _kid(root, "thigh_arm")
    pop_pin = _kid(root, "thigh_pop_pin")
    grips = [_kid(root, n) for n in GRIP_NAMES]

    if thigh_arm.data.users != 1:
        thigh_arm.data = thigh_arm.data.copy()

    # 1. Lower thigh pad for ~15-16 cm thigh clearance above front of seat.006
    thigh.location = (0.0, -0.20, THIGH_Z_NEW)
    thigh.rotation_euler = (0.0, 0.0, 0.0)
    thigh[TAG] = TAG_VER

    # 2. Rebuild thigh_arm as outer -X outrigger + receiver sleeve + gusset + cantilever + handle stems
    thigh_arm.location = (0.0, 0.0, 0.0)
    thigh_arm.rotation_mode = "XYZ"
    thigh_arm.rotation_euler = (0.0, 0.0, 0.0)
    thigh_arm.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    thigh_arm.scale = (1.0, 1.0, 1.0)
    thigh_arm.matrix_parent_inverse.identity()
    for mod in list(thigh_arm.modifiers):
        if mod.type == "BEVEL":
            thigh_arm.modifiers.remove(mod)
    thigh_arm.data.materials.clear()
    thigh_arm.data.materials.append(_get_mat("E_silver"))
    _build_frame_mesh(thigh_arm.data)
    thigh_arm[TAG] = TAG_VER

    # 3. Build/update companion chrome post + collar + barrel + floor foot + index detents
    hw, hw_created = _ensure_hardware_obj(root, thigh_arm)

    # 4. Reposition yellow pop-pin onto outer -X face of receiver sleeve
    pop_pin.location = POP_PIN_LOC.copy()
    pop_pin.rotation_euler = POP_PIN_ROT
    pop_pin[TAG] = TAG_VER

    # 5. Lower side handles (curl_grip*) to natural thigh-pad height (z=0.750)
    for g in grips:
        g.location.z = GRIP_Z_NEW
        g[TAG] = TAG_VER

    root[TAG] = TAG_VER
    bpy.context.view_layer.update()

    # Compute summary bounds in root local space
    inv_root = root.matrix_world.inverted()

    def _bb(ob):
        m = inv_root @ ob.matrix_world
        pts = [m @ v.co for v in ob.data.vertices]
        return {
            "x": [round(min(p.x for p in pts), 4), round(max(p.x for p in pts), 4)],
            "y": [round(min(p.y for p in pts), 4), round(max(p.y for p in pts), 4)],
            "z": [round(min(p.z for p in pts), 4), round(max(p.z for p in pts), 4)],
            "verts": len(pts),
        }

    return {
        "status": "already" if already_tagged else "fixed",
        "root": ROOT_NAME,
        "hardware_created": hw_created,
        "thigh": _bb(thigh),
        "thigh_arm": _bb(thigh_arm),
        "hardware": _bb(hw),
        "thigh_pop_pin": _bb(pop_pin),
        "curl_grip": _bb(grips[0]),
        "curl_grip.001": _bb(grips[1]),
    }


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
    print("detail6_fix_seated_leg_curl", json.dumps(res, ensure_ascii=False))
    if save is not None:
        bpy.ops.wm.save_as_mainfile(filepath=str(save), copy=True, compress=True, relative_remap=False)
        print("saved", save)


if __name__ == "__main__":
    _main()
