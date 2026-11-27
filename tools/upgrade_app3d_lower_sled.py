"""Fit saved gym exteriors to lower sleds without changing the equipment tracks."""

import argparse
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

from upgrade_app3d_adjust_bench import HERE, append_batch, load
from upgrade_app3d_machines import decompose_frames, strip_fake_animation
from upgrade_app3d_rest_bars import check_round_target, round_parts as grip_parts
from upgrade_app3d_rest_cables import round_parts as cable_parts
from upgrade_app3d_rest_pull_stations import extent_over_hull, finish_mesh
from part_registry import MAT_CHROME, MAT_FRAME, MAT_RUBBER, MAT_SILVER


TARGETS = "lower_sled_targets.json"
SOURCE = "scene_lower_sled_source.json"
REPORT = "lower_sled_fit.json"
CABLES = {f"cable_segment__{n:03d}": ("cable_segment", MAT_RUBBER, 5, 1) for n in range(1, 4)}
MITRE = ConvexHull(np.array([
    [x * a, y * b, z * c]
    for a, b, c in ((.5, .2, .2), (.37, .2, .5), (.37, .5, .2))
    for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)
])).equations
ROUND = {
    "bar_collar__001": ("bar_collar", 12, MAT_SILVER),
    "bar_collar__002": ("bar_collar", 8, MAT_SILVER),
    "bar_sleeve__003": ("loading_horn", 8, MAT_CHROME),
    "handle_end_cap__002": ("handle_end_cap", 6, MAT_CHROME),
    "handle_mount__005": ("loading_horn", 8, MAT_CHROME),
    "handle_support__006": ("loading_horn", 8, MAT_CHROME),
    "ladder_rung__001": ("loading_horn", 8, MAT_SILVER),
    "loading_horn__001": ("loading_horn", 12, MAT_CHROME),
    "loading_horn__003": ("loading_horn", 8, MAT_CHROME),
    "loading_horn__004": ("loading_horn", 8, MAT_CHROME),
}
SHELLS = {
    "base_beam": "base_runner", "base_runner": "base_runner", "floor_base": "base_runner",
    "frame_foot": "base_runner",
    "frame_leg": "frame_rail", "frame_link": "frame_rail", "frame_post": "frame_rail",
    "frame_rail": "frame_rail", "handle_mount": "frame_rail", "handle_support": "frame_rail",
    "frame_brace": "frame_brace", "pad_post": "frame_brace", "pad_support": "frame_brace",
    "tower_post": "frame_brace", "footplate_support": "frame_brace",
    "rubber_foot": "rubber_foot", "stop_bumper": "stop_bumper",
}
# Rotate source Z to the contact normal or the bearing axis. X stays across the plate.
Z_TO_Y = Rotation.from_euler("x", -90, degrees=True)
Z_TO_X = Rotation.from_euler("y", 90, degrees=True)


def layer(source, material):
    return np.asarray(source["v"]), np.asarray(source["t"]), False, material, source["rgb"]


def compact_mitre(verts, old):
    """Keep the same conservative end bevel on all 24-vertex tube instances."""
    size = np.ptp(verts, axis=0)
    radius = np.einsum("vi,fi->vf", verts / size, MITRE[:, :3]) / -MITRE[:, 3]
    # Keep the axial mounting plane. Only intermediate bevel rings move inward.
    fitted = verts / np.maximum(1., radius.max(1))[:, None]
    end = abs(verts[:, 0]) == abs(verts[:, 0]).max()
    fitted[end] = np.sign(verts[end]) * size * [.5, .2, .2]
    if extent_over_hull(old / np.ptp(old, axis=0), fitted / size) > 1e-5:
        return None
    return fitted, size


