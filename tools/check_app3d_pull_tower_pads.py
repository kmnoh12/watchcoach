"""Read back only the seven tower pad overlays: contact surfaces, moving carriers and V6 skin."""

import argparse
import json
from pathlib import Path

import numpy as np
import check_app3d_stage1 as wire
from check_app3d_row_pads import files, ids, triangles
from upgrade_app3d_pull_stations import avatar_at_key_times
from upgrade_app3d_pull_tower_pads import HERE, REPORT, TARGETS, center, load
from fixed_pad_contact import penetration
from part_registry import MAT_PAD


def heights(mesh, faces, axis, sign, probes):
    """Ray through each probe against actual cushion triangles (not the bounding box)."""
    tri = mesh[faces]
    xy = np.delete(tri, axis, axis=2)
    a, b, c = xy.transpose(1, 0, 2)
    u, v = b - a, c - a

    def cross(u, v):
        return u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0]

    det = cross(u, v)
    valid = abs(det) > 1e-12
    out = []
    for q in probes:
        s = np.divide(cross(q - a, v), det, where=valid, out=np.zeros(len(a)))
        t = np.divide(cross(u, q - a), det, where=valid, out=np.zeros(len(a)))
        hit = valid & (s >= -1e-8) & (t >= -1e-8) & (s + t <= 1 + 1e-8)
        z = (
            tri[:, 0, axis]
            + s * (tri[:, 1, axis] - tri[:, 0, axis])
            + t * (tri[:, 2, axis] - tri[:, 0, axis])
        )
        assert hit.any(), "no cushion under contact probe"
        out.append((sign * z[hit]).max())
    return np.array(out)


