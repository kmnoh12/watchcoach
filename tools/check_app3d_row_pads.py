"""Decode the lever-row batch against the immediately preceding tower + plate bundle."""

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

import check_app3d_stage1 as wire
from check_app3d_adjust_bench import files
from upgrade_app3d_adjust_bench import HERE, load, object_pose
from upgrade_app3d_machines import decompose_frames, strip_fake_animation
from upgrade_app3d_pull_stations import (
    assemble,
    avatar_at_key_times,
    load_source,
    vertices,
)
from upgrade_app3d_row_pads import REPORT, TARGETS
from bench_fit import swept_clear
from body_fit import SkinSweep
from fixed_pad_contact import penetration
from pull_pad_fit import axial_gap

ROWS = {"seated_row_machine", "seated_row_machine~m=single"}


def triangles(objects, targets, decoded):
    return sum(
        len(o["tris"]) // 3 for i, o in enumerate(objects) if str(i) not in targets
    ) + sum(len(r["faces"]) for r in decoded)


def ids(group, layers, shared):
    pids = tuple(r["pid"] for r in layers)
    assert shared.setdefault(group, pids) == pids, (group, shared[group], pids)


def cloud(layers):
    return [(r["world"][0], r["faces"]) for r in layers]


def check_tower(k, raw, base, skin, sweep, oldrows, newrows, towerfit, report, shared):
    mapping = load(HERE / "pull_station_targets.json")[k]
    plan, fit = assemble(k, raw, mapping, load_source(), skin, base)
    assert fit == towerfit["fits"] and len(plan) == len(oldrows) == towerfit["records"]
    for entry, prev, row in zip(plan, oldrows, newrows):
        if not entry["contact"]:
            assert all(
                prev[f] == row[f] for f in ("pid", "rgb", "mat", "nf")
            ) and np.array_equal(prev["world"], row["world"])
        else:
            assert row["nf"] == 1 and swept_clear(sweep, row["world"][0])
            assert np.allclose(row["pos"], entry["pos"], atol=1e-6)
    for name, pad in fit.items():
        idx = [i for i, e in enumerate(plan) if e["name"] == name and e["smooth"]]
        assert len(idx) == 2
        group = mapping[name][1]
        ids(group, [newrows[i] for i in idx], shared)
        axis = -np.asarray(pad["normal"])
        assert np.allclose(np.cross(pad["offset"], pad["axis"]), 0)
        gaps = [
            1000 * axial_gap(skin, base, pad["role"], cloud([rs[i] for i in idx]), axis)
            for rs in (oldrows, newrows)
        ]
        assert 2 <= gaps[1] <= 5
        report[name] = dict(previous_gap_mm=gaps[0], gap_mm=gaps[1], axis=pad["axis"])


