"""Decode the lower sled/press overlays: contacts, shared PIDs, indexed hardware and unchanged bytes."""

import argparse
import json
from pathlib import Path

import numpy as np
import check_app3d_stage1 as wire
from check_app3d_row_pads import cloud, files, ids, triangles
from upgrade_app3d_lower_press_pads import (
    HERE,
    POST,
    REPORT,
    TARGETS,
    Z,
    load,
    pose,
    vertices,
    world,
)
from upgrade_app3d_pull_stations import avatar_at_key_times
from bench_fit import swept_clear
from body_fit import SkinSweep
from fixed_pad_contact import penetration
from pull_pad_fit import axial_gap


def bounds(v):
    return np.array([v.min(axis=-2), v.max(axis=-2)])


def overlap(a, b):
    return np.minimum(a.max(0), b.max(0)) - np.maximum(a.min(0), b.min(0))


def mechanism(key, objects, layers, meta, seat, sweep):
    post = POST[key]
    pieces = layers[post]
    pin = "seat_adjuster.001" if key == "leg_press_horizontal" else post
    collar, lower, upper, slider = pieces[:4]
    shaft, knob = layers[pin][4:6] if pin == post else layers[pin]
    tray = (layers["seat_frame"][0] if pin != post else pieces[6])["world"][0]
    assert all(
        row["nf"] == 1 and swept_clear(sweep, row["world"][0])
        for n, rs in layers.items()
        if "rail" in meta[n]
        for row in rs
    )
    hole = collar["pos"][0]
    tip = slider["world"][0, :, 2].max()
    bottom = slider["world"][0, :, 2].min()
    ix = (hole[2] - bottom) / (tip - bottom) * 12 - 0.5
    assert abs(ix - round(ix)) < 0.0001 and 0 <= round(ix) < 12
    assert (
        np.max(abs(shaft["pos"][0, 1:] - hole[1:])) < 1e-6
        and abs(knob["pos"][0, 2] - hole[2]) < 1e-6
    )
    assert (
        shaft["world"][0, :, 0].min() < hole[0] < shaft["world"][0, :, 0].max()
        and (overlap(knob["world"][0], shaft["world"][0]) > 0).all()
    )
    assert (
        np.max(abs(upper["world"][0, :, 2].min() - collar["world"][0, :, 2].max()))
        < 1e-6
    )
    assert (
        lower["world"][0, :, 2].min()
        <= bottom
        < hole[2]
        < upper["world"][0, :, 2].max()
        < tip
    )
    assert tray[:, 2].min() < tip < tray[:, 2].max() and (overlap(tray, seat) > 0).all()
    assert (overlap(tray, slider["world"][0]) > 0).all() and (
        overlap(tray, upper["world"][0]) < 0
    ).any()
    if key == "leg_press_calf":
        base = pieces[-1]["world"][0]
        assert all(
            (overlap(base, world(objects[n])) > 0).all()
            for n in ("foot.004", "foot.005")
        )
    else:
        base = world(
            objects["mopt_seat_base_link" if key == "leg_press_45" else "seat_mount"]
        )
    assert (overlap(lower["world"][0], base) > 0).all()
    if pin != post:
        assert np.allclose(
            world(objects[pin])[:, 0].max(), knob["world"][0, :, 0].max(), atol=1e-6
        )
        assert tray[:, 2].min() > hole[2] + 0.012
    # No sled, footplate or other moving mesh can strike the new fixed assembly.
    for o in objects.values():
        p, r, s = pose(o)
        if len(p) == 1:
            continue
        v = wire.original(o).reshape(-1, 3)
        for n, rs in layers.items():
            if "rail" in meta[n] or meta[n].get("axis"):
                for row in rs:
                    assert (overlap(row["world"][0], v) < 0).any(), (key, n, o["name"])
    return dict(
        index=int(round(ix)),
        axis=meta[post]["rail"]["axis"],
        tray_to_slider_mm=(tip - tray[:, 2].min()) * 1000,
        pan_to_tray_mm=overlap(tray, seat)[2] * 1000,
    )


