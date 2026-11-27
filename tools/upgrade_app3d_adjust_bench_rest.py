"""Add bench and free-weight exterior overlays after the pads and round plates."""

import argparse
from pathlib import Path

import numpy as np

from upgrade_app3d_adjust_bench import HERE, append_batch, load
from upgrade_app3d_machines import decompose_frames, strip_fake_animation
from upgrade_app3d_rest_bars import ROUND_PROFILES, assemble as assemble_bar, parts as bar_parts
from fixed_pad_contact import penetration
from part_registry import MAT_CHROME, MAT_FRAME, MAT_PAD, MAT_RUBBER, MAT_SILVER
from scene_lat_parts import _nine

TARGETS = "adjust_bench_rest_targets.json"
SOURCE = "scene_adjust_bench_rest_source.json"
REPORT = "adjust_bench_rest_fit.json"
FIXED_TARGETS = "fixed_bench_rest_targets.json"
FIXED_REPORT = "fixed_bench_rest_fit.json"
FLAT_TARGETS = "fixed_bench_rest_targets_03.json"
FLAT_REPORT = "fixed_bench_rest_fit_03.json"
GRIPS = {"dumbbell_grip", "hand_grip"}
BAR_GROUPS = {"barbell_shaft__001", "bar_sleeve__001", "bar_collar__001"}
FLAT_BAR_GROUPS = BAR_GROUPS | {"barbell_shaft__002", "bar_sleeve__004", "bar_collar__005",
                               "sleeve_shoulder__001", "sleeve_shoulder__003"}
BENCH_SOURCES = {
    "frame_leg": "frame_post",
    "frame_rail": "base_beam",
    "horn_end_cap": "end_cap",
    "pad_rail": "base_beam",
    "seat_post": "frame_post",
    "seat_support": "base_beam",
}
FINISHES = {
    "dumbbell_cap": MAT_CHROME,
    "dumbbell_head": MAT_RUBBER,
    "floor_mat": MAT_PAD,
    "end_cap": MAT_SILVER,
    "ez_bar": MAT_SILVER,
    "horn_end_cap": MAT_SILVER,
    "rubber_foot": MAT_RUBBER,
    **dict.fromkeys(GRIPS, MAT_CHROME),
}


def exterior(role, source, old, tris):
    """Normalize a scene mesh to the target's local bounds and original pivot."""
    source_role = "dumbbell_grip" if role in GRIPS else BENCH_SOURCES.get(role, role)
    slot = source[source_role]
    color = slot["rgb"]
    if role in GRIPS or role == "ez_bar":
        # The scene applies knurl as a material bump. Retain the hand-fitted
        # contact polygon and the original continuous EZ bend.
        vertices, triangles = old, tris
    else:
        vertices, triangles = np.asarray(slot["v"]), np.asarray(slot["t"])
    lo, hi = vertices.min(0), vertices.max(0)
    old_size = np.ptp(old, axis=0)
    old_center = (old.min(0) + old.max(0)) / 2
    old_center[abs(old_center) < 1e-6] = 0
    if role == "floor_mat":
        # Keep the scene mat's horizontal rim and the target's top and floor planes.
        vertices = vertices.copy()
        for axis in (0, 1):
            vertices[:, axis] = _nine(vertices[:, axis], (hi - lo)[axis] / 2,
                                      old_size[axis] / 2, 0.016)
        lo, hi = vertices.min(0), vertices.max(0)
    return (
        ((vertices - (lo + hi) / 2) / (hi - lo) + old_center / old_size).round(6) + 0.0,
        triangles.reshape(-1),
        color,
        FINISHES.get(role, MAT_FRAME),
        role in {"dumbbell_cap", "ez_bar"},
    )


def upgrade(view, *, fixed=False, flat=False):
    bars = load(HERE / "scene_rest_bar_source.json")
    bar_templates = {}
    for group in FLAT_BAR_GROUPS if flat else BAR_GROUPS:
        profile = ROUND_PROFILES.get(group)
        original = bars[profile[0] if profile else group]
        bar_templates[group] = (*bar_parts(group, original), original["rgb"])

    def assemble(key, raw, mapping, source, frames, base):
        if frames is None or frames.shape[1:] != (1401, 3):
            raise ValueError("missing final hand poses")
        faces = np.asarray(base["triangles"]).reshape(-1, 3)
        hp = view / "human_v5" / (key + ".bin")
        times = np.frombuffer(hp.read_bytes(), "<f4", len(frames), 40)
        acts = np.asarray(raw["acts"], "<f4")
        if fixed or flat:
            source = {**source, "floor_mat": bars["floor_mat__002"]}
        if flat:
            source = {**source, **flat_sources, "ez_bar": bars["ez_bar__002"]}
        rows = []
        metadata = {}
        bar_mapping = {}
        for name, (index, group) in mapping.items():
            if group in bar_templates:
                bar_mapping[name] = (index, group)
                continue
            obj = raw["objects"][index]
            if name != obj["name"]:
                raise ValueError(f"{name}: stale target index")
            role = group.split("__")[0]
            old = np.asarray(obj["verts"]).reshape(-1, 3)
            size = np.ptp(old, axis=0)
            if size.min() <= 0:
                raise ValueError(f"{name}: empty exterior bounds")
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
            if fixed or flat:
                metadata[name]["adjustment_axis"] = None
        bar_rows, bar_metadata = assemble_bar(raw, bar_mapping, bar_templates, frames, times, faces)
        for name, info in bar_metadata.items():
            metadata[name] = {**info, "count": sum(r["name"] == name for r in bar_rows)}
        rows.extend(bar_rows)
        return rows, metadata

    if flat:
        flat_sources = load(HERE / "scene_fixed_bench_rest_source.json")
        targets, report = FLAT_TARGETS, FLAT_REPORT
    elif fixed:
        targets, report = FIXED_TARGETS, FIXED_REPORT
    else:
        targets, report = TARGETS, REPORT
    return append_batch(view, targets_file=targets, source_file=SOURCE,
                        report_file=report, build_model=assemble)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", type=Path)
    batches = parser.add_mutually_exclusive_group()
    batches.add_argument("--fixed", action="store_true", help="apply the first fixed-bench batch")
    batches.add_argument("--flat", action="store_true", help="apply the flat-bench exterior batch")
    args = parser.parse_args()
    upgrade(args.view, fixed=args.fixed, flat=args.flat)
