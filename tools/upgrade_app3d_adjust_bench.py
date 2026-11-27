"""Append only fitted adjustable-bench overlays. Run after plates and cable towers.
Preserve preceding WGM records verbatim, including animated weight plates on shared clips.
"""

import argparse
import json
from pathlib import Path
import struct

import numpy as np
from scipy.spatial.transform import Rotation
from upgrade_app3d_machines import (
    PartCatalogPacker,
    decompose_frames,
    load_wgp2_human_frames,
    pack_clip,
    strip_fake_animation,
)
from bench_fit import fit, swept_clear
from body_fit import SkinSweep
from scene_lat_parts import _nine
from selector_tower import CHARCOAL, STEEL, YELLOW, cylinder, drilled_slider
from part_registry import MAT_ACCENT, MAT_CHROME, MAT_FRAME, MAT_PAD, MAT_RUBBER

HERE = Path(__file__).resolve().parent / "viewer3d"


def load(path):
    return json.loads(path.read_text())


def catalog_records(stock):
    """Index exact WGC2 geometry, including shading flags and any UV payload."""
    magic, count = struct.unpack_from("<4sI", stock)
    assert magic == b"WGC2"
    offset = 8
    for _ in range(count):
        nv, nt, flags = struct.unpack_from("<HHB", stock, offset)
        size = 32 + nv * (6 + 4 * bool(flags & 2)) + nt * 6
        yield stock[offset : offset + size]
        offset += size
    assert offset == len(stock)


def object_pose(o):
    mats = strip_fake_animation(o["m"])
    assert len(mats) == 1
    p, q, s = decompose_frames(mats)
    return p[0], Rotation.from_quat(q[0]), s[0]


def ends(o):
    p, r, s = object_pose(o)
    v = np.array(o["verts"]).reshape(-1, 3) * s
    lo, hi = v.min(0), v.max(0)
    axis = (hi - lo).argmax()
    e = np.tile((lo + hi) / 2, (2, 1))
    e[:, axis] = [lo[axis], hi[axis]]
    v = r.apply(e) + p
    return v[np.argsort(v[:, 2])]


def layers(parts, o):
    # The source piping can be disconnected at material boundaries. Stretch the same
    # central strip on every layer, not each material's own bounding box.
    p, r, s = object_pose(o)
    old = np.array(o["verts"]).reshape(-1, 3) * s
    h = np.ptp(old, axis=0).round(5) / 2
    orig = np.vstack([x["v"] for x in parts])
    a, b = orig.min(0), orig.max(0)
    mid = (a + b) / 2
    half = (b - a) / 2
    out = []
    for part in parts:
        v = np.array(part["v"]) - mid
        for j, band in enumerate([0.04, 0.07, 0.018]):
            v[:, j] = _nine(v[:, j], half[j], h[j], band)
        out.append((v, np.array(part["t"]).reshape(-1, 3)))
    return out


def tube(collar=False):
    """Hollow square sleeve. Collar has aligned through-bores on both walls."""
    v = []
    t = []

    def ring(pts):
        idx = np.arange(len(pts)) + len(v)
        v.extend(pts)
        return idx

    def strip(a, b):
        for i in range(len(a)):
            j = (i + 1) % len(a)
            t.extend([(a[i], a[j], b[j]), (a[i], b[j], b[i])])

    if not collar:
        rings = [
            ring([(x * r, y * r, z) for x, y in [(-1, -1), (1, -1), (1, 1), (-1, 1)]])
            for r, z in [(0.021, 0), (0.021, 1), (0.014, 1), (0.014, 0)]
        ]
        for i in range(4):
            strip(rings[i], rings[(i + 1) % 4])
    else:
        th = np.pi / 4 + np.arange(16) * np.pi / 8
        c, s = np.cos(th), np.sin(th)
        m = np.maximum(abs(c), abs(s))
        rings = []
        for sign in (-1, 1):
            outer, inner, oh, ih = [
                ring(np.column_stack((np.full(16, x * sign), y, z)))
                for x, y, z in [
                    (0.021, 0.021 * c / m, 0.010 * s / m),
                    (0.014, 0.014 * c / m, 0.010 * s / m),
                    (0.021, 0.0038 * c, 0.0038 * s),
                    (0.014, 0.0038 * c, 0.0038 * s),
                ]
            ]
            if sign < 0:
                strip(oh, outer)
                strip(inner, ih)
                strip(ih, oh)
            else:
                strip(outer, oh)
                strip(ih, inner)
                strip(oh, ih)
            rings.append((outer, inner))
        for j in range(16):
            k = (j + 1) % 16
            side = abs(c[j] / m[j] - c[k] / m[k]) < 1e-7
            L, I = rings[0]
            R, J = rings[1]

            def quad(a, b, c, d):
                t.extend([(a, b, c), (a, c, d)])

            if side:
                quad(L[j], L[k], R[k], R[j])
                quad(J[j], J[k], I[k], I[j])
            else:
                quad(L[j], L[k], I[k], I[j])
                quad(J[j], J[k], R[k], R[j])
            if j in (0, 4, 8, 12):
                if s[j] > 0 and c[j] > 0 or s[j] < 0 and c[j] < 0:
                    quad(R[j], L[j], I[j], J[j])
                else:
                    quad(L[j], R[j], J[j], I[j])
    return np.array(v), np.array(t)


