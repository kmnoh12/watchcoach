"""Extract full evaluated free-weight and exercise mat meshes from the saved gym scene."""

import json
from pathlib import Path
import sys

import bpy
import numpy as np


SOURCES = {
    "barbell_shaft__001": ("P_barbell", "bar", "E_knurl"),
    "bar_sleeve__001": ("P_barbell", "sleeve.001", "E_steel"),
    "bar_collar__001": ("P_barbell", "lock_collar.001", "E_silver"),
    "floor_mat__002": ("Gym_StretchingZone", "Stretch mat 3", "StretchMat_Charcoal"),
    "ez_bar__002": ("Fixed EZ-bar rack", "EZ bar shaft 10kg", "Brushed alloy"),
    "hex_bar_frame__001": ("Cable grip rack", "Rack upright front", "Accessory rack steel"),
    "sleeve_shoulder__004": ("P_barbell", "flange.001", "E_steel"),
}


def extract():
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    deps = bpy.context.evaluated_depsgraph_get()
    result = {}
    for group, (parent, name, material) in SOURCES.items():
        obj = bpy.data.objects[name]
        assert obj.parent.name == parent
        ev = obj.evaluated_get(deps)
        mesh = ev.to_mesh()
        try:
            assert [m.name for m in mesh.materials] == [material]
            mesh.calc_loop_triangles()
            v = np.array([vertex.co[:] for vertex in mesh.vertices])
            if group == "floor_mat__002":
                # Orient the mat's long side along local Y. Its dimensions are in object scale.
                transform = obj.parent.matrix_world.inverted() @ ev.matrix_world
                v = (v @ np.asarray(transform.to_3x3()).T)[:, [1, 0, 2]]
                v[:, 0] *= -1
            elif group != "ez_bar__002":
                # The authored cylinders already use local Z as their axle.
                v *= np.asarray(ev.scale)
            else:
                # Keep the full curved reference and sample its straight terminal
                # cross-section at 24 sides for the app's separately tracked pieces.
                profile = obj.copy()
                profile.data = obj.data.copy()
                bpy.context.scene.collection.objects.link(profile)
                curve = profile.data
                try:
                    curve.bevel_resolution = 10
                    curve.use_fill_caps = False
                    bpy.context.view_layer.update()
                    profile_eval = profile.evaluated_get(deps)
                    mesh_ring = profile_eval.to_mesh()
                    try:
                        ring = np.array([vert.co[:] for vert in mesh_ring.vertices])
                        ring = ring[np.isclose(ring[:, 0], ring[:, 0].max()), 1:]
                        assert len(ring) == 24
                        ring -= (ring.max(0) + ring.min(0)) / 2
                    finally:
                        profile_eval.to_mesh_clear()
                finally:
                    bpy.data.objects.remove(profile, do_unlink=True)
                    bpy.data.curves.remove(curve)
            v -= (v.max(0) + v.min(0)) / 2
            result[group] = dict(
                object=name,
                material=material,
                rgb=[round(c, 6) for c in mesh.materials[0].diffuse_color[:3]],
                v=v.round(7).tolist(),
                t=[list(tri.vertices) for tri in mesh.loop_triangles],
                smooth=[bool(mesh.polygons[tri.polygon_index].use_smooth) for tri in mesh.loop_triangles],
            )
            if group == "ez_bar__002":
                result[group]["ring"] = ring.round(7).tolist()
        finally:
            ev.to_mesh_clear()
    return result


if __name__ == "__main__":
    path = Path(__file__).with_name("scene_rest_bar_source.json")
    out = extract()
    data = json.dumps(out, separators=(",", ":")) + chr(10)
    if "--check" in sys.argv:
        assert path.read_text() == data
    else:
        path.write_text(data)
    print({group: len(obj["t"]) for group, obj in out.items()})
