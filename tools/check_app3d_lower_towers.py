"""Read back the lower-tower WGM2 overlays and verify their mechanical and body clearance."""

import argparse
from collections import defaultdict
import json
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

import check_app3d_stage1 as wire
from upgrade_app3d_lower_towers import ADJUSTABLE, HERE, UPPER_SHEAVES, assemble, fit_support, load, sources
from bench_fit import swept_clear, top_gap
from body_fit import SkinSweep, contact_region


def projected_clear(triangles, probe):
    """Separating-axis test for a projected solid against an unobstructed bore."""
    footprint = probe[ConvexHull(probe).vertices]
    close = ((triangles.min(1) < probe.max(0)) & (triangles.max(1) > probe.min(0))).all(1)
    for tri in triangles[close]:
        edge = np.roll(tri, -1, axis=0) - tri
        if abs(np.linalg.det(edge[:2])) < 1e-13:
            continue
        normals = np.vstack((edge, np.roll(footprint, -1, axis=0) - footprint))[:, ::-1] * [-1, 1]
        a, b = tri @ normals.T, footprint @ normals.T
        if not np.any(a.max(0) <= b.min(0) + 1e-12) and not np.any(b.max(0) <= a.min(0) + 1e-12):
            return False
    return True


def check_stack(key, raw, casting, old, hardware):
    cast = casting["world"][0] - casting["pos"][0]
    triangles = casting["faces"]
    assert np.allclose(casting["quat"], casting["quat"][0])
    upside = Rotation.from_quat(casting["quat"][0]).apply([0, 0, 1])
    assert np.allclose(upside, [0, 0, 1], atol=1e-6)
    assert np.allclose(casting["pos"][:, :2], casting["pos"][0, :2])
    old_center = (old.min(1) + old.max(1)) / 2
    assert np.allclose(casting["pos"], old_center, rtol=0, atol=0.00008)
    assert np.allclose(cast.min(0), old[0].min(0) - old_center[0], rtol=0, atol=0.00003)
    assert np.allclose(cast.max(0), old[0].max(0) - old_center[0], rtol=0, atol=0.00003)
    colliding = []
    for obj in hardware:
        name = obj["name"].split(".")[0]
        probe = wire.original(obj)
        if name.startswith(("weight_guide", "guide", "stack_guide")) or name in ("selector_rod", "selector_stem", "selector_lift_rod"):
            assert np.allclose(probe[:, :, :2], probe[0, :, :2], atol=1e-6)
            footprint = probe[0, :, :2] - casting["pos"][0, :2]
            if not projected_clear(cast[triangles][:, :, :2], footprint):
                colliding.append(name)
        else:
            width, depth = (1, 0) if key == "torso_rotation_machine" else (0, 1)
            # Test where the part actually enters the casting envelope, with the original
            # selector's real placement and motion. Never translate a pin to every plate center.
            xy = probe[0, :, :2] - casting["pos"][0, :2]
            assert np.allclose(probe[:, :, :2], probe[0, :, :2], atol=1e-6)
            if xy[:, depth].max() <= cast[:, depth].min() or xy[:, depth].min() >= cast[:, depth].max():
                continue
            zip_grid = lambda n: raw["acts"] if n == len(raw["acts"]) else np.linspace(0, 1, n)
            times = np.union1d(zip_grid(len(probe)), zip_grid(len(casting["pos"])))
            pin_z = np.interp(times, zip_grid(len(probe)), probe[:, 0, 2])
            plate_z = np.interp(times, zip_grid(len(casting["pos"])), casting["pos"][:, 2])
            zs = np.unique(np.round(pin_z - plate_z, 6))
            local_z = probe[0, :, 2] - probe[0, 0, 2]
            # Only the tip reaches the plate for the common wide-selector head.
            if name == "selector":
                tip_sign = np.sign(-xy[:, depth].mean())
                tip = tip_sign * xy[:, depth] >= cast[:, depth].min() - 0.00005
            else:
                tip = np.ones(len(xy), dtype=bool)
            for z in zs:
                if local_z.max() + z <= cast[:, 2].min() or local_z.min() + z >= cast[:, 2].max():
                    continue
                if not projected_clear(cast[triangles][:, :, [width, 2]],
                                       np.column_stack((xy[tip, width], local_z[tip] + z))):
                    colliding.append(name)
                    break
    return colliding


