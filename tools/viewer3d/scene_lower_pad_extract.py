"""Extract evaluated hip-machine upholstery in object axes, including every stitch face."""

import json
from pathlib import Path
import sys

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene_cable_extract import slots


def extract():
    assert bpy.app.background
    dg = bpy.context.evaluated_depsgraph_get()
    result = {}
    for role, name, parent in [
        ("back_pad", "back.010", "P_hip_abductor"),
        ("seat_pad", "seat.014", "P_hip_abductor"),
        ("thigh_pad", "thigh", "P_seated_leg_curl"),
    ]:
        o = bpy.data.objects[name]
        assert o.parent.name == parent and [m.name for m in o.data.materials] == [
            "E_pad",
            "E_stitch",
        ]
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        try:
            me.calc_loop_triangles()
            v = np.array([p.co[:] for p in me.vertices]) * np.array(
                ev.matrix_world.to_scale()
            )
            v -= (v.min(0) + v.max(0)) / 2
            t = np.array([f.vertices[:] for f in me.loop_triangles])
            m = np.array([f.material_index for f in me.loop_triangles])
            result[role] = slots(v, t, m)
            print(role, len(t), np.ptp(v, axis=0))
        finally:
            ev.to_mesh_clear()
    return result


if __name__ == "__main__":
    dest = Path(__file__).with_name("scene_lower_pad_source.json")
    payload = json.dumps(extract(), separators=(",", ":")) + chr(10)
    if "--check" in sys.argv:
        assert dest.read_text() == payload
    else:
        dest.write_text(payload)
