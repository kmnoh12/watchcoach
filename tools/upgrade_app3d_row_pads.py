"""Lever-row support skins. Existing tower fits precede these additive WGM2 layers."""

import argparse
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation
from upgrade_app3d_adjust_bench import HERE, append_batch, load, object_pose, tube
from upgrade_app3d_machines import decompose_frames, strip_fake_animation
from upgrade_app3d_pull_pads import local_parts, shared_axle_trial
from upgrade_app3d_pull_stations import _nine_mesh, slider_bottom, vertices, world
from body_fit import SkinSweep, fit_body_part
from bench_fit import swept_clear
from fixed_pad_contact import penetration
from pull_pad_fit import axial_gap
from scene_lat_parts import build_roller, build_seat, palette
from selector_tower import cylinder, drilled_slider
from part_registry import MAT_FRAME, MAT_CHROME, MAT_ACCENT, MAT_PAD

TARGETS = "pull_pad_targets_02.json"
REPORT = "pull_pad_fit_02.json"
X, Y, Z = np.eye(3)
EYE = Rotation.identity()


def indexed_receiver(
    emit, socket, slider, pin, axis, lock, low, high, tip, width, pin_end, rail_bottom
):
    """Hollow tube and bored collar straddle the original pin at the same world line.
    Stretch the perforated inner rail between a real engaged bore and its attachment.
    Distances along axis are world coordinates. The rail must not escape the sleeve.
    """
    rot = EYE if axis[2] else Rotation.from_euler("x", -90, degrees=True)
    lock_at = lock @ axis
    bottom = slider_bottom(rail_bottom, tip, lock_at) if tip > lock_at else np.inf
    if not low < lock_at < high or not low <= bottom < lock_at < tip or tip < high:
        raise ValueError(f"{slider}: no engaged index hole inside the receiver travel")

    def pos(t):
        return lock + axis * (t - lock_at)

    def put(name, shape, at, sc, mat, rgb, orientation=rot):
        emit(name, shape, at, orientation, sc, mat, rgb)

    scale = width / 0.042
    steel, gray = palette()["steel"], palette()["casting"]
    band = min(0.011, high - lock_at, lock_at - low)
    put(socket, tube(True), lock, [scale, scale, band / 0.010], MAT_FRAME, gray)
    for a, b in [(low, lock_at - band), (lock_at + band, high)]:
        if b - a > 0.00001:
            put(socket, tube(), pos(a), [scale, scale, b - a], MAT_FRAME, gray)
    put(
        slider,
        drilled_slider(),
        pos(tip),
        [scale, scale, (tip - bottom) / 0.24],
        MAT_CHROME,
        steel,
    )
    # Use the smaller of the collar and inner hole radii in the pin cross section.
    radius = 0.86 * min(
        0.0038 * scale,
        0.0038 * band / 0.010,
        0.0037 * (tip - bottom) / 0.24,
        0.0037 * scale,
    )
    shaft_begin = -width / 2
    put(
        pin,
        cylinder(radius, pin_end - shaft_begin, 0, 20),
        lock + X * ((pin_end + shaft_begin) / 2),
        [1] * 3,
        MAT_CHROME,
        steel,
        EYE,
    )
    put(
        pin,
        cylinder(0.012, 0.019, 0, 20),
        lock + X * (pin_end - 0.0095),
        [1] * 3,
        MAT_ACCENT,
        [0.98, 0.61, 0.016],
        EYE,
    )
    return dict(axis=axis.tolist(), bore=lock.tolist(), tip=tip, bottom=bottom)


