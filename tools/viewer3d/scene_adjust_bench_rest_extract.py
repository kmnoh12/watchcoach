"""Extract evaluated bench and free weight exteriors from the saved gym scene.

Blender -b --factory-startup --disable-autoexec promo/scenes/scene_gym.blend
    --python-exit-code 1 -P tools/viewer3d/scene_adjust_bench_rest_extract.py [-- --check]
"""

import json
from pathlib import Path
import sys

import bpy
import numpy as np


def extract():
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    dg = bpy.context.evaluated_depsgraph_get()
    objects = bpy.data.objects
    out = {}
    for role, name, root in (
        ("base_beam", "spine.001", "P_adjustable_bench"),
        ("base_crossfoot", "foot_f", "P_adjustable_bench"),
        ("frame_post", "leg_f", "P_adjustable_bench"),
        ("dumbbell_grip", "handle.010", "P_dumbbell.010"),
        ("dumbbell_cap", "ferrule.020", "P_dumbbell.010"),
        ("dumbbell_head", "Dgym_freeweight_DB_12_26", None),
    ):
        obj = objects[name]
        if root:
            assert obj in objects[root].children_recursive
        evaluated = obj.evaluated_get(dg)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            v = np.asarray([p.co[:] for p in mesh.vertices])
            t = np.asarray([p.vertices[:] for p in mesh.loop_triangles])
            material, = obj.material_slots if root else obj.material_slots[:1]
            if role == "dumbbell_head":
                # Take one complete rubber head. The other is mirrored on the rack.
                slots = np.asarray([p.material_index for p in mesh.loop_triangles])
                mask = (v[:, 1] > 0)[t].all(1)
                assert mask[slots == 0].sum() * 2 == (slots == 0).sum()
                t = t[mask & (slots == 0)]
                keep, indices = np.unique(t, return_inverse=True)
                t = indices.reshape(-1, 3)
                # Y axle -> Z axle. Keep the flat sides aligned with the legacy hex.
                v = v[keep][:, [2, 0, 1]]
            v -= (v.min(0) + v.max(0)) / 2
            out[role] = dict(
                v=v.round(7).tolist(), t=t.ravel().tolist(),
                rgb=list(material.material.diffuse_color[:3]),
            )
        finally:
            evaluated.to_mesh_clear()
    return out


if __name__ == "__main__":
    dest = Path(__file__).with_name("scene_adjust_bench_rest_source.json")
    source = extract()
    serial = json.dumps(source, separators=(",", ":")) + chr(10)
    if "--check" in sys.argv:
        assert dest.read_text() == serial
    else:
        dest.write_text(serial)
    print({role: len(part["t"]) // 3 for role, part in source.items()})
