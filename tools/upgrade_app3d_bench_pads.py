"""Fixed bench upholstery overlays. Run on the final posed hand bundle after prior overlays."""

import argparse
from pathlib import Path

import numpy as np

from upgrade_app3d_adjust_bench import HERE, append_batch, load
from upgrade_app3d_machines import decompose_frames, strip_fake_animation
from scene_lat_parts import _nine
from fixed_pad_contact import penetration
from part_registry import MAT_PAD, MAT_RUBBER


def cushion(source, role, size):
    # Choose the long cushion for single-piece tops. The scene trim spans BOTH seats;
    # fit its own ends below each cushion, never bridge the gap with a redundant board.
    skin = source[role]
    v = np.vstack([x["v"] for x in skin])
    lo, hi = v.min(0), v.max(0)
    trim = source["trim"][0]
    tv = np.asarray(trim["v"])
    a, b = tv.min(0), tv.max(0)
    z0, z1 = min(lo[2], a[2]), hi[2]
    for slot in [*skin, trim]:
        v = np.array(slot["v"])
        is_trim = slot is trim
        for j, band in enumerate([0.04, 0.07]):
            lower, upper = (a[j], b[j]) if is_trim else (lo[j], hi[j])
            # Source underside sits 10 mm inside the padded outside edges.
            v[:, j] = _nine(
                v[:, j] - (lower + upper) / 2,
                (upper - lower) / 2,
                size[j] / 2 - (0.01 if is_trim else 0),
                band,
            )
        v[:, 2] = _nine(v[:, 2] - (z0 + z1) / 2, (z1 - z0) / 2, size[2] / 2, 0.018)
        yield (
            v,
            np.array(slot["t"]),
            slot["rgb"],
            MAT_RUBBER if is_trim else MAT_PAD,
            not is_trim,
        )


def wrap(size, shaft_radius):
    """Use the saved foam roller profile, not its rigid end cap. A bar wrap instead has
    a through bore and a longitudinal slit. Keep full scene angular resolution and end rings."""
    src = load(HERE / "scene_lat_source.json")
    roll = src["roller"]
    faces = np.asarray(roll["tri"])
    v = (
        np.asarray(roll["verts"])[np.unique(faces[np.asarray(roll["material"]) == 0])]
        * 1e-6
    )
    profile = []
    for z in np.unique(v[:, 2]):
        ring = v[v[:, 2] == z, :2]
        rr = np.linalg.norm(ring, axis=1)
        profile.append((z, rr.max()))
    res = np.count_nonzero(rr > 0.001)
    assert res == 32 and len(profile) == 8
    # Continue the open lip with the opposite rounded shoulder; remove no foam rings.
    profile += [(-z, r) for z, r in reversed(profile[:3]) if -z > profile[-1][0]]
    h = max(z for z, _ in profile)
    radius = max(r for _, r in profile)
    bore = shaft_radius + 0.0004
    assert np.isclose(size[0], size[1]) and 0 < bore < size[0] / 2
    outer = [
        (float(_nine(z, h, size[2] / 2, 0.032)), r / radius * size[0] / 2)
        for z, r in profile
    ]
    # Seam opposite the body-facing underside (local -X points up on this shaft). Close both cut faces.
    theta = np.linspace(np.pi + 0.035, 3 * np.pi - 0.035, res + 1)
    n = res + 1
    m = len(outer)
    verts = []
    triangles = []

    def quad(a, b, c, d):
        triangles.extend([[a, b, c], [a, c, d]])

    # Matching rows on the bore close both cut faces without T-junctions.
    for z, r in outer:
        for rad in [r, bore]:
            verts.extend([(rad * np.cos(t), rad * np.sin(t), z) for t in theta])
    for i in range(m - 1):
        a = 2 * i * n
        b = a + 2 * n
        for j in range(res):
            quad(a + j, a + j + 1, b + j + 1, b + j)
            quad(a + n + j, b + n + j, b + n + j + 1, a + n + j + 1)
        quad(a, b, b + n, a + n)
        quad(a + res, a + n + res, b + n + res, b + res)
    for j in range(res):
        a = 2 * (m - 1) * n + j
        quad(j, j + n, j + n + 1, j + 1)
        quad(a, a + 1, a + n + 1, a + n)
    return (
        np.asarray(verts),
        np.asarray(triangles).ravel(),
        src["palette"]["pad"],
        MAT_PAD,
        True,
    )


