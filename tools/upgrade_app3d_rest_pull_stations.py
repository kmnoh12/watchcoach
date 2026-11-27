"""Fit gym exteriors to the lever-row and pulldown assemblies and their existing tracks."""

import argparse
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

from upgrade_app3d_adjust_bench import HERE, append_batch, load
from upgrade_app3d_machines import decompose_frames, strip_fake_animation
from upgrade_app3d_rest_bars import check_round_target, round_parts as grip_parts
from upgrade_app3d_rest_cables import round_parts
from part_registry import MAT_CHROME, MAT_FRAME, MAT_RUBBER, MAT_SILVER


TARGETS = "rest_pull_targets.json"
SOURCE = "scene_rest_pull_source.json"
REPORT = "rest_pull_fit.json"
SHELLS = {
    "base_beam": "frame_foot",
    "base_runner": "frame_foot",
    "bearing_mount": "frame_post",
    "footplate_support": "footplate_support",
    "frame_brace": "frame_brace",
    "frame_bridge": "frame_crossbeam",
    "frame_crossbeam": "frame_crossbeam",
    "frame_foot": "frame_foot",
    "frame_gusset": "frame_brace",
    "frame_post": "frame_post",
    "frame_rail": "frame_post",
    "frame_spine": "frame_spine",
    "handle_support": "lever_arm",
    "lever_arm": "lever_arm",
    "load_arm": "load_arm",
    "top_beam": "frame_crossbeam",
}
COVERS = {"handle_end_cap", "pivot_cover"}
RUBBER = {"rubber_foot", "rubber_insert"}
TUBE_SIDE_COUNTS = {
    "hand_grip__001": 8, "hand_grip__002": 8, "hand_grip__003": 8,
    "hand_grip__005": 8, "hand_grip__006": 8, "hand_grip__009": 10,
    "hand_grip__012": 16, "hand_grip__018": 16,
    "handle_bridge__003": 8, "handle_bridge__004": 8, "handle_support__006": 8,
}
UPRIGHT_FOOT_CONTACT = {"seated_row_machine", "seated_row_machine~m=single"}
# A right-handed quarter turn puts the flat plate's top on the seated row's
# local +Y foot-contact plane. Both orientations use the identical WGC2 mesh.
UPRIGHT_FOOTPLATE = Rotation.from_euler("x", -90, degrees=True)
# These square tubes share a 30%-wide mitre in both transverse axes. Use a
# single conservative axial mitre for each scaled instance of the scene shell.
MITRED_TUBES = {"frame_crossbeam__001", "frame_crossbeam__002", "frame_brace__001"}
MITRE = np.array([[.5, .2, .2], [.467, .5, .2], [.467, .2, .5]])
OCTANTS = np.array(np.meshgrid(*[[-1, 1]] * 3)).reshape(3, -1).T
MITRE_PLANES = ConvexHull((MITRE[:, None] * OCTANTS).reshape(-1, 3)).equations


def extent_over_hull(old, new):
    planes = ConvexHull(old).equations
    return float((np.einsum("vi,fi->vf", new, planes[:, :3]) + planes[:, 3]).max())


def scene_shell(old, part, *, cap=False):
    verts = np.asarray(part["v"])
    center = (old.min(0) + old.max(0)) / 2
    dims = np.ptp(verts, axis=0)
    scale = np.ptp(old, axis=0) / dims
    verts = verts + center / scale
    if cap:
        # Match the old inset of the circular hardware into its socket. Only
        # the radial bevel is fitted inside the lower-sided original surface.
        hull = ConvexHull(old).equations
        side = hull[abs(hull[:, 2]) < 1e-5]
        if not len(side) or np.linalg.norm(center[:2]) > 1e-6:
            raise ValueError("cover no longer has a centered cylindrical socket")
        radius = np.einsum("vi,fi->vf", verts[:, :2] * scale[:2], side[:, :2])
        radius = np.maximum(radius.max(0), 1e-12)
        scale[:2] *= min(1., float((-side[:, 3] / radius).min()))
    return scale, verts


def finish_mesh(old, tris):
    """Remove the authored local offset and normalize size for catalogue reuse."""
    dims = np.ptp(old, axis=0)
    center = (old.min(0) + old.max(0)) / 2
    verts = ((old - center) / dims).round(6)
    order = np.lexsort(verts.T[::-1])
    faces = np.argsort(order)[np.asarray(tris).reshape(-1, 3)]
    faces = np.take_along_axis(faces, (faces.argmin(1)[:, None] + np.arange(3)) % 3, axis=1)
    return dims, center, verts[order], faces[np.lexsort(faces.T[::-1])]


def casing(role, source, color):
    """The exact contour is retained on bends, welded clusters and complex grips."""
    rubber_grip = role == "hand_grip" and max(color) < .2
    if role in RUBBER or rubber_grip:
        return source["rubber_foot" if role in RUBBER else role], MAT_RUBBER
    if role in COVERS:
        return source[role], MAT_CHROME if role == "handle_end_cap" else MAT_SILVER
    if role in {"footplate", "footplate_lip"}:
        return source["footplate"], MAT_RUBBER if max(color) < .2 else MAT_SILVER
    if role in {"handle_support", "handle_bridge", "hand_grip"} and max(color) > .35:
        return source["metal_grip"], MAT_CHROME
    if role in {"load_arm", "lever_arm"} and color[0] > .35 and color[1] < .2:
        return source["lever_arm"], MAT_FRAME
    return source[SHELLS.get(role, "frame_crossbeam")], MAT_SILVER if min(color) > .3 else MAT_FRAME


