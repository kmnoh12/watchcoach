"""Append the reviewed cable exteriors to the existing stack and pulley overlays."""

import argparse
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

from upgrade_app3d_adjust_bench import append_batch
from upgrade_app3d_machines import decompose_frames, strip_fake_animation
from upgrade_app3d_rest_bars import fit_round_profile
from fixed_pad_contact import penetration
from part_registry import MAT_CHROME, MAT_FRAME, MAT_RUBBER, MAT_SILVER


TARGETS = "rest_cable_targets.json"
SOURCE = "scene_rest_cable_source.json"
REPORT = "rest_cable_fit.json"

# The authored runner and upright carry the frame's powder coat and bevels.
SHELLS = {
    "base_beam": ("rubber_foot", "frame_post", MAT_FRAME),
    "base_crossfoot": ("frame_foot", "frame_foot", MAT_FRAME),
    "frame_foot": ("frame_foot", "frame_foot", MAT_FRAME),
    "frame_rail": ("frame_post", "frame_post", MAT_FRAME),
    "frame_post": ("frame_post", "frame_post", MAT_FRAME),
    "frame_brace": ("frame_brace", "frame_brace", MAT_FRAME),
    "frame_link": ("frame_link", "frame_link", MAT_FRAME),
    "rubber_foot": ("rubber_foot", "rubber_foot", MAT_RUBBER),
    "rope_stop": ("rope_stop", "rope_stop", MAT_RUBBER),
    "rope_connector": ("rope_connector", "rope_connector", MAT_SILVER),
}
ROUNDS = {
    "cable_segment__001": ("cable_segment", MAT_RUBBER, 5, 1),
    "cable_segment__004": ("cable_segment", MAT_RUBBER, 8, 2),
    "hand_grip__002": ("hand_grip", MAT_RUBBER, 8, 2),
    "hand_grip__004": ("hand_grip", MAT_RUBBER, 8, 2),
    "handle_support__005": ("handle_support", MAT_CHROME, 6, 2),
    "d_handle_side__001": ("handle_support", MAT_CHROME, 8, 2),
    "d_handle_bridge__001": ("handle_support", MAT_CHROME, 8, 2),
    "lat_bar__001": ("lat_bar", MAT_CHROME, 8, 2),
    "rope_cord__002": ("rope_cord", MAT_RUBBER, 6, 2),
}


def round_profile(source, sides):
    if "ring" in source:
        ring = np.asarray(source["ring"])
    else:
        v = np.asarray(source["v"])
        ring = v[v[:, 2] == v[:, 2].max(), :2]
    # The original contact planes are invariant. The added samples live on the
    # original facets and only the surface normals and material change.
    return fit_round_profile(ring / np.linalg.norm(ring, axis=1).mean(), sides)


def round_parts(group, obj, source):
    shape, mat, sides, axis = ROUNDS[group]
    src = source[shape]
    order = [0, 2, 1] if axis == 1 else [0, 1, 2]
    old = obj[:, order].copy()
    if axis == 1:
        old[:, 1] *= -1
    high = old.max(0)
    radius = high[1]
    angles = np.arange(sides) * 2 * np.pi / sides
    ring = np.column_stack((np.sin(angles), np.cos(angles))) * radius
    expected = np.vstack([np.c_[ring, np.full(sides, z)] for z in (old[:, 2].min(), high[2])])
    if len(old) != len(expected) or np.max(np.min(np.linalg.norm(old[:, None] - expected, axis=2), axis=1)) > 0.00001:
        raise ValueError(f"{group}: unexpected tube contact profile")
    end = old[:, 2].max() - old[:, 2].min()
    anchor = round(old[:, 2].min() / end, 5)
    profile = round_profile(src, sides)
    n = len(profile)
    i = np.arange(n)
    j = np.roll(i, -1)
    wall = np.column_stack((np.tile(i, 2), np.r_[i + n, j + n], np.r_[j + n, j]))
    caps = np.column_stack((np.repeat([2 * n, 2 * n + 1], n), np.r_[i, j + n], np.r_[j, i + n]))
    # Keep native-sized catalogue coordinates even for the long cables. Scale
    # quantization then acts on metres and the far endpoint stays sub-mm.
    vv = np.vstack((np.c_[profile * 0.015, np.full(n, anchor)],
                    np.c_[profile * 0.015, np.full(n, anchor + 1.0)]))
    cap_vertices = np.vstack((vv, [[0, 0, anchor], [0, 0, anchor + 1.0]]))
    factor = np.array([radius / 0.015, radius / 0.015, end])[order]
    result = []
    for v, t, smooth in ((vv, wall, True), (cap_vertices, caps, False)):
        v = v[:, order]
        if axis == 1:
            v[:, 2] *= -1
        result.append((v, t, smooth, mat, src['rgb']))
    return factor, result


