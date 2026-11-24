"""Apply detail pass 2 (gym interior: posing room, locker rooms, showers/restrooms, main-floor life) to the open gym scene.

Run headless:  Blender -b promo/scenes/scene_gym.blend --python promo/tools/apply_detail_pass2.py [-- --save]
Only the pass-2 packages run here, so later edits to pass-1 objects (apply_detail_pass.py) and the realism pass
(apply_realism_pass.py) are left alone. Every package is idempotent.
"""
import importlib
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PACKAGES = ("gym_posing", "gym_lockers", "gym_wet", "gym_life")


def apply():
    out = {}
    for p in PACKAGES:
        m = importlib.import_module("detail_" + p)
        importlib.reload(m)
        r = m.apply()
        out[p] = {k: r.get(k) for k in ("objects_added", "triangles_added")}
    return out


if __name__ == "__main__":
    print("DETAIL_PASS2", apply())
    if "--save" in sys.argv:
        bpy.ops.wm.save_mainfile()
        print("DETAIL_PASS2 saved", bpy.data.filepath)
