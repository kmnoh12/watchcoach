"""Build an offline viewer bundle with the revised Blender hand from an existing one.
Usage: python tools/build_v5_hand_viewer_copy.py SOURCE OUTPUT [--clips KEY ...]
SOURCE is a phone APK or an unpacked bundle folder (phone/src/main/assets/viewer3d).
Requires numpy, scipy, and Blender 5.2. The existing phone assets are never written.
"""

import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import zipfile

import numpy as np

REPO = Path(__file__).resolve().parents[1]
PREFIX = "assets/viewer3d/"
DIGITS = ("thumb", "index", "middle", "ring", "pinky")


def dump_rig(path):
    import bpy

    obj = bpy.data.objects["V5_Body"]
    rig = bpy.data.objects["V5_CommonRig"]
    mesh = obj.data
    mesh.calc_loop_triangles()
    data = dict(
        rest=[v.co[:] for v in mesh.vertices],
        weights=[
            {
                obj.vertex_groups[g.group].name: g.weight
                for g in v.groups
                if g.weight > 0
            }
            for v in mesh.vertices
        ],
        triangles=[p.vertices[:] for p in mesh.loop_triangles],
        heads={b.name: b.head_local[:] for b in rig.data.bones},
    )
    Path(path).write_text(json.dumps(data))


def unit(v):
    return v / max(np.linalg.norm(v), 1e-12)


def rigid(x, y):
    # One least-squares rigid transform per frame; the cache quantization is below 0.1 mm.
    x0 = x.mean(0)
    y0 = y.mean(1)
    u, _, vh = np.linalg.svd(np.einsum("vi,fvj->fij", x - x0, y - y0[:, None, :]))
    u[:, :, -1] *= np.linalg.det(u @ vh)[:, None]
    q = u @ vh
    return q, y0 - np.einsum("i,fij->fj", x0, q)


def posed(v, q, t):
    return v @ q + t[:, None, :]


def decode(blob):
    magic, frames, count, _ = struct.unpack_from("<4sIII", blob)
    assert magic == b"WGP2"
    lo, scale = np.frombuffer(blob, "<f4", 6, 16).reshape(2, 3)
    acts = np.frombuffer(blob, "<f4", frames, 40)
    delta = np.frombuffer(blob, "<u2", offset=40 + 4 * frames).reshape(frames, count, 3)
    return acts, np.cumsum(delta, axis=0, dtype=np.uint16) * scale + lo


class Transfer:
    def __init__(self, base, rig):
        from scipy.spatial import cKDTree

        self.names = base["bone_names"]
        self.r = np.asarray(base["rest"]).reshape(-1, 3)
        self.n = np.asarray(rig["rest"])
        self.heads = rig["heads"]
        self.w = np.zeros((len(self.r), len(self.names)))
        np.add.at(
            self.w,
            (np.arange(len(self.r))[:, None], np.asarray(base["joints"])),
            base["weights"],
        )
        self.u = np.array(
            [[weights.get(n, 0.0) for n in self.names] for weights in rig["weights"]]
        )
        self.tris = np.asarray(rig["triangles"])
        wids = np.argsort(-self.u, axis=1)[:, :4]
        self.base = dict(
            vertices=len(self.n),
            rest=self.n.ravel().tolist(),
            triangles=self.tris.ravel().tolist(),
            bone_names=self.names,
            joints=wids.tolist(),
            weights=np.take_along_axis(self.u, wids, axis=1).tolist(),
        )
        d, self.old = cKDTree(self.r).query(self.n)
        self.same = d < 1e-6
        self.seams = {}
        # New vertices from the arm cut lie on original edges. Carry their full baked motion.
        tris = np.asarray(base["triangles"]).reshape(-1, 3)
        edges = np.unique(
            np.sort(
                np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]]),
                axis=1,
            ),
            axis=0,
        )
        starts = self.r[edges[:, 0]]
        directions = self.r[edges[:, 1]] - starts
        for i in np.flatnonzero(~self.same):
            if not any(
                self.u[i, self.names.index("lowerarm_" + s)] > 0.999 for s in "lr"
            ):
                continue
            a = np.clip(
                ((self.n[i] - starts) * directions).sum(1)
                / (directions * directions).sum(1),
                0,
                1,
            )
            dist = np.linalg.norm(starts + directions * a[:, None] - self.n[i], axis=1)
            k = np.argmin(dist)
            if dist[k] < 1e-6:
                self.seams[i] = (edges[k], a[k])

    def skin(self, p):
        q = {}
        t = {}
        out = np.zeros((len(p), len(self.n), 3))
        for side in "lr":
            for name in (
                "hand",
                *(f"{d}_0{k}" for d in DIGITS for k in (1, 2, 3)),
                "lowerarm",
            ):
                n = name + "_" + side
                j = self.names.index(n)
                ids = self.w[:, j] > 0.999
                if name == "lowerarm":
                    h = "hand_" + side
                    hw = self.w[:, self.names.index(h)]
                    ids = (self.w[:, j] > 0.5) & ((self.w[:, j] + hw) > 0.9999)
                    y = (
                        p[:, ids] - posed(self.r[ids], q[h], t[h]) * hw[ids, None]
                    ) / self.w[ids, j, None]
                else:
                    y = p[:, ids]
                q[n], t[n] = rigid(self.r[ids], y)
                sel = self.u[:, j] > 0
                out[:, sel] += posed(self.n[sel], q[n], t[n]) * self.u[sel, j, None]
        out[:, self.same] = p[:, self.old[self.same]]
        for i, (edge, f) in self.seams.items():
            out[:, i] = p[:, edge[0]] * (1 - f) + p[:, edge[1]] * f
        return out, q, t


