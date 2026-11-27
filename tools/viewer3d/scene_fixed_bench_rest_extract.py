"""Extract the full molded gym rubber foot and bar end badge from the saved scene."""

import json
from pathlib import Path
import sys

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene_cable_extract import mesh, select


def part(vertices, triangles, material):
    vertices = vertices - (vertices.min(0) + vertices.max(0)) / 2
    return dict(v=vertices.round(7).tolist(), t=triangles.ravel().tolist(),
                rgb=list(material.diffuse_color[:3]))


def extract():
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    chassis = "Ddetail6_LP_LowerChassis"
    v, t, slots = mesh(chassis, "P_lat_pulldown")
    # The molded pad is a complete separate island under the right crossbar.
    center = np.array([0.295, -0.550, 0.0085])
    half_size = np.array([0.045, 0.031, 0.0085])
    rubber_faces = slots == 2
    foot, faces, materials = select(v, t[rubber_faces], slots[rubber_faces],
                                    (abs(v - center) <= half_size + 1e-6).all(1))
    assert set(materials) == {2}
    assert np.allclose(np.ptp(foot, axis=0), 2 * half_size, atol=1e-6)
    rubber = bpy.data.objects[chassis].material_slots[2].material

    badge = bpy.data.objects["end_badge"]
    assert badge.parent.name == "P_barbell"
    ev = badge.evaluated_get(bpy.context.evaluated_depsgraph_get())
    evaluated = ev.to_mesh()
    try:
        evaluated.calc_loop_triangles()
        color, = evaluated.materials
        assert color.name == "E_accent"
        cap = part(np.array([p.co[:] for p in evaluated.vertices]) * np.asarray(ev.scale),
                   np.array([tri.vertices[:] for tri in evaluated.loop_triangles]), color)
    finally:
        ev.to_mesh_clear()
    return {"rubber_foot": part(foot, faces, rubber), "end_cap": cap}


if __name__ == "__main__":
    destination = Path(__file__).with_name("scene_fixed_bench_rest_source.json")
    source = extract()
    serial = json.dumps(source, separators=(",", ":")) + "\n"
    if "--check" in sys.argv:
        assert destination.read_text() == serial
    else:
        destination.write_text(serial)
    print({role: len(part["t"]) // 3 for role, part in source.items()})