def check(view, baseline):
    d, old, h = view / "data", baseline / "data", view / "human_v5"
    base = load(h / "base.json")
    assert base["vertices"] == 1401 and (h / "watch.json").is_file()
    faces = np.array(base["triangles"]).reshape(-1, 3)
    spec, fit = load(HERE / TARGETS), load(d / REPORT)
    assert spec.keys() == fit.keys() and len(spec) == 7
    passed = {k for k in fit if "pads" in fit[k]}
    first, final = files(baseline), files(view)
    assert first.keys() <= final.keys()
    diff = {
        str(f)
        for f in final
        if f not in first or (view / f).read_bytes() != (baseline / f).read_bytes()
    }
    assert diff - {"v5_bundle_report.json"} == {f"data/{k}.wgm" for k in passed} | {
        "data/" + n for n in (REPORT, "wgm_manifest.json", "parts.bin")
    }
    pre, post = (old / "parts.bin").read_bytes(), (d / "parts.bin").read_bytes()
    assert pre[8:] == post[8 : len(pre)]
    parts = wire.read_parts(d / "parts.bin")
    ma, mb = load(d / "wgm_manifest.json"), load(old / "wgm_manifest.json")
    assert set(ma["clips"]) == set(mb["clips"]) | passed
    assert {**ma, "clips": None, "machineOverlays": None} == {
        **mb,
        "clips": None,
        "machineOverlays": None,
    }
    assert {k: v for k, v in ma["machineOverlays"].items() if k not in passed} == {
        k: v for k, v in mb["machineOverlays"].items() if k not in passed
    }
    shared, models = {}, {}
    # The source geometry for this group first appears on the pullover in the row batch.
    donor = "pullover_machine"
    desc = load(old / "pull_pad_fit_02.json")[donor]
    j = desc["preceding"]
    source = wire.read_clip(old / (donor + ".wgm"), parts)[1]
    for row in desc["pads"].values():
        if row["group"] == "back_pad__003":
            ids(row["group"], source[j : j + row["records"]], shared)
        j += row["records"]
    hands = load(view / "hand_fit_report.json")
    for k, mp in spec.items():
        raw = load(d / (k + ".json"))
        objects = raw["objects"]
        path = old / (k + ".wgm")
        prev = wire.read_clip(path, parts)[1] if path.exists() else []
        prior = mb["machineOverlays"].get(k, {})
        targets = prior.get("targets", mb["plateOverlays"].get(k, {}))
        covered = prior.get("covered", {})
        grips = hands[k]["grips"]
        assert len(grips) == 2
        assert not {s["part"] for s in grips.values()} & mp.keys()
        g = models[k] = dict(
            tris_before=triangles(objects, targets | covered, prev),
            hand_min_mm=min(
                p[0] for side in grips.values() for p in side["pad_mm"].values()
            ),
        )
        if k not in passed:
            g.update(tris_after=g["tris_before"], **fit[k])
            continue
        acts, rows = wire.read_clip(d / path.name, parts)
        assert np.array_equal(acts, np.asarray(raw["acts"], "<f4"))
        if prev:
            oldbytes, blob = path.read_bytes(), (d / path.name).read_bytes()
            assert oldbytes[:6] == blob[:6] and oldbytes[8:] == blob[8 : len(oldbytes)]
        overlay = ma["machineOverlays"][k]
        j = len(prev)
        assert j == fit[k]["preceding"] and overlay["targets"] == targets | {
            str(i): n for n, (i, _) in mp.items()
        }
        assert overlay.get("covered", {}) == covered and overlay["count"] == len(rows)
        clock, skin = avatar_at_key_times(h / (k + ".bin"), acts)
        g.update(
            tris_after=triangles(objects, overlay["targets"] | covered, rows), pads={}
        )
        for n, (i, group) in mp.items():
            m = fit[k]["pads"][n]
            o = objects[i]
            assert o["name"] == n and group == m["group"]
            cushion, stitch = layers = rows[j : j + 2]
            j += 2
            ids(group, layers, shared)
            assert [len(a["faces"]) for a in layers] == [380, 96]
            assert all(a["mat"] == MAT_PAD for a in layers)
            orig = wire.original(o)
            knee = group.startswith("knee_pad")
            nf = len(acts) if knee else 1
            assert len(orig) in (1, len(acts)) and all(a["nf"] == nf for a in layers)
            assert m["adjustment_axis"] is None and m["stroke_axis"] == (
                [0, 0, 1] if knee else None
            )
            for a in layers:
                assert np.isfinite(a["world"]).all() and np.array_equal(
                    a["quat"], np.broadcast_to(a["quat"][0], a["quat"].shape)
                )
                tri = a["world"][0][a["faces"]]
                assert (
                    np.linalg.norm(
                        np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1
                    ).min()
                    > 1e-12
                )
            combined = np.concatenate([a["world"] for a in layers], axis=1)
            env = max(
                abs(getattr(combined, fn)(1) - getattr(orig, fn)(1)).max()
                for fn in ("max", "min")
            )
            assert env < 0.00011, (k, n, env)
            back = group.startswith("back_pad")
            axis, sign = (1, -1) if back else (2, 1)
            half = np.delete(np.ptp(orig[0], axis=0), axis) / 2
            probes = np.delete(center(orig[0]), axis) + half * np.array(
                [[0, 0], [0.55, 0], [-0.55, 0], [0, 0.55], [0, -0.55]]
            )
            ref = heights(
                orig[0], np.array(o["tris"]).reshape(-1, 3), axis, sign, probes
            )
            dev = (
                heights(cushion["world"][0], cushion["faces"], axis, sign, probes) - ref
            )
            contact = np.max(
                abs(
                    dev[:, None]
                    + sign
                    * (
                        cushion["pos"][:, axis]
                        - cushion["pos"][0, axis]
                        - (orig[:, 0, axis] - orig[0, 0, axis])
                    )
                )
            )
            # Keep the central bearing plane locked; a rounded shoulder can recede a few
            # millimetres relative to the old square cushion away from its centre.
            assert abs(dev[0]) < 0.001 and contact < 0.005, (k, n, dev, contact)
            # Decoded translation, not the unquantized input track. Compare old and new
            # skin intrusion in their common carrier frame (envelope error bounded above).
            p = cushion["pos"]
            q = np.tile([0.0, 0.0, 0.0, 1.0], (nf, 1))
            hit = penetration(
                skin, faces, clock, acts, orig[0] - p[0], combined[0] - p[0], p, q
            )
            assert hit["added_hull_mm"] <= 10
            g["pads"][n] = dict(
                **hit,
                frames=nf,
                bounds_error_mm=round(env * 1000, 4),
                contact_error_mm=round(contact * 1000, 4),
                stroke_mm=m["stroke_mm"],
            )
        assert j == len(rows) == len(prev) + fit[k]["records"]
    return dict(
        models=models,
        shared=shared,
        bytes=[sum(first.values()), sum(final.values())],
        catalog=[int.from_bytes(pre[4:8], "little"), len(parts)],
        deltas=sorted(diff),
        unchanged=len(final) - len(diff),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", type=Path)
    parser.add_argument("baseline", type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.view, args.baseline), indent=2))
