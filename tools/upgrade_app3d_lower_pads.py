"""Skin lower-machine supports after lower towers; reject an entire incompatible assembly."""

import argparse
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation, Slerp
from upgrade_app3d_adjust_bench import HERE, append_batch, load
from upgrade_app3d_lower_towers import pose, center, vertices, roller_layers
from upgrade_app3d_row_pads import indexed_receiver
from bench_fit import swept_clear, top_gap
from body_fit import SkinSweep, contact_region, fit_body_part
from fixed_pad_contact import penetration
from part_registry import MAT_FRAME, MAT_PAD, MAT_RUBBER
from scene_lat_parts import _nine, palette
from selector_tower import block

TARGETS = "lower_pad_targets.json"
REPORT = "lower_pad_fit.json"
X, Y, Z = np.eye(3)


def folded_skin(frames, times, acts, obj):
    """Pose keys and half-steps in the exercise lever coordinate frame."""
    p, r, s = pose(obj)
    keys = np.union1d(times, np.asarray(acts, dtype="<f4"))
    ticks = np.sort(np.r_[keys, (keys[:-1] + keys[1:]) / 2])
    j = np.searchsorted(times, ticks, side="right").clip(1, len(times) - 1)
    w = ((ticks - times[j - 1]) / (times[j] - times[j - 1])).clip(0, 1)[:, None, None]
    skin = frames[j - 1] + w * (frames[j] - frames[j - 1])
    if len(p) == 1:
        return np.einsum("fvi,ij->fvj", skin - p[0], r[0].as_matrix())
    grid = np.asarray(acts) if len(acts) == len(p) else np.linspace(0, 1, len(p))
    rr = Slerp(grid, r)(ticks.clip(grid[0], grid[-1]))
    pp = np.column_stack([np.interp(ticks, grid, z) for z in p.T])
    return np.einsum("fvi,fij->fvj", skin - pp[:, None, :], rr.as_matrix())


def clearance(skin, base, role, layers, normal, across):
    v = np.vstack([v for v, t, *_ in layers])
    t = np.vstack(
        [
            np.asarray(t).reshape(-1, 3) + i
            for (_, t, *_), i in zip(
                layers, np.cumsum([0] + [len(a[0]) for a in layers[:-1]])
            )
        ]
    )
    basis = np.stack([across, np.cross(normal, across), normal])
    faces = contact_region(base, role)[0]
    hint = fit_body_part(skin, base, role, np.zeros(3), v, -normal, across)
    g = top_gap(
        np.einsum("fvi,ji->fvj", skin, basis)[:, faces].reshape(-1, 3, 3),
        (v + hint) @ basis.T,
        t,
    )
    return float(hint @ normal + g)


def profile_back(v, t, old):
    """Follow the legacy lumbar profile, without removing any scene corners or stitches.
    Split only triangles crossing a profile station; share vertices across the cuts.
    """
    rings = np.unique(old[:, 2])
    hulls = [old[old[:, 2] == z] for z in rings]
    if len(rings) != 8 or not all(len(ring) == 6 for ring in hulls):
        return v, t
    mesh = v[np.array(t).reshape(-1, 3)]
    for z in rings[1:-1]:
        cross = (mesh[:, :, 2].min(1) < z - 1e-7) & (mesh[:, :, 2].max(1) > z + 1e-7)
        keep = list(mesh[~cross])
        for tri in mesh[cross]:
            for sign in (-1, 1):
                poly = []
                for a, b in zip(tri, np.roll(tri, -1, axis=0)):
                    if sign * (a[2] - z) >= 0:
                        poly.append(a)
                    if (a[2] - z) * (b[2] - z) < 0:
                        poly.append(a + (b - a) * ((z - a[2]) / (b[2] - a[2])))
                keep.extend(
                    [poly[0], poly[i], poly[i + 1]] for i in range(1, len(poly) - 1)
                )
        mesh = np.array(keep)
    v, t = np.unique(mesh.reshape(-1, 3).round(9), axis=0, return_inverse=True)
    z = v[:, 2]
    half = np.ptp(old, axis=0) / 2
    side = np.abs(v[:, 0]) / half[0]
    v[:, 0] *= np.interp(z, rings, [ring[:, 0].max() for ring in hulls]) / half[0]
    for i, fun in enumerate((np.min, np.max)):
        ctr = np.interp(
            z, rings, [fun(ring[np.abs(ring[:, 0]) < 1e-7, 1]) for ring in hulls]
        )
        edge = np.interp(
            z, rings, [fun(ring[np.abs(ring[:, 0]) > 1e-7, 1]) for ring in hulls]
        )
        bound = ctr + (edge - ctr) * side
        if i == 0:
            low = bound
        else:
            high = bound
    v[:, 1] = low + (high - low) * (v[:, 1] + half[1]) / (2 * half[1])
    return v, t.reshape(-1, 3)


