"""Extract complete evaluated exterior pieces from the saved gym chest press."""

import json
from pathlib import Path
import sys

import bmesh
import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene_cable_extract import select
from scene_rest_cable_extract import encode, island, named_mesh, orient


ROOT = 'P_chest_press_machine'
PARTS = {
    'base_crossfoot': ('footbar', 108),
    'frame_crossbeam': ('pivot_bridge', 108),
    'footplate': ('foot_pedal', 76),
    'footplate_support': ('pedal_stem', 108),
    'pad_support': ('back_post.001', 108),
    'panel_mount': ('Guide mounting boss.005', 108),
    'pivot_cover': ('press_hub_cap', 92),
}


def guide_panel(root):
    panel = bpy.data.objects['Exercise guide.010']
    assert panel.parent == root
    dg = bpy.context.evaluated_depsgraph_get()
    origin = panel.evaluated_get(dg).matrix_world.inverted()
    pieces = []
    for obj in [panel, *sorted(panel.children, key=lambda child: child.name)]:
        evaluated = obj.evaluated_get(dg)
        mesh = evaluated.to_mesh()
        try:
            transform = np.asarray(origin @ evaluated.matrix_world)
            v = np.asarray([point.co[:] for point in mesh.vertices])
            v = v @ transform[:3, :3].T + transform[:3, 3]
            mesh.calc_loop_triangles()
            triangles = mesh.loop_triangles
            assert len(mesh.materials) == 1 and len(triangles), obj.name
            pieces.append(encode(orient(v, (1, -3, 2)), np.asarray([f.vertices[:] for f in triangles]),
                                 mesh.materials[0], [False] * len(triangles)))
        finally:
            evaluated.to_mesh_clear()
    return pieces


def frame_pieces(root):
    frame = bpy.data.objects['Ddetail6_SM_CP_Frame']
    assert frame.parent == root
    evaluated = frame.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        v = np.asarray([point.co[:] for point in mesh.vertices])
        t = np.asarray([face.vertices[:] for face in mesh.loop_triangles])
        m = np.asarray([face.material_index for face in mesh.loop_triangles])
        for role, center, size, slot, axes, count in (
            ('base_runner', (0, -.095, .05), (.086, 1.51, .084), 0, (2, -1, 3), 108),
            ('rubber_foot', (0, -.77, .00375), (.094, .120, .016), 2, (1, 2, 3), 44),
        ):
            ids = np.unique(t[m == slot])
            seed = ids[np.linalg.norm(v[ids] - (np.asarray(center) + np.asarray(size) / 2), axis=1).argmin()]
            vv, tt, slots = select(v, t, m, island(t, seed, len(v)))
            assert len(tt) == count and np.all(slots == slot) and np.allclose(np.ptp(vv, axis=0), size, atol=1e-5)
            yield role, encode(orient(vv - center, axes), tt, mesh.materials[slot], [False] * len(tt))
    finally:
        evaluated.to_mesh_clear()


def lever(root):
    obj = bpy.data.objects['lever_knuckle']
    assert obj in root.children_recursive
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        # The saved bevel contains collapsed corner faces. Weld only those
        # coincident samples before packing the full bevel into WGC2.
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.000015)
        bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=.000015)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        assert all(edge.is_manifold for edge in bm.edges)
        bm.verts.index_update()
        axis = np.asarray([-.080, -.020, -.340])
        axis /= np.linalg.norm(axis)
        side = np.cross(axis, [1, 0, 0])
        side /= np.linalg.norm(side)
        v = np.asarray([x.co[:] for x in bm.verts]) @ np.stack([axis, side, np.cross(axis, side)], axis=1)
        v -= (v.min(0) + v.max(0)) / 2
        t = np.asarray([[loop.vert.index for loop in triangle] for triangle in bm.calc_loop_triangles()])
        return encode(v, t, mesh.materials[0], [False] * len(t))
    finally:
        bm.free()
        evaluated.to_mesh_clear()


def extract():
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    root = bpy.data.objects[ROOT]
    parts = dict(frame_pieces(root))
    for role, (name, count) in PARTS.items():
        assert bpy.data.objects[name] in root.children_recursive
        shape = named_mesh(name)
        assert len(shape['t']) == count, name
        parts[role] = shape
    parts['lever_arm'] = lever(root)
    parts['sign_panel'] = guide_panel(root)
    return parts


if __name__ == '__main__':
    output = Path(__file__).with_name('scene_chest_press_rest_source.json')
    source = extract()
    encoded = json.dumps(source, separators=(',', ':')) + chr(10)
    if '--check' in sys.argv:
        assert output.read_text() == encoded
    else:
        output.write_text(encoded)
    print({role: sum(len(layer['t']) for layer in part) if isinstance(part, list) else len(part['t'])
           for role, part in source.items()})
