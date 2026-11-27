"""Extract full evaluated upholstery and underside trim in pad-local metres (never save scene).
Blender -b --factory-startup --disable-autoexec promo/scenes/scene_gym.blend
  --python-exit-code 1 -P tools/viewer3d/scene_bench_extract.py [-- --check]
"""

import json
from pathlib import Path
import sys

import bpy
import numpy as np


def extract():
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    root = bpy.data.objects["P_adjustable_bench"]
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    for role, cushion, trim in [
        ("back_pad", "back.002", "back_trim"),
        ("seat_pad", "seat.003", "seat_trim"),
    ]:
        parts = []
        for name in (cushion, trim):
            obj = bpy.data.objects[name]
            assert obj in root.children_recursive
            ev = obj.evaluated_get(dg)
            me = ev.to_mesh()
            try:
                inv = (
                    bpy.data.objects[cushion].evaluated_get(dg).matrix_world.inverted()
                )
                xf = np.asarray(inv @ ev.matrix_world)
                v = (
                    np.asarray([p.co[:] for p in me.vertices]) @ xf[:3, :3].T
                    + xf[:3, 3]
                )
                me.calc_loop_triangles()
                t = np.array([p.vertices[:] for p in me.loop_triangles])
                slots = np.array([p.material_index for p in me.loop_triangles])
                for i, slot in enumerate(obj.material_slots):
                    ids, ix = np.unique(t[slots == i], return_inverse=True)
                    parts.append(
                        dict(
                            material=slot.name,
                            v=v[ids].round(6).tolist(),
                            t=ix.flatten().tolist(),
                            rgb=list(slot.material.diffuse_color[:3]),
                        )
                    )
            finally:
                ev.to_mesh_clear()
        assert [p["material"] for p in parts] == ["E_pad", "E_stitch", "E_grip"]
        assert sum(len(p["t"]) // 3 for p in parts) == 584
        out[role] = parts
    return out


if __name__ == "__main__":
    dest = Path(__file__).with_name("scene_bench_source.json")
    s = json.dumps(extract(), separators=(",", ":"))
    if "--check" in sys.argv:
        assert dest.read_text() == s
    else:
        dest.write_text(s)
