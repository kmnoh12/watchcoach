"""Append the second cable-station exterior batch to the final hand bundle."""

import argparse
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

import upgrade_app3d_rest_cables as cable
from upgrade_app3d_adjust_bench import HERE, append_batch, load
from upgrade_app3d_machines import decompose_frames, strip_fake_animation
from upgrade_app3d_rest_bars import round_parts
from upgrade_app3d_strength_access import scene_profile
from fixed_pad_contact import penetration
from part_registry import MAT_CHROME, MAT_FRAME, MAT_RUBBER, MAT_SILVER


TARGETS = "cable_rest_targets_02.json"
SOURCE = "scene_cable_rest_source.json"
REPORT = "cable_rest_fit_02.json"

# Reuse the rack's perforated post, cross foot and straight chin-up bar.
SHARED_FRAMES = {"base_beam__001", "frame_post__002", "pullup_bar__001"}
SHARED_SHELLS = {
    "base_beam__002", "base_crossfoot__002", "frame_foot__002", "frame_brace__002",
    "frame_rail__003", "rubber_foot__001", "frame_post__003", "frame_link__001",
    "rope_connector__001", "rope_stop__002",
}
FRAME_PROFILES = {
    "base_crossfoot__003": "base_crossfoot__002",
    "frame_brace__003": "frame_brace__002",
    "frame_foot__003": "frame_foot__002",
    "handle_mount__001": "frame_brace__002",
    "handle_mount__002": "frame_brace__002",
    "rubber_foot__002": "rubber_foot__001",
    "seat_post__001": "frame_post__003",
    "seat_support__001": "base_crossfoot__002",
    "top_beam__001": "frame_crossbeam__004",
}
# source, original contact polygon, original local axle, pivot at one end
TUBES = {
    "cable_segment__005": ("cable_segment", 5, "y", True, MAT_RUBBER),
    "carabiner_link__002": ("carabiner_link", 5, "z", False, MAT_CHROME),
    "hand_grip__006": ("hand_grip", 8, "z", False, MAT_RUBBER),
    "handle_support__004": ("d_handle_side", 6, "z", False, MAT_CHROME),
    "pullup_bar__002": ("hand_grip", 8, "z", False, MAT_RUBBER),
    "rope_cord__001": ("rope_cord", 6, "z", False, MAT_RUBBER),
    "rope_ferrule__001": ("rope_connector", 10, "z", False, MAT_CHROME),
    "rope_grip__001": ("rope_cord", 6, "z", False, MAT_RUBBER),
    "rope_stop__001": ("rope_stop", 8, "z", False, MAT_RUBBER),
    "support_handle__001": ("hand_grip", 8, "z", False, MAT_RUBBER),
}
ADJUSTERS = {"adjustment_track", "carriage", "height_detent", "height_slot", "lock_pin"}


def use_source(source, shared, group):
    if group in SHARED_FRAMES:
        return scene_profile(group, shared[group], "pullup_bar")
    if group in TUBES:
        key, sides, axis, end_pivot, material = TUBES[group]
        slot = source[key]
        _, pieces = round_parts(slot, sides, material, True)
        radius = np.linalg.norm(np.asarray(slot["ring"]), axis=1).mean()
        height = np.ptp(np.asarray(slot["v"])[:, 0])
        layers = []
        for v, t, smooth, mat in pieces:
            v = v / [radius, radius, height]
            if end_pivot:
                v[:, 2] += 0.5
            if axis == "y":
                v = v[:, [0, 2, 1]] * [1, 1, -1]
            layers.append((v, t, slot["rgb"], mat, smooth))
        return None, layers
    slot = source[FRAME_PROFILES.get(group, group)]
    v = np.asarray(slot["v"])
    tris = np.asarray(slot["t"])
    materials = np.asarray(slot["material"])
    layers = []
    for index in sorted(set(materials)):
        used, faces = np.unique(tris[materials == index], return_inverse=True)
        name = slot["materials"][index]
        material = MAT_RUBBER if name.endswith("_Grip") else MAT_FRAME if name.endswith("_Frame") else MAT_SILVER
        smooth = name.endswith(("_Steel", "_Grip"))
        layers.append((v[used], faces.ravel(), slot["rgb"][index], material, smooth))
    return np.ptp(v, axis=0), layers


def envelope_error(points, hull):
    planes = ConvexHull(hull).equations
    return float(np.max(np.einsum("vi,pi->vp", points, planes[:, :3]) + planes[:, 3]))


