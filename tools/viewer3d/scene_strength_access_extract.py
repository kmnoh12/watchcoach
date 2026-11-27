"""Extract complete evaluated rack and plyo-box meshes from the saved gym scene."""

import json
from pathlib import Path
import sys

import bpy
import numpy as np


SOURCES = {
    "frame_post__002": ("Perforated upright", "P_power_rack"),
    "base_beam__001": ("base.001", "P_power_rack"),
    "frame_crossbeam__003": ("back_top", "P_power_rack"),
    "frame_rail__001": ("side_top", "P_power_rack"),
    "pullup_bar__001": ("pullup", "P_power_rack"),
    "frame_panel__001": ("Plyo box", "Gym_StretchingZone"),
    "hand_grip__007": ("neutral_pull", "P_power_rack"),
}


def wood_swatch(material):
    # WGM has no wood shader. Use a diffuse swatch from the scene's packed grain.
    nodes = material.node_tree.nodes
    texture = next(node.image for node in nodes if node.type == "TEX_IMAGE")
    hue = next(node for node in nodes if node.type == "HUE_SAT")
    pixels = np.empty(len(texture.pixels), dtype=np.float32)
    texture.pixels.foreach_get(pixels)
    samples = pixels.reshape(-1, 4)[::64, :3]
    if not texture.is_float and texture.colorspace_settings.name == "sRGB":
        samples = np.where(samples <= .04045, samples / 12.92, ((samples + .055) / 1.055) ** 2.4)
    saturation = hue.inputs["Saturation"].default_value
    color = samples * saturation + samples.max(1, keepdims=True) * (1 - saturation)
    return np.round(color.mean(0) * hue.inputs["Value"].default_value, 6).tolist()


def extract():
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    deps = bpy.context.evaluated_depsgraph_get()
    result = {}
    for group, (name, parent) in SOURCES.items():
        obj = bpy.data.objects[name]
        assert obj.parent.name == parent
        evaluated = obj.evaluated_get(deps)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            v = np.array([vertex.co[:] for vertex in mesh.vertices])
            if group == "frame_post__002":
                # App columns run along local X. Keep the bore along local Y.
                v = v[:, [2, 1, 0]]
                v[:, 2] *= -1
            v -= (v.max(0) + v.min(0)) / 2
            result[group] = dict(
                object=name,
                v=v.round(7).tolist(),
                t=[list(tri.vertices) for tri in mesh.loop_triangles],
                material=[tri.material_index for tri in mesh.loop_triangles],
                rgb=[list(mat.diffuse_color[:3]) for mat in mesh.materials],
            )
            if group == "frame_panel__001":
                result[group]["rgb"] = [wood_swatch(mesh.materials[0])]
        finally:
            evaluated.to_mesh_clear()
    return result


if __name__ == "__main__":
    path = Path(__file__).with_name("scene_strength_access_source.json")
    source = extract()
    data = json.dumps(source, separators=(",", ":")) + "\n"
    if "--check" in sys.argv:
        assert path.read_text() == data
    else:
        path.write_text(data)
    print({group: len(obj["t"]) for group, obj in source.items()})