def exterior_shape(key, role, group, old, source):
    orientation = None
    ref = old
    if role == "footplate" and key in UPRIGHT_FOOT_CONTACT:
        orientation = UPRIGHT_FOOTPLATE
        ref = orientation.inv().apply(old)
    if role in {"footplate", "footplate_lip"} | RUBBER | COVERS:
        shape = source["footplate" if role == "footplate_lip" else role]
    elif role in SHELLS:
        shape = source[SHELLS[role]]
    else:
        return None
    if len(old) not in (8, 16, 24, 56):
        return None
    factor, verts = scene_shell(ref, shape, cap=role in COVERS)
    if group in MITRED_TUBES:
        dims = np.ptp(np.asarray(shape["v"]), axis=0)
        rho = np.einsum("vi,fi->vf", verts / dims, MITRE_PLANES[:, :3]) / -MITRE_PLANES[:, 3]
        verts = verts / np.maximum(1., rho.max(1))[:, None]
    # Rounded boxes with tighter original corners use their existing mesh.
    if extent_over_hull(ref, verts * factor) > .00001:
        return None
    smooth = shape["smooth"]
    return orientation, factor, verts, shape["t"], any(smooth) if isinstance(smooth, list) else smooth


def build_model(key, raw, mapping, source, frames, base):
    if frames is None or not np.isfinite(frames).all():
        raise ValueError("missing final posed body")
    rows, audit = [], {}
    for name, (index, group) in mapping.items():
        role = group.split("__")[0]
        obj = raw["objects"][index]
        if obj["name"] != name:
            raise ValueError(f"{name}: stale role-map index")
        old = np.asarray(obj["verts"]).reshape(-1, 3)
        track = strip_fake_animation(obj["m"])
        p, q, s = decompose_frames(track)
        if np.any(s <= 0) or np.any(np.ptp(old, axis=0) < .0001):
            raise ValueError(f"{name}: invalid exterior bounds or track")
        # Asset exporter stores TRS matrices. Refuse any actual shear before
        # using a local envelope to prove the same result between motion keys.
        matrix = np.asarray(track).reshape(-1, 4, 4)
        linear = Rotation.from_quat(q).as_matrix() * s[:, None, :]
        if not np.allclose(linear, matrix[:, :3, :3].transpose(0, 2, 1), atol=3e-5):
            raise ValueError(f"{name}: sheared original transform")
        finish, mat = casing(role, source, obj["color"])
        orientation = None
        center = np.zeros(3)
        if role == "cable_segment" or group in TUBE_SIDE_COUNTS:
            if role == "cable_segment":
                factor, parts = round_parts(group, old, source)
            else:
                sides = TUBE_SIDE_COUNTS[group]
                check_round_target(name, old, sides)
                size, layers = grip_parts(source["hand_grip"], sides, mat, True)
                factor = np.ptp(old, axis=0) / size
                parts = [(v, t, smooth, material, finish["rgb"]) for v, t, smooth, material in layers]
            mode = "profile"
        else:
            shape = exterior_shape(key, role, group, old, source)
            if shape is not None:
                orientation, factor, verts, tris, smooth = shape
                parts = [(verts, tris, smooth, mat, finish["rgb"])]
                mode = "scene"
            else:
                # Moving compound objects keep their local pivot. Centering a
                # static contour makes mirrored duplicates reusable by size.
                if len(p) == 1:
                    factor, center, verts, tris = finish_mesh(old, obj["tris"])
                else:
                    factor = np.ptp(old, axis=0)
                    verts, tris = old / factor, obj["tris"]
                parts = [(verts, tris, False, mat, finish["rgb"])]
                mode = "finish"
        ref = old if orientation is None else orientation.inv().apply(old)
        fitted = np.vstack([v * factor + center for v, *_ in parts])
        excess = extent_over_hull(ref, fitted)
        if excess > .00001:
            raise ValueError(f"{name}: exterior exceeds the original contact envelope")
        if orientation is not None:
            q = (Rotation.from_quat(q) * orientation).as_quat()
            s = s[:, [0, 2, 1]]
        p = p + np.einsum("fij,j->fi", linear, center)
        for verts, tris, smooth, material, color in parts:
            rows.append(dict(name=name, verts=verts, tris=np.ravel(tris), smooth=smooth,
                             mat=material, color=color, pos=p, quats=q, sc=s * factor))
        audit[name] = dict(group=group, type=mode, frames=len(p), records=len(parts),
                           outward_mm=round(max(0., excess) * 1000, 6))
    return rows, audit


def load_shared():
    cable = load(HERE / "scene_rest_cable_source.json")
    bench = load(HERE / "scene_rest_bench_source.json")
    return {"frame_post": cable["frame_post"], "frame_brace": cable["frame_brace"],
            "frame_spine": bench["frame_spine"], "rubber_foot": cable["rubber_foot"],
            "rubber_insert": cable["rubber_foot"], "cable_segment": cable["cable_segment"],
            "metal_grip": cable["lat_bar"]}


def upgrade(view):
    shared = load_shared()

    def build(key, raw, mapping, source, frames, base):
        return build_model(key, raw, mapping, {**source, **shared}, frames, base)

    return append_batch(view, targets_file=TARGETS, source_file=SOURCE,
                        report_file=REPORT, build_model=build)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("viewer", type=Path)
    upgrade(parser.parse_args().viewer)
