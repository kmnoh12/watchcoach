"""Read back the eight chest presses, including the unchanged pin seats and hand tracks."""

import argparse
import json
from pathlib import Path

import numpy as np
import check_app3d_stage1 as wire
from check_app3d_lower_press_pads import bounds, overlap
from check_app3d_row_pads import cloud, files, ids, triangles
from upgrade_app3d_chest_press_pads import (
    HERE,
    PIN,
    POST,
    RAIL,
    REPORT,
    SEAT,
    TARGETS,
    Z,
    center,
    load,
    object_pose,
    vertices,
    world,
)
from upgrade_app3d_pull_stations import avatar_at_key_times
from bench_fit import swept_clear
from body_fit import SkinSweep
from fixed_pad_contact import penetration
from pull_pad_fit import axial_gap


def engagement(objects, layers, sweep):
    post = layers[POST]
    collar = post[0]["world"][0]
    insert, saddle = [r["world"][0] for r in layers[RAIL]]
    shaft, knob = [r["world"][0] for r in layers[PIN]]
    seat = np.vstack([r["world"][0] for r in layers[SEAT]])
    hole = center(collar)
    pin = center(world(objects[PIN]))
    lock = center(world(objects[POST]))
    lock[2] = pin[2]
    assert (
        np.max(abs(lock - hole)) < 0.0001
        and np.max(abs(center(shaft)[1:] - hole[1:])) < 0.0001
    )
    index = (hole[2] - insert[:, 2].min()) / np.ptp(insert[:, 2]) * 12 - 0.5
    assert 0 <= round(index) <= 11 and abs(index - round(index)) < 0.0002
    assert min(shaft[:, 0]) < hole[0] < max(shaft[:, 0]) and np.all(
        overlap(shaft, knob) > 0
    )
    assert (overlap(insert, saddle) > 0).all() and (overlap(saddle, seat) > 0).all()
    assert min(saddle[:, 2]) > max(r["world"][0, :, 2].max() for r in post)
    assert knob[:, 2].max() < seat[:, 2].min()
    assert any(
        (overlap(r["world"][0], world(objects["base_rail.005"])) > 0).all()
        for r in post
    )
    for n in (SEAT, POST, RAIL, PIN):
        for r in layers[n]:
            v = r["world"][0]
            assert swept_clear(sweep, v)
            for o in objects.values():
                if not np.allclose(o["m"], o["m"][0], atol=1e-5):
                    assert (overlap(v, wire.original(o).reshape(-1, 3)) < 0).any(), (
                        n,
                        o["name"],
                    )
    return int(round(index))


