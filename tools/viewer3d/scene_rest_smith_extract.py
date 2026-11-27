"""Extract evaluated Smith frame and hardware meshes from the saved gym."""

import json
from pathlib import Path
import sys

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene_rest_cable_extract import named_mesh, orient


def upright():
    obj = bpy.data.objects["Perforated upright.006"]
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        vertices = orient(np.array([v.co[:] for v in mesh.vertices]), (3, 2, -1))
        vertices -= (vertices.min(0) + vertices.max(0)) / 2
        return dict(
            v=vertices.round(7).tolist(),
            t=[list(t.vertices) for t in mesh.loop_triangles],
            slots=[t.material_index for t in mesh.loop_triangles],
            finishes={m.name: [round(c, 6) for c in m.diffuse_color[:3]] for m in mesh.materials},
        )
    finally:
        evaluated.to_mesh_clear()


def extract():
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    machine = bpy.data.objects["P_smith_machine"]
    parts = {
        "frame_foot": "foot.005",
        "top_beam": "top.001",
        "guide_rail": "rail",
        "storage_peg": "peg.009",
    }
    assert all(bpy.data.objects[name].parent == machine for name in (*parts.values(), "Perforated upright.006"))
    return {"frame_post": upright(), **{role: named_mesh(name) for role, name in parts.items()}}


if __name__ == "__main__":
    path = Path(__file__).with_name("scene_rest_smith_source.json")
    parts = extract()
    payload = json.dumps(parts, separators=(",", ":")) + "\n"
    if "--check" in sys.argv:
        assert path.read_text() == payload
    else:
        path.write_text(payload)
    print({role: len(part["t"]) for role, part in parts.items()})