def check(view, baseline):
    d, old, h = view / "data", baseline / "data", view / "human_v5"
    base = load(h / "base.json")
    faces = np.array(base["triangles"]).reshape(-1, 3)
    assert base["vertices"] == 1401 and (h / "watch.json").is_file()
    mapping, fits = load(HERE / TARGETS), load(d / REPORT)
    assert fits.keys() == mapping.keys()
    changed_keys = ROWS | {k for k, f in fits.items() if "pads" in f}
    assert (set(mapping) | ROWS) - changed_keys == {
        "pulldown_machine~m=pin",
        "pulldown_machine~m=plate",
    }
    f0, f1 = files(baseline), files(view)
    changed = {
        p.as_posix()
        for p in f1
        if p not in f0 or (view / p).read_bytes() != (baseline / p).read_bytes()
    }
    expected = {f"data/{k}.wgm" for k in changed_keys} | {
        "data/" + s
        for s in ("parts.bin", "wgm_manifest.json", "pull_station_fit.json", REPORT)
    }
    assert f0.keys() <= f1.keys() and changed - {"v5_bundle_report.json"} == expected, (
        changed ^ expected
    )
    cat = wire.read_parts(d / "parts.bin")
    prefix = (old / "parts.bin").read_bytes()
    assert (d / "parts.bin").read_bytes()[8 : len(prefix)] == prefix[8:]
    before, after = [load(root / "wgm_manifest.json") for root in (old, d)]
    assert {
        k: v for k, v in before.items() if k not in ("clips", "machineOverlays")
    } == {k: v for k, v in after.items() if k not in ("clips", "machineOverlays")}
    assert set(after["clips"]) == set(before["clips"]) | changed_keys
    assert {
        k: v for k, v in before["machineOverlays"].items() if k not in changed_keys
    } == {k: v for k, v in after["machineOverlays"].items() if k not in changed_keys}
    tower0, tower1 = [load(root / "pull_station_fit.json") for root in (old, d)]
    assert {
        k for k in tower0 if tower0[k] != tower1[k]
    } == ROWS and tower0.keys() == tower1.keys()
    hands = load(view / "hand_fit_report.json")
    report = {}
    shared = {}
    for k in sorted(set(mapping) | ROWS):
        raw = load(d / (k + ".json"))
        objs = raw["objects"]
        grips = hands[k]["grips"]
        hand = [p[0] for g in grips.values() for p in g["pad_mm"].values()]
        src = old / (k + ".wgm")
        oldrows = wire.read_clip(src, cat)[1] if src.is_file() else []
        prior = (
            before["machineOverlays"]
            .get(k, {})
            .get("targets", before["plateOverlays"].get(k, {}))
        )
        r = report[k] = dict(
            hand_min_mm=min(hand, default=None),
            tris_before=triangles(objs, prior, oldrows),
        )
        if k not in changed_keys:
            assert "no shared 2–5 mm setting" in fits[k]["unchanged"]
            r.update(tris_after=r["tris_before"], **fits[k])
            continue
        acts, rows = wire.read_clip(d / (k + ".wgm"), cat)
        clock, skin = avatar_at_key_times(h / (k + ".bin"), acts)
        assert np.array_equal(acts, np.asarray(raw["acts"], "<f4"))
        sweep = SkinSweep(skin, faces)
        pads = r["pads"] = {}
        i = len(oldrows)
        overlay = after["machineOverlays"][k]
        spec = mapping.get(k, {})
        assert overlay == dict(
            count=len(rows),
            targets={**prior, **{str(j): n for n, (j, _) in spec.items()}},
        )
        r.update(tris_after=triangles(objs, overlay["targets"], rows), poses=len(clock))
        if k in ROWS:
            check_tower(
                k, raw, base, skin, sweep, oldrows, rows, tower1[k], pads, shared
            )
        else:
            prev, blob = src.read_bytes(), (d / (k + ".wgm")).read_bytes()
            assert blob[:6] == prev[:6] and blob[8 : len(prev)] == prev[8:]
        if k in fits:
            assert fits[k]["preceding"] == i and fits[k]["records"] == len(rows) - i
        for name, m in fits.get(k, {}).get("pads", {}).items():
            j, group = spec[name]
            o = objs[j]
            assert o["name"] == name and group == m["group"]
            layers = rows[i : i + m["records"]]
            i += len(layers)
            assert len(layers) == 2
            ids(group, layers, shared)
            p, q, s = decompose_frames(strip_fake_animation(o["m"]))
            rot = Rotation.from_quat(q)
            shift = np.array(m.get("offset", np.zeros(3)))
            assert all(
                l["nf"] == len(p)
                and np.max(np.linalg.norm(l["pos"] - p - shift, axis=1)) < 0.00011
                for l in layers
            )
            if "axle" in m:
                axis = rot[0].apply([0, 0, 1])
                axle = next(obj for obj in objs if obj["name"] == "roller_axle")
                pc, ar, _ = object_pose(axle)
                assert (
                    abs(np.dot(ar.apply([0, 0, 1]), axis)) > 0.99999
                    and abs(axis[0]) > 0.99999
                )
                assert np.linalg.norm(np.cross(p[0] - pc, axis)) < 1e-5
                assert all(
                    abs(np.dot(Rotation.from_quat(l["quat"][0]).apply([0, 0, 1]), axis))
                    > 0.99999
                    for l in layers
                )
            else:
                assert all(
                    np.max((Rotation.from_quat(l["quat"]) * rot.inv()).magnitude())
                    < 0.00011
                    for l in layers
                )
            if m["axis"] is not None:
                axis = np.asarray(m["axis"])
                assert np.linalg.norm(np.cross(shift, axis)) < 1e-8
                gap = axial_gap(skin, base, m["anatomy"], cloud(layers), axis) * 1000
                assert 2 <= gap <= 5 and swept_clear(
                    sweep, np.vstack([v for v, _ in cloud(layers)])
                )
                rail = m["rail"]
                b = np.array(rail["bore"])
                t = rail["tip"]
                z = rail["bottom"]
                hole = (np.dot(b, axis) - z) / (t - z) * 12 - 0.5
                assert (
                    np.allclose(axis, rail["axis"])
                    and 0 <= round(hole) <= 11
                    and abs(hole - round(hole)) < 1e-7
                )
                pin = next(
                    o
                    for o in objs
                    if o["name"]
                    == (
                        "chest_pin"
                        if name == "chest"
                        else ("adjust_pin" if k.startswith("plate_row") else "seat_pin")
                    )
                )
                assert (
                    np.linalg.norm(np.cross(b - object_pose(pin)[0], [1, 0, 0])) < 1e-6
                )
                assert any(
                    np.linalg.norm(l["pos"][0] - b) < 1e-5 and l["nf"] == 1
                    for l in rows[i:]
                )
                pads[name] = dict(
                    gap_mm=gap, axis=m["axis"], travel_mm=np.dot(shift, axis) * 1000
                )
            else:
                baked = (
                    rot[0]
                    .inv()
                    .apply(np.vstack([l["world"][0] for l in layers]) - p[0])
                )
                orig = vertices(o) * s[0]
                bounds_mm = 1000 * max(
                    abs(orig.min(0) - baked.min(0)).max(),
                    abs(orig.max(0) - baked.max(0)).max(),
                )
                assert bounds_mm < 0.1, (k, name, bounds_mm)
                hit = penetration(
                    skin,
                    faces,
                    clock,
                    acts,
                    orig,
                    baked,
                    layers[0]["pos"],
                    q if "axle" in m else layers[0]["quat"],
                )
                assert (
                    hit["added_hull_mm"] <= 10
                    and abs(hit["new_hull_mm"] - m["collision"]["new_hull_mm"]) < 0.15
                )
                pads[name] = dict(**hit, bounds_mm=bounds_mm, keys=len(p))
                if "axle" in m:
                    pads[name]["axle"] = m["axle"]
        assert all(
            l["nf"] == 1
            and np.isfinite(l["world"]).all()
            and swept_clear(sweep, l["world"][0])
            for l in rows[i:]
        )
        r["hardware_records"] = len(rows) - i
    return dict(
        clips=report,
        unchanged_files=len(f1) - len(changed),
        catalog=[int.from_bytes(prefix[4:8], "little"), len(cat)],
        bytes_before=sum(f0.values()),
        bytes_after=sum(f1.values()),
        deltas={f: f1[Path(f)] - f0.get(Path(f), 0) for f in sorted(changed)},
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("view", type=Path)
    ap.add_argument("baseline", type=Path)
    args = ap.parse_args()
    print(json.dumps(check(args.view, args.baseline), indent=2))
