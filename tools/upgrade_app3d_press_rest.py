"""Overlay the press and arm machine exteriors on the finished new-hand bundle."""

import argparse
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from upgrade_app3d_adjust_bench import HERE, append_batch, load
from part_registry import MAT_ACCENT, MAT_CHROME, MAT_FRAME, MAT_PAD, MAT_RUBBER, MAT_SILVER
from scene_lat_parts import palette
from upgrade_app3d_lower_sled import compact_mitre
from upgrade_app3d_machines import decompose_frames, strip_fake_animation
from upgrade_app3d_pull_rest import exterior as pull_exterior
from upgrade_app3d_pull_stations import world
from upgrade_app3d_rest_bars import check_round_target, round_parts
from upgrade_app3d_rest_cables import round_parts as cable_parts
from upgrade_app3d_rest_pull_stations import extent_over_hull, scene_shell
from upgrade_app3d_row_pads import indexed_receiver

TARGETS = "press_rest_targets.json"
SOURCE = "scene_press_rest_source.json"
REPORT = "press_rest_fit.json"
CABLES = {"cable_segment__001": ("cable_segment", MAT_RUBBER, 5, 1)}
ROUND = {
    "bar_collar__007": ("bar_collar__001", MAT_RUBBER),
    "bar_sleeve__003": ("bar_sleeve__003", MAT_CHROME),
    "footplate__004": ("hand_grip", MAT_RUBBER),
    "frame_rail__005": ("handle_stem", MAT_FRAME),
    "handle_branch__003": ("handle_stem", MAT_CHROME),
    "handle_collar__001": ("bar_collar__001", MAT_CHROME),
    "handle_stem__001": ("handle_stem", MAT_CHROME),
    "handle_support__006": ("handle_stem", MAT_CHROME),
    "lever_arm__008": ("handle_stem", MAT_ACCENT),
    "loading_horn__002": ("bar_sleeve__003", MAT_CHROME),
    "sleeve_shoulder__004": ("sleeve_shoulder__004", MAT_SILVER),
    "hand_grip__001": ("row_grip", MAT_RUBBER),
    "hand_grip__002": ("row_grip", MAT_RUBBER),
    "hand_grip__003": ("row_grip", MAT_RUBBER),
    "hand_grip__008": ("hand_grip", MAT_RUBBER),
}
CAPS = {"handle_end_cap": "handle_end_cap", "horn_end_cap": "handle_end_cap", "pivot_cover": "pivot_cover"}
SHELLS = {
    "arch_joint": "frame_crossbeam", "base_beam": "base_runner", "base_crossfoot": "base_runner",
    "base_runner": "base_runner", "frame_brace": "frame_crossbeam", "frame_bridge": "frame_crossbeam",
    "frame_crossbeam": "frame_crossbeam", "frame_foot": "base_runner", "frame_gusset": "frame_crossbeam",
    "frame_post": "frame_crossbeam", "frame_rail": "frame_crossbeam", "frame_spine": "base_runner",
    "frame_stay": "frame_crossbeam", "lever_arm": "lever_arm", "lever_yoke": "frame_crossbeam",
    "load_arm": "load_arm", "panel_mount": "frame_crossbeam", "pad_post": "frame_crossbeam",
    "pad_support": "frame_crossbeam", "pad_yoke": "frame_crossbeam", "top_beam": "frame_crossbeam",
    "tower_post": "frame_crossbeam", "tower_side_member": "frame_crossbeam",
    "rubber_foot": "rubber_foot", "end_cap": "rubber_foot",
}
ADJUSTER = {"rest_post", "rest_inner", "height_pin"}
SIGN_MATERIALS = {"print": MAT_PAD, "accent": MAT_ACCENT, "silver": MAT_SILVER}


def exterior(key, name, group, old, source):
    role = group.split("__")[0]
    if group in CABLES:
        factor, parts = cable_parts(group, old, source, rounds=CABLES)
        return factor, parts, "cable"
    if group in ROUND:
        shape, material = ROUND[group]
        sides = len(old) // 2
        check_round_target(name, old, sides)
        slot = source[shape]
        size, parts = round_parts(slot, sides, material, True)
        color = slot["rgb"] if material in (MAT_RUBBER, MAT_CHROME, MAT_SILVER) else palette()["casting"]
        if group == "bar_collar__007":
            color = source["hand_grip"]["rgb"]
        elif material == MAT_ACCENT:
            color = palette()["lower_red"]
        return np.ptp(old, axis=0) / size, [(*part, color) for part in parts], "round"
    if group == "footplate__001":
        scale, layers = pull_exterior(group, old, source, source, source)
        return scale, [(v, t, smooth, mat, rgb) for v, t, rgb, mat, smooth in layers], "tread"
    if group == "sign_panel__001":
        layers = [source["pec_deck"][0], *source[key.split("~")[0]][1:]]
        bounds = np.vstack([part["v"] for part in layers])
        scale = np.ptp(old, axis=0) / np.ptp(bounds, axis=0)
        parts = []
        for part in layers:
            finish = part["material"].rsplit("_", 1)[-1].lower()
            material = SIGN_MATERIALS.get(finish, MAT_RUBBER)
            parts.append((np.asarray(part["v"]), part["t"], False, material, part["rgb"]))
        return scale, parts, "sign"
    if role in CAPS:
        slot = source[CAPS[role]]
        factor, verts = scene_shell(old, slot, cap=True)
        return factor, [(verts, slot["t"], any(slot["smooth"]), MAT_SILVER, slot["rgb"])], "cap"
    slot = source[SHELLS[role]]
    verts = np.asarray(slot["v"])
    size = np.ptp(verts, axis=0)
    if len(old) == 24:
        fit = compact_mitre(verts, old)
        if fit is None:
            raise ValueError(f"{name}: the original beam ends need their existing profile")
        verts, size = fit
    material = MAT_RUBBER if role in {"rubber_foot", "end_cap"} else MAT_FRAME
    return np.ptp(old, axis=0) / size, [(verts, slot["t"], False, material, slot["rgb"])], "shell"


