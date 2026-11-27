"""Read the lat station cable's evaluated bevel from the saved gym scene."""

import json
from pathlib import Path
import sys

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scene_rest_cable_extract import straight_profile


if __name__ == "__main__":
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    cable = bpy.data.objects["Lat bar cable"]
    assert cable in bpy.data.objects["P_lat_pulldown"].children_recursive
    source = {"cable_segment": straight_profile(cable.name, clear_animation=True)}
    path = HERE / "scene_lat_exterior_source.json"
    encoded = json.dumps(source, separators=(",", ":")) + "\n"
    if "--check" in sys.argv:
        assert path.read_text() == encoded
    else:
        path.write_text(encoded)
    print({name: (len(part["ring"]), part["material"]) for name, part in source.items()})
