"""Extract the assisted knee platform and the narrow pec-deck arm bolster from the saved gym.

Blender -b --factory-startup -P this_script [-- --check]. Only append the two objects.
"""

import json
from pathlib import Path
import sys

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scene_cable_extract import slots


def ancestors(obj):
    chain = []
    while obj.parent:
        obj = obj.parent
        chain.append(obj)
    return chain


def extract():
    assert bpy.app.background
    gym = HERE.parents[1] / "promo/scenes/scene_gym.blend"
    configs = {
        "knee": ("knee_pad", "P_assisted_pullup"),
        "pad": ("forearm_pad", "P_pec_deck"),
    }
    with bpy.data.libraries.load(str(gym)) as (src, dst):
        assert configs.keys() <= set(src.objects)
        dst.objects = list(configs)
    scene = bpy.context.scene
    for obj in dst.objects:
        for parent in (*reversed(ancestors(obj)), obj):
            if parent.name not in scene.collection.objects:
                scene.collection.objects.link(parent)
    dg = bpy.context.evaluated_depsgraph_get()
    result = {}
    for obj in dst.objects:
        role, root = configs[obj.name]
        assert ancestors(obj)[-1].name == root
        assert [m.name for m in obj.data.materials] == [
            "E_pad" if role == "knee_pad" else "Ddetail6_SM_PD_Pad",
            "E_stitch",
        ]
        ev = obj.evaluated_get(dg)
        me = ev.to_mesh()
        try:
            me.calc_loop_triangles()
            v = np.array([p.co[:] for p in me.vertices]) * np.array(
                ev.matrix_world.to_scale()
            )
            v -= (v.min(0) + v.max(0)) / 2
            if role == "forearm_pad":
                # The vertical bolster rests horizontally on this tower; rotate (don't reflect)
                # the thin X axis to the new top, the long Z axis along the arm rail.
                v = v[:, [1, 2, 0]]
            t = np.array([p.vertices[:] for p in me.loop_triangles])
            m = np.array([p.material_index for p in me.loop_triangles])
            dims = np.ptp(v, axis=0)
            print(
                role,
                dims,
                "triangles",
                np.bincount(m),
                "stitch bounds",
                v[t[m == 1]].min((0, 1)),
                v[t[m == 1]].max((0, 1)),
            )
            assert dims.argmin() == 2
            result[role] = slots(v, t, m)
        finally:
            ev.to_mesh_clear()
    return result


if __name__ == "__main__":
    dest = HERE / "scene_pull_tower_pad_source.json"
    payload = json.dumps(extract(), separators=(",", ":")) + chr(10)
    if "--check" in sys.argv:
        assert dest.read_text() == payload
    else:
        dest.write_text(payload)
