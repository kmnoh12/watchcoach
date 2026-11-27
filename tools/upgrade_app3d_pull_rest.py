"""Add the scene's exterior parts to the seated row, T-bar and lever pulldown clips."""

import argparse
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

import upgrade_app3d_cable_rest as cable_rest
import upgrade_app3d_rest_cables as cable
from upgrade_app3d_adjust_bench import HERE, append_batch, load
from upgrade_app3d_machines import decompose_frames, strip_fake_animation
from upgrade_app3d_pull_pads import shared_axle_trial
from upgrade_app3d_rest_bars import check_round_target, round_parts
from fixed_pad_contact import penetration
from part_registry import MAT_ACCENT, MAT_CHROME, MAT_FRAME, MAT_PAD, MAT_RUBBER, MAT_SILVER


TARGETS = "pull_rest_targets.json"
SOURCE = "scene_pull_rest_source.json"
REPORT = "pull_rest_fit.json"

ROUND_PROFILES = {
    "footplate_support__004": ("d_handle_side", 8, MAT_SILVER),
    "frame_brace__006": ("d_handle_side", 12, MAT_CHROME),
    "hand_grip__001": ("row_grip", 8, MAT_RUBBER),
    "hand_grip__003": ("row_grip", 8, MAT_CHROME),
    "hand_grip__010": ("row_grip", 10, MAT_RUBBER),
    "hand_grip__013": ("row_grip", 20, MAT_CHROME),
    "handle_bridge__005": ("d_handle_side", 6, MAT_CHROME),
    "bar_sleeve__003": ("bar_sleeve__003", 8, MAT_CHROME),
    "bar_collar__002": ("bar_collar__001", 8, MAT_SILVER),
    "bar_collar__005": ("bar_collar__001", 8, MAT_SILVER),
}
FRAME_PROFILES = {
    "base_beam": "frame_post", "base_crossfoot": "frame_foot", "frame_crossbeam": "frame_link",
    "frame_brace": "frame_brace", "frame_foot": "frame_foot", "frame_leg": "frame_post",
    "frame_link": "frame_link", "frame_post": "frame_post", "frame_spine": "frame_spine",
    "frame_stay": "frame_brace", "top_beam": "frame_link", "tower_post": "frame_post",
    "panel_mount": "frame_brace", "handle_support": "lever_arm", "lever_arm": "lever_arm",
    "footplate_support": "footplate_support", "rubber_foot": "rubber_foot",
}
PANELS = {"footplate__001", "sign_panel__001", "badge__001", "pivot_cover__001"}
CONTACTS = {"cable_segment", "hand_grip", "handle_bridge", "bar_sleeve", "bar_collar"}


def exterior(group, old, source, shared, finish):
    role = group.split("__")[0]
    if group in cable.ROUNDS:
        factor, parts = cable.round_parts(group, old, shared)
        return factor, [(v, t, rgb, mat, smooth) for v, t, smooth, mat, rgb in parts]
    if group == "handle_support__004":
        _, parts = cable_rest.use_source(finish, {}, group)
        return np.array([old[:, 1].max()] * 2 + [np.ptp(old[:, 2])]), parts
    if group in ROUND_PROFILES:
        shape, sides, material = ROUND_PROFILES[group]
        check_round_target(group, old, sides)
        slot = source[shape]
        dims, parts = round_parts(slot, sides, material, True)
        return np.ptp(old, axis=0) / dims, [(v, t, slot["rgb"], mat, smooth) for v, t, smooth, mat in parts]
    if group in cable_rest.SHARED_SHELLS:
        shape, colour, mat = cable.SHELLS[role]
        slot = shared[shape]
        v = np.asarray(slot["v"])
        return np.ptp(old, axis=0) / np.ptp(v, axis=0), [(v, np.asarray(slot["t"]), shared[colour]["rgb"], mat, False)]
    if group in PANELS:
        pieces = source[group] if isinstance(source[group], list) else [source[group]]
        shape = np.vstack([p["v"] for p in pieces])
        fitted = []
        for index, p in enumerate(pieces):
            name = p["material"]
            material = {"E_print": MAT_PAD, "E_steel": MAT_CHROME, "E_silver": MAT_SILVER}.get(name, MAT_RUBBER)
            if name.endswith("_Accent"):
                material = MAT_ACCENT
            elif name.endswith("_Silver"):
                material = MAT_SILVER
            vertices = np.asarray(p["v"])
            if group == "footplate__001" and index == 0:
                # Raise the backing to meet the ribs and keep the tread crest
                # on the original contact plane. The bevel and all ribs remain.
                bottom = vertices[:, 2].min()
                top = shape[:, 2].max() - .002
                vertices[:, 2] = bottom + (vertices[:, 2] - bottom) * (top - bottom) / np.ptp(vertices[:, 2])
            fitted.append((vertices, np.asarray(p["t"]), p["rgb"], material, False))
        return np.ptp(old, axis=0) / np.ptp(shape, axis=0), fitted
    if group in {"base_crossfoot__003", "frame_crossbeam__004", "top_beam__001"}:
        dims, parts = cable_rest.use_source(finish, {}, group)
        return np.ptp(old, axis=0) / dims, parts
    slot = source[FRAME_PROFILES[role]]
    v = np.asarray(slot["v"])
    material = MAT_RUBBER if role == "rubber_foot" else MAT_FRAME
    return np.ptp(old, axis=0) / np.ptp(v, axis=0), [(v, np.asarray(slot["t"]), slot["rgb"], material, False)]