def grip_objects(objs):
    import re

    select = re.compile(
        r"grip|handle|shaft|pullup|bar_main|^bar$|^barbell|^pull_up|dip_bar|^rope_cord"
    )
    skip = re.compile(
        r"mount|link|support|stem|drop|end|stop|swing|eye|knuckle|neck|collar|plate|sleeve"
    )
    return [
        o
        for o in objs
        if select.search(o["name"].lower()) and not skip.search(o["name"].lower())
    ]


def track_times(count, eq_acts):
    # The phone viewer plays a track sampled once per equipment phase at those phase times,
    # and any other track at uniform spacing.
    if eq_acts is not None and count == len(eq_acts):
        return np.asarray(eq_acts, float)
    return np.linspace(0, 1, count)


def handles(objects, acts, eq_acts=None):
    from scipy.spatial.transform import Rotation, Slerp

    result = []
    for ob in objects:
        v = np.unique(np.asarray(ob["verts"]).reshape(-1, 3), axis=0)
        if len(v) < 6:
            continue
        m = np.asarray(ob["m"]).reshape(-1, 4, 4).transpose(0, 2, 1)
        scale = np.linalg.norm(m[:, :3, :3], axis=1)
        if np.min(scale) < 1e-8:
            continue
        norm = m[:, :3, :3] / scale[:, None, :]
        if np.min(np.linalg.det(norm)) < 0:
            continue
        if len(m) > 1:
            times = track_times(len(m), eq_acts)
            rots = Slerp(times, Rotation.from_matrix(norm))(
                np.clip(acts, 0, 1)
            ).as_matrix()
            sc = np.array([np.interp(acts, times, s) for s in scale.T]).T
            loc = np.array([np.interp(acts, times, s) for s in m[:, :3, 3].T]).T
        else:
            rots = norm
            sc = scale
            loc = m[:, :3, 3]
        world = v @ (rots * sc[:, None, :]).transpose(0, 2, 1) + loc[:, None, :]
        if len(world) == 1:
            world = np.broadcast_to(world, (len(acts), len(v), 3))
        c = world.mean(1)
        _, _, axes = np.linalg.svd(world[0] - c[0], full_matrices=False)
        local = rots[0].T @ axes[0]
        a = np.broadcast_to(rots @ local, c.shape)
        axial = np.einsum("fvi,fi->fv", world - c[:, None, :], a)
        radial = np.linalg.norm(
            world - c[:, None, :] - axial[:, :, None] * a[:, None, :], axis=2
        )
        radius = np.percentile(radial, 90, axis=1)
        if not (0.005 < radius[0] < 0.038 and np.ptp(axial[0]) > 2.5 * radius[0]):
            continue
        # Reject curved or composite pieces whose outer skin is not a round handle.
        surface = radial[0][radial[0] > 0.003]
        if len(surface) < 4 or np.percentile(np.abs(surface - radius[0]), 75) > 0.003:
            continue
        result.append((ob["name"], c, a, radius, axial.min(1), axial.max(1)))
    return result


