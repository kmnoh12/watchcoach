"""Append just the reviewed cable-station overlays to a fresh stage1+plates bundle.
Existing catalogue records / WGM2 files retain their IDs and exact bytes. Other equipment,
including the adjustable trolley, detents, outlet, pin and hand contacts, stays in JSON.
"""

import argparse
import json
from pathlib import Path
import struct

import numpy as np
from scipy.spatial.transform import Rotation

from upgrade_app3d_machines import PartCatalogPacker, decompose_frames, pack_clip, strip_fake_animation
from upgrade_app3d_adjust_bench import catalog_records
from part_registry import MAT_ACCENT, MAT_CHROME, MAT_FRAME, MAT_RUBBER, MAT_SELECTOR_WINDOW, MAT_SILVER
from scene_lat_parts import build_stickers, palette

HERE = Path(__file__).resolve().parent / "viewer3d"


def load_batch(batch):
    target_file = {
        1: "cable_tower_targets.json",
        2: "cable_tower_targets_02.json",
        3: "cable_tower_03_targets.json",
    }[batch]
    targets = json.loads((HERE / target_file).read_text())
    source = json.loads((HERE / "scene_cable_source.json").read_text())
    if batch == 2:
        source.update(json.loads((HERE / "scene_cable_thin_source.json").read_text()))
    if batch == 3:
        source.update(json.loads((HERE / "scene_cable_mount_source.json").read_text()))
    return targets, source


def assemble(raw, targets, source, batch=1):
    objects = raw["objects"]
    groups = {int(i): g.split("__")[0] for i, (n, g) in targets.items()}
    for i, (name, group) in targets.items():
        assert objects[int(i)]["name"] == name, "Stale cable-tower role map: " + name
    plates = sorted(
        (i for i, g in groups.items() if g.endswith("stack_plate")), key=lambda i: -objects[i]["m"][0][14]
    )
    # Each station has its own top-to-bottom sequence, even when the stacks share a model.
    plate_rows = {}
    stacks = {}
    for idx in plates:
        xy = tuple(np.round(objects[idx]["m"][0][12:14], 3)) if batch != 1 else ()
        plate_rows[idx] = stacks.get(xy, 0)
        stacks[xy] = plate_rows[idx] + 1
    station_covers = {}
    if batch == 2:
        covers = [i for i, g in groups.items() if g == "shroud_panel"]
        for i in plates:
            xy = np.asarray(objects[i]["m"][0][12:14])
            station_covers[i] = min(
                covers, key=lambda j: np.linalg.norm(xy - objects[j]["m"][0][12:14])
            )
    wheels = [np.asarray(objects[i]["m"][0][12:15]) for i, g in groups.items() if g == "pulley_wheel"]
    colors = palette()
    entries = []
    for idx, role in groups.items():
        obj = objects[idx]
        v = np.asarray(obj["verts"]).reshape(-1, 3)
        size = np.ptp(v, axis=0)
        assert np.max(abs(v.min(0) + v.max(0))) < 0.0001
        mats = strip_fake_animation(obj["m"])
        pos, q, scale = decompose_frames(mats)
        assert np.allclose(scale, 1, atol=0.00005)

        def put(vv, tt, mat, color, factor=(1, 1, 1), offset=(0, 0, 0), rotation=q):
            entries.append(
                dict(
                    index=idx,
                    name=role,
                    verts=vv,
                    tris=tt,
                    mat=mat,
                    color=color,
                    smooth=False,
                    pos=pos + offset,
                    quats=rotation,
                    sc=scale * factor,
                )
            )

        if role.endswith("stack_plate"):
            rotation = Rotation.from_quat(q)
            if batch == 3:
                assert np.allclose(rotation.apply([0, 0, 1]), [0, 0, 1], atol=1e-5)
            elif batch == 2:
                # The reverse stations are rotated 180 degrees about the vertical guides.
                assert np.allclose(q[:, :2], 0) and np.allclose(q[:, 2] * q[:, 3], 0)
            else:
                assert np.allclose(q, [0, 0, 0, 1])
            wide = targets[str(idx)][1].endswith("__001")
            factor = size / [0.34, 0.28, 0.075]
            casting = "stack_wide_socket" if wide else "stack_round_socket"
            if wide and station_covers:
                casting = "stack_thin_socket"
            (p,) = source[casting]
            put(p["v"], p["t"], MAT_FRAME, colors["casting"], factor)
            # Scene convention (not training load). Use a single native decal size on all plates.
            label_q = q
            label_offset = rotation.apply([0, (0.28 - size[1]) / 2, 0])
            if batch == 2:
                cover = station_covers[idx]
                front = -np.sign(objects[cover]["m"][0][13] - pos[0, 1])
                assert front != 0
                label_q = np.broadcast_to([0, 0, 0, 1] if front < 0 else [0, 0, 1, 0], q.shape)
                label_offset = [0, -front * (0.28 - size[1]) / 2, 0]
            kg = 2.5 + 5 * plate_rows[idx]
            for sp in build_stickers(0.34, 0.28, 0.075, kg, round(kg * 2.20462262)):
                vv = sp.verts.copy()
                # Leave the largest pin socket clear. Plate depth is an instance offset,
                # not another copy of each number in the shared geometry catalogue.
                vv[:, 0] += 0.013 * np.sign(vv[:, 0])
                put(
                    vv, sp.tris, sp.mat_preset, sp.color,
                    offset=label_offset, rotation=label_q,
                )
        elif role == "pulley_wheel":
            r = np.hypot(v[:, 0], v[:, 1]).max()
            f = [r / 0.074, r / 0.074, size[2] / 0.027]
            mats = [MAT_ACCENT, MAT_RUBBER, MAT_CHROME]
            rgb = [[0.95, 0.72, 0.04], colors["grip"], colors["steel"]]
            for s in source[role]:
                slot = s["slot"]
                put(s["v"], s["t"], mats[slot], rgb[slot], f)
        elif role == "pulley_hub":
            (p,) = source[role]
            dims = np.ptp(p["v"], axis=0)
            diam = 2 * np.hypot(v[:, 0], v[:, 1]).max()
            put(
                p["v"],
                p["t"],
                MAT_CHROME,
                colors["steel"],
                [diam / dims[0], diam / dims[0], size[2] / dims[2]],
            )
        elif role == "pulley_fork":
            assert len(pos) == 1
            axle = min(wheels, key=lambda w: np.linalg.norm(w - pos[0]))
            delta = axle - pos[0]
            if batch == 3:
                assert np.allclose(Rotation.from_quat(q[0]).inv().apply(delta), [0, -0.030, 0.090], atol=0.001)
            else:
                assert np.allclose(q, [0, 0, 0, 1])
                assert np.allclose(delta, [0, -0.030, 0.090], atol=0.001)
            # Both cheeks straddle the wheel, bolt centres coaxial; rear ends engage the existing carriage.
            (p,) = source[role]
            put(p["v"], p["t"], MAT_SILVER, colors["silver"], [1.34, 1.35, 1], delta)
        elif role == "cable_mount":
            # The kickback outlet arm ends below the axle. Use the inboard
            # cheek of the existing scene fork as a cantilever axle mount.
            assert len(pos) == 1 and np.allclose(q, [0, 0, 0, 1])
            put(v, obj["tris"], MAT_SILVER, obj["color"])
            axle = max(wheels, key=lambda w: w[0])
            assert np.allclose(axle - pos[0], [0.225, -0.07, 0.06], atol=0.001)
            (p,) = source["pulley_fork"]
            fv = np.asarray(p["v"])
            ft = np.asarray(p["t"]).reshape(-1, 3)
            inboard = fv[:, 0] < 0
            assert np.array_equal(inboard[ft].any(1), inboard[ft].all(1))
            indices, triangles = np.unique(ft[inboard[ft].all(1)], return_inverse=True)
            cheek = fv[indices]
            # Extend toward the supporting arm while keeping the exposed tip within the wheel profile.
            cheek[:, 1] *= np.where(cheek[:, 1] > 0, 2.2, 0.85)
            put(
                cheek, triangles.ravel(), MAT_SILVER, colors["silver"], [1.34, 1, 1],
                axle - pos[0], Rotation.from_euler("x", [-60], degrees=True).as_quat(),
            )
        elif role in ("pulley_bracket", "pulley_support"):
            (p,) = source["pulley_bracket"]
            put(p["v"], p["t"], MAT_SILVER, colors["silver"], size / np.ptp(p["v"], axis=0))
        elif role == "shroud_panel":
            (p,) = source[role]
            put(
                p["v"], p["t"], MAT_SELECTOR_WINDOW, [0.16, 0.18, 0.22], [size[0] / 0.330, 1, size[2] / 0.568]
            )
        else:
            raise ValueError("Unexpected role " + role)
    return entries


