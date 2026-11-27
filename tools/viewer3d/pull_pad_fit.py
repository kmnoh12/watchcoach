"""Signed vertical clearance to the actual seat crown / underside of a horizontal roller."""

import numpy as np
from bench_fit import top_gap
from body_fit import contact_region


def vertical_gap(skin, base, role, layers):
    # top_gap looks down at the crown. Turn the scene over for an overhead roller;
    # a proper rotation, not a reflection, preserves the outward face winding.
    flip = np.array([1.0, -1.0, -1.0]) if role == "thigh_roller" else np.ones(3)
    vertices, faces, offset = [], [], 0
    for v, t in layers:
        vertices.append(v * flip)
        faces.append(np.asarray(t).reshape(-1, 3) + offset)
        offset += len(v)
    anatomy = contact_region(base, role)[0]
    return top_gap(
        (skin[:, anatomy] * flip).reshape(-1, 3, 3),
        np.vstack(vertices),
        np.vstack(faces),
    )


def axial_gap(frames, base, role, layers, outward):
    """Physical gap along the cushion travel axis (world Y or Z, never the box)."""
    up = np.asarray(outward, dtype=float)
    x = np.array([1., 0., 0.])
    assert abs(np.dot(x, up)) < 1e-8 and np.isclose(np.linalg.norm(up), 1.)
    basis = np.stack([x, np.cross(up, x), up])
    vs, ts, offset = [], [], 0
    for v, t in layers:
        vs.append(v @ basis.T)
        ts.append(np.asarray(t).reshape(-1, 3) + offset)
        offset += len(v)
    anatomy = contact_region(base, role)[0]
    body = np.einsum('fvj,ij->fvi', frames, basis)
    return top_gap(body[:, anatomy].reshape(-1, 3, 3), np.vstack(vs), np.vstack(ts))