def build_layers(source, roller, role, group, obj, cache):
    old = vertices(obj)
    dims = np.ptp(old, axis=0)
    c = center(old)
    if role == "leg_roller":
        # The decagonal legacy section is narrower across flats than across corners.
        # Size by physical radius, never by that polygon's x bounding box.
        d = 2 * np.max(np.linalg.norm(old[:, :2] - c[:2], axis=1))
        dims[:2] = d
    if group not in cache:
        if role == "leg_roller":
            mesh = roller_layers(roller, obj)
            parts = [
                (v, t, m, palette()[col])
                for (v, t), m, col in zip(mesh, [MAT_PAD, MAT_RUBBER], ["pad", "grip"])
            ]
        else:
            src = source[
                "back_pad"
                if role in ("back_pad", "chest_pad") and dims.argmin() == 1
                else "seat_pad"
                if role == "seat_pad"
                else "thigh_pad"
            ]
            vs = np.vstack([a["v"] for a in src])
            h = np.ptp(vs, axis=0) / 2
            # Keep the stitching on the wide face, including vertical inner-thigh cups.
            orient = (
                Rotation.identity()
                if role != "thigh_pad" or dims.argmin() != 0
                else Rotation.from_euler("y", 90, degrees=True)
            )
            size = np.abs(orient.inv().apply(dims)) / 2
            parts = []
            for part in src:
                v = np.array(part["v"])
                for i in range(3):
                    v[:, i] = _nine(v[:, i], h[i], size[i], min(0.030, size[i] * 0.45))
                t = part["t"]
                if role == "back_pad":
                    v, t = profile_back(v * [-1, -1, 1], t, old - c)
                parts.append(
                    (
                        orient.apply(v),
                        t,
                        MAT_PAD,
                        palette()[("pad", "stitch")[part["slot"]]],
                    )
                )
        cache[group] = dims.copy(), parts
    extent, parts = cache[group]
    return parts, dims / extent, c


def disk_distance(tris, pt):
    delta = pt - tris
    edge = np.roll(tris, -1, axis=1) - tris
    cross = edge[:, :, 0] * delta[:, :, 1] - edge[:, :, 1] * delta[:, :, 0]
    if ((cross > 0).all(1) | (cross < 0).all(1)).any():
        return 0.0
    w = (delta * edge).sum(2) / np.maximum((edge * edge).sum(2), 1e-18)
    return np.linalg.norm(delta - edge * w.clip(0, 1)[:, :, None], axis=2).min(
        initial=np.inf
    )


