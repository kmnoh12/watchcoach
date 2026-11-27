"""Read evaluated structural tubes and grips from the saved gym rack."""

import json
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene_rest_cable_extract import named_mesh


PARTS = {
    "base_beam": ("base", 108),
    "frame_brace": ("brace", 108),
    "frame_crossbeam": ("back_top", 108),
    "handle_support": ("pu_arm", 108),
    "pullup_bar": ("pullup", 76),
    "top_beam": ("side_top", 108),
}


def extract():
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    rack = bpy.data.objects["P_power_rack"]
    parts = {}
    for role, (name, count) in PARTS.items():
        assert bpy.data.objects[name].parent == rack
        donor = named_mesh(name)
        assert len(donor["t"]) == count, name
        parts[role] = donor
    return parts


if __name__ == "__main__":
    path = Path(__file__).with_name("scene_rest_pull_rack_source.json")
    parts = extract()
    payload = json.dumps(parts, separators=(",", ":")) + chr(10)
    if "--check" in sys.argv:
        assert path.read_text() == payload
    else:
        path.write_text(payload)
    print({key: len(part["t"]) for key, part in parts.items()})
