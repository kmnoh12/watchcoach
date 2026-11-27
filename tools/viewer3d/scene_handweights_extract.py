"""Extract the evaluated cast-iron kettlebell exterior from the saved gym scene."""

import json
from pathlib import Path
import sys

import bpy
import numpy as np


def extract():
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    depsgraph = bpy.context.evaluated_depsgraph_get()
    root = bpy.data.objects["Kettlebell 16kg"]
    body = bpy.data.objects["Kettlebell body 16kg"]
    handle = bpy.data.objects["Kettlebell handle 16kg"]
    assert body.parent == handle.parent == root
    evaluated = body.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        vertices = np.array([v.co[:] for v in mesh.vertices])
        triangles = [i for face in mesh.loop_triangles for i in face.vertices]
        vertices -= (vertices.min(0) + vertices.max(0)) / 2
        return {
            "cast_weight_body": dict(v=vertices.round(7).tolist(), t=triangles,
                                     rgb=list(body.material_slots[0].material.diffuse_color[:3])),
            "cast_handle": dict(rgb=list(handle.material_slots[0].material.diffuse_color[:3])),
        }
    finally:
        evaluated.to_mesh_clear()


if __name__ == "__main__":
    source = extract()
    output = Path(__file__).with_name("scene_handweights_source.json")
    payload = json.dumps(source, separators=(",", ":")) + "\n"
    if "--check" in sys.argv:
        assert output.read_text() == payload
    else:
        output.write_text(payload)
    print("cast_weight_body:", len(source["cast_weight_body"]["t"]) // 3, "triangles")