def trial_ankle(skin, base, obj, objects, layers):
    """Test the entire moving rail, not just contact planes along it.

    In the roller frame exercise motion disappears. Intervals of slider positions
    that contain a skin sample inside the central barrel can be merged exactly.
    For the shin lever also exclude centre lines that bury the axle in its solid end.
    """
    from scipy.spatial import ConvexHull

    p, r, _ = pose(obj)
    rail = objects["roller_adjust_rail"]
    a, ar, _ = pose(rail)
    offset = ar[0].inv().apply(p[0] - a[0])[2]
    axis = r.inv().apply(ar.apply(np.tile(Z, (len(ar), 1))))
    assert np.allclose(axis, axis[0], atol=0.0001) and abs(axis[0, 2]) < 0.0001
    lo, hi = np.array([vertices(rail)[:, 2].min(), vertices(rail)[:, 2].max()]) - offset
    norm = axis[0]
    span = np.ptp(vertices(obj)[:, 2]) / 2
    v = layers[0][0]
    radius = np.max(np.linalg.norm(v[:, :2], axis=1))
    desc = f"{obj['name']}: rail Z {ar[0].apply(Z).round(5).tolist()}, travel [{lo * 1000:.1f}, {hi * 1000:.1f}] mm"
    candidates = []
    for sign in (-1, 1):
        g = clearance(skin, base, "ankle_roller", layers, sign * norm, Z)
        candidates.append(round(1000 * sign * (g - 0.0035), 1))
    desc += f"; axial fits {candidates} mm"
    faces = contact_region(base, "ankle_roller")[0]
    tri = skin[:, faces].reshape(-1, 3, 3)
    samples = np.vstack((skin.reshape(-1, 3), tri.mean(1)))
    samples = samples[np.abs(samples[:, 2]) < span - 0.041]
    along = np.einsum("vi,i->v", samples, norm)
    normal = samples - along[:, None] * norm
    disc = (radius * 0.98) ** 2 - (normal[:, :2] ** 2).sum(1)
    valid = disc > 0
    extent = np.sqrt(disc[valid])
    ranges = np.column_stack((along[valid] - extent, along[valid] + extent))
    end = lo
    for l, h in ranges[np.argsort(ranges[:, 0])]:
        if l > end:
            break
        end = max(end, h)
    if end >= hi:
        raise ValueError(
            desc + "; skin enters the barrel envelope at every rail setting"
        )
    if "shin_lever" in objects:
        lever = objects["shin_lever"]
        lp, lr, ls = pose(lever)
        wv = lr[0].apply(vertices(lever) * ls[0]) + lp[0]
        axle = objects["roller_axle"]
        ap, aq, asc = pose(axle)
        av = aq[0].apply(vertices(axle) * asc[0]) + ap[0]
        section = lp[0, 0]
        assert av[:, 0].min() < section < av[:, 0].max()
        out = []
        for face in wv[np.asarray(lever["tris"]).reshape(-1, 3)]:
            for x, y in zip(face, np.roll(face, -1, axis=0)):
                if (x[0] - section) * (y[0] - section) < 0:
                    out.append(x + (y - x) * (section - x[0]) / (y[0] - x[0]))
        poly = r[0].inv().apply(np.array(out) - p[0])[:, :2]
        poly = poly[ConvexHull(poly).vertices]
        fan = np.array(
            [[poly[0], poly[i], poly[i + 1]] for i in range(1, len(poly) - 1)]
        )
        shaft_radius = np.linalg.norm(vertices(axle)[:, :2], axis=1).max() * 0.92
        tri = tri[
            (tri[:, :, 2].min(1) < span + 0.025) & (tri[:, :, 2].max(1) > -span - 0.025)
        ][:, :, :2]
        u = norm[:2]
        l, h = (
            np.minimum(lo * u, hi * u) - radius - 0.025,
            np.maximum(lo * u, hi * u) + radius + 0.025,
        )
        tri = tri[(tri.min(1) < h).all(1) & (tri.max(1) > l).all(1)]
        steps = np.linspace(lo, hi, int(np.ceil((hi - lo) / 0.001)) + 1)
        half_step = (steps[1] - steps[0]) / 2
        # Distance is 1-Lipschitz. Include the entire half-step on either side.
        safe = [
            t for t in steps if disk_distance(fan, t * u) + half_step >= shaft_radius
        ]
        lower = min(
            0.025,
            min((disk_distance(tri, t * u) for t in safe), default=np.inf)
            - radius
            - half_step,
        )
        if lower > 0.005:
            raise ValueError(
                desc
                + f"; outside the solid shin lever, sampled skin gap at least {lower * 1000:.1f} mm"
            )
    raise ValueError(
        desc + "; no verified indexed axle setting for this moving assembly"
    )