def sdf(points, handle, frame):
    _, centers, axes, radii, lo, hi = handle
    v = points - centers[frame]
    a = v @ axes[frame]
    side = np.linalg.norm(v - a[:, None] * axes[frame], axis=1) - radii[frame]
    end = np.maximum(lo[frame] - a, a - hi[frame])
    return np.minimum(np.maximum(side, end), 0) + np.hypot(
        np.maximum(side, 0), np.maximum(end, 0)
    )


def fit_hand(tr, out, q, t, side, handle):
    """Fit each digit about its existing MCP pivot. Reuse local angles while the grasp persists."""
    from scipy.optimize import least_squares
    from scipy.spatial.transform import Rotation

    h = "hand_" + side
    centers, axes = handle[1:3]
    frames = len(out)
    ref = frames // 2
    # A single local correction is appropriate for a hand holding a moving rigid handle.
    # For varying hand/handle relationships fit additional keys, interpolating on SO(3).
    wrist = np.asarray(tr.heads[h]) @ q[h] + t[h]
    rel = centers - wrist
    axial = np.einsum("fi,fi->f", rel, axes)
    nearest = (rel - axial[:, None] * axes)[:, None, :] @ q[h].transpose(0, 2, 1)
    keys = [0]
    for f in range(1, frames - 1):
        if np.linalg.norm(nearest[f] - nearest[keys[-1]]) > 0.004:
            keys.append(f)
    keys = sorted(set(keys + [ref, frames - 1]))
    orig = out.copy()
    checks = {}
    for digit in ("index", "middle", "ring", "pinky", "thumb"):
        names = [f"{digit}_0{k}_{side}" for k in (1, 2, 3)]
        weights = tr.u[:, [tr.names.index(n) for n in names]]
        ids = np.flatnonzero(weights.sum(1) > 0.001)
        strength = weights[ids].sum(1)[:, None]
        tip = weights[ids, 2] > 0.88
        middle = weights[ids, 1] > 0.88
        base = weights[ids, 0] > 0.88
        pivot = np.asarray(tr.heads[names[0]]) @ q[names[0]] + t[names[0]]
        cloud = orig[:, ids] - pivot[:, None, :]
        # Sample face interiors too: long flat facets can cut into a round handle
        # even when every vertex is outside it.
        ix = np.full(len(tr.n), -1)
        ix[ids] = np.arange(len(ids))
        faces = ix[tr.tris]
        faces = faces[(faces >= 0).all(1)]
        edges = np.unique(
            np.sort(
                np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]])),
                axis=1,
            ),
            axis=0,
        )
        solved = {}

        def solve(f):
            axis = axes[f]
            center = centers[f]
            rad = handle[3][f]
            pts = cloud[f]
            ip = out[f, tr.u[:, tr.names.index("index_03_" + side)] > 0.88].mean(0)
            th = orig[f, ids[tip]].mean(0)

            def radial(v):
                v = v - center
                return unit(v - axis * (axis @ v))

            target = unit(radial(th) + radial(ip))
            # Keep the thumb alongside the index while putting its pad against the shaft.
            root_axis = pivot[f] @ axis
            axial_target = ip @ axis + np.sign(root_axis - ip @ axis) * 0.014
            segments = []
            for other in DIGITS:
                if other == digit:
                    continue
                if other == "thumb" and digit != "thumb":
                    continue
                chain = []
                for k in (1, 2, 3):
                    name = f"{other}_0{k}_{side}"
                    mask = tr.u[:, tr.names.index(name)] > 0.80
                    chain.append(out[f, mask].mean(0))
                segments.extend(zip(chain[:-1], chain[1:]))

            def obstacle(v):
                if not segments:
                    return np.zeros(0)
                a = np.array([a for a, b in segments])
                delta = np.array([b - a for a, b in segments])
                offset = v[:, None, :] - a
                fraction = np.clip(
                    (offset * delta).sum(2) / (delta * delta).sum(1), 0, 1
                )
                distances = np.linalg.norm(
                    offset - fraction[:, :, None] * delta, axis=2
                ).min(1)
                return np.minimum(distances - 0.010, 0) * 2.0

            def residual(rv):
                rot = Rotation.from_rotvec(rv).as_matrix()
                v = pts + strength * (pts @ rot.T - pts) + pivot[f]
                dist = sdf(v, handle, f)
                samples = np.vstack(
                    ((v[edges[:, 0]] + v[edges[:, 1]]) * 0.5, v[faces].mean(1))
                )
                interior = sdf(samples, handle, f)
                # Contact with the handle outranks every pose preference.
                values = [
                    np.minimum(dist - 0.00065, 0) * 12,
                    np.minimum(interior - 0.0005, 0) * 9,
                    obstacle(v[tip | middle]),
                    rv * 0.0025,
                    np.array(
                        [np.min(dist[tip]) - 0.00045, np.min(dist[middle]) - 0.001]
                    )
                    # The thumb pad must close on the handle, not hover beside it.
                    * (4.0 if digit == "thumb" else 1.4),
                ]
                if digit != "thumb":
                    values.append((rv - axis * (rv @ axis)) * 0.030)
                if digit == "thumb":
                    pad = v[tip].mean(0)
                    values.extend(
                        [
                            (radial(pad) - target) * 0.006,
                            np.array([pad @ axis - axial_target]) * 0.75,
                        ]
                    )
                return np.concatenate(values)

            # Inward MCP rotation is bounded. The thumb has more CMC opposition.
            limit = 1.05 if digit == "thumb" else 0.42
            sol = least_squares(
                residual,
                np.zeros(3),
                bounds=(-limit, limit),
                max_nfev=35,
                ftol=1e-6,
                xtol=1e-6,
            )
            return q[h][f] @ sol.x

        # Angles between keys are interpolated. Where an in-between frame still
        # cuts into the handle, solve that frame too and interpolate again.
        moving = strength[:, 0] > 0.5
        start = out[:, ids].copy()
        frame_keys = list(keys)
        for _ in range(5):
            for f in frame_keys:
                if f not in solved:
                    solved[f] = solve(f)
            frame_keys = sorted(solved)
            local = np.stack(
                [
                    np.interp(np.arange(frames), frame_keys, k)
                    for k in np.array([solved[f] for f in frame_keys]).T
                ],
                axis=1,
            )
            rv = np.einsum("fi,fij->fj", local, q[h])
            rot = Rotation.from_rotvec(rv).as_matrix()
            out[:, ids] = start + strength * (cloud @ rot.transpose(0, 2, 1) - cloud)
            inside = np.array(
                [sdf(out[f, ids[moving]], handle, f).min() for f in range(frames)]
            )
            bad = [f for f in np.flatnonzero(inside < -0.0007) if f not in solved]
            if not bad:
                break
            # The deepest frame of each run of consecutive bad frames.
            runs = np.split(np.array(bad), np.flatnonzero(np.diff(bad) > 1) + 1)
            frame_keys = [int(r[np.argmin(inside[r])]) for r in runs]
        gaps = np.array([sdf(out[f, ids], handle, f) for f in range(frames)])
        checks[digit] = [
            round(1000 * gaps.min(), 2),
            round(1000 * gaps[:, tip].min(1).max(), 2),
        ]
    return checks