def check(view, baseline):
    data = view / "data"
    old = baseline / "data"
    h = view / "human_v5"
    spec = load(HERE / TARGETS)
    fit = load(data / REPORT)
    assert fit.keys() == spec.keys()
    passed = {k for k, m in fit.items() if "pads" in m}
    assert set(spec) - passed == {
        "standing_calf",
        "standing_leg_curl",
        "torso_rotation_machine",
    }
    m0, m1 = (load(d / "wgm_manifest.json") for d in (old, data))
    f0, f1 = files(baseline), files(view)
    assert f0.keys() <= f1.keys()
    changes = {
        str(f)
        for f in f1
        if f not in f0 or (view / f).read_bytes() != (baseline / f).read_bytes()
    }
    assert changes - {"v5_bundle_report.json"} == {f"data/{k}.wgm" for k in passed} | {
        "data/" + n for n in ["parts.bin", "wgm_manifest.json", REPORT]
    }
    assert set(m1["clips"]) == set(m0["clips"]) | passed
    for key in set(m1) | set(m0):
        if key == "machineOverlays":
            assert {k: m for k, m in m1[key].items() if k not in passed} == {
                k: m for k, m in m0[key].items() if k not in passed
            }
        elif key != "clips":
            assert m0[key] == m1[key]
    prefix = (old / "parts.bin").read_bytes()
    assert (data / "parts.bin").read_bytes()[8 : len(prefix)] == prefix[8:]
    cat = wire.read_parts(data / "parts.bin")
    base = load(h / "base.json")
    assert base["vertices"] == 1401 and (h / "watch.json").is_file()
    faces = np.array(base["triangles"]).reshape(-1, 3)
    hands = load(view / "hand_fit_report.json")
    shared = {}
    results = {}
    # Verify against the actual PIDs in the earlier batches, not just this batch's repeat instances.
    prior = load(old / "pull_pad_fit_02.json")
    for k in ("pullover_machine", "seated_row_machine"):
        rows = wire.read_clip(old / (k + ".wgm"), cat)[1]
        i = prior[k]["preceding"]
        for m in prior[k]["pads"].values():
            rs = rows[i : i + m["records"]]
            i += len(rs)
            ids(m["group"], rs, shared)
    for k, m in fit.items():
        raw = load(data / (k + ".json"))
        objects = raw["objects"]
        names = {o["name"]: o for o in objects}
        prev = m0["machineOverlays"].get(k, {})
        t0 = prev.get("targets", m0["plateOverlays"].get(k, {}))
        covered = prev.get("covered", {})
        op = old / (k + ".wgm")
        oldrows = wire.read_clip(op, cat)[1] if op.exists() else []
        total = triangles(objects, t0 | covered, oldrows)
        grips = [v[0] for g in hands[k]["grips"].values() for v in g["pad_mm"].values()]
        res = results[k] = dict(tris_before=total, hand_min_mm=min(grips, default=None))
        if k not in passed:
            res.update(tris_after=total, **m)
            continue
        path = data / (k + ".wgm")
        acts, rows = wire.read_clip(path, cat)
        i = len(oldrows)
        meta = m["pads"]
        ov = m1["machineOverlays"][k]
        assert (
            ov["targets"] == t0 | {str(idx): n for n, (idx, _) in spec[k].items()}
            and ov.get("covered", {}) == covered
        )
        assert (
            ov["count"] == len(rows)
            and m["preceding"] == i
            and len(rows) == i + m["records"]
        )
        assert np.array_equal(acts, np.asarray(raw["acts"], "<f4"))
        if i:
            blob = op.read_bytes()
            assert (
                path.read_bytes()[:6] == blob[:6]
                and path.read_bytes()[8 : len(blob)] == blob[8:]
            )
        res.update(
            tris_after=triangles(objects, ov["targets"] | covered, rows), pads={}
        )
        clock, skin = avatar_at_key_times(h / (k + ".bin"), acts)
        layers = {}
        seat = None
        sweep = SkinSweep(skin, faces) if k in POST else None
        for n, pad in meta.items():
            j, group = spec[k][n]
            o = objects[j]
            assert o["name"] == n and pad["group"] == group
            rs = layers[n] = rows[i : i + pad["records"]]
            i += len(rs)
            for row in rs:
                v, t = cat[row["pid"]]
                tri = v[t]
                assert (
                    np.isfinite(row["world"]).all()
                    and np.linalg.norm(
                        np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1
                    ).min()
                    > 1e-12
                )
            if "rail" in pad:
                continue
            ids(group, rs, shared)
            p, r, s = pose(o)
            oldv = vertices(o) * s[0]
            offset = np.array(pad.get("offset", [0, 0, 0]))
            vv = np.concatenate([l["world"] for l in rs], axis=1)
            assert (
                all(l["nf"] == len(p) for l in rs) and np.max(np.abs(s - s[0])) < 2e-5
            )
            local = np.einsum(
                "fvi,fij->fvj", vv - (p + offset)[:, None, :], r.as_matrix()
            )
            err = np.abs(bounds(local) - bounds(oldv)[:, None, :]).max() * 1000
            assert err < 0.18, (k, n, err)
            drift = np.abs(local - local[:1]).max() * 1000
            assert drift < 0.18
            result = res["pads"][n] = dict(
                poses=len(p),
                tris=sum(len(l["faces"]) for l in rs),
                box_error_mm=err,
                rigid_drift_mm=drift,
            )
            if pad["axis"]:
                seat = vv[0]
                assert np.allclose(np.cross(offset, Z), 0) and pad["axis"] == Z.tolist()
                # Match both original key times and intermediate poses of the V6 fitter.
                samples = np.concatenate((skin, (skin[1:] + skin[:-1]) / 2))
                gap = axial_gap(samples, base, "seat_pad", cloud(rs), Z) * 1000
                assert abs(gap - 3.5) < 0.04 and swept_clear(sweep, seat)
                result.update(gap_mm=gap, adjust_mm=1000 * offset[2])
                continue
            hit = penetration(skin, faces, clock, acts, oldv, local[0], p, r.as_quat())
            assert (
                hit["added_hull_mm"] <= 10
                and abs(hit["new_hull_mm"] - pad["collision"]["new_hull_mm"]) < 0.18
            ), (k, n, hit, pad)
            result.update(hit)
        assert i == len(rows) and set(layers) == set(spec[k])
        if seat is not None:
            res["mechanism"] = mechanism(k, names, layers, meta, seat, sweep)
    return dict(
        clips=results,
        catalog=[int.from_bytes(prefix[4:8], "little"), len(cat)],
        unchanged_files=len(f1) - len(changes),
        bytes_before=sum(f0.values()),
        bytes_after=sum(f1.values()),
        deltas={f: f1[Path(f)] - f0.get(Path(f), 0) for f in sorted(changes)},
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("view", type=Path)
    ap.add_argument("baseline", type=Path)
    a = ap.parse_args()
    print(json.dumps(check(a.view, a.baseline), indent=2))
