"""Check the installed bench batch against its immediate predecessor, including packed tracks."""

import argparse
import json
from pathlib import Path
import struct

import numpy as np
from scipy.spatial.transform import Rotation

import check_app3d_stage1 as wire
from check_app3d_adjust_bench import closed_solid, files
from fixed_pad_contact import penetration
from upgrade_app3d_adjust_bench import HERE, load
from upgrade_app3d_bench_pads import batch_files
from upgrade_app3d_machines import decompose_frames, strip_fake_animation
from part_registry import MAT_PAD, MAT_RUBBER


def check(view, baseline, batch=1):
    data, old, human = view / "data", baseline / "data", view / "human_v5"
    targets_file, report_file = batch_files(batch)
    spec = load(HERE / targets_file)
    fit = load(data / report_file)
    assert fit.keys() == spec.keys()
    src = load(HERE / "scene_flat_bench_source.json")
    mf = load(data / "wgm_manifest.json")
    prev = load(old / "wgm_manifest.json")
    base = load(human / "base.json")
    hands = load(view / "hand_fit_report.json")
    assert base["vertices"] == 1401 and (human / "watch.json").is_file()
    faces = np.array(base["triangles"]).reshape(-1, 3)
    parts = wire.read_parts(data / "parts.bin")
    stock = (old / "parts.bin").read_bytes()
    assert (data / "parts.bin").read_bytes()[8 : len(stock)] == stock[8:]
    f0, f1 = files(baseline), files(view)
    applied = {k for k, x in fit.items() if "pads" in x}
    assert set(mf["clips"]) == set(prev["clips"]) | applied
    assert {k: v for k, v in mf.items() if k not in ("clips", "machineOverlays")} == {
        k: v for k, v in prev.items() if k not in ("clips", "machineOverlays")
    }
    assert {k: v for k, v in mf["machineOverlays"].items() if k not in applied} == {
        k: v for k, v in prev.get("machineOverlays", {}).items() if k not in applied
    }
    changed = {
        str(f)
        for f in f1
        if f not in f0 or (baseline / f).read_bytes() != (view / f).read_bytes()
    }
    assert f0.keys() <= f1.keys()
    # Batch 02 uses the same five upholstery sizes already packed by batch 01.
    # Every record must point back into the existing, byte-identical catalogue.
    if batch == 2:
        assert (data / "parts.bin").read_bytes() == stock
    assert changed - {"v5_bundle_report.json"} == {
        "data/" + k + ".wgm" for k in applied
    } | {"data/wgm_manifest.json", "data/" + report_file} | (
        {"data/parts.bin"} if batch == 1 else set()
    )
    reports = [load(root / "v5_bundle_report.json") for root in [baseline, view]]
    assert {k: v for k, v in reports[0].items() if k != "bytes"} == {
        k: v for k, v in reports[1].items() if k != "bytes"
    }
    diff = {s: f1[Path(s)] - f0.get(Path(s), 0) for s in sorted(changed)}
    report = dict(
        bytes_before=sum(f0.values()),
        bytes_after=sum(f1.values()),
        file_deltas=diff,
        catalog_before=struct.unpack_from("<I", stock, 4)[0],
        catalog_after=len(parts),
        unchanged_files=len(f1) - len(changed),
        clips={},
    )
    groups = {}
    for key, mapping in spec.items():
        if key not in applied:
            report["clips"][key] = {"unchanged": fit[key]["unchanged"]}
            continue
        raw = load(data / (key + ".json"))
        acts, rows = wire.read_clip(data / (key + ".wgm"), parts)
        assert np.array_equal(acts, np.asarray(raw["acts"], "<f4"))
        prefix = fit[key]["preceding"]
        targets = (
            prev.get("machineOverlays", {})
            .get(key, {})
            .get("targets", prev.get("plateOverlays", {}).get(key, {}))
        )
        idx = prefix
        assert mf["machineOverlays"][key] == dict(
            targets={**targets, **{str(i): n for n, (i, g) in mapping.items()}},
            count=len(rows),
        )
        if prefix:
            stock = (old / (key + ".wgm")).read_bytes()
            added = (data / (key + ".wgm")).read_bytes()
            assert (
                stock[:6] == added[:6]
                and stock[8:] == added[8 : len(stock)]
                and struct.unpack_from("<H", stock, 6)[0] == prefix
            )
        else:
            assert key not in prev["clips"]
        frames = wire.build.load_wgp2_human_frames(human / (key + ".bin"))
        times = np.frombuffer(
            (human / (key + ".bin")).read_bytes(), "<f4", len(frames), 40
        )
        assert frames.shape[1:] == (1401, 3) and np.all(np.diff(times) > 0)
        grips = hands[key]["grips"]
        assert not set(mapping) & {g["part"] for g in grips.values()}
        finger = [p[0] for g in grips.values() for p in g["pad_mm"].values()]
        tri = sum(
            len(o["tris"]) // 3
            for i, o in enumerate(raw["objects"])
            if str(i) not in targets
        ) + sum(len(r["faces"]) for r in rows[:idx])
        out = report["clips"][key] = dict(
            poses=len(frames),
            prefix=prefix,
            tris_before=tri,
            pads={},
            finger_mm=min(finger, default=None),
        )
        for name, (i, group) in mapping.items():
            obj = raw["objects"][i]
            assert obj["name"] == name
            info = fit[key]["pads"][name]
            assert info["group"] == group and info["adjustment_axis"] is None
            wrap = group.startswith("hip_pad__")
            layer = rows[idx : idx + (1 if wrap else 3)]
            idx += len(layer)
            ids = tuple(x["pid"] for x in layer)
            assert groups.setdefault(group, ids) == ids
            pos, q, s = decompose_frames(strip_fake_animation(obj["m"]))
            r = layer[0]
            assert r["nf"] == len(pos) == (len(acts) if wrap else 1)
            assert all(
                np.array_equal(x[k], r[k])
                for x in layer
                for k in ["pos", "quat", "scale"]
            )
            assert np.allclose(r["scale"], r["scale"][0])
            assert np.isfinite(r["world"]).all()
            rot = Rotation.from_quat(r["quat"])
            max_angle = np.max((rot * Rotation.from_quat(q).inv()).magnitude())
            assert max_angle < 0.0001
            center_error = np.max(np.linalg.norm(pos - r["pos"], axis=1))
            assert center_error < 0.00011
            v = np.vstack([parts[x["pid"]][0] for x in layer]) * r["scale"][0]
            ov = np.asarray(obj["verts"]).reshape(-1, 3) * s[0]
            if wrap:
                assert info["attachment"] == "bar_shaft" and r["mat"] == MAT_PAD
                shaft = next(o for o in raw["objects"] if o["name"] == "barbell_shaft")
                assert np.allclose(shaft["m"], obj["m"], atol=0.00003)
                closed_solid(v, r["faces"])
                rad = np.linalg.norm(v[:, :2], axis=1)
                shaft_r = np.linalg.norm(
                    np.asarray(shaft["verts"]).reshape(-1, 3)[:, :2], axis=1
                ).max()
                assert (
                    0 < rad.min() - shaft_r < 0.001
                    and len(np.unique(np.round(v[:, 2], 5))) >= 8
                )
                surface_error = max(
                    abs(rad.max() - np.linalg.norm(ov[:, :2], axis=1).max()),
                    np.max(abs(v[:, 2].min() - ov[:, 2].min())),
                    abs(v[:, 2].max() - ov[:, 2].max()),
                )
            else:
                assert info["attachment"] == "fixed_mount" and [
                    x["mat"] for x in layer
                ] == [MAT_PAD, MAT_PAD, MAT_RUBBER]
                role = (
                    "back_pad"
                    if group.startswith("back_pad") or np.ptp(ov[:, 1]) > 0.6
                    else "seat_pad"
                )
                for row, slot in zip(layer, src[role] + src["trim"]):
                    assert np.array_equal(
                        row["faces"].ravel(), slot["t"]
                    ) and np.allclose(
                        np.asarray(row["rgb"]) / 255, slot["rgb"], atol=0.5 / 255
                    )
                # Top and mounting underside planes in local normal + frame origin, not global Z (inclined benches).
                surface_error = max(
                    abs(v.max(0) - ov.max(0)).max(), abs(v.min(0) - ov.min(0)).max()
                )
                assert np.all(v.max(0) > v.min(0))
            assert surface_error < 0.00003
            # Compare old/new in the decoded pose's reference frame. Catch binary drift separately above.
            hit = penetration(frames, faces, times, acts, ov, v, r["pos"], r["quat"])
            assert (
                hit["added_hull_mm"] <= 10
                and abs(hit["added_hull_mm"] - info["collision"]["added_hull_mm"])
                < 0.12
            )
            out["pads"][name] = dict(
                **hit,
                center_mm=round(center_error * 1000, 4),
                surface_mm=round(surface_error * 1000, 4),
                rotation_deg=round(np.degrees(max_angle), 5),
                frames=r["nf"],
            )
            tri += sum(len(x["faces"]) for x in layer) - len(obj["tris"]) // 3
        assert idx == len(rows)
        out["tris_after"] = tri
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("view", type=Path)
    ap.add_argument("baseline", type=Path)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--batch", type=int, choices=(1, 2), default=1)
    args = ap.parse_args()
    result = json.dumps(check(args.view, args.baseline, args.batch), indent=2)
    print(result)
    if args.report:
        args.report.write_text(result + chr(10))
