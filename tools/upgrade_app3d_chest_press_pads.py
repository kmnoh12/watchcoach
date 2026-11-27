"""Chest press upholstery. Append after the pin stations (their V6 seats already fit)."""

import argparse
from pathlib import Path

import numpy as np
from upgrade_app3d_adjust_bench import HERE, append_batch, load, object_pose
from upgrade_app3d_bench_pads import cushion
from upgrade_app3d_lower_press_pads import common_shapes, world
from upgrade_app3d_lower_towers import center, vertices
from upgrade_app3d_pull_pads import foam
from upgrade_app3d_row_pads import EYE, Z, indexed_receiver
from bench_fit import fit, swept_clear
from body_fit import SkinSweep
from fixed_pad_contact import penetration
from part_registry import MAT_FRAME, MAT_ACCENT
from scene_lat_parts import palette
from selector_tower import block

TARGETS = "chest_press_pad_targets.json"
REPORT = "chest_press_pad_fit.json"
SEAT, POST, RAIL, PIN = "seat.015", "seat_post.008", "seat_slide.002", "seat_adjust.002"


def upgrade(view):
    shared = {
        g: [(v, t, col, mat, True) for v, t, mat, col in ps]
        for g, ps in common_shapes(view).items()
        if g in ("back_pad__003", "head_pad__001", "seat_pad__002")
    }
    donor = load(view / "data" / "lever_pulldown~m=pin.json")
    roller = next(o for o in donor["objects"] if o["name"] == "thigh_roller.001")
    shared["leg_roller__001"] = [
        (p.verts, p.tris, p.color, p.mat_preset, p.smooth) for p in foam(roller, 1)
    ]
    towers = load(view / "data" / "press_station_fit.json")

    def build(key, raw, mapping, flat, frames, base):
        objects = {o["name"]: o for o in raw["objects"]}
        faces = np.asarray(base["triangles"]).reshape(-1, 3)
        times = np.frombuffer(
            (view / "human_v5" / (key + ".bin")).read_bytes(), "<f4", len(frames), 40
        )
        if (
            SEAT in objects
            and SEAT not in mapping
            and SEAT not in towers.get(key, {}).get("fits", {})
        ):
            raise ValueError(
                "preceding pin station has no fitted seat; leave the model untouched"
            )
        rows, meta = [], {}

        def emit(name, mesh, origin, rot, scale, mat, color, smooth=False):
            v, t = mesh
            rows.append(
                dict(
                    name=name,
                    verts=v,
                    tris=np.ravel(t),
                    pos=np.array([origin]),
                    quats=np.array([rot.as_quat()]),
                    sc=np.array([scale]),
                    mat=mat,
                    color=color,
                    smooth=smooth,
                )
            )

        for name, (i, group) in mapping.items():
            o = objects[name]
            assert raw["objects"][i] is o
            if name in (POST, RAIL, PIN):
                continue
            p, rot, s = object_pose(o)
            old = vertices(o) * s
            dims = np.ptp(old, axis=0)
            if group.startswith("leg_roller"):
                dims[:2] = (
                    2 * np.linalg.norm(old[:, :2] - center(old)[:2], axis=1).max()
                )
            if group not in shared:
                assert name in ("back", "seat")
                shared[group] = list(cushion(flat, group.split("__")[0], dims))
            pieces = shared[group]
            proto = np.vstack([a[0] for a in pieces])
            scale = dims / np.ptp(proto, axis=0)
            anchor = center(old) - center(proto) * scale
            v = proto * scale + anchor
            origin = p.copy()
            m = meta[name] = dict(group=group, records=len(pieces), axis=None)
            if name == SEAT:
                assert np.allclose(rot.as_matrix(), np.eye(3), atol=2e-5)
                allfaces = np.vstack(
                    [
                        np.asarray(a[1]).reshape(-1, 3) + j
                        for a, j in zip(
                            pieces, np.cumsum([0] + [len(a[0]) for a in pieces[:-1]])
                        )
                    ]
                )
                _, origin, gap = fit(frames, base, "seat_pad", (p, rot), (v, allfaces))
                if not 0.002 <= gap <= 0.005:
                    raise ValueError(
                        f"{name}: gap {gap * 1000:.2f} mm outside seat range"
                    )
                m.update(
                    axis=Z.tolist(), offset=(origin - p).tolist(), gap_mm=gap * 1000
                )
                seat_bottom = v[:, 2].min() + origin[2]
                sweep = SkinSweep(frames, faces)
                if not swept_clear(sweep, rot.apply(v) + origin):
                    raise ValueError("fitted seat meets moving skin")
            else:
                hit = penetration(
                    frames, faces, times, raw["acts"], old, v, [p], [rot.as_quat()]
                )
                if hit["added_hull_mm"] > 10:
                    raise ValueError(f"{name}: added overlap {hit}")
                m["collision"] = hit
                if name == "ankle_roller":
                    m["axle"] = rot.apply(
                        Z
                    ).tolist()  # fixed between two welded posts, not a height slider
            for vv, tt, col, mat, smooth in pieces:
                emit(
                    name,
                    (vv, tt),
                    origin + rot.apply(anchor),
                    rot,
                    scale,
                    mat,
                    col,
                    smooth,
                )

        if SEAT in mapping:
            post, knob = world(objects[POST]), world(objects[PIN])
            lock = center(post)
            lock[2] = center(knob)[2]
            low, tip = post[:, 2].min(), seat_bottom - 0.003
            high = min(post[:, 2].max(), seat_bottom - 0.007, lock[2] + 0.018)
            # Leave the handle at the original fixed receiver bore, and land the inner
            # post inside a shallow steel saddle directly under the fitted cushion.
            if not lock[2] + 0.004 < high < tip:
                raise ValueError(
                    "seat cannot clear the original pin within receiver travel"
                )
            lengths = (tip - lock[2]) / (1 - (np.arange(12) + 0.5) / 12)
            valid = lengths[
                (lengths < tip - low - 0.003) & (lengths > tip - lock[2] + 0.006)
            ]
            if not len(valid):
                raise ValueError("no index hole engages the original seat pin")

            def hardware(n, shape, at, rot, sc, mat, col):
                if n == PIN and mat == MAT_ACCENT:
                    # Retain the lock axis while keeping its thumb knob below the cushion.
                    sc = [1, 1, min(1, (seat_bottom - at[2] - 0.001) / 0.012)]
                if not swept_clear(sweep, rot.apply(shape[0] * np.array(sc)) + at):
                    raise ValueError(n + ": hardware meets moving skin")
                emit(n, shape, at, rot, sc, mat, col)

            rail = indexed_receiver(
                hardware,
                POST,
                RAIL,
                PIN,
                Z,
                lock,
                low,
                high,
                tip,
                np.ptp(post[:, 0]),
                knob[:, 0].max() - lock[0],
                tip - valid.max(),
            )
            hardware(
                RAIL,
                block([0.17, 0.108, 0.006], 0.0015),
                np.r_[lock[:2], seat_bottom - 0.002],
                EYE,
                [1] * 3,
                MAT_FRAME,
                palette()["casting"],
            )
            for n in (POST, RAIL, PIN):
                meta[n] = dict(
                    group=mapping[n][1],
                    records=sum(r["name"] == n for r in rows),
                    rail=rail,
                )
            rows.sort(key=lambda r: list(meta).index(r["name"]))
        assert set(meta) == set(mapping)
        return rows, meta

    return append_batch(
        view,
        targets_file=TARGETS,
        source_file="scene_flat_bench_source.json",
        report_file=REPORT,
        build_model=build,
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("view", type=Path)
    upgrade(ap.parse_args().view)
