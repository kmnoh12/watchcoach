"""Rebuild both gym locker suites (gym_locker_suites) and their detail packages in the open gym scene.

Run headless:
    Blender -b promo/scenes/scene_gym.blend --python promo/tools/rebuild_locker_suites.py [-- --save]
Without --save nothing is written. Idempotent: it restores what detail_gym_lockers / detail_gym_wet tagged
(`detail_pkg`), deletes every object under the "Gym Locker Suites" collection tree (keeping the collections),
purges the data those objects used, rebuilds the suites under the same parent collection, then re-runs
detail_gym_lockers.apply() and detail_gym_wet.apply(). No other collection is touched.
"""
import importlib
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

ROOT_COLL = "Gym Locker Suites"


def _parent_of(name):
    for c in bpy.data.collections:
        if name in c.children:
            return c
    return bpy.context.scene.collection if name in bpy.context.scene.collection.children else None


def _clear_suites(root):
    datas = []
    for ob in list(root.all_objects):
        if ob.data is not None:
            datas.append(ob.data)
        bpy.data.objects.remove(ob, do_unlink=True)
    pools = {bpy.types.Mesh: bpy.data.meshes, bpy.types.Curve: bpy.data.curves,
             bpy.types.Light: bpy.data.lights, bpy.types.LightProbe: bpy.data.lightprobes}
    for d in {id(d): d for d in datas}.values():
        try:
            if d.users:
                continue
        except ReferenceError:
            continue
        for t, pool in pools.items():
            if isinstance(d, t):
                pool.remove(d)
                break


def rebuild() -> dict:
    import detail_gym_lockers as DL
    import detail_gym_wet as DW
    import gym_locker_suites as G
    for m in (G, DL, DW):
        importlib.reload(m)
    DL.restore()
    DW.restore_existing()
    root = bpy.data.collections.get(ROOT_COLL)
    if root is not None:
        parent = _parent_of(ROOT_COLL)
        _clear_suites(root)
    else:
        parent = bpy.data.collections.get("Reel gym fixtures") or bpy.context.scene.collection
    G.build_locker_suites(parent)
    out = {"lockers": DL.apply(), "wet": DW.apply()}
    for k in ("lockers", "wet"):
        out[k] = {kk: out[k].get(kk) for kk in ("objects_added", "triangles_added", "lockers")}
    out["suite_objects"] = len(bpy.data.collections[ROOT_COLL].all_objects)
    out["locker_floor_m2"] = round(G.WIDTH * abs(G.Y_LBACK + G.WALL_T / 2 - G.Y_FRONT), 2)
    return out


if __name__ == "__main__":
    print("REBUILD_LOCKER_SUITES", rebuild())
    if "--save" in sys.argv:
        bpy.ops.wm.save_mainfile()
        print("REBUILD_LOCKER_SUITES saved", bpy.data.filepath)
