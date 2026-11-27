"""Apply fixed bench frames and free-weight exteriors to the posed phone bundle."""

import argparse
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from upgrade_app3d_adjust_bench import HERE, append_batch, load
from upgrade_app3d_adjust_bench_rest import BAR_GROUPS, exterior
from upgrade_app3d_machines import decompose_frames, strip_fake_animation
from upgrade_app3d_rest_bars import assemble as assemble_bar, parts as bar_parts
from fixed_pad_contact import penetration
from part_registry import MAT_SILVER

TARGETS = "rest_bench_targets.json"
SOURCE = "scene_rest_bench_source.json"
REPORT = "rest_bench_fit.json"
HANDWEIGHT_TARGETS = "rest_handweights_targets.json"
HANDWEIGHT_REPORT = "rest_handweights_fit.json"
HANDWEIGHT_TARGETS_02 = "rest_handweights_targets_02.json"
HANDWEIGHT_REPORT_02 = "rest_handweights_fit_02.json"


def exterior_part(group, source, centered, triangles):
    role = group.split("__")[0]
    scene_role = {"dumbbell_neck": "dumbbell_cap", "pad_mount": "frame_post",
                  "seat_post": "frame_post", "seat_support": "base_beam"}.get(role, role)
    v, t, rgb, mat, smooth = exterior(scene_role, source, centered, triangles)
    if role == "frame_brace":
        mat = MAT_SILVER
    if group == "dumbbell_head__002":
        # The contoured dumbbell has local X as its axle and the wide hex axis along Y.
        v = v[:, [2, 1, 0]] * [1, 1, -1]
    return v, t, rgb, mat, smooth


def assemble(view, key, raw, mapping, source, frames, base, bars):
    if frames is None or frames.shape[1:] != (1401, 3):
        raise ValueError("missing final hand poses")
    faces = np.asarray(base["triangles"]).reshape(-1, 3)
    motion = view / "human_v5" / (key + ".bin")
    times = np.frombuffer(motion.read_bytes(), "<f4", len(frames), 40)
    acts = np.asarray(raw["acts"], "<f4")
    rows, audit = [], {}
    bar_mapping = {}
    for name, (index, group) in mapping.items():
        if group in BAR_GROUPS:
            bar_mapping[name] = (index, group)
            continue
        obj = raw["objects"][index]
        if obj["name"] != name:
            raise ValueError(f"{name}: stale target index")
        old = np.asarray(obj["verts"]).reshape(-1, 3)
        size = np.ptp(old, axis=0)
        center = (old.min(0) + old.max(0)) / 2
        p, q, s = decompose_frames(strip_fake_animation(obj["m"]))
        if size.min() <= 0 or np.any(s <= 0) or not np.allclose(s, s[0], atol=1e-5):
            raise ValueError(f"{name}: exterior requires a rigid track with positive dimensions")
        centered = old - center
        v, t, color, mat, smooth = exterior_part(group, source, centered, np.asarray(obj["tris"]))
        # Pullover and row store the grip and both head offsets in the moving mesh.
        # Recenter around each original part without changing the shared motion path.
        origin = p + Rotation.from_quat(q).apply(center * s)
        scale = s * size
        overlap = penetration(frames, faces, times, acts, centered * s[0],
                              v * scale[0], origin, q)
        if overlap["added_hull_mm"] > 10:
            raise ValueError(f"{name}: visible new body overlap ({overlap})")
        rows.append(dict(name=name, verts=v, tris=t, color=color, mat=mat, smooth=smooth,
                         pos=origin, quats=q, sc=scale))
        audit[name] = dict(group=group, frames=len(p), adjustment_axis=None,
                           old_triangles=len(obj["tris"]) // 3, new_triangles=len(t) // 3,
                           collision=overlap)
    bar_rows, bar_audit = assemble_bar(raw, bar_mapping, bars, frames, times, faces)
    return rows + bar_rows, {**audit, **bar_audit}


def upgrade(view, *, handweights=False, handweights_02=False):
    source_file = "scene_adjust_bench_rest_source.json"
    targets_file, report_file = HANDWEIGHT_TARGETS, HANDWEIGHT_REPORT
    shared, bars = {}, {}
    if handweights_02:
        targets_file, report_file = HANDWEIGHT_TARGETS_02, HANDWEIGHT_REPORT_02
    elif not handweights:
        targets_file, source_file, report_file = TARGETS, SOURCE, REPORT
        shared = load(HERE / "scene_adjust_bench_rest_source.json")
        shared["rubber_foot"] = load(HERE / "scene_fixed_bench_rest_source.json")["rubber_foot"]
        source_bars = load(HERE / "scene_rest_bar_source.json")
        bars = {group: (*bar_parts(group, source_bars[group]), source_bars[group]["rgb"])
                for group in BAR_GROUPS}

    def build_model(key, raw, mapping, source, frames, base):
        return assemble(view, key, raw, mapping, {**shared, **source}, frames, base, bars)

    return append_batch(view, targets_file=targets_file, source_file=source_file,
                        report_file=report_file, build_model=build_model)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("viewer", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--handweights", action="store_true", help="apply the first dumbbell batch")
    mode.add_argument("--handweights-02", action="store_true", help="apply the second dumbbell batch")
    args = parser.parse_args()
    upgrade(args.viewer, handweights=args.handweights, handweights_02=args.handweights_02)