def exterior(name, group, old, tris, color, source):
    role = group.split("__")[0]
    material = MAT_SILVER
    orientation = None
    center = (old.min(0) + old.max(0)) / 2
    if role == "cable_segment":
        factor, pieces = cable_parts(group, old, source, rounds=CABLES)
        return orientation, np.zeros(3), pieces, [(factor, np.zeros(3))] * len(pieces), "profile"

    round_spec = ROUND.get(group)
    if role in {"hand_grip", "support_handle"}:
        mat = MAT_RUBBER if max(color) < .2 else MAT_CHROME
        round_spec = "hand_grip", 8, mat
    if group in {"base_beam__009", "frame_crossbeam__007", "frame_post__007", "frame_rail__005"}:
        round_spec = "loading_horn", 8, MAT_SILVER
    if len(old) == 16 and np.ptp(old, axis=0).argmax() == 0 and group not in ROUND:
        # Stock octagonal structural tubing runs along X. The scene's round
        # profile retains those eight planes when it is installed on that axis.
        orientation = Z_TO_X
        round_spec = "loading_horn", 8, MAT_SILVER
    if round_spec:
        prototype, sides, mat = round_spec
        ref = orientation.inv().apply(old - center) if orientation else old - center
        try:
            check_round_target(name, ref, sides)
        except ValueError:
            if role in {"hand_grip", "support_handle"}:
                raise
        else:
            slot = source[prototype]
            size, pieces = grip_parts(slot, sides, mat, True)
            finish = source.get(SHELLS.get(role), slot)
            if prototype == "hand_grip" and mat == MAT_CHROME:
                finish = source["loading_horn"]
            rgb = color if color[1] > .55 and color[0] < .4 else finish["rgb"]
            layout = [(np.ptp(ref, axis=0) / size, np.zeros(3))] * len(pieces)
            return orientation, center, [(*p, rgb) for p in pieces], layout, "profile"
    orientation = None

    if role == "footplate" and np.ptp(old, axis=0).argmin() == 1:
        orientation = Z_TO_Y
    elif role == "stop_bumper" and np.ptp(old, axis=0).argmin() == 1:
        orientation = Z_TO_Y
    elif role == "sleeve_bushing" and np.ptp(old, axis=0).argmax() == 1:
        orientation = Z_TO_Y * Z_TO_X.inv()
    elif group == "footplate_support__001" and name == "plate_back":
        orientation = Z_TO_X.inv()
    ref = orientation.inv().apply(old - center) if orientation else old - center
    prototype = SHELLS.get(role, "frame_crossbeam")
    if role in {"footplate", "footplate_tread"}:
        prototype = role
        material = MAT_RUBBER if max(color) < .2 else MAT_SILVER
    if role in {"rubber_foot", "stop_bumper"}:
        material = MAT_RUBBER
    if role == "sleeve_bushing":
        # These app sleeves ride square or octagonal rails. Keep the square
        # casting, including the ends which seat against the carriage.
        prototype = "frame_rail"
    if prototype == "frame_brace":
        material = MAT_FRAME
    slot = source[prototype]
    verts, faces, smooth, _, rgb = layer(slot, material)
    if color[1] > .55 and color[0] < .4:
        rgb = color
    elif role == "stop_bumper":
        # A round stop in the scene sits inside a square mounting block in the
        # app. Keep the block so its broad stop surface remains engaged.
        verts, faces, smooth, _, _ = layer(source["rubber_foot"], material)
    elif role == "sleeve_bushing":
        rgb = source["sleeve_bushing"]["rgb"]
    size = np.ptp(verts, axis=0)
    if len(old) == 24 and prototype not in {"rubber_foot", "stop_bumper"}:
        fitted = compact_mitre(verts, ref)
        if fitted is not None:
            verts, size = fitted
    else:
        fitted = verts
    factor = np.ptp(ref, axis=0) / size
    if len(old) in {8, 24} and fitted is not None and extent_over_hull(ref, verts * factor) <= .000015:
        offsets = [np.zeros(3)]
        scales = [factor]
        if role == "footplate" and name in {"foot_surface", "foot_plate", "pendulum_footplate"}:
            # Keep the crest on the original surface. Recess only the backing
            # between the nine scene ribs. The opposite mounting plane is fixed.
            depth = min(.0006, size[2] * factor[2] * .04)
            bottom, top = verts[:, 2].min(), verts[:, 2].max()
            backing_scale = factor.copy()
            backing_scale[2] -= depth / size[2]
            rib, rib_faces, _, _, ink = layer(source["footplate_tread"], MAT_RUBBER)
            tread_scale = np.array([size[0] * factor[0] * .89,
                                    size[1] * factor[1] * .032, depth * 1.75]) / np.ptp(rib, axis=0)
            tread_top = top * factor[2] - rib[:, 2].max() * tread_scale[2]
            offsets = [np.array([0, 0, bottom * (factor[2] - backing_scale[2])])]
            offsets.extend(np.array([0, y, tread_top]) for y in np.linspace(-.42, .42, 9) * size[1] * factor[1])
            scales = [backing_scale, *([tread_scale] * 9)]
            pieces = [(verts, faces, smooth, material, rgb), *([(rib, rib_faces, False, MAT_RUBBER, ink)] * 9)]
        else:
            pieces = [(verts, faces, smooth, material, rgb)]
        return orientation, center, pieces, list(zip(scales, offsets)), "scene"

    # Compound and tight sockets keep the original surface and get the scene finish.
    dims, middle, verts, faces = finish_mesh(old, tris)
    return None, middle, [(verts, faces, False, material, rgb)], [(dims, np.zeros(3))], "finish"


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
        if np.any(s <= 0) or np.any(np.ptp(old, axis=0) < .0001):
            raise ValueError(f"{name}: invalid exterior bounds or track")
        matrix = np.asarray(track).reshape(-1, 4, 4)[:, :3, :3].transpose(0, 2, 1)
        rot = Rotation.from_quat(q)
        linear = rot.as_matrix() * s[:, None, :]
        error = np.einsum("fij,j->fi", abs(linear - matrix), abs(old).max(0)).max()
        if error > .000025:
            raise ValueError(f"{name}: original transform cannot be represented")
        orientation, center, layers, transforms, mode = exterior(name, group, old, obj["tris"], obj["color"], source)
        fitted = np.vstack([v * sc + offset for (v, *_), (sc, offset) in zip(layers, transforms)])
        if orientation:
            fitted = orientation.apply(fitted)
        excess = extent_over_hull(old, fitted + center)
        if excess > .000025:
            raise ValueError(f"{name}: exterior leaves the original envelope by {excess * 1000:.3f} mm")
        p = p + np.einsum("fij,j->fi", linear, center)
        if orientation:
            q = (rot * orientation).as_quat()
            s = s @ abs(orientation.as_matrix())
        for i in range(1, len(q)):
            if np.dot(q[i - 1], q[i]) < 0:
                q[i] *= -1
        part_rot = Rotation.from_quat(q)
        if len(layers) > 2 and (np.ptp(q, axis=0).max() > 2e-5 or np.ptp(s, axis=0).max() > 2e-5):
            raise ValueError(f"{name}: tread layout requires a translating or fixed plate")
        for (verts, tris, smooth, material, color), (sc, offset) in zip(layers, transforms):
            rows.append(dict(name=name, verts=verts, tris=np.ravel(tris), smooth=smooth,
                             mat=material, color=color, pos=p + part_rot.apply(s * offset), quats=q, sc=s * sc))
        audit[name] = dict(group=group, type=mode, frames=len(p), records=len(layers),
                           outward_mm=round(max(0., excess) * 1000, 6))
    return rows, audit


def shared_sources():
    cable = load(HERE / "scene_rest_cable_source.json")
    bars = load(HERE / "scene_rest_bar_source.json")
    return {"cable_segment": cable["cable_segment"], "rubber_foot": cable["rubber_foot"],
            "bar_collar": bars["bar_collar__001"]}


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
