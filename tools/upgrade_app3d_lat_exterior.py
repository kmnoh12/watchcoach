"""Fit scene cable and handle exteriors to the seven stage-one lat stations."""

from functools import lru_cache
import json
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

from fixed_pad_contact import penetration
from part_catalog import _ensure_outward
from part_registry import MAT_CHROME, MAT_RUBBER, MAT_SILVER


HERE = Path(__file__).resolve().parent / "viewer3d"
TUBES = {
    "cable_segment__001": ("cable_segment", 8, 1),
    "cable_segment__004": ("cable_segment", 8, 2),
    "hand_grip__004": ("hand_grip", 8, 2),
    "d_handle_side__001": ("handle_support", 8, 2),
    "d_handle_bridge__001": ("handle_support", 8, 2),
    "lat_bar__002": ("lat_bar", 8, 2),
    "handle_branch__002": ("handle_support", 8, 2),
    "frame_brace__006": ("handle_support", 12, 2),
    "rope_cord__003": ("rope_cord", 8, 2),
    "rope_grip__002": ("rope_cord", 8, 2),
    "rope_connector__002": ("rope_connector", 8, 2),
}
HARDWARE = {
    "rope_ferrule__002": ("rope_ferrule", MAT_CHROME),
    "rope_stop__003": ("rope_stop", MAT_RUBBER),
    "swivel_collar__002": ("swivel_collar", MAT_CHROME),
}


@lru_cache(maxsize=1)
def inputs():
    def load(name):
        return json.loads((HERE / name).read_text())

    source = load("scene_rest_cable_source.json")
    source.update(load("scene_lat_exterior_source.json"))
    return load("lat_exterior_targets.json"), source


def tube(old, source, sides, axis):
    from upgrade_app3d_rest_cables import round_profile

    # Work in axial-Z coordinates. Keep the old end planes and cross-section
    # corners, placing the scene's additional profile samples on the old facets.
    order = [0, 2, 1] if axis == 1 else [0, 1, 2]
    signs = np.array([1, -1, 1]) if axis == 1 else np.ones(3)
    ref = old[:, order] * signs
    lo, hi = ref.min(0), ref.max(0)
    center = (lo[:2] + hi[:2]) / 2
    radius = (hi[0] - lo[0]) / 2
    profile = round_profile(source, sides) * radius + center
    n = len(profile)
    verts = np.vstack((np.c_[profile, np.full(n, lo[2])], np.c_[profile, np.full(n, hi[2])],
                       [*center, lo[2]], [*center, hi[2]]))
    verts = (verts * signs)[:, order].round(7)
    def outside(points, boundary):
        planes = ConvexHull(boundary).equations
        return np.max(np.einsum("vi,pi->vp", points, planes[:, :3]) + planes[:, 3])

    if max(outside(verts, old), outside(old, verts)) > 1e-5:
        raise ValueError("scene profile would move the existing tube contact surface")
    i = np.arange(n)
    j = np.roll(i, -1)
    faces = np.vstack((np.c_[i, i+n, j+n], np.c_[i, j+n, j],
                       np.c_[np.full(n, 2*n), i, j], np.c_[np.full(n, 2*n+1), j+n, i+n]))
    return verts, _ensure_outward(verts, faces)


