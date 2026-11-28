"""detail8 mural_fullres: swap the 21 m bodybuilder "Locker wall mural" texture from the
downscaled gym_wall_opt JPG (2048x341) to the original gym_print PNG (4344x724).

Touches ONLY the image used by the "Locker wall mural" material. Geometry, UVs and the
material graph stay as they are (same 6:1 aspect, UV 0..1).

Run (never saves unless --save is given):
  Blender -b promo/scenes/scene_gym.blend --python promo/tools/detail8_mural_fullres.py [-- --save]
"""
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "parts" / "gym_print" / "locker_mural.png"
MAT = "Locker wall mural"


def main():
    mat = bpy.data.materials.get(MAT)
    if mat is None or not mat.node_tree:
        raise SystemExit(f"material {MAT!r} not found")
    texs = [n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE"]
    if not texs:
        raise SystemExit("no image node on mural material")
    old = texs[0].image
    img = bpy.data.images.get("locker_mural_fullres")
    if img is None:
        img = bpy.data.images.load(str(SRC), check_existing=False)
        img.name = "locker_mural_fullres"
    img.colorspace_settings.name = old.colorspace_settings.name if old else "sRGB"
    if not img.packed_file:
        img.pack()
    for n in texs:
        n.image = img
    if old and old != img and old.users == 0:
        bpy.data.images.remove(old)
    print(f"MURAL_OK {img.size[0]}x{img.size[1]} (was {old.size[0]}x{old.size[1]} {old.name})" if old else "MURAL_OK")
    if "--save" in sys.argv:
        bpy.ops.wm.save_mainfile()
        print("MURAL_SAVED")


main()
