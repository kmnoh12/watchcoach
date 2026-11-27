"""Compare fixed support / bar-synchronous soft pad envelopes on the final posed skin."""

import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation, Slerp


def penetration(frames, skin_faces, times, samples, obj, replacement, positions, quats):
    """Old convex solid vs conservative outer hull of replacement (the wrap bore is ignored).
    Sample vertices, edge midpoints and triangle centres at pose keys and half steps.
    Mesh arguments are local metres after scaling; padding is not moved to disguise collisions.
    """
    old = np.asarray(obj)
    new = np.asarray(replacement)
    planes = [np.unique(ConvexHull(v).equations.round(10), axis=0) for v in [old, new]]
    lo = np.minimum(new.min(0), old.min(0))
    hi = np.maximum(new.max(0), old.max(0))
    edges = np.unique(
        np.sort(skin_faces[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2), axis=1), axis=0
    )
    times = np.asarray(times)
    samples = np.asarray(samples)
    keys = np.unique(np.r_[times, samples])
    ticks = np.sort(np.r_[keys, (keys[1:] + keys[:-1]) / 2])
    ticks = np.clip(ticks, times[0], times[-1])
    if len(positions) > 1:
        grid = (
            samples
            if len(positions) == len(samples)
            else np.linspace(0, 1, len(positions))
        )
        t = ticks.clip(grid[0], grid[-1])
        rot = Slerp(grid, Rotation.from_quat(quats))(t).as_matrix()
        pos = np.column_stack([np.interp(t, grid, c) for c in positions.T])
    else:
        rot = np.broadcast_to(
            Rotation.from_quat(quats[0]).as_matrix(), (len(ticks), 3, 3)
        )
        pos = np.broadcast_to(positions[0], (len(ticks), 3))
    out = np.zeros(3)
    for i, t in enumerate(ticks):
        j = np.searchsorted(times, t, side="right").clip(1, len(times) - 1)
        w = (t - times[j - 1]) / (times[j] - times[j - 1])
        f = frames[j - 1] + w * (frames[j] - frames[j - 1])
        local = np.einsum("vj,ji->vi", f - pos[i], rot[i])
        pts = np.vstack((local, local[edges].mean(1), local[skin_faces].mean(1)))
        pts = pts[((pts >= lo) & (pts <= hi)).all(1)]
        if not len(pts):
            continue
        depths = [
            np.maximum(0, -(np.einsum("vi,pi->vp", pts, p[:, :3]) + p[:, 3]).max(1))
            for p in planes
        ]
        a, b = depths
        out = np.maximum(out, [a.max(), b.max(), (b - a).max()])
    return dict(
        samples=len(ticks),
        old_mm=round(1000 * out[0], 3),
        new_hull_mm=round(1000 * out[1], 3),
        added_hull_mm=round(1000 * out[2], 3),
    )
