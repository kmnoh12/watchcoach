"""Apply saved gym free-weight shells and the fixed exercise mat to bar batches."""

import argparse
from pathlib import Path

import numpy as np

from upgrade_app3d_adjust_bench import append_batch
from upgrade_app3d_machines import decompose_frames, strip_fake_animation
from fixed_pad_contact import penetration
from part_registry import MAT_BAR_KNURL, MAT_CHROME, MAT_FRAME, MAT_PAD, MAT_SILVER
from scene_lat_parts import _nine


MATERIALS = {
    "barbell_shaft__001": MAT_CHROME,
    "bar_sleeve__001": MAT_CHROME,
    "bar_collar__001": MAT_SILVER,
    "floor_mat__002": MAT_PAD,
}

# A scene profile can cover several roles, but different contact polygons cannot
# share geometry. Each role group gets one profile scaled by each part's track.
ROUND_PROFILES = {
    "barbell_shaft__002": ("barbell_shaft__001", 10, MAT_BAR_KNURL, True),
    "bar_collar__005": ("bar_collar__001", 8, MAT_SILVER, True),
    "ez_bar__002": ("ez_bar__002", 12, MAT_SILVER, True),
    "hex_bar_frame__001": ("hex_bar_frame__001", 8, MAT_FRAME, False),
    "handle_bridge__006": ("hex_bar_frame__001", 8, MAT_FRAME, False),
    "handle_support__006": ("hex_bar_frame__001", 8, MAT_FRAME, False),
    "hand_grip__002": ("barbell_shaft__001", 8, MAT_BAR_KNURL, True),
    "hand_grip__009": ("barbell_shaft__001", 10, MAT_BAR_KNURL, True),
    "bar_sleeve__004": ("bar_sleeve__001", 10, MAT_CHROME, True),
    "sleeve_shoulder__001": ("sleeve_shoulder__004", 10, MAT_CHROME, True),
    "sleeve_shoulder__003": ("sleeve_shoulder__004", 10, MAT_CHROME, True),
    "sleeve_shoulder__004": ("sleeve_shoulder__004", 8, MAT_CHROME, True),
}


def fit_round_profile(ring, sides):
    """Keep the scene samples and the original polygon's corners and contact planes."""
    degrees = np.rint(np.degrees(np.arctan2(ring[:, 0], ring[:, 1]))).astype(int) % 360
    step = 360 / sides
    angles = np.union1d(degrees, np.arange(sides) * step)
    radius = np.linalg.norm(ring, axis=1).mean()
    radius *= np.cos(np.radians(step / 2)) / np.cos(np.radians(angles % step - step / 2))
    return radius[:, None] * np.column_stack((np.sin(np.radians(angles)), np.cos(np.radians(angles))))


def round_parts(source, sides, material, smooth):
    if "ring" in source:
        ring = np.array(source["ring"])
        # The authored curve is fitted one straight segment at a time in the app.
        # Use the scene's cylindrical cross section with each segment's own length.
        half_length = np.ptp(np.array(source["v"])[:, 0]) / 2
    else:
        verts = np.array(source["v"])
        half_length = verts[:, 2].max()
        ring = verts[verts[:, 2] == half_length, :2]
    profile = fit_round_profile(ring, sides)
    n = len(profile)
    i = np.arange(n)
    j = np.roll(i, -1)
    wall = np.column_stack((np.tile(i, 2), np.r_[i + n, j + n], np.r_[j + n, j]))
    v = np.vstack((np.c_[profile, np.full(n, -half_length)], np.c_[profile, np.full(n, half_length)]))
    # Each subdivided edge shares its cap boundary. A centre fan also avoids
    # degenerate faces where adjacent samples lie on the same contact plane.
    caps = np.column_stack((np.repeat([2 * n, 2 * n + 1], n), np.r_[i, j + n], np.r_[j, i + n]))
    end_material = MAT_CHROME if material == MAT_BAR_KNURL else material
    return np.ptp(v, axis=0), [
        (v, wall.ravel(), smooth, material),
        (np.vstack((v, [[0, 0, -half_length], [0, 0, half_length]])), caps.ravel(), False, end_material),
    ]


def check_round_target(name, old, sides):
    theta = np.arange(sides) * (2 * np.pi / sides)
    expected = np.column_stack((np.sin(theta), np.cos(theta)))
    h = old.max(0)
    radial = old[:, :2] / np.linalg.norm(old[:, :2], axis=1)[:, None]
    if (
        len(old) != 2 * sides
        or not np.allclose(abs(old[:, 2]), h[2], atol=0.00001)
        or not np.allclose(np.linalg.norm(old[:, :2], axis=1), h[1], atol=0.00001)
        or np.max(np.min(np.linalg.norm(radial[:, None] - expected, axis=2), axis=1)) > 0.001
    ):
        raise ValueError(f"{name}: grip or tube differs from the {sides}-plane source")


