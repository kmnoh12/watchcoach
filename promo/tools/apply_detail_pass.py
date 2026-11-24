"""Apply the real-photo detail pass (8 DETAIL_* packages) to the open gym scene, plus two scene fixes.

Run headless:  Blender -b promo/scenes/scene_gym.blend --python promo/tools/apply_detail_pass.py [-- --save]
Every package is idempotent, so re-running is safe.
"""
import importlib
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PACKAGES = ("hall_surfaces", "hall_props", "hall_storefronts",
            "gym_floor", "gym_ceiling", "gym_freeweight", "gym_counter", "gym_wall_graphics")
MAC_ARIAL_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def hide_stray_baseboard():
    """Baseboard_Left stayed at the old wall line (x -4.5) when the gym was widened to x -7.5."""
    ob = bpy.data.objects.get("Baseboard_Left")
    if ob and ob.location.x > -6.0 and not ob.hide_render:
        ob["detail_fix"] = "stray baseboard from before the left extension"
        ob.hide_render = ob.hide_viewport = True


def freeze_info_logo_text():
    """InfoLogo_* text points at a Windows-only Arial path and renders as boxes on the Mac.
    Bake the glyphs into meshes so the sign renders the same on every PC."""
    texts = [o for o in bpy.data.objects
             if o.type == "FONT" and o.name.startswith("InfoLogo_") and o.data.font
             and "Windows/Fonts" in o.data.font.filepath]
    if not texts:
        return []
    if not os.path.exists(MAC_ARIAL_BOLD):
        return []   # on Windows the original path works; nothing to fix
    font = bpy.data.fonts.load(MAC_ARIAL_BOLD, check_existing=True)
    dg = None
    done = []
    for ob in texts:
        ob.data.font = font
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        me.name = ob.name
        new = bpy.data.objects.new(ob.name + "_mesh", me)
        new.matrix_world = ob.matrix_world.copy()
        new.parent = ob.parent
        new.matrix_parent_inverse = ob.matrix_parent_inverse.copy()
        new.location, new.rotation_euler, new.scale = ob.location.copy(), ob.rotation_euler.copy(), ob.scale.copy()
        for c in ob.users_collection:
            c.objects.link(new)
        new.hide_render, new.hide_viewport = ob.hide_render, ob.hide_viewport
        name = ob.name
        bpy.data.objects.remove(ob)
        new.name = name
        done.append(name)
    if font.users == 0:
        bpy.data.fonts.remove(font)
    return done


def apply():
    out = {}
    for p in PACKAGES:
        m = importlib.import_module("detail_" + p)
        importlib.reload(m)
        r = m.apply()
        out[p] = {k: r.get(k) for k in ("objects_added", "triangles_added")}
    hide_stray_baseboard()
    out["info_logo_frozen"] = freeze_info_logo_text()
    return out


if __name__ == "__main__":
    print("DETAIL_PASS", apply())
    if "--save" in sys.argv:
        bpy.ops.wm.save_mainfile()
        print("DETAIL_PASS saved", bpy.data.filepath)
