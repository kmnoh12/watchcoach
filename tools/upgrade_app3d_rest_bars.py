"""Apply the saved gym barbell shells and fixed exercise mat to batch b_rest_bar_01."""

import argparse
from pathlib import Path

import numpy as np

from upgrade_app3d_adjust_bench import append_batch
from upgrade_app3d_machines import decompose_frames, strip_fake_animation
from fixed_pad_contact import penetration
from part_registry import MAT_BAR_KNURL, MAT_CHROME, MAT_PAD, MAT_SILVER
from scene_lat_parts import _nine


MATERIALS = {
    "barbell_shaft__001": MAT_CHROME,
    "bar_sleeve__001": MAT_CHROME,
    "bar_collar__001": MAT_SILVER,
    "floor_mat__002": MAT_PAD,
}


def parts(group, source, *, mat_size=(0.660, 1.850, 0.025)):
    """Preserve scene resolution and keep smooth sides separate from flat end normals."""
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
            expected = np.column_stack((
                np.sin(np.arange(12) * np.pi / 6), np.cos(np.arange(12) * np.pi / 6)
            ))
            radial = old[:, :2] / high[:2]
            if len(old) != 24 or np.max(np.min(np.linalg.norm(radial[:, None] - expected, axis=2), axis=1)) > 0.001:
                raise ValueError(f"{name}: grip cross section differs from the 12-plane source")
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


def upgrade(view):
    prototypes = {}

    def build_model(key, raw, mapping, source, frames, base):
        if frames is None or len(frames) < 2:
            raise ValueError("missing posed character samples")
        path = view / "human_v5" / (key + ".bin")
        times = np.frombuffer(path.read_bytes(), "<f4", len(frames), 40)
        if not prototypes:
            prototypes.update({group: (*parts(group, obj), obj["rgb"]) for group, obj in source.items()})
        return assemble(raw, mapping, prototypes, frames, times, np.asarray(base["triangles"]).reshape(-1, 3))

    return append_batch(view, targets_file="rest_bar_targets.json", source_file="scene_rest_bar_source.json",
                        report_file="rest_bar_fit.json", build_model=build_model)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("viewer", type=Path)
    upgrade(parser.parse_args().viewer)