def upgrade(view):
    # The preceding tower batch already installs this exact unify_group on the
    # single-arm seated row. Keep its cushion and stitch PIDs on the shrug seat.
    donor = load(view / "data" / "seated_row_machine~m=single.json")
    seat = vertices(next(o for o in donor["objects"] if o["name"] == "seat.001"))
    shared = {
        "seat_pad__016": (
            np.ptp(seat, axis=0),
            local_parts(build_seat(seat.min(0), seat.max(0))),
        )
    }

    def build(key, raw, mapping, source, frames, base):
        objs = {o["name"]: o for o in raw["objects"]}
        assert all(raw["objects"][i]["name"] == n for n, (i, _) in mapping.items())
        if "roller_cross_axle" in objs:
            shared_axle_trial(objs, frames, base)
        times = np.frombuffer(
            (view / "human_v5" / f"{key}.bin").read_bytes(), "<f4", len(frames), 40
        )
        faces = np.asarray(base["triangles"]).reshape(-1, 3)
        sweep = SkinSweep(frames, faces)
        rows, meta = [], {}

        def emit(name, shape, p, r, sc, mat, rgb):
            vv, tt = shape
            p, q, sc = np.atleast_2d(p), np.atleast_2d(r.as_quat()), np.atleast_2d(sc)
            if not swept_clear(
                sweep, Rotation.from_quat(q[0]).apply(vv * sc[0]) + p[0]
            ):
                raise ValueError(f"{name}: adjustment hardware intersects moving skin")
            rows.append(
                dict(
                    name=name,
                    verts=vv,
                    tris=np.ravel(tt),
                    pos=p,
                    quats=q,
                    sc=sc,
                    mat=mat,
                    color=rgb,
                    smooth=False,
                )
            )

        for name, (_, group) in mapping.items():
            role = group.split("__")[0]
            if role not in {
                "seat_pad",
                "back_pad",
                "chest_pad",
                "head_pad",
                "arm_pad",
                "leg_roller",
            }:
                continue
            o = objs[name]
            orig = vertices(o)
            dims = np.ptp(orig, axis=0)
            p, q, s = decompose_frames(strip_fake_animation(o["m"]))
            rot = Rotation.from_quat(q[0])
            orient = EYE
            assert np.allclose(s, s[0], atol=1e-5)
            if group not in shared:
                if role == "seat_pad":
                    pieces = local_parts(build_seat(orig.min(0), orig.max(0)))
                elif role == "leg_roller":
                    radius = np.linalg.norm(orig[:, :2], axis=1).max()
                    half = np.array([radius, radius, dims[2] / 2])
                    pieces = local_parts(build_roller(-half, half, 1))
                else:
                    slots = source["chest_pad"]
                    half = np.ptp(np.vstack([a["v"] for a in slots]), axis=0) / 2
                    pieces = [
                        (
                            _nine_mesh(a["v"], half, dims / 2),
                            a["t"],
                            palette()[("pad", "stitch")[a["slot"]]],
                            MAT_PAD,
                            True,
                        )
                        for a in slots
                    ]
                shared[group] = (dims, pieces)
            size, pieces = shared[group]
            scale = s * dims / size
            pos = p.copy()
            if role == "leg_roller":
                axis = rot.apply(Z)
                center = object_pose(objs["roller_axle"])[0]
                assert np.linalg.norm(np.cross(p[0] - center, axis)) < 1e-5
                if axis[0] * p[0, 0] < 0:
                    orient = Rotation.from_euler("x", 180, degrees=True)
            local = [(orient.apply(v * scale[0]), t) for v, t, *_ in pieces]
            surf = [(rot.apply(v) + p[0], t) for v, t in local]
            offset = np.zeros(3)
            m = meta[name] = dict(group=group, records=len(pieces), axis=None)
            if role == "leg_roller":
                m["axle"] = axis.tolist()
            if (role == "chest_pad" and "chest_adjuster" in objs) or (
                role == "seat_pad" and "seat_adjuster" in objs
            ):
                axis = Z if role == "seat_pad" else Y
                anatomy = "seat_pad" if role == "seat_pad" else "back_pad"
                first = (
                    fit_body_part(
                        frames,
                        base,
                        anatomy,
                        p[0],
                        np.vstack([v for v, _ in surf]),
                        -axis,
                        X,
                    )
                    - p[0]
                )
                gap = axial_gap(
                    frames, base, anatomy, [(v + first, t) for v, t in surf], axis
                )
                offset = first + axis * (gap - 0.0035)
                pos += offset
                if not swept_clear(sweep, np.vstack([v for v, _ in surf]) + offset):
                    raise ValueError(f"{name}: fitted pad intersects skin")
                m.update(
                    axis=axis.tolist(),
                    offset=offset.tolist(),
                    gap_mm=3.5,
                    anatomy=anatomy,
                )
            else:
                hit = penetration(
                    frames,
                    faces,
                    times,
                    raw["acts"],
                    orig * s[0],
                    np.vstack([v for v, _ in local]),
                    p,
                    q,
                )
                if hit["added_hull_mm"] > 10:
                    raise ValueError(
                        f"{name}: new pad adds {hit['added_hull_mm']} mm overlap"
                    )
                m["collision"] = hit
            for vv, t, color, mat, smooth in pieces:
                rows.append(
                    dict(
                        name=name,
                        verts=vv,
                        tris=np.ravel(t),
                        color=color,
                        mat=mat,
                        smooth=smooth,
                        pos=pos,
                        quats=(Rotation.from_quat(q) * orient).as_quat(),
                        sc=scale,
                    )
                )
        if "seat_adjuster" in mapping:
            name = next(n for n in meta if n.startswith("seat"))
            pad = meta[name]
            socket = next(n for n in ("seat_outer", "seat_base") if n in mapping)
            pin = next(n for n in ("adjust_pin", "seat_pin") if n in mapping)
            box = world(objs[socket])[0]
            lock = object_pose(objs[socket])[0].copy()
            lock[2] = object_pose(objs[pin])[0][2]
            tip = world(objs[name])[0, :, 2].min() + pad["offset"][2] + 0.006
            pad["rail"] = indexed_receiver(
                emit,
                socket,
                "seat_adjuster",
                pin,
                Z,
                lock,
                box[:, 2].min(),
                box[:, 2].max(),
                tip,
                np.ptp(box[:, 0]),
                world(objs[pin])[0, :, 0].max(),
                max(box[:, 2].min() + 0.015, tip - 0.24),
            )
        if "chest_adjuster" in mapping:
            # Truncate only the upper end of the leaning post to support the new
            # horizontal socket instead of running a solid post through its pin bore.
            pin = "chest_pin"
            lock = object_pose(objs[pin])[0].copy()
            lock[0] = 0
            post = objs["chest_post"]
            pv = world(post)[0].copy()
            up = object_pose(post)[1].apply(X)
            top = pv[:, 2] > pv[:, 2].mean()
            pv[top] += (lock[2] - 0.022 - pv[top, 2])[:, None] * up / up[2]
            center = pv.mean(0)
            emit(
                "chest_post",
                (pv - center, post["tris"]),
                center,
                EYE,
                [1] * 3,
                MAT_FRAME,
                palette()["casting"],
            )
            p, r, s = object_pose(objs["chest"])
            y = r.apply(Y)
            p = p + meta["chest"]["offset"]
            dist = np.ptp(vertices(objs["chest"])[:, 1]) * s[1] / 2
            rear = p[1] + (-dist - (lock[2] - p[2]) * y[2]) / y[1]
            tip = max(lock[1] + 0.014, rear + 0.012)
            if tip > rear + 0.045:
                raise ValueError("chest slide would emerge through the upholstery")
            meta["chest"]["rail"] = indexed_receiver(
                emit,
                "chest_adjuster",
                "chest_adjuster",
                pin,
                Y,
                lock,
                lock[1] - 0.067,
                lock[1] + 0.009,
                tip,
                0.048,
                world(objs[pin])[0, :, 0].max(),
                lock[1] - 0.056,
            )
        assert set(mapping) == {row["name"] for row in rows}
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
