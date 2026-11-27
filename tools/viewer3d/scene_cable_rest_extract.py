"""Extract the cable-station exteriors from the saved gym without editing it."""

import json
from pathlib import Path
import sys

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene_cable_extract import CC, mesh, select

# The remaining structural prototypes use the app part's local axes.
FRAMES = {
    "adjustment_rail__002": ("guide", "xyz"),
    "base_crossfoot__002": ("top", "xyz"),
    "carriage__001": ("slider", "xyz"),
    "frame_brace__002": ("Ddetail6_SM_CC_Frame", "y-xz", (-1.104, .22, 1.794)),
    "frame_crossbeam__004": ("top", "xyz"),
    "frame_foot__002": ("Ddetail6_SM_CC_Frame", "y-xz", (-1.05, .058, .054)),
    "frame_post__003": ("Ddetail6_SM_CC_Frame", "zy-x", (-1.24, .456, 1.194)),
    "rubber_foot__001": ("tower_foot.008", "xyz"),
}


def orient(vertices, axes):
    indices = ["xyz".index(a) for a in axes if a != "-"]
    signs = [-1 if i and axes[i-1] == "-" else 1 for i, a in enumerate(axes) if a != "-"]
    assert np.linalg.det(np.eye(3)[:, indices] * signs) > 0
    return vertices[:, indices] * signs


def frame(name, axes, island=None):
    v, t, m = mesh(name, CC)
    if island:
        # Compare centres of complete connected solids, not individual vertices.
        available = set(np.unique(t))
        best = (float("inf"), None)
        while available:
            keep = np.zeros(len(v), bool)
            keep[min(available)] = True
            while True:
                used = np.unique(t[keep[t].any(axis=1)])
                if len(used) == keep.sum():
                    break
                keep[used] = True
            available.difference_update(used)
            subset = v[keep]
            distance = np.linalg.norm((subset.min(0) + subset.max(0)) / 2 - island)
            if distance < best[0]:
                best = (distance, keep)
        assert best[0] < .002, (name, island, best[0])
        v, t, m = select(v, t, m, best[1])
    v = orient(v, axes)
    v -= (v.max(0) + v.min(0)) / 2
    return dict(object=name, v=v.round(7).tolist(), t=t.tolist(), material=m.tolist(),
                rgb=[list(s.material.diffuse_color[:3]) for s in bpy.data.objects[name].material_slots],
                materials=[s.material.name for s in bpy.data.objects[name].material_slots])


def local(name):
    obj = bpy.data.objects[name]
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = evaluated.to_mesh()
    try:
        return np.array([p.co[:] for p in me.vertices]), list(me.materials[0].diffuse_color[:3])
    finally:
        evaluated.to_mesh_clear()


def extract():
    assert bpy.app.background and bpy.context.scene.unit_settings.scale_length == 1
    out = {group: frame(*args) for group, args in FRAMES.items()}
    for key, name in {"hand_grip": "stirrup_grip", "d_handle_side": "stirrup",
                      "carabiner_link": "Cable terminal.002", "rope_stop": "Rope bell stop",
                      "rope_connector": "Rope swivel collar", "rope_cord": "Tricep rope leg",
                      "cable_segment": "Coated load cable.002"}.items():
        v, rgb = local(name)
        if key == "cable_segment":
            # The first ring is perpendicular to the initial straight span.
            points = v[np.isclose(v[:, 1], v[0, 1], atol=1e-6)][:4]
            ring = points[:, [0, 2]]
            assert len(ring) == 4
        elif key == "rope_cord":
            # The scene has a curved rope. Its first bevel ring supplies the
            # profile while the exercise keeps each original straight segment.
            ring3 = v[:8] - v[:8].mean(0)
            _, _, basis = np.linalg.svd(ring3)
            ring = ring3 @ basis[:2].T
            assert np.max(np.abs(ring3 @ basis[2])) < 1e-6
        else:
            ring = v[np.isclose(v[:, 2], v[:, 2].min()), :2]
        ring -= ring.mean(0)
        assert np.ptp(np.linalg.norm(ring, axis=1)) < 1e-6
        out[key] = dict(object=name, rgb=rgb, ring=ring.round(7).tolist(),
                        v=v.round(7).tolist())
    return out


if __name__ == "__main__":
    path = Path(__file__).with_name("scene_cable_rest_source.json")
    source = extract()
    data = json.dumps(source, separators=(",", ":")) + "\n"
    if "--check" in sys.argv:
        assert path.read_text() == data
    else:
        path.write_text(data)
    print({key: len(piece.get("t", piece.get("ring", []))) for key, piece in source.items()})
