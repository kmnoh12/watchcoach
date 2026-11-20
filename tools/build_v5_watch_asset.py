"""Export the left-wrist watch of promo/models/v6.blend for the phone viewer.

  python3 tools/build_v5_watch_asset.py [--blender PATH]

Writes tools/viewer3d/watch_v5.json: the watch parts in the V5 rest pose (same frame as the
new-hand human_v5/base.json), one colour per material, and three forearm anchor vertices.
The viewer moves the watch rigidly with those anchors (lowerarm_l weight 1), so clips need no
extra data. tools/refresh_app3d_newhand.py copies the file into the bundle as human_v5/watch.json.
"""
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
BLEND = REPO / "promo/models/v6.blend"
OUT = REPO / "tools/viewer3d/watch_v5.json"
PARTS = ("Watch_Case", "Watch_Strap", "Watch_Buckle", "Watch_Display", "Watch_ButtonA", "Watch_ButtonB")
BLENDER = {
    "Darwin": "/Applications/Blender.app/Contents/MacOS/Blender",
    "Windows": r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
}.get(platform.system(), "blender")


def dump(path):
    import bpy
    from mathutils import Matrix

    rig = bpy.data.objects["V5_CommonRig"]
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    body = bpy.data.objects["V5_Body"]
    lower = body.vertex_groups["lowerarm_l"].index
    data = dict(
        body_rest=[v.co[:] for v in body.data.vertices],
        lowerarm_l=[next((g.weight for g in v.groups if g.group == lower), 0.0) for v in body.data.vertices],
        wrist=rig.data.bones["hand_l"].head_local[:],
        parts=[],
    )
    for name in PARTS:
        ob = bpy.data.objects[name]
        mesh = ob.data
        mesh.calc_loop_triangles()
        mw = ob.matrix_world
        colors = []
        for slot in ob.material_slots:
            mat = slot.material
            node = mat.node_tree.nodes.get("Principled BSDF") if mat and mat.node_tree else None
            rgba = node.inputs["Base Color"].default_value[:] if node else mat.diffuse_color[:]
            colors.append([round(c, 4) for c in rgba[:3]])
        data["parts"].append(dict(
            name=name,
            verts=[(mw @ v.co)[:] for v in mesh.vertices],
            tris=[(t.material_index, t.vertices[:]) for t in mesh.loop_triangles],
            colors=colors,
        ))
    Path(path).write_text(json.dumps(data))


def main():
    import numpy as np

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", default=BLENDER)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temp:
        raw = Path(temp) / "watch.json"
        subprocess.run([args.blender, "-b", str(BLEND), "--python-exit-code", "1", "-P", __file__, "--", "dump", str(raw)],
                       check=True, stdout=subprocess.DEVNULL)
        data = json.loads(raw.read_text())
    rest = np.asarray(data["body_rest"])
    # The bundle's human_v5/base.json takes its rest pose from promo/cast/src_v5_rig.blend; this blend must match it.
    ref = REPO / "phone/src/main/assets/viewer3d/human_v5/base.json"
    if ref.exists():
        base = json.loads(ref.read_text())
        if base["vertices"] == len(rest):
            assert np.abs(np.asarray(base["rest"]).reshape(-1, 3) - rest).max() < 1e-5, "watch blend and bundle body differ"
    parts = []
    for part in data["parts"]:
        verts = np.asarray(part["verts"])
        for k, color in enumerate(part["colors"]):
            tris = [t for m, t in part["tris"] if m == k]
            used = sorted({i for t in tris for i in t})
            index = {v: i for i, v in enumerate(used)}
            parts.append(dict(
                name=part["name"] + ("" if len(part["colors"]) == 1 else f".{k}"),
                color=color,
                verts=np.round(verts[used], 6).ravel().tolist(),
                tris=[index[i] for t in tris for i in t],
            ))
    every = np.concatenate([np.asarray(p["verts"]).reshape(-1, 3) for p in parts])
    center = every.mean(0)
    weight = np.asarray(data["lowerarm_l"])
    # Use the rigid new-hand forearm ring right under the watch (0.95..0.995, within 4.5 cm);
    # vertices with lowerarm_l == 1.0 lie on the arm-cut seam / old mesh and deform across clips.
    near = np.flatnonzero((weight >= 0.95) & (weight < 0.995) & (np.linalg.norm(rest - center, axis=1) < 0.045))
    assert len(near) >= 3, "too few rigid forearm vertices near the watch"
    # Three well-spread anchors: farthest pair, then the vertex farthest from their line.
    pts = rest[near]
    d = np.linalg.norm(pts[:, None] - pts[None], axis=2)
    a, b = np.unravel_index(np.argmax(d), d.shape)
    line = pts[b] - pts[a]
    off = np.linalg.norm(np.cross(pts - pts[a], line), axis=1) / np.linalg.norm(line)
    c = int(np.argmax(off))
    anchors = [int(near[a]), int(near[b]), int(near[c])]
    out = dict(
        source="promo/models/v6.blend",
        bone="lowerarm_l",
        anchors=anchors,
        anchor_rest=np.round(rest[anchors], 6).ravel().tolist(),
        parts=parts,
    )
    OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    print(f"{OUT.relative_to(REPO)}: {len(parts)} parts, {len(every)} vertices, anchors {anchors} "
          f"(spread {d[a, b] * 1000:.0f} x {off[c] * 1000:.0f} mm)")


if __name__ == "__main__":
    if "--" in sys.argv and sys.argv[sys.argv.index("--") + 1] == "dump":
        dump(sys.argv[-1])
    else:
        main()
