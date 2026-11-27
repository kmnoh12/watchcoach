"""Append just the reviewed cable-station overlays to a fresh stage1+plates bundle.
Existing catalogue records / WGM2 files retain their IDs and exact bytes. Other equipment,
including the adjustable trolley, detents, outlet, pin and hand contacts, stays in JSON.
"""

import argparse
import json
from pathlib import Path
import struct

import numpy as np

from upgrade_app3d_machines import PartCatalogPacker, decompose_frames, pack_clip, strip_fake_animation
from part_registry import MAT_ACCENT, MAT_CHROME, MAT_FRAME, MAT_RUBBER, MAT_SELECTOR_WINDOW, MAT_SILVER
from scene_lat_parts import build_stickers, palette

HERE = Path(__file__).resolve().parent / "viewer3d"


def assemble(raw, targets, source):
    objects = raw["objects"]
    groups = {int(i): g.split("__")[0] for i, (n, g) in targets.items()}
    for i, (name, group) in targets.items():
        assert objects[int(i)]["name"] == name, "Stale cable-tower role map: " + name
    plates = sorted(
        (i for i, g in groups.items() if g.endswith("stack_plate")), key=lambda i: -objects[i]["m"][0][14]
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

        def put(vv, tt, mat, color, factor=(1, 1, 1), offset=(0, 0, 0), smooth=False):
            entries.append(
                dict(
                    index=idx,
                    name=role,
                    verts=vv,
                    tris=tt,
                    mat=mat,
                    color=color,
                    smooth=smooth,
                    pos=pos + offset,
                    quats=q,
                    sc=scale * factor,
                )
            )

        if role.endswith("stack_plate"):
            assert np.allclose(q, [0, 0, 0, 1])
            wide = targets[str(idx)][1].endswith("__001")
            factor = size / [0.34, 0.28, 0.075]
            (p,) = source["stack_wide_socket" if wide else "stack_round_socket"]
            put(p["v"], p["t"], MAT_FRAME, colors["casting"], factor)
            # Scene convention (not training load). Use a single native decal size on all plates.
            kg = 2.5 + 5 * plates.index(idx)
            for sp in build_stickers(0.34, 0.28, 0.075, kg, round(kg * 2.20462262)):
                vv = sp.verts.copy()
                # Leave the largest pin socket clear. Plate depth is an instance offset,
                # not another copy of each number in the shared geometry catalogue.
                vv[:, 0] += 0.013 * np.sign(vv[:, 0])
                put(vv, sp.tris, sp.mat_preset, sp.color, offset=[0, (0.28 - size[1]) / 2, 0])
        elif role == "pulley_wheel":
            r = np.hypot(v[:, 0], v[:, 1]).max()
            f = [r / 0.074, r / 0.074, size[2] / 0.027]
            mats = [MAT_ACCENT, MAT_RUBBER, MAT_CHROME]
            rgb = [[0.95, 0.72, 0.04], colors["grip"], colors["steel"]]
            for s in source[role]:
                slot = s["slot"]
                put(s["v"], s["t"], mats[slot], rgb[slot], f, smooth=False)
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
            assert len(pos) == 1 and np.allclose(q, [0, 0, 0, 1])
            axle = min(wheels, key=lambda w: np.linalg.norm(w - pos[0]))
            delta = axle - pos[0]
            assert np.allclose(delta, [0, -0.030, 0.090], atol=0.001)
            # Both cheeks straddle the wheel, bolt centres coaxial; rear ends engage the existing carriage.
            (p,) = source[role]
            put(p["v"], p["t"], MAT_SILVER, colors["silver"], [1.34, 1.35, 1], delta)
        elif role == "shroud_panel":
            (p,) = source[role]
            put(
                p["v"], p["t"], MAT_SELECTOR_WINDOW, [0.16, 0.18, 0.22], [size[0] / 0.330, 1, size[2] / 0.568]
            )
        else:
            raise ValueError("Unexpected role " + role)
    return entries


def append_batch(view):
    d = view / "data"
    manifest = json.loads((d / "wgm_manifest.json").read_text())
    base = (d / "parts.bin").read_bytes()
    magic, n = struct.unpack_from("<4sI", base)
    assert magic == b"WGC2"
    targets = json.loads((HERE / "cable_tower_targets.json").read_text())
    source = json.loads((HERE / "scene_cable_source.json").read_text())
    assert not set(targets) & set(manifest["clips"]), "Append to the preceding catalogue, not a second time"
    packer = PartCatalogPacker()
    clips = {}
    overlays = {}
    for model, slots in targets.items():
        raw = json.loads((d / (model + ".json")).read_text())
        entries = assemble(raw, slots, source)
        for e in entries:
            e["part_id"] = n + packer.add(e["verts"], e["tris"], e["smooth"])
        clips[model], _, _ = pack_clip(model, raw["acts"], entries)
        overlays[model] = dict(targets={i: x[0] for i, x in slots.items()}, count=len(entries))
    for m, b in clips.items():
        (d / (m + ".wgm")).write_bytes(b)
    (d / "parts.bin").write_bytes(
        struct.pack("<4sI", magic, n + packer.count) + base[8:] + packer.build_bytes()[8:]
    )
    manifest.setdefault("machineOverlays", {}).update(overlays)
    manifest["clips"] = sorted(set(manifest["clips"]) | set(clips))
    (d / "wgm_manifest.json").write_text(json.dumps(manifest, separators=(",", ":")))
    print(
        f"{len(clips)} cable overlays, {sum(map(len, clips.values()))} bytes, {packer.count} additional shared parts"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", type=Path)
    append_batch(parser.parse_args().view)