def clearance(palm, handle):
    """Smallest per-frame handle shift, across its axis, that keeps the palm out of it."""
    from scipy.ndimage import gaussian_filter1d
    from scipy.optimize import least_squares

    frames = len(palm)
    offsets = np.zeros((frames, 3))

    def solve(f, start):
        axis = handle[2][f]
        u = unit(np.cross(axis, [0.0, 0.0, 1.0] if abs(axis[2]) < 0.9 else [1.0, 0, 0]))
        w = np.cross(axis, u)
        basis = np.stack([u, w])
        x0 = basis @ start

        def residual(x):
            d = x @ basis
            return np.concatenate(
                [np.minimum(sdf(palm[f] - d, handle, f) - 0.001, 0) * 10, x * 0.02]
            )

        return least_squares(residual, x0).x @ basis

    for f in range(frames):
        if sdf(palm[f], handle, f).min() < -0.0005:
            offsets[f] = solve(f, np.zeros(3))
    if not offsets.any():
        return offsets
    # Ease the shift in and out over a few frames; re-solve any frame it leaves inside.
    offsets = gaussian_filter1d(offsets, 3.0, axis=0, mode="nearest")
    for f in range(frames):
        if sdf(palm[f] - offsets[f], handle, f).min() < -0.0005:
            offsets[f] = solve(f, offsets[f])
    return offsets


