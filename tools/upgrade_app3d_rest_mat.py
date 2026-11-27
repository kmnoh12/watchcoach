"""Fit the gym stretching mat and ab wheel finishes to the floor exercise clips."""

import argparse
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from upgrade_app3d_adjust_bench import HERE, append_batch, load
from upgrade_app3d_adjust_bench_rest import exterior
from upgrade_app3d_machines import decompose_frames, strip_fake_animation
from upgrade_app3d_rest_bars import fit_round_profile
from fixed_pad_contact import penetration
from part_registry import MAT_FRAME, MAT_RUBBER


TARGETS = "rest_mat_targets.json"
SOURCE = "scene_rest_mat_source.json"
REPORT = "rest_mat_fit.json"
# Local axle sections (axial position, radius) in metres. Keep the flanges on
# the hand-fitted grip and the open bore around the original hub and spokes.
GRIP_SECTIONS = [(-.0655, .025), (-.0585, .025), (-.0555, .023),
                 (.0535, .023), (.0565, .025), (.0655, .025)]
TIRE_SECTIONS = [(-.030, .083), (-.030, .103), (-.023, .110),
                 (.023, .110), (.030, .103), (.030, .083)]


def rubber_shell(old, source, *, tire):
    # One grip profile fits both sides: the left grip is an end-for-end copy.
    # Keep pivots and the tread's original angular phase when the wheel rolls.
    sections, sides = (TIRE_SECTIONS, 16) if tire else (GRIP_SECTIONS, 10)
    theta = np.arange(sides) * (2 * np.pi / sides)
    if tire:
        theta += np.pi / 2
    expected = np.vstack([np.column_stack((np.full(sides, x), radius * np.cos(theta),
                                           radius * np.sin(theta))) for x, radius in sections])
    if len(old) != len(expected) or np.linalg.norm(old[:, None] - expected, axis=2).min(1).max() > .00001:
        raise ValueError("original rubber shell no longer matches its axle section")

    verts = np.asarray(source["v"])
    ring = verts[verts[:, 0] == verts[:, 0].max(), 1:]
    # Retain every circumferential sample of the scene and add the authored
    # corners. The added samples lie on the original contact planes.
    # The old grips start at +Y. Reorient the source samples before fitting.
    profile = fit_round_profile(ring, sides) if tire else fit_round_profile(ring[:, ::-1], sides)[:, ::-1]
    profile = profile / np.linalg.norm(ring, axis=1).mean()
    perimeter = np.argsort(np.arctan2(profile[:, 1], profile[:, 0]))
    profile = profile[perimeter]
    n = len(profile)
    i = np.arange(n)
    j = np.roll(i, -1)
    v = np.vstack([np.column_stack((np.full(n, x), profile * radius)) for x, radius in sections])
    walls = []
    for section in range(len(sections) if tire else len(sections) - 1):
        a, b = section * n, (section + 1) % len(sections) * n
        walls.extend([np.c_[a + i, a + j, b + j], np.c_[a + i, b + j, b + i]])
    layers = [(v, np.vstack(walls), True)]
    if not tire:
        for boundary in (v[:n][::-1], v[-n:]):
            center = [boundary[0, 0], 0., 0.]
            layers.append((np.vstack([boundary, center]), np.c_[np.full(n, n), i, j], False))
    return layers


def upgrade(view):
    mat = load(HERE / "scene_rest_bar_source.json")["floor_mat__002"]

    def build_model(key, raw, mapping, source, frames, base):
        if frames is None or frames.shape[1:] != (1401, 3) or not np.isfinite(frames).all():
            raise ValueError("missing finite new-hand poses")
        path = view / "human_v5" / (key + ".bin")
        times = np.frombuffer(path.read_bytes(), "<f4", len(frames), 40)
        acts = np.asarray(raw["acts"], "<f4")
        skin_faces = np.asarray(base["triangles"]).reshape(-1, 3)
        rows, audit = [], {}
        for name, (index, group) in mapping.items():
            role = group.split("__")[0]
            if index >= len(raw["objects"]) or raw["objects"][index]["name"] != name:
                raise ValueError(f"{name}: stale role-map index")
            obj = raw["objects"][index]
            old = np.asarray(obj["verts"]).reshape(-1, 3)
            track = strip_fake_animation(obj["m"])
            p, q, s = decompose_frames(track)
            r = Rotation.from_quat(q)
            linear = np.asarray(track).reshape(-1, 4, 4)[:, :3, :3].transpose(0, 2, 1)
            if (len(p) != (1 if role == "floor_mat" else len(acts)) or np.any(s <= 0)
                    or not np.allclose(s, s[0], atol=.00001)
                    or not np.allclose(linear, r.as_matrix() * s[:, None, :], atol=.00002)):
                raise ValueError(f"{name}: unsupported exterior track")
            color = source[role]["rgb"]
            size = np.ptp(old, axis=0)
            if not np.isfinite(old).all() or np.any(size <= 0):
                raise ValueError(f"{name}: invalid exterior bounds")
            if role == "floor_mat":
                v, t, _, material, smooth = exterior(role, {role: mat}, old, obj["tris"])
                layers, scale = [(v, t, smooth)], s * size
            elif role == "wheel_spoke":
                # The scene's red wheel insert is solid. Transfer its finish
                # to the original open spokes so the hub and bore stay visible.
                layers, material, scale = [(old, obj["tris"], False)], MAT_FRAME, s
            else:
                center = (old.min(0) + old.max(0)) / 2
                tire = role == "wheel_tire"
                if tire and np.linalg.norm(center) > .00001:
                    raise ValueError(f"{name}: tread no longer centered on the axle")
                if not tire and not np.allclose(q, q[0], atol=.00001):
                    raise ValueError(f"{name}: grip pivot rotates")
                old = old - center
                p = p + r.apply(center * s)
                # Rotate the left grip 180 degrees about local Y to share the
                # right grip shape with the slightly asymmetric flange lengths.
                reverse = not tire and center[0] < 0
                if reverse:
                    old = old * [-1, 1, -1]
                    q = (r * Rotation.from_rotvec([0, np.pi, 0])).as_quat()
                layers, material, scale = rubber_shell(old, source[role], tire=tire), MAT_RUBBER, s

            fitted = np.vstack([v for v, _, _ in layers]) * scale[0]
            check = penetration(frames, skin_faces, times, acts, old * s[0], fitted, p, q)
            if check["added_hull_mm"] > 10:
                raise ValueError(f"{name}: added body overlap: {check}")
            for v, t, smooth in layers:
                rows.append(dict(name=name, verts=v, tris=np.ravel(t), color=color, mat=material,
                                 smooth=smooth, pos=p, quats=q, sc=scale))
            audit[name] = dict(group=group, frames=len(p), records=len(layers),
                               adjustment_axis=None, collision=check)
        return rows, audit

    return append_batch(view, targets_file=TARGETS, source_file=SOURCE,
                        report_file=REPORT, build_model=build_model)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("viewer", type=Path)
    upgrade(parser.parse_args().viewer)