def check(view, baseline):
    d, old, h = view / "data", baseline / "data", view / "human_v5"
    base = load(h / "base.json")
    assert base["vertices"] == 1401 and (h / "watch.json").is_file()
    faces = np.array(base["triangles"]).reshape(-1, 3)
    hands = load(view / "hand_fit_report.json")
    spec, fit = load(HERE / TARGETS), load(d / REPORT)
    assert spec.keys() == fit.keys() and len(fit) == 8
    passed = {k for k, m in fit.items() if "pads" in m}
    a, b = files(baseline), files(view)
    assert a.keys() <= b.keys()
    delta = {
        str(p)
        for p in b
        if p not in a or (view / p).read_bytes() != (baseline / p).read_bytes()
    }
    assert delta - {"v5_bundle_report.json"} == {f"data/{k}.wgm" for k in passed} | {
        "data/" + n for n in ("parts.bin", "wgm_manifest.json", REPORT)
    }
    mb, ma = (load(z / "wgm_manifest.json") for z in (old, d))
    assert set(ma["clips"]) == set(mb["clips"]) | passed
    assert {**ma, "clips": None, "machineOverlays": None} == {
        **mb,
        "clips": None,
        "machineOverlays": None,
    }
    assert {k: v for k, v in ma["machineOverlays"].items() if k not in passed} == {
        k: v for k, v in mb["machineOverlays"].items() if k not in passed
    }
    cat = wire.read_parts(d / "parts.bin")
    prefix = (old / "parts.bin").read_bytes()
    assert (d / "parts.bin").read_bytes()[8 : len(prefix)] == prefix[8:]
    shared = {}
    result = {}
    towers = load(old / "press_station_fit.json")
    # Tie the standard cushion/foam IDs back to the already installed prototypes.
    prior = load(old / "pull_pad_fit_02.json")
    for donor in ("pullover_machine", "plate_row"):
        rr = wire.read_clip(old / (donor + ".wgm"), cat)[1]
        i = prior[donor]["preceding"]
        for m in prior[donor]["pads"].values():
            j = i + m["records"]
            if m["group"] in ("seat_pad__002", "back_pad__003", "head_pad__001"):
                ids(m["group"], rr[i:j], shared)
            i = j
    donorrows = wire.read_clip(old / "lever_pulldown~m=pin.wgm", cat)[1]
    for k, mapping in spec.items():
        raw = load(d / (k + ".json"))
        objs = {o["name"]: o for o in raw["objects"]}
        path = old / (k + ".wgm")
        prev = wire.read_clip(path, cat)[1] if path.exists() else []
        before = mb["machineOverlays"].get(k, {})
        native = before.get("targets", mb["plateOverlays"].get(k, {}))
        covered = before.get("covered", {})
        grips = [
            v[0] for side in hands[k]["grips"].values() for v in side["pad_mm"].values()
        ]
        r = result[k] = dict(
            hand_min_mm=min(grips, default=None),
            tris_before=triangles(raw["objects"], native | covered, prev),
        )
        if k not in passed:
            r.update(tris_after=r["tris_before"], **fit[k])
            continue
        f = d / path.name
        acts, rows = wire.read_clip(f, cat)
        off = len(prev)
        assert fit[k]["preceding"] == off
        if off:
            p = path.read_bytes()
            assert f.read_bytes()[:6] == p[:6] and f.read_bytes()[8 : len(p)] == p[8:]
        ov = ma["machineOverlays"][k]
        assert (
            ov["targets"] == native | {str(i): n for n, (i, g) in mapping.items()}
            and ov.get("covered", {}) == covered
            and ov["count"] == len(rows) == off + fit[k]["records"]
        )
        assert np.array_equal(acts, np.array(raw["acts"], "<f4"))
        clock, skin = avatar_at_key_times(h / (k + ".bin"), acts)
        samples = np.concatenate((skin, (skin[1:] + skin[:-1]) / 2))
        sweep = SkinSweep(skin, faces)
        r.update(
            tris_after=triangles(raw["objects"], ov["targets"] | covered, rows), pads={}
        )
        layers = {}
        for n, m in fit[k]["pads"].items():
            j, g = mapping[n]
            o = raw["objects"][j]
            assert o["name"] == n and m["group"] == g
            rs = layers[n] = rows[off : off + m["records"]]
            off += len(rs)
            assert all(z["nf"] == 1 for z in rs)
            for row in rs:
                v = row["world"][0]
                tri = v[row["faces"]]
                assert (
                    np.isfinite(v).all()
                    and np.linalg.norm(
                        np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1
                    ).min()
                    > 1e-12
                )
            if "rail" in m:
                continue
            ids(g, rs, shared)
            p, rot, s = object_pose(o)
            orig = vertices(o) * s
            v = np.vstack([a for a, t in cloud(rs)])
            offset = np.array(m.get("offset", [0, 0, 0]))
            local = rot.inv().apply(v - p - offset)
            hit = r["pads"][n] = {}
            err = abs(bounds(orig) - bounds(local)).max() * 1000
            if n == "ankle_roller":
                assert any(
                    tuple(z["pid"] for z in donorrows[i : i + 2]) == shared[g]
                    for i in range(len(donorrows) - 1)
                )
                axis = rot.apply(Z)
                assert np.allclose(axis, m["axle"]) and np.allclose(
                    abs(axis), [1, 0, 0]
                )
                assert np.max(abs(center(v) - p)) < 0.0001
                for mount in ("roller_post", "roller_post.001"):
                    assert (overlap(v, world(objs[mount])) > 0).all()
                err = 1000 * max(
                    abs(np.ptp(orig[:, 2]) - np.ptp(local[:, 2])),
                    abs(
                        np.linalg.norm(orig[:, :2], axis=1).max()
                        - np.linalg.norm(local[:, :2], axis=1).max()
                    ),
                )
                hit["axis"] = axis.round(6).tolist()
            assert err < 0.15, (k, n, err)
            hit["contact_extent_error_mm"] = err
            if m.get("axis"):
                gap = 1000 * axial_gap(samples, base, "seat_pad", cloud(rs), Z)
                assert (
                    2 <= gap <= 5
                    and np.allclose(offset[:2], 0)
                    and m["axis"] == Z.tolist()
                )
                hit.update(gap_mm=gap, adjust_mm=1000 * offset[2])
            else:
                htest = penetration(
                    skin, faces, clock, acts, orig, local, [p], [rot.as_quat()]
                )
                assert (
                    htest["added_hull_mm"] <= 10
                    and abs(htest["new_hull_mm"] - m["collision"]["new_hull_mm"]) < 0.15
                )
                hit.update(htest)
        assert off == len(rows) and set(layers) == set(mapping)
        if POST in mapping:
            r["engaged_hole"] = engagement(objs, layers, sweep)
        if k in towers:
            seat = towers[k]["fits"][SEAT]
            p, rot, s = object_pose(objs[SEAT])
            pos = p + Z * seat["offset_mm"] / 1000
            crown = [
                z
                for z in prev
                if z["nf"] == 1
                and np.allclose(z["pos"][0], pos, atol=0.00001)
                and z["mat"] == 4
            ]
            assert len(crown) == 2
            gap = 1000 * axial_gap(
                samples, base, "seat_pad", cloud(crown), rot.apply(Z)
            )
            assert 2 <= gap <= 5 and seat["axis"] == Z.tolist()
            r["prior_seat_gap_mm"] = gap
    return dict(
        models=result,
        catalog=[int.from_bytes(prefix[4:8], "little"), len(cat)],
        bytes=[sum(a.values()), sum(b.values())],
        unchanged_files=len(b) - len(delta),
        deltas=sorted(delta),
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("view", type=Path)
    ap.add_argument("baseline", type=Path)
    args = ap.parse_args()
    print(json.dumps(check(args.view, args.baseline), indent=2))