def assemble(key, raw, mapping, source, frames, base):
    objs = {o["name"]: o for o in raw["objects"]}
    assert len(objs) == len(raw["objects"])
    for name, (idx, g) in mapping.items():
        assert raw["objects"][idx]["name"] == name
    rows = []
    meta = {}
    sw = SkinSweep(frames, np.asarray(base["triangles"]).reshape(-1, 3))
    one = np.ones(3)

    def put(name, mesh, pos, rot, scale, mat, color, smooth=False):
        v, t = mesh
        world = rot.apply(v * scale) + pos
        if not swept_clear(sw, world):
            raise ValueError(name + ": swept body overlaps proposed support envelope")
        rows.append(
            dict(
                name=name,
                verts=v,
                tris=np.ravel(t),
                pos=np.array([pos]),
                quats=rot.as_quat()[None, :],
                sc=np.array([scale]),
                smooth=smooth,
                mat=mat,
                color=color,
            )
        )

    def hardware(name, anchor, head):
        d = head - anchor
        length = np.linalg.norm(d)
        az = d / length
        ax = np.array([1.0, 0, 0])
        ax -= az * ax.dot(az)
        ax /= np.linalg.norm(ax)
        r = Rotation.from_matrix(np.stack((ax, np.cross(az, ax), az), axis=1))
        # Keep full width; on short seat columns shorten the insert and its index pitch.
        f = min(1.0, (length - 0.015) / 0.24)
        pitch = 0.020 * f
        exposed = 4.5 * pitch
        collar = head - exposed * az
        low = length - exposed - 0.010
        assert low > 0
        put(name, tube(), anchor, r, [1, 1, low], MAT_FRAME, CHARCOAL)
        put(name, tube(True), collar, r, one, MAT_FRAME, CHARCOAL)
        put(name, drilled_slider(), head, r, [1, 1, f], MAT_CHROME, STEEL)
        put(name, cylinder(0.003, 0.054, 0, 16), collar, r, one, MAT_CHROME, STEEL)
        put(
            name,
            cylinder(0.009, 0.011, 0, 20),
            collar + 0.026 * ax,
            r,
            one,
            MAT_ACCENT,
            YELLOW,
        )

    def original(name, transform):
        o = objs[name]
        p, r, s = object_pose(o)
        p, r = transform(p, r)
        v = np.array(o["verts"]).reshape(-1, 3)
        size = np.ptp(v, axis=0)
        # Same mount/rail, different dimensions: share normalized geometry, size per instance.
        vertices = np.round(v / size, 6) + 0.0
        put(
            name,
            (vertices, np.array(o["tris"])),
            p,
            r,
            s * size,
            MAT_FRAME,
            o["color"],
        )

    used = set()
    for name in ("back", "incline_pad", "seat"):
        if name not in mapping:
            continue
        o = objs[name]
        p, r, s = object_pose(o)
        role = mapping[name][1].split("__")[0]
        parts = source[role]
        meshes = layers(parts, o)
        if name == "seat":
            pivot = None
        elif "hinge" in objs:
            pivot = object_pose(objs["hinge"])[0]
        elif "back_rail" in objs:
            pivot = ends(objs["back_rail"])[0]
        else:
            pivot = ends(objs["front_post"])[1]
        v = np.vstack([m[0] for m in meshes[:2]])
        faces = np.vstack([meshes[0][1], meshes[1][1] + len(meshes[0][0])])
        anatomy = "arm_pad" if name == "incline_pad" else role
        try:
            nr, at, gap = fit(frames, base, anatomy, (p, r), (v, faces), pivot)
        except ValueError as ex:
            raise ValueError(f"{name}: {ex}") from ex
        assert 0.002 <= gap <= 0.005
        for (vv, t), slot in zip(meshes, parts):
            put(
                name,
                (vv, t),
                at,
                nr,
                one,
                MAT_RUBBER if slot["material"] == "E_grip" else MAT_PAD,
                slot["rgb"],
                slot["material"] != "E_grip",
            )
        delta = nr * r.inv()
        xf = lambda pt, rot: (at + delta.apply(pt - p), delta * rot)
        used.add(name)
        meta[name] = dict(
            axis=([0, 0, 1] if pivot is None else r.apply([1, 0, 0]).round(7).tolist()),
            pivot=None if pivot is None else pivot.tolist(),
            skin=anatomy,
            gap_mm=round(1000 * gap, 3),
            dz_mm=round(1000 * (at - p)[2], 2),
            angle_deg=round(np.degrees(delta.magnitude()), 3),
        )
        related = (
            ("seat_mount", "seat_rail")
            if name == "seat"
            else ("back_mount", "back_rail", "hinge_link", "spine")
        )
        for n in mapping:
            if n.split(".")[0] in related:
                original(n, xf)
                used.add(n)
        brace = (
            "seat_post"
            if name == "seat"
            else next(
                n for n in ("telescopic_brace", "back_brace", "rear_post") if n in objs
            )
        )
        low, high = ends(objs[brace])
        hardware(brace, low, xf(high, r)[0])
        used.add(brace)
    assert used == set(mapping)
    return rows, meta


