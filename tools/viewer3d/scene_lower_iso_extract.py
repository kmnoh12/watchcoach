"""Extract complete lower-machine exteriors from the saved gym scene."""

import json
from pathlib import Path
import sys

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene_cable_extract import select
from scene_rest_cable_extract import encode, island, named_mesh, orient


PARTS = {
    'footplate': ('P_leg_press_45', 'footplate', 108),
    'footplate_tread': ('P_leg_press_45', 'traction_rib', 108),
    'hand_grip': ('P_seated_leg_curl', 'curl_grip', 76),
    'handle_end_cap': ('P_hip_abductor', 'side_grip_cap1.004', 76),
    'pivot_cover': ('P_leg_extension', 'leg_pivot_cap', 92),
    'roller_end_cap': ('P_seated_leg_curl', 'roller_cap_l', 76),
    'sign_panel': ('P_leg_extension', 'Service panel.014', 108),
}


def extract():
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    parts = {}
    for role, (root, name, count) in PARTS.items():
        assert bpy.data.objects[name] in bpy.data.objects[root].children_recursive
        part = named_mesh(name)
        assert len(part['t']) == count, name
        parts[role] = part
    frame = bpy.data.objects['Ddetail6_SM_LE_Frame']
    assert frame in bpy.data.objects['P_leg_extension'].children_recursive
    evaluated = frame.evaluated_get(bpy.context.evaluated_depsgraph_get())
    geometry = evaluated.to_mesh()
    geometry.calc_loop_triangles()
    v = np.asarray([point.co[:] for point in geometry.vertices])
    t = np.asarray([face.vertices[:] for face in geometry.loop_triangles])
    m = np.asarray([face.material_index for face in geometry.loop_triangles])
    evaluated.to_mesh_clear()
    for role, center, size, axes, slot, count in (
        ('base_runner', (0, -.005, .050), (.084, 1.290, .084), (2, -1, 3), 0, 108),
        ('frame_post', (-.200, -.295, .308), (.034, .036, .488), (3, 2, -1), 0, 44),
        ('rubber_foot', (0, -.570, .00375), (.094, .120, .016), (1, 2, 3), 2, 44),
    ):
        corner = np.asarray(center) + np.asarray(size) / 2
        candidates = np.unique(t[m == slot])
        seed = candidates[np.linalg.norm(v[candidates] - corner, axis=1).argmin()]
        vv, tt, slots = select(v, t, m, island(t, seed, len(v)))
        assert np.allclose(np.ptp(vv, axis=0), size, atol=.0001), role
        assert len(tt) == count and np.all(slots == slot), role
        vv = orient(vv - (vv.min(0) + vv.max(0)) / 2, axes)
        parts[role] = encode(vv, tt, frame.data.materials[slot], [False] * len(tt))
    return parts


if __name__ == '__main__':
    output = Path(__file__).with_name('scene_lower_iso_source.json')
    source = extract()
    encoded = json.dumps(source, separators=(',', ':')) + chr(10)
    if '--check' in sys.argv:
        assert output.read_text() == encoded
    else:
        output.write_text(encoded)
    print({role: len(part['t']) for role, part in source.items()})
