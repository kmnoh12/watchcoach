"""detail8 watchcoach_sign_move: hang the round WatchCoach projecting sign on the gym-side hallway
wall right above the Rocket Fresh cooler-bag stack (beside the gym entrance) instead of over the
vacant unit 303 on the opposite wall.

Moves only the "Sign_WatchCoach" root (children follow). Sets an absolute world transform, so it can
be re-run safely.

Run (never saves unless --save is given):
  Blender -b promo/scenes/scene_gym.blend --python promo/tools/detail8_watchcoach_sign_move.py [-- --save]
"""
import math
import sys

import bpy
from mathutils import Euler, Matrix, Vector

SIGN = "Sign_WatchCoach"
STACK = "Hallway_RocketFreshStack"
BACK = 0.354      # sign root -> back of its wall plate (r 0.23 + 0.115 + half plate 0.009)
Z = 2.32          # same hanging height as before


def main():
    sign = bpy.data.objects[SIGN]
    stack = bpy.data.objects[STACK].matrix_world.translation
    dg = bpy.context.evaluated_depsgraph_get()
    hit, loc, nrm, *_ = bpy.context.scene.ray_cast(dg, Vector((stack.x, stack.y, Z)), Vector((1, 0, 0)))
    if not hit or nrm.x > -0.9:
        raise SystemExit("gym-side wall not found beside the fresh-bag stack")
    # local +y (wall-plate side) must point to world +x (the gym wall) -> world yaw -90 deg
    target = Vector((loc.x - BACK, stack.y, Z))
    sign.matrix_world = Matrix.Translation(target) @ Euler((0, 0, -math.pi / 2)).to_matrix().to_4x4()
    print(f"SIGN_OK wall_x={loc.x:.3f} sign={tuple(round(v, 3) for v in target)}")
    if "--save" in sys.argv:
        bpy.ops.wm.save_mainfile(compress=True)
        print("SIGN_SAVED")


main()
