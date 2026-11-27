"""Append scene upholstery to lower sleds, presses and auxiliary machines on final V6 skin."""

import argparse
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

from upgrade_app3d_adjust_bench import HERE, append_batch, load
from upgrade_app3d_lower_pads import (
    X,
    Z,
    build_layers,
    clearance,
    folded_skin,
    profile_back,
)
from upgrade_app3d_lower_towers import center, pose, vertices
from upgrade_app3d_pull_stations import _nine_mesh
from upgrade_app3d_row_pads import indexed_receiver
from body_fit import SkinSweep, contact_region
from bench_fit import swept_clear
from fixed_pad_contact import penetration
from part_registry import MAT_FRAME, MAT_PAD
from scene_lat_parts import build_seat, palette
from selector_tower import block

TARGETS = "lower_pad_targets_02.json"
REPORT = "lower_pad_fit_02.json"
I = Rotation.identity()
POST = {
    "leg_press_45": "mopt_seat_stem",
    "leg_press_calf": "seat_support",
    "torso_rotation_machine": "seat_column",
    "leg_press_horizontal": "seat_post.008",
}
SUPPORT = {"torso_rotation_machine": "seat_mount", "leg_press_horizontal": "seat_frame"}


def world(o):
    p, r, s = pose(o)
    return r[0].apply(vertices(o) * s[0]) + p[0]


def upholstery(parts, dims):
    h = np.ptp(np.vstack([a["v"] for a in parts]), axis=0) / 2
    return [
        (
            _nine_mesh(a["v"], h, dims / 2),
            a["t"],
            MAT_PAD,
            palette()[("pad", "stitch")[a["slot"]]],
        )
        for a in parts
    ]


def common_shapes(view):
    # Recreate the preceding row / Nordic prototypes, not new near-identical PIDs.
    d = view / "data"

    def donor(k, n):
        return next(o for o in load(d / (k + ".json"))["objects"] if o["name"] == n)

    chest = load(HERE / "scene_pull_source.json")["chest_pad"]
    shared = {}
    for group, key, name in [
        ("back_pad__003", "pullover_machine", "back"),
        ("head_pad__001", "pullover_machine", "headrest"),
        ("seat_pad__002", "plate_row", "seat.001"),
        ("seat_pad__013", "seated_row_machine", "seat.001"),
    ]:
        v = vertices(donor(key, name))
        dims = np.ptp(v, axis=0)
        pieces = (
            [
                (p.verts, p.tris, p.mat_preset, p.color)
                for p in build_seat(v.min(0), v.max(0))
            ]
            if group.startswith("seat_")
            else upholstery(chest, dims)
        )
        shared[group] = pieces
    cache = {}
    roller = load(HERE / "scene_lower_tower_source.json")["leg_roller"]
    shared["leg_roller__003"] = build_layers(
        {},
        roller,
        "leg_roller",
        "leg_roller__003",
        donor("nordic_curl", "ankle_roller"),
        cache,
    )[0]
    return shared


def pad_geometry(source, shared, group, obj):
    v = vertices(obj)
    dims = np.ptp(v, axis=0)
    role = group.split("__")[0]
    orient = I
    if role == "leg_roller":
        dims[:2] = 2 * np.linalg.norm(v[:, :2] - center(v)[:2], axis=1).max()
    if group not in shared:
        thin = dims.argmin()
        prototype = (
            "back_pad"
            if thin == 1
            else "seat_pad"
            if role in ("seat_pad", "start_mat")
            else "thigh_pad"
        )
        parts = upholstery(source[prototype], dims)
        if role == "back_pad" and thin == 1:
            parts = [
                (*profile_back(mesh * [-1, -1, 1], t, v - center(v)), m, c)
                for mesh, t, m, c in parts
            ]
        shared[group] = parts
    parts = shared[group]
    if role == "shoulder_pad":
        orient = Rotation.from_euler("x", 180, degrees=True)  # wearer below the pad
    vv = np.vstack([a[0] for a in parts])
    size = np.ptp(vv, axis=0)
    scale = dims / size
    # Profiled lumbar surfaces already follow the exact sloped legacy front and rear.
    c = center(v) - orient.apply(center(vv) * scale)
    return parts, scale, c, orient