def fit_rest_stop(objects, emit):
    """Keep the Viking lever's rest preset and install the existing height pin in a real bore."""
    post, insert, pin = (world(objects[name])[0] for name in ("rest_post", "rest_inner", "height_pin"))
    lock = (pin.max(0) + pin.min(0)) / 2
    lock[:2] = (post.max(0) + post.min(0))[:2] / 2
    low, high = post[:, 2].min(), post[:, 2].max()
    tip = insert[:, 2].max()
    start = lock[2] - .065
    result = indexed_receiver(
        emit, "rest_post", "rest_inner", "height_pin", np.array([0., 0., 1.]),
        lock, low, high, tip, np.ptp(post[:, 0]), pin[:, 0].max() - lock[0], start,
    )
    result["hole"] = int(round((lock[2] - result["bottom"]) * 12 / (tip - result["bottom"]) - .5))
    return result


def build_model(key, raw, mapping, source, frames, base):
    if frames is None or frames.shape[1:] != (base["vertices"], 3) or not np.isfinite(frames).all():
        raise ValueError("missing final posed body")
    objects = {obj["name"]: obj for obj in raw["objects"]}
    adjuster = ADJUSTER & mapping.keys()
    if adjuster and adjuster != ADJUSTER:
        raise ValueError("incomplete Viking rest stop assembly")
    rows, audit = [], {}
    for name, (index, group) in mapping.items():
        obj = raw["objects"][index]
        if obj["name"] != name:
            raise ValueError(f"{name}: stale role-map index")
        if name in adjuster:
            continue
        old = np.asarray(obj["verts"]).reshape(-1, 3)
        track = strip_fake_animation(obj["m"])
        pos, quat, scale = decompose_frames(track)
        original = np.asarray(track).reshape(-1, 4, 4)[:, :3, :3].transpose(0, 2, 1)
        if group in CABLES:
            # Keep the axial column exact so a cable's far endpoint cannot drift.
            y = original[:, :, 1] / scale[:, 1, None]
            x = original[:, :, 0] - np.einsum("ij,ij->i", original[:, :, 0], y)[:, None] * y
            x /= np.linalg.norm(x, axis=1)[:, None]
            quat = Rotation.from_matrix(np.stack((x, y, np.cross(x, y)), axis=2)).as_quat()
            for i in range(1, len(quat)):
                if np.dot(quat[i - 1], quat[i]) < 0:
                    quat[i] *= -1
        linear = Rotation.from_quat(quat).as_matrix() * scale[:, None, :]
        if np.any(scale <= 0) or np.einsum("fij,j->fi", abs(linear - original), abs(old).max(0)).max() > .000025:
            raise ValueError(f"{name}: original transform cannot be represented")
        factor, layers, mode = exterior(key, name, group, old, source)
        fitted = np.vstack([v for v, *_ in layers]) * factor
        if extent_over_hull(old, fitted) > .000025:
            raise ValueError(f"{name}: shell leaves the original envelope")
        if mode in {"round", "cable"} and extent_over_hull(fitted, old) > .000025:
            raise ValueError(f"{name}: contact profile changed")
        for v, t, smooth, mat, rgb in layers:
            if mode == "shell" and max(obj["color"]) < .2:
                mat, rgb = MAT_RUBBER, source["rubber_foot"]["rgb"]
            elif mode == "shell" and min(obj["color"]) > .5 and mat == MAT_FRAME and max(rgb) < .1:
                # Retain the existing silver frame sections under the scene satin finish.
                mat, rgb = MAT_SILVER, obj["color"]
            rows.append(dict(name=name, verts=v, tris=np.ravel(t), color=rgb, mat=mat,
                             smooth=smooth, pos=pos, quats=quat, sc=scale * factor))
        audit[name] = dict(group=group, mode=mode, records=len(layers), frames=len(pos))

    if adjuster:
        def emit(name, mesh, at, rotation, dims, material, color):
            v, t = mesh
            rows.append(dict(name=name, verts=v, tris=np.ravel(t), color=color, mat=material,
                             smooth=False, pos=np.asarray(at)[None], quats=rotation.as_quat()[None],
                             sc=np.asarray(dims)[None]))
            spec = audit.setdefault(name, dict(group=mapping[name][1], mode="adjuster", records=0, frames=1))
            spec["records"] += 1

        audit_lock = fit_rest_stop(objects, emit)
        audit["rest_inner"]["lock"] = audit_lock
    return rows, audit


def upgrade(view):
    shared = load(HERE / "scene_lower_sled_source.json")
    for filename, roles in (
        ("scene_rest_cable_source.json", ("cable_segment", "rubber_foot")),
        ("scene_rest_bar_source.json", ("bar_collar__001", "sleeve_shoulder__004")),
        ("scene_rest_pull_source.json", ("lever_arm", "load_arm")),
        ("scene_pull_rest_source.json", ("bar_sleeve__003", "footplate__001", "row_grip")),
    ):
        src = load(HERE / filename)
        shared.update({name: src[name] for name in roles})

    def build(key, raw, mapping, source, frames, base):
        return build_model(key, raw, mapping, {**shared, **source}, frames, base)

    return append_batch(view, targets_file=TARGETS, source_file=SOURCE, report_file=REPORT, build_model=build)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("viewer", type=Path)
    upgrade(parser.parse_args().viewer)
