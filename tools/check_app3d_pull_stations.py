"""Check tower overlays from the actual phone WGC2/WGM2 bytes and preceding bundle."""

import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

import check_app3d_stage1 as wire
from body_fit import fit_body_part
from upgrade_app3d_pull_stations import (
    HERE, PASSAGES, PIN_ROLES, assemble, avatar_at_key_times, check_passages, load, load_source, verify_skin, world,
)


def check(view, baseline, *, targets_file="pull_station_targets.json", report_file="pull_station_fit.json",
          source_loader=load_source, build_model=assemble):
    data, old, human = view/"data", baseline/"data", view/"human_v5"
    avatar = load(human/"base.json")
    assert avatar["vertices"] == 1401 and (human/"watch.json").is_file()
    faces = np.asarray(avatar["triangles"]).reshape(-1, 3)
    hand = load(view/"hand_fit_report.json")
    stock, final = (old/"parts.bin").read_bytes(), (data/"parts.bin").read_bytes()
    assert final[8:len(stock)] == stock[8:]
    catalog = wire.read_parts(data/"parts.bin")
    before, manifest = load(old/"wgm_manifest.json"), load(data/"wgm_manifest.json")
    targets = load(HERE/targets_file)
    fit = load(data/report_file)
    assert set(fit) == set(targets)
    passed = {k for k, v in fit.items() if "fits" in v}
    assert set(manifest["clips"]) == set(before["clips"]) | passed
    assert {k: v for k, v in manifest["machineOverlays"].items() if k not in passed} == before["machineOverlays"]
    assert {k: v for k, v in manifest.items() if k not in {"clips", "machineOverlays"}} == {
        k: v for k, v in before.items() if k not in {"clips", "machineOverlays"}
    }
    old_files = {p.relative_to(baseline): p.stat().st_size for p in baseline.rglob("*") if p.is_file()}
    new_files = {p.relative_to(view): p.stat().st_size for p in view.rglob("*") if p.is_file()}
    assert old_files.keys() <= new_files.keys()
    changes = {p.as_posix() for p in new_files
               if p not in old_files or (view/p).read_bytes() != (baseline/p).read_bytes()}
    expected = {f"data/{key}.wgm" for key in passed} | {
        "data/parts.bin", "data/wgm_manifest.json", f"data/{report_file}",
    }
    assert changes - {"v5_bundle_report.json"} == expected, changes ^ expected

    source = source_loader()
    report = {}
    groups = {}
    for key, mapping in targets.items():
        if key not in passed:
            report[key] = fit[key]
            continue
        raw = load(data/f"{key}.json")
        objects = raw["objects"]
        acts, decoded = wire.read_clip(data/f"{key}.wgm", catalog)
        assert np.array_equal(acts, np.asarray(raw["acts"], "<f4"))
        clock, skin = avatar_at_key_times(human/f"{key}.bin", acts)
        plan, fits = build_model(key, raw, mapping, source, skin, avatar)
        assert fits == fit[key]["fits"]
        slots = {str(e["index"]): e["name"] for e in plan}
        assert manifest["machineOverlays"][key] == dict(targets=slots, count=len(decoded))
        assert len(plan) == len(decoded) == fit[key]["records"]
        obstacles = [(name, world(objects[idx]), group.rsplit("__", 1)[0] in PIN_ROLES)
                     for name, (idx, group) in mapping.items()
                     if group.rsplit("__", 1)[0] in PASSAGES]
        real = []
        pads = {name: [] for name in fits}
        counts = Counter()
        track_error = 0
        for entry, row in zip(plan, decoded):
            v, t = catalog[row["pid"]]
            assert np.array_equal(t.ravel(), entry["tris"])
            assert np.allclose(v, entry["verts"], atol=.00002, rtol=0)
            assert row["nf"] == len(entry["pos"])
            assert np.allclose(row["quat"], entry["quats"], atol=.00003, rtol=0)
            assert np.allclose(row["scale"], entry["sc"], atol=.00005, rtol=0)
            track_error = max(track_error, np.linalg.norm(row["pos"]-entry["pos"], axis=1).max())
            assert track_error < .00009
            role = entry["group"].rsplit("__", 1)[0]
            if role.endswith("stack_plate") and entry["mat"] == 1:
                groups.setdefault("stack_casting", row["pid"])
                assert groups["stack_casting"] == row["pid"]
                check_passages(row["world"][0], t, row["pos"], obstacles)
            if role in ("pulley_wheel", "pulley_hub", "pulley_bracket") and not entry["contact"]:
                lookup = entry["group"], row["mat"]
                assert groups.setdefault(lookup, row["pid"]) == row["pid"]
            if entry["name"] in pads and entry["mat"] in (4, 6) and entry["smooth"]:
                pads[entry["name"]].append((row["world"][0], t))
            counts["moving" if row["nf"] > 1 else "static"] += 1
            real.append(dict(name=entry["name"], verts=v, pos=row["pos"], quats=row["quat"], sc=row["scale"]))
        verify_skin(real, clock, skin, acts, faces)
        clearances = {}
        for name, surfaces in pads.items():
            surface = np.vstack([v for v, _ in surfaces])
            spec = fits[name]
            normal, across = np.array(spec["normal"]), np.array(spec["across"])
            center = np.array(spec["origin"]) + spec["offset"]
            if spec.get("gap_method") == "axial_surface":
                from pull_pad_fit import axial_gap
                gap = 1000 * axial_gap(skin, avatar, spec["role"], surfaces, -normal)
            elif spec.get("gap_method") == "vertical_surface":
                from pull_pad_fit import vertical_gap
                gap = 1000 * vertical_gap(skin, avatar, spec["role"], surfaces)
            else:
                target = fit_body_part(skin, avatar, spec["role"], center, surface, normal, across)
                gap = (.0035-np.dot(target-center, normal))*1000
            assert 2 <= gap <= 5, (name, gap)
            clearances[name] = gap

        old_tri = sum(len(o["tris"])//3 for o in objects)
        removed = sum(len(objects[int(idx)]["tris"])//3 for idx in slots)
        inserted = sum(len(r["faces"]) for r in decoded)
        contact = [p[0] for g in hand[key]["grips"].values() for p in g["pad_mm"].values()]
        report[key] = dict(objects=len(slots), **counts, intervals=len(clock)-1,
                           old_tri=old_tri, new_tri=old_tri-removed+inserted,
                           track_mm=track_error*1000, clearance_mm=clearances,
                           hand_min_mm=min(contact, default=None))
    return dict(
        clips=report, skin_penetrations=0, unchanged_files=len(new_files)-len(changes),
        catalog_before=int.from_bytes(stock[4:8], "little"), catalog_after=len(catalog),
        bytes_before=sum(old_files.values()), bytes_after=sum(new_files.values()),
        byte_delta_by_file={p: new_files[Path(p)]-old_files.get(Path(p), 0) for p in sorted(changes)},
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", type=Path)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--upper", action="store_true", help="check the upper-station batch")
    args = parser.parse_args()
    if args.upper:
        import upgrade_app3d_upper_stations as upper

        report = check(args.view, args.baseline, targets_file=upper.TARGETS, report_file=upper.REPORT,
                       source_loader=upper.load_source, build_model=upper.build_model)
    else:
        report = check(args.view, args.baseline)
    log = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.write_text(log)
    else:
        print(log, end="")
