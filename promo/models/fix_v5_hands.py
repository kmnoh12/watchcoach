"""Rebuild only the two distal hand patches of the V5 promo rig (Blender 5.2).
Run: blender -b --python-exit-code 1 -P promo/models/fix_v5_hands.py
The forearm cut is distal to the watch center at 55 mm. All dimensions below are metres.
Digit landmarks follow the existing rig, including its non-connected phalanges.
"""

import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

SOURCE = Path(__file__).resolve().parents[1] / "cast" / "src_v5_rig.blend"
DIGITS = ("pinky", "ring", "middle", "index")
VERSION = "v5_hand_patch_1"


def bridge(bm, first, second):
    """Join cyclic contours with unequal counts by matching perimeter progress."""

    def fractions(loop):
        lengths = [(v.co - loop[i - 1].co).length for i, v in enumerate(loop)]
        total = sum(lengths)
        values = [0.0]
        for length in lengths[1:] + lengths[:1]:
            values.append(values[-1] + length / total)
        return values

    u, v = fractions(first), fractions(second)
    i = j = 0
    while i < len(first) or j < len(second):
        a, b = first[i % len(first)], second[j % len(second)]
        ni = u[i + 1] if i < len(first) else 2
        nj = v[j + 1] if j < len(second) else 2
        face = [a]
        if ni <= nj + 0.018:
            i += 1
            face.append(first[i % len(first)])
        if nj <= ni + 0.018:
            j += 1
            face.append(second[j % len(second)])
        face.append(b)
        bm.faces.new(face)


def loft(start, out, surface, end, f):
    """Forearm loop point: on the source surface at the cut, easing into the
    straight line toward the wrist collar. Never more than 1 mm outside that
    line, which removes the pointed ulnar vertex of the source mesh."""
    line = start.lerp(end, f)
    point = surface.lerp(line, f * f * (3 - 2 * f))
    bulge = (point - line).dot(out)
    if bulge > 0.001:
        point -= out * (bulge - 0.001)
    return point


def align(loop, target):
    """Choose start and winding by geometric correspondence, preserving adjacency."""

    def score(order):
        return sum(
            (
                v.co - target[round(i * len(target) / len(order)) % len(target)].co
            ).length_squared
            for i, v in enumerate(order)
        )

    options = []
    for ring in (loop, list(reversed(loop))):
        options.extend(ring[i:] + ring[:i] for i in range(len(ring)))
    return min(options, key=score)


