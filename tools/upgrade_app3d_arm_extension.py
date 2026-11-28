"""Pack machine_triceps_extension as a full WGM2 clip with shared PBR materials.

Appends only machine_triceps_extension's geometry to parts.bin and writes
data/machine_triceps_extension.wgm without touching any other clip.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools/viewer3d"))

from part_registry import (
    MAT_ACCENT,
    MAT_CHROME,
    MAT_FRAME,
    MAT_PAD,
    MAT_RUBBER,
    MAT_SELECTOR_WINDOW,
    MAT_SILVER,
)
from upgrade_app3d_adjust_bench import catalog_records
from upgrade_app3d_machines import (
    PartCatalogPacker,
    decompose_frames,
    pack_clip,
    strip_fake_animation,
)

KEY = "machine_triceps_extension"


def classify_armext_part(name: str, color: list[float]) -> tuple[int, bool]:
    """Return (mat_preset, smooth) matching the app's commercial-gym machine style."""
    low = name.lower()
    if "window" in low:
        return MAT_SELECTOR_WINDOW, False
    if any(k in low for k in ("grip", "rubber_foot", "cable", "pulley_stack", "pulley_front", "instruction_panel")):
        if low.endswith("_hub"):
            return MAT_ACCENT, True
        return MAT_RUBBER, any(k in low for k in ("grip", "cable", "pulley"))
    if any(k in low for k in ("selector_pin", "seat_lock", "back_lock", "pivot_cap", "_hub")):
        if low.endswith("_stem") or low.endswith("_shaft"):
            return MAT_CHROME, True
        return MAT_ACCENT, True
    if any(k in low for k in ("guide_", "selector_rod", "back_rail", "pivot_axle", "handle_stem")):
        return MAT_CHROME, "rail" not in low
    if any(k in low for k in ("seat", "back_pad", "arm_pad", "placard_face")):
        if any(k in low for k in ("post", "sleeve", "bracket", "pan")):
            return (MAT_SILVER if min(color) > 0.4 else MAT_FRAME), False
        return MAT_PAD, "placard" not in low
    if any(k in low for k in ("lever_arm", "drive_cam", "pivot_boom", "back_wrap_arm", "pivot_bearing", "handle_collar", "handle_cap")):
        is_red = color[0] > 0.4 and color[1] < 0.1
        is_silver = min(color) > 0.4
        mat = MAT_FRAME if is_red else (MAT_SILVER if is_silver else MAT_FRAME)
        return mat, True
    if min(color) > 0.4:
        return MAT_SILVER, False
    return MAT_FRAME, False


def upgrade(view: Path) -> bool:
    data_dir = view / "data"
    src_path = data_dir / f"{KEY}.json"
    if not src_path.is_file():
        return False

    raw = json.loads(src_path.read_text())
    mf_path = data_dir / "wgm_manifest.json"
    mf = json.loads(mf_path.read_text())
    stock = (data_dir / "parts.bin").read_bytes()
    magic, n = struct.unpack_from("<4sI", stock)
    assert magic == b"WGC2"

    indices = {part: i for i, part in enumerate(catalog_records(stock))}
    extra: list[bytes] = []
    entries = []

    for obj in raw["objects"]:
        name = obj["name"]
        color = obj["color"]
        mat, smooth = classify_armext_part(name, color)
        verts = np.asarray(obj["verts"], dtype=np.float64).reshape(-1, 3)
        tris = np.asarray(obj["tris"], dtype=np.int32).reshape(-1)
        track = strip_fake_animation(obj["m"])
        pos, quats, sc = decompose_frames(track)

        packer = PartCatalogPacker()
        packer.add(verts, tris, smooth)
        part_blob = packer.build_bytes()[8:]
        if part_blob not in indices:
            indices[part_blob] = n + len(extra)
            extra.append(part_blob)

        entries.append(
            dict(
                name=name,
                verts=verts,
                tris=tris,
                color=color,
                mat=mat,
                smooth=smooth,
                pos=pos,
                quats=quats,
                sc=sc,
                part_id=indices[part_blob],
            )
        )

    blob, total_tris, groups = pack_clip(KEY, raw["acts"], entries)
    (data_dir / f"{KEY}.wgm").write_bytes(blob)
    if extra:
        (data_dir / "parts.bin").write_bytes(
            struct.pack("<4sI", magic, n + len(extra)) + stock[8:] + b"".join(extra)
        )
    mf["clips"] = sorted(set(mf["clips"]) | {KEY})
    mf_path.write_text(json.dumps(mf, ensure_ascii=False, separators=(",", ":")))
    print(f"upgraded {KEY}: {len(entries)} parts, {total_tris} tris, {groups} groups, {len(blob)} B (+{len(extra)} catalog parts)")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", type=Path)
    upgrade(parser.parse_args().view)
