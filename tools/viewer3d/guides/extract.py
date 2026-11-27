"""Bake the original gym placard's ink (not the machine) to flat 0.1 mm triangles.
Blender -b promo/scenes/scene_gym.blend --python tools/viewer3d/guides/extract.py
"""
import json
from pathlib import Path

import bpy
import numpy as np


def extract(plate):
    points, indices, lookup = [], [], {}

    def triangle(a, b, c):
        tri = np.rint(np.array([a, b, c]) * 10000).astype(int)
        x, y = tri[1] - tri[0]; u, v = tri[2] - tri[0]
        if x*v == y*u:
            return
        for pt in (tri if x*v > y*u else tri[::-1]):
            key = tuple(pt.tolist())
            if key not in lookup:
                lookup[key] = len(points); points.append(key)
            indices.append(lookup[key])

    for o in sorted(plate.children_recursive, key=lambda c: c.name):
        local = plate.matrix_world.inverted() @ o.matrix_world
        if o.type == 'CURVE':
            for spline in o.data.splines:
                xy = np.array([(local @ p.co.xyz)[:2] for p in spline.points]); d = np.diff(xy, axis=0)
                normals = d[:, ::-1] * [-1, 1] / np.linalg.norm(d, axis=1)[:, None]
                n = np.vstack([normals[0], normals[:-1] + normals[1:], normals[-1]])
                n /= np.sum(n * np.vstack([normals, normals[-1]]), axis=1)[:, None]
                a, b = xy + n*o.data.bevel_depth, xy - n*o.data.bevel_depth
                for i in range(len(xy)-1):
                    triangle(a[i], b[i], b[i+1]); triangle(a[i], b[i+1], a[i+1])
        elif o.type == 'FONT':
            o.data.resolution_u = 2  # ink at mobile scale, no extrusion or sidewalls
            evaluated = o.evaluated_get(bpy.context.evaluated_depsgraph_get()); mesh = evaluated.to_mesh()
            mesh.calc_loop_triangles()
            for t in mesh.loop_triangles:
                triangle(*[(local @ mesh.vertices[i].co)[:2] for i in t.vertices])
            evaluated.to_mesh_clear()
        elif o.name.startswith('Guide head'):
            xy = np.array([(local @ v.co)[:2] for v in o.data.vertices]); lo, hi = xy.min(0), xy.max(0)
            c, r = (hi + lo)/2, (hi - lo)/2; t = np.arange(10)*np.pi/5
            ring = c + r * np.column_stack([np.cos(t), np.sin(t)])
            for a,b in zip(ring, np.roll(ring, -1, axis=0)):
                triangle(c, a, b)
    return dict(xz=points, tris=indices)


art = extract(bpy.data.objects["Exercise guide.003"])
Path(__file__).with_name("lat_pulldown.json").write_text(json.dumps(art, separators=(",", ":")) + "\n")