def batch_files(batch):
    suffix = {1: "", 2: "_02", 3: "_03", 4: "_04"}[batch]
    return f"bench_pad_targets{suffix}.json", f"bench_pad_fit{suffix}.json"


def upgrade(view, batch=1):
    shapes = {}

    def assemble(key, raw, mapping, source, frames, base):
        rows = []
        meta = {}
        for name, (idx, group) in mapping.items():
            o = raw["objects"][idx]
            assert name == o["name"]
            old = np.array(o["verts"]).reshape(-1, 3)
            dims = np.ptp(old, axis=0)
            assert np.max(abs(old.max(0) + old.min(0))) < 1e-6
            p, q, s = decompose_frames(strip_fake_animation(o["m"]))
            role = group.split("__")[0]
            if group not in shapes:
                if role == "hip_pad":
                    shaft = next(
                        x for x in raw["objects"] if x["name"] == "barbell_shaft"
                    )
                    if not np.allclose(shaft["m"], o["m"], atol=0.00003):
                        raise ValueError("wrap is not coaxial with moving shaft")
                    radius = np.max(
                        np.linalg.norm(
                            np.array(shaft["verts"]).reshape(-1, 3)[:, :2], axis=1
                        )
                    )
                    prototype = [wrap(dims, radius)]
                elif role == "knee_pad":
                    # Loose kneeling mat on the floor, not a bench with a rigid pan.
                    from upgrade_app3d_rest_bars import parts as mat_parts

                    mat = load(HERE / "scene_rest_bar_source.json")["floor_mat__002"]
                    _, layers = mat_parts("floor_mat__002", mat, mat_size=dims)
                    prototype = [(v, t, mat["rgb"], m, sm) for v, t, sm, m in layers]
                else:
                    shape = (
                        "back_pad"
                        if role == "back_pad" or dims[1] > 0.6
                        else "seat_pad"
                    )
                    prototype = list(cushion(source, shape, dims))
                shapes[group] = dims, prototype
            template, parts = shapes[group]
            scale = s * (dims / template)
            if role != "hip_pad" and len(p) != 1:
                raise ValueError("fixed bench has an adjustable or moving pad")
            assert np.max(abs(s - s[0])) < 1e-6
            hp = view / "human_v5" / (key + ".bin")
            times = np.frombuffer(hp.read_bytes(), "<f4", len(frames), 40)
            check = penetration(
                frames,
                np.asarray(base["triangles"]).reshape(-1, 3),
                times,
                np.array(raw["acts"], "<f4"),
                old * s[0],
                np.vstack([x[0] for x in parts]) * scale[0],
                p,
                q,
            )
            if check["added_hull_mm"] > 10:
                raise ValueError(f"{name}: new skin overlap exceeds 1 cm ({check})")
            for v, t, color, mat, smooth in parts:
                rows.append(
                    dict(
                        name=name,
                        verts=v,
                        tris=t,
                        color=color,
                        mat=mat,
                        smooth=smooth,
                        pos=p,
                        quats=q,
                        sc=scale,
                    )
                )
            meta[name] = dict(
                group=group,
                adjustment_axis=None,
                attachment={"hip_pad": "bar_shaft", "knee_pad": "floor"}.get(role, "fixed_mount"),
                records=len(parts),
                collision=check,
            )
        return rows, meta

    targets_file, report_file = batch_files(batch)
    return append_batch(
        view,
        targets_file=targets_file,
        source_file="scene_flat_bench_source.json",
        report_file=report_file,
        build_model=assemble,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("viewer", type=Path)
    parser.add_argument("--batch", type=int, choices=(1, 2, 3, 4), default=1)
    args = parser.parse_args()
    upgrade(args.viewer, args.batch)
