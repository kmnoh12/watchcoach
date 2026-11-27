"""Fitting a hinged back is a rotation, not a push along its surface normal.
Use stage 02's anatomy fit for the initial plane, then measure the actual upholstered crown.
"""

import numpy as np
from scipy.optimize import brentq
from scipy.spatial.transform import Rotation
from body_fit import contact_region, fit_body_part


def cross(a, b):
    return a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]


def top_gap(tri, v, faces):
    """Minimum +Z separation at projected triangle intersections (all incident skin faces).
    Extremum of the affine height difference occurs at a triangle vertex or edge crossing.
    Only upper skin of the cushion matters, not the coincident boundary of the stitch slot.
    """
    top = v[faces]
    n = np.cross(top[:, 1] - top[:, 0], top[:, 2] - top[:, 0])
    top = top[n[:, 2] > 1e-9]
    lo, hi = tri.min(1), tri.max(1)
    near = ((hi[:, :2] >= v.min(0)[:2]) & (lo[:, :2] <= v.max(0)[:2])).all(1)
    tri, lo, hi = tri[near], lo[near], hi[near]
    best = np.inf
    # Visit flat crown first; it normally provides a tight upper bound.
    for p in top[np.argsort(-top[:, :, 2].min(1))]:
        mn, mx = p.min(0), p.max(0)
        valid = ((hi[:, :2] >= mn[:2]) & (lo[:, :2] <= mx[:2])).all(1) & (
            lo[:, 2] < mx[2] + best
        )
        t = tri[valid]
        if not len(t):
            continue
        e = np.roll(p, -1, axis=0) - p
        g = np.roll(t, -1, axis=1) - t
        ab, ac = p[1] - p[0], p[2] - p[0]
        det = cross(ab, ac)
        q = t - p[0]
        u = cross(q, ac) / det
        w = cross(ab, q) / det
        gap = t[:, :, 2] - (p[0, 2] + u * ab[2] + w * ac[2])
        best = min(best, gap[(u >= 0) & (w >= 0) & (u + w <= 1)].min(initial=np.inf))
        ab, ac = t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]
        det = cross(ab, ac)
        ok = abs(det) > 1e-14
        det = np.where(ok, det, 1.0)
        for pt in p:
            q = pt - t[:, 0]
            u = cross(q, ac) / det
            w = cross(ab, q) / det
            z = t[:, 0, 2] + u * ab[:, 2] + w * ac[:, 2] - pt[2]
            best = min(
                best, z[ok & (u >= 0) & (w >= 0) & (u + w <= 1)].min(initial=np.inf)
            )
        for a, edge in zip(p, e):
            den = cross(g, edge)
            ok = abs(den) > 1e-14
            den = np.where(ok, den, 1.0)
            q = a - t
            u = cross(q, edge) / den
            w = cross(q, g) / den
            gap = t[:, :, 2] + u * g[:, :, 2] - (a[2] + w * edge[2])
            best = min(
                best,
                gap[ok & (u >= 0) & (u <= 1) & (w >= 0) & (w <= 1)].min(initial=np.inf),
            )
    if not np.isfinite(best):
        raise ValueError("no projected contact on cushion")
    return float(best)


def fit(frames, base, role, pose, geometry, pivot=None):
    pos, q = pose
    v, faces = geometry
    ax = q.apply([1, 0, 0])
    normal = q.apply([0, 0, 1])
    anatomy, _ = contact_region(base, role)

    # Work on the original skin samples; the independent final sweep covers between poses.
    def plane(r, p):
        surf = r.apply(v) + p
        axis = -r.apply([0, 0, 1])
        at = fit_body_part(frames, base, role, p, surf, axis, ax)
        return (at - p).dot(axis)

    def gap(r, p):
        local = np.einsum("fvi,ij->fvj", frames - p, r.as_matrix())
        return top_gap(local[:, anatomy].reshape(-1, 3, 3), v, faces)

    if pivot is None:
        # Physical height column is vertical even if the seat tilts slightly.
        p = pos + np.array([0, 0, -plane(q, pos) / normal[2]])
        measured = gap(q, p)
        if not 0.0024 <= measured <= 0.0046:

            def residual(dz):
                return gap(q, p + [0, 0, dz]) - 0.0035

            room = max(0.018, abs(measured - 0.0035) * 1.7)
            dz = brentq(residual, -room, room, xtol=0.00005)
            p = p + [0, 0, dz]
        if abs(p[2] - pos[2]) > 0.085:
            raise ValueError("seat would leave its supported height range")
        return q, p, gap(q, p)

    def pose_at(a):
        r = Rotation.from_rotvec(ax * a)
        return r * q, pivot + r.apply(pos - pivot)

    pitch = np.arctan2(q.apply([0, 1, 0])[2], q.apply([0, 0, 1])[2])
    l, h = (
        np.radians([max(0, np.degrees(pitch) - 25), min(85, np.degrees(pitch) + 25)])
        - pitch
    )

    def solve(fun, low, high):
        if fun(low) * fun(high) > 0:
            raise ValueError(
                "no contact solution on original hinge within bench travel"
            )
        return brentq(fun, low, high, xtol=0.00005)

    try:
        a = solve(lambda a: plane(*pose_at(a)), l, h)
    except ValueError:
        a = 0.0
    r, p = pose_at(a)
    measured = gap(r, p)
    if not 0.0024 <= measured <= 0.0046:
        a = solve(lambda a: gap(*pose_at(a)) - 0.0035, l, h)
        r, p = pose_at(a)
    return r, p, gap(r, p)


def swept_clear(sweep, world):
    """Refine ambiguous pad-plane overlaps, e.g. an arm grazing a rounded corner.
    A separating projection for all six endpoints proves separation throughout the interval.
    If these conservative hulls cannot be separated, the proposed model stays unmodified.
    """
    if sweep.clear(world):
        return True
    from itertools import combinations
    from scipy.spatial import ConvexHull

    hull = ConvexHull(world)
    pad = world[hull.vertices]
    planes = np.unique(hull.equations.round(10), axis=0)
    edges = hull.simplices
    pe = world[edges] - world[np.roll(edges, 1, axis=1)]
    pe = pe.reshape(-1, 3)
    pe = np.unique((pe / np.linalg.norm(pe, axis=1)[:, None]).round(8), axis=0)
    ij = np.array(list(combinations(range(6), 2)))
    ijk = np.array(list(combinations(range(6), 3)))
    fr, fi = np.nonzero(((sweep.hi >= pad.min(0)) & (sweep.lo <= pad.max(0))).all(2))

    def separates(skin, axes):
        axes = axes.reshape(-1, 3)
        npad = np.einsum("ij,kj->ik", pad, axes)
        nskin = np.einsum("ij,kj->ik", skin, axes)
        return (
            (npad.max(0) < nskin.min(0) - 1e-10) | (nskin.max(0) < npad.min(0) - 1e-10)
        ).any()

    for f, face in zip(fr, fi):
        skin = sweep.frames[[f, min(f + 1, len(sweep.frames) - 1)]][
            :, sweep.faces[face]
        ].reshape(6, 3)
        if (
            (np.einsum("ij,kj->ik", skin, planes[:, :3]) + planes[:, 3]).min(0) > 1e-8
        ).any():
            continue
        a, b, c = skin[ijk].transpose(1, 0, 2)
        if separates(skin, np.cross(b - a, c - a)):
            continue
        se = skin[ij[:, 1]] - skin[ij[:, 0]]
        if not any(separates(skin, np.cross(e, pe)) for e in se):
            return False
    return True