def ankle_setting(skin, base, obj, lever, surf):
    p, r, _ = pose(obj)
    lp, lr, _ = pose(lever)
    axis = r[0].inv().apply(lr[0].apply(X))
    travel = r[0].inv().apply(world(lever) - p[0]) @ axis
    # Try both sides with the common body fitter. Check the *whole* feasible lever
    # length against skin samples inside the middle of the roller, not the cap.
    hints = [
        clearance(skin, base, "ankle_roller", surf, sign * axis, Z) for sign in (-1, 1)
    ]
    faces = contact_region(base, "ankle_roller")[0]
    pts = np.vstack([skin.reshape(-1, 3), skin[:, faces].mean(2).reshape(-1, 3)])
    vv = surf[0][0]
    half = np.ptp(vv[:, 2]) / 2 - 0.041
    pts = pts[abs(pts[:, 2]) < half]
    step = np.linspace(travel.min(), travel.max(), 601)
    nearest = cKDTree(pts[:, :2]).query(step[:, None] * axis[:2])[0]
    # Inscribed barrel radius from a central ring, conservative for angular facets.
    middle = vv[np.abs(vv[:, 2]) == np.min(np.abs(vv[:, 2]))]
    radius = np.linalg.norm(middle[:, :2], axis=1).max() * 0.96
    depth = radius - nearest.max() - (step[1] - step[0]) / 2
    if depth > 0:
        raise ValueError(
            f"ankle roller: common axial gaps {np.round(1000 * np.array(hints), 1).tolist()} mm; skin enters central barrel by at least {depth * 1000:.1f} mm at every setting on {np.ptp(travel) * 1000:.1f} mm lever"
        )
    raise ValueError(
        "ankle roller: no verified indexed axle attachment on the solid lever"
    )


