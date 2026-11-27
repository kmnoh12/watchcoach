"""Read the full evaluated spine and brace from the saved gym benches."""

import json
from pathlib import Path
import sys

import bpy
import numpy as np


SOURCES = {
    "frame_spine": ("P_flat_bench", "spine", "E_frame", (0, 1, 2)),
    "frame_brace": ("P_adjustable_bench", "locking_stay", "E_silver", (1, 2, 0)),
}


def extract():
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    deps = bpy.context.evaluated_depsgraph_get()
    result = {}
    for role, (parent, name, material, axes) in SOURCES.items():
        obj = bpy.data.objects[name]
        assert obj.parent.name == parent
        ev = obj.evaluated_get(deps)
        mesh = ev.to_mesh()
        try:
            assert [m.name for m in mesh.materials] == [material]
            mesh.calc_loop_triangles()
            v = (np.array([vertex.co[:] for vertex in mesh.vertices]) * np.asarray(ev.scale))[:, axes]
            v -= (v.min(0) + v.max(0)) / 2
            result[role] = dict(
                v=v.round(7).tolist(),
                t=[i for tri in mesh.loop_triangles for i in tri.vertices],
                rgb=list(mesh.materials[0].diffuse_color[:3]),
            )
        finally:
            ev.to_mesh_clear()
    return result


if __name__ == "__main__":
    path = Path(__file__).with_name("scene_rest_bench_source.json")
    source = extract()
    data = json.dumps(source, separators=(",", ":")) + "\n"
    if "--check" in sys.argv:
        assert path.read_text() == data
    else:
        path.write_text(data)
    print({role: len(mesh["t"]) // 3 for role, mesh in source.items()})