def outside(points, reference):
    planes = ConvexHull(reference).equations
    return float((np.einsum("vi,pi->vp", points, planes[:, :3]) + planes[:, 3]).max())


def upgrade(view):
    shared = load(HERE / cable.SOURCE)
    finish = load(HERE / cable_rest.SOURCE)
    reused = load(HERE / "scene_rest_bench_source.json")
    bars = load(HERE / "scene_rest_bar_source.json")
    shared["frame_spine"] = reused["frame_spine"]

    def assemble(key, raw, mapping, source, frames, base):
        if frames is None or frames.shape[1:] != (1401, 3):
            raise ValueError("missing final hand poses")
        objects = {obj["name"]: obj for obj in raw["objects"]}
        if "roller_cross_axle" in objects:
            shared_axle_trial(objects, frames, base)
        source = {**finish, **shared, **source, **bars}
        faces = np.asarray(base["triangles"]).reshape(-1, 3)
        hp = view / "human_v5" / (key + ".bin")
        times = np.frombuffer(hp.read_bytes(), "<f4", len(frames), 40)
        acts = np.asarray(raw["acts"], "<f4")
        rows, audit = [], {}
        for name, (index, group) in mapping.items():
            obj = raw["objects"][index]
            if obj["name"] != name:
                raise ValueError(f"{name}: stale target index")
            old = np.asarray(obj["verts"]).reshape(-1, 3)
            lo, hi = old.min(0), old.max(0)
            role = group.split("__")[0]
            track = strip_fake_animation(obj["m"])
            pos, quats, scale = decompose_frames(track)
            matrix = np.asarray(track).reshape(-1, 4, 4)[:, :3, :3].transpose(0, 2, 1)
            cable_run = role == "cable_segment"
            if np.any(hi <= lo) or np.any(scale <= 0) or (not cable_run and np.max(abs(lo + hi)) > 1e-5):
                raise ValueError(f"{name}: unexpected exterior geometry or pivot")
            if cable_run:
                # Anchor the orthonormal basis to the cable's length column, so
                # JSON rounding in the perpendicular columns cannot move its ends.
                y = matrix[:, :, 1] / scale[:, 1, None]
                x = matrix[:, :, 0] - np.einsum("ij,ij->i", matrix[:, :, 0], y)[:, None] * y
                x /= np.linalg.norm(x, axis=1)[:, None]
                quats = Rotation.from_matrix(np.stack((x, y, np.cross(x, y)), axis=2)).as_quat()
                for i in range(1, len(quats)):
                    if np.dot(quats[i - 1], quats[i]) < 0:
                        quats[i] *= -1
            linear = Rotation.from_quat(quats).as_matrix() * scale[:, None, :]
            rounding = np.einsum("fij,j->fi", abs(linear - matrix), np.maximum(abs(lo), abs(hi)))
            if not np.isfinite(rounding).all() or rounding.max() > .000015:
                raise ValueError(f"{name}: original transform cannot be represented")
            factor, layers = exterior(group, old, source, shared, finish)
            fitted = np.vstack([v for v, *_ in layers]) * factor
            contact = None
            if role in CONTACTS or group in ROUND_PROFILES or group == "handle_support__004":
                contact = 1000 * scale.max() * max(outside(fitted, old), outside(old, fitted))
                if contact > .12:
                    raise ValueError(f"{name}: contact envelope differs by {contact:.3f} mm")
            if role == "footplate":
                contact = float(np.max(abs(np.r_[fitted.min(0) - lo, fitted.max(0) - hi])) * 1000)
                if contact > .12 or not np.any(np.isclose(fitted[:, 2], hi[2], atol=1e-6)):
                    raise ValueError(f"{name}: tread leaves the original contact plane")
            collision = None
            if not cable_run or np.allclose(scale, scale[0], atol=1e-5):
                collision = penetration(frames, faces, times, acts, old * scale[0], fitted * scale[0], pos, quats)
                if collision["added_hull_mm"] > 10:
                    raise ValueError(f"{name}: exterior adds {collision['added_hull_mm']} mm of overlap")
            for v, tris, color, mat, smooth in layers:
                if name.startswith(("floor_shoe", "tower_shoe")):
                    mat, color = MAT_RUBBER, shared["rubber_foot"]["rgb"]
                rows.append(dict(name=name, verts=v, tris=tris.ravel(), color=color, mat=mat, smooth=smooth,
                                 pos=pos, quats=quats, sc=scale * factor))
            audit[name] = dict(group=group, count=len(layers), frames=len(pos), collision=collision, contact_mm=contact)
        # The outlet changes height with the existing cable routing. Its guide
        # and detents are mechanical, independent of the seated body supports.
        if "row_outlet_carriage" in objects:
            audit["row_outlet_carriage"] = {"count": 0, "adjustment_axis": [0, 0, 1]}
        return rows, audit

    return append_batch(view, targets_file=TARGETS, source_file=SOURCE, report_file=REPORT, build_model=assemble)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", type=Path)
    upgrade(parser.parse_args().view)