def shell_parts(group, old, source):
    role = group.split("__")[0]
    shape, finish, material = SHELLS[role]
    src = source[shape]
    v, t = np.asarray(src["v"]), np.asarray(src["t"])
    size = np.ptp(old, axis=0)
    center = (old.min(0) + old.max(0)) / 2
    if not np.allclose(center, 0, atol=0.00001) or np.any(size < 0.001):
        raise ValueError(f"{group}: unexpected shell pivot or dimensions")
    if role not in {"rope_stop", "rope_connector"} and len(old) != 8:
        raise ValueError(f"{group}: expected a solid frame member")
    if role in {"base_crossfoot", "frame_foot", "base_beam", "rubber_foot"}:
        # Keep the existing floor and neighbouring structural support surfaces.
        assert np.allclose(v.max(0), -v.min(0), atol=0.00001)
    return size / np.ptp(v, axis=0), [(v, t, False, material, source[finish]["rgb"])]


def carabiner(raw, attachments, source):
    names = [f"carabiner_main_{i}" for i in range(12)]
    by_name = {obj["name"]: obj for obj in attachments}
    if set(by_name) != set(names):
        raise ValueError("carabiner does not have the twelve original track segments")
    tracks = [decompose_frames(by_name[name]["m"]) for name in names]
    points = np.asarray([p for p, _, _ in tracks])
    phase = np.arange(12)[:, None, None] * np.pi / 6
    center = points.mean(0)
    short = (points[0] - points[6]) / 2
    long = (points[3] - points[9]) / 2
    expected = center + short * np.cos(phase) + long * np.sin(phase)
    if len(center) != len(raw["acts"]) or np.max(abs(points - expected)) > 0.00001:
        raise ValueError("carabiner segments do not trace a common rigid oval")
    y, z = [span / np.linalg.norm(span, axis=1)[:, None] for span in (short, long)]
    q = Rotation.from_matrix(np.stack([np.cross(y, z), y, z], axis=2)).as_quat()
    for i in range(1, len(q)):
        if np.dot(q[i - 1], q[i]) < 0:
            q[i] *= -1
    short_radius = np.linalg.norm(short, axis=1)
    long_radius = np.linalg.norm(long, axis=1)
    wire_radius = np.median([s[:, 0] for _, _, s in tracks])
    if np.ptp(short_radius) > 0.00001 or np.ptp(long_radius) > 0.00001 or not np.isclose(wire_radius, 0.0055, atol=0.00001):
        raise ValueError("carabiner radii vary across poses")
    scales = np.broadcast_to([wire_radius / 0.0045, np.median(short_radius) / 0.014,
                              np.median(long_radius) / 0.027], center.shape)
    rows = []
    for part in ("ring", "gate"):
        src = source[f"carabiner_link_{part}"]
        rows.append(dict(name=names[0], verts=src["v"], tris=np.ravel(src["t"]), smooth=True,
                         color=src["rgb"], mat=MAT_CHROME, pos=center, quats=q, sc=scales))
    return rows


