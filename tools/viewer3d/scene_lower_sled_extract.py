"""Read the complete evaluated exteriors of the saved gym's inclined leg press."""

import json
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene_rest_cable_extract import named_mesh


PARTS = {
    "base_runner": "base_runner",
    "frame_crossbeam": "cross_member",
    "frame_brace": "rear_stay",
    "frame_rail": "incline_stringer",
    "footplate": "footplate",
    "footplate_tread": "traction_rib",
    "hand_grip": "side_grip",
    "handle_end_cap": "side_grip_cap1",
    "loading_horn": "load_horn",
    "sleeve_bushing": "linear_bearing",
    "stop_bumper": "rubber_stop",
}


def extract():
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    machine = bpy.data.objects["P_leg_press_45"]
    source = {}
    for role, name in PARTS.items():
        assert bpy.data.objects[name] in machine.children_recursive
        source[role] = named_mesh(name)
    return source


if __name__ == "__main__":
    destination = Path(__file__).with_name("scene_lower_sled_source.json")
    source = extract()
    payload = json.dumps(source, separators=(",", ":")) + chr(10)
    if "--check" in sys.argv:
        assert destination.read_text() == payload
    else:
        destination.write_text(payload)
    print({key: len(part["t"]) for key, part in source.items()})
