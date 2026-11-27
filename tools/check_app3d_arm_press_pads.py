"""Decode the six arm and shoulder clips against the already fitted tower bundle."""

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linprog
from scipy.spatial import ConvexHull
import check_app3d_stage1 as wire
from check_app3d_lower_press_pads import bounds, overlap
from check_app3d_row_pads import cloud, files, ids, triangles
from upgrade_app3d_arm_press_pads import (
    HERE,
    REPORT,
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
from part_registry import MAT_PAD, MAT_CHROME


def joined(a, b):
    """Test convex component envelopes, not just their bounding boxes."""
    if not np.all(overlap(a, b) > 0):
        return False
    planes = np.vstack([ConvexHull(v).equations for v in (a, b)])
    return linprog(
        [0, 0, 0],
        A_ub=planes[:, :3],
        b_ub=-planes[:, 3] - 0.00002,
        bounds=[(None, None)] * 3,
        method="highs",
    ).success


def engagement(k, objs, layers, slider, setting):
    socket, pin = setting["socket"], setting["pin"]
    collar, lower, upper = [z["world"][0] for z in layers[socket][:3]]
    (insert,) = [z["world"][0] for z in layers[slider] if z["mat"] == MAT_CHROME]
    shaft, knob = [z["world"][0] for z in layers[pin][-2:]]
    bore = center(collar)
    axis = np.array(setting["axis"])

    def along(v):
        return np.einsum("...j,j->...", v, axis)

    lo, hi = along(insert).min(), along(insert).max()
    assert np.allclose(bore, setting["bore"], atol=1e-5)
    ix = (along(bore) - lo) / (hi - lo) * 12 - 0.5
    assert (
        0 <= round(ix) < 12
        and abs(ix - round(ix)) < 0.0002
        and round(ix) == setting["hole"]
    )
    assert np.max(abs(center(shaft)[1:] - bore[1:])) < 0.0001
    assert shaft[:, 0].min() < bore[0] < shaft[:, 0].max() and joined(shaft, knob)
    assert along(lower).min() <= lo < along(bore) < along(upper).max() < hi
    assert (
        abs(along(lower).max() - along(collar).min()) < 1e-5
        and abs(along(upper).min() - along(collar).max()) < 1e-5
    )
    if pin != socket:
        assert np.max(abs(center(world(objs[pin]))[1:] - bore[1:])) < 0.0001
    back = slider == "back_mount"
    support = world(
        objs[
            "back_support"
            if back
            else "base_rail"
            if k == "dip_machine"
            else "seat_spine"
        ]
    )
    assert any(joined(v, support) for v in (lower, upper, collar)), (
        k,
        socket,
        "support",
    )
    pad = layers["tapered_back" if back else "seat.001"][0]["world"][0]
    if back:
        guide = layers["back_mount.001"][0]["world"][0]
        assert joined(insert, pad) and joined(guide, support) and joined(guide, pad)
        assert not joined(insert, support)
    else:
        tray = layers["seat_pan" if k == "dip_machine" else slider][-1]["world"][0]
        assert joined(tray, insert) and joined(tray, pad) and not joined(upper, tray)
        if k == "dip_machine":
            assert joined(layers[slider][0]["world"][0], tray)
    return int(round(ix))


def check(view, baseline):
    d, old, h = view / "data", baseline / "data", view / "human_v5"
    base = load(h / "base.json")
    hands = load(view / "hand_fit_report.json")
    assert base["vertices"] == 1401 and (h / "watch.json").is_file()
    faces = np.array(base["triangles"]).reshape(-1, 3)
    spec, fit = load(HERE / TARGETS), load(d / REPORT)
    assert spec.keys() == fit.keys() and len(fit) == 6
    passed = {k for k, m in fit.items() if "pads" in m}
    a, b = files(baseline), files(view)
    assert a.keys() <= b.keys()
    delta = {
        str(p)
        for p in b
        if p not in a or (view / p).read_bytes() != (baseline / p).read_bytes()
    }
    assert delta - {"v5_bundle_report.json"} == {f"data/{k}.wgm" for k in passed} | {
        "data/" + s for s in ("parts.bin", "wgm_manifest.json", REPORT)
    }
    mb, ma = [load(r / "wgm_manifest.json") for r in (old, d)]
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
    pre = (old / "parts.bin").read_bytes()
    assert (d / "parts.bin").read_bytes()[8 : len(pre)] == pre[8:]
    shared = {}
    towers = load(old / "upper_station_fit.json")
    donors = load(old / "pull_pad_fit_02.json")
    for donor in ("pullover_machine", "plate_row"):
        rr = wire.read_clip(old / (donor + ".wgm"), cat)[1]
        i = donors[donor]["preceding"]
        for m in donors[donor]["pads"].values():
            j = i + m["records"]
            if m["group"] in ("seat_pad__002", "back_pad__003"):
                ids(m["group"], rr[i:j], shared)
            i = j
    result = {}
    for k, mapping in spec.items():
        raw = load(d / (k + ".json"))
        objs = {o["name"]: o for o in raw["objects"]}
        before = mb["machineOverlays"].get(k, {})
        native = before.get("targets", mb["plateOverlays"].get(k, {}))
        covered = before.get("covered", {})
        path = old / (k + ".wgm")
        prev = wire.read_clip(path, cat)[1] if path.exists() else []
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
            i, g = mapping[n]
            o = raw["objects"][i]
            assert o["name"] == n and m["group"] == g
            rs = layers[n] = rows[off : off + m["records"]]
            off += len(rs)
            for z in rs:
                v = z["world"][0]
                tri = v[z["faces"]]
                assert (
                    z["nf"] == 1
                    and np.isfinite(v).all()
                    and np.linalg.norm(
                        np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1
                    ).min()
                    > 1e-12
                )
            if "axis" not in m:
                assert all(swept_clear(sweep, z["world"][0]) for z in rs), (k, n)
                continue
            ids(g, rs, shared)
            assert len(rs) == 2 and all(z["mat"] == MAT_PAD for z in rs)
            if n == "preacher_pad":
                assert [len(z["faces"]) for z in rs] == [380, 96]
            p, rot, s = object_pose(o)
            orig = vertices(o) * s
            v = np.vstack([a for a, t in cloud(rs)])
            offset = np.array(m.get("offset", [0, 0, 0]))
            local = rot.inv().apply(v - p - offset)
            err = 1000 * abs(bounds(local) - bounds(orig)).max()
            assert err < 0.15, (k, n, err)
            hit = r["pads"][n] = dict(contact_extent_error_mm=err)
            if m.get("axis"):
                axis = np.array(m["axis"])
                assert np.allclose(
                    axis, [0, -1, 0] if n == "tapered_back" else Z
                ) and np.allclose(np.cross(axis, offset), 0)
                gap = 1000 * axial_gap(samples, base, g.split("__")[0], cloud(rs), axis)
                assert 2 <= gap <= 5 and swept_clear(sweep, v), (k, n, gap)
                hit.update(
                    gap_mm=gap, adjust_mm=1000 * (offset @ axis), axis=axis.tolist()
                )
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
        for slider, m in fit[k]["pads"].items():
            for setting in m.get("locks", []):
                r.setdefault("engaged_holes", {})[slider] = engagement(
                    k, objs, layers, slider, setting
                )
        if "pad_post" in layers:
            stand = layers["pad_post"][0]["world"][0]
            assert joined(stand, world(objs["spine"])) and joined(
                stand, layers["preacher_pad"][0]["world"][0]
            )
        if k in towers and "seat" in objs:
            seat = towers[k]["fits"]["seat"]
            p, rot, s = object_pose(objs["seat"])
            pos = p + seat["offset"]
            crown = [
                z
                for z in prev
                if z["nf"] == 1
                and np.allclose(z["pos"][0], pos, atol=0.00001)
                and z["mat"] == MAT_PAD
            ]
            assert len(crown) == 2
            gap = 1000 * axial_gap(
                samples, base, "seat_pad", cloud(crown), rot.apply(Z)
            )
            assert 2 <= gap <= 5 and np.allclose(seat["axis"], Z), (k, gap)
            r["prior_seat_gap_mm"] = gap
            shell, collar, slider, shaft = [z["world"][0] for z in prev[-4:]]
            hole = center(collar)
            lo, hi = slider[:, 2].min(), slider[:, 2].max()
            ix = (hole[2] - lo) / (hi - lo) * 12 - 0.5
            assert (
                0 <= round(ix) < 12
                and abs(ix - round(ix)) < 0.0003
                and lo < hole[2] < hi
            )
            assert (
                np.allclose(center(shaft)[1:], hole[1:], atol=0.0001)
                and shaft[:, 0].min() < hole[0] < shaft[:, 0].max()
            )
            assert shell[:, 2].min() < lo and joined(slider, crown[0]["world"][0])
            assert all(swept_clear(sweep, z["world"][0]) for z in prev[-6:])
            r["prior_seat_hole"] = int(round(ix))
    return dict(
        models=result,
        catalog=[int.from_bytes(pre[4:8], "little"), len(cat)],
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
