"""Decode the nine lower-machine clips against the preceding lower tower/plate bundle."""

import argparse
import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
import check_app3d_stage1 as wire
from check_app3d_row_pads import triangles, ids, files, cloud
from upgrade_app3d_lower_pads import HERE, TARGETS, REPORT, load, pose, vertices, center
from upgrade_app3d_pull_stations import avatar_at_key_times
from bench_fit import swept_clear
from body_fit import SkinSweep
from fixed_pad_contact import penetration
from pull_pad_fit import axial_gap


def check(view, baseline):
    d, old = view / "data", baseline / "data"
    mapping = load(HERE / TARGETS)
    fit = load(d / REPORT)
    assert fit.keys() == mapping.keys()
    passed = {k for k, v in fit.items() if "pads" in v}
    assert passed == {"glute_kickback_machine", "hip_abductor", "nordic_curl"}
    f0, f1 = files(baseline), files(view)
    changed = {
        str(f)
        for f in f1
        if f not in f0 or (view / f).read_bytes() != (baseline / f).read_bytes()
    }
    expected = {f"data/{k}.wgm" for k in passed} | {
        "data/" + s for s in ("parts.bin", "wgm_manifest.json", REPORT)
    }
    assert f0.keys() <= f1.keys() and changed - {"v5_bundle_report.json"} == expected
    prefix = (old / "parts.bin").read_bytes()
    assert (d / "parts.bin").read_bytes()[8 : len(prefix)] == prefix[8:]
    cat = wire.read_parts(d / "parts.bin")
    m0, m1 = [load(x / "wgm_manifest.json") for x in (old, d)]
    assert set(m1["clips"]) == set(m0["clips"]) | passed
    assert {k: v for k, v in m1.items() if k not in ("clips", "machineOverlays")} == {
        k: v for k, v in m0.items() if k not in ("clips", "machineOverlays")
    }
    assert {k: v for k, v in m1["machineOverlays"].items() if k not in passed} == {
        k: v for k, v in m0["machineOverlays"].items() if k not in passed
    }
    h = view / "human_v5"
    base = load(h / "base.json")
    assert base["vertices"] == 1401 and (h / "watch.json").is_file()
    faces = np.array(base["triangles"]).reshape(-1, 3)
    hands = load(view / "hand_fit_report.json")
    result = {}
    shared = {}
    for k, spec in mapping.items():
        raw = load(d / f"{k}.json")
        objs = raw["objects"]
        by_name = {o["name"]: o for o in objs}
        grips = [v[0] for g in hands[k]["grips"].values() for v in g["pad_mm"].values()]
        prior = m0["machineOverlays"].get(k, {})
        targets = prior.get("targets", m0["plateOverlays"].get(k, {}))
        covered = prior.get("covered", {})
        old_path = old / f"{k}.wgm"
        oldrows = wire.read_clip(old_path, cat)[1] if old_path.is_file() else []
        total = triangles(objs, targets | covered, oldrows)
        r = result[k] = dict(tris_before=total, hand_min_mm=min(grips, default=None))
        if k not in passed:
            r.update(tris_after=total, **fit[k])
            continue
        acts, rows = wire.read_clip(d / f"{k}.wgm", cat)
        assert np.array_equal(acts, np.asarray(raw["acts"], "<f4"))
        i = len(oldrows)
        assert fit[k]["preceding"] == i and len(rows) - i == fit[k]["records"]
        updated = m1["machineOverlays"][k]
        assert (
            updated["targets"] == targets | {str(j): n for n, (j, _) in spec.items()}
            and updated.get("covered", {}) == covered
            and updated["count"] == len(rows)
        )
        if i:
            prefix0 = old_path.read_bytes()
            blob = (d / f"{k}.wgm").read_bytes()
            assert blob[:6] == prefix0[:6] and blob[8 : len(prefix0)] == prefix0[8:]
        r.update(
            tris_after=triangles(objs, updated["targets"] | covered, rows), pads={}
        )
        clock, skin = avatar_at_key_times(h / f"{k}.bin", acts)
        sweep = SkinSweep(skin, faces) if k == "hip_abductor" else None
        seats = []
        for name, meta in fit[k]["pads"].items():
            layers = rows[i : i + meta["records"]]
            i += len(layers)
            j, group = spec[name]
            o = objs[j]
            assert o["name"] == name and all(
                np.isfinite(l["world"]).all() for l in layers
            )
            if "rail" in meta:
                assert len(layers) == 7 and len(seats) == 2
                collar, lower, upper, slider, shaft, knob, saddle = layers
                assert all(
                    l["nf"] == 1 and swept_clear(sweep, l["world"][0]) for l in layers
                )
                bore = collar["pos"][0]
                rq = meta["rail"]
                assert np.linalg.norm(bore - rq["bore"]) < 1e-6
                assert np.linalg.norm(shaft["pos"][0, 1:] - bore[1:]) < 1e-6
                shaftv = shaft["world"][0]
                assert (
                    shaftv[:, 0].min() < bore[0] < shaftv[:, 0].max()
                    and abs(knob["pos"][0, 2] - bore[2]) < 1e-6
                )
                v = slider["world"][0]
                bottom, tip = v[:, 2].min(), v[:, 2].max()
                hole = (bore[2] - bottom) / (tip - bottom) * 12 - 0.5
                assert 0 <= round(hole) < 12 and abs(hole - round(hole)) < 0.001
                v = saddle["world"][0]
                assert v[:, 2].min() < tip < v[:, 2].max() and np.allclose(
                    v[:, :2].mean(0), bore[:2], atol=0.001
                )
                assert all(
                    0.0001 < v[:, 2].max() - sv[:, 2].min() < 0.005
                    and (
                        np.minimum(v.max(0), sv.max(0))[:2]
                        - np.maximum(v.min(0), sv.min(0))[:2]
                        > 0.02
                    ).all()
                    for sv in seats
                )
                b = by_name["mopt_seat_base_link"]
                p, rot, s = pose(b)
                vb = rot[0].apply(vertices(b) * s[0]) + p[0]
                assert vb[:, 2].min() < lower["world"][0, :, 2].min() < vb[:, 2].max()
                arm_top = -np.inf
                for arm in ("leg_arm", "leg_arm.001"):
                    _, rr, _ = pose(by_name[arm])
                    spin = (rr * rr[0].inv()).apply([0, 0, 1])
                    assert np.allclose(spin, [0, 0, 1], atol=1e-5)
                    arm_top = max(arm_top, wire.original(by_name[arm])[:, :, 2].max())
                arm_gap = (saddle["world"][0, :, 2].min() - arm_top) * 1000
                assert arm_gap > 2, ("moving hip levers strike the saddle", arm_gap)
                r["post"] = dict(
                    moving_arm_gap_mm=arm_gap,
                    height_axis=rq["axis"],
                    engaged_index=int(round(hole)),
                    static_records=len(layers),
                )
                continue
            assert group == meta["group"] and len(layers) == 2
            ids(group, layers, shared)
            p, rot, s = pose(o)
            c = center(vertices(o))
            delta = np.asarray(meta["offset"])
            q = (
                (rot * Rotation.from_euler("z", 180, degrees=True))
                if meta.get("inward_half_turn")
                else rot
            )
            expect = p + rot.apply(c * s) + delta
            assert all(
                l["nf"] == len(p)
                and np.max(np.linalg.norm(l["pos"] - expect, axis=1)) < 0.00013
                and np.max((Rotation.from_quat(l["quat"]) * q.inv()).magnitude())
                < 0.00012
                for l in layers
            )
            v = np.vstack([l["world"][0] for l in layers])
            oldv = vertices(o) * s[0]
            local = rot[0].inv().apply(v - p[0] - delta)
            pad = r["pads"][name] = dict(
                poses=len(p), tris=sum(len(l["faces"]) for l in layers)
            )
            assert pad["tris"] >= (1216 if "axle_local" in meta else 476)
            if meta["axis"]:
                assert np.allclose(np.cross(delta, meta["axis"]), 0)
                gap = (
                    axial_gap(skin, base, "seat_pad", cloud(layers), meta["axis"])
                    * 1000
                )
                assert (
                    2 < gap < 5
                    and abs(gap - meta["gap_mm"]) < 0.03
                    and swept_clear(sweep, v)
                )
                seats.append(v)
                pad.update(gap_mm=gap, offset_mm=delta[2] * 1000)
                continue
            hit = penetration(skin, faces, clock, acts, oldv, local, p, rot.as_quat())
            assert (
                hit["added_hull_mm"] <= 10
                and abs(hit["new_hull_mm"] - meta["collision"]["new_hull_mm"]) < 0.18
            ), (k, name, hit, meta)
            pad.update(hit)
            if "axle_local" in meta:
                axle = by_name.get("roller_axle", by_name.get("ankle_axle"))
                ap, ar, _ = pose(axle)
                axis = ar.apply([0, 0, 1])
                qa = Rotation.from_quat(layers[0]["quat"]).apply([0, 0, 1])
                err = np.linalg.norm(
                    np.cross(layers[0]["pos"] - ap, axis), axis=1
                ).max()
                assert err < 0.00013 and np.all(
                    np.abs(np.sum(qa * axis, axis=1)) > 0.9999
                )
                pad["axle_error_mm"] = err * 1000
        assert i == len(rows)
    return dict(
        clips=result,
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
    a = ap.parse_args()
    print(json.dumps(check(a.view, a.baseline), indent=2))
