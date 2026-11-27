"""Extract uninterrupted evaluated meshes from the gym's plate-loaded row."""

import json
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene_rest_cable_extract import named_mesh


PARTS = {
    "frame_crossbeam": ("cross", 108),
    "frame_foot": ("foot.013", 108),
    "lever_arm": ("pull_arm", 108),
    "load_arm": ("load_arm", 108),
    "footplate": ("footboard", 108),
    "footplate_support": ("footrest_stay.002", 108),
    "hand_grip": ("neutral_grip", 76),
    "handle_end_cap": ("neutral_grip_cap1", 76),
    "pivot_cover": ("iso_bearing_cap", 92),
}


def extract():
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    parts = {}
    root = bpy.data.objects["P_plate_row"]
    for role, (name, triangle_count) in PARTS.items():
        assert bpy.data.objects[name] in root.children_recursive
        part = named_mesh(name)
        assert len(part["t"]) == triangle_count, name
        parts[role] = part
    return parts


if __name__ == "__main__":
    output = Path(__file__).with_name("scene_rest_pull_source.json")
    source = extract()
    encoded = json.dumps(source, separators=(",", ":")) + "\n"
    if "--check" in sys.argv:
        assert output.read_text() == encoded
    else:
        output.write_text(encoded)
    print({role: len(part["t"]) for role, part in source.items()})
