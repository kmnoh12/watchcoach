"""Read back the upper-station overlays and verify the installed tracks and V6 clearance."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

import check_app3d_stage1 as wire
from bench_fit import top_gap
from body_fit import contact_region
from upgrade_app3d_press_stations import (
    HERE, PASSAGES, assemble, avatar_at_key_times, check_casting, load, load_source,
    skin_envelope, verify_skin, world, vertices,
)


def connected(a, b):
    return np.all(np.minimum(a.max(0), b.max(0))-np.maximum(a.min(0), b.min(0)) > .0001)


def check_mounts(raw, rows):
    by_name = {o["name"]: o for o in raw["objects"]}
    names = [n for n in rows if n.startswith("return_pulley")]
    if not names:
        return
    first = sorted(names)[0]
    cross, left, right, _ = (r["world"][0] for r in rows[first][3:])
    for end, post in zip((left, right), ("tower_post", "tower_post.001")):
        assert connected(cross, end) and connected(end, world(by_name[post])[0])
    for n in names:
        axle = rows[n][-1]["world"][0]
        wheel = np.vstack([r["world"][0] for r in rows[n][:3]])
        assert connected(axle, cross) and connected(axle, wheel)
        assert np.allclose(rows[n][-1]["pos"][0][[0, 2]], by_name[n]["m"][0][12:15:2], atol=.0001)
    wheel = np.vstack([r["world"][0] for r in rows["stack_pulley"][:3]])
    left, right, axle = (r["world"][0] for r in rows["stack_pulley"][3:])
    cap = rows["tower_cap"][0]["world"][0]
    assert connected(axle, wheel)
    for end in (left, right):
        assert connected(axle, end) and connected(cap, end)


def check(view, baseline):
    data, previous = view/"data", baseline/"data"
    stock, installed = (previous/"parts.bin").read_bytes(), (data/"parts.bin").read_bytes()
    assert installed[8:len(stock)] == stock[8:]
    parts = wire.read_parts(data/"parts.bin")
    manifest, before = load(data/"wgm_manifest.json"), load(previous/"wgm_manifest.json")
    assert manifest["plateOverlays"] == before["plateOverlays"]
    fits = load(data/"press_station_fit.json")
    targets = load(HERE/"press_station_targets.json")
    avatar = load(view/"human_v5/base.json")
    assert avatar["vertices"] == 1401 and (view/"human_v5/watch.json").is_file()
    faces = np.asarray(avatar["triangles"]).reshape(-1, 3)
    source = {**load_source(), **load(HERE/"scene_press_source.json")}
    allowed = {"data/parts.bin", "data/wgm_manifest.json", "data/press_station_fit.json", "v5_bundle_report.json"}
    applied = {k for k, r in fits.items() if "unchanged" not in r}
    assert set(manifest["clips"]) == set(before["clips"]) | applied
    assert set(fits) == set(targets)
    assert {k: v for k, v in manifest["machineOverlays"].items() if k not in applied} == before["machineOverlays"]
    allowed.update(f"data/{k}.wgm" for k in applied)
    untouched = 0
    for path in baseline.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(baseline)
        if rel.as_posix() not in allowed:
            assert path.read_bytes() == (view/rel).read_bytes(), str(rel)
            untouched += 1

    results, casting_ids = {}, set()
    grip_report = load(view/"hand_fit_report.json")
    for key, mapping in targets.items():
        if key not in applied:
            results[key] = fits[key]
            continue
        raw = load(data/f"{key}.json")
        clock, human = avatar_at_key_times(view/"human_v5"/f"{key}.bin", raw["acts"])
        expected, metadata = assemble(raw, mapping, source, human, avatar)
        record = fits[key]
        actions, packed = wire.read_clip(data/f"{key}.wgm", parts)
        assert np.array_equal(actions, np.asarray(raw["acts"], "<f4"))
        assert metadata == record["fits"]
        old_count = record["preceding"]
        if old_count:
            original = (previous/f"{key}.wgm").read_bytes()
            new = (data/f"{key}.wgm").read_bytes()
            assert new[:6] == original[:6] and new[8:len(original)] == original[8:]
        packed = packed[old_count:]
        original = before.get("machineOverlays", {}).get(key, {}).get(
            "targets", before["plateOverlays"].get(key, {})
        )
        overlay = {str(e["index"]): e["name"] for e in expected}
        assert manifest["machineOverlays"][key] == dict(targets={**original, **overlay},
                                                       count=old_count+len(packed))
        assert len(packed) == len(expected) == record["records"]
        skin_rows, grouped = [], defaultdict(list)
        max_pos = max_angle = 0.
        for row, e in zip(packed, expected):
            assert row["nf"] == len(e["pos"])
            assert row["mat"] == e["mat"] and np.array_equal(row["faces"], e["tris"].reshape(-1, 3))
            position = np.linalg.norm(row["pos"] - e["pos"], axis=1).max()
            angle = (Rotation.from_quat(row["quat"]) * Rotation.from_quat(e["quats"]).inv()).magnitude().max()
            assert position < .0001 and angle < .0001 and np.allclose(row["scale"], e["sc"], atol=.0001)
            max_pos, max_angle = max(max_pos, position), max(max_angle, angle)
            skin_rows.append(skin_envelope(dict(e, verts=parts[row["pid"]][0], quats=row["quat"],
                                                 sc=row["scale"], pos=row["pos"])))
            grouped[e["name"]].append(row)
        verify_skin(skin_rows, clock, human, actions, faces)
        check_mounts(raw, grouped)

        obstacles = [(obj, world(raw["objects"][i]), g.startswith(("selector_pin__", "weight_selector__")))
                     for obj, (i, g) in mapping.items() if g.rsplit("__", 1)[0] in PASSAGES]
        gaps = {}
        for name, rows in grouped.items():
            idx, group = mapping[name]
            obj = raw["objects"][idx]
            first = rows[0]
            if group.startswith(("rest_stack_plate__", "selected_stack_plate__")):
                check_casting(first["world"][0], first["faces"], first["pos"], obstacles)
                casting_ids.add(first["pid"])
            if group.startswith(("pulley_wheel__", "pulley_hub__")):
                n = 3 if group.startswith("pulley_wheel__") else 1
                surface = np.vstack([parts[r["pid"]][0]*r["scale"][0] for r in rows[:n]])
                raw_position, _, scale = wire.build.decompose_frames(obj["m"][:1])
                native = vertices(obj)*scale[0]
                assert np.allclose(first["pos"][0], raw_position[0], atol=.0001)
                assert np.allclose(np.ptp(surface[:, 2]), np.ptp(native[:, 2]), atol=.00003)
                assert abs(np.hypot(*surface[:, :2].T).max()-np.hypot(*native[:, :2].T).max()) < .00003
            if group.startswith("seat_pad__"):
                rotation = Rotation.from_quat(first["quat"][0])
                local = [(r["world"][0]-first["pos"][0]) @ rotation.as_matrix() for r in rows[:2]]
                face = np.vstack((first["faces"], rows[1]["faces"]+len(local[0])))
                anatomy, _ = contact_region(avatar, "seat_pad")
                skin = np.einsum("fvi,ij->fvj", human-first["pos"][0], rotation.as_matrix())
                gap = top_gap(skin[:, anatomy].reshape(-1, 3, 3), np.vstack(local), face)
                assert .002 <= gap <= .005
                gaps[name] = gap*1000

        old_tris = sum(len(raw["objects"][int(i)]["tris"])//3 for i in overlay)
        new_tris = sum(len(row["faces"]) for row in packed)
        assert new_tris == record["triangles"]
        before_model = sum(len(o["tris"])//3 for o in raw["objects"])
        if old_count:
            prior_model_tris = sum(len(raw["objects"][int(i)]["tris"])//3 for i in original)
            before_model += sum(len(r["faces"]) for r in wire.read_clip(data/f"{key}.wgm", parts)[1][:old_count])-prior_model_tris
        hand_gaps = [v[0] for g in grip_report.get(key, {}).get("grips", {}).values()
                     for v in g["pad_mm"].values()]
        results[key] = dict(
            originals=len(overlay), static=sum(len(r["pos"]) == 1 for r in expected),
            moving=sum(len(r["pos"]) > 1 for r in expected), triangles=[before_model, before_model-old_tris+new_tris],
            replacement_triangles=[old_tris, new_tris], track_error_mm=1000*max_pos,
            rotation_error_deg=np.degrees(max_angle), skin_sweep_intervals=len(clock)-1,
            skin_overlaps=0, seat_gap_mm=gaps, original_grip_gap_mm=min(hand_gaps, default=None),
            wgm_bytes=(data/f"{key}.wgm").stat().st_size, axes=metadata,
        )
    assert len(casting_ids) <= 1, "All stack plates in the upper batch share one packed casting"
    return dict(models=results, kept_files=untouched, shared_castings=len(casting_ids),
                catalog_bytes=[len(stock), len(installed)], catalog_records=[int.from_bytes(stock[4:8], "little"), len(parts)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", type=Path)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = check(args.view, args.baseline)
    if args.report:
        args.report.write_text(json.dumps(result, indent=2)+"\n")
    print({key: row.get("seat_gap_mm", row.get("unchanged")) for key, row in result["models"].items()})
