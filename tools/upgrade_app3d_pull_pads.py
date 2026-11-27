"""Append pull-station pad layers after tower and plate overlays, without duplicating pin stations."""

import argparse
from pathlib import Path

import numpy as np
from fixed_pad_contact import penetration
from part_registry import MAT_PAD
from pull_pad_fit import vertical_gap
from scene_lat_parts import build_roller, build_seat, palette
from scipy.spatial.transform import Rotation
from upgrade_app3d_adjust_bench import HERE, append_batch, load, object_pose
from upgrade_app3d_bench_pads import cushion
from upgrade_app3d_pull_stations import (
    _nine_mesh,
    verify_skin,
    vertices,
)
from upgrade_app3d_pull_stations import (
    assemble as lever,
)

TARGETS = "pull_pad_targets.json"
REPORT = "pull_pad_fit.json"


def foam(obj, sign):
    v = vertices(obj)
    r = np.linalg.norm(v[:, :2], axis=1).max()
    return build_roller([-r, -r, v[:, 2].min()], [r, r, v[:, 2].max()], sign)


def local_parts(parts):
    return [(p.verts, p.tris, p.color, p.mat_preset, p.smooth) for p in parts]


def world_parts(obj, pieces):
    p, r, s = object_pose(obj)
    return [(r.apply(v * s) + p, t) for v, t, *_ in pieces]


def shared_axle_trial(objects, frames, base):
    # Both foams are on ONE original cross-shaft. Solve for feasible travel intervals,
    # not two independent offsets which would separate them from the indexed slide.
    gaps = []
    center, rot, _ = object_pose(objects["roller_cross_axle"])
    axle = rot.apply([0, 0, 1])
    for name in ("thigh_roller", "thigh_roller.001"):
        o = objects[name]
        p, r, _ = object_pose(o)
        assert np.linalg.norm(np.cross(p - center, axle)) < 1e-5
        pieces = local_parts(foam(o, int(np.sign(p[0] * r.apply([0, 0, 1])[0]))))
        gaps.append(vertical_gap(frames, base, "thigh_roller", world_parts(o, pieces)))
    lo, hi = 0.002 - min(gaps), 0.005 - max(gaps)
    seat = objects["seat"]
    v = vertices(seat)
    crown = world_parts(seat, local_parts(build_seat(v.min(0), v.max(0))))
    seat_gap = vertical_gap(frames, base, "seat_pad", crown)
    # Most favourable endpoint of the allowed 2–5 mm interval, before the pan hits the socket.
    pan = min(v[:, 2].min() for v, _ in crown)
    post = objects["seat_outer_post"]
    p, r, s = object_pose(post)
    sleeve_top = (r.apply(vertices(post) * s) + p)[:, 2].max()
    pan_margin = pan + seat_gap - 0.002 - sleeve_top
    if lo > hi:
        raise ValueError(
            f"common horizontal axle {axle.round(6).tolist()}, vertical adjustment: "
            f"no shared 2–5 mm setting (surface gaps {gaps[0] * 1000:.3f}/{gaps[1] * 1000:.3f} mm; "
            f"dz must be >= {1000 * lo:.3f} and <= {1000 * hi:.3f} mm); "
            f"seat Z: initial surface gap {1000 * seat_gap:.3f} mm, "
            f"highest permissible pan vs sleeve {1000 * pan_margin:.3f} mm"
        )
    raise ValueError(
        "shared-height setting needs indexed column and seat travel verification"
    )


def upgrade(view):
    flat = load(HERE / "scene_flat_bench_source.json")

    def build(key, raw, mapping, source, frames, base):
        objects = {o["name"]: o for o in raw["objects"]}
        assert all(raw["objects"][i]["name"] == n for n, (i, _) in mapping.items())
        times = np.frombuffer(
            (view / "human_v5" / f"{key}.bin").read_bytes(), "<f4", len(frames), 40
        )
        faces = np.asarray(base["triangles"]).reshape(-1, 3)
        if "roller_cross_axle" in objects:
            shared_axle_trial(objects, frames, base)
        if "seat_sleeve" in objects:
            rows, fits = lever(key, raw, mapping, source, frames, base)
            assert {e["name"] for e in rows} == set(mapping)
            verify_skin(rows, times, frames, raw["acts"], faces)
            return rows, fits
        rows, meta = [], {}
        for name, (_, group) in mapping.items():
            obj = objects[name]
            p, r, s = object_pose(obj)
            v = vertices(obj)
            size = np.ptp(v, axis=0)
            assert np.allclose(v.min(0), -v.max(0), atol=1e-6)
            orient = Rotation.identity()
            if name == "bench":
                pieces = list(cushion(flat, "back_pad", size))
            elif group.startswith("seat_pad__"):
                pieces = local_parts(build_seat(v.min(0), v.max(0)))
            elif group.startswith("leg_roller__"):
                axle = r.apply([0, 0, 1])
                center = object_pose(objects["roller_axle"])[0]
                assert np.linalg.norm(np.cross(p - center, axle)) < 1e-5
                if np.sign(axle[0] * p[0]) < 0:
                    orient = Rotation.from_euler("x", 180, degrees=True)
                pieces = local_parts(
                    foam(obj, 1)
                )  # One outward cap, mounted from opposite ends.
            else:
                assert group.startswith("chest_pad__")
                slots = source["chest_pad"]
                half = np.ptp(np.vstack([a["v"] for a in slots]), axis=0) / 2
                pieces = [
                    (
                        _nine_mesh(a["v"], half, size / 2),
                        a["t"],
                        palette()[("pad", "stitch")[a["slot"]]],
                        MAT_PAD,
                        True,
                    )
                    for a in slots
                ]
            posed = r * orient
            new = np.vstack([orient.apply(x[0] * s) for x in pieces])
            hit = penetration(
                frames,
                faces,
                times,
                raw["acts"],
                v * s,
                new,
                p[None],
                r.as_quat()[None],
            )
            if hit["added_hull_mm"] > 10:
                raise ValueError(
                    f"{name}: proposed overlap increases by {hit['added_hull_mm']} mm"
                )
            meta[name] = {
                "group": group,
                "adjustment_axis": None,
                "records": len(pieces),
                "collision": hit,
            }
            if group.startswith("leg_roller__"):
                meta[name]["axle"] = axle.tolist()
            for mesh, tris, color, mat, smooth in pieces:
                rows.append(
                    {
                        "name": name,
                        "verts": mesh,
                        "tris": np.ravel(tris),
                        "color": color,
                        "mat": mat,
                        "smooth": smooth,
                        "pos": p[None],
                        "quats": posed.as_quat()[None],
                        "sc": s[None],
                    }
                )
        return rows, meta

    return append_batch(
        view,
        targets_file=TARGETS,
        source_file="scene_pull_source.json",
        report_file=REPORT,
        build_model=build,
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("view", type=Path)
    upgrade(ap.parse_args().view)
