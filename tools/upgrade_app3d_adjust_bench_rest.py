"""Add adjustable-bench exterior overlays after the fitted pads and round plates."""

import argparse
from pathlib import Path

import numpy as np

from upgrade_app3d_adjust_bench import HERE, append_batch, load
from upgrade_app3d_machines import decompose_frames, strip_fake_animation
from upgrade_app3d_rest_bars import assemble as assemble_bar, parts as bar_parts
from fixed_pad_contact import penetration
from part_registry import MAT_CHROME, MAT_FRAME, MAT_RUBBER

TARGETS = "adjust_bench_rest_targets.json"
SOURCE = "scene_adjust_bench_rest_source.json"
REPORT = "adjust_bench_rest_fit.json"
GRIPS = {"dumbbell_grip", "hand_grip"}
BAR_GROUPS = {"barbell_shaft__001", "bar_sleeve__001", "bar_collar__001"}
FINISHES = {
    "dumbbell_cap": MAT_CHROME,
    "dumbbell_head": MAT_RUBBER,
    **dict.fromkeys(GRIPS, MAT_CHROME),
}


def exterior(role, source, old, tris):
    """Center the shared mesh in a unit box, preserving the original grip surface."""
    slot = source["dumbbell_grip" if role == "hand_grip" else role]
    color = slot["rgb"]
    if role in GRIPS:
        # The scene applies knurl as a material bump. Retain the hand-fitted
        # contact polygon instead of substituting its rounder source cylinder.
        vertices, triangles = old, tris
    else:
        vertices, triangles = np.asarray(slot["v"]), np.asarray(slot["t"])
    lo, hi = vertices.min(0), vertices.max(0)
    return (
        ((vertices - (lo + hi) / 2) / (hi - lo)).round(6) + 0.0,
        triangles,
        color,
        FINISHES.get(role, MAT_FRAME),
        role in FINISHES and role not in GRIPS and role != "dumbbell_head",
    )


def upgrade(view):
    bars = load(HERE / "scene_rest_bar_source.json")
    bar_templates = {group: (*bar_parts(group, bars[group]), bars[group]["rgb"])
                     for group in BAR_GROUPS}

    def assemble(key, raw, mapping, source, frames, base):
        if frames is None or frames.shape[1:] != (1401, 3):
            raise ValueError("missing final hand poses")
        faces = np.asarray(base["triangles"]).reshape(-1, 3)
        hp = view / "human_v5" / (key + ".bin")
        times = np.frombuffer(hp.read_bytes(), "<f4", len(frames), 40)
        acts = np.asarray(raw["acts"], "<f4")
        rows = []
        metadata = {}
        bar_mapping = {}
        for name, (index, group) in mapping.items():
            if group in BAR_GROUPS:
                bar_mapping[name] = (index, group)
                continue
            obj = raw["objects"][index]
            assert name == obj["name"]
            role = group.split("__")[0]
            old = np.asarray(obj["verts"]).reshape(-1, 3)
            size = np.ptp(old, axis=0)
            if np.max(abs(old.min(0) + old.max(0))) > 1e-6 or size.min() <= 0:
                raise ValueError(f"{name}: exterior must share the original part centre")
            pos, quats, scale = decompose_frames(strip_fake_animation(obj["m"]))
            if not np.allclose(scale, scale[0], atol=1e-5) or np.any(scale <= 0):
                raise ValueError(f"{name}: exterior requires a rigid track")
            v, t, color, mat, smooth = exterior(role, source, old, np.asarray(obj["tris"]))
            overlap = penetration(frames, faces, times, acts, old * scale[0],
                                  v * size * scale[0], pos, quats)
            if overlap["added_hull_mm"] > 10:
                raise ValueError(f"{name}: visible new body overlap ({overlap})")
            rows.append(dict(name=name, verts=v, tris=t, color=color, mat=mat, smooth=smooth,
                             pos=pos, quats=quats, sc=scale * size))
            metadata[name] = dict(group=group, collision=overlap, count=1)
        bar_rows, bar_metadata = assemble_bar(raw, bar_mapping, bar_templates, frames, times, faces)
        for name, info in bar_metadata.items():
            metadata[name] = {**info, "count": sum(r["name"] == name for r in bar_rows)}
        rows.extend(bar_rows)
        return rows, metadata

    return append_batch(view, targets_file=TARGETS, source_file=SOURCE,
                        report_file=REPORT, build_model=assemble)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", type=Path)
    upgrade(parser.parse_args().view)
