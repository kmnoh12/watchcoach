"""Read the saved P_flat_bench in background mode; export all cushion and trim triangles."""

import json
from pathlib import Path
import sys

import bpy
import numpy as np


def extract():
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    root = bpy.data.objects["P_flat_bench"]
    dg = bpy.context.evaluated_depsgraph_get()
    inv = root.evaluated_get(dg).matrix_world.inverted()
    out = {}
    for key, name in [
        ("back_pad", "back.001"),
        ("seat_pad", "seat.002"),
        ("trim", "trim"),
    ]:
        obj = bpy.data.objects[name]
        assert obj in root.children_recursive
        ev = obj.evaluated_get(dg)
        mesh = ev.to_mesh()
        try:
            mat = np.array(inv @ ev.matrix_world)
            vertices = (
                np.array([v.co[:] for v in mesh.vertices]) @ mat[:3, :3].T + mat[:3, 3]
            )
            assert np.linalg.det(mat[:3, :3]) > 0
            mesh.calc_loop_triangles()
            tris = np.array([t.vertices[:] for t in mesh.loop_triangles])
            slots = np.array([t.material_index for t in mesh.loop_triangles])
            layers = []
            for idx, slot in enumerate(obj.material_slots):
                used, remap = np.unique(tris[slots == idx], return_inverse=True)
                layers.append(
                    dict(
                        material=slot.name,
                        v=vertices[used].round(6).tolist(),
                        t=remap.ravel().tolist(),
                        rgb=list(slot.material.diffuse_color[:3]),
                    )
                )
            assert [p["material"] for p in layers] == (
                ["E_grip"] if key == "trim" else ["E_pad", "E_stitch"]
            )
            assert len(tris) == (108 if key == "trim" else 476)
            out[key] = layers
        finally:
            ev.to_mesh_clear()
    return out


if __name__ == "__main__":
    path = Path(__file__).with_name("scene_flat_bench_source.json")
    data = json.dumps(extract(), separators=(",", ":"))
    if "--check" in sys.argv:
        assert path.read_text() == data
    else:
        path.write_text(data)