def upgrade(view):
    roller = load(HERE / "scene_lower_tower_source.json")["leg_roller"]
    cache = {}

    def build(key, raw, mapping, source, frames, base):
        objs = {a["name"]: a for a in raw["objects"]}
        assert all(raw["objects"][i]["name"] == n for n, (i, _) in mapping.items())
        times = np.frombuffer(
            (view / "human_v5" / f"{key}.bin").read_bytes(), "<f4", len(frames), 40
        )
        acts = raw["acts"]
        faces = np.array(base["triangles"]).reshape(-1, 3)
        pads = {}
        info = {}
        rows = []
        for n, (_, group) in mapping.items():
            role = group.split("__")[0]
            if not (role.endswith("_pad") or role == "leg_roller"):
                continue
            o = objs[n]
            p, r, s = pose(o)
            assert np.allclose(s, 1, atol=2e-5)
            parts, scale, c = build_layers(source, roller, role, group, o, cache)
            # Both lateral cups use one mesh. Turn the right cup toward the leg.
            turn = (
                role == "thigh_pad"
                and np.ptp(vertices(o), axis=0).argmin() == 0
                and p[0, 0] > 0
            )
            signs = np.array([-1.0, -1.0, 1.0]) if turn else np.ones(3)
            surf = [(v * signs * scale + c, t) for v, t, *_ in parts]
            pads[n] = (parts, scale, c, surf)
            info[n] = dict(group=group, axis=None, offset=[0, 0, 0], records=len(parts))

            if turn:
                info[n]["inward_half_turn"] = True

        def gap(n, role, normal, across=X):
            return clearance(
                folded_skin(frames, times, acts, objs[n]),
                base,
                role,
                pads[n][3],
                normal,
                across,
            )

        if "roller_adjust_rail" in objs:
            n = "roller" if "roller" in objs else "ankle_roller"
            trial_ankle(
                folded_skin(frames, times, acts, objs[n]),
                base,
                objs[n],
                objs,
                pads[n][3],
            )
        if "locking_pin" in objs and "hip_pad_wrap" in objs:
            # Test whether the existing transverse lock can enter the two vertical columns.
            pin = pose(objs["locking_pin"])[0][0]
            post = objs["frame_post.001"]
            p, r, s = pose(post)
            y = (r[0].apply(vertices(post) * s[0]) + p[0])[:, 1]
            miss = max(y.min() - pin[1], pin[1] - y.max(), 0)
            if miss > 0.005:
                raise ValueError(
                    f"hip pad: original lock centreline misses right upright by {1000 * miss:.1f} mm; no coaxial vertical index receiver"
                )
        if "height_pin" in objs:
            gaps = [gap(n, "thigh_roller", -Z) for n in ("knee", "knee.001")]
            hp = pose(objs["height_pin"])[0][0]
            holes = [
                pose(objs[n])[0][0] for n in sorted(objs) if n.startswith("adjust_hole")
            ]
            settings = [hp[2] - h[2] for h in holes]
            valid = [t for t in settings if all(0.002 <= g + t <= 0.005 for g in gaps)]
            if not valid:
                raise ValueError(
                    "shared knee insert local Z: gaps "
                    + str(np.round(np.array(gaps) * 1000, 2).tolist())
                    + " mm; available hole offsets "
                    + str(np.round(np.array(settings) * 1000, 1).tolist())
                    + " mm; no common 2-5 mm index"
                )
            raise ValueError(
                "shared calf carriage: original transverse height pin has no matching transverse bore in the carriage"
            )
        if key in ("hip_abductor", "hip_adductor"):
            names = [n for n in pads if n.startswith("seat")]
            gs = [gap(n, "seat_pad", Z) for n in names]
            lo = max(g - 0.005 for g in gs)
            hi = min(g - 0.002 for g in gs)
            if lo > hi:
                raise ValueError(f"no common seat height: gaps {gs}")
            dz = (lo + hi) / 2
            pan = (
                min(
                    pose(objs[n])[0][0, 2] + min(np.min(v[:, 2]) for v, t in pads[n][3])
                    for n in names
                )
                + dz
            )
            if "seat_turntable" in objs:
                # A rotating seat cannot be driven down into its existing yoke to close the gap.
                o = objs["seat_yoke"]
                p, r, s = pose(o)
                top = (r[0].apply(vertices(o) * s[0]) + p[0])[:, 2].max()
                if pan < top - 0.005:
                    raise ValueError(
                        f"seat Z: fit {dz * 1000:.2f} mm sinks pan {(top - pan) * 1000:.2f} mm into fixed turntable yoke"
                    )
            for n, g in zip(names, gs):
                info[n].update(
                    axis=Z.tolist(), offset=(Z * dz).tolist(), gap_mm=1000 * (g - dz)
                )
        sweep = (
            SkinSweep(frames, faces) if any(i["axis"] for i in info.values()) else None
        )
        for n, (parts, scale, c, surf) in pads.items():
            o = objs[n]
            p, r, s = pose(o)
            m = info[n]
            shift = np.array(m["offset"])
            local = np.vstack([v for v, t in surf])
            old = vertices(o) * s[0]
            cc = r.apply(c * s) + p + shift
            if m["axis"]:
                if not swept_clear(sweep, r[0].apply(local) + p[0] + shift):
                    raise ValueError(f"{n}: fitted surface intersects moving skin")
            else:
                hit = penetration(
                    frames, faces, times, acts, old, local, p, r.as_quat()
                )
                m["collision"] = hit
                if hit["added_hull_mm"] > 10:
                    raise ValueError(f"{n}: added overlap {hit}")
            if m["group"].startswith("leg_roller"):
                m["axle_local"] = Z.tolist()
                axle = objs.get("roller_axle", objs.get("ankle_axle"))
                if axle:
                    a, ar, _ = pose(axle)
                    axis = r.apply(np.tile(Z, (len(r), 1)))
                    assert np.max(
                        np.linalg.norm(np.cross(cc - a, axis), axis=1)
                    ) < 0.0001 and np.all(
                        abs(np.sum(axis * ar.apply(np.tile(Z, (len(ar), 1))), axis=1))
                        > 0.9999
                    )
            for v, t, mat, color in parts:
                rows.append(
                    dict(
                        name=n,
                        verts=v,
                        tris=np.ravel(t),
                        pos=cc,
                        quats=(
                            (r * Rotation.from_euler("z", 180, degrees=True))
                            if m.get("inward_half_turn")
                            else r
                        ).as_quat(),
                        sc=scale * s,
                        mat=mat,
                        color=color,
                        smooth=True,
                    )
                )
        if "mopt_seat_stem" in mapping:
            n = "mopt_seat_stem"
            o = objs[n]
            p, r, s = pose(o)
            vv = r[0].apply(vertices(o) * s[0]) + p[0]
            lo = vv[:, 2].min()
            tip = pan - 0.001
            lock = p[0].copy()
            lock[2] = tip - 0.085
            width = np.ptp(vv[:, 0])
            seat_y = lock[1]

            def emit(name, shape, at, rot, sc, mat, color):
                v, t = shape
                if not swept_clear(sweep, rot.apply(v * sc) + at):
                    raise ValueError(
                        "seat saddle or index mechanism intersects V6 skin"
                    )
                rows.append(
                    dict(
                        name=n,
                        verts=v,
                        tris=np.ravel(t),
                        pos=np.atleast_2d(at),
                        quats=np.atleast_2d(rot.as_quat()),
                        sc=np.atleast_2d(sc),
                        mat=mat,
                        color=color,
                        smooth=False,
                    )
                )

            rail = indexed_receiver(
                emit,
                n,
                n,
                n,
                Z,
                lock,
                lo,
                lock[2] + 0.025,
                tip,
                width,
                width / 2 + 0.021,
                max(lo + 0.015, tip - 0.24),
            )
            # One saddle bolts the split cushions to one telescoping column. No seam bridge on top.
            emit(
                n,
                block([0.265, 0.11, 0.008], 0.004),
                np.array([lock[0], seat_y, pan - 0.001]),
                Rotation.identity(),
                np.ones(3),
                MAT_FRAME,
                palette()["casting"],
            )
            info[n] = dict(rail=rail, records=sum(x["name"] == n for x in rows))
        assert {a["name"] for a in rows} == set(mapping)
        return rows, info

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