def append_batch(view, *, targets_file="adjust_bench_targets.json", source_file="scene_bench_source.json",
                 report_file="adjust_bench_fit.json", build_model=assemble, covered_slots=None):
    d = view / "data"
    h = view / "human_v5"
    base = load(h / "base.json")
    assert base["vertices"] == 1401
    mf = load(d / "wgm_manifest.json")
    stock = (d / "parts.bin").read_bytes()
    magic, n = struct.unpack_from("<4sI", stock)
    assert magic == b"WGC2"
    targets = load(HERE / targets_file)
    source = load(HERE / source_file)
    indices = {part: i for i, part in enumerate(catalog_records(stock))}
    extra = []
    updates = {}
    report = {}
    for key, mapping in targets.items():
        raw = load(d / (key + ".json"))
        previous = mf.get("machineOverlays", {}).get(key)
        oldtargets = (previous or {}).get(
            "targets", mf.get("plateOverlays", {}).get(key, {})
        )
        new = {str(i): name for name, (i, g) in mapping.items()}
        covered = (covered_slots or {}).get(key, {})
        oldcovered = (previous or {}).get("covered", {})
        assert not (set(new) | set(covered)) & (set(oldtargets) | set(oldcovered))
        assert not set(new) & set(covered) and (key not in mf["clips"] or oldtargets)
        assert all(raw["objects"][int(i)]["name"] == name for i, name in covered.items())
        try:
            rows, fitmeta = build_model(
                key,
                raw,
                mapping,
                source,
                load_wgp2_human_frames(h / (key + ".bin")),
                base,
            )
        except ValueError as e:
            report[key] = {"unchanged": str(e)}
            print(key, str(e), flush=True)
            continue
        for row in rows:
            packer = PartCatalogPacker()
            packer.add(row["verts"], row["tris"], row["smooth"])
            part = packer.build_bytes()[8:]
            if part not in indices:
                indices[part] = n + len(extra)
                extra.append(part)
            row["part_id"] = indices[part]
        blob, _, _ = pack_clip(key, raw["acts"], rows)
        off = 8 + 4 * len(raw["acts"])
        oldcount = 0
        if oldtargets:
            old = (d / (key + ".wgm")).read_bytes()
            oldcount = struct.unpack_from("<H", old, 6)[0]
            assert old[:6] == blob[:6] and old[8:off] == blob[8:off]
            blob = (
                old[:6] + struct.pack("<H", oldcount + len(rows)) + old[8:] + blob[off:]
            )
        updates[key] = blob
        mf.setdefault("machineOverlays", {})[key] = dict(
            targets={**oldtargets, **new}, count=len(rows) + oldcount
        )
        if oldcovered or covered:
            mf["machineOverlays"][key]["covered"] = {**oldcovered, **covered}
        report[key] = {"pads": fitmeta, "records": len(rows), "preceding": oldcount}
        print(key, fitmeta, flush=True)
    for key, blob in updates.items():
        (d / (key + ".wgm")).write_bytes(blob)
    (d / "parts.bin").write_bytes(
        struct.pack("<4sI", magic, n + len(extra)) + stock[8:] + b"".join(extra)
    )
    mf["clips"] = sorted(set(mf["clips"]) | set(updates))
    (d / "wgm_manifest.json").write_text(json.dumps(mf, separators=(",", ":")))
    (d / report_file).write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", type=Path)
    append_batch(parser.parse_args().view)
