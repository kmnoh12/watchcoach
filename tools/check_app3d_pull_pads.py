"""Compare the ten pull-station pad models to the immediately preceding tower/plate bundle."""

import argparse
import json
from pathlib import Path

import check_app3d_stage1 as wire
import numpy as np
from check_app3d_adjust_bench import files
from fixed_pad_contact import penetration
from pull_pad_fit import vertical_gap
from scipy.spatial.transform import Rotation
from upgrade_app3d_adjust_bench import HERE, load, object_pose
from upgrade_app3d_pull_pads import REPORT, TARGETS
from upgrade_app3d_pull_stations import avatar_at_key_times, verify_skin


def check(view, before):
    data, old, human = view / "data", before / "data", view / "human_v5"
    base = load(human / "base.json")
    faces = np.asarray(base["triangles"]).reshape(-1, 3)
    assert base["vertices"] == 1401 and (human / "watch.json").is_file()
    spec, fits = load(HERE / TARGETS), load(data / REPORT)
    pin_keys = ["lever_pulldown~m=pin", "lever_pulldown~m=pin_single"]
    prev, mf = [load(root / "wgm_manifest.json") for root in (old, data)]
    cat, prevcat = [wire.read_parts(root / "parts.bin") for root in (data, old)]
    stock = (old / "parts.bin").read_bytes()
    assert (data / "parts.bin").read_bytes()[8 : len(stock)] == stock[8:]
    f0, f1 = files(before), files(view)
    changed = {
        str(f)
        for f in f1
        if f not in f0 or (view / f).read_bytes() != (before / f).read_bytes()
    }
    passed = set(pin_keys) | {k for k, f in fits.items() if "pads" in f}
    assert f0.keys() <= f1.keys() and changed - {"v5_bundle_report.json"} == {
        "data/" + k + ".wgm" for k in passed
    } | {
        "data/" + s
        for s in ("parts.bin", "wgm_manifest.json", REPORT, "pull_station_fit.json")
    }
    assert {k: v for k, v in mf.items() if k not in ("clips", "machineOverlays")} == {
        k: v for k, v in prev.items() if k not in ("clips", "machineOverlays")
    }
    assert set(mf["clips"]) == set(prev["clips"]) | passed
    assert {k: v for k, v in mf["machineOverlays"].items() if k not in passed} == {
        k: v for k, v in prev["machineOverlays"].items() if k not in passed
    }
    grips = load(view / "hand_fit_report.json")
    report = {}
    shared = {}
    for k in [*spec, *pin_keys]:
        if k not in passed:
            report[k] = fits[k]
            continue
        raw = load(data / f"{k}.json")
        objs = raw["objects"]
        acts, rows = wire.read_clip(data / f"{k}.wgm", cat)
        assert np.array_equal(acts, np.array(raw["acts"], "<f4"))
        clock, skin = avatar_at_key_times(human / f"{k}.bin", acts)
        hand = [p[0] for g in grips[k]["grips"].values() for p in g["pad_mm"].values()]
        out = report[k] = {
            "poses": len(clock),
            "hand_min_mm": min(hand, default=None),
            "pads": {},
        }
        oldrows = wire.read_clip(old / f"{k}.wgm", prevcat)[1]
        orig = (
            prev["machineOverlays"]
            .get(k, {})
            .get("targets", prev["plateOverlays"].get(k, {}))
        )
        current = mf["machineOverlays"][k]["targets"]
        assert current == (
            orig
            if k in pin_keys
            else {**orig, **{str(i): n for n, (i, _) in spec[k].items()}}
        )

        def tris(objects, targets, rendered):
            return sum(
                len(o["tris"]) // 3
                for i, o in enumerate(objects)
                if str(i) not in targets
            ) + sum(len(r["faces"]) for r in rendered)

        out.update(
            tris_before=tris(objs, orig, oldrows), tris_after=tris(objs, current, rows)
        )
        oldbytes, newbytes = [(p / f"{k}.wgm").read_bytes() for p in (old, data)]
        if k in pin_keys:
            # All 21 support records are static (50 B each); check the entire preceding station unchanged.
            prefix = len(oldrows) - 21
            assert (
                len(rows) == len(oldrows)
                and oldbytes[: -21 * 50] == newbytes[: -21 * 50]
            )
        else:
            prefix = len(oldrows)
            assert (
                oldbytes[:6] == newbytes[:6]
                and oldbytes[8:] == newbytes[8 : len(oldbytes)]
            )
        out["preserved_prefix"] = prefix
        tail = rows[prefix:]
        assert all(r["nf"] == 1 and np.isfinite(r["world"]).all() for r in tail)
        if k.startswith("lever_pulldown"):
            assert len(tail) == 21
            real = [
                {
                    "name": k,
                    "verts": cat[r["pid"]][0],
                    "pos": r["pos"],
                    "quats": r["quat"],
                    "sc": r["scale"],
                }
                for r in tail
            ]
            verify_skin(real, clock, skin, acts, faces)
            params = (
                load(data / "pull_station_fit.json")[k]["fits"]
                if k in pin_keys
                else fits[k]["pads"]
            )
            for n, start in [
                ("seat", 0),
                ("thigh_roller", 7),
                ("thigh_roller.001", 14),
            ]:
                meta = params[n]
                layers = tail[start : start + 2]
                o = next(x for x in objs if x["name"] == n)
                pos, rot, _scale = object_pose(o)
                target = pos + meta["offset"]
                axis = np.array(meta["axis"])
                assert np.allclose(axis, [0, 0, 1]) and np.allclose(
                    np.cross(axis, target - pos), 0
                )
                for row in layers:
                    assert (
                        np.allclose(row["pos"][0], target, atol=1e-7)
                        and (Rotation.from_quat(row["quat"][0]) * rot.inv()).magnitude()
                        < 1e-6
                    )
                ids = tuple(r["pid"] for r in layers)
                assert shared.setdefault(n, ids) == ids
                gap = 1000 * vertical_gap(
                    skin,
                    base,
                    meta["role"],
                    [(r["world"][0], r["faces"]) for r in layers],
                )
                assert 2 <= gap <= 5 and abs(gap - meta["gap_mm"]) < 0.03
                out["pads"][n] = {
                    "gap_mm": gap,
                    "axis": axis.tolist(),
                    "dz_mm": 1000 * (target - pos)[2],
                }
                if n != "seat":
                    axle = rot.apply([0, 0, 1])
                    spindle = tail[start + 4]
                    assert (
                        abs(axle[0]) > 0.9999
                        and np.linalg.norm(np.cross(spindle["pos"][0] - target, axle))
                        < 1e-5
                    )
                    out["pads"][n]["axle"] = axle.tolist()
                    if k in pin_keys:
                        before_layers = oldrows[prefix + start : prefix + start + 2]
                        out["pads"][n]["previous_gap_mm"] = 1000 * vertical_gap(
                            skin,
                            base,
                            meta["role"],
                            [(r["world"][0], r["faces"]) for r in before_layers],
                        )
            continue
        idx = 0
        for name, (i, group) in spec[k].items():
            meta = fits[k]["pads"][name]
            assert meta["group"] == group and meta["adjustment_axis"] is None
            layers = tail[idx : idx + meta["records"]]
            idx += len(layers)
            ids = tuple(r["pid"] for r in layers)
            assert shared.setdefault(group, ids) == ids
            obj = objs[i]
            assert obj["name"] == name
            p, r, s = object_pose(obj)
            v = np.array(obj["verts"]).reshape(-1, 3) * s
            baked = r.inv().apply(np.vstack([l["world"][0] for l in layers]) - p)
            error = max(
                abs(v.min(0) - baked.min(0)).max(), abs(v.max(0) - baked.max(0)).max()
            )
            assert error < 0.00003
            assert all(np.linalg.norm(l["pos"][0] - p) < 0.000001 for l in layers)
            if "axle" in meta:
                assert (
                    abs(
                        np.dot(
                            Rotation.from_quat(layers[0]["quat"][0]).apply([0, 0, 1]),
                            meta["axle"],
                        )
                    )
                    > 0.99999
                )
            hit = penetration(
                skin, faces, clock, acts, v, baked, p[None], r.as_quat()[None]
            )
            assert (
                hit["added_hull_mm"] <= 10
                and abs(hit["added_hull_mm"] - meta["collision"]["added_hull_mm"]) < 0.1
            )
            out["pads"][name] = dict(**hit, surface_mm=error * 1000)
        assert idx == len(tail)
    return {
        "clips": report,
        "unchanged_files": len(f1) - len(changed),
        "bytes_before": sum(f0.values()),
        "bytes_after": sum(f1.values()),
        "catalog": [len(prevcat), len(cat)],
        "deltas": {f: f1[Path(f)] - f0.get(Path(f), 0) for f in sorted(changed)},
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("view", type=Path)
    ap.add_argument("baseline", type=Path)
    args = ap.parse_args()
    print(json.dumps(check(args.view, args.baseline), indent=2))
