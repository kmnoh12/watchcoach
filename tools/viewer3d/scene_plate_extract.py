"""Extract the eight saved gym plate meshes (metres, local Z axle), without saving the scene.
blender -b --disable-autoexec promo/scenes/scene_gym.blend --python-exit-code 1 -P tools/viewer3d/scene_plate_extract.py [-- --check]
"""
import json
from pathlib import Path
import sys

import bpy

PREFIX = 'Dgym_freeweight_Plate_'


def extract():
    assert bpy.app.background
    plates = {}
    dg = bpy.context.evaluated_depsgraph_get()
    for obj in sorted(bpy.context.scene.objects, key=lambda o: o.name):
        if not obj.name.startswith(PREFIX):
            continue
        key = obj.data.name.removeprefix(PREFIX)
        if key in plates:
            continue
        ob = obj.evaluated_get(dg)
        me = ob.to_mesh()
        try:
            assert [m.name for m in me.materials] == ['Dgym_freeweight_PlateFaces', 'Dgym_freeweight_Chrome']
            me.calc_loop_triangles()
            parts = []
            for slot, expected in enumerate((480, 320)):
                lookup, verts, uv, tris = {}, [], [], []
                for tri in me.loop_triangles:
                    if tri.material_index != slot:
                        continue
                    for loop in tri.loops:
                        vi = me.loops[loop].vertex_index
                        u = tuple(round(x, 7) for x in me.uv_layers.active.data[loop].uv)
                        # The chrome bore and rim have sharp edges in the scene.
                        # Split those normal fans as well as the UV seams before
                        # the viewer computes normals on the indexed geometry.
                        normal = tuple(round(x, 5) for x in me.corner_normals[loop].vector)
                        vertex = (vi, u, normal)
                        if vertex not in lookup:
                            lookup[vertex] = len(verts)
                            verts.append([round(x, 7) for x in me.vertices[vi].co]); uv.append(u)
                        tris.append(lookup[vertex])
                assert len(tris) == 3 * expected
                parts.append(dict(v=verts, uv=uv, t=tris))
            plates[key] = parts
        finally:
            ob.to_mesh_clear()
    assert set(plates) == {'b25','b20','b15','b10','b5','i20','i10','i5'}
    return plates


if __name__ == '__main__':
    out = Path(__file__).with_name('scene_plate_source.json')
    data = json.dumps(extract(), separators=(',', ':'), sort_keys=True) + chr(10)
    if '--check' in sys.argv:
        assert out.read_text() == data
    else:
        out.write_text(data)
    print('8 scene meshes, 6400 original triangles, face-corner UVs')
