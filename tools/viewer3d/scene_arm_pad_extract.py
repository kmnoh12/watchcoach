"""Extract only the preacher pad object, without loading or saving the gym scene.
Blender -b --factory-startup -P this_script [-- --check].
"""

import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scene_cable_extract import slots


def extract():
    assert bpy.app.background
    gym = HERE.parents[1] / "promo/scenes/scene_gym.blend"
    with bpy.data.libraries.load(str(gym), link=False) as (src, dst):
        assert "arm_pad" in src.objects
        dst.objects = ["arm_pad"]
    obj = dst.objects[0]
    assert obj.parent.name == "P_preacher_machine"
    assert [m.name for m in obj.data.materials] == ["E_pad", "E_stitch"]
    for o in (obj.parent, obj):
        bpy.context.scene.collection.objects.link(o)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        # Undo the scene's baked 40 degree uphill slope; the app owns the angle.
        xf = np.array(
            Matrix.Rotation(np.radians(-40), 4, "X")
            @ obj.parent.evaluated_get(dg).matrix_world.inverted()
            @ ev.matrix_world
        )
        v = np.array([p.co[:] for p in me.vertices]) @ xf[:3, :3].T
        v -= (v.min(0) + v.max(0)) / 2
        me.calc_loop_triangles()
        t = np.array([f.vertices[:] for f in me.loop_triangles])
        m = np.array([f.material_index for f in me.loop_triangles])
        print("source dimensions and triangles", np.ptp(v, axis=0), len(t))
        assert np.allclose(np.ptp(v, axis=0), [0.42, 0.40, 0.085], atol=0.001)
        return {"arm_pad": slots(v, t, m)}
    finally:
        ev.to_mesh_clear()


if __name__ == "__main__":
    dest = HERE / "scene_arm_pad_source.json"
    result = json.dumps(extract(), separators=(",", ":")) + chr(10)
    if "--check" in sys.argv:
        assert dest.read_text() == result
    else:
        dest.write_text(result)
