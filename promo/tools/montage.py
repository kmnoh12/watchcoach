"""Blender -b -P tools/montage.py -- out.png cols in1.png in2.png ..."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bake_poses_grid as G
a = sys.argv[sys.argv.index("--") + 1:]
G.grid([(os.path.basename(p), p) for p in a[2:]], a[0], int(a[1]))