def append_batch(view, batch=1):
    d = view / "data"
    manifest = json.loads((d / "wgm_manifest.json").read_text())
    base = (d / "parts.bin").read_bytes()
    magic, n = struct.unpack_from("<4sI", base)
    assert magic == b"WGC2"
    targets, source = load_batch(batch)
    assert not set(targets) & set(manifest["clips"]), "Append to the preceding catalogue, not a second time"
    packer = PartCatalogPacker()
    clips = {}
    overlays = {}
    entries_by_model = {}
    for model, slots in targets.items():
        raw = json.loads((d / (model + ".json")).read_text())
        entries = assemble(raw, slots, source, batch)
        for e in entries:
            e["part_id"] = packer.add(e["verts"], e["tris"], e["smooth"])
        entries_by_model[model] = (raw["acts"], entries)
        overlays[model] = dict(targets={i: x[0] for i, x in slots.items()}, count=len(entries))
    # Reuse identical records from earlier overlays without changing any installed IDs.
    installed = {record: i for i, record in enumerate(catalog_records(base))}
    new_records, remap = [], []
    for record in catalog_records(packer.build_bytes()):
        if record not in installed:
            installed[record] = n + len(new_records)
            new_records.append(record)
        remap.append(installed[record])
    for model, (acts, entries) in entries_by_model.items():
        for entry in entries:
            entry["part_id"] = remap[entry["part_id"]]
        clips[model], _, _ = pack_clip(model, acts, entries)
    for m, b in clips.items():
        (d / (m + ".wgm")).write_bytes(b)
    (d / "parts.bin").write_bytes(
        struct.pack("<4sI", magic, n + len(new_records)) + base[8:] + b"".join(new_records)
    )
    manifest.setdefault("machineOverlays", {}).update(overlays)
    manifest["clips"] = sorted(set(manifest["clips"]) | set(clips))
    (d / "wgm_manifest.json").write_text(json.dumps(manifest, separators=(",", ":")))
    print(
        f"{len(clips)} cable overlays, {sum(map(len, clips.values()))} bytes, {len(new_records)} additional shared parts"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", type=Path)
    batch_options = parser.add_mutually_exclusive_group()
    batch_options.add_argument("--batch", type=int, choices=(1, 2, 3), default=1)
    batch_options.add_argument("--batch-03", dest="batch", action="store_const", const=3)
    args = parser.parse_args()
    append_batch(args.view, args.batch)
