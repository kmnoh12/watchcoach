"""Extract full-resolution press-station exteriors from the saved gym."""

import json
from pathlib import Path
import sys

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene_pull_rest_extract import assembly
from scene_rest_cable_extract import named_mesh


def extract():
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    out = {
        "hand_grip": named_mesh("grip.004"),
        "handle_end_cap": named_mesh("pec_grip_cap1"),
        "pivot_cover": named_mesh("fly_hinge_cap"),
        "handle_stem": named_mesh("grip_stem"),
    }
    for key, guide in (("pec_deck", "Exercise guide.001"),
                       ("preacher_machine", "Exercise guide.025")):
        backing = bpy.data.objects[guide]
        layers = assembly(guide, sorted(backing.children, key=lambda obj: obj.name), (1, -3, 2), relief=True)
        # Keep the print close to the backing after the panel is scaled to the app envelope.
        vertices = [np.asarray(layer["v"]) for layer in layers]
        for detail in vertices[1:]:
            detail[:, 1] += .00065
        depth = np.concatenate([part[:, 1] for part in vertices])
        middle = (depth.min() + depth.max()) / 2
        for layer, part in zip(layers, vertices):
            part[:, 1] -= middle
            layer["v"] = part.round(7).tolist()
        out[key] = layers
    return out


if __name__ == "__main__":
    path = Path(__file__).with_name("scene_press_rest_source.json")
    source = extract()
    payload = json.dumps(source, separators=(",", ":")) + chr(10)
    if "--check" in sys.argv:
        assert path.read_text() == payload
    else:
        path.write_text(payload)
    print({k: sum(len(row["t"]) for row in (v if isinstance(v, list) else [v])) for k, v in source.items()})
