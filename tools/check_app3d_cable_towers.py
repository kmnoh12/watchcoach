"""Read back this batch's packed records. Sweep actual V6 skin faces against each changed
part's conservative bounding box on the union of equipment and human key times.
These parts have identity or constant rotation and scale; only stack translation varies.
"""

import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

import check_app3d_stage1 as wire
from upgrade_app3d_cable_towers import HERE


def bounds(raw):
    return (raw.min(axis=1) + raw.max(axis=1)) / 2


def check(view):
    d = view / "data"
    hdir = view / "human_v5"
    targets = json.loads((HERE / "cable_tower_targets.json").read_text())
    manifest = json.loads((d / "wgm_manifest.json").read_text())
    base = json.loads((hdir / "base.json").read_text())
    faces = np.asarray(base["triangles"]).reshape(-1, 3)
    assert base["vertices"] == 1401 and (hdir / "watch.json").is_file()
    catalog = wire.read_parts(d / "parts.bin")
    result = []
    groups = {}
    fit = json.loads((view / "hand_fit_report.json").read_text())
    for key, slots in targets.items():
        raw = json.loads((d / f"{key}.json").read_text())
        acts, rows = wire.read_clip(d / f"{key}.wgm", catalog)
        assert (
            manifest["machineOverlays"][key]
            == dict(targets={i: n for i, (n, g) in slots.items()}, count=len(rows))
            and key in manifest["clips"]
        )
        assert np.array_equal(acts, np.asarray(raw["acts"], "<f4"))
        hfile = hdir / f"{key}.bin"
        h = wire.build.load_wgp2_human_frames(hfile)
        assert h.shape[1] == 1401
        ht = np.frombuffer(hfile.read_bytes(), "<f4", len(h), 40)
        times = np.union1d(ht, acts)
        j = np.searchsorted(ht, times, side="right").clip(1, len(ht) - 1)
        alpha = ((times - ht[j - 1]) / (ht[j] - ht[j - 1])).clip(0, 1)
        skin = h[j - 1] + alpha[:, None, None] * (h[j] - h[j - 1])
        tri = skin[:, faces]
        lo = tri.min(2)
        hi = tri.max(2)
        k = 0
        max_mm = 0.0
        old_t = new_t = 0
        static = Counter()
        moving = Counter()
        tested = set()
        for idx, (name, group) in slots.items():
            role = group.split("__")[0]
            obj = raw["objects"][int(idx)]
            assert obj["name"] == name
            nr = 3 if role in ("pulley_wheel", "selected_stack_plate", "rest_stack_plate") else 1
            got = rows[k : k + nr]
            k += nr
            pid = tuple(r["pid"] for r in got[:1])
            assert groups.setdefault(group, pid) == pid
            matrices = wire.build.strip_fake_animation(obj["m"])
            nf = len(matrices)
            original = np.asarray(matrices).reshape(-1, 4, 4)
            expected = original[:, 3, :3].copy()
            assert nf in (1, len(acts))
            if role == "pulley_fork":
                expected += [0, -0.03, 0.09]
            for layer, r in enumerate(got):
                assert (
                    r["nf"] == nf
                    and np.allclose(r["quat"], r["quat"][0])
                    and np.allclose(r["scale"], r["scale"][0])
                )
                assert np.allclose(
                    Rotation.from_quat(r["quat"]).as_matrix(),
                    original[:, :3, :3].transpose(0, 2, 1),
                    atol=0.00003,
                )
                target = expected
                if role.endswith("stack_plate") and layer:
                    depth = np.ptp(np.asarray(obj["verts"]).reshape(-1, 3)[:, 1])
                    target = expected + [0, (0.28 - depth) / 2, 0]
                mm = 1000 * np.linalg.norm(r["pos"] - target, axis=1).max()
                max_mm = max(max_mm, mm)
                assert mm < 0.1
                new_t += len(r["faces"])
                mesh = r["world"][0] - r["pos"][0]
                lower = mesh.min(0)
                upper = mesh.max(0)
                track = np.column_stack([np.interp(times, acts if nf > 1 else [0], x) for x in r["pos"].T])
                # Subtract moving origin BEFORE taking swept bounds (includes all interpolated phases).
                left = lo - track[:, None, :]
                right = hi - track[:, None, :]
                overlap = (
                    (np.minimum(left[1:], left[:-1]) <= upper) & (np.maximum(right[1:], right[:-1]) >= lower)
                ).all(2)
                assert not overlap.any(), f"{key} / {name}: skin bounds overlap; measure before accepting"
                tested.add(r["pid"])
            (moving if nf > 1 else static)[role] += 1
            old_t += len(obj["tris"]) // 3
            if role.endswith("stack_plate"):
                assert np.allclose(bounds(got[0]["world"]), expected, atol=0.0001)
                # Vertical open channels in the actual decoded casting around the two guide axes and rod.
                # Use all triangles: none may cover even part of the shaft's projected polygon.
                cast = got[0]["world"][0]
                bodies = [
                    o
                    for o in raw["objects"]
                    if o["name"].split(".")[0] in ("guide", "selector_rod", "selector_pin")
                ]
                for part in bodies:
                    pn = part["name"].split(".")[0]
                    axis = [0, 2] if pn == "selector_pin" else [0, 1]
                    pts = wire.original(part)[0][:, axis].copy()
                    if pn == "selector_pin":
                        pts[:, 1] += expected[0, 2] - part["m"][0][14]
                    footprint = pts[ConvexHull(pts).vertices]
                    proj = cast[:, axis]
                    tris = proj[got[0]["faces"]]
                    hit = ((tris.min(1) < pts.max(0)) & (tris.max(1) > pts.min(0))).all(1)
                    for t in tris[hit]:
                        edges = np.roll(t, -1, axis=0) - t
                        if abs(np.linalg.det(edges[:2])) < 1e-13:
                            continue
                        edges = np.vstack([edges, np.roll(footprint, -1, axis=0) - footprint])
                        axes = edges[:, ::-1] * [-1, 1]
                        axes = axes[np.linalg.norm(axes, axis=1) > 1e-12]
                        a = np.einsum("ij,kj->ik", t, axes)
                        b = np.einsum("ij,kj->ik", footprint, axes)
                        assert np.any(a.max(0) <= b.min(0) + 1e-13) or np.any(b.max(0) <= a.min(0) + 1e-13), (
                            f"{key}/{name}: obstructed {pn}"
                        )
        assert k == len(rows)
        old_all = sum(len(o["tris"]) // 3 for o in raw["objects"])
        pad = [x[0] for g in fit[key]["grips"].values() for x in g["pad_mm"].values()]
        result.append(
            dict(
                model=key,
                objects=len(slots),
                static=dict(static),
                moving=dict(moving),
                parts=len(tested),
                old_tri=old_t,
                new_tri=new_t,
                old_model_tri=old_all,
                new_model_tri=old_all - old_t + new_t,
                track_mm=max_mm,
                skin_overlap_mm=0,
                hand_pad_min_mm=min(pad, default=None),
                sweep_intervals=len(times) - 1,
            )
        )
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("view", type=Path)
    p.add_argument("--report", type=Path)
    a = p.parse_args()
    r = check(a.view)
    if a.report:
        a.report.write_text(json.dumps(r, indent=2) + chr(10))
    print(
        len(r),
        "clips;",
        sum(x["objects"] for x in r),
        "objects;",
        max(x["track_mm"] for x in r),
        "mm max track error; skin clear",
    )
