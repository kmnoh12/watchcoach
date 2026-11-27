"""Fit gym shells to assisted towers, captain chairs, and a straight chin-up station."""

import argparse
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from upgrade_app3d_adjust_bench import HERE, append_batch, load
from part_registry import MAT_CHROME, MAT_FRAME, MAT_RUBBER, MAT_SILVER
from upgrade_app3d_lower_sled import CABLES, compact_mitre, layer
from upgrade_app3d_machines import decompose_frames, strip_fake_animation
from upgrade_app3d_rest_bars import check_round_target, round_parts as grip_parts
from upgrade_app3d_rest_cables import round_parts as cable_parts
from upgrade_app3d_rest_pull_stations import extent_over_hull, finish_mesh


TARGETS = "rest_pull_tower_targets.json"
SOURCE = "scene_rest_pull_tower_source.json"
REPORT = "rest_pull_tower_fit.json"
ROUND = {"dip_handle", "hand_grip", "handle_mount", "pullup_bar"}
SHELLS = {
    "base_beam": "frame_foot", "floor_anchor": "step_platform",
    "frame_gusset": "frame_brace", "frame_stay": "frame_brace",
    "handle_branch": "handle_support", "lever_arm": "handle_support",
    "pad_mount": "handle_support", "top_beam": "frame_crossbeam",
    "tower_side_member": "frame_post",
}


def shared_sources():
    cable = load(HERE / "scene_rest_cable_source.json")
    sled = load(HERE / "scene_lower_sled_source.json")
    return {"cable_segment": cable["cable_segment"], "rubber_foot": cable["rubber_foot"],
            "footplate_tread": sled["footplate_tread"]}


def exterior(name, group, old, triangles, color, source):
    role = group.split("__")[0]
    if role == "cable_segment":
        scale, parts = cable_parts(group, old, source, rounds=CABLES)
        return np.zeros(3), scale, parts, "profile"

    center = (old.min(0) + old.max(0)) / 2
    dims = np.ptp(old, axis=0)
    material = MAT_SILVER if min(color) > .3 else MAT_FRAME
    if role in ROUND:
        steel = role in {"pullup_bar", "handle_mount"} or group == "dip_handle__002"
        profile = source["pullup_bar" if steel else role]
        sides = 6 if role == "handle_mount" else 8
        check_round_target(name, old - center, sides)
        size, parts = grip_parts(profile, sides, MAT_CHROME if steel else MAT_RUBBER, True)
        return center, dims / size, [(*part, profile["rgb"]) for part in parts], "profile"

    if role in {"rubber_foot", "footplate_tread"} or (role == "step_platform" and max(color) < .2):
        material = MAT_RUBBER
    slot = source[SHELLS.get(role, role)]
    verts, tris, smooth, material, finish = layer(slot, material)
    if material == MAT_RUBBER:
        finish = source["rubber_foot"]["rgb"]
    elif material == MAT_FRAME:
        finish = source["frame_foot"]["rgb"]
    size = np.ptp(verts, axis=0)
    if len(old) == 24 and role != "rubber_foot":
        fitted = compact_mitre(verts, old - center)
        if fitted is not None:
            verts, size = fitted
    scale = dims / size
    if extent_over_hull(old, verts * scale + center) <= .000025:
        return center, scale, [(verts, tris, smooth, material, finish)], "scene"

    # Keep the exact contour if a scene shell cannot preserve the mounting envelope.
    dims, center, verts, tris = finish_mesh(old, triangles)
    return center, dims, [(verts, tris, False, material, finish)], "finish"


def build_model(key, raw, mapping, source, frames, base):
    if frames is None or not np.isfinite(frames).all():
        raise ValueError("missing final posed body")
    rows, audit = [], {}
    for name, (index, group) in mapping.items():
        obj = raw["objects"][index]
        if obj["name"] != name:
            raise ValueError(f"{name}: stale exterior index")
        old = np.asarray(obj["verts"]).reshape(-1, 3)
        track = strip_fake_animation(obj["m"])
        p, q, s = decompose_frames(track)
        linear = Rotation.from_quat(q).as_matrix() * s[:, None, :]
        stock = np.asarray(track).reshape(-1, 4, 4)[:, :3, :3].transpose(0, 2, 1)
        if np.any(s <= 0) or not np.allclose(linear, stock, atol=3e-5):
            raise ValueError(f"{name}: invalid or sheared exterior track")
        center, scale, parts, mode = exterior(name, group, old, obj["tris"], obj["color"], source)
        fitted = np.vstack([v * scale + center for v, *_ in parts])
        excess = extent_over_hull(old, fitted)
        if excess > .000025:
            raise ValueError(f"{name}: exterior exceeds the original contact envelope")
        p = p + np.einsum("fij,j->fi", linear, center)
        for verts, tris, smooth, material, color in parts:
            rows.append(dict(name=name, verts=verts, tris=np.ravel(tris), smooth=smooth,
                             mat=material, color=color, pos=p,
                             quats=q, sc=s * scale))
        audit[name] = dict(group=group, type=mode, frames=len(p), records=len(parts),
                           outward_mm=round(max(0., excess) * 1000, 6))
    return rows, audit


def upgrade(view):
    shared = shared_sources()

    def build(key, raw, mapping, source, frames, base):
        return build_model(key, raw, mapping, {**source, **shared}, frames, base)

    return append_batch(view, targets_file=TARGETS, source_file=SOURCE,
                        report_file=REPORT, build_model=build)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("viewer", type=Path)
    upgrade(parser.parse_args().viewer)
