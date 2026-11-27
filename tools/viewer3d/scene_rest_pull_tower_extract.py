"""Read the complete evaluated assisted-tower exteriors from the saved gym."""

import json
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene_rest_cable_extract import named_mesh


PARTS = {
    "frame_foot": "foot.009",
    "frame_post": "post",
    "frame_crossbeam": "knee_carrier",
    "frame_brace": "step_support",
    "handle_support": "handle_arm",
    "step_platform": "step",
    "dip_handle": "dip_grip",
    "hand_grip": "pull",
    "pullup_bar": "bar.005",
}


if __name__ == "__main__":
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    tower = bpy.data.objects["P_assisted_pullup"]
    assert all(bpy.data.objects[name] in tower.children_recursive for name in PARTS.values())
    parts = {role: named_mesh(name) for role, name in PARTS.items()}
    destination = Path(__file__).with_name("scene_rest_pull_tower_source.json")
    payload = json.dumps(parts, separators=(",", ":")) + "\n"
    if "--check" in sys.argv:
        assert destination.read_text() == payload
    else:
        destination.write_text(payload)
    print({key: len(part["t"]) for key, part in parts.items()})
