"""Transplant the V6 standard hands & wrists onto the extra rigs.

1. Copies V6 hand & finger bone landmarks (32 bones, exact wrist pivot match)
   from `promo/models/v6.blend` into `promo/cast/src_figure_copy.blend` (`Fig.rig`).
2. Applies `fix_v5_hands.hand()` to `BASE_Low Poly Man` in `src_figure_copy.blend`,
   replacing the old blocky hands/wrists with the V6 standard forearm loft + palm + 5 fingers.
3. Propagates the updated mesh + hand bone landmarks into all 5 extras in
   `promo/cast/cast_library.blend` (preserving each extra's color, scale, location, and pose).

Run:
  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P promo/models/fix_extra_hands.py
"""

import os
import sys
import bmesh
import bpy
from mathutils import Vector

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(THIS_DIR, "..", ".."))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import fix_v5_hands

V6_BLEND = os.path.join(REPO_ROOT, "promo", "models", "v6.blend")
EXTRA_SRC = os.path.join(REPO_ROOT, "promo", "cast", "src_figure_copy.blend")
CAST_LIB = os.path.join(REPO_ROOT, "promo", "cast", "cast_library.blend")
RENDER_DIR = os.path.join(REPO_ROOT, "promo", "models", "renders_extra_hands_qa")

HAND_PREFIXES = ("hand_", "thumb_", "index_", "middle_", "ring_", "pinky_")
PATCH_VERSION = "v6_extra_hand_patch_1"


def is_hand_bone(name):
    return name.startswith(HAND_PREFIXES)


def read_v6_hand_bones():
    bpy.ops.wm.open_mainfile(filepath=V6_BLEND)
    rig = bpy.data.objects["V5_CommonRig"]
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bones_info = {}
    for eb in rig.data.edit_bones:
        if is_hand_bone(eb.name):
            bones_info[eb.name] = (eb.head.copy(), eb.tail.copy(), eb.roll)
    bpy.ops.object.mode_set(mode="OBJECT")
    print(f"[v6_hands] read {len(bones_info)} hand/finger bones from v6.blend")
    return bones_info


def copy_hand_bones_into_rig(rig, bones_info):
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    ebones = rig.data.edit_bones
    updated = 0
    for name, (head, tail, roll) in bones_info.items():
        eb = ebones.get(name)
        if eb is not None:
            eb.head = head.copy()
            eb.tail = tail.copy()
            eb.roll = roll
            updated += 1
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.select_set(False)
    return updated


def apply_v6_hands_to_mesh(body, rig):
    if body.data.get("hand_patch") == PATCH_VERSION:
        print(f"[v6_hands] {body.name} already patched ({PATCH_VERSION})")
        return False

    if body.data.shape_keys is not None:
        body.shape_key_clear()

    bm = bmesh.new()
    bm.from_mesh(body.data)
    old_faces = set(bm.faces)

    left, fit_l, loft_l = fix_v5_hands.hand(bm, body, rig, "l")
    right, fit_r, loft_r = fix_v5_hands.hand(bm, body, rig, "r")

    for _ in range(3):
        bmesh.ops.smooth_vert(
            bm,
            verts=left + right + fit_l + fit_r,
            factor=0.38,
            use_axis_x=True,
            use_axis_y=True,
            use_axis_z=True,
        )
        for v, c, d, surface, p, f in loft_l + loft_r:
            v.co = fix_v5_hands.loft(c, d, surface, p.co, f)

    for lv, rv in zip(left, right, strict=True):
        rv.co = (-lv.co.x, lv.co.y, lv.co.z)

    new_faces = [f for f in bm.faces if f not in old_faces]
    bmesh.ops.recalc_face_normals(bm, faces=new_faces)
    for f in new_faces:
        f.smooth = False

    non_manifold = [e for f in new_faces for e in f.edges if not e.is_manifold]
    assert not non_manifold, f"Open hand patch: {len(non_manifold)} non-manifold edges"

    bm.to_mesh(body.data)
    bm.free()
    body.data.update()
    body.data["hand_patch"] = PATCH_VERSION
    print(f"[v6_hands] patched {body.name}: verts={len(body.data.vertices)}, polys={len(body.data.polygons)}")
    return True


def patch_src_figure(bones_info):
    bpy.ops.wm.open_mainfile(filepath=EXTRA_SRC)
    rig = bpy.data.objects["Fig.rig"]
    body = bpy.data.objects["BASE_Low Poly Man"]

    n = copy_hand_bones_into_rig(rig, bones_info)
    print(f"[v6_hands] updated {n} hand bones in Fig.rig")
    apply_v6_hands_to_mesh(body, rig)

    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=EXTRA_SRC, compress=True)
    print(f"[v6_hands] saved {EXTRA_SRC}")


def patch_cast_library(bones_info):
    bpy.ops.wm.open_mainfile(filepath=CAST_LIB)
    extra_names = ["Extra_red", "Extra_yellow", "Extra_gray", "Extra_blue", "Extra_green"]
    for ename in extra_names:
        rig = bpy.data.objects.get(ename)
        body = bpy.data.objects.get(ename + "_Body")
        if rig is None or body is None:
            print(f"[v6_hands] skip missing {ename}")
            continue
        # Ensure we work on a clean un-shared mesh datablock
        if body.data.users > 1:
            body.data = body.data.copy()
        if rig.data.users > 1:
            rig.data = rig.data.copy()
        copy_hand_bones_into_rig(rig, bones_info)
        apply_v6_hands_to_mesh(body, rig)

    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=CAST_LIB, compress=True)
    print(f"[v6_hands] saved {CAST_LIB}")


def main():
    bones_info = read_v6_hand_bones()
    patch_src_figure(bones_info)
    patch_cast_library(bones_info)


if __name__ == "__main__":
    main()
