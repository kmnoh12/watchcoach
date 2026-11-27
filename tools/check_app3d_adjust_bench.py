"""Check the installed bench overlay against its preceding viewer bundle, without refitting.
Usage: python3 tools/check_app3d_adjust_bench.py <viewer3d> <pre-bench viewer3d> [--report path]
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import struct

import numpy as np
from scipy.spatial.transform import Rotation

import check_app3d_stage1 as wire
from bench_fit import swept_clear, top_gap
from body_fit import SkinSweep, contact_region
from upgrade_app3d_adjust_bench import HERE, ends, object_pose


def load(path):
    return json.loads(path.read_text())


def files(root):
    return {
        p.relative_to(root): p.stat().st_size for p in root.rglob("*") if p.is_file()
    }


def closed_solid(v, t):
    edges = Counter(
        zip(t.flatten().tolist(), np.roll(t, -1, axis=1).flatten().tolist())
    )
    assert all(n == 1 and edges[b, a] == 1 for (a, b), n in edges.items())
    a, b, c = v[t].transpose(1, 0, 2)
    assert np.einsum("ij,ij->", a, np.cross(b, c)) > 0


def check(view, baseline):
    d, old, human = view / "data", baseline / "data", view / "human_v5"
    base = load(human / "base.json")
    assert base["vertices"] == 1401 and (human / "watch.json").is_file()
    skin_faces = np.asarray(base["triangles"]).reshape(-1, 3)
    hand = load(view / "hand_fit_report.json")
    mf, before = [load(path / "wgm_manifest.json") for path in (d, old)]
    parts = wire.read_parts(d / "parts.bin")
    prev_parts = (old / "parts.bin").read_bytes()
    old_count = struct.unpack_from("<I", prev_parts, 4)[0]
    assert (d / "parts.bin").read_bytes()[8 : len(prev_parts)] == prev_parts[8:]
    targets = load(HERE / "adjust_bench_targets.json")
    fit = load(d / "adjust_bench_fit.json")
    source = load(HERE / "scene_bench_source.json")
    assert set(fit) == set(targets)
    fitted = {k for k, result in fit.items() if "pads" in result}
    assert set(mf["clips"]) == set(before["clips"]) | fitted
    assert {k: v for k, v in mf.items() if k not in ("clips", "machineOverlays")} == {
        k: v for k, v in before.items() if k not in ("clips", "machineOverlays")
    }
    assert {k: v for k, v in mf["machineOverlays"].items() if k not in fitted} == {
        k: v for k, v in before.get("machineOverlays", {}).items() if k not in fitted
    }
    f0, f1 = files(baseline), files(view)
    assert not (f0.keys() - f1.keys())
    changed = {
        str(f)
        for f in f1
        if f not in f0 or (baseline / f).read_bytes() != (view / f).read_bytes()
    }
    required = {"data/" + s + ".wgm" for s in fitted} | {
        "data/parts.bin",
        "data/wgm_manifest.json",
        "data/adjust_bench_fit.json",
    }
    assert changed - {"v5_bundle_report.json"} == required, changed ^ required
    old_report, new_report = [
        load(v / "v5_bundle_report.json") for v in (baseline, view)
    ]
    for rep in [old_report, new_report]:
        rep.pop("bytes", None)
    assert old_report == new_report
    report = dict(
        bytes_before=sum(f0.values()),
        bytes_after=sum(f1.values()),
        byte_delta_by_file={
            s: f1[Path(s)] - f0.get(Path(s), 0) for s in sorted(changed)
        },
        unchanged_files=len(f1) - len(changed),
        catalog_before=old_count,
        catalog_after=len(parts),
        clips={},
    )
    common = {}
    mechanisms = set()

    def share(key, rows):
        ids = tuple(x["pid"] for x in rows)
        assert common.setdefault(key, ids) == ids, key

    for key, mapping in targets.items():
        raw = load(d / (key + ".json"))
        objects = raw["objects"]
        assert all(objects[i]["name"] == name for name, (i, _) in mapping.items())
        grips = hand[key]["grips"]
        gaps = [n[0] for g in grips.values() for n in g["pad_mm"].values()]
        out = report["clips"][key] = dict(
            min_existing_finger_mm=min(gaps, default=None)
        )
        if key not in fitted:
            assert fit[key]["unchanged"]
            out["unchanged"] = fit[key]["unchanged"]
            continue
        assert not set(mapping) & {g["part"] for g in grips.values()}
        oldtargets = (
            before.get("machineOverlays", {})
            .get(key, {})
            .get("targets", before["plateOverlays"].get(key, {}))
        )
        info = fit[key]
        acts, rows = wire.read_clip(d / (key + ".wgm"), parts)
        cursor = info["preceding"]
        expected_targets = {
            **oldtargets,
            **{str(idx): n for n, (idx, _) in mapping.items()},
        }
        assert mf["machineOverlays"][key] == {
            "count": len(rows),
            "targets": expected_targets,
        }
        if key in before["clips"]:
            a = (old / (key + ".wgm")).read_bytes()
            b = (d / (key + ".wgm")).read_bytes()
            assert (
                a[:6] == b[:6]
                and a[8:] == b[8 : len(a)]
                and struct.unpack_from("<H", a, 6)[0] == cursor
            )
            if key == "seated_barbell_overhead_press":
                assert (
                    list(oldtargets.values()) == ["plate", "plate.001"] and cursor == 4
                )
        else:
            assert not oldtargets and cursor == 0
        assert len(rows) == cursor + info["records"] and np.array_equal(
            acts, np.array(raw["acts"], "<f4")
        )
        hp = human / (key + ".bin")
        frames = wire.build.load_wgp2_human_frames(hp)
        ht = np.frombuffer(hp.read_bytes(), "<f4", len(frames), 40)
        assert frames.shape[1:] == (1401, 3) and np.all(np.diff(ht) > 0)
        sweep = SkinSweep(frames, skin_faces)
        for r in rows[cursor:]:
            assert r["nf"] == 1 and swept_clear(sweep, r["world"][0]), (key, r["pid"])
        old_tris = sum(
            len(o["tris"]) // 3
            for i, o in enumerate(objects)
            if str(i) not in oldtargets
        ) + sum(len(r["faces"]) for r in rows[:cursor])
        replaced = sum(len(objects[i]["tris"]) // 3 for i, _ in mapping.values())
        out.update(
            poses=len(frames),
            intervals=len(sweep.lo),
            records=info["records"],
            prefix=cursor,
            tris_before=old_tris,
            tris_after=old_tris
            - replaced
            + sum(len(r["faces"]) for r in rows[cursor:]),
            pads={},
        )
        for name in ("back", "incline_pad", "seat"):
            if name not in mapping:
                continue
            index, group = mapping[name]
            role = group.split("__")[0]
            meta = info["pads"][name]
            g = rows[cursor : cursor + 3]
            cursor += 3
            share(group, g)
            for row, slot in zip(g, source[role]):
                assert np.array_equal(row["faces"].ravel(), slot["t"]) and all(
                    np.array_equal(row[j], g[0][j]) for j in ("pos", "quat", "scale")
                )
            p, rot = g[0]["pos"][0], Rotation.from_quat(g[0]["quat"][0])
            op, org, _ = object_pose(objects[index])
            delta = rot * org.inv()
            if name == "seat":
                assert meta["pivot"] is None and np.array_equal(meta["axis"], [0, 0, 1])
                assert delta.magnitude() < 1e-6 and np.linalg.norm((p - op)[:2]) < 1e-6
            else:
                pivot = np.array(meta["pivot"])
                axis = org.apply([1, 0, 0])
                assert np.allclose(axis, meta["axis"], atol=1e-6)
                assert (
                    np.linalg.norm(delta.apply(axis) - axis) < 1e-6
                    and np.linalg.norm(pivot + delta.apply(op - pivot) - p) < 1e-6
                )
            local = np.einsum("fvi,ij->fvj", frames - p, rot.as_matrix())
            faces = contact_region(base, meta["skin"])[0]
            v0, t0 = parts[g[0]["pid"]]
            v1, t1 = parts[g[1]["pid"]]
            gap = 1000 * top_gap(
                local[:, faces].reshape(-1, 3, 3),
                np.vstack([v0, v1]),
                np.vstack([t0, t1 + len(v0)]),
            )
            assert 2 <= gap <= 5 and abs(gap - meta["gap_mm"]) < 0.02, (key, name, gap)
            out["pads"][name] = round(gap, 4)
            names = (
                ("seat_mount", "seat_rail")
                if name == "seat"
                else ("back_mount", "back_rail", "hinge_link", "spine")
            )
            for n, (idx, subgroup) in mapping.items():
                if n.split(".")[0] not in names:
                    continue
                row = rows[cursor]
                cursor += 1
                share(subgroup, [row])
                ref = p + delta.apply(wire.original(objects[idx])[0] - op)
                assert np.max(abs(ref - row["world"][0])) < 0.00002, (key, n)
            brace = (
                "seat_post"
                if name == "seat"
                else next(
                    n
                    for n in ("telescopic_brace", "back_brace", "rear_post")
                    if n in mapping
                )
            )
            low, high = ends(objects[mapping[brace][0]])
            kit = rows[cursor : cursor + 5]
            cursor += 5
            share("adjuster", kit)
            sleeve, collar, insert, pin, head = kit
            top = p + delta.apply(high - op)
            col = collar["pos"][0]
            r = Rotation.from_quat(collar["quat"][0])
            x, z = r.apply([[1, 0, 0], [0, 0, 1]])
            assert (
                np.linalg.norm(sleeve["pos"][0] - low) < 2e-6
                and np.linalg.norm(insert["pos"][0] - top) < 2e-6
            )
            assert np.linalg.norm(col - low - z * (0.01 + sleeve["scale"][0, 2])) < 2e-6
            assert (
                np.linalg.norm(col - top + z * 0.09 * insert["scale"][0, 2]) < 2e-6
                and np.linalg.norm(pin["pos"][0] - col) < 2e-6
            )
            assert np.linalg.norm(head["pos"][0] - col - 0.026 * x) < 2e-6
            for r in kit[:3]:
                if r["pid"] not in mechanisms:
                    closed_solid(*parts[r["pid"]])
                    mechanisms.add(r["pid"])
        assert cursor == len(rows)
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("view", type=Path)
    p.add_argument("baseline", type=Path)
    p.add_argument("--report", type=Path)
    a = p.parse_args()
    s = json.dumps(check(a.view, a.baseline), indent=2)
    print(s)
    if a.report:
        a.report.write_text(s + chr(10))