def shift_equipment(machine, part, offsets, acts):
    """Move the handle and every part rigidly attached to it (constant distance)."""

    def centroid(o):
        v = np.asarray(o["verts"], float).reshape(-1, 3).mean(0)
        m = np.asarray(o["m"], float).reshape(-1, 4, 4).transpose(0, 2, 1)
        return np.einsum("j,fij->fi", v, m[:, :3, :3]) + m[:, :3, 3]

    objects = machine["objects"]
    anchor = centroid(next(o for o in objects if o["name"] == part))
    count = len(anchor)
    times = track_times(count, machine.get("acts"))
    shift = np.stack([np.interp(times, acts, offsets[:, k]) for k in range(3)], axis=1)
    moved = []
    for o in objects:
        shape = np.asarray(o["m"]).shape
        m = np.asarray(o["m"], float).reshape(-1, 16)
        if len(m) != count:
            continue
        if np.ptp(np.linalg.norm(centroid(o) - anchor, axis=1)) > 0.003:
            continue
        m[:, 12:15] += shift
        o["m"] = m.reshape(shape).tolist()
        moved.append(o["name"])
    return moved


class Folder:
    """Read an unpacked viewer3d folder with the same names as inside the APK."""

    def __init__(self, path):
        self.path = Path(path)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, name):
        return (self.path / name[len(PREFIX) :]).read_bytes()

    def namelist(self):
        return [
            PREFIX + p.relative_to(self.path).as_posix()
            for p in self.path.rglob("*")
            if p.is_file()
        ]


def open_source(path):
    return Folder(path) if Path(path).is_dir() else zipfile.ZipFile(path)


def convert(clip, apk, outdir, tr):
    from build_app3d_v5 import pack_motion

    with open_source(apk) as z:
        key = clip["id"]
        machine = json.loads(z.read(PREFIX + "data/" + key + ".json"))
        acts, points = decode(z.read(PREFIX + "human_v5/" + key + ".bin"))
        result, q, t = tr.skin(points)
        options = handles(grip_objects(machine["objects"]), acts, machine.get("acts"))
        row = {}
        chosen = {}
        for side in "lr":
            ids = tr.u[:, tr.names.index("middle_02_" + side)] > 0.9
            if not options:
                continue
            mid = len(acts) // 2
            handle = min(
                options, key=lambda h: abs(sdf(result[mid, ids], h, mid)).min()
            )
            near = [
                abs(sdf(result[f, ids], handle, f)).min()
                for f in (0, mid, len(acts) - 1)
            ]
            if max(near) > 0.023:
                continue
            chosen[side] = handle[0]
        # Some source poses put the palm itself inside the handle, which no
        # finger angle can fix. There, shift the handle just clear of the fitted
        # hand and fit the fingers again.
        shifted = {}
        source = result
        for attempt in range(4):
            result = source.copy()
            for side, part in chosen.items():
                handle = next(h for h in options if h[0] == part)
                row[side] = {
                    "part": part,
                    "pad_mm": fit_hand(tr, result, q, t, side, handle),
                }
            if attempt == 3:
                break
            again = False
            for part in set(chosen.values()):
                sides = [s for s in chosen if chosen[s] == part]
                hand = np.flatnonzero(
                    sum(
                        tr.u[:, tr.names.index(f"{b}_{s}")]
                        for s in sides
                        for b in ("hand",)
                        + tuple(f"{d}_0{k}" for d in DIGITS for k in (1, 2, 3))
                    )
                    > 0.5
                )
                handle = next(h for h in options if h[0] == part)
                offsets = clearance(result[:, hand], handle)
                # A large shift means the source pose does not hold this handle at
                # all (e.g. the hand turned 90 degrees from it). Moving the handle
                # cannot fix that; leave it for the motion itself to be corrected.
                if np.linalg.norm(offsets, axis=1).max() + shifted.get(part, (0,))[0] / 1000 > 0.008:
                    continue
                if offsets.any():
                    moved = shift_equipment(machine, part, offsets, acts)
                    total = shifted.get(part, (0, moved))[0]
                    shifted[part] = (
                        round(total + 1000 * np.linalg.norm(offsets, axis=1).max(), 1),
                        moved,
                    )
                    again = True
            if not again:
                break
            options = handles(grip_objects(machine["objects"]), acts, machine.get("acts"))
        for side, part in chosen.items():
            if part in shifted:
                row[side]["handle_shift_mm"], row[side]["shifted_parts"] = shifted[part]
        blob, error = pack_motion(dict(acts=acts, frames=result), len(tr.n))
        (outdir / "human_v5" / (key + ".bin")).write_bytes(blob)
        (outdir / "data" / (key + ".json")).write_text(
            json.dumps(machine, ensure_ascii=False, separators=(",", ":")),
            encoding="utf8",
        )
        row_report = {"grips": row, "cache_error_mm": error}
        print(
            key,
            len(acts),
            [(s, r["part"], r["pad_mm"]["thumb"]) for s, r in row.items()],
            flush=True,
        )
        return key, row_report