def parts(group, source, *, mat_size=(0.660, 1.850, 0.025)):
    """Preserve scene resolution and keep smooth sides separate from flat end normals."""
    if group in ROUND_PROFILES:
        _, sides, material, smooth = ROUND_PROFILES[group]
        return round_parts(source, sides, material, smooth)
    v = np.array(source["v"])
    t = np.array(source["t"])
    sides = np.array(source["smooth"])
    if group == "barbell_shaft__001":
        # The authored 24-sided shaft has twice the app grip's angular resolution.
        # Put intermediate vertices on the existing 12 grip planes. Knurl is shading only.
        phase = np.rint(np.arctan2(v[:, 0], v[:, 1]) * 12 / np.pi).astype(int)
        middle = phase % 2 == 1
        v[middle, :2] *= np.cos(np.pi / 12)
        # The projected ring has collinear neighbors. Fan each end about its center
        # so the flat end shares every boundary vertex without zero-area triangles.
        caps = []
        for sign in (-1, 1):
            ring = np.flatnonzero(sign * v[:, 2] > 0)
            ring = ring[np.argsort(-sign * phase[ring])]
            caps.extend(zip(np.full(len(ring), len(v)), ring, np.roll(ring, -1)))
            v = np.vstack((v, [0, 0, v[ring[0], 2]]))
        t = np.vstack((t[sides], caps))
        sides = np.r_[sides[sides], np.zeros(len(caps), dtype=bool)]
    if group == "floor_mat__002":
        # Preserve the moulded rim and the flat upper contact surface. Only resize the middle.
        for axis, size in enumerate(mat_size):
            v[:, axis] = _nine(v[:, axis], np.ptp(v[:, axis]) / 2, size / 2, 0.016)
    dims = np.ptp(v, axis=0)
    result = []
    for smooth in (True, False):
        faces = t[sides == smooth]
        if len(faces):
            used, remap = np.unique(faces, return_inverse=True)
            material = MAT_BAR_KNURL if group == "barbell_shaft__001" and smooth else MATERIALS[group]
            result.append((v[used], remap.ravel(), smooth, material))
    return dims, result


def assemble(raw, mapping, prototypes, frames, times, skin_faces):
    rows, audit = [], {}
    for name, (index, group) in mapping.items():
        obj = raw["objects"][index]
        if obj["name"] != name:
            raise ValueError(f"{name}: stale target index")
        old = np.asarray(obj["verts"]).reshape(-1, 3)
        low, high = old.min(0), old.max(0)
        if not np.allclose(low, -high, atol=0.00001):
            raise ValueError(f"{name}: target is off its local centre")
        p, q, s = decompose_frames(strip_fake_animation(obj["m"]))
        if np.any(s <= 0) or not np.allclose(s, s[0], atol=0.00001):
            raise ValueError(f"{name}: unsupported scale track")
        dims, mesh_parts, color = prototypes[group]
        if group == "floor_mat__002" and (len(p) != 1 or not np.allclose(high - low, dims, atol=0.00001)):
            raise ValueError(f"{name}: fixed mat moved or changed size")
        scale = s * (high - low) / dims
        fitted = np.vstack([v for v, *_ in mesh_parts]) * scale[0]
        if group == "barbell_shaft__001":
            check_round_target(name, old, 12)
        elif group in ROUND_PROFILES:
            check_round_target(name, old, ROUND_PROFILES[group][1])
        check = penetration(
            frames, skin_faces, times, np.asarray(raw["acts"], "<f4"),
            old * s[0], fitted, p, q,
        )
        if check["added_hull_mm"] > 10:
            raise ValueError(f"{name}: new body overlap exceeds 10 mm: {check}")
        for v, t, smooth, material in mesh_parts:
            rows.append(dict(name=name, verts=v, tris=t, color=color,
                             mat=material, smooth=smooth, pos=p, quats=q, sc=scale))
        audit[name] = dict(group=group, frames=len(p), adjustment_axis=None,
                           old_triangles=len(obj["tris"]) // 3,
                           new_triangles=sum(len(t) // 3 for _, t, *_ in mesh_parts), collision=check)
    return rows, audit


def upgrade(view, batch=1):
    prototypes = {}

    def build_model(key, raw, mapping, source, frames, base):
        if frames is None or len(frames) < 2:
            raise ValueError("missing posed character samples")
        path = view / "human_v5" / (key + ".bin")
        times = np.frombuffer(path.read_bytes(), "<f4", len(frames), 40)
        for group in {group for _, group in mapping.values()} - prototypes.keys():
            source_group = ROUND_PROFILES[group][0] if group in ROUND_PROFILES else group
            obj = source[source_group]
            prototypes[group] = (*parts(group, obj), obj["rgb"])
        return assemble(raw, mapping, prototypes, frames, times, np.asarray(base["triangles"]).reshape(-1, 3))

    suffix = "" if batch == 1 else "_02"
    return append_batch(view, targets_file=f"rest_bar_targets{suffix}.json", source_file="scene_rest_bar_source.json",
                        report_file=f"rest_bar_fit{suffix}.json", build_model=build_model)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("viewer", type=Path)
    parser.add_argument("--batch", type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    upgrade(args.viewer, args.batch)