def carabiner_clearance(attachments, replacement, frames, skin, times, phase):
    """Compare sampled outer envelopes in the shared ring frame.

    The convex hull includes the ring's open centre, so this is only a
    conservative check for a visible change around the small attachment.
    """
    ref = replacement[0]
    inv = Rotation.from_quat(ref["quats"]).inv()
    inverse_matrices = inv.as_matrix()
    original_parts = []
    drift = 0.0
    for obj in attachments:
        p, q, s = decompose_frames(obj["m"])
        v = np.asarray(obj["verts"]).reshape(-1, 3)
        world = Rotation.from_quat(q[0]).apply(v * s[0]) + p[0]
        original_parts.append((world - ref["pos"][0]) @ inverse_matrices[0].T)
        # The cylinders can roll about their axes, so compare centreline
        # positions separately from the sampled skin clearance envelope.
        ends = inv.apply(p - ref["pos"])
        drift = max(drift, float(np.linalg.norm(ends - ends[0], axis=1).max()))
    fitted = np.concatenate([np.asarray(row["verts"]) * row["sc"][0] for row in replacement])
    check = penetration(frames, skin, times, phase, np.concatenate(original_parts), fitted,
                        ref["pos"], ref["quats"])
    if drift > 0.00001 or check["added_hull_mm"] > 10:
        raise ValueError(f"carabiner contact fit failed: {check}")
    return check


def build_model(key, raw, mapping, source, frames, base, times):
    skin = np.asarray(base["triangles"]).reshape(-1, 3)
    phase = np.asarray(raw["acts"], dtype="<f4")
    rows, audit, attachments = [], {}, []
    for name, (index, group) in mapping.items():
        obj = raw["objects"][index]
        if obj["name"] != name:
            raise ValueError(f"{name}: stale target index")
        if group == "carabiner_link__001":
            attachments.append(obj)
            continue
        old = np.asarray(obj["verts"]).reshape(-1, 3)
        p, q, s = decompose_frames(strip_fake_animation(obj["m"]))
        if np.any(s <= 0):
            raise ValueError(f"{name}: unexpected mirrored or singular track")
        factor, parts = round_parts(group, old, source) if group in ROUNDS else shell_parts(group, old, source)
        scale = s * factor
        fitted = np.concatenate([v * factor for v, *_ in parts])
        if group in ROUNDS:
            # Check the shape in its unscaled frame so this also covers variable
            # cable lengths and all interpolated scales without skin resampling.
            hull = ConvexHull(old).equations
            added = np.max(np.einsum("vi,pi->vp", fitted, hull[:, :3]) + hull[:, 3])
            if added > 0.00001:
                raise ValueError(f"{name}: replacement protrudes beyond original tube")
            check = dict(added_hull_mm=0.0)
        else:
            if not np.allclose(s[0], s, atol=0.00001):
                raise ValueError(f"{name}: unexpected varying shell scale")
            check = penetration(frames, skin, times, phase, old * s[0], fitted * s[0], p, q)
            if check["added_hull_mm"] > 10:
                raise ValueError(f"{name}: visible new overlap with the character: {check}")
        for v, t, smooth, mat, color in parts:
            rows.append(dict(name=name, verts=v, tris=t.ravel(), smooth=smooth,
                             mat=mat, color=color, pos=p, quats=q, sc=scale))
        audit[name] = dict(group=group, count=len(parts), frames=len(p), collision=check)
    if attachments:
        fitted = carabiner(raw, attachments, source)
        rows.extend(fitted)
        audit["carabiner_main_0"] = dict(group="carabiner_link__001", count=len(fitted),
                                         frames=len(fitted[0]["pos"]), merged=len(attachments),
                                         collision=carabiner_clearance(attachments, fitted, frames, skin, times, phase))
    track = next((o for o in raw["objects"] if o["name"].startswith("adjustment_track.")), None)
    audit["adjustment_axis"] = [0, 0, 1] if track else None
    return rows, audit


def upgrade(view):
    def build(key, raw, mapping, source, frames, base):
        if frames is None or len(frames) < 2:
            raise ValueError("missing posed character samples")
        path = view / "human_v5" / (key + ".bin")
        times = np.frombuffer(path.read_bytes(), "<f4", len(frames), 40)
        return build_model(key, raw, mapping, source, frames, base, times)

    return append_batch(view, targets_file=TARGETS, source_file=SOURCE, report_file=REPORT, build_model=build)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("viewer", type=Path)
    upgrade(parser.parse_args().viewer)
