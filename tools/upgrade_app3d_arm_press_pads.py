"""Append torso and arm upholstery to six upper-body clips after their tower fits."""

import argparse
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation
from upgrade_app3d_adjust_bench import HERE, append_batch, load, object_pose
from upgrade_app3d_lower_pads import clearance
from upgrade_app3d_lower_press_pads import common_shapes, upholstery, world
from upgrade_app3d_lower_towers import center, vertices
from upgrade_app3d_row_pads import indexed_receiver, X, Y, Z, EYE
from bench_fit import fit, swept_clear
from body_fit import SkinSweep
from fixed_pad_contact import penetration
from part_registry import MAT_FRAME
from scene_lat_parts import build_seat, palette
from selector_tower import block

TARGETS = "arm_press_pad_targets.json"
REPORT = "arm_press_pad_fit.json"


def plane_at(o, normal, offset, axis, line, inset=0):
    """Intersection of a support centreline and the underside of a mounted pad."""
    p, r, s = object_pose(o)
    v = r.apply(vertices(o) * s) + p + offset
    return line + axis * (
        (np.max(v @ normal) - inset - line @ normal) / (axis @ normal)
    )


def upgrade(view):
    shared = common_shapes(view)
    back = load(HERE / "scene_pull_source.json")["chest_pad"]
    prior = load(view / "data/upper_station_fit.json")

    def build(key, raw, mapping, arm, frames, base):
        objs = {o["name"]: o for o in raw["objects"]}
        if "seat" in objs and "seat" not in prior.get(key, {}).get("fits", {}):
            raise ValueError("preceding tower has no fitted seat")
        faces = np.asarray(base["triangles"]).reshape(-1, 3)
        clock = np.frombuffer(
            (view / "human_v5" / (key + ".bin")).read_bytes(), "<f4", len(frames), 40
        )
        sweep = SkinSweep(frames, faces)
        rows = {n: [] for n in mapping}
        meta = {n: dict(group=g) for n, (idx, g) in mapping.items()}
        offsets = {}

        def emit(n, mesh, pos, r, scale, mat, color, smooth=False):
            v, t = mesh
            pos = np.asarray(pos)
            scale = np.asarray(scale)
            if not smooth and not swept_clear(sweep, r.apply(v * scale) + pos):
                raise ValueError(n + ": mounting hardware meets skin")
            rows[n].append(
                dict(
                    name=n,
                    verts=v,
                    tris=np.ravel(t),
                    pos=pos[None],
                    quats=r.as_quat()[None],
                    sc=scale[None],
                    mat=mat,
                    color=color,
                    smooth=smooth,
                )
            )

        for n, (idx, g) in mapping.items():
            assert raw["objects"][idx]["name"] == n
            role = g.split("__")[0]
            if role not in ("arm_pad", "back_pad", "seat_pad", "head_pad"):
                continue
            o = objs[n]
            p, r, s = object_pose(o)
            old = vertices(o) * s
            size = np.ptp(old, axis=0)
            if g not in shared:
                shared[g] = (
                    [
                        (part.verts, part.tris, part.mat_preset, part.color)
                        for part in build_seat(-size / 2, size / 2)
                    ]
                    if role == "seat_pad"
                    else upholstery(arm["arm_pad"] if role == "arm_pad" else back, size)
                )
            pieces = shared[g]
            proto = np.vstack([a[0] for a in pieces])
            sc = size / np.ptp(proto, axis=0)
            c = center(old) - center(proto) * sc
            v = proto * sc + c
            surf = [(r.apply(a[0] * sc + c) + p, a[1]) for a in pieces]
            axis = None
            shift = np.zeros(3)
            if role == "seat_pad":
                tri = np.vstack(
                    [
                        np.asarray(a[1]).reshape(-1, 3) + j
                        for a, j in zip(
                            pieces, np.cumsum([0] + [len(a[0]) for a in pieces[:-1]])
                        )
                    ]
                )
                axis = Z
                _, pos, gap = fit(frames, base, role, (p, r), (v, tri))
                shift = pos - p
            elif n == "tapered_back":
                # Both original back standoffs run fore/aft; the side pin runs across them.
                axis = -Y
                gap = clearance(frames, base, role, surf, axis, X)
                shift = axis * (gap - 0.0035)
                gap -= shift @ axis
                if np.linalg.norm(shift) > 0.060:
                    raise ValueError("back setting exceeds the mount travel")
            if axis is not None:
                if not 0.002 <= gap <= 0.005 or not swept_clear(
                    sweep, r.apply(v) + p + shift
                ):
                    raise ValueError(n + ": no clear setting")
                meta[n].update(
                    axis=axis.tolist(), gap_mm=gap * 1000, offset=shift.tolist()
                )
            else:
                hit = penetration(
                    frames, faces, clock, raw["acts"], old, v, [p], [r.as_quat()]
                )
                meta[n].update(axis=None, collision=hit)
                if hit["added_hull_mm"] > 10:
                    raise ValueError(f"{n}: added penetration {hit}")
            offsets[n] = shift
            for verts, tris, mat, color in pieces:
                emit(n, (verts, tris), p + shift + r.apply(c), r, sc, mat, color, True)

        gray = palette()["casting"]

        def bar(n, size, at):
            emit(n, block(size, 0.002), at, EYE, [1] * 3, MAT_FRAME, gray)

        def rail(
            socket, slider, pin, frame, axis, lock, low, high, tip, width, pin_end
        ):
            # indexed_receiver takes +Z/+Y; invert Y and Z together for forward travel.
            bore = frame.inv().apply(lock)
            along = bore @ axis
            lengths = (tip - along) / (1 - (np.arange(12) + 0.5) / 12)
            valid = lengths[
                (lengths < tip - low - 0.002) & (lengths > tip - along + 0.007)
            ]
            if not len(valid):
                raise ValueError(slider + ": pin would miss all index holes")

            def put(name, mesh, at, r, sc, mat, col):
                emit(name, mesh, frame.apply(at), frame * r, sc, mat, col)

            info = indexed_receiver(
                put,
                socket,
                slider,
                pin,
                axis,
                bore,
                low,
                high,
                tip,
                width,
                pin_end,
                tip - valid.max(),
            )
            meta[slider].setdefault("locks", []).append(
                dict(
                    axis=frame.apply(axis).round(8).tolist(),
                    bore=lock.tolist(),
                    hole=int(
                        round(
                            (along - info["bottom"]) / (tip - info["bottom"]) * 12 - 0.5
                        )
                    ),
                    socket=socket,
                    pin=pin,
                )
            )

        if "seat.001" in offsets:
            bottom = world(objs["seat.001"])[:, 2].min() + offsets["seat.001"][2]
            dip = key == "dip_machine"
            socket, slider, pin = (
                ("seat_post", "seat_rail", "seat_post")
                if dip
                else ("seat_base", "seat_adjuster", "seat_pin")
            )
            post = world(objs[socket])
            lo = post[:, 2].min()
            lock = center(post)
            width = np.ptp(post[:, 0])
            pan = "seat_pan" if dip else slider
            tip = bottom - 0.003
            if dip:
                # The stock crossmember runs transversely, not along the height adjustment.
                # Carry it under the saddle; the telescope follows the existing upright.
                lock[2] = lo + (tip - lo) * 0.61
                high = lock[2] + 0.018
                pin_end = width / 2 + 0.024
                tie = world(objs[slider])
                bar(
                    slider,
                    [np.ptp(tie[:, 0]), 0.030, 0.018],
                    [*center(tie)[:2], bottom - 0.012],
                )
            else:
                knob = world(objs[pin])
                lock[2] = center(knob)[2]
                high = min(post[:, 2].max(), tip - 0.007)
                pin_end = knob[:, 0].max() - lock[0]
            rail(socket, slider, pin, EYE, Z, lock, lo, high, tip, width, pin_end)
            pad = world(objs[pan]) if dip else post
            size = np.ptp(pad, axis=0)[:2] if dip else [0.15, 0.095]
            bar(pan, [*size, 0.008], [*center(pad)[:2], bottom - 0.002])

        if "tapered_back" in offsets:
            n = "tapered_back"
            offset = offsets[n]
            normal = object_pose(objs[n])[1].apply(Y)
            post = world(objs["back_support"])
            knob = world(objs["back_adjust_pin"])
            lock = center(knob)
            # Side-mounted guide shares the original transverse pin line. It touches
            # the upright's side instead of drilling its slider through solid steel.
            width = 0.040
            lock[0] = post[:, 0].max() + width / 2 - 0.0015
            at = plane_at(objs[n], normal, offset, Y, lock, 0.003)
            rail(
                "back_mount",
                "back_mount",
                "back_adjust_pin",
                Rotation.from_euler("x", 180, degrees=True),
                Y,
                lock,
                -lock[1] - 0.037,
                -lock[1] + 0.019,
                -at[1],
                width,
                knob[:, 0].max() - lock[0],
            )
            upper = "back_mount.001"
            old = world(objs[upper])
            mount = center(old)
            at = plane_at(objs[n], normal, offset, Y, mount, 0.004)
            end = old[:, 1].max() + 0.005
            if end <= at[1]:
                raise ValueError("upper back guide exceeds its attachment")
            bar(
                upper,
                [0.030, end - at[1], 0.030],
                [mount[0], (end + at[1]) / 2, mount[2]],
            )
        if "pad_post" in mapping:
            # The supplied preacher column stops below the sloped pad. Attach it to
            # the actual underside, without translating the arm contact surface.
            post = world(objs["pad_post"])
            line = center(post)
            o = objs["preacher_pad"]
            normal = -object_pose(o)[1].apply(Z)
            top = plane_at(o, normal, offsets["preacher_pad"], Z, line, 0.005)[2]
            low = world(objs["spine"])[:, 2].max() - 0.003
            bar(
                "pad_post",
                [*np.ptp(post, axis=0)[:2], top - low],
                [*line[:2], (top + low) / 2],
            )
        for n, rs in rows.items():
            assert rs, n
            meta[n]["records"] = len(rs)
        return [r for rs in rows.values() for r in rs], meta

    return append_batch(
        view,
        targets_file=TARGETS,
        source_file="scene_arm_pad_source.json",
        report_file=REPORT,
        build_model=build,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", type=Path)
    upgrade(parser.parse_args().view)
