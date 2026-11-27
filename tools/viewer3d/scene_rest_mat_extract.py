"""Extract the evaluated rubber shells and finishes of the gym ab wheel."""

import json
from pathlib import Path
import sys

import bpy
import numpy as np


def extract():
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    wheel = bpy.data.objects["Dgym_life_AbWheel"]
    evaluated = wheel.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        assert [m.name for m in mesh.materials] == [
            "Dgym_life_Rubber", "Dgym_life_ShakerRed", "Dgym_life_Chrome"
        ]
        mesh.calc_loop_triangles()
        vertices = np.asarray([vertex.co[:] for vertex in mesh.vertices])
        result = {}
        for role, lo, hi, sides in [("wheel_tire", -.04, .04, 24), ("foam_grip", .06, .18, 12)]:
            faces = []
            for tri in mesh.loop_triangles:
                ids = list(tri.vertices)
                x = vertices[ids, 0]
                if mesh.polygons[tri.polygon_index].material_index == 0 and np.all((x > lo) & (x < hi)):
                    faces.append(ids)
            used, indices = np.unique(faces, return_inverse=True)
            assert len(used) == 2 * sides and len(faces) == 4 * sides - 4
            points = vertices[used].copy()
            points -= (points.min(0) + points.max(0)) / 2
            result[role] = dict(v=points.round(7).tolist(), t=indices.reshape(-1, 3).tolist(),
                                rgb=[round(c, 6) for c in mesh.materials[0].diffuse_color[:3]])
        result["wheel_spoke"] = dict(rgb=[round(c, 6) for c in mesh.materials[1].diffuse_color[:3]])
    finally:
        evaluated.to_mesh_clear()
    mat = bpy.data.objects["Stretch mat 1"].data.materials[0]
    assert mat.name == "StretchMat_Sage"
    result["floor_mat"] = dict(rgb=[round(c, 6) for c in mat.diffuse_color[:3]])
    return result


if __name__ == "__main__":
    source = extract()
    path = Path(__file__).with_name("scene_rest_mat_source.json")
    payload = json.dumps(source, separators=(",", ":")) + "\n"
    if "--check" in sys.argv:
        assert path.read_text() == payload
    else:
        path.write_text(payload)
    print({role: len(part.get("t", [])) for role, part in source.items()})