def upgrade(view):
    shared = load(HERE / "scene_strength_access_source.json")
    previous = load(HERE / cable.SOURCE)
    templates = {}

    def assemble(key, raw, mapping, source, frames, base):
        if frames is None or frames.shape[1:] != (1401, 3):
            raise ValueError("missing final hand poses")
        objects = {obj["name"]: obj for obj in raw["objects"]}
        for side in ("l", "r"):
            name = "cable_out_" + side
            if name in mapping:
                track = np.asarray(objects[name]["m"]).reshape(-1, 4, 4)
                hook = np.asarray(objects[f"carabiner_{side}_3"]["m"]).reshape(-1, 4, 4)
                gap = np.linalg.norm(track[:, 3, :3] + track[:, 2, :3] - hook[:, 3, :3], axis=1).max()
                if gap > .02:
                    raise ValueError(f"{name}: existing outgoing cable detaches by {gap * 1000:.1f} mm")
        faces = np.asarray(base["triangles"]).reshape(-1, 3)
        times = np.frombuffer((view / "human_v5" / (key + ".bin")).read_bytes(), "<f4", len(frames), 40)
        acts = np.asarray(raw["acts"], "<f4")
        rows, audit, attachments = [], {}, {}
        for name, (index, group) in mapping.items():
            obj = raw["objects"][index]
            if name != obj["name"]:
                raise ValueError(f"{name}: stale target index")
            if group == "carabiner_link__001":
                attachments.setdefault(name.rsplit("_", 1)[0], []).append(obj)
                continue
            old = np.asarray(obj["verts"]).reshape(-1, 3)
            lo, hi = old.min(0), old.max(0)
            track = strip_fake_animation(obj["m"])
            pos, quats, scale = decompose_frames(track)
            legacy = np.asarray(track).reshape(-1, 4, 4)[:, :3, :3].transpose(0, 2, 1)
            if np.any(hi <= lo) or np.any(scale <= 0):
                raise ValueError(f"{name}: degenerate source or track")
            if group == "cable_segment__004":
                # Six-decimal JSON rounding is significant across a 4.5 mm
                # radius. Anchor the rotation to the full-length column to
                # keep both cable endpoints exact before WGM quantization.
                z = legacy[:, :, 2] / scale[:, 2, None]
                x = legacy[:, :, 0] / scale[:, 0, None]
                x -= np.einsum("ij,ij->i", x, z)[:, None] * z
                x /= np.linalg.norm(x, axis=1)[:, None]
                quats = Rotation.from_matrix(np.stack((x, np.cross(z, x), z), axis=2)).as_quat()
                for i in range(1, len(quats)):
                    if np.dot(quats[i - 1], quats[i]) < 0:
                        quats[i] *= -1
            linear = Rotation.from_quat(quats).as_matrix() * scale[:, None, :]
            if not np.allclose(linear, legacy, rtol=0, atol=1e-5):
                raise ValueError(f"{name}: cannot preserve original transform")
            if group in SHARED_SHELLS or (group in cable.ROUNDS and group not in SHARED_FRAMES):
                fit = cable.round_parts if group in cable.ROUNDS else cable.shell_parts
                size, parts = fit(group, old, previous)
                layers = [(v, t, color, mat, smooth) for v, t, smooth, mat, color in parts]
            else:
                if group not in templates:
                    templates[group] = use_source(source, shared, group)
                dims, layers = templates[group]
                if group in TUBES:
                    _, _, axis, _, _ = TUBES[group]
                    radius = -lo[2] if axis == "y" else hi[1]
                    size = np.full(3, radius)
                    i = "xyz".index(axis)
                    size[i] = hi[i] - lo[i]
                else:
                    if np.max(abs(lo + hi)) > 1e-5:
                        raise ValueError(f"{name}: exterior has an off-centre pivot")
                    size = (hi - lo) / dims
            fitted = np.vstack([layer[0] for layer in layers]) * size
            if group in TUBES or group in cable.ROUNDS or group == "pullup_bar__001":
                # Both envelopes coincide, including end planes. This also
                # bounds the difference through all varying cable scales.
                err = max(envelope_error(fitted, old), envelope_error(old, fitted))
                if err * scale.max() > .0002:
                    raise ValueError(f"{name}: contact profile differs by {err * scale.max() * 1000:.3f} mm")
            else:
                err = None
            collision = None
            if np.allclose(scale, scale[0], atol=1e-5):
                collision = penetration(frames, faces, times, acts, old * scale[0], fitted * scale[0], pos, quats)
                if collision["added_hull_mm"] > 10:
                    raise ValueError(f"{name}: new visible overlap ({collision})")
            for p, tris, color, mat, smooth in layers:
                rows.append(dict(name=name, verts=p, tris=tris, color=color, mat=mat, smooth=smooth,
                                 pos=pos, quats=quats, sc=scale * size))
            audit[name] = dict(group=group, count=len(layers), frames=len(pos), collision=collision,
                               contact_mm=None if err is None else round(err * scale.max() * 1000, 4))
        for prefix, links in attachments.items():
            fitted = cable.carabiner(raw, links, previous, prefix=prefix)
            collision = cable.carabiner_clearance(links, fitted, frames, faces, times, acts)
            rows.extend(fitted)
            audit[links[0]["name"]] = dict(group="carabiner_link__001", count=len(fitted),
                                           frames=len(acts), collision=collision,
                                           merged=[obj["name"] for obj in links])
        # Height presets determine the line of pull, including pulley mounts
        # connected to the carriage. Only record the axis here. There are no
        # independently body-adjustable pads or rollers in these exercises.
        for obj in raw["objects"]:
            if obj["name"].split(".")[0] in ADJUSTERS:
                audit.setdefault(obj["name"], {"count": 0})["adjustment_axis"] = [0, 0, 1]
        return rows, audit

    return append_batch(view, targets_file=TARGETS, source_file=SOURCE, report_file=REPORT, build_model=assemble)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", type=Path)
    upgrade(parser.parse_args().view)