def hand(bm, body, rig, side):
    suffix = "_" + side
    sign = 1 if side == "l" else -1

    # Work from a single set of anatomical landmarks for exact mirror geometry.
    def mirrored(co):
        return Vector((co.x * sign, co.y, co.z))

    def landmark(name, tail=False):
        bone = rig.data.bones[name + "_l"]
        return mirrored(bone.tail_local if tail else bone.head_local)

    wrist = landmark("hand")
    fore = (wrist - landmark("lowerarm")).normalized()
    forward = (landmark("middle_01", True) - landmark("middle_01")).normalized()
    span = landmark("index_01") - landmark("pinky_01")
    dorsal = span.cross(forward).normalized() * sign
    across = forward.cross(dorsal).normalized() * sign
    layer = bm.verts.layers.deform.active
    group = {
        g.name[:-2]: g.index for g in body.vertex_groups if g.name.endswith(suffix)
    }
    created = []  # identical on both sides; the right side is mirrored from the left
    fitted = []  # follows each side's own forearm, which is not exactly mirrored
    lofted = []

    def vert(co, weights, mirror=True):
        v = bm.verts.new(co)
        (created if mirror else fitted).append(v)
        for name, weight in weights.items():
            if weight:
                v[layer][group[name]] = weight
        return v

    # Bisect triangles in their original planes. This keeps the band-contact
    # surface, even where an oblique old wrist triangle runs under the band.
    # Cut above the watch seat. Below it the source forearm is a fan of long
    # triangles converging on a pointed ulnar vertex; it is replaced by a loft.
    plane = wrist - fore * 0.095
    source = BVHTree.FromBMesh(bm)  # the forearm surface before the cut
    local = {
        v for v in bm.verts if (v.co - wrist).length < 0.235 and v.co.x * sign > 0.31
    }
    faces = {f for v in local for f in v.link_faces}
    edges = {e for f in faces for e in f.edges}
    cut = bmesh.ops.bisect_plane(
        bm, geom=list(faces | edges | local), dist=1e-7, plane_co=plane, plane_no=fore
    )
    seam = {v for v in cut["geom_cut"] if isinstance(v, bmesh.types.BMVert)}
    bmesh.ops.delete(
        bm,
        geom=[v for v in local if v.is_valid and (v.co - plane).dot(fore) > 1e-6],
        context="VERTS",
    )
    # The strap follows the forearm bone. The old 25% hand influence under
    # its seat pulled the skin through the case when the hand pivoted.
    for v in seam | {v for v in local if v.is_valid}:
        weights = v[layer]
        if group["hand"] in weights or v in seam:
            weights.clear()
            weights[group["lowerarm"]] = 1.0
    ring = [min(seam, key=lambda v: (v.co - wrist).dot(across))]
    while len(ring) < len(seam):
        choices = [
            e.other_vert(ring[-1])
            for e in ring[-1].link_edges
            if e.is_boundary
            and e.other_vert(ring[-1]) in seam
            and e.other_vert(ring[-1]) not in ring
        ]
        if not choices:
            raise ValueError("The forearm cut must be a single closed loop")
        ring.append(choices[0])

    def pos(x, y, z):
        return wrist + across * x + forward * y + dorsal * z

    def collar(y, center, half_width, depth, tilt, hand_weight):
        return [
            vert(
                pos(
                    center + half_width * math.cos(t),
                    y,
                    depth * math.sin(t) + tilt * math.cos(t),
                ),
                {"lowerarm": 1 - hand_weight, "hand": hand_weight},
            )
            for t in [i * math.pi / 6 for i in range(12)]
        ]

    # Continue every edge of the sparse source forearm down to an elliptical
    # wrist collar, so its long facets run on to the wrist at the same density.
    # Each strip starts on the source surface and eases into the straight line
    # to the collar; the pointed ulnar vertex of the source is not followed.
    center = sum((v.co for v in ring), Vector()) / len(ring)
    proximal_center = pos(-0.015, -0.032, 0)
    ellipse = [
        pos(
            -0.015 + 0.0305 * math.cos(t),
            -0.032,
            0.0165 * math.sin(t) - 0.011 * math.cos(t),
        )
        for t in [i * math.pi / 360 for i in range(720)]
    ]

    def flat(v):
        return (v - fore * v.dot(fore)).normalized()

    proximal, outward = [], []
    for r in ring:
        d = flat(r.co - center)
        e = max(ellipse, key=lambda q: flat(q - proximal_center).dot(d))
        proximal.append(vert(e, {"lowerarm": 0.94, "hand": 0.06}, mirror=False))
        outward.append(d)
    rows_ = [ring]
    for f in (1 / 3, 2 / 3):
        row = []
        for r, d, p in zip(ring, outward, proximal):
            hit, _, _, _ = source.ray_cast(center.lerp(proximal_center, f), d)
            surface = hit if hit else r.co.lerp(p.co, f)
            c = r.co.copy()
            v = vert(
                loft(c, d, surface, p.co, f),
                {"lowerarm": 1 - 0.06 * f, "hand": 0.06 * f},
                mirror=False,
            )
            lofted.append((v, c, d, surface, p, f))
            row.append(v)
        rows_.append(row)
    rows_.append(proximal)
    for lo, hi in zip(rows_, rows_[1:]):
        for i in range(len(ring)):
            bm.faces.new([lo[i - 1], lo[i], hi[i], hi[i - 1]])
    # The wrist collar meets the hand's twelve-point root at the wrist crease.
    root = collar(-0.014, -0.009, 0.0305, 0.017, -0.006, 0.24)
    bridge(bm, align(proximal, root), root)

    # Each row has nine dorsal/palmar stations across four metacarpals,
    # plus the mid-height point on each side wall. Internal webs share vertices.
    rows = []
    for row in range(3):
        top, bottom = [], []
        for j in range(9):
            u = (j - 4) / 4
            x = (
                -0.005
                + u * (0.035, 0.043, 0.044)[row]
                + max(u, 0) ** 2 * (0.009, 0.004, 0)[row]
            )
            arch = 1 - u * u
            y = (
                (0.006, 0.039, 0.066)[row]
                + (0.004, 0.007, 0.002)[row] * arch
                - (0.009, 0.002, 0.002)[row] * max(u, 0)
                - (0, 0.002, 0.008)[row] * max(-u, 0) ** 2
            )
            z = -0.003 - 0.003 * row / 2 - (0.006, 0.002, 0)[row] * u
            thenar = math.exp(-(((u - 0.64) / 0.42) ** 2))
            weights = {"hand": (0.70, 0.99, 1)[row], "lowerarm": (0.30, 0.01, 0)[row]}
            top.append(
                vert(
                    pos(x, y, z + 0.006 + 0.008 * arch + 0.003 * (1 - abs(u))), weights
                )
            )
            bottom.append(
                vert(
                    pos(
                        x,
                        y + 0.002,
                        z
                        - 0.006
                        - 0.011 * thenar
                        - 0.004 * math.exp(-(((u + 0.65) / 0.3) ** 2))
                        - 0.002 * arch,
                    ),
                    weights,
                )
            )
        mids = {
            j: vert((top[j].co + bottom[j].co) * 0.5, {"hand": 1})
            for j in (range(0, 9, 2) if row == 2 else (0, 8))
        }
        rows.append((top, bottom, mids))

    def outline(row):
        t, b, m = row
        return t + [m[8]] + list(reversed(b)) + [m[0]]

    perimeter = outline(rows[0])
    bridge(bm, align(root, perimeter), perimeter)
    for k in range(2):
        t, b, m = rows[k]
        T, B, M = rows[k + 1]
        for j in range(8):
            for lo, hi in ((t, T), (b, B)):
                bm.faces.new([lo[j], lo[j + 1], hi[j + 1], hi[j]])
        for j in (0, 8):
            if j == 8 and k == 0:  # thenar opening in radial side wall
                continue
            for lo, hi in ((t, T), (b, B)):
                bm.faces.new([lo[j], m[j], M[j], hi[j]])

    def digit(name, socket, width, depth):
        bones = [name + "_0" + str(i) for i in (1, 2, 3)]
        h = [landmark(n) for n in bones] + [landmark(bones[-1], True)]
        # Narrow faceted pads taper to a small bevel at the fingertip. Paired
        # support rings bracket each joint to spread its rotation over the skin.
        previous = socket
        for k in range(3):
            axis = (h[k + 1] - h[k]).normalized()
            lateral = (across - axis * across.dot(axis)).normalized()
            normal = lateral.cross(axis).normalized() * sign
            stations = (
                ((0.40, 1.0), (0.66, 0.96))
                if k == 0
                else ((0.0, 0.98), (0.37, 0.93), (0.66, 0.86))
                if k == 1
                else ((0.0, 0.88), (0.40, 0.83), (0.69, 0.76), (0.93, 0.53))
            )
            if k == 0 and name == "thumb":
                stations = ((0.84, 1.12),)
            for fraction, taper in stations:
                if k == 2 and name in ("pinky", "ring"):
                    end = h[k].lerp(h[k + 1], 0.77 if name == "ring" else 0.80)
                else:
                    end = h[k + 1]
                c = h[k].lerp(end, fraction)
                # The thumb web fans toward the index metacarpal, then narrows at the IP joint.
                base_flare = (1.12 if k == 0 else 1.0) if name == "thumb" else 1.0
                weights = {bones[k]: 1.0}
                if k > 0 and fraction <= 0.26:
                    mix = 0.5 if fraction == 0 else 0.10
                    weights = {bones[k - 1]: mix, bones[k]: 1 - mix}
                elif fraction >= 0.66 and k < 2:
                    weights = {bones[k]: 0.90, bones[k + 1]: 0.10}
                section = [
                    vert(
                        c
                        + lateral * (x * width * taper * base_flare)
                        + normal * (z * depth * taper),
                        weights,
                    )
                    for x, z in (
                        (-0.67, 0.90),
                        (0, 1),
                        (0.67, 0.90),
                        (1, 0),
                        (0.72, -0.78),
                        (0, -1),
                        (-0.72, -0.78),
                        (-1, 0),
                    )
                ]
                if previous is socket:
                    bridge(bm, align(previous, section), section)
                else:
                    for i in range(8):
                        bm.faces.new(
                            [previous[i - 1], previous[i], section[i], section[i - 1]]
                        )
                previous = section
        tip = vert(end, {bones[-1]: 1})
        for i in range(8):
            bm.faces.new([previous[i - 1], previous[i], tip])

    t, b, m = rows[-1]
    for i, name in enumerate(DIGITS):
        j = 2 * i
        socket = [t[j], t[j + 1], t[j + 2], m[j + 2], b[j + 2], b[j + 1], b[j], m[j]]
        # Shared webs remain primarily on the palm, central knuckle pads follow flexion.
        for v in (t[j + 1], b[j + 1]):
            v[layer][group["hand"]] = 0.58
            v[layer][group[name + "_01"]] = 0.42
        for col in (j, j + 2):
            for v in (t[col], b[col], m[col]):
                portion = 0.21 if col not in (0, 8) else 0.42
                v[layer][group["hand"]] -= portion
                v[layer][group[name + "_01"]] = portion
        digit(
            name,
            socket,
            (0.0084, 0.0102, 0.0105, 0.0100)[i],
            (0.0076, 0.0090, 0.0092, 0.0088)[i],
        )
    t, b, m = rows[0]
    T, B, M = rows[1]
    # The CMC pivots through the thenar pad. Spread opposition into the
    # radial palm instead of stretching a single strip between palm and thumb.
    for top, bottom, mid in rows[:2]:
        for v, share in ((top[7], .14), (bottom[7], .22), (top[8], .46),
                         (bottom[8], .52), (mid[8], .56)):
            for joint, value in list(v[layer].items()):
                v[layer][joint] = value * (1 - share)
            v[layer][group["thumb_01"]] = share
    digit("thumb", [t[8], T[8], M[8], B[8], b[8], m[8]], 0.0130, 0.0105)

    return created, fitted, lofted