def main():
    from build_app3d_v5 import pack_motion

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path, help="APK or unpacked viewer3d folder")
    parser.add_argument("output", type=Path)
    parser.add_argument("--clips", nargs="+")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--blender",
        default=r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
    )
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Choose a new viewer-copy directory")
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "rig.json"
        subprocess.run(
            [
                args.blender,
                "-b",
                str(REPO / "promo/cast/src_v5_rig.blend"),
                "--python-exit-code",
                "1",
                "-P",
                __file__,
                "--",
                "dump",
                str(path),
            ],
            check=True,
        )
        rig = json.loads(path.read_text())
    with open_source(args.apk) as z:
        read = lambda name: json.loads(z.read(PREFIX + name))
        tr = Transfer(read("human_v5/base.json"), rig)
        manifest = read("human_v5/manifest.json")
        mapping = read("exercise_models.json")
        selected = set(args.clips or [c["id"] for c in manifest["clips"]])
        clips = [c for c in manifest["clips"] if c["id"] in selected]
        assert len(clips) == len(selected)
        outdir = args.output
        (outdir / "human_v5").mkdir(parents=True)
        (outdir / "data").mkdir()
        for name in z.namelist():
            if name.startswith(PREFIX + "three/") or name in {
                PREFIX + n
                for n in ("index.html", "camera_views.json", "human_stats.html")
            }:
                dst = outdir / name[len(PREFIX) :]
                dst.parent.mkdir(parents=True, exist_ok=True)
                if not name.endswith("/"):
                    dst.write_bytes(z.read(name))

        def write(path, obj):
            (outdir / path).write_text(
                json.dumps(obj, ensure_ascii=False, separators=(",", ":")),
                encoding="utf8",
            )

        report = {}
        from concurrent.futures import ProcessPoolExecutor

        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            jobs = [pool.submit(convert, clip, args.apk, outdir, tr) for clip in clips]
            for job in jobs:
                key, row = job.result()
                report[key] = row
        write("human_v5/base.json", tr.base)
        write(
            "human_v5/manifest.json",
            {**manifest, "revision": "v5-hands-local", "clips": clips},
        )
        write(
            "exercise_models.json",
            {k: v for k, v in mapping.items() if set(v) <= selected},
        )
        write("hand_fit_report.json", report)


if __name__ == "__main__":
    if "--" in sys.argv and sys.argv[sys.argv.index("--") + 1] == "dump":
        dump_rig(sys.argv[-1])
    else:
        main()
