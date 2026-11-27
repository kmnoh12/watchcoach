"""Read the saved gym, without saving the scene. Blender -b scene_gym.blend -P this.py [-- --check].
Triangulate evaluated source parts, not an approximation of the wheel groove or the hardware.
Keep whole connected pieces from symmetric twin stations. Output is in local metres.
"""

import json
from pathlib import Path
import sys

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
CC, LP = "P_cable_crossover", "P_lat_pulldown"


def mesh(name, root):
    dg = bpy.context.evaluated_depsgraph_get()
    root = bpy.data.objects[root]
    obj = bpy.data.objects[name]
    assert obj in root.children_recursive
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        xf = np.asarray(root.evaluated_get(dg).matrix_world.inverted() @ ev.matrix_world)
        v = np.asarray([p.co[:] for p in me.vertices]) @ xf[:3, :3].T + xf[:3, 3]
        me.calc_loop_triangles()
        t = np.asarray([p.vertices[:] for p in me.loop_triangles])
        m = np.asarray([p.material_index for p in me.loop_triangles])
        return v, t, m
    finally:
        ev.to_mesh_clear()


def select(v, t, m, mask):
    assert not np.any(mask[t].any(1) != mask[t].all(1)), "Crop split a source island"
    sel = mask[t].all(1)
    assert np.any(sel)
    keep, ix = np.unique(t[sel], return_inverse=True)
    return v[keep], ix.reshape(-1, 3), m[sel]


def slots(v, t, m):
    result = []
    for slot in sorted(set(m)):
        keep, ix = np.unique(t[m == slot], return_inverse=True)
        result.append(dict(slot=int(slot), v=v[keep].round(6).tolist(), t=ix.flatten().tolist()))
    return result


def casting(wide):
    # Start with the scene's through-bored casting, KEEP both mouth bevels. The
    # scene only models the front/back socket: drill three vertical passages for
    # the phone's fixed twin guides and central lift rod. No decimation.
    s = json.loads((HERE / "scene_lat_source.json").read_text())["plate"]
    v = np.asarray(s["verts"], float) / s["size"] * [0.34, 0.28, 0.075]
    t = np.asarray(s["tri"])
    old = np.asarray(s["verts"], float)
    for i in range(16, 80):
        direction = old[i, [0, 2]]
        direction /= np.linalg.norm(direction)
        lip = 1.15 if i < 32 or i >= 64 else 1.0
        v[i, [0, 2]] = (
            direction / abs(direction).max() * [0.023, 0.022] if wide else direction * 0.0102
        ) * lip
    me = bpy.data.meshes.new("cable fit")
    me.from_pydata(v.tolist(), [], t.tolist())
    me.update()
    obj = bpy.data.objects.new("cable fit", me)
    bpy.context.collection.objects.link(obj)
    for x in [-0.130, 0, 0.130]:
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.022, depth=0.12, location=(x, 0, 0))
        drill = bpy.context.object
        mod = obj.modifiers.new("App guide bore", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = "EXACT"
        mod.object = drill
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        me.calc_loop_triangles()
        vv = np.array([p.co[:] for p in me.vertices])
        tt = np.array([p.vertices[:] for p in me.loop_triangles])
        assert len(tt) > len(t)
        return slots(vv, tt, np.zeros(len(tt), int))
    finally:
        ev.to_mesh_clear()


def extract():
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    v, t, m = mesh("Ddetail6_LP_FrontPulleyWheel", LP)
    v -= (v.max(0) + v.min(0)) / 2
    assert np.allclose(np.ptp(v, axis=0), [0.027, 0.148, 0.148], atol=0.00001)
    # Proper rotation: source X axle -> target local Z; retain all three material regions.
    out = {"pulley_wheel": slots(v[:, [2, 1, 0]] * [-1, 1, 1], t, m)}
    assert len(out["pulley_wheel"]) == 3
    v, t, m = mesh("Ddetail6_SM_CC_Frame", CC)
    v -= np.array([-1.05, -0.134, 2.18])
    mask = (abs(v) < [0.05, 0.05, 0.05]).all(1)
    v, t, m = select(v, t, m, mask)
    assert set(m) == {0, 2}
    out["pulley_fork"] = slots(v, t[m == 0], m[m == 0])
    assert np.allclose(np.ptp(v[t[m == 0]], axis=(0, 1)), [0.042, 0.078, 0.088], atol=1e-5)
    # Bolt heads and washers from the cheek assembly, central axle from lat guard.
    a, b, c = mesh("Ddetail6_LP_FrontPulleyGuard", LP)
    from mathutils import Vector

    root = bpy.data.objects[LP]
    spindle = bpy.data.objects["Ddetail6_LP_FrontPulleySpindle"]
    center = np.array(root.matrix_world.inverted() @ spindle.matrix_world @ Vector((0, 0, 0)))
    a -= center
    a, b, c = select(a, b, c, (np.abs(a[:, 0]) <= 0.02201) & (np.hypot(a[:, 1], a[:, 2]) <= 0.01101))
    vv = np.vstack([v, a])
    tt = np.vstack([t[m == 2], b + len(v)])
    out["pulley_hub"] = slots(vv[:, [2, 1, 0]] * [-1, 1, 1], tt, np.full(len(tt), 2))
    v, t, m = mesh("Ddetail6_SM_CC_AcrylicRearUpper", CC)
    v, t, m = select(v, t, m, v[:, 0] < 0)
    v -= (v.min(0) + v.max(0)) / 2
    assert np.allclose(np.ptp(v, axis=0), [0.330, 0.004, 0.568], atol=0.00001)
    out["shroud_panel"] = slots(v, t, m)
    out["stack_round_socket"] = casting(False)
    out["stack_wide_socket"] = casting(True)
    return out


if __name__ == "__main__":
    data = extract()
    output = HERE / "scene_cable_source.json"
    encoded = json.dumps(data, separators=(",", ":")) + chr(10)
    if "--check" in sys.argv:
        assert output.read_text() == encoded
    else:
        output.write_text(encoded)
    print({k: sum(len(s["t"]) // 3 for s in v) for k, v in data.items()})