def upgrade(view):
    shared = common_shapes(view)

    def build(key, raw, mapping, source, frames, base):
        objs = {o["name"]: o for o in raw["objects"]}
        acts = raw["acts"]
        faces = np.array(base["triangles"]).reshape(-1, 3)
        times = np.frombuffer(
            (view / "human_v5" / (key + ".bin")).read_bytes(), "<f4", len(frames), 40
        )
        rows = []
        meta = {}
        positions = {}
        shoulders = []
        sweep = SkinSweep(frames, faces) if key in POST else None

        def emit(n, shape, at, rot, sc, mat, col, smooth=False):
            v, t = shape
            rows.append(
                dict(
                    name=n,
                    verts=v,
                    tris=np.ravel(t),
                    pos=np.atleast_2d(at),
                    quats=np.atleast_2d(rot.as_quat()),
                    sc=np.atleast_2d(sc),
                    mat=mat,
                    color=col,
                    smooth=smooth,
                )
            )

        for n, (idx, group) in mapping.items():
            o = objs[n]
            assert raw["objects"][idx] is o
            role = group.split("__")[0]
            if not (role.endswith("_pad") or role in ("leg_roller", "start_mat")):
                continue
            parts, scale, c, orient = pad_geometry(source, shared, group, o)
            p, r, s = pose(o)
            assert np.allclose(s, s[0], atol=2e-5) and np.allclose(
                s[0], s[0, 0], atol=2e-5
            )
            surf = [
                ((orient.apply(v * scale) + c) * s[0], np.array(t).reshape(-1, 3))
                for v, t, *_ in parts
            ]
            vv = np.vstack([a[0] for a in surf])
            old = vertices(o) * s[0]
            m = meta[n] = dict(group=group, records=len(parts), axis=None)
            shift = np.zeros(3)
            if role == "leg_roller":
                ankle_setting(
                    folded_skin(frames, times, acts, o),
                    base,
                    o,
                    objs["shin_lever"],
                    surf,
                )
            if key == "standing_calf":
                skin = folded_skin(frames, times, acts, o)
                shoulders.append(clearance(skin, base, "back_pad", surf, -Z, X))
            if role == "seat_pad" and key in POST:
                assert len(p) == 1 and np.allclose(
                    r[0].as_matrix(), np.eye(3), atol=2e-5
                )
                g = clearance(
                    folded_skin(frames, times, acts, o), base, "seat_pad", surf, Z, X
                )
                shift = Z * (g - 0.0035)
                positions[n] = r[0].apply(vv) + p[0] + shift
                if not swept_clear(sweep, positions[n]):
                    raise ValueError(n + ": V6 skin intersects fitted seat")
                m.update(axis=Z.tolist(), offset=shift.tolist(), gap_mm=3.5)
            else:
                hit = penetration(frames, faces, times, acts, old, vv, p, r.as_quat())
                m["collision"] = hit
                if hit["added_hull_mm"] > 10:
                    raise ValueError(n + f": added hull overlap {hit}")
            for v, t, mat, col in parts:
                emit(
                    n,
                    (v, t),
                    p + r.apply(c * s) + shift,
                    r * orient,
                    s * scale,
                    mat,
                    col,
                    True,
                )
        if shoulders:
            # Both guide blocks move the entire yoke, including the two grips.
            # Do not slide that yoke away from the animated hands to close a pad gap.
            if not all(0.002 <= g <= 0.005 for g in shoulders):
                raise ValueError(
                    f"fore-aft tracks carry grips and both shoulder arms; at grip-preserving setting shoulder gaps {np.round(1000 * np.array(shoulders), 2).tolist()} mm"
                )
        if key in POST:
            seat, skin = next(iter(positions.items()))
            pan = skin[:, 2].min()
            shift = np.array(meta[seat]["offset"])
            post = POST[key]
            v = world(objs[post])
            lock = center(v)
            lo = v[:, 2].min()
            width = np.ptp(v[:, 0])
            tip = pan + 0.001
            carrier = SUPPORT.get(key)
            if carrier:
                plate = world(objs[carrier]) + shift
                tip = plate[:, 2].min() + 0.003
            if key == "torso_rotation_machine":
                top = world(objs["hub_disc"])[:, 2].max()
                if pan < top:
                    raise ValueError(
                        f"seat Z {1000 * shift[2]:.2f} mm: pan enters rotating hub by {1000 * (top - pan):.2f} mm"
                    )
            pin = "seat_adjuster.001" if key == "leg_press_horizontal" else post
            lock[2] = (
                center(world(objs[pin]))[2]
                if pin != post
                else tip - min(0.072, (tip - lo) * 0.42)
            )
            if pin != post and tip < lock[2] + 0.024:
                # Shorten only the underside of the stock 50 mm steel pan to clear its
                # side pin. Keep the upper mounting face, fore/aft span and bore line.
                tray_top = plate[:, 2].max()
                tray_bottom = lock[2] + 0.022
                if tray_top - tray_bottom < 0.024:
                    raise ValueError("seat Z: no room above pin for a 24 mm tray")
                tip = tray_bottom + 0.003
            if tip < lock[2] + 0.006:
                raise ValueError(
                    f"seat Z {1000 * shift[2]:.2f} mm: fitted tray bottom {(tip - 0.003) * 1000:.1f} mm, transverse pin centre {lock[2] * 1000:.1f} mm; pin cannot pass below tray into slider"
                )

            def hardware(name, shape, at, rot, sc, mat, col):
                if not swept_clear(sweep, rot.apply(shape[0] * np.asarray(sc)) + at):
                    raise ValueError(name + ": support hardware intersects moving skin")
                emit(name, shape, at, rot, sc, mat, col)

            # Sleeve remains on the base; only the perforated inner tube follows seat height.
            high = lock[2] + min(0.022, (tip - lock[2]) * 0.5)
            extent = (
                world(objs[pin])[:, 0].max() - lock[0]
                if pin != post
                else width / 2 + 0.023
            )
            # Choose an actual index, rather than rounding to one below the floor.
            lengths = (tip - lock[2]) / (1 - (np.arange(12) + 0.5) / 12)
            choices = lengths[
                (lengths <= min(0.24, tip - lo - 0.002))
                & (lengths > tip - lock[2] + 0.006)
            ]
            if not len(choices):
                raise ValueError(
                    post + ": no bore engages inside the available post length"
                )
            rail = indexed_receiver(
                hardware,
                post,
                post,
                pin,
                Z,
                lock,
                lo,
                high,
                tip,
                width,
                extent,
                tip - choices.max(),
            )
            if carrier:
                dims = np.ptp(plate, axis=0)
                dims[2] = plate[:, 2].max() - (tip - 0.003)
                at = center(plate)
                at[2] = plate[:, 2].max() - dims[2] / 2
                hardware(
                    carrier,
                    block(dims, 0.003),
                    at,
                    I,
                    np.ones(3),
                    MAT_FRAME,
                    palette()["casting"],
                )
            else:
                # Saddle must lie wholly below the crown and bolt into the slider.
                hardware(
                    post,
                    block([0.19, 0.10, 0.010], 0.003),
                    np.array([lock[0], lock[1], pan - 0.003]),
                    I,
                    np.ones(3),
                    MAT_FRAME,
                    palette()["casting"],
                )
            if key == "leg_press_calf":
                # The stock rear seat stub misses the crossmember. Tie it to BOTH floor runners.
                feet = [world(objs[n]) for n in ("foot.004", "foot.005")]
                xmin, xmax = sorted(center(f)[0] for f in feet)
                z = min(lo - 0.008, min(f[:, 2].max() for f in feet) - 0.014)
                hardware(
                    post,
                    block([xmax - xmin, 0.054, 2 * (lo - z + 0.004)], 0.004),
                    np.array([(xmin + xmax) / 2, lock[1], z]),
                    I,
                    np.ones(3),
                    MAT_FRAME,
                    palette()["casting"],
                )
            for n in dict.fromkeys(n for n in (post, pin, carrier) if n):
                meta[n] = dict(
                    group=mapping[n][1],
                    records=sum(a["name"] == n for a in rows),
                    rail=rail,
                )
            # Keep layers contiguous for independent wire inspection.
            rows.sort(key=lambda row: list(meta).index(row["name"]))
        assert {a["name"] for a in rows} == set(mapping)
        return rows, meta

    return append_batch(
        view,
        targets_file=TARGETS,
        source_file="scene_lower_pad_source.json",
        report_file=REPORT,
        build_model=build,
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("view", type=Path)
    upgrade(ap.parse_args().view)
