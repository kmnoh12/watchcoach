"""Extract full-resolution pull-station exteriors from the saved gym scene."""

import json
from pathlib import Path
import sys

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene_rest_cable_extract import named_mesh, orient


def assembly(name, details, axes, *, relief=False):
    """Preserve the evaluated backing and all its selected surface details."""
    root = bpy.data.objects[name]
    graph = bpy.context.evaluated_depsgraph_get()
    origin = root.evaluated_get(graph).matrix_world.inverted()
    layers = []
    for obj in [root, *details]:
        ev = obj.evaluated_get(graph)
        mesh = ev.to_mesh()
        try:
            mesh.calc_loop_triangles()
            transform = np.asarray(origin @ ev.matrix_world)
            v = np.asarray([p.co[:] for p in mesh.vertices]) @ transform[:3, :3].T + transform[:3, 3]
            v = orient(v, axes)
            mat = mesh.materials[0]
            layers.append((v, dict(object=obj.name, t=[list(f.vertices) for f in mesh.loop_triangles],
                                   material=mat.name, rgb=list(mat.diffuse_color[:3]), smooth=False)))
        finally:
            ev.to_mesh_clear()
    if relief:
        # The source print sits almost flush. Give it relief in the packed viewer
        # so the face and the ink stay distinct after depth and mesh quantization.
        backing_front = layers[0][0][:, 1].min()
        for v, _ in layers[1:]:
            v[:, 1] -= max(0.0, v[:, 1].max() - backing_front + .0012)
    all_v = np.vstack([v for v, _ in layers])
    centre = (all_v.min(0) + all_v.max(0)) / 2
    return [dict(layer, v=(v - centre).round(7).tolist()) for v, layer in layers]


def extract():
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    ribs = [bpy.data.objects[n] for n in ("foot_rib", *(f"foot_rib.{i:03d}" for i in range(1, 5)))]
    return {
        "footplate__001": assembly("foot_plate", ribs, (1, 2, 3)),
        "sign_panel__001": assembly("Exercise guide.019", bpy.data.objects["Exercise guide.019"].children,
                                     (1, -3, 2), relief=True),
        "badge__001": assembly("Exercise guide.003", [bpy.data.objects["Mark LAT PULLDOWN.001"]],
                                (1, -3, 2), relief=True),
        "pivot_cover__001": named_mesh("lever_bearing_cap", axes=(2, 3, 1)),
        "bar_sleeve__003": named_mesh("peg.015"),
        "lever_arm": named_mesh("pull_arm"),
        "footplate_support": named_mesh("footboard_mount"),
        "row_grip": named_mesh("row_grip"),
    }


if __name__ == "__main__":
    source = extract()
    path = Path(__file__).with_name("scene_pull_rest_source.json")
    encoded = json.dumps(source, separators=(",", ":")) + "\n"
    if "--check" in sys.argv:
        assert path.read_text() == encoded
    else:
        path.write_text(encoded)
    print({k: sum(len(p["t"]) for p in (v if isinstance(v, list) else [v])) for k, v in source.items()})
