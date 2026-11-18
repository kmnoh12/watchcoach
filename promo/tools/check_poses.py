import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wc_lib as W, bpy
argv = sys.argv[sys.argv.index("--")+1:]
names = argv[0].split(","); view = argv[1] if len(argv)>1 else "front"; who = argv[2] if len(argv)>2 else "hero"
W.new_scene("flat", bg="gray", preview=True)
arm = W.add_hero("Guy") if who=="hero" else W.add_extra(who)
sc=bpy.context.scene; sc.render.resolution_percentage=35
cam=W.use_camera("Cam_Front")
pos={"front":((0,-4.2,1.1),(0,0,0.85)),"three":((2.6,-3.4,1.3),(0,0,0.85)),"back":((-2.4,3.4,1.3),(0,0,0.85))}[view]
cam.location, t = pos; W.look_at(cam,t); cam.data.lens=50
import bake_poses_grid as G
tiles=[]
for n in names:
    W.apply_pose(arm,n); tiles.append((n, W.render_still(os.path.join(W.ROOT,"renders","_pose_tmp",f"chk_{view}_{n}.png"))))
G.grid(tiles, os.path.join(W.ROOT,"renders","_pose_tmp",f"check_{view}_{who}.png"), min(4,len(tiles)))