def check_upper_mount(objects, grouped, key):
    indices = {o["name"]: i for i, o in enumerate(objects)}
    _, span, riser = (p["world"][0] for p in grouped[indices["pulley_bracket"]])
    cap = grouped[indices["tower_cap"]][0]["world"][0]

    def contact(a, b):
        return np.minimum(a.max(0), b.max(0)) - np.maximum(a.min(0), b.min(0))

    assert (contact(cap, riser) > 0.005).all()
    assert (contact(riser, span) > 0.005).all()
    hubs = [rows[0]["world"][0] for i, rows in grouped.items()
            if objects[i]["name"].startswith("pulley_hub")]
    for name in UPPER_SHEAVES[key]:
        axle = np.asarray(objects[indices[name]]["m"][0][12:15])
        hub = min(hubs, key=lambda v: np.linalg.norm((v.min(0) + v.max(0)) / 2 - axle))
        assert (contact(span, hub) > 0.001).all(), f"{key}/{name}: mount misses the axle"
    cables = [wire.original(obj).reshape(-1, 3) for obj in objects if obj["name"].startswith("cable")]
    assert all(contact(part, cable).min() < -0.001 for part in (span, riser) for cable in cables)


def check(view):
    d, h = view / "data", view / "human_v5"
    base = load(h / "base.json")
    assert base["vertices"] == 1401 and (h / "watch.json").is_file()
    faces = np.asarray(base["triangles"]).reshape(-1, 3)
    catalog = wire.read_parts(d / "parts.bin")
    targets = load(HERE / "lower_tower_targets.json")
    manifest = load(d / "wgm_manifest.json")
    fits = load(d / "lower_tower_fit.json")
    hand_report = load(view / "hand_fit_report.json")
    assert "leg_press_horizontal" not in manifest["clips"]
    source = sources()
    report, shared_ids, failures = [], {}, []
    for key, slots in targets.items():
        raw = load(d / f"{key}.json")
        acts, rows = wire.read_clip(d / f"{key}.wgm", catalog)
        hf = h / f"{key}.bin"
        human = wire.build.load_wgp2_human_frames(hf)
        assert human.shape[1] == 1401
        ht = np.frombuffer(hf.read_bytes(), "<f4", len(human), 40)
        times = np.union1d(ht, acts)
        intervals = np.searchsorted(ht, times, side="right").clip(1, len(human) - 1)
        alpha = ((times - ht[intervals - 1]) / (ht[intervals] - ht[intervals - 1])).clip(0, 1)[:, None, None]
        skin = human[intervals - 1] + alpha * (human[intervals] - human[intervals - 1])
        skin_lo, skin_hi = skin.min((0, 1)), skin.max((0, 1))
        fixed_sweep = SkinSweep(skin, faces)
        assert np.array_equal(acts, np.asarray(raw["acts"], dtype=np.float32))
        expected = assemble(key, raw, slots, source)
        if key in ADJUSTABLE and "exception" not in fits[key]:
            additional, fit = fit_support(key, raw, source, human, base)
            expected.extend(additional)
            assert fit == fits[key]
        grouped = defaultdict(list)
        objects = raw["objects"]
        replacements = {str(e["index"]): objects[e["index"]]["name"] for e in expected}
        assert manifest["machineOverlays"][key] == dict(targets=replacements, count=len(rows))
        assert len(rows) == len(expected) and key in manifest["clips"]
        hardware = [o for o in objects if o["name"].split(".")[0] in {
            "guide", "stack_guide", "weight_guide", "selector_stem", "selector_rod",
            "selector_lift_rod", "selector", "selector_pin",
        }]
        max_mm = 0.0
        for built, row in zip(expected, rows):
            i = built["index"]
            group = slots[str(i)][1] if str(i) in slots else objects[i]["name"]
            layer = len(grouped[i])
            grouped[i].append(row)
            assert shared_ids.setdefault((group, layer), row["pid"]) == row["pid"] or (
                built["name"].endswith("stack_plate") and layer > 0
            ), f"{key}/{objects[i]['name']}: group geometry differs"
            assert row["nf"] == len(built["pos"])
            mm = 1000 * np.linalg.norm(row["pos"] - built["pos"], axis=1).max()
            max_mm = max(max_mm, mm)
            assert mm < 0.1 and np.allclose(row["scale"], built["sc"], rtol=0, atol=0.00008)
            assert (Rotation.from_quat(row["quat"]).inv() * Rotation.from_quat(built["quats"])).magnitude().max() < 0.00008
            assert np.array_equal(row["faces"].ravel(), built["tris"])
            mesh = row["world"][0] - row["pos"][0]
            assert np.allclose(row["quat"], row["quat"][0]) and np.allclose(row["scale"], row["scale"][0])
            lo = mesh.min(0) + row["pos"].min(0)
            hi = mesh.max(0) + row["pos"].max(0)
            near = ((skin_hi >= lo) & (skin_lo <= hi)).all()
            # Decal layers are planar and covered by the casting's conservative envelope.
            if near and not (layer and built["name"].endswith("stack_plate")):
                if row["nf"] == 1:
                    clear = swept_clear(fixed_sweep, row["world"][0])
                else:
                    grid = acts if row["nf"] == len(acts) else np.linspace(0, 1, row["nf"])
                    motion = np.column_stack([np.interp(times, grid, p) for p in row["pos"].T])
                    clear = swept_clear(SkinSweep(skin - motion[:, None, :], faces), mesh)
                if not clear:
                    failures.append(f"{key}/{objects[i]['name']} layer {layer}: V6 overlap")
            if built["name"].endswith("stack_plate") and layer == 0:
                failures.extend(f"{key}/{objects[i]['name']}: obstructed {part}" for part in
                                check_stack(key, raw, row, wire.original(objects[i]), hardware))
        if key in UPPER_SHEAVES:
            check_upper_mount(objects, grouped, key)
        if key in ADJUSTABLE and "exception" not in fits[key]:
            fit = fits[key]
            pads = grouped[next(i for i, obj in enumerate(objects) if obj["name"] == fit["part"])]
            axis = np.asarray(fit["axis"]) * (-1 if ADJUSTABLE[key][3] else 1)
            basis = np.stack(([1, 0, 0], np.cross(axis, [1, 0, 0]), axis))
            verts = np.vstack([p["world"][0] for p in pads])
            offsets = np.cumsum([0] + [p["world"].shape[1] for p in pads[:-1]])
            tris = np.vstack([p["faces"] + i for i, p in zip(offsets, pads)])
            contact, _ = contact_region(base, fit["anatomy"])
            local = np.einsum("fvi,ji->fvj", skin, basis)
            gap = top_gap(local[:, contact].reshape(-1, 3, 3), verts @ basis.T, tris)
            assert 0.002 <= gap <= 0.005, (key, gap)
            fit["decoded_gap_mm"] = round(1000 * gap, 4)
        old = sum(len(o["tris"]) // 3 for o in objects)
        removed = sum(len(objects[i]["tris"]) // 3 for i in grouped)
        new = sum(len(row["faces"]) for row in rows)
        pad = [x[0] for g in hand_report[key]["grips"].values() for x in g["pad_mm"].values()]
        report.append(dict(model=key, replaced=len(grouped), old_tri=old, new_tri=old-removed+new,
                           error_mm=max_mm, sweep_intervals=len(times)-1,
                           hand_gap_mm=min(pad, default=None), fit=fits.get(key)))
    assert not failures, "\n".join(failures)
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("view", type=Path)
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    rows = check(args.view)
    if args.report:
        args.report.write_text(json.dumps(rows, indent=2) + "\n")
    print(f"{len(rows)} clips, {sum(x['replaced'] for x in rows)} replaced objects, mechanics and V6 skin clear")
