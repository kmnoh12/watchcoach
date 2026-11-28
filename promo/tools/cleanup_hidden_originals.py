"""Delete render-hidden leftover objects (old originals that detail scripts hid instead of
removing) from the gym scene, then purge orphan data.

Keeps any hidden object that something still uses: a parent of another object, a modifier /
constraint / geometry-nodes target (e.g. boolean door cutters), or a member of an instanced
collection. Cameras are kept.

Run (never saves unless --save is given; --out PATH saves a copy instead):
  Blender -b promo/scenes/scene_gym.blend --python promo/tools/cleanup_hidden_originals.py -- [--save | --out copy.blend]
"""
import sys

import bpy


def referenced_names():
    refs = set()
    for o in bpy.data.objects:
        if o.parent:
            refs.add(o.parent.name)
        for m in o.modifiers:
            for a in ("object", "mirror_object", "offset_object", "start_cap", "end_cap",
                      "target", "auxiliary_target", "curve"):
                t = getattr(m, a, None)
                if isinstance(t, bpy.types.Object):
                    refs.add(t.name)
            if m.type == "BOOLEAN" and m.operand_type == "COLLECTION" and m.collection:
                refs.update(x.name for x in m.collection.all_objects)
            if m.type == "NODES":
                for _, v in m.items():
                    if isinstance(v, bpy.types.Object):
                        refs.add(v.name)
                    elif isinstance(v, bpy.types.Collection):
                        refs.update(x.name for x in v.all_objects)
        for c in o.constraints:
            t = getattr(c, "target", None)
            if t:
                refs.add(t.name)
        if o.instance_type == "COLLECTION" and o.instance_collection:
            refs.update(x.name for x in o.instance_collection.all_objects)
    for ng in bpy.data.node_groups:
        for n in ng.nodes:
            for attr in ("object", "collection"):
                v = getattr(n, attr, None)
                if isinstance(v, bpy.types.Object):
                    refs.add(v.name)
            for s in n.inputs:
                v = getattr(s, "default_value", None)
                if isinstance(v, bpy.types.Object):
                    refs.add(v.name)
                elif isinstance(v, bpy.types.Collection):
                    refs.update(x.name for x in v.all_objects)
    return refs


def main():
    refs = referenced_names()
    doomed = []
    for o in bpy.data.objects:
        if o.type == "CAMERA":
            continue
        hidden = o.hide_render or not o.users_collection or any(c.hide_render for c in o.users_collection)
        if hidden and o.name not in refs:
            doomed.append(o)
    names = sorted(o.name for o in doomed)
    for o in doomed:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    print(f"CLEANUP_OK removed={len(names)} kept_referenced_hidden="
          f"{sum(1 for o in bpy.data.objects if o.hide_render)} objects_left={len(bpy.data.objects)}")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--out" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=argv[argv.index("--out") + 1], copy=True, compress=True)
        print("CLEANUP_SAVED_COPY")
    elif "--save" in argv:
        bpy.ops.wm.save_mainfile(compress=True)
        print("CLEANUP_SAVED")


main()