def main():
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    body = bpy.data.objects["V5_Body"]
    if body.data.get("hand_patch") == VERSION:
        print("V5 hand patch already applied")
        return
    rig = bpy.data.objects["V5_CommonRig"]
    assert len(rig.data.bones) == 52 and len(body.data.vertices) == 893, (
        "Unexpected source rig"
    )
    bm = bmesh.new()
    bm.from_mesh(body.data)
    old_faces = set(bm.faces)
    left, fit_l, loft_l = hand(bm, body, rig, "l")
    right, fit_r, loft_r = hand(bm, body, rig, "r")
    # Round the new skin, keeping the cut contour where it meets the source arm.
    # Both sides are smoothed together (the source forearms are not exactly
    # mirrored), then the hand is copied left to right for exact symmetry.
    # The watch strap is refit to the resulting surface by build_v5_with_watch.py.
    for _ in range(3):
        bmesh.ops.smooth_vert(
            bm,
            verts=left + right + fit_l + fit_r,
            factor=0.38,
            use_axis_x=True,
            use_axis_y=True,
            use_axis_z=True,
        )
        # Smoothing would pinch the straight forearm loft into a cuff at the
        # cut; keep its loops on the lines to the (smoothed) wrist collar.
        for v, c, d, surface, p, f in loft_l + loft_r:
            v.co = loft(c, d, surface, p.co, f)
    for lv, rv in zip(left, right, strict=True):
        rv.co = (-lv.co.x, lv.co.y, lv.co.z)
    new_faces = [f for f in bm.faces if f not in old_faces]
    bmesh.ops.recalc_face_normals(bm, faces=new_faces)
    for f in new_faces:
        f.smooth = False
    assert all(e.is_manifold for f in new_faces for e in f.edges), "Open hand patch"
    bm.to_mesh(body.data)
    bm.free()
    body.data.update()
    body.data["hand_patch"] = VERSION
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE), compress=True)


if __name__ == "__main__":
    main()
