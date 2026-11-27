"""Extract original pull-station meshes from the saved gym in background Blender."""

import json
from pathlib import Path
import sys

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene_cable_extract import casting, mesh, select, slots


def centered(v, t, m):
    return slots(v - (v.min(0) + v.max(0)) / 2, t, m)


def extract():
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    row = "P_seated_cable_row"
    v, t, m = mesh("Ddetail6_SM_SCR_AcrylicFront", row)
    front = centered(*select(v, t, m, v[:, 0] < 0))
    # The same wide-pin casting serves four guide spacings after instance scaling.
    # The oval passages reach the narrowest guides without thinning the outer wall.
    guides = ((-0.124, 0.029, 0.024), (0, 0.025, 0.025), (0.124, 0.029, 0.024))
    return {
        "stack_casting": casting(True, guides=guides, socket=(.0255, .023)),
        "shroud_side": centered(*mesh("Side shroud.036", row)),
        "shroud_cap": centered(*mesh("cover.009", row)),
        "shroud_front": front,
        "chest_pad": centered(*mesh("chest", row)),
    }


if __name__ == "__main__":
    source = extract()
    output = Path(__file__).with_name("scene_pull_source.json")
    encoded = json.dumps(source, separators=(",", ":")) + "\n"
    if "--check" in sys.argv:
        assert output.read_text() == encoded
    else:
        output.write_text(encoded)
    print({k: sum(len(p["t"]) // 3 for p in v) for k, v in source.items()})