def fit_exterior(key, raw, entries, frames, faces):
    from upgrade_app3d_rest_cables import CARABINER_LINKS, carabiner, carabiner_clearance, hardware_03

    targets, source = inputs()
    mapping = targets[key]
    objects = {o["name"]: o for o in raw["objects"]}
    tracks = {e["name"]: e for e in entries}
    if not mapping.keys() <= objects.keys():
        raise ValueError("lat exterior targets no longer match the original object names")
    replacements = {}
    phase = np.asarray(raw["acts"], dtype="<f4")

    def put(entry, group, verts, tris, shape, mat, smooth=True, **pose):
        return dict(entry, catalog_id=group, verts=np.asarray(verts), tris=np.ravel(tris),
                    color=source[shape]["rgb"], mat=mat, smooth=smooth, **pose)

    def check_skin(entry, before, after):
        if np.max(np.ptp(entry["sc"], axis=0)) > 3e-5:
            raise ValueError(f"{entry['name']}: unexpected changing hardware scale")
        swept = penetration(frames, faces, phase, phase, before, after,
                            entry["pos"], entry["quats"])
        if swept["added_hull_mm"] > 10:
            raise ValueError(f"{entry['name']}: scene exterior adds visible body overlap")

    for name, group in mapping.items():
        if group == "carabiner_link__001":
            continue
        if name not in tracks:
            raise ValueError(f"{name}: missing stage-one track")
        entry = tracks[name]
        obj = objects[name]
        old = np.asarray(obj["verts"]).reshape(-1, 3)
        if group in TUBES:
            shape, sides, axis = TUBES[group]
            # Use the fitted stage-one cable as the mounting reference; preserve
            # its adjusted load socket, actual outlet and all phase keys.
            if shape == "cable_segment":
                old = entry["verts"]
            verts, tris = tube(old, source[shape], sides, axis)
            mat = entry["mat"]
            if group == "rope_connector__002":
                mat = MAT_SILVER
            elif shape == "handle_support":
                mat = MAT_CHROME
            elif group == "lat_bar__002" and name == "bar_main":
                mat = MAT_RUBBER
            finish = "hand_grip" if group == "lat_bar__002" and mat == MAT_RUBBER else shape
            updated = put(entry, group, verts, tris, finish, mat)
            if group == "frame_brace__006":
                scale = entry["sc"][0]
                check_skin(entry, entry["verts"] * scale, verts * scale)
        elif group in HARDWARE:
            shape, mat = HARDWARE[group]
            factor, parts = hardware_03(shape, old, source)
            verts, tris, _, _, _ = parts[0]
            scale = entry["sc"][0]
            check_skin(entry, old * scale, verts * factor * scale)
            updated = put(entry, group, verts, tris, shape, mat, sc=entry["sc"] * factor)
        elif group == "cable_lug__002":
            # The original V-bar plate has a through-hole for the hook. Keep
            # this functional profile and apply the scene's hardware finish.
            updated = put(entry, group, old, obj["tris"], "carabiner_link_ring", MAT_SILVER, False)
        else:
            # The rope's original clip is a single capsule, in local XZ. Size
            # the scene ring to its end faces, including the present cable tip.
            if group != "rope_connector__003" or name != "rope_clip":
                raise ValueError(f"{name}: unexpected lat exterior group {group}")
            ring = np.asarray(source["carabiner_link_ring"]["v"])
            offset = (old.min(0) + old.max(0)) / 2
            rot = Rotation.from_euler("z", -90, degrees=True)
            factor = np.ptp(old, axis=0)[[1, 0, 2]] / np.ptp(ring, axis=0)
            rotation = Rotation.from_quat(entry["quats"])
            if not np.allclose(entry["sc"], 1, atol=1e-5):
                raise ValueError("rope clip is no longer rigid")
            pos = entry["pos"] + rotation.apply(offset)
            q = (rotation * rot).as_quat()
            updated = []
            for shape in ("carabiner_link_ring", "carabiner_link_gate"):
                mesh = source[shape]
                updated.append(put(entry, group, mesh["v"], mesh["t"], shape, MAT_CHROME,
                                   pos=pos, quats=q, sc=np.broadcast_to(factor, pos.shape)))
            fitted = np.concatenate([rot.apply(row["verts"] * factor) + offset for row in updated])
            check_skin(entry, old, fitted)
            replacements[name] = updated
            continue
        replacements[name] = [updated]

    attachments = [objects[name] for name in CARABINER_LINKS
                   if mapping.get(name) == "carabiner_link__001"]
    if attachments:
        ring = carabiner(raw, attachments, source)
        carabiner_clearance(attachments, ring, frames, faces, phase, phase)
        name = tracks["carabiner_main"]["name"]
        replacements[name] = [dict(row, name=name, role="CLEANUP", catalog_id="carabiner_link__001")
                              for row in ring]
    return replacements
