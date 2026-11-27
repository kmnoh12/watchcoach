"""Read evaluated cable station exteriors from the saved gym without saving the scene."""

import json
from pathlib import Path
import sys

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene_cable_extract import CC, LP, mesh, select


FRAME_OBJECT = "Ddetail6_SM_CC_Frame"
FRAME_PARTS = {
    "frame_foot": ((-1.05, 0.058, 0.054), (0.104, 0.724, 0.080), 1, (2, -1, 3), 108),
    "frame_post": ((-1.24, 0.456, 1.194), (0.044, 0.092, 2.164), 0, (3, 2, -1), 108),
    "frame_brace": ((-1.104, 0.220, 1.794), (0.036, 0.360, 0.056), 0, (2, -1, 3), 44),
    "frame_link": ((-1.104, 0.240, 2.258), (0.034, 0.480, 0.046), 0, (2, -1, 3), 44),
    "rubber_foot": ((-1.05, -0.230, 0.009), (0.096, 0.120, 0.018), 3, (1, 2, 3), 44),
}


def encode(v, t, material, smooth):
    return dict(v=v.round(7).tolist(), t=t.tolist(), material=material.name,
                rgb=[round(c, 6) for c in material.diffuse_color[:3]], smooth=smooth)


def orient(v, axes):
    return v[:, np.abs(axes) - 1] * np.sign(axes)


def island(tris, seed, vertex_count):
    mask = np.arange(vertex_count) == seed
    while np.any(mask[tris].any(1) != mask[tris].all(1)):
        mask[tris[mask[tris].any(1)]] = True
    return mask


def named_mesh(name, *, axes=(1, 2, 3)):
    obj = bpy.data.objects[name]
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    try:
        me.calc_loop_triangles()
        assert len(me.materials) == 1
        v = orient(np.array([p.co[:] for p in me.vertices]), axes)
        v -= (v.min(0) + v.max(0)) / 2
        return encode(v, np.array([f.vertices[:] for f in me.loop_triangles]), me.materials[0],
                      [bool(me.polygons[f.polygon_index].use_smooth) for f in me.loop_triangles])
    finally:
        ev.to_mesh_clear()


def straight_profile(name, *, along_y=False):
    """Evaluate the source curve's bevel on a straight run with the app's axial track."""
    obj = bpy.data.objects[name]
    curve = obj.data.copy()
    curve.splines.clear()
    curve.use_fill_caps = False
    spline = curve.splines.new("POLY")
    spline.points.add(1)
    for point, z in zip(spline.points, (0, 1)):
        point.co = (0, 0, z, 1)
    probe = bpy.data.objects.new("cable profile", curve)
    bpy.context.collection.objects.link(probe)
    try:
        data = named_mesh(probe.name)
    finally:
        bpy.data.objects.remove(probe, do_unlink=True)
        bpy.data.curves.remove(curve)
    v = np.asarray(data["v"])
    ring = v[np.isclose(v[:, 2], v[:, 2].max()), :2]
    assert len(ring) >= 4 and len(v) == 2 * len(ring)
    if along_y:
        # Convert the straight ±X/±Y ring to the axis convention of the old cable.
        ring[:, 1] *= -1
    data["ring"] = ring.tolist()
    return data


def extract():
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    out = {}
    v, t, m = mesh(FRAME_OBJECT, CC)
    frame = bpy.data.objects[FRAME_OBJECT]
    for role, (center, size, slot, axes, count) in FRAME_PARTS.items():
        corner = np.asarray(center) + np.asarray(size) / 2
        ids = np.unique(t[m == slot])
        seed = ids[np.linalg.norm(v[ids] - corner, axis=1).argmin()]
        p, faces, mat = select(v, t, m, island(t, seed, len(v)))
        assert len(faces) == count and set(mat) == {slot}, role
        assert np.allclose(np.ptp(p, axis=0), size, atol=1e-5), role
        out[role] = encode(orient(p - center, axes), faces, frame.material_slots[slot].material, False)

    out["hand_grip"] = named_mesh("stirrup_grip")
    out["handle_support"] = named_mesh("stirrup")
    out["lat_bar"] = named_mesh("bar.002")
    # Both app rope branches are straight segments. Retain the scene rope's bevel
    # and finish while leaving the existing moving endpoints and hand contact planes.
    out["rope_cord"] = straight_profile("Tricep rope leg")
    out["rope_stop"] = named_mesh("Rope bell stop", axes=(1, -2, -3))
    out["rope_connector"] = named_mesh("Rope swivel collar")
    out["cable_segment"] = straight_profile("Coated load cable.002", along_y=True)

    name = "Ddetail6_LP_BarHardware"
    v, t, m = mesh(name, LP)
    center = np.array((0, -0.450, 1.922))
    local = v - center
    # Isolate the two complete authored islands. The adjoining clevis and ferrule
    # belong to the lat machine and are not part of this moving cable attachment.
    for target, count, y, z in (("ring", 480, 0.01851, 0.0316), ("gate", 92, 0.0209, 0.0111)):
        seed = np.argmin(np.linalg.norm(local - ([0.0045, 0.014, 0] if target == "ring"
                                                  else [0.0068, -0.014, 0.011]), axis=1))
        p, faces, slots = select(local, t, m, island(t, seed, len(v)))
        assert len(faces) == count and set(slots) == {0}, target
        assert (abs(p) <= [0.007, y, z]).all(), target
        out[f"carabiner_link_{target}"] = encode(p, faces, bpy.data.objects[name].material_slots[0].material, True)
    return out


if __name__ == "__main__":
    path = Path(__file__).with_name("scene_rest_cable_source.json")
    source = extract()
    encoded = json.dumps(source, separators=(",", ":")) + chr(10)
    if "--check" in sys.argv:
        assert path.read_text() == encoded
    else:
        path.write_text(encoded)
    print({role: len(part["t"]) for role, part in source.items()})
