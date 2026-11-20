"""Swap every hero in an existing promo .blend to the V6 base model, in place.

  blender -b <file.blend> --factory-startup -P tools/swap_hero_v6.py

V6 (models/v6.blend) is the V5 body with the rebuilt hands and the left-wrist watch fitted to the new wrist.
Only the hero's body mesh and the watch meshes change: the rig, its poses and animation, everything parented to it
(cap, phone, ...), materials, object names and the scene stay as they were. The 52-bone rest pose must match V6;
the script stops without saving if it does not. It also turns the hero's left-finger curl the right way (see
fix_left_fingers). Safe to run again on a file it already swapped.
"""
import os
import sys

import bpy

V6 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "v6.blend")
PARTS = ("Watch_Case", "Watch_Strap", "Watch_Display", "Watch_ButtonA", "Watch_ButtonB", "Watch_Buckle")


def base_name(name):
    return name.split(".")[0]


LEFT_FINGERS = [f"{f}_0{i}_l" for f in ("index", "middle", "ring", "pinky") for i in (1, 2, 3)] + ["thumb_02_l", "thumb_03_l"]


def fix_left_fingers(hero):
    """The pose library curled the left fingers with +X, which bends them backwards (bake_poses.palm_dir picked
    the back of the hand). Curl is -X on this rig, so a positive pure-X finger rotation is flipped. Running it
    twice changes nothing."""
    fixed = 0
    for name in LEFT_FINGERS:
        pb = hero.pose.bones.get(name)
        q = pb.rotation_quaternion if pb else None
        if q is not None and q.x > 1e-5 and abs(q.y) < 1e-4 and abs(q.z) < 1e-4:
            q.x = -q.x
            fixed += 1
    actions = set()
    ad = hero.animation_data
    if ad:
        actions.add(ad.action)
        actions.update(s.action for t in ad.nla_tracks for s in t.strips)
    for act in filter(None, actions):
        curves = list(act.fcurves) if hasattr(act, "fcurves") else [
            fc for layer in act.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]
        for name in LEFT_FINGERS:
            path = f'pose.bones["{name}"].rotation_quaternion'
            xs = [fc for fc in curves if fc.data_path == path and fc.array_index == 1]
            side = [fc for fc in curves if fc.data_path == path and fc.array_index in (2, 3)]
            if not xs or any(abs(k.co[1]) > 1e-4 for fc in side for k in fc.keyframe_points):
                continue
            fc = xs[0]
            if min(k.co[1] for k in fc.keyframe_points) < -1e-5 or max(k.co[1] for k in fc.keyframe_points) < 1e-5:
                continue
            for k in fc.keyframe_points:
                k.co[1] = -k.co[1]
                k.handle_left[1] = -k.handle_left[1]
                k.handle_right[1] = -k.handle_right[1]
            fc.update()
            fixed += 1
    return fixed


def main():
    heroes = [o for o in bpy.data.objects if o.type == "ARMATURE" and o.data.name.startswith("V5_CommonRig")]
    if not heroes:
        print("SWAP no hero")
        return
    kinds = ("meshes", "materials", "armatures", "actions", "images", "node_groups", "textures")
    before = {k: set(getattr(bpy.data, k)) for k in kinds}
    with bpy.data.libraries.load(V6, link=False) as (src, dst):
        names = list(src.objects)
        dst.objects = list(names)
    v6 = dict(zip(names, dst.objects))   # appended objects may be renamed (.001) when the file already has the name
    rig, body = v6["V5_CommonRig"], v6["V5_Body"]
    watch = v6["LowPolyWatch"]
    parts = {base_name(c.name): c for c in watch.children}
    group_names = [g.name for g in body.vertex_groups]
    rest = {b.name: (b.head_local.copy(), b.tail_local.copy()) for b in rig.data.bones}
    done = []
    for hero in heroes:
        worst = max(max((b.head_local - rest[b.name][0]).length, (b.tail_local - rest[b.name][1]).length)
                    for b in hero.data.bones)
        if set(b.name for b in hero.data.bones) != set(rest) or worst > 1e-4:
            sys.exit(f"SWAP FAIL {hero.name}: rest pose differs from V6 ({worst * 1000:.2f} mm)")
        done.append(f"{hero.name} left fingers fixed {fix_left_fingers(hero)}")
        for child in hero.children:
            if child.type == "MESH" and any(m.type == "ARMATURE" for m in child.modifiers):
                old = child.data
                old_count = len(old.vertices)
                mesh = body.data.copy()
                mesh.name = old.name
                mesh.materials.clear()
                for m in old.materials:
                    mesh.materials.append(m)
                for p in mesh.polygons:
                    p.material_index = 0
                    p.use_smooth = False
                child.vertex_groups.clear()
                for n in group_names:
                    child.vertex_groups.new(name=n)
                child.data = mesh
                if old.users == 0:
                    bpy.data.meshes.remove(old)
                done.append(f"{child.name} {old_count}->{len(mesh.vertices)}")
            elif child.type == "EMPTY" and child.parent_type == "BONE" and child.parent_bone == "lowerarm_l":
                child.matrix_parent_inverse = watch.matrix_parent_inverse.copy()
                child.matrix_basis = watch.matrix_basis.copy()
                existing = {base_name(part.name) for part in child.children}
                for name in PARTS:
                    if name not in existing:
                        new = parts[name]
                        part = new.copy()
                        part.name = name
                        child.users_collection[0].objects.link(part)
                        part.parent = child
                for part in child.children:
                    new = parts.get(base_name(part.name))
                    if part.type != "MESH" or new is None:
                        continue
                    old = part.data
                    mesh = new.data.copy()
                    mesh.name = old.name
                    if len(old.materials) == len(mesh.materials):
                        for i, m in enumerate(old.materials):
                            mesh.materials[i] = m
                    part.data = mesh
                    part.matrix_parent_inverse = new.matrix_parent_inverse.copy()
                    part.matrix_basis = new.matrix_basis.copy()
                    if old.users == 0:
                        bpy.data.meshes.remove(old)
                    done.append(f"{part.name}->{len(mesh.vertices)}")
    for o in dst.objects:
        if o:
            bpy.data.objects.remove(o, do_unlink=True)
    # Remove only what the append brought in and nothing uses now (V6 rig, its meshes, duplicate materials).
    # A global orphan purge would also drop the file's own unused materials, which Blender keeps on save.
    changed = True
    while changed:
        changed = False
        for k in kinds:
            for idb in [i for i in getattr(bpy.data, k) if i not in before[k] and i.users == 0]:
                getattr(bpy.data, k).remove(idb)
                changed = True
    with open(bpy.data.filepath, "rb") as f:
        compressed = f.read(4) == b"\x28\xb5\x2f\xfd"
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_mainfile(compress=compressed)
    print("SWAP OK", os.path.basename(bpy.data.filepath), [h.name for h in heroes], done)


main()
