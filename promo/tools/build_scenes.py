"""Build the flat scene and the empty gym interior with their previews.
Run: Blender -b --factory-startup -P tools/build_scenes.py -- [flat|gym|all]"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import wc_lib as W
which = (sys.argv[sys.argv.index("--") + 1:] or ["all"])[0] if "--" in sys.argv else "all"
out = {}
for kind in (["flat", "gym"] if which == "all" else [which]):
    sc = W.new_scene(kind, bg="yellow")
    if kind == "gym":
        from reel_gym import stage_reel
        stage_reel()
        W.frame_gym_interior()
    else:
        g = W.add_hero("Guy")
        W.apply_pose(g, "stand")
    path = W.save(os.path.join(W.ROOT, "scenes", f"scene_{kind}.blend"))
    if kind == "gym":
        W.render_still(os.path.join(W.ROOT, "renders", "scenes", "gym_interior.png"))
    else:
        sc.render.resolution_percentage = 50
        for cam in ("Cam_Front", "Cam_Side", "Cam_Low"):
            W.use_camera(cam)
            W.render_still(os.path.join(W.ROOT, "renders", "scenes", f"{kind}_{cam}.png"))
    out[kind] = path
print("@@JSON@@", out)
