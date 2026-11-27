"""Fit saved gym exteriors to the Smith clips after the plate and pad overlays."""

import argparse
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

from upgrade_app3d_adjust_bench import HERE, append_batch, load
from upgrade_app3d_machines import decompose_frames, strip_fake_animation
from upgrade_app3d_rest_bars import check_round_target, round_parts
from upgrade_app3d_rest_pull_stations import extent_over_hull
from part_registry import MAT_BAR_KNURL, MAT_CHROME, MAT_FRAME, MAT_RUBBER, MAT_SILVER


TARGETS = "rest_smith_targets.json"
SOURCE = "scene_rest_smith_source.json"
REPORT = "rest_smith_fit.json"
SHELLS = {
    "base_beam": "frame_foot", "base_crossfoot": "top_beam", "frame_brace": "top_beam",
    "frame_crossbeam": "top_beam", "frame_rail": "top_beam", "guide_mount": "top_beam",
    "pad_mount": "top_beam", "pad_rail": "top_beam", "rail_mount": "top_beam",
}
ROUND = {
    "barbell_shaft__001": ("barbell_shaft__001", 12, MAT_BAR_KNURL),
    "barbell_shaft__003": ("barbell_shaft__001", 8, MAT_BAR_KNURL),
    "bar_sleeve__001": ("bar_sleeve__001", 12, MAT_CHROME),
    "bar_sleeve__003": ("bar_sleeve__001", 8, MAT_CHROME),
    "bar_collar__001": ("bar_collar__001", 12, MAT_SILVER),
    "bar_collar__002": ("bar_collar__001", 8, MAT_SILVER),
    "guide_rail__001": ("guide_rail", 8, MAT_CHROME),
    "frame_rail__008": ("guide_rail", 12, MAT_CHROME),
    "storage_peg__001": ("storage_peg", 8, MAT_CHROME),
}


def fit_shell(vertices, envelope, axis):
    """Tuck the bevel inside the stock chamfer without moving either mounting end."""
    vertices = vertices.copy()
    radial = vertices.copy()
    radial[:, axis] = 0
    planes = ConvexHull(envelope).equations
    distance = -vertices[:, axis, None] * planes[:, axis] - planes[:, 3]
    slopes = np.einsum("vi,pi->vp", radial, planes[:, :3])
    limits = np.ones_like(slopes)
    np.divide(distance, slopes, out=limits, where=slopes > 1e-10)
    vertices += radial * (np.minimum(1, limits.min(1))[:, None] - 1)
    return vertices


def prototype(group, old, source):
    if group in ROUND:
        key, sides, material = ROUND[group]
        profile = source[key]
        check_round_target(group, old, sides)
        size, parts = round_parts(profile, sides, material, True)
        return [(v / size, t, smooth, mat, profile["rgb"]) for v, t, smooth, mat in parts]

    role = group.split("__")[0]
    key = SHELLS.get(role, role)
    if group in {"frame_post__001", "frame_post__004"}:
        key = "top_beam"
    slot = source[key]
    v = np.asarray(slot["v"])
    v = fit_shell(v / np.ptp(v, axis=0), old / np.ptp(old, axis=0), 2 if role == "rubber_foot" else 0)
    t = np.asarray(slot["t"]).reshape(-1, 3)
    if key == "frame_post":
        # Keep the perforations and their original wall finish in one reusable shape.
        finish = np.asarray(slot["slots"])
        return [(v, t[finish == i].ravel(), False, mat, slot["finishes"][label])
                for i, (label, mat) in enumerate((("E_frame", MAT_FRAME), ("E_silver", MAT_SILVER)))]
    return [(v, t.ravel(), False, MAT_RUBBER if role == "rubber_foot" else MAT_FRAME, slot["rgb"])]


def build_model(raw, mapping, source, frames, prototypes):
    if frames is None or not np.isfinite(frames).all():
        raise ValueError("missing final posed body")
    rows, audit = [], {}
    for name, (index, group) in mapping.items():
        obj = raw["objects"][index]
        if obj["name"] != name:
            raise ValueError(f"{name}: stale exterior index")
        old = np.asarray(obj["verts"]).reshape(-1, 3)
        dims = np.ptp(old, axis=0)
        center = (old.min(0) + old.max(0)) / 2
        track = strip_fake_animation(obj["m"])
        p, q, s = decompose_frames(track)
        linear = Rotation.from_quat(q).as_matrix() * s[:, None, :]
        stock = np.asarray(track).reshape(-1, 4, 4)[:, :3, :3].transpose(0, 2, 1)
        if np.any(dims <= 0) or np.any(s <= 0) or not np.allclose(linear, stock, atol=3e-5):
            raise ValueError(f"{name}: unsupported exterior track or bounds")
        if group not in prototypes:
            prototypes[group] = prototype(group, old - center, source)
        parts = prototypes[group]
        fitted = np.vstack([v * dims + center for v, *_ in parts])
        excess = extent_over_hull(old, fitted)
        if excess > 0.000025:
            raise ValueError(f"{name}: scene shape exceeds the original envelope by {excess * 1000:.3f} mm")
        p = p + np.einsum("fij,j->fi", linear, center)
        for v, tris, smooth, mat, rgb in parts:
            rows.append(dict(name=name, verts=v, tris=tris, smooth=smooth, mat=mat, color=rgb,
                             pos=p, quats=q, sc=s * dims))
        audit[name] = dict(group=group, frames=len(p), records=len(parts),
                           outward_mm=round(max(0, excess) * 1000, 6))
    return rows, audit


def shared_sources():
    bars = load(HERE / "scene_rest_bar_source.json")
    return {
        **{group: bars[group] for group in ("barbell_shaft__001", "bar_sleeve__001", "bar_collar__001")},
        "rubber_foot": load(HERE / "scene_rest_cable_source.json")["rubber_foot"],
    }


def upgrade(view):
    shared = shared_sources()
    prototypes = {}

    def assemble(key, raw, mapping, source, frames, base):
        return build_model(raw, mapping, {**source, **shared}, frames, prototypes)

    return append_batch(view, targets_file=TARGETS, source_file=SOURCE,
                        report_file=REPORT, build_model=assemble)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("viewer", type=Path)
    upgrade(parser.parse_args().viewer)
